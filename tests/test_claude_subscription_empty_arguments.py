"""A tool call without arguments is accepted; tool argument text that is not valid JSON fails as ProviderError.

A tool call without arguments streams one input_json_delta whose partial_json is the empty string. Such
a call must yield the arguments {} and must reach Hermes with the arguments text "{}". Argument
fragments that do not form valid JSON must fail with ProviderError("invalid tool argument JSON"), so
that the client writes a stream audit, instead of the generic JSONDecodeError protocol error.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI,
no network, a temporary HERMES_HOME). Only the model-runtime child is rerouted to the small event
producer below. All identifiers, texts and argument values are synthetic.
"""
import copy
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
stream_events = importlib.import_module("subscription_plugin.stream_events")
MODEL = provider.MODEL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())

INVALID = "invalid tool argument JSON"
NOT_OBJECT = "tool arguments must be an object"
PROTOCOL = "runtime startup, I/O or malformed protocol: JSONDecodeError"  # the error before this fix
TOOL_NAME = "list_items"
NO_ARGUMENTS_TOOL = {"type": "function", "function": {
    "name": TOOL_NAME, "description": "Synthetic tool without parameters",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}
TOOL_RESULT = "SYNTHETIC LIST RESULT"
ARGUMENT_CANARY = "/SYNTHETIC-ARGUMENT-CANARY-0d4e"  # must never appear in a stream audit
# Fragments that do not form valid JSON: an unterminated object and a trailing comma.
INVALID_FRAGMENTS = ['{"path": "' + ARGUMENT_CANARY + '", ']
NOT_OBJECT_FRAGMENTS = ["[1, ", "2]"]


def stream_event(kind, **fields):
    return {"type": "stream_event", "event": {"type": kind, **fields}, "parent_tool_use_id": None}


class MessageTests(unittest.TestCase):
    """The parser alone: one tool_use block, its argument fragments, then content_block_stop."""

    def tool_message(self, fragments):
        message = stream_events.Message({MODEL})
        message.feed(stream_event("message_start", message={"id": "msg_unit", "model": MODEL}))
        message.feed(stream_event("content_block_start", index=0, content_block={
            "type": "tool_use", "id": "toolu_unit", "name": client.PREFIX + TOOL_NAME, "input": {}}))
        for fragment in fragments:
            message.feed(stream_event("content_block_delta", index=0,
                                      delta={"type": "input_json_delta", "partial_json": fragment}))
        message.feed(stream_event("content_block_stop", index=0))
        return message

    def test_an_empty_or_whitespace_only_fragment_yields_empty_arguments_and_clears_the_fragments(self):
        for fragments in ([""], ["", ""], ["   "], [" ", "\n\t\r "]):
            with self.subTest(fragments=fragments):
                call = self.tool_message(fragments).calls[0]
                self.assertEqual(call["arguments"], {})
                # Cleared, so client.py forwards json.dumps({}) instead of the empty text.
                self.assertEqual(call["fragments"], [])

    def test_a_complete_message_with_a_call_without_arguments_matches_its_snapshot(self):
        message = stream_events.Message({MODEL})
        message.feed(stream_event("message_start", message={"id": "msg_unit", "model": MODEL}))
        block = {"type": "tool_use", "id": "toolu_unit", "name": client.PREFIX + TOOL_NAME, "input": {}}
        message.feed(stream_event("content_block_start", index=0, content_block=block))
        message.feed(stream_event("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": ""}))
        message.feed({"type": "assistant", "message": {"id": "msg_unit", "model": MODEL, "content": [block]},
                      "parent_tool_use_id": None})
        message.feed(stream_event("content_block_stop", index=0))
        message.feed(stream_event("message_delta", delta={"stop_reason": "tool_use"}))
        message.feed(stream_event("message_stop"))
        self.assertTrue(message.done)
        self.assertEqual(message.facts()["calls"], [{"id": "toolu_unit", "name": client.PREFIX + TOOL_NAME, "arguments": {}}])
        self.assertEqual(message.escapes, [])

    def test_fragments_that_are_not_valid_json_raise_provider_error(self):
        # U+00A0 is whitespace to str.strip() but not JSON whitespace (RFC 8259), so it is not "no arguments".
        for fragments in (INVALID_FRAGMENTS, ['{"path"', ": }"], ["not json"], ["{}", "{}"], ["\u00a0"]):
            with self.subTest(fragments=fragments):
                with self.assertRaises(client.ProviderError) as raised:
                    self.tool_message(fragments)
                self.assertIs(type(raised.exception), client.ProviderError)
                self.assertEqual(str(raised.exception), INVALID)

    def test_valid_json_that_is_not_an_object_still_raises_the_unchanged_error(self):
        for fragments in (NOT_OBJECT_FRAGMENTS, ['"text"'], ["null"], ["3"], [" [] "]):
            with self.subTest(fragments=fragments):
                with self.assertRaises(client.ProviderError) as raised:
                    self.tool_message(fragments)
                self.assertEqual(str(raised.exception), NOT_OBJECT)

    def test_normal_argument_fragments_are_parsed_and_kept_unchanged(self):
        fragments = ['{"pa', 'th": "/synthetic/a"', "}"]
        call = self.tool_message(fragments).calls[0]
        self.assertEqual(call["arguments"], {"path": "/synthetic/a"})
        self.assertEqual(call["fragments"], fragments)  # the client still forwards the streamed fragments

    def test_a_call_with_no_delta_keeps_the_block_input(self):
        call = self.tool_message([]).calls[0]
        self.assertEqual((call["arguments"], call["fragments"]), ({}, []))


