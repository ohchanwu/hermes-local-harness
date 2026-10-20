"""The CLI snapshot's extra decoding of a literal backslash-u sequence is accepted; nothing else is.

Hermetic: synthetic events fed straight into the stream parser, plus the synthetic-CLI harness of
test_claude_subscription_stream_audit.py for the client's audit entry. No real CLI, network or transcript.
Escape sequences are built with chr(92) so this source never holds one literally.
"""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402
import test_claude_subscription_snapshot_mismatch as mismatch  # noqa: E402

client = provider.client
stream_events = importlib.import_module("subscription_plugin.stream_events")
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
ProviderError = stream_events.ProviderError
MODEL, READ, TOOL_ERROR, call = provider.MODEL, mismatch.READ, mismatch.TOOL_ERROR, mismatch.call
STAGE = "snapshot_unicode_escape_accepted"
MARKER = "UNICODE-ESCAPE-CANARY-2f9a"
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())


def seq(code, digits="{:04x}"):
    """The literal six-character escape sequence for `code`."""
    return chr(92) + "u" + digits.format(code)


QUOTE, PAIR, EMOJI = seq(0x2019), seq(0xD83D) + seq(0xDE00), chr(0x1F600)


def stream(streamed, snapshot, width=5):
    """Feed one message whose tool calls stream `streamed` and whose snapshots show `snapshot`."""
    message = stream_events.Message({MODEL})
    def ev(kind, **kwargs):
        message.feed({"type": "stream_event", "event": {"type": kind, **kwargs}})
    ev("message_start", message={"id": "msg_1", "model": MODEL})
    for index, (sent, shown) in enumerate(zip(streamed, snapshot)):
        ev("content_block_start", index=index, content_block={**sent, "input": {}})
        text = json.dumps(sent["input"])
        for start in range(0, len(text), width):
            ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": text[start:start + width]})
        message.feed({"type": "assistant", "message": {"id": "msg_1", "model": MODEL, "content": [shown]}})
        ev("content_block_stop", index=index)
    ev("message_delta", delta={"stop_reason": "tool_use"})
    ev("message_stop")
    return message


class AcceptedTests(unittest.TestCase):
    def accepted(self, streamed, shown, expected, others=()):
        """`streamed` against `shown` in the last of the calls; earlier calls `others` are equal on both sides."""
        sent = [*others, call(streamed, id=f"toolu_{len(others)}")]
        message = stream(sent, [*others, call(shown, id=f"toolu_{len(others)}")])
        self.assertTrue(message.done)
        self.assertEqual(message.escapes, [{"index": len(others), **expected}])
        for executed, original in zip(message.calls, sent):
            # Hermes runs the streamed arguments, in the streamed fragments, unchanged.
            self.assertEqual(executed["arguments"], original["input"])
            self.assertEqual("".join(executed["fragments"]), json.dumps(original["input"]))
        return message

    def test_one_sequence(self):
        message = self.accepted({"path": "a.py", "content": "Ray" + QUOTE + "s"},
                                {"path": "a.py", "content": "Ray" + chr(0x2019) + "s"}, {"keys": ["content"], "decoded": 1})
        self.assertIn(chr(92), message.calls[0]["arguments"]["content"])
        self.assertEqual(len(message.calls[0]["arguments"]["content"]), 10)

    def test_several_sequences_in_several_keys_and_upper_case_hex(self):
        streamed = {"path": "p" + seq(0xFC, "{:04X}"), "content": "x" + QUOTE + seq(0xE9) + "y" + seq(0x4E2D), "n": 3}
        shown = {"path": "p" + chr(0xFC), "content": "x" + chr(0x2019) + chr(0xE9) + "y" + chr(0x4E2D), "n": 3}
        self.accepted(streamed, shown, {"keys": ["content", "path"], "decoded": 4})

    def test_a_surrogate_pair_written_as_two_sequences(self):
        self.accepted({"content": "smile " + PAIR + "!"}, {"content": "smile " + EMOJI + "!"}, {"keys": ["content"], "decoded": 1})

    def test_a_lone_surrogate_before_a_pair_stays_while_the_pair_decodes(self):
        lone = seq(0xD800)
        self.accepted({"content": lone + PAIR}, {"content": lone + EMOJI}, {"keys": ["content"], "decoded": 1})

    def test_sequences_inside_nested_lists_and_objects(self):
        streamed = {"edits": [{"old": "a", "new": "b" + QUOTE}, "c" + seq(0xFC)], "options": {"note": {"text": QUOTE}, "k": 1}}
        shown = {"edits": [{"old": "a", "new": "b" + chr(0x2019)}, "c" + chr(0xFC)],
                 "options": {"note": {"text": chr(0x2019)}, "k": 1}}
        self.accepted(streamed, shown, {"keys": ["edits", "options"], "decoded": 3})

    def test_a_later_call_is_reported_by_its_index(self):
        self.accepted({"path": QUOTE}, {"path": chr(0x2019)}, {"keys": ["path"], "decoded": 1}, others=[call({"path": "a"})])

    def test_values_equal_under_the_existing_comparison_stay_equal(self):
        # The existing check compares with Python's ==, so 1 and 1.0 were already equal; that is unchanged.
        self.accepted({"limit": 1, "path": QUOTE}, {"limit": 1.0, "path": chr(0x2019)}, {"keys": ["path"], "decoded": 1})

    def test_equal_messages_record_nothing(self):
        self.assertEqual(stream([call({"path": "a" + QUOTE})], [call({"path": "a" + QUOTE})]).escapes, [])


