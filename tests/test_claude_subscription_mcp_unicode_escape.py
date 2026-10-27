"""An MCP request whose arguments equal a call's streamed arguments only after the snapshot's extra
backslash-u decoding is matched to that call (client._match), when the snapshot check accepted that call
under the same rule (Message.escapes); nothing else is accepted.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI, no network,
a temporary HERMES_HOME), with the model-runtime child rerouted to the event producer below. Requests reach
the client through the plugin's own mcp_server.py, or, for two requests queued at once (which that server
never sends), through a minimal peer on the same authenticated bridge socket. All names, ids and argument
values are synthetic. Escape sequences are built with chr(92), so this source never holds one literally.

"Before the change" replaces only client.escape_equal (the new rule) with a function that accepts nothing;
every other part of the client is unchanged, so those runs show the behaviour at the baseline commit.
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
stream_events = importlib.import_module("subscription_plugin.stream_events")
MODEL = provider.MODEL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())
ERROR = "unmatched/replayed/unadvertised model and MCP invocation"
STAGE = "mcp_unicode_escape_accepted"
TOOL_NAME = "synthetic_writer_5b1e"
OTHER_NAME = "synthetic_heartbeat_93d0"


def tool(name):
    return {"type": "function", "function": {"name": name, "description": "Synthetic tool", "parameters": {
        "type": "object", "properties": {"content": {"type": "string"}, "title": {"type": "string"}}}}}


TOOLS = [tool(TOOL_NAME), tool(OTHER_NAME)]


def seq(code):
    """The literal six-character backslash-u sequence for `code`."""
    return chr(92) + "u" + format(code, "04x")


SIX = (0x2019, 0x00E9, 0x2014, 0x00A0, 0x201C, 0x201D)
TWO = (0x2018, 0x00FC)


def texts(marker, codes):
    """(streamed, decoded): synthetic text holding one literal sequence per code, and the same text decoded."""
    parts = [f"{marker}-part{n}-" for n in range(len(codes))]
    return ("".join(p + seq(c) for p, c in zip(parts, codes)) + "end",
            "".join(p + chr(c) for p, c in zip(parts, codes)) + "end")


STREAMED_6, DECODED_6 = texts("CONTENT-CANARY-6a1f", SIX)
STREAMED_2, DECODED_2 = texts("CONTENT-CANARY-2c7d", TWO)
TITLE_STREAMED, TITLE_DECODED = texts("TITLE-CANARY-e4b0", (0x2019,))
PLAIN = "CONTENT-CANARY-PLAIN-71c3"
PLAIN_B = "CONTENT-CANARY-PLAIN-B-0f58"
CANARIES = ("CANARY", STREAMED_6, DECODED_6, STREAMED_2, DECODED_2, PLAIN, PLAIN_B, chr(92) + "u",
            *(chr(c) for c in SIX + TWO))


def one_char_off(text):
    return text[:-1] + ("X" if text[-1] != "X" else "Y")


def detail(**changes):
    """The expected mcp_match_failure record: a fresh session's single message with one call."""
    return {"call_site": "message_calls", "condition": "no_equal_call", "mcp_call": 0, "sequence": 0,
            "delivered_unacknowledged": 0, "name_advertised": True, "candidates": 1, "same_name_candidates": 1,
            "keep_last_in_request": False, "matches_dropped_call": False,
            "same_name_equal_after_escape_decoding": False, "runtime_output_pending": False, **changes}


def before_the_change():
    return patch.object(client, "escape_equal", lambda *args: None)


