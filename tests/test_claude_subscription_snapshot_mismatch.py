"""A stream/snapshot mismatch adds a content-free `snapshot_mismatch` classification to the stream audit.

Hermetic: synthetic events fed straight into the stream parser; no CLI, network or real transcript.
All argument values are synthetic.
"""
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
MARKER = "SNAPSHOT-MISMATCH-CANARY-6d41"
stream_events = importlib.import_module("subscription_plugin.stream_events")
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
ProviderError = stream_events.ProviderError
MODEL, READ = provider.MODEL, "mcp__hermes__read_file"
DECLARED = {READ, "mcp__hermes__write_file"}
TOOL_ERROR = "stream/snapshot tool identity or arguments mismatch"


def call(input, id="toolu_A", name=READ):
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def fail(streamed, snapshot, raw=None, width=7):
    """Stream one message whose tool_use blocks are `streamed` (or raw JSON) and whose snapshots are `snapshot`."""
    message = stream_events.Message({MODEL})
    def ev(kind, **kwargs):
        message.feed({"type": "stream_event", "event": {"type": kind, **kwargs}})
    ev("message_start", message={"id": "msg_1", "model": MODEL})
    for index, (sent, shown) in enumerate(zip(streamed, snapshot)):
        ev("content_block_start", index=index, content_block={**sent, "input": {}})
        text = raw if raw is not None else json.dumps(sent["input"])
        for start in range(0, len(text), width):
            ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": text[start:start + width]})
        message.feed({"type": "assistant", "message": {"id": "msg_1", "model": MODEL, "content": [shown]}})
        ev("content_block_stop", index=index)
    ev("message_delta", delta={"stop_reason": "tool_use"})
    try:
        ev("message_stop")
    except ProviderError as error:
        return error
    raise AssertionError("no mismatch raised")


def classify(error):
    record = stream_audit.payload(error, "s", MODEL, "2.1.302", [], stream_audit.StreamLog(), declared=DECLARED)
    return record["snapshot_mismatch"]


def key(result, name):
    return next(k for k in result["calls"][0]["keys"] if k["key"] == name)


def char(category, ascii, surrogate=False, control=False):
    return {"category": category, "ascii": ascii, "surrogate": surrogate, "control": control}


