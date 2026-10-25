"""tool_progress events are accepted; a non-JSON runtime stdout line leaves a bounded, redacted stream audit.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI,
no network, a temporary HERMES_HOME). Only the model-runtime child is rerouted to the small event
producer below. Every event shape follows the Claude Code Agent SDK TypeScript reference
(SDKToolProgressMessage, SDKAssistantMessage, SDKUserMessage, SDKPartialAssistantMessage); all
identifiers, texts and secret-shaped values are synthetic.
"""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
MODEL, TOOL = provider.MODEL, provider.TOOL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())

MALFORMED = "malformed runtime event or unexpected subagent"
PROTOCOL = "runtime startup, I/O or malformed protocol: JSONDecodeError"
SECRET = "SYNTHETIC-SECRET-VALUE-5e9a1c"   # secret-shaped synthetic value, replaced by the test redaction
MARKER = "[test-redacted]"
WORDS = ["kestrel", "quartzite", "lanternfish", "marigold", "tamarind", "ziggurat"]  # appear nowhere else in an audit
# A non-JSON line longer than 200 bytes, with the secret-shaped value inside its first 200 bytes.
LINE = ("Synthetic diagnostic: token=" + SECRET + " " + " ".join(WORDS * 12)).encode()
TOOL_RESULT = "SYNTHETIC TOOL RESULT"


def progress(tool_use_id, parent=None, **extra):
    """An SDKToolProgressMessage; every field is synthetic."""
    return {"type": "tool_progress", "tool_use_id": tool_use_id, "tool_name": client.PREFIX + "read_file",
            "parent_tool_use_id": parent, "elapsed_time_seconds": 30, "uuid": "uuid-synthetic",
            "session_id": "session-synthetic", **extra}


def test_redaction(text):
    return text.replace(SECRET, MARKER)