class EmptyArgumentsClientTests(unittest.TestCase):
    """Replayed streams through the client, as in test_claude_subscription_tool_progress.py."""

    def setUp(self):
        real = subprocess.Popen
        def reroute(argv, *args, **kwargs):
            # The provider harness turns the synthetic CLI into its own script; send model runs here.
            if "--synthetic-runtime" in argv and "--version" not in argv:
                argv = [SCRIPT if part == PROVIDER_SCRIPT else part for part in argv]
            return real(argv, *args, **kwargs)
        guard = patch("subprocess.Popen", reroute)
        guard.start()
        self.addCleanup(guard.stop)
        provider.ClientTests.setUp(self)  # temporary HERMES_HOME = HOME = self.directory
        self.sessions = self.directory / "sessions"

    def messages(self, text):
        return [{"role": "system", "content": "Synthetic system"}, {"role": "user", "content": text}]

    def continuation(self, call_id, result, **kwargs):
        messages = copy.deepcopy(self.c._history.messages)
        messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
        return self.c.create(model=MODEL, messages=messages, tools=[NO_ARGUMENTS_TOOL], **kwargs)

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def only_audit(self):
        files = self.audits()
        self.assertEqual(len(files), 1, files)
        return files[0], json.loads(files[0].read_text())

    def test_a_streamed_call_without_arguments_reaches_hermes_as_an_empty_object(self):
        chunks = list(self.c.create(model=MODEL, messages=self.messages("__no_arguments__"),
                                    tools=[NO_ARGUMENTS_TOOL], stream=True))
        deltas = [d for chunk in chunks for d in getattr(chunk.choices[0].delta, "tool_calls", None) or []]
        self.assertEqual([(d.index, d.id, d.function.name) for d in deltas if getattr(d, "id", None)],
                         [(0, "toolu_noargs", TOOL_NAME)])
        text = "".join(d.function.arguments for d in deltas)
        self.assertEqual(text, "{}")
        self.assertEqual(json.loads(text), {})
        self.assertEqual(chunks[-1].choices[0].finish_reason, "tool_calls")
        final = list(self.continuation("toolu_noargs", TOOL_RESULT, stream=True))
        self.assertEqual("".join(getattr(c.choices[0].delta, "content", None) or "" for c in final), "Got " + TOOL_RESULT)
        self.assertEqual(final[-1].choices[0].finish_reason, "stop")
        parked = [a for a in self.c.audit if a["stage"] == "tool_parked"]
        self.assertEqual([(a["tool_use_id"], a["name"], a["arguments"]) for a in parked], [("toolu_noargs", TOOL_NAME, {})])
        self.assertEqual(self.audits(), [])

    def test_a_non_streamed_call_without_arguments_reaches_hermes_as_an_empty_object(self):
        first = self.c.create(model=MODEL, messages=self.messages("__no_arguments__"), tools=[NO_ARGUMENTS_TOOL])
        self.assertEqual(first.choices[0].finish_reason, "tool_calls")
        call = first.choices[0].message.tool_calls[0]
        self.assertEqual((call.id, call.function.name), ("toolu_noargs", TOOL_NAME))
        self.assertEqual(json.loads(call.function.arguments), {})
        final = self.continuation(call.id, TOOL_RESULT)
        self.assertEqual((final.choices[0].message.content, final.choices[0].finish_reason), ("Got " + TOOL_RESULT, "stop"))
        self.assertEqual(self.audits(), [])

    def failing_request(self, trigger, text):
        with self.assertLogs(client.log.name, "WARNING") as logs, \
                self.assertRaisesRegex(client.ProviderError, "^" + re.escape(text) + "$") as raised:
            self.c.create(model=MODEL, messages=self.messages(trigger), tools=[NO_ARGUMENTS_TOOL])
        self.assertIs(type(raised.exception), client.ProviderError)
        self.assertTrue(self.c.is_closed())
        path, record = self.only_audit()
        self.assertTrue(any(path.name in line for line in logs.output))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(record["error"], {"class": "ProviderError", "message": text})
        self.assertNotIn(PROTOCOL, path.read_text())
        self.assertNotIn(ARGUMENT_CANARY, path.read_text())  # tool arguments never enter the audit
        message = record["stream"]["messages"][-1]
        self.assertEqual(message["id"], "msg_bad")
        self.assertIn(["content_block_stop", 1], message["events"])
        return record

    def test_invalid_argument_json_raises_provider_error_and_writes_a_stream_audit(self):
        record = self.failing_request("__invalid_arguments__", INVALID)
        self.assertEqual(record["stream"]["drain"]["ended"], "complete")
        self.assertEqual([a for a in self.c.audit if a["stage"] == "tool_parked"], [])

    def test_argument_json_that_is_not_an_object_still_raises_the_unchanged_error(self):
        self.failing_request("__not_object_arguments__", NOT_OBJECT)