class ToolMismatchTests(unittest.TestCase):
    def test_the_error_is_unchanged_and_still_fails_closed(self):
        error = fail([call({"path": "a"})], [call({"path": "b"})])
        self.assertIs(type(error), ProviderError)
        self.assertEqual(str(error), TOOL_ERROR)

    def test_id_differs(self):
        result = classify(fail([call({"path": "a"})], [call({"path": "a"}, id="toolu_B")]))
        self.assertEqual((result["kind"], result["streamed_calls"], result["snapshot_tool_uses"], result["calls_truncated"]),
                         ("tool_use", 1, 1, 0))
        first = result["calls"][0]
        self.assertEqual({k: first[k] for k in ("index", "id_equal", "name_equal", "stream_name", "snapshot_name",
                                                "stream_input_type", "snapshot_input_type")},
                         {"index": 0, "id_equal": False, "name_equal": True, "stream_name": READ, "snapshot_name": READ,
                          "stream_input_type": "object", "snapshot_input_type": "object"})
        self.assertTrue(key(result, "path")["equal"])

    def test_name_differs_and_an_undeclared_name_is_not_recorded(self):
        result = classify(fail([call({"path": "a"})], [call({"path": "a"}, name="mcp__other__secret_tool")]))
        first = result["calls"][0]
        self.assertEqual((first["id_equal"], first["name_equal"], first["stream_name"], first["snapshot_name"]),
                         (True, False, READ, "<undeclared>"))
        self.assertNotIn("secret_tool", json.dumps(result))

    def test_extra_and_missing_keys(self):
        result = classify(fail([call({"path": "a", "limit": 3})], [call({"path": "a", "offset": 1, "mode": "r"})]))
        first = result["calls"][0]
        self.assertEqual((first["only_in_stream"], first["only_in_snapshot"]), (["limit"], ["mode", "offset"]))
        self.assertEqual((first["only_in_stream_truncated"], first["only_in_snapshot_truncated"]), (0, 0))
        self.assertEqual([k["key"] for k in first["keys"]], ["path"])

    def test_fragment_totals(self):
        arguments = {"path": "a" * 50}
        first = classify(fail([call(arguments)], [call({"path": "b"})], width=7))["calls"][0]
        text = json.dumps(arguments)
        self.assertEqual((first["fragments"], first["fragment_chars"]), (-(-len(text) // 7), len(text)))

    def test_string_differs_at_one_index(self):
        cases = (("abcédef", char("Ll", False)), ("abc\x01def", char("Cc", True, control=True)),
                 ("abc\ud800def", char("Cs", False, surrogate=True)))
        for shown, expected in cases:
            with self.subTest(expected["category"]):
                entry = key(classify(fail([call({"path": "abcXdef"})], [call({"path": shown})])), "path")
                self.assertEqual({k: entry[k] for k in ("stream_type", "snapshot_type", "stream_length", "snapshot_length",
                                                        "equal", "equal_canonical", "first_difference", "prefix")},
                                 {"stream_type": "string", "snapshot_type": "string", "stream_length": 7,
                                  "snapshot_length": 7, "equal": False, "equal_canonical": False,
                                  "first_difference": 3, "prefix": None})
                self.assertEqual((entry["stream_char"], entry["snapshot_char"]), (char("Lu", True), expected))
                self.assertNotEqual(entry["stream_sha256"], entry["snapshot_sha256"])

    def test_integer_against_float_is_equal_after_a_canonical_round_trip(self):
        # Python's == takes 1 for 1.0, so another key differs to make the check fail.
        result = classify(fail([call({"limit": 1, "path": "a"})], [call({"limit": 1.0, "path": "b"})]))
        entry = key(result, "limit")
        self.assertEqual({k: entry[k] for k in ("stream_type", "snapshot_type", "stream_length", "snapshot_length",
                                                "equal", "equal_canonical")},
                         {"stream_type": "integer", "snapshot_type": "number", "stream_length": 1, "snapshot_length": 3,
                          "equal": False, "equal_canonical": True})
        self.assertNotIn("first_difference", entry)
        self.assertEqual(key(result, "path")["equal"], False)

    def test_truncated_string_is_a_prefix(self):
        entry = key(classify(fail([call({"content": "x" * 30})], [call({"content": "x" * 12})])), "content")
        self.assertEqual((entry["stream_length"], entry["snapshot_length"], entry["first_difference"], entry["prefix"],
                          entry["stream_char"], entry["snapshot_char"]), (30, 12, 12, "snapshot", char("Ll", True), None))

    def test_bounds_are_marked(self):
        many = {f"k{i:03}": i for i in range(stream_audit.MAX_MISMATCH_KEYS + 5)}
        extra = {f"s{i:03}": i for i in range(stream_audit.MAX_ONLY_KEYS + 2)}
        first = classify(fail([call(many)], [call({**many, **extra, "k000": -1})]))["calls"][0]
        self.assertEqual((len(first["keys"]), first["keys_truncated"]), (stream_audit.MAX_MISMATCH_KEYS, 5))
        self.assertEqual((len(first["only_in_snapshot"]), first["only_in_snapshot_truncated"]), (stream_audit.MAX_ONLY_KEYS, 2))
        result = stream_audit.snapshot_mismatch("tool_use", [], [call({})] * 25, DECLARED)
        self.assertEqual((len(result["calls"]), result["calls_truncated"], result["calls"][0]["stream_input_type"]),
                         (20, 5, "<missing>"))


class ContentFreeTests(unittest.TestCase):
    def written(self, error):
        """The audit file the client writes for `error`, with its declared tools, into a temporary home."""
        with tempfile.TemporaryDirectory() as home:
            c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
            c._home, c._model, c._scope, c._tools = Path(home), MODEL, ("s",), [{"name": "read_file"}]
            c._persist_stream_audit(stream_audit.StreamLog(), error, SimpleNamespace(read=lambda: None), {})
            files = list((Path(home) / "sessions").glob("stream_audit_*.json"))
            self.assertEqual(len(files), 1)
            return files[0].read_text()

    def test_no_argument_value_or_marker_reaches_the_file(self):
        values = {"path": f"/{MARKER}/a", "content": f"{MARKER} body ünï\x01", "limit": 7311, "flags": [MARKER, 9133],
                  "nested": {"inner": MARKER}}
        shown = {**values, "content": f"{MARKER} body ünï\x02", "path": f"/{MARKER}", "extra": MARKER}
        text = self.written(fail([call(values)], [call(shown)]))
        record = json.loads(text)
        self.assertEqual(record["error"]["message"], TOOL_ERROR)
        self.assertEqual(record["snapshot_mismatch"]["calls"][0]["stream_name"], READ)  # declared names come from the client
        self.assertEqual(record["snapshot_mismatch"]["calls"][0]["only_in_snapshot"], ["extra"])
        self.assertNotIn(MARKER, text)
        self.assertNotIn(MARKER.encode().hex(), text)
        for value in [*values.values(), *shown.values(), "ünï", "\\u00fc"]:
            if not isinstance(value, (dict, list)):
                self.assertNotIn(json.dumps(value).strip('"'), text)
        for value in ("7311", "9133", "body"):
            self.assertNotIn(value, text)

    def test_text_content_mismatch_is_classified_without_its_text(self):
        message = stream_events.Message({MODEL})
        feed = lambda kind, **kw: message.feed({"type": "stream_event", "event": {"type": kind, **kw}})
        feed("message_start", message={"id": "msg_1", "model": MODEL})
        feed("content_block_start", index=0, content_block={"type": "text", "text": ""})
        feed("content_block_delta", index=0, delta={"type": "text_delta", "text": MARKER + " streamed"})
        message.feed({"type": "assistant", "message": {"id": "msg_1", "model": MODEL,
                                                       "content": [{"type": "text", "text": MARKER + " str"}]}})
        feed("content_block_stop", index=0)
        feed("message_delta", delta={"stop_reason": "end_turn"})
        with self.assertRaisesRegex(ProviderError, r"^stream/snapshot content mismatch$") as raised:
            feed("message_stop")
        text = self.written(raised.exception)
        result = json.loads(text)["snapshot_mismatch"]
        self.assertEqual({k: result[k] for k in ("kind", "stream_chars", "snapshot_chars", "first_difference", "prefix")},
                         {"kind": "text", "stream_chars": len(MARKER) + 9, "snapshot_chars": len(MARKER) + 4,
                          "first_difference": len(MARKER) + 4, "prefix": "snapshot"})
        self.assertNotIn(MARKER, text)
        self.assertNotIn("streamed", text)

    def test_other_errors_have_no_classification(self):
        self.assertNotIn("snapshot_mismatch", json.loads(self.written(ProviderError("duplicate streamed message"))))


if __name__ == "__main__":
    unittest.main()