class ToolProgressClientTests(unittest.TestCase):
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
        self.phase = 1
        self.read_log = []  # (request phase, event type, len(_awaiting) when read) per tool_progress event
        original = client.Runtime.read
        def recording(runtime):
            obj = original(runtime)
            if isinstance(obj, dict) and obj.get("type") == "tool_progress":
                self.read_log.append((self.phase, obj, len(self.c._awaiting)))
            return obj
        reader = patch.object(client.Runtime, "read", recording)
        reader.start()
        self.addCleanup(reader.stop)

    def messages(self, text):
        return [{"role": "system", "content": "Synthetic system"}, {"role": "user", "content": text}]

    def continuation(self, response, results):
        messages = copy.deepcopy(self.c._history.messages)
        for call, result in zip(response.choices[0].message.tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        return self.c.create(model=MODEL, messages=messages, tools=[TOOL])

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def only_audit(self):
        files = self.audits()
        self.assertEqual(len(files), 1, files)
        return files[0], json.loads(files[0].read_text())

    def fresh_client(self):
        for path in self.audits():
            path.unlink()
        self.c.close()
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)

    def test_c1_heartbeats_while_hermes_runs_a_parked_call_do_not_fail_the_request(self):
        first = self.c.create(model=MODEL, messages=self.messages("__parked_progress__"), tools=[TOOL])
        self.assertEqual(first.choices[0].finish_reason, "tool_calls")
        call = first.choices[0].message.tool_calls[0]
        self.assertEqual((call.function.name, json.loads(call.function.arguments)), ("read_file", {"path": "/synthetic/a"}))
        time.sleep(1.0)  # Hermes runs the tool; the CLI writes its heartbeats meanwhile
        self.phase = 2
        final = self.continuation(first, [TOOL_RESULT])
        self.assertEqual(final.choices[0].finish_reason, "stop")
        self.assertEqual(final.choices[0].message.content, "Got " + TOOL_RESULT)
        read = [(phase, obj["parent_tool_use_id"], obj.get("heartbeat")) for phase, obj, _ in self.read_log]
        self.assertEqual(read, [(2, "toolu_progress_a", True), (2, None, True)])
        stages = [a["stage"] for a in self.c.audit]
        self.assertEqual(stages, ["launch", "user_input", "init", "tool_parked", "result_delivered",
                                  "result_returned", "result"])
        self.assertEqual(self.audits(), [])
        self.assertFalse(self.c.is_closed())

    def test_c2_progress_variants_are_accepted_and_change_no_message_or_audit_state(self):
        response = self.c.create(model=MODEL, messages=self.messages("__progress_variants__"))
        self.assertEqual(response.choices[0].message.content, "Fine")
        self.assertEqual(response.choices[0].finish_reason, "stop")
        variants = [obj for _, obj, _ in self.read_log]
        self.assertEqual([(o.get("heartbeat"), o.get("subagent_type"), o.get("subagent_retry"), o["parent_tool_use_id"])
                          for o in variants],
                         [(True, None, None, None), (None, "synthetic-agent", None, "toolu_parent"),
                          (None, None, {"attempt": 1}, "toolu_parent"), (True, None, None, None)])
        self.assertEqual([a["stage"] for a in self.c.audit], ["launch", "user_input", "init", "result"])
        self.assertEqual(self.audits(), [])
        self.assertEqual((self.c._pending, self.c._awaiting, self.c._queued), (None, [], {}))

    def test_c2_progress_while_calls_of_the_message_are_still_awaited_is_accepted(self):
        first = self.c.create(model=MODEL, messages=self.messages("__parallel_progress__"), tools=[TOOL])
        self.assertEqual(len(first.choices[0].message.tool_calls), 2)
        self.phase = 2
        final = self.continuation(first, ["RESULT A", "RESULT B"])
        self.assertEqual(final.choices[0].message.content, "RESULT A|RESULT B")
        # Read while the CLI had not yet requested the second call: the awaiting branch did not fire.
        self.assertEqual([(phase, awaiting) for phase, _, awaiting in self.read_log], [(2, 1), (2, 1)])
        self.assertEqual(self.audits(), [])

    def test_c3_subagent_marker_on_message_events_still_fails(self):
        for trigger in ("__subagent_assistant__", "__subagent_user__", "__subagent_stream_event__"):
            with self.subTest(trigger):
                self.fresh_client()
                with self.assertRaisesRegex(client.ProviderError, "^" + re.escape(MALFORMED) + "$"):
                    self.c.create(model=MODEL, messages=self.messages(trigger))
                self.assertTrue(self.c.is_closed())
                self.assertEqual(self.only_audit()[1]["error"]["message"], MALFORMED)

    def test_c4_an_undocumented_event_type_still_fails_as_unknown(self):
        for trigger in ("__undocumented__", "__undocumented_with_parent__"):
            with self.subTest(trigger):
                self.fresh_client()
                with self.assertRaisesRegex(client.ProviderError, r"^unknown runtime event$"):
                    self.c.create(model=MODEL, messages=self.messages(trigger))
                self.assertEqual(self.only_audit()[1]["error"]["message"], "unknown runtime event")

    def non_json_request(self):
        with self.assertLogs(client.log.name, "WARNING") as logs, \
                self.assertRaisesRegex(client.ProviderError, "^" + re.escape(PROTOCOL) + "$") as raised:
            self.c.create(model=MODEL, messages=self.messages("__non_json__"))
        self.assertIs(type(raised.exception), client.ProviderError)
        self.assertTrue(self.c.is_closed())
        self.assertTrue(self.c._runtime.cleanup["group_absent"])
        path, record = self.only_audit()
        self.assertTrue(any(path.name in line for line in logs.output))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)  # C7
        self.assertEqual(record["error"], {"class": "ProviderError", "message": PROTOCOL})
        stream = record["stream"]
        self.assertIn(["<non-json-line>", 1], stream["runtime_events"])
        # The drain read the rest of the current message into the record only.
        self.assertEqual(stream["drain"]["ended"], "complete")
        self.assertGreater(stream["drain"]["events"], 0)
        self.assertTrue(stream["messages"][-1]["stopped"])
        rejected = record["rejected_line"]
        self.assertEqual((rejected["bytes"], rejected["sha256"]), (len(LINE), hashlib.sha256(LINE).hexdigest()))
        self.assertLessEqual(rejected["prefix_bytes"], stream_audit.PREFIX_BYTES)
        return path, rejected

    def test_c5_a_non_json_line_raises_the_baseline_error_and_audits_a_redacted_prefix(self):
        with patch.object(stream_audit, "redactor", return_value=test_redaction):
            path, rejected = self.non_json_request()
        kept = LINE[:rejected["prefix_bytes"]]
        self.assertEqual(rejected["prefix"], test_redaction(kept.decode()))
        self.assertLessEqual(len(rejected["prefix"].encode()), stream_audit.PREFIX_BYTES)
        self.assertTrue(rejected["prefix"].startswith("Synthetic diagnostic: token=" + MARKER + " "))
        self.assertNotIn("prefix_omitted", rejected)
        self.assertNotIn(SECRET, path.read_text())

    def test_c6_without_redaction_no_part_of_the_line_is_stored(self):
        def broken(text):
            raise RuntimeError("synthetic redaction failure")
        for name, redactor in (("import fails", patch.object(stream_audit, "redactor", side_effect=ImportError)),
                               ("call fails", patch.object(stream_audit, "redactor", return_value=broken)),
                               ("no hermes on path", patch.dict(sys.modules, {"agent": None}))):
            with self.subTest(name):
                self.fresh_client()
                with redactor:
                    path, rejected = self.non_json_request()
                self.assertEqual((rejected["prefix"], rejected["prefix_bytes"]), (None, 0))
                self.assertEqual(rejected["prefix_omitted"], "redaction unavailable")
                text = path.read_text()
                for fragment in [SECRET, "Synthetic diagnostic", "token="] + WORDS:
                    self.assertNotIn(fragment, text)


class RejectedLineTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(stream_audit, "redactor", return_value=test_redaction)
        guard.start()
        self.addCleanup(guard.stop)

    def test_a_short_line_is_kept_whole_after_redaction(self):
        line = b"plain " + SECRET.encode() + b" end"
        self.assertEqual(stream_audit.rejected(line), {
            "bytes": len(line), "sha256": hashlib.sha256(line).hexdigest(), "prefix_bytes": len(line),
            "prefix": "plain " + MARKER + " end"})

    def test_a_token_cut_by_the_boundary_is_left_out_whole(self):
        head = b"a" * 150 + b" "
        line = head + b"b" * 120
        out = stream_audit.rejected(line)
        self.assertEqual((out["bytes"], out["prefix_bytes"], out["prefix"]), (len(line), len(head), head.decode()))
        ended = b"c" * 199 + b" " + b"d" * 50  # the boundary falls on a separator: nothing is cut
        self.assertEqual(stream_audit.rejected(ended)["prefix_bytes"], 200)

    def test_invalid_utf8_is_escaped_and_the_prefix_stays_within_the_bound(self):
        line = b"\xff\xfe " * 100
        out = stream_audit.rejected(line)
        self.assertEqual(out["prefix_bytes"], 200)
        self.assertTrue(out["prefix"].startswith("\\xff\\xfe "))
        self.assertLessEqual(len(out["prefix"].encode()), 200)