class RejectedTests(unittest.TestCase):
    def rejected(self, streamed, snapshot):
        with self.assertRaises(ProviderError) as raised:
            stream(streamed, snapshot)
        error = raised.exception
        self.assertIs(type(error), ProviderError)
        self.assertEqual(str(error), TOOL_ERROR)  # unchanged, and still classified
        result = mismatch.classify(error)
        self.assertEqual((result["kind"], result["streamed_calls"]), ("tool_use", len(streamed)))
        return result

    def one(self, streamed, shown, **identity):
        return self.rejected([call(streamed)], [call(shown, **identity)])

    def test_another_character_differs_as_well(self):
        self.one({"content": "Ray" + QUOTE + "s"}, {"content": "Ray" + chr(0x2019) + "S"})
        self.one({"content": "Ray" + QUOTE + "s", "path": "a"}, {"content": "Ray" + chr(0x2019) + "s", "path": "b"})

    def test_the_decoded_stream_still_differs(self):
        self.one({"content": "Ray" + QUOTE + "s"}, {"content": "Ray" + chr(0x2018) + "s"})
        self.one({"content": QUOTE + QUOTE}, {"content": chr(0x2019) + QUOTE})  # every sequence is decoded
        self.one({"content": "abc"}, {"content": "abd"})

    def test_a_lone_surrogate_sequence_is_not_decoded(self):
        for shown in (chr(0xFFFD), chr(0xD800)):
            with self.subTest(hex(ord(shown))):
                self.one({"content": "a" + seq(0xD800) + "b"}, {"content": "a" + shown + "b"})
        self.one({"content": seq(0xDE00)}, {"content": chr(0xFFFD)})
        self.one({"content": seq(0xD83D) + "x" + seq(0xDE00)}, {"content": EMOJI})  # not adjacent, not a pair

    def test_a_key_on_one_side_only(self):
        result = self.one({"content": QUOTE, "path": "a"}, {"content": chr(0x2019)})
        self.assertEqual(result["calls"][0]["only_in_stream"], ["path"])
        result = self.one({"content": QUOTE}, {"content": chr(0x2019), "path": "a"})
        self.assertEqual(result["calls"][0]["only_in_snapshot"], ["path"])
        self.one({"o": {"t": QUOTE, "x": 1}}, {"o": {"t": chr(0x2019)}})

    def test_the_id_or_name_differs(self):
        self.assertFalse(self.one({"c": QUOTE}, {"c": chr(0x2019)}, id="toolu_B")["calls"][0]["id_equal"])
        self.assertFalse(self.one({"c": QUOTE}, {"c": chr(0x2019)}, name="mcp__hermes__write_file")["calls"][0]["name_equal"])

    def test_a_non_string_value_or_structure_differs(self):
        self.one({"content": QUOTE, "limit": 1}, {"content": chr(0x2019), "limit": 2})
        self.one({"content": QUOTE}, {"content": [chr(0x2019)]})
        self.one({"content": [QUOTE]}, {"content": chr(0x2019)})
        self.one({"edits": [QUOTE, "a"]}, {"edits": [chr(0x2019)]})
        self.one({"edits": [QUOTE, 1]}, {"edits": [chr(0x2019), 2]})
        self.one({"edits": [QUOTE, "1"]}, {"edits": [chr(0x2019), 1]})
        self.one({"edits": [QUOTE, 1]}, {"edits": [chr(0x2019), None]})
        self.rejected([call({"content": QUOTE})], [{"type": "tool_use", "id": "toolu_A", "name": READ, "input": [chr(0x2019)]}])

    def test_the_reverse_direction(self):
        self.one({"content": "Ray" + chr(0x2019) + "s"}, {"content": "Ray" + QUOTE + "s"})
        self.one({"content": EMOJI}, {"content": PAIR})

    def test_one_rejected_call_rejects_the_message(self):
        self.rejected([call({"c": QUOTE}), call({"c": QUOTE}, id="toolu_B")],
                      [call({"c": chr(0x2019)}), call({"c": chr(0x2018)}, id="toolu_B")])


