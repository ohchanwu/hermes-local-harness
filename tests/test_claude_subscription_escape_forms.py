"""Backslash-u forms that the Claude CLI 2.1.302 snapshot leaves undecoded, and the audit's decode diagnosis.

The CLI's snapshot repair (read in the 2.1.302 binary, never run) decodes a literal backslash-u sequence in a
string value except when an odd number of backslashes directly precede it (that backslash is itself escaped),
when it denotes a lone surrogate, or when it denotes a control character (U+0000 to U+001F, U+007F to U+009F).
stream_events must accept exactly that result and nothing else.

Hermetic: synthetic events fed straight into the stream parser; no CLI, network or real transcript. Escape
sequences are built with chr(92), so this source never holds one literally.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_snapshot_mismatch as mismatch  # noqa: E402
import test_claude_subscription_unicode_escape as escape  # noqa: E402

stream_events, ProviderError, call, seq = escape.stream_events, escape.ProviderError, escape.call, escape.seq
TOOL_ERROR = mismatch.TOOL_ERROR
B = chr(92)
NBSP, QUOTE = chr(0xA0), chr(0x2019)
MARKER = "ESCAPE-FORMS-CANARY-71c3"


def decoded_text(parts):
    """`parts` with each code point decoded: the snapshot side of a streamed text built by encoded_text()."""
    return "".join(chr(p) if isinstance(p, int) else p for p in parts)


def encoded_text(parts):
    """`parts` with each code point written as a literal backslash-u sequence: the streamed side."""
    return "".join(seq(p) if isinstance(p, int) else p for p in parts)


def accept(test, streamed, shown, decoded):
    """One call streaming {"content": streamed} against a snapshot showing {"content": shown}; it must be accepted."""
    message = escape.stream([call({"content": streamed})], [call({"content": shown})])
    test.assertTrue(message.done)
    test.assertEqual(message.escapes, [{"index": 0, "keys": ["content"], "decoded": decoded}])
    test.assertEqual(message.calls[0]["arguments"], {"content": streamed})  # Hermes runs the streamed value
    return message


def reject(test, streamed, shown):
    """The same call must still fail with the unchanged error; returns the audit entry for its content key."""
    with test.assertRaises(ProviderError) as raised:
        escape.stream([call({"content": streamed})], [call({"content": shown})])
    test.assertIs(type(raised.exception), ProviderError)
    test.assertEqual(str(raised.exception), TOOL_ERROR)
    return mismatch.key(mismatch.classify(raised.exception), "content")


class AlreadyAcceptedTests(unittest.TestCase):
    """Forms tried from the card that the baseline decoder already accepts; kept as regression tests."""

    def test_two_three_and_six_sequences(self):
        for count in (2, 3, 6):
            with self.subTest(count=count):
                parts = [p for i in range(count) for p in (f"w{i} ", 0xA0)]
                accept(self, encoded_text(parts), decoded_text(parts), count)

    def test_sequences_next_to_each_other(self):
        parts = [0xA0, 0xA0, 0x2019, 0xE9, 0xA0, 0xA0]
        accept(self, encoded_text(parts), decoded_text(parts), 6)

    def test_a_sequence_next_to_another_escape(self):
        # Literal backslash-n, backslash-t and backslash-quote stay as written on both sides.
        for other in (B + "n", B + "t", B + '"', B + "x41"):
            with self.subTest(other=other):
                accept(self, other + seq(0xA0) + other + seq(0xA0), other + NBSP + other + NBSP, 2)

    def test_an_even_number_of_backslashes_before_the_sequence(self):
        for run in (2, 4):
            with self.subTest(run=run):
                accept(self, "a" + B * run + seq(0xA0) + seq(0xA0), "a" + B * run + NBSP + NBSP, 2)


class OddBackslashTests(unittest.TestCase):
    """A sequence after an odd number of backslashes: the CLI keeps it as written and decodes the others."""

    def test_a_doubled_backslash_before_u_among_two_three_and_six_sequences(self):
        for count in (2, 3, 6):
            with self.subTest(count=count):
                parts = [p for i in range(count - 1) for p in (f"w{i} ", 0xA0)]
                streamed = "x " + B + seq(0xA0) + " " + encoded_text(parts)
                shown = "x " + B + seq(0xA0) + " " + decoded_text(parts)
                accept(self, streamed, shown, count - 1)

    def test_one_three_and_five_backslashes_before_the_sequence(self):
        for run in (1, 3, 5):
            with self.subTest(run=run):
                accept(self, B * run + seq(0xA0) + seq(0xA0), B * run + seq(0xA0) + NBSP, 1)

    def test_a_surrogate_pair_after_a_doubled_backslash_stays_whole(self):
        pair = seq(0xD83D) + seq(0xDE00)
        accept(self, B + pair + seq(0x2019), B + pair + QUOTE, 1)

    def test_sequences_next_to_each_other_after_a_doubled_backslash(self):
        # Only the first sequence follows the doubled backslash; the next one follows a hex digit.
        accept(self, B + seq(0xA0) + seq(0xA0) + seq(0xA0), B + seq(0xA0) + NBSP + NBSP, 2)

    def test_near_misses_are_rejected(self):
        streamed = "a" + B + seq(0xA0) + "b" + seq(0xA0)
        reject(self, streamed, "a" + B + NBSP + "b" + NBSP)          # the doubled one decoded as well
        reject(self, streamed, "a" + B + seq(0xA0) + "c" + NBSP)     # one other character differs
        reject(self, streamed, "a" + seq(0xA0) + "b" + NBSP)         # the second backslash dropped
        reject(self, streamed, "a" + B + seq(0xA0) + "b" + seq(0xA0) + " ")


class ControlCharacterTests(unittest.TestCase):
    """A sequence for a control character: the CLI keeps it as written and decodes the others."""

    def test_control_characters_at_each_range_boundary_stay(self):
        for code in (0x00, 0x09, 0x1B, 0x1F, 0x7F, 0x85, 0x9F):
            with self.subTest(code=hex(code)):
                accept(self, seq(code) + "a" + seq(0xA0) + seq(0xA0), seq(code) + "a" + NBSP + NBSP, 2)

    def test_the_characters_next_to_the_ranges_are_decoded(self):
        for code in (0x20, 0x7E, 0xA0):
            with self.subTest(code=hex(code)):
                accept(self, seq(code) + seq(0x1F) + seq(0x7F) + seq(0x2019),
                       chr(code) + seq(0x1F) + seq(0x7F) + QUOTE, 2)

    def test_a_control_sequence_next_to_a_decoded_one(self):
        accept(self, seq(0xA0) + seq(0x1B) + seq(0xA0), NBSP + seq(0x1B) + NBSP, 2)

    def test_near_misses_are_rejected(self):
        streamed = "a" + seq(0x1B) + "b" + seq(0xA0)
        reject(self, streamed, "a" + chr(0x1B) + "b" + NBSP)        # the control sequence decoded as well
        reject(self, streamed, "a" + seq(0x1B) + "c" + NBSP)        # one other character differs
        reject(self, streamed, "a" + seq(0x1C) + "b" + NBSP)        # a different control sequence


class DiagnosisTests(unittest.TestCase):
    """snapshot_mismatch() adds `escape_decoding` to each unequal string key: counts, lengths, classes only."""

    def diagnosis(self, streamed, shown, other=None):
        entry = reject(self, streamed, shown) if other is None else self.other_key(streamed, shown, other)
        self.assertIn("escape_decoding", entry)
        return entry["escape_decoding"]

    def other_key(self, streamed, shown, other):
        with self.assertRaises(ProviderError) as raised:
            escape.stream([call({"content": streamed, "path": "a"})], [call({"content": shown, "path": other})])
        return mismatch.key(mismatch.classify(raised.exception), "content")

    def test_a_doubled_backslash_before_the_first_difference(self):
        streamed = "ab" + B + seq(0xA0) + "c" + seq(0xA0)
        result = self.diagnosis(streamed, "ab" + B + NBSP + "c" + NBSP)
        self.assertEqual(result, {
            "sequences": 2, "decoded_sequences": 1, "kept_odd_backslashes": 1, "kept_surrogate": 0, "kept_control": 0,
            "decoded_length": len(streamed) - 5, "decoded_equal": False, "first_difference": 3, "stream_index": 3,
            "decoded_char": mismatch.char("Po", True), "snapshot_char": mismatch.char("Zs", False),
            "sequence_at_difference": True, "backslash_before_sequence": True})

    def test_a_control_sequence_at_the_first_difference(self):
        streamed = seq(0xA0) + "x" + seq(0x1B) + seq(0xD800)
        result = self.diagnosis(streamed, NBSP + "x" + chr(0x1B) + seq(0xD800))
        self.assertEqual(result, {
            "sequences": 3, "decoded_sequences": 1, "kept_odd_backslashes": 0, "kept_surrogate": 1, "kept_control": 1,
            "decoded_length": len(streamed) - 5, "decoded_equal": False, "first_difference": 2, "stream_index": 7,
            "decoded_char": mismatch.char("Po", True), "snapshot_char": mismatch.char("Cc", True, control=True),
            "sequence_at_difference": True, "backslash_before_sequence": False})

    def test_a_difference_away_from_any_sequence(self):
        result = self.diagnosis(seq(0xA0) + seq(0x2019) + "abc", NBSP + QUOTE + "abd")
        self.assertEqual({k: result[k] for k in ("first_difference", "stream_index", "decoded_char", "snapshot_char",
                                                 "sequence_at_difference", "backslash_before_sequence")},
                         {"first_difference": 4, "stream_index": 14, "decoded_char": mismatch.char("Ll", True),
                          "snapshot_char": mismatch.char("Ll", True), "sequence_at_difference": False,
                          "backslash_before_sequence": None})

    def test_a_snapshot_that_ends_first(self):
        result = self.diagnosis(seq(0xA0) + "abc", NBSP + "ab")
        self.assertEqual((result["first_difference"], result["stream_index"], result["decoded_char"],
                          result["snapshot_char"]), (3, 8, mismatch.char("Ll", True), None))

    def test_no_sequences(self):
        result = self.diagnosis("abc", "abd")
        self.assertEqual({k: result[k] for k in ("sequences", "decoded_sequences", "decoded_length", "decoded_equal",
                                                 "first_difference", "stream_index")},
                         {"sequences": 0, "decoded_sequences": 0, "decoded_length": 3, "decoded_equal": False,
                          "first_difference": 2, "stream_index": 2})

    def test_a_key_that_decodes_equal_while_another_key_differs(self):
        result = self.diagnosis("a" + seq(0xA0), "a" + NBSP, other="b")
        self.assertEqual(result, {"sequences": 1, "decoded_sequences": 1, "kept_odd_backslashes": 0, "kept_surrogate": 0,
                                  "kept_control": 0, "decoded_length": 2, "decoded_equal": True})

    def test_equal_keys_and_non_string_values_have_no_diagnosis(self):
        error = mismatch.fail([call({"content": "a", "limit": 1, "path": "x"})],
                              [call({"content": "a", "limit": 2, "path": ["x"]})])
        calls = mismatch.classify(error)["calls"][0]["keys"]
        self.assertEqual([k["key"] for k in calls], ["content", "limit", "path"])
        for entry in calls:
            self.assertNotIn("escape_decoding", entry)

    written = mismatch.ContentFreeTests.written  # the client writes the audit file into a temporary home

    def test_no_value_reaches_the_audit_file(self):
        streamed = MARKER + " " + B + seq(0x2019) + " " + seq(0x1B) + " " + MARKER + seq(0xA0) + "7311"
        shown = MARKER + " " + B + QUOTE + " " + chr(0x1B) + " " + MARKER + NBSP + "7311"
        with self.assertRaises(ProviderError) as raised:
            escape.stream([call({"content": streamed})], [call({"content": shown})])
        text = self.written(raised.exception)
        entry = json.loads(text)["snapshot_mismatch"]["calls"][0]["keys"][0]
        self.assertEqual((entry["key"], entry["escape_decoding"]["sequences"]), ("content", 3))
        # Digits alone are not checked: hashes and the timestamp hold arbitrary digit runs.
        for forbidden in (MARKER, MARKER.encode().hex(), "u2019", "u001b", "u00a0", "ESCAPE-FORMS"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