def synthetic_runtime(argv):
    """Inert event producer for tool_progress and non-JSON line shapes; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    tools = [client.PREFIX + "read_file"] if config["mcpServers"] else []
    model = argv[argv.index("--model") + 1]
    bridge = None
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit({"type": "stream_event", "event": {"type": kind, **kwargs}, "parent_tool_use_id": None})
    def block(message_id, index, value):
        if value["type"] == "text":
            ev("content_block_start", index=index, content_block={"type": "text", "text": ""})
            ev("content_block_delta", index=index, delta={"type": "text_delta", "text": value["text"]})
        else:
            ev("content_block_start", index=index, content_block={**value, "input": {}})
            ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": json.dumps(value["input"])})
        emit({"type": "assistant", "message": {"id": message_id, "model": model, "content": [value],
              "usage": {"output_tokens": 1}}, "parent_tool_use_id": None})
        ev("content_block_stop", index=index)
    def message(message_id, blocks, stop="end_turn", between=None):
        ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})
        if between:
            between()
        for index, value in enumerate(blocks):
            block(message_id, index, value)
        ev("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2})
        ev("message_stop")
    def result():
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
              "modelUsage": {model: {"canonicalModel": model, "provider": "firstParty"}}})
    def text(value):
        return {"type": "text", "text": value}
    def call(tool_use_id, path):
        return {"type": "tool_use", "id": tool_use_id, "name": client.PREFIX + "read_file", "input": {"path": path}}
    def open_bridge():
        cfg = config["mcpServers"]["hermes"]
        process = subprocess.Popen([cfg["command"]] + cfg["args"], env=cfg["env"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True)
        process.stdin.write(json.dumps({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}) + "\n")
        process.stdin.flush()
        process.stdout.readline()
        return process
    def request_call(rpc_id, path):
        bridge.stdin.write(json.dumps({"id": rpc_id, "method": "tools/call",
                                       "params": {"name": "read_file", "arguments": {"path": path}}}) + "\n")
        bridge.stdin.flush()
    def reply(tool_use_id):
        value = json.loads(bridge.stdout.readline())["result"]["content"][0]["text"]
        emit({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": value}]}, "parent_tool_use_id": None})
        return value
    for ordinal, line in enumerate(sys.stdin):
        content = json.loads(line)["message"]["content"]
        prompt = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if b.get("type") == "text")
        if ordinal == 0:
            emit({"type": "system", "subtype": "init", "model": model, "tools": tools, "apiKeySource": "none",
                  "claude_code_version": "2.1.283"})
        if "__parked_progress__" in prompt:
            message("msg_parked_1", [call("toolu_progress_a", "/synthetic/a")], stop="tool_use")
            bridge = open_bridge()
            request_call(2, "/synthetic/a")
            time.sleep(0.3)  # the tool runs in Hermes; the CLI reports progress meanwhile
            emit(progress("toolu_progress_a", "toolu_progress_a", heartbeat=True))
            emit(progress("toolu_progress_a", None, heartbeat=True))
            value = reply("toolu_progress_a")
            message("msg_parked_2", [text("Got " + value)])
            result()
        elif "__parallel_progress__" in prompt:
            message("msg_parallel_1", [call("toolu_par_a", "/synthetic/a"), call("toolu_par_b", "/synthetic/b")],
                    stop="tool_use")
            bridge = open_bridge()
            request_call(2, "/synthetic/a")
            first = reply("toolu_par_a")
            emit(progress("toolu_par_b", None, heartbeat=True))
            emit(progress("toolu_par_b", "toolu_par_b", heartbeat=True))
            time.sleep(0.3)  # the client reads the progress before the CLI requests the second call
            request_call(3, "/synthetic/b")
            second = reply("toolu_par_b")
            message("msg_parallel_2", [text(first + "|" + second)])
            result()
        elif "__progress_variants__" in prompt:
            emit(progress("toolu_v", None, heartbeat=True))
            emit(progress("toolu_v", "toolu_parent", subagent_type="synthetic-agent", task_id="task-synthetic"))
            emit(progress("toolu_v", "toolu_parent", subagent_retry={"attempt": 1}))
            message(f"msg_variants_{ordinal}", [text("Fine")],
                    between=lambda: emit(progress("toolu_v", None, heartbeat=True)))
            result()
        elif "__subagent_assistant__" in prompt:
            ev("message_start", message={"id": "msg_sub", "model": model, "usage": {"input_tokens": 1}})
            emit({"type": "assistant", "message": {"id": "msg_sub", "model": model, "content": [text("x")]},
                  "parent_tool_use_id": "toolu_parent"})
        elif "__subagent_user__" in prompt:
            emit({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_child", "content": "x"}]}, "parent_tool_use_id": "toolu_parent"})
        elif "__subagent_stream_event__" in prompt:
            emit({"type": "stream_event", "event": {"type": "message_start", "message": {
                "id": "msg_sub", "model": model, "usage": {"input_tokens": 1}}}, "parent_tool_use_id": "toolu_parent"})
        elif "__undocumented_with_parent__" in prompt:
            emit({"type": "undocumented_kind", "parent_tool_use_id": "toolu_parent"})
        elif "__undocumented__" in prompt:
            emit({"type": "undocumented_kind"})
        elif "__non_json__" in prompt:
            ev("message_start", message={"id": "msg_nj", "model": model, "usage": {"input_tokens": 1}})
            sys.stdout.buffer.write(LINE + b"\n")
            sys.stdout.flush()
            block("msg_nj", 0, text("After the line."))
            ev("message_delta", delta={"stop_reason": "end_turn"}, usage={"output_tokens": 2})
            ev("message_stop")
            result()
    if bridge:
        bridge.terminate()
        bridge.wait(timeout=2)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