class McpUnicodeEscapeTests(unittest.TestCase):
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
        return self.c.create(model=MODEL, tools=TOOLS, messages=[{"role": "system", "content": "Synthetic system"},
                                                                 {"role": "user", "content": prompt}], **kwargs)

    def rebuilt(self, prompt, **kwargs):
        """A new client handed an existing transcript, as after a restart: the first input is a rebuild."""
        return self.c.create(model=MODEL, tools=TOOLS, messages=[
            {"role": "system", "content": "Synthetic system"}, {"role": "user", "content": "Synthetic earlier request."},
            {"role": "assistant", "content": "Synthetic earlier reply."}, {"role": "user", "content": prompt}], **kwargs)

    def results(self, response, text="SYNTHETIC RESULT"):
        messages = [*self.c._history.messages]
        return messages + [{"role": "tool", "tool_call_id": c.id, "content": text}
                           for c in response.choices[0].message.tool_calls]

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def stages(self, name):
        return [a for a in self.c.audit if a["stage"] == name]

    def decisions(self):
        return [(a["outcome"], a["row"]) for a in self.c.audit if a["stage"] == "second_message"]

    def assertNoArgumentText(self, text):
        for forbidden in CANARIES:
            self.assertNotIn(forbidden, text)

    def assertAccepted(self, expected):
        """Exactly one new audit stage with `expected`, holding no argument text in memory or once sanitized."""
        [entry] = self.stages(STAGE)
        self.assertEqual(entry, {"stage": STAGE, **expected})
        self.assertNoArgumentText(json.dumps(entry, ensure_ascii=False))
        record = stream_audit.payload(client.ProviderError("synthetic"), None, MODEL, None, self.c.audit,
                                      stream_audit.StreamLog())
        [written] = [a for a in record["audit"] if a["stage"] == STAGE]
        self.assertEqual(written, {"stage": STAGE, **expected, "keys_truncated": 0})
        self.assertNoArgumentText(json.dumps([a for a in record["audit"] if a["stage"] != "tool_parked"],
                                             ensure_ascii=False))

    def rejected(self, call, expected):
        """`call` fails as no_equal_call (or `expected`'s condition) and writes one audit without argument text."""
        chunks = []
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            for chunk in call():
                chunks.append(chunk)
        message = str(raised.exception)
        self.assertEqual(message, f"{ERROR} ({expected['condition']})")
        self.assertEqual(chunks, [])
        self.assertTrue(self.c.is_closed())
        [path] = self.audits()
        text = path.read_text()
        record = json.loads(text)
        self.assertEqual(record["mcp_match_failure"], expected)
        self.assertNotIn(STAGE, [a["stage"] for a in record["audit"]])
        self.assertEqual(self.stages(STAGE), [])
        self.assertNoArgumentText(json.dumps(record["mcp_match_failure"]))
        self.assertNoArgumentText(json.dumps([a for a in record["audit"] if a["stage"] != "tool_parked"]))
        return record

    def test_the_synthetic_texts_decode_as_the_snapshot_check_decodes(self):
        self.assertEqual(stream_events._decode_escapes(STREAMED_6), (DECODED_6, 6))
        self.assertEqual(stream_events._decode_escapes(STREAMED_2), (DECODED_2, 2))
        self.assertEqual(stream_events._decode_escapes(TITLE_STREAMED), (TITLE_DECODED, 1))

    # Evidence case 1: message_calls, six decoded sequences in `content`.

    def test_message_calls_request_with_six_decoded_sequences_is_accepted(self):
        response = self.request("__six__")
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        [call] = response.choices[0].message.tool_calls
        self.assertEqual(call.id, "toolu_six")
        # Hermes runs the streamed (faithful) arguments, not the request's decoded ones.
        self.assertEqual(json.loads(call.function.arguments), {"content": STREAMED_6})
        self.assertEqual(self.c._pending["tool_use_id"], "toolu_six")
        self.assertEqual(self.stages("snapshot_unicode_escape_accepted"),
                         [{"stage": "snapshot_unicode_escape_accepted", "index": 0, "keys": ["content"], "decoded": 6}])
        self.assertAccepted({"call_site": "message_calls", "mcp_call": 0, "sequence": 0, "decoded": 6, "keys": ["content"]})
        self.assertEqual(self.audits(), [])
        answer = self.c.create(model=MODEL, tools=TOOLS, messages=self.results(response))
        self.assertEqual(answer.choices[0].message.content, "Got SYNTHETIC RESULT")
        self.assertEqual(self.audits(), [])

    def test_message_calls_request_with_six_decoded_sequences_before_the_change(self):
        with before_the_change():
            self.rejected(lambda: self.request("__six__", stream=True), detail(same_name_equal_after_escape_decoding=True))

    # Evidence case 2: remaining_calls after a rebuild from a transcript, two decoded sequences in `content`.

    def test_remaining_calls_request_with_two_decoded_sequences_after_a_rebuild_is_accepted(self):
        response = self.rebuilt("__two_remaining__")
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_beat", "toolu_two"])
        self.assertEqual(json.loads(response.choices[0].message.tool_calls[1].function.arguments), {"content": STREAMED_2})
        self.assertEqual(len(self.stages("rebuild")), 1)
        self.assertEqual(self.stages("snapshot_unicode_escape_accepted"),
                         [{"stage": "snapshot_unicode_escape_accepted", "index": 1, "keys": ["content"], "decoded": 2}])
        self.assertEqual(self.stages(STAGE), [])  # the first request asked for the call without sequences
        answer = self.c.create(model=MODEL, tools=TOOLS, messages=self.results(response))
        self.assertEqual(answer.choices[0].message.content, "Got SYNTHETIC RESULT")
        self.assertAccepted({"call_site": "remaining_calls", "mcp_call": 1, "sequence": 1, "decoded": 2, "keys": ["content"]})
        self.assertEqual(self.audits(), [])

    def test_the_snapshot_record_is_kept_for_the_remaining_calls_until_they_are_requested(self):
        response = self.rebuilt("__two_remaining__")
        self.assertEqual(self.c._escaped, {"toolu_two": ["content"]})  # the parked call needs no record
        self.c.create(model=MODEL, tools=TOOLS, messages=self.results(response))
        self.assertEqual(self.c._escaped, {})

    def test_remaining_calls_request_with_two_decoded_sequences_before_the_change(self):
        response = self.rebuilt("__two_remaining__")
        with before_the_change():
            self.rejected(lambda: self.c.create(model=MODEL, tools=TOOLS, messages=self.results(response), stream=True),
                          detail(call_site="remaining_calls", mcp_call=1, sequence=1,
                                 same_name_equal_after_escape_decoding=True))

    def test_remaining_calls_request_one_character_off_is_rejected(self):
        response = self.rebuilt("__two_remaining_off__")
        self.rejected(lambda: self.c.create(model=MODEL, tools=TOOLS, messages=self.results(response), stream=True),
                      detail(call_site="remaining_calls", mcp_call=1, sequence=1))

    # Near misses: each still fails as no_equal_call.

    def test_a_request_one_character_off_the_decoded_stream_is_rejected(self):
        self.rejected(lambda: self.request("__off_by_one__", stream=True), detail())

    def test_a_request_with_another_key_set_is_rejected(self):
        self.rejected(lambda: self.request("__extra_key__", stream=True), detail())

    def test_a_request_for_another_tool_name_is_rejected(self):
        self.rejected(lambda: self.request("__other_tool__", stream=True), detail(same_name_candidates=0))

    def test_a_differing_value_without_any_sequence_is_rejected(self):
        self.rejected(lambda: self.request("__plain_differs__", stream=True), detail())

    def test_a_decoded_request_for_a_call_the_snapshot_showed_undecoded_is_rejected(self):
        # The decoding rule alone would match, but the snapshot check recorded no decoding for this call.
        self.rejected(lambda: self.request("__snapshot_undecoded__", stream=True),
                      detail(same_name_equal_after_escape_decoding=True))

    def test_a_request_decoded_in_more_keys_than_the_snapshot_is_rejected(self):
        # The snapshot decoded `content` only; the request also decodes `title`.
        self.rejected(lambda: self.request("__more_keys__", stream=True),
                      detail(same_name_equal_after_escape_decoding=True))

    def test_the_request_with_the_streamed_arguments_still_matches_exactly(self):
        response = self.request("__six_streamed__")
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        self.assertEqual(self.stages(STAGE), [])
        self.assertEqual(self.audits(), [])

    # A message continued after max_tokens: the merged message keeps the continuation's snapshot record.

    def test_a_decoded_request_for_a_call_of_a_continued_message_is_accepted(self):
        response = self.request("__append__")
        self.assertEqual(self.decisions(), [("append", "continuation")])
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_append"])
        self.assertAccepted({"call_site": "message_calls", "mcp_call": 0, "sequence": 0, "decoded": 2, "keys": ["content"]})
        self.assertEqual(self.audits(), [])

    # `requested` at a second message's message_start uses the same rule (specification item 4).

    def test_a_queued_decoded_request_counts_as_requested_for_the_second_message_decision(self):
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            for _ in self.request("__requested__", stream=True):
                pass
        self.assertEqual(str(raised.exception), "duplicate streamed message")
        self.assertEqual(self.decisions(), [("fail", "internal_step_after_mcp_request")])
        self.assertTrue(self.stages("second_message")[0]["requested"])
        [path] = self.audits()
        self.assertNoArgumentText(path.read_text())

    def test_a_queued_decoded_request_before_the_change_lets_keep_last_drop_the_requested_call(self):
        with before_the_change():
            response = self.request("__requested__")
        self.assertEqual(self.decisions(), [("keep_last", "internal_step")])
        self.assertFalse(self.stages("second_message")[0]["requested"])
        self.assertEqual([c.id for c in response.choices[0].message.tool_calls], ["toolu_b"])


