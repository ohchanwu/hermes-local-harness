"""A rejected MCP invocation (client._match) writes a stream audit whose detail record names the failed condition.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI, no
network, a temporary HERMES_HOME), with the model-runtime child rerouted to the event producer below.
Requests reach the client either through the plugin's own mcp_server.py or, for requests that server
never sends (a wrong call number, an rpc id of another type, an unadvertised name, a request before the
acknowledgement), through a minimal peer on the same authenticated bridge socket. All names, ids and
argument values are synthetic.

The keep_last sequences below are the ones tried for the card's cause search (part 3); see each test.
"""
import importlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
MODEL = provider.MODEL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())
ERROR = "unmatched/replayed/unadvertised model and MCP invocation"
TOOL_NAME = "synthetic_lookup_7c2a"
OTHER_NAME = "unadvertised_lookup_e91f"
TOOL = {"type": "function", "function": {"name": TOOL_NAME, "description": "Synthetic lookup",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
ARG = "/ARGUMENT-CANARY-0d4b"
ARG_B = "/ARGUMENT-CANARY-B-58e3"
ARG_C = "/ARGUMENT-CANARY-C-a417"
ARG_OTHER = "/ARGUMENT-CANARY-OTHER-2c66"
CANARIES = (ARG, ARG_B, ARG_C, ARG_OTHER, ARG.strip("/"), ARG_B.strip("/"), ARG_C.strip("/"), ARG_OTHER.strip("/"))
QUOTE = chr(92) + "u2019"  # a literal backslash-u sequence, built so that this source never holds one


def detail(**changes):
    """The expected mcp_match_failure record: a fresh session's single message with one call."""
    return {"call_site": "message_calls", "condition": "no_equal_call", "mcp_call": 0, "sequence": 0,
            "delivered_unacknowledged": 0, "name_advertised": True, "candidates": 1, "same_name_candidates": 1,
            "keep_last_in_request": False, "matches_dropped_call": False,
            "same_name_equal_after_escape_decoding": False, "runtime_output_pending": False, **changes}


class MatchAuditTests(unittest.TestCase):
    def setUp(self):
        real = subprocess.Popen
        def reroute(argv, *args, **kwargs):
            if "--synthetic-runtime" in argv and "--version" not in argv:
                argv = [SCRIPT if part == PROVIDER_SCRIPT else part for part in argv]
            return real(argv, *args, **kwargs)
        guard = patch("subprocess.Popen", reroute)
        guard.start()
        self.addCleanup(guard.stop)
        provider.ClientTests.setUp(self)
        self.sessions = self.directory / "sessions"

    def fresh(self):
        for path in self.audits():
            path.unlink()
        self.c.close()
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)

    def request(self, prompt, **kwargs):
        return self.c.create(model=MODEL, tools=[TOOL], messages=[{"role": "system", "content": "Synthetic system"},
                                                                  {"role": "user", "content": prompt}], **kwargs)

    def results(self, response, text="SYNTHETIC RESULT"):
        """Hermes's next request: its history plus one result per call of the parked batch."""
        messages = [*self.c._history.messages]
        return messages + [{"role": "tool", "tool_call_id": c.id, "content": text}
                           for c in response.choices[0].message.tool_calls]

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def rejected(self, call, expected, *, tool_name_in_file=False):
        """`call` fails with the condition in its text and writes exactly one audit holding `expected`.

        Nothing reaches Hermes, nothing is parked, and no synthetic argument value or tool name appears in
        the error text, the detail record or (unless an earlier park recorded it) the audit file.
        """
        chunks = []
        with self.assertLogs(client.log.name, "WARNING") as logs, self.assertRaises(client.ProviderError) as raised:
            for chunk in call():
                chunks.append(chunk)
        self.assertIs(type(raised.exception), client.ProviderError)
        message = str(raised.exception)
        self.assertEqual(message, f"{ERROR} ({expected['condition']})")
        self.assertTrue(message.startswith(ERROR))
        self.assertEqual(chunks, [])
        self.assertIsNone(self.c._pending)
        self.assertTrue(self.c.is_closed())
        [path] = self.audits()
        self.assertTrue(any(f"stream failed ({message}); stream audit written to {path.name}" in line for line in logs.output))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        text = path.read_text()
        record = json.loads(text)
        self.assertEqual(record["error"], {"class": "ProviderError", "message": message})
        self.assertEqual(record["mcp_match_failure"], expected)
        parts = (message, json.dumps(record["mcp_match_failure"]))
        for forbidden in (*CANARIES, TOOL_NAME, OTHER_NAME, "ARGUMENT-CANARY", "u2019"):
            for part in parts:
                self.assertNotIn(forbidden, part)
            if forbidden not in (TOOL_NAME,) or not tool_name_in_file:
                self.assertNotIn(forbidden, text)
        return record

    # Part 1: one distinct condition value for each condition, recorded in the audit.

    def test_a_call_number_other_than_the_client_sequence(self):
        self.rejected(lambda: self.request("__wrong_call_number__", stream=True), detail(condition="call_sequence_differs",
                                                                                         mcp_call=7, same_name_candidates=1))

    def test_a_request_before_the_previous_result_was_acknowledged(self):
        response = self.request("__unacknowledged__")
        self.assertEqual(len(response.choices[0].message.tool_calls), 2)
        self.rejected(lambda: self.c.create(model=MODEL, tools=[TOOL], messages=self.results(response), stream=True),
                      detail(call_site="remaining_calls", condition="result_not_acknowledged", mcp_call=1, sequence=1,
                             delivered_unacknowledged=1), tool_name_in_file=True)  # the earlier tool_parked entry
        self.assertEqual(len([a for a in self.c.audit if a["stage"] == "result_delivered"]), 1)

    def test_an_rpc_id_of_another_type(self):
        self.rejected(lambda: self.request("__float_rpc_id__", stream=True), detail(condition="invalid_rpc_id_type"))

    def test_an_unadvertised_tool_name(self):
        self.rejected(lambda: self.request("__unadvertised_name__", stream=True),
                      detail(condition="tool_not_advertised", name_advertised=False, same_name_candidates=0))

    def test_no_call_with_equal_name_and_arguments(self):
        self.rejected(lambda: self.request("__other_arguments__", stream=True), detail())

    def test_the_same_request_with_equal_arguments_is_accepted(self):
        response = self.request("__equal_arguments__")
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        self.assertEqual(self.c._pending["tool_use_id"], "toolu_equal")
        self.assertEqual(self.audits(), [])

    def test_the_record_keeps_only_allowlisted_counts_and_booleans(self):
        self.assertEqual(stream_audit.match_failure({
            "call_site": "elsewhere", "condition": TOOL_NAME, "mcp_call": "7", "sequence": None, "candidates": 2.5,
            "delivered_unacknowledged": [ARG], "same_name_candidates": {"k": ARG}, "name_advertised": "yes",
            "keep_last_in_request": 1, "matches_dropped_call": True, "arguments": {"path": ARG}, "name": TOOL_NAME}),
            {"call_site": "<other>", "condition": "<other>", "mcp_call": "<string>", "sequence": "<null>",
             "delivered_unacknowledged": "<array>", "candidates": "<number>", "same_name_candidates": "<object>",
             "name_advertised": False, "keep_last_in_request": False, "matches_dropped_call": True,
             "same_name_equal_after_escape_decoding": False, "runtime_output_pending": False})
        self.assertNotIn("mcp_match_failure", stream_audit.payload(client.ProviderError("x"), None, MODEL, None, [],
                                                                    stream_audit.StreamLog()))

    def test_the_audit_names_snapshot_escape_decoding_when_the_request_holds_the_decoded_arguments(self):
        # Hypothesis tested for the cause search: the CLI may run its snapshot's (decoded) input. The
        # flag records that case. Card t_15903481 accepts that request under the snapshot's rule
        # (test_claude_subscription_mcp_unicode_escape.py); with that rule off, it is rejected as before.
        with patch.object(client, "escape_equal", lambda *args: None):
            record = self.rejected(lambda: self.request("__escape_decoded__", stream=True),
                                   detail(same_name_equal_after_escape_decoding=True))
        self.assertIn("snapshot_unicode_escape_accepted", [a["stage"] for a in record["audit"]])
        self.fresh()
        response = self.request("__escape_decoded__")  # with the rule: the decoded request is accepted
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        self.assertEqual([a["stage"] for a in self.c.audit if a["stage"] == "mcp_unicode_escape_accepted"],
                         ["mcp_unicode_escape_accepted"])
        self.assertEqual(self.audits(), [])
        self.fresh()
        response = self.request("__escape_streamed__")  # the streamed (faithful) arguments still match
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        self.assertEqual(self.audits(), [])

    # Part 3: sequences around a keep_last (internal_step) resolution in the same request.

    def test_keep_last_then_the_kept_message_call_is_accepted(self):
        response = self.request("__step__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_b"])
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        answer = self.c.create(model=MODEL, tools=[TOOL], messages=self.results(response))
        self.assertEqual(answer.choices[0].message.content, "Got SYNTHETIC RESULT")
        self.assertEqual(self.audits(), [])

    def test_keep_last_after_a_delivered_result_in_the_same_request_is_accepted(self):
        # The request starts by delivering a result (sequence 0 -> 1); the server's next call number is 1.
        response = self.request("__step_after_delivery__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_m"])
        response = self.c.create(model=MODEL, tools=[TOOL], messages=self.results(response))
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_b"])
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        self.assertEqual(self.c._sequence, 1)
        answer = self.c.create(model=MODEL, tools=[TOOL], messages=self.results(response))
        self.assertEqual(answer.choices[0].message.content, "Got SYNTHETIC RESULT")
        self.assertEqual(self.audits(), [])

    def test_two_keep_last_resolutions_then_the_last_message_call_is_accepted(self):
        response = self.request("__step_twice__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_c"])
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")] * 2)
        self.assertEqual(self.audits(), [])

    def test_keep_last_with_the_kept_call_requested_before_its_message_ended_is_accepted(self):
        # A request for the second message's call queued while that message still streams.
        response = self.request("__step_early_request__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_b"])
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        self.assertEqual(self.audits(), [])

    def test_keep_last_then_a_request_for_the_dropped_call_is_still_rejected(self):
        # The CLI answered the first message's call itself and also asked Hermes for it, after the second
        # message began. `requested` is computed at that message_start only, so keep_last is decided and
        # the dropped call's request is then rejected. Rejecting is right: Hermes must not run a call the
        # runtime already answered. No counter disagrees (mcp_call == sequence == 0).
        self.rejected(lambda: self.request("__step_stale_request__", stream=True),
                      detail(keep_last_in_request=True, matches_dropped_call=True, same_name_candidates=1))
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])

    # The reproduced cause. The CLI writes a message's events, then requests its call. One runtime read
    # buffers that whole burst and returns nothing yet; the loop then takes the bridge request before it
    # parses the buffered events, so the request was matched against the previous, completed message and
    # rejected as no_equal_call. The delay below holds the client between that read and the next bridge
    # pump, as a busy process delays the client thread; without it the same order occurs by chance.
    # "Before the fix" disables only the new deferral, by reporting no unread output.

    def delayed(self, marker):
        original = client.Runtime.read
        def read(runtime):
            obj = original(runtime)
            if obj is None and marker in runtime.buffer and not getattr(runtime, "delayed", False):
                runtime.delayed = True
                time.sleep(.5)
            return obj
        return patch.object(client.Runtime, "read", read)

    def without_deferral(self):
        return patch.object(client.Runtime, "output_pending", lambda runtime: False)

    def test_keep_last_then_the_next_message_request_taken_before_its_events_were_parsed(self):
        # The failure that follows a keep_last resolution in the same request (the evidence's pattern):
        # A and B are answered by the runtime, C is real; C's request is taken while C's events are unread.
        with self.delayed(b'"msg_c"'), self.without_deferral():
            self.rejected(lambda: self.request("__step_twice_request_before_start__", stream=True),
                          detail(keep_last_in_request=True))
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        self.fresh()
        with self.delayed(b'"msg_c"'):
            response = self.request("__step_twice_request_before_start__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_c"])
        self.assertEqual(self.c._pending["tool_use_id"], "toolu_c")
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")] * 2)
        self.assertEqual(self.audits(), [])

    def test_the_next_message_request_taken_before_its_events_were_parsed_without_keep_last_first(self):
        # The same order one message earlier: the rejection then comes with no keep_last line at all.
        with self.delayed(b'"msg_b"'), self.without_deferral():
            self.rejected(lambda: self.request("__step_request_before_start__", stream=True), detail())
        self.assertEqual(self.decisions(), [])
        self.fresh()
        with self.delayed(b'"msg_b"'):
            response = self.request("__step_request_before_start__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_b"])
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        self.assertEqual(self.audits(), [])

    def test_a_deferred_request_that_matches_nothing_once_the_output_is_read_is_still_rejected(self):
        # The deferral only waits for output already written; the matching rule itself is unchanged.
        with self.delayed(b'"msg_b"'):
            self.rejected(lambda: self.request("__step_request_before_start_other__", stream=True),
                          detail(keep_last_in_request=True))
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])

    def decisions(self):
        return [(a["outcome"], a["row"]) for a in self.c.audit if a["stage"] == "second_message"]