def synthetic_runtime(argv):
    """Inert event producer for tool calls with empty, invalid or non-object arguments; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    tools = [client.PREFIX + TOOL_NAME] if config["mcpServers"] else []
    model = argv[argv.index("--model") + 1]
    bridge = None
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit(stream_event(kind, **kwargs))
    def tool_message(message_id, tool_use_id, fragments):
        value = {"type": "tool_use", "id": tool_use_id, "name": client.PREFIX + TOOL_NAME, "input": {}}
        ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})
        ev("content_block_start", index=0, content_block=value)
        for fragment in fragments:
            ev("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": fragment})
        emit({"type": "assistant", "message": {"id": message_id, "model": model, "content": [value],
              "usage": {"output_tokens": 1}}, "parent_tool_use_id": None})
        ev("content_block_stop", index=0)
        ev("message_delta", delta={"stop_reason": "tool_use"}, usage={"output_tokens": 2})
        ev("message_stop")
    def text_message(message_id, value):
        ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})
        ev("content_block_start", index=0, content_block={"type": "text", "text": ""})
        ev("content_block_delta", index=0, delta={"type": "text_delta", "text": value})
        emit({"type": "assistant", "message": {"id": message_id, "model": model,
              "content": [{"type": "text", "text": value}], "usage": {"output_tokens": 1}}, "parent_tool_use_id": None})
        ev("content_block_stop", index=0)
        ev("message_delta", delta={"stop_reason": "end_turn"}, usage={"output_tokens": 2})
        ev("message_stop")
    def result():
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
              "modelUsage": {model: {"canonicalModel": model, "provider": "firstParty"}}})
    def open_bridge():
        cfg = config["mcpServers"]["hermes"]
        process = subprocess.Popen([cfg["command"]] + cfg["args"], env=cfg["env"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True)
        process.stdin.write(json.dumps({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}) + "\n")
        process.stdin.flush()
        process.stdout.readline()
        return process
    for ordinal, line in enumerate(sys.stdin):
        content = json.loads(line)["message"]["content"]
        prompt = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if b.get("type") == "text")
        if ordinal == 0:
            emit({"type": "system", "subtype": "init", "model": model, "tools": tools, "apiKeySource": "none",
                  "claude_code_version": "2.1.283"})
        if "__no_arguments__" in prompt:
            tool_message("msg_noargs_1", "toolu_noargs", [""])
            bridge = open_bridge()
            bridge.stdin.write(json.dumps({"id": 2, "method": "tools/call",
                                           "params": {"name": TOOL_NAME, "arguments": {}}}) + "\n")
            bridge.stdin.flush()
            value = json.loads(bridge.stdout.readline())["result"]["content"][0]["text"]
            emit({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_noargs", "content": value}]}, "parent_tool_use_id": None})
            text_message("msg_noargs_2", "Got " + value)
            result()
        elif "__invalid_arguments__" in prompt:
            tool_message("msg_bad", "toolu_bad", INVALID_FRAGMENTS)
            result()
        elif "__not_object_arguments__" in prompt:
            tool_message("msg_bad", "toolu_bad", NOT_OBJECT_FRAGMENTS)
            result()
    if bridge:
        bridge.terminate()
        bridge.wait(timeout=2)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