def synthetic_runtime(argv):
    """Inert event producer and MCP client for these request shapes; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    model = argv[argv.index("--model") + 1]
    cfg = config["mcpServers"]["hermes"]
    writer, beat = client.PREFIX + TOOL_NAME, client.PREFIX + OTHER_NAME

    def emit(obj):
        print(json.dumps(obj), flush=True)

    def ev(kind, **kwargs):
        return {"type": "stream_event", "event": {"type": kind, **kwargs}}

    def blocks(message_id, values):
        out = []
        for index, value in enumerate(values):
            shown = value.pop("shown", None)
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

    def message(message_id, values, stop="tool_use"):
        return ([ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})]
                + blocks(message_id, values)
                + [ev("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2}), ev("message_stop")])

    def text(value):
        return {"type": "text", "text": value}

    def call(tool_use_id, arguments, shown=None, name=writer):
        value = {"type": "tool_use", "id": tool_use_id, "name": name, "input": arguments}
        if shown is not None:
            value["shown"] = shown
        return value

    def burst(events):
        sys.stdout.write("".join(json.dumps(e) + "\n" for e in events))
        sys.stdout.flush()

    def finish(reply):
        burst(message("msg_final", [text("Got " + reply)], "end_turn"))
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

        def ask(self, arguments, name=TOOL_NAME):
            self.rpc += 1
            self.write({"id": self.rpc, "method": "tools/call", "params": {"name": name, "arguments": arguments}})

        def answer(self):
            return self.read()["result"]["content"][0]["text"]

    class Peer:
        """A minimal bridge peer that can queue two requests at once, which mcp_server.py never does."""
        def __init__(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(cfg["args"][-1])
            self.reader = self.sock.makefile("rb")
            self.send({"hello": cfg["env"]["HERMES_BRIDGE_TOKEN"]})
            json.loads(self.reader.readline())  # the advertised tools

        def send(self, value):
            self.sock.sendall(json.dumps(value).encode() + b"\n")

    six = call("toolu_six", {"content": STREAMED_6}, shown={"content": DECODED_6})
    requests = {"__six__": {"content": DECODED_6}, "__six_streamed__": {"content": STREAMED_6},
                "__off_by_one__": {"content": one_char_off(DECODED_6)},
                "__extra_key__": {"content": DECODED_6, "title": "x"}}
    for line in sys.stdin:
        content = json.loads(line)["message"]["content"]
        prompt = content if isinstance(content, str) else "".join(b.get("text", "") for b in content)
        prompt = prompt.rsplit("\n", 1)[-1]  # a rebuilt session's input ends with the newest user message
        emit({"type": "system", "subtype": "init", "model": model, "tools": [writer, beat], "apiKeySource": "none",
              "claude_code_version": "2.1.283"})
        if prompt in requests:
            server = Server()
            burst(message("msg_six", [six]))
            server.ask(requests[prompt])
            if prompt in ("__six__", "__six_streamed__"):
                finish(server.answer())
            else:
                time.sleep(30)
        elif prompt == "__other_tool__":
            server = Server()
            burst(message("msg_six", [six]))
            server.ask({"content": DECODED_6}, name=OTHER_NAME)
            time.sleep(30)
        elif prompt == "__plain_differs__":
            server = Server()
            burst(message("msg_plain", [call("toolu_plain", {"content": PLAIN})]))
            server.ask({"content": PLAIN_B})
            time.sleep(30)
        elif prompt == "__snapshot_undecoded__":
            server = Server()
            burst(message("msg_raw", [call("toolu_raw", {"content": STREAMED_6})]))  # the snapshot equals the stream
            server.ask({"content": DECODED_6})
            time.sleep(30)
        elif prompt == "__more_keys__":
            server = Server()
            burst(message("msg_keys", [call("toolu_keys", {"content": STREAMED_6, "title": TITLE_STREAMED},
                                            shown={"content": DECODED_6, "title": TITLE_STREAMED})]))
            server.ask({"content": DECODED_6, "title": TITLE_DECODED})
            time.sleep(30)
        elif prompt in ("__two_remaining__", "__two_remaining_off__"):
            server = Server()
            burst(message("msg_two", [text("Saving."), call("toolu_beat", {"content": PLAIN}, name=beat),
                                      call("toolu_two", {"content": STREAMED_2}, shown={"content": DECODED_2})]))
            server.ask({"content": PLAIN}, name=OTHER_NAME)
            server.answer()  # delivered at the start of Hermes's next request
            server.ask({"content": DECODED_2 if prompt == "__two_remaining__" else one_char_off(DECODED_2)})
            reply = server.answer()
            burst([{"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": i, "content": "delivered"} for i in ("toolu_beat", "toolu_two")]}}])
            finish(reply)
        elif prompt == "__append__":
            server = Server()
            burst(message("msg_cut", [text("Partial")], "max_tokens")
                  + message("msg_more", [text(" continued."), call("toolu_append", {"content": STREAMED_2},
                                                                    shown={"content": DECODED_2})]))
            server.ask({"content": DECODED_2})
            time.sleep(30)
        elif prompt == "__requested__":
            peer = Peer()  # connected before any message, so both requests can be queued at once below
            burst(message("msg_a", [call("toolu_a", {"content": STREAMED_2}, shown={"content": DECODED_2})])
                  + [{"type": "user", "message": {"role": "user", "content": [
                      {"type": "tool_result", "tool_use_id": "toolu_a", "content": "synthetic rejection", "is_error": True}]}}]
                  + message("msg_b", [call("toolu_b", {"content": PLAIN})]))
            # Neither request is matched against msg_a while msg_b is still unread: the first equals msg_b's
            # call, the second is msg_a's call in decoded form.
            peer.send({"call": 0, "rpc_id": 2, "name": TOOL_NAME, "arguments": {"content": PLAIN}})
            peer.send({"call": 0, "rpc_id": 3, "name": TOOL_NAME, "arguments": {"content": DECODED_2}})
            time.sleep(30)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