def synthetic_runtime(argv):
    """Inert event producer and bridge peer for _match shapes; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    model = argv[argv.index("--model") + 1]
    cfg = config["mcpServers"]["hermes"]
    tool = client.PREFIX + TOOL_NAME

    def emit(obj):
        print(json.dumps(obj), flush=True)

    def ev(kind, **kwargs):
        return {"type": "stream_event", "event": {"type": kind, **kwargs}}

    def start(message_id):
        return [ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})]

    def blocks(message_id, values):
        out = []
        for index, value in enumerate(values):
            shown = value.pop("shown", None) if isinstance(value, dict) else None
            if value["type"] == "text":
                out += [ev("content_block_start", index=index, content_block={"type": "text", "text": ""}),
                        ev("content_block_delta", index=index, delta={"type": "text_delta", "text": value["text"]})]
            else:
                out += [ev("content_block_start", index=index, content_block={**value, "input": {}}),
                        ev("content_block_delta", index=index,
                           delta={"type": "input_json_delta", "partial_json": json.dumps(value["input"])})]
            snapshot = {**value, "input": shown} if shown is not None else value
            out += [{"type": "assistant", "message": {"id": message_id, "model": model, "content": [snapshot],
                                                      "usage": {"output_tokens": 1}}},
                    ev("content_block_stop", index=index)]
        return out

    def end(stop):
        return [ev("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2}), ev("message_stop")]

    def message(message_id, values, stop="tool_use"):
        return start(message_id) + blocks(message_id, values) + end(stop)

    def rejected_answer(tool_use_id):
        """The runtime answering a call itself with a rejection, as in the live audits."""
        return [{"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": "synthetic rejection", "is_error": True}]}}]

    def burst(events):
        """Write events in one write, as one burst of runtime output."""
        sys.stdout.write("".join(json.dumps(e) + "\n" for e in events))
        sys.stdout.flush()

    def call(tool_use_id, path, shown=None):
        value = {"type": "tool_use", "id": tool_use_id, "name": tool, "input": {"path": path}}
        if shown is not None:
            value["shown"] = {"path": shown}
        return value

    def result():
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
              "modelUsage": {model: {"canonicalModel": model, "provider": "firstParty"}}})

    class Server:
        """The plugin's own MCP server, driven over stdio like the CLI drives it."""
        def __init__(self):
            self.process = subprocess.Popen([cfg["command"]] + cfg["args"], env=cfg["env"], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, text=True)
            self.rpc = 1
            self.write({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
            self.read()

        def write(self, value):
            self.process.stdin.write(json.dumps(value) + "\n")
            self.process.stdin.flush()

        def read(self):
            return json.loads(self.process.stdout.readline())

        def ask(self, path):
            self.rpc += 1
            self.write({"id": self.rpc, "method": "tools/call", "params": {"name": TOOL_NAME, "arguments": {"path": path}}})

        def answer(self):
            return self.read()["result"]["content"][0]["text"]

    class Peer:
        """A minimal bridge peer that can send what mcp_server.py never sends."""
        def __init__(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(cfg["args"][-1])
            self.reader = self.sock.makefile("rb")
            self.send({"hello": cfg["env"]["HERMES_BRIDGE_TOKEN"]})
            json.loads(self.reader.readline())  # the advertised tools

        def send(self, value):
            self.sock.sendall(json.dumps(value).encode() + b"\n")

        def receive(self):
            return json.loads(self.reader.readline())

    for line in sys.stdin:
        prompt = json.loads(line)["message"]["content"]
        emit({"type": "system", "subtype": "init", "model": model, "tools": [tool], "apiKeySource": "none",
              "claude_code_version": "2.1.283"})
        if prompt in ("__wrong_call_number__", "__float_rpc_id__", "__unadvertised_name__"):
            burst(message("msg_a", [call("toolu_a", ARG)]))
            request = {"call": 0, "rpc_id": 2, "name": TOOL_NAME, "arguments": {"path": ARG}}
            request.update({"__wrong_call_number__": {"call": 7}, "__float_rpc_id__": {"rpc_id": 2.5},
                            "__unadvertised_name__": {"name": OTHER_NAME}}[prompt])
            Peer().send(request)
            time.sleep(30)
        elif prompt == "__unacknowledged__":
            burst(message("msg_p", [call("toolu_p1", ARG), call("toolu_p2", ARG_B)]))
            peer = Peer()
            peer.send({"call": 0, "rpc_id": 2, "name": TOOL_NAME, "arguments": {"path": ARG}})
            peer.receive()  # the delivered result; no acknowledgement is sent for it
            peer.send({"call": 1, "rpc_id": 3, "name": TOOL_NAME, "arguments": {"path": ARG_B}})
            time.sleep(30)
        elif prompt in ("__other_arguments__", "__equal_arguments__"):
            burst(message("msg_a", [call("toolu_equal", ARG)]))
            Server().ask(ARG_OTHER if prompt == "__other_arguments__" else ARG)
            time.sleep(30)
        elif prompt in ("__escape_decoded__", "__escape_streamed__"):
            streamed, shown = ARG + QUOTE, ARG + chr(0x2019)
            burst(message("msg_e", [call("toolu_e", streamed, shown=shown)]))
            Server().ask(shown if prompt == "__escape_decoded__" else streamed)
            time.sleep(30)
        elif prompt == "__step__":
            server = Server()
            burst(message("msg_a", [text_block("Checking."), call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            burst(message("msg_b", [call("toolu_b", ARG_B)]))
            server.ask(ARG_B)
            reply = server.answer()
            burst(message("msg_final", [text_block("Got " + reply)], "end_turn"))
            result()
        elif prompt == "__step_after_delivery__":
            server = Server()
            burst(message("msg_m", [call("toolu_m", ARG)]))
            server.ask(ARG)
            server.answer()  # the first request's result, delivered at the start of the second request
            burst([{"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_m", "content": "delivered"}]}}])
            burst(message("msg_a", [call("toolu_a", ARG_C)]) + rejected_answer("toolu_a"))
            burst(message("msg_b", [call("toolu_b", ARG_B)]))
            server.ask(ARG_B)
            reply = server.answer()
            burst(message("msg_final", [text_block("Got " + reply)], "end_turn"))
            result()
        elif prompt == "__step_twice__":
            server = Server()
            burst(message("msg_a", [call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            burst(message("msg_b", [call("toolu_b", ARG_B)]) + rejected_answer("toolu_b"))
            burst(message("msg_c", [call("toolu_c", ARG_C)]))
            server.ask(ARG_C)
            time.sleep(30)
        elif prompt == "__step_early_request__":
            server = Server()
            burst(message("msg_a", [call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            burst(start("msg_b") + blocks("msg_b", [call("toolu_b", ARG_B)]))
            time.sleep(.3)
            server.ask(ARG_B)
            time.sleep(.3)  # the client queues the request while the message is still open
            burst(end("tool_use"))
            time.sleep(30)
        elif prompt == "__step_stale_request__":
            server = Server()
            burst(message("msg_a", [call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            burst(start("msg_b"))
            time.sleep(.3)
            server.ask(ARG)  # the dropped call, after the second message began
            time.sleep(.3)
            burst(blocks("msg_b", [call("toolu_b", ARG_B)]) + end("tool_use"))
            time.sleep(30)
        elif prompt in ("__step_request_before_start__", "__step_request_before_start_other__"):
            server = Server()
            burst(message("msg_a", [call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            time.sleep(.3)
            # As the CLI does: the message's events are written first, then its call is requested.
            burst(message("msg_b", [call("toolu_b", ARG_B)]))
            server.ask(ARG_B if prompt == "__step_request_before_start__" else ARG_OTHER)
            time.sleep(30)
        elif prompt == "__step_twice_request_before_start__":
            server = Server()
            burst(message("msg_a", [call("toolu_a", ARG)]) + rejected_answer("toolu_a"))
            time.sleep(.3)
            burst(message("msg_b", [call("toolu_b", ARG_B)]) + rejected_answer("toolu_b"))
            time.sleep(.3)
            burst(message("msg_c", [call("toolu_c", ARG_C)]))
            server.ask(ARG_C)
            time.sleep(30)


def text_block(value):
    return {"type": "text", "text": value}


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
