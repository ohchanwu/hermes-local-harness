"""Rebuild of a transcript that Hermes' context compaction left starting with tool calls.

Hermetic: reuses the synthetic CLI harness of test_claude_subscription_provider.py.
All fixture content is neutral, synthetic text.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
MODEL, TOOL = provider.MODEL, provider.TOOL


def call(call_id, path="/nonexistent/synthetic"):
    return {"id": call_id, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": path})}}


def calls(*ids, content=""):
    return {"role": "assistant", "content": content, "tool_calls": [call(i) for i in ids]}


def result(call_id, content):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def user(content):
    return {"role": "user", "content": content}


def compacted(tail):
    """The shape seen after a compaction: system, a complete tool-call group, then the summary turn."""
    rows = [{"role": "system", "content": "Synthetic system"},
            calls("toolu_lead"), result("toolu_lead", "LEAD RESULT"),
            user("[CONTEXT COMPACTION] Synthetic summary of earlier turns."),
            {"role": "assistant", "content": "Synthetic acknowledgement."},
            user("Synthetic request."),
            calls("toolu_a", "toolu_b"), result("toolu_a", "A RESULT"), result("toolu_b", "B RESULT"),
            calls("toolu_c"), result("toolu_c", "C RESULT")]
    return rows + [user("What did it say?")] if tail == "user" else rows


REPLAY = {"tool": ["user", "assistant", "user", "assistant", "tool", "tool", "assistant"],
          "user": ["user", "assistant", "user", "assistant", "tool", "tool", "assistant", "tool"]}


class LeadingGroupHistoryTests(unittest.TestCase):
    def test_leading_group_is_left_out_of_the_replay_but_tracked(self):
        for tail in ("tool", "user"):
            with self.subTest(tail=tail):
                messages = compacted(tail)
                h = client.History()
                self.assertEqual(h.accept(messages), [client.History.canonical(messages[-1])])
                self.assertEqual([m["role"] for m in h.restored], REPLAY[tail])
                self.assertEqual(h.restored[0]["content"], messages[3]["content"])
                self.assertEqual(h.skipped, 2)
                self.assertEqual(h.messages, [client.History.canonical(m) for m in messages])
                text, _ = client.render_restored(h.restored, h.messages[-1])
                self.assertNotIn("LEAD RESULT", text)
                self.assertNotIn("toolu_lead", text)
                self.assertIn("[CONTEXT COMPACTION] Synthetic summary", text)

    def test_several_complete_groups_in_any_result_order_are_accepted(self):
        messages = [calls("x"), result("x", "X"), calls("y", "z"), result("z", "Z"), result("y", "Y"),
                    user("summary"), calls("w"), result("w", "W")]
        h = client.History()
        h.accept(messages)
        self.assertEqual(h.skipped, 5)
        self.assertEqual([m["role"] for m in h.restored], ["user", "assistant"])

    def test_a_normal_rebuild_skips_nothing(self):
        h = client.History()
        h.accept([user("Read"), calls("a"), result("a", "A"), user("next")])
        self.assertEqual((h.skipped, len(h.restored)), (0, 3))

    def test_strict_continuation_uses_the_transcript_as_hermes_sends_it(self):
        for tail in ("tool", "user"):
            with self.subTest(tail=tail, next="user"):
                h, messages = client.History(), compacted(tail)
                h.accept(messages)
                answer = {"role": "assistant", "content": "done"}
                h.assistant(answer)
                self.assertEqual(h.accept(messages + [answer, user("next")]), [user("next")])
                self.assertIsNone(h.restored)
                self.assertEqual(h.skipped, 0)
            with self.subTest(tail=tail, next="tool"):
                h, messages = client.History(), compacted(tail)
                h.accept(messages)
                h.assistant(calls("toolu_d"))
                self.assertEqual(h.accept(messages + [calls("toolu_d"), result("toolu_d", "D")]),
                                 [result("toolu_d", "D")])
            with self.subTest(tail=tail, next="without the leading group"):
                h, messages = client.History(), compacted(tail)
                h.accept(messages)
                h.assistant(answer)
                with self.assertRaises(client.ProviderError):
                    h.accept(messages[:1] + messages[3:] + [answer, user("next")])

    def test_malformed_leading_rows_are_still_rejected(self):
        system = {"role": "system", "content": "S"}
        invalid = {
            "assistant without calls": [system, {"role": "assistant", "content": "text"}, user("summary")],
            "lone tool row": [result("a", "A"), user("summary")],
            "lone tool row after system": [system, result("a", "A"), user("summary")],
            "missing result": [calls("a", "b"), result("a", "A"), user("summary")],
            "no results": [calls("a"), user("summary")],
            "extra result": [calls("a"), result("a", "A"), result("b", "B"), user("summary")],
            "duplicate result": [calls("a"), result("a", "A"), result("a", "A"), user("summary")],
            "wrong result": [calls("a"), result("b", "B"), user("summary")],
            "group then assistant text": [calls("a"), result("a", "A"), {"role": "assistant", "content": "t"}, user("u")],
            "group then system": [calls("a"), result("a", "A"), system, user("u")],
            "group then incomplete group": [calls("a"), result("a", "A"), calls("b"), user("u")],
            "only a group": [system, calls("a"), result("a", "A")],
            "only groups": [calls("a"), result("a", "A"), calls("b"), result("b", "B")],
            "ends with assistant": [calls("a"), result("a", "A"), user("u"), {"role": "assistant", "content": "t"}],
            "ends with assistant calls": [calls("a"), result("a", "A"), user("u"), calls("b")],
            "final results incomplete": [calls("a"), result("a", "A"), user("u"), calls("b", "c"), result("b", "B")],
            "later result for a skipped call": [calls("a"), result("a", "A"), user("u"), result("a", "A")],
            "orphan result later": [calls("a"), result("a", "A"), user("u"), result("x", "X"), user("v")],
        }
        for name, messages in invalid.items():
            h = client.History()
            with self.subTest(name), self.assertRaises(client.ProviderError):
                h.accept(messages)
            self.assertEqual((h.messages, h.restored, h.skipped), ([], None, 0))


class LeadingGroupClientTests(unittest.TestCase):
    setUp = provider.ClientTests.setUp  # the synthetic-CLI, no-network, no-real-process harness

    def rebuild(self, tail, sent):
        original = client.Runtime.send
        def record(runtime, text, *args, **kwargs):
            sent.append(text)
            return original(runtime, text, *args, **kwargs)
        messages = compacted(tail)
        with patch.object(client.Runtime, 'send', record):
            response = self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        self.assertEqual(response.choices[0].message.content, 'RESTORED C RESULT')
        self.assertIn('<restored-transcript-', sent[0])
        self.assertIn('[CONTEXT COMPACTION] Synthetic summary', sent[0])
        self.assertNotIn('LEAD RESULT', sent[0])
        self.assertNotIn('toolu_lead', sent[0])
        rebuilds = [a for a in self.c.audit if a['stage'] == 'rebuild']
        self.assertEqual([(a['messages'], a['tail'], a['skipped_leading']) for a in rebuilds],
                         [(len(REPLAY[tail]), tail, 2)])
        return messages + [{"role": "assistant", "content": response.choices[0].message.content}]

    def assert_one_session(self):
        stages = [a['stage'] for a in self.c.audit]
        self.assertEqual((stages.count('launch'), stages.count('rebuild'), stages.count('session_reset')), (1, 1, 0))

    def next_user_turn(self, tail):
        sent = []
        messages = self.rebuild(tail, sent)
        original = client.Runtime.send
        def record(runtime, text, *args, **kwargs):
            sent.append(text)
            return original(runtime, text, *args, **kwargs)
        with patch.object(client.Runtime, 'send', record):
            followup = self.c.create(model=MODEL, messages=messages + [user("Followup")], tools=[TOOL])
        self.assertEqual(followup.choices[0].message.content, 'FOLLOWUP')
        self.assertEqual(sent[1:], ['Followup'])
        self.assert_one_session()

    def next_tool_results(self, tail):
        messages = self.rebuild(tail, []) + [user("__tool__")]
        response = self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        self.assertEqual(response.choices[0].finish_reason, 'tool_calls')
        message = response.choices[0].message
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in message.tool_calls]})
        messages.append(result(message.tool_calls[0].id, "NEW RESULT"))
        answer = self.c.create(model=MODEL, messages=copy.deepcopy(messages), tools=[TOOL])
        self.assertEqual(answer.choices[0].message.content, 'NEW RESULT')
        self.assertEqual(len([a for a in self.c.audit if a['stage'] == 'result_returned']), 1)
        self.assert_one_session()

    def test_tool_tail_rebuild_then_next_user_turn_continues_strictly(self):
        self.next_user_turn("tool")

    def test_user_tail_rebuild_then_next_user_turn_continues_strictly(self):
        self.next_user_turn("user")

    def test_tool_tail_rebuild_then_next_tool_results_continue_strictly(self):
        self.next_tool_results("tool")

    def test_user_tail_rebuild_then_next_tool_results_continue_strictly(self):
        self.next_tool_results("user")

    def test_a_normal_rebuild_records_nothing_skipped(self):
        messages = [{"role": "system", "content": "Synthetic system"}, user("Read it"), calls("toolu_old"),
                    result("toolu_old", "OLD RESULT")]
        self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        self.assertEqual([a['skipped_leading'] for a in self.c.audit if a['stage'] == 'rebuild'], [0])

    def test_malformed_leading_group_fails_before_launch(self):
        for messages in ([{"role": "system", "content": "Synthetic system"}, calls("a", "b"), result("a", "A"), user("u")],
                         [{"role": "system", "content": "Synthetic system"}, calls("a"), result("a", "A")]):
            with self.subTest(roles=[m["role"] for m in messages]), self.assertRaises(client.ProviderError):
                self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        self.assertEqual(self.launches, [])


if __name__ == "__main__":
    unittest.main()