STREAMED = {"path": "/" + MARKER + "/Ray" + QUOTE + "s.py", "nested": {"inner": [MARKER + PAIR]}, "limit": 7311}
SHOWN = {**STREAMED, "path": "/" + MARKER + "/Ray" + chr(0x2019) + "s.py", "nested": {"inner": [MARKER + EMOJI]}}


class AuditTests(unittest.TestCase):
    def test_sanitize_keeps_index_count_and_bounded_key_names_only(self):
        keys = ["content", "free text key", *(f"k{i:02}" for i in range(stream_audit.MAX_ONLY_KEYS))]
        entry = {"stage": STAGE, "index": 2, "decoded": 5, "keys": keys, "value": MARKER, "arguments": STREAMED}
        out = stream_audit.sanitize(entry)
        self.assertEqual(set(out), {"stage", "index", "decoded", "keys", "keys_truncated"})
        self.assertEqual((out["index"], out["decoded"], out["keys_truncated"]), (2, 5, 2))
        self.assertEqual(out["keys"][:2], ["<other>", "content"])
        self.assertNotIn(MARKER, json.dumps(out))

    def setUp(self):
        real = subprocess.Popen
        def reroute(argv, *args, **kwargs):
            if "--synthetic-runtime" in argv and "--version" not in argv:
                argv = [SCRIPT if part == PROVIDER_SCRIPT else part for part in argv]
            return real(argv, *args, **kwargs)
        guard = patch("subprocess.Popen", reroute)
        guard.start()
        self.addCleanup(guard.stop)

    def test_the_client_records_one_content_free_entry_and_no_value_reaches_the_audit_file(self):
        provider.ClientTests.setUp(self)
        # A second message after the accepted one fails the turn, so the client writes its audit file.
        with self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
            self.c.create(model=MODEL, messages=[{"role": "user", "content": "__escape__"}], tools=[provider.TOOL])
        self.assertEqual([a for a in self.c.audit if a["stage"] == STAGE],
                         [{"stage": STAGE, "index": 0, "keys": ["nested", "path"], "decoded": 2}])
        files = list((self.directory / "sessions").glob("stream_audit_*.json"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text()
        record = json.loads(text)
        self.assertNotIn("snapshot_mismatch", record)
        self.assertEqual([a["stage"] for a in record["audit"]], ["launch", "user_input", "init", STAGE, "second_message"])
        self.assertEqual(record["audit"][3], {"stage": STAGE, "index": 0, "decoded": 2, "keys": ["nested", "path"],
                                              "keys_truncated": 0})
        for forbidden in (MARKER, MARKER.encode().hex(), "Ray", "7311", "inner", "u2019", "ud83d", "U0001f600"):
            self.assertNotIn(forbidden, text)


def synthetic_runtime(argv):
    """Inert event producer: one tool call whose snapshot decodes its sequences, then a second message."""
    model = argv[argv.index("--model") + 1]
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit({"type": "stream_event", "event": {"type": kind, **kwargs}})
    for _ in sys.stdin:
        emit({"type": "system", "subtype": "init", "model": model, "tools": [client.PREFIX + "read_file"],
              "apiKeySource": "none", "claude_code_version": "2.1.283"})
        block = {"type": "tool_use", "id": "toolu_escape", "name": client.PREFIX + "read_file"}
        ev("message_start", message={"id": "msg_e1", "model": model})
        ev("content_block_start", index=0, content_block={**block, "input": {}})
        ev("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": json.dumps(STREAMED)})
        emit({"type": "assistant", "message": {"id": "msg_e1", "model": model, "content": [{**block, "input": SHOWN}]}})
        ev("content_block_stop", index=0)
        ev("message_delta", delta={"stop_reason": "tool_use"})
        ev("message_stop")
        ev("message_start", message={"id": "msg_e2", "model": model})
        ev("content_block_start", index=0, content_block={"type": "text", "text": ""})
        ev("content_block_delta", index=0, delta={"type": "text_delta", "text": "Later."})
        emit({"type": "assistant", "message": {"id": "msg_e2", "model": model, "content": [{"type": "text", "text": "Later."}]}})
        ev("content_block_stop", index=0)
        ev("message_delta", delta={"stop_reason": "end_turn"})
        ev("message_stop")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
