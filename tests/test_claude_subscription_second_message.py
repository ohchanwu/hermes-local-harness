"""A second assistant message after a completed one: whole-message buffering and the decision table.

Hermetic: the decision function is pure; the client tests reuse the synthetic-CLI harness of
test_claude_subscription_provider.py (no real CLI, no network, a temporary HERMES_HOME) with the
model-runtime child rerouted to the small event producer below. All ids and texts are synthetic.
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

client = provider.client
decision = importlib.import_module("subscription_plugin.second_message")
stream_events = importlib.import_module("subscription_plugin.stream_events")
MODEL, TOOL = provider.MODEL, provider.TOOL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())
APPEND, KEEP_FIRST, KEEP_LAST, FAIL = decision.APPEND, decision.KEEP_FIRST, decision.KEEP_LAST, decision.FAIL


def msg(id_, stop, text="", calls=(), model=MODEL):
    return {"id": id_, "model": model, "stop": stop, "text": text,
            "calls": [{"id": c, "name": "mcp__hermes__read_file", "arguments": {"path": "/synthetic/" + c}} for c in calls]}


TOOL_1 = msg("m1", "tool_use", "Checking.", ["t1"])
# (name, first, second, keyword evidence, expected outcome, expected row)
TABLE = [
    ("replay of a complete reply", msg("m1", "end_turn", "Done."), msg("m2", "end_turn", "Done."), {}, KEEP_FIRST, "replay"),
    ("replay with the same id", msg("m1", "end_turn", "Done."), msg("m1", "end_turn", "Done."), {}, KEEP_FIRST, "replay"),
    ("replay of a tool-call message", TOOL_1, msg("m2", "tool_use", "Checking.", ["t1"]), {}, KEEP_FIRST, "replay"),
    ("cut off, second extends it", msg("m1", "max_tokens", "Part one"), msg("m2", "end_turn", "Part one and two."), {},
     APPEND, "continuation"),
    ("cut off, second is new text", msg("m1", "max_tokens", "Part one"), msg("m2", "end_turn", " and two."), {},
     APPEND, "continuation"),
    ("cut off without text, second has it", msg("m1", "max_tokens", ""), msg("m2", "end_turn", "Text."), {},
     APPEND, "continuation"),
    ("cut off, second continues with a call", msg("m1", "max_tokens", "Part"), msg("m2", "tool_use", " more.", ["t2"]), {},
     APPEND, "continuation"),
    ("internal step precedes the real reply (the live audits)", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"], "errored": ["t1"]}, KEEP_LAST, "internal_step"),
    ("internal step, then a text reply", TOOL_1, msg("m2", "end_turn", "Answer."), {"answered": ["t1"], "errored": ["t1"]},
     KEEP_LAST, "internal_step"),
    ("internal step for two parallel calls", msg("m1", "tool_use", "", ["t1", "t1b"]), msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1b", "t1"], "errored": ["t1", "t1b"]}, KEEP_LAST, "internal_step"),
    ("internal step, the same call rejected twice", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1", "t1"], "errored": ["t1", "t1"]}, KEEP_LAST, "internal_step"),
    # Every FAIL fallback:
    ("model changed", msg("m1", "end_turn", "Done."), msg("m2", "end_turn", "Done.", model="other"), {}, FAIL, "model_changed"),
    ("first stop unknown", msg("m1", "refusal", "x"), msg("m2", "end_turn", "x"), {}, FAIL, "unknown_stop"),
    ("second stop unknown", TOOL_1, msg("m2", None, "", ["t2"]), {"answered": ["t1"]}, FAIL, "unknown_stop"),
    ("replay after the runtime answered the calls", TOOL_1, msg("m2", "tool_use", "Checking.", ["t1"]),
     {"answered": ["t1"]}, FAIL, "replay_after_internal_step"),
    ("same id, different content", msg("m1", "end_turn", "Done."), msg("m1", "end_turn", "Done. More."), {},
     FAIL, "same_id_different_content"),
    ("cut off, then tool results", msg("m1", "max_tokens", "Part"), msg("m2", "end_turn", " two."), {"answered": ["t9"]},
     FAIL, "cut_off_with_tool_results"),
    ("cut off, second repeats it exactly", msg("m1", "max_tokens", "Part"), msg("m2", "end_turn", "Part"), {},
     FAIL, "cut_off_without_continuation"),
    ("cut off, second is shorter", msg("m1", "max_tokens", "Part one"), msg("m2", "end_turn", "Part"), {},
     FAIL, "cut_off_without_continuation"),
    ("cut off, second is empty", msg("m1", "max_tokens", "Part"), msg("m2", "tool_use", "", ["t2"]), {},
     FAIL, "cut_off_without_continuation"),
    ("complete, second extends it", msg("m1", "end_turn", "Alpha."), msg("m2", "end_turn", "Alpha. More."), {},
     FAIL, "complete_not_replay"),
    ("complete, second disjoint", msg("m1", "end_turn", "Alpha."), msg("m2", "end_turn", "Beta."), {},
     FAIL, "complete_not_replay"),
    ("tool_use, no internal step", TOOL_1, msg("m2", "tool_use", "", ["t2"]), {}, FAIL, "tool_use_without_internal_step"),
    ("internal step answered only some calls", msg("m1", "tool_use", "", ["t1", "t1b"]), msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"]}, FAIL, "internal_step_partial"),
    ("internal step answered a foreign call", TOOL_1, msg("m2", "tool_use", "", ["t2"]), {"answered": ["t1", "tx"]},
     FAIL, "internal_step_partial"),
    ("internal step, but the CLI also asked Hermes", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"], "requested": True}, FAIL, "internal_step_after_mcp_request"),
    ("internal step after the first was forwarded", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"], "forwarded": True}, FAIL, "internal_step_after_forwarding"),
    ("internal step, second reuses a call id", TOOL_1, msg("m2", "tool_use", "", ["t2", "t1"]), {"answered": ["t1"]},
     FAIL, "internal_step_reused_call"),
    # The runtime's own answers must all be rejections (built-in tools are off); anything else may have run.
    ("internal step, one success among several answers", msg("m1", "tool_use", "", ["t1", "t1b", "t1c"]),
     msg("m2", "tool_use", "", ["t2"]), {"answered": ["t1", "t1b", "t1c"], "errored": ["t1", "t1c"]},
     FAIL, "internal_step_non_error_result"),
    ("internal step, is_error missing (no error evidence)", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"]}, FAIL, "internal_step_non_error_result"),
    ("internal step, the same call answered as error and as success", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1", "t1"], "errored": ["t1"]}, FAIL, "internal_step_non_error_result"),
    ("internal step, one call's error counted for another's success", msg("m1", "tool_use", "", ["t1", "t1b"]),
     msg("m2", "tool_use", "", ["t2"]), {"answered": ["t1", "t1b"], "errored": ["t1", "t1"]},
     FAIL, "internal_step_non_error_result"),
    ("internal step, error evidence for a call never answered", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"], "errored": ["t1", "tx"]}, FAIL, "internal_step_non_error_result"),
    ("non-error answer, but an earlier row still decides", TOOL_1, msg("m2", "tool_use", "", ["t2"]),
     {"answered": ["t1"], "requested": True}, FAIL, "internal_step_after_mcp_request"),
]


class DecisionTableTests(unittest.TestCase):
    def test_every_row_and_every_fail_fallback(self):
        rows = set()
        for name, first, second, evidence, outcome, row in TABLE:
            with self.subTest(name):
                self.assertEqual(decision.decide(first, second, **evidence), (outcome, row))
                rows.add(row)
        # Every row the function can return is exercised (too_many_messages is the client's own bound).
        source = Path(decision.__file__).read_text()
        self.assertEqual(rows, set(__import__("re").findall(r'(?:APPEND|KEEP_FIRST|KEEP_LAST|FAIL), "(\w+)"', source)))

    def test_decide_is_pure_and_deterministic(self):
        for name, first, second, evidence, outcome, row in TABLE:
            frozen = json.dumps([first, second, evidence], sort_keys=True)
            self.assertEqual({decision.decide(first, second, **evidence) for _ in range(3)}, {(outcome, row)})
            self.assertEqual(json.dumps([first, second, evidence], sort_keys=True), frozen, name)

    def test_appended_text(self):
        self.assertEqual(decision.appended_text("Part one", "Part one and two."), " and two.")
        self.assertEqual(decision.appended_text("Part one", " and two."), " and two.")
        self.assertEqual(decision.appended_text("", "Text."), "Text.")


class ForwardingTests(unittest.TestCase):
    def test_the_parser_produces_text_before_its_message_completes(self):
        # The baseline forwarded these deltas to Hermes as they arrived; the client now holds them (see below).
        message = stream_events.Message({MODEL})
        message.feed({"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m1", "model": MODEL}}})
        message.feed({"type": "stream_event", "event": {"type": "content_block_start", "index": 0,
                                                        "content_block": {"type": "text", "text": ""}}})
        deltas = message.feed({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                                                 "delta": {"type": "text_delta", "text": "Hi"}}})
        self.assertEqual(deltas, [{"content": "Hi"}])
        self.assertFalse(message.done)
        self.assertEqual(message.deltas, [{"content": "Hi"}])

    def test_only_results_marked_is_error_exactly_true_count_as_errors_per_id(self):
        message = stream_events.Message({MODEL})
        message.feed({"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m1", "model": MODEL}}})
        marks = [("t1", {"is_error": True}), ("t2", {"is_error": False}), ("t3", {}), ("t4", {"is_error": "true"}),
                 ("t5", {"is_error": 1}), ("t1", {"is_error": False})]
        message.observe_user({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": id_, "content": "synthetic", **mark} for id_, mark in marks]}})
        self.assertEqual(message.answered, ["t1", "t2", "t3", "t4", "t5", "t1"])
        self.assertEqual(message.errored, ["t1"])


class ClientTests(unittest.TestCase):
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

    def request(self, text, **kwargs):
        return self.c.create(model=MODEL, messages=[{"role": "system", "content": "Synthetic system"},
                                                    {"role": "user", "content": text}], **kwargs)

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def decisions(self):
        return [(a["outcome"], a["row"]) for a in self.c.audit if a["stage"] == "second_message"]

    @staticmethod
    def text(chunks):
        return "".join(getattr(c.choices[0].delta, "content", None) or "" for c in chunks)

    def test_text_reaches_hermes_only_after_its_message_is_final(self):
        order, original = [], client.Runtime.read
        def read(runtime, *args, **kwargs):
            obj = original(runtime, *args, **kwargs)
            if isinstance(obj, dict) and obj.get("type") in ("stream_event", "result"):
                order.append(obj.get("event", {}).get("type") or obj["type"])
            return obj
        with patch.object(client.Runtime, "read", read):
            for chunk in self.request("__plain__", stream=True):
                if getattr(chunk.choices[0].delta, "content", None):
                    order.append("chunk")
        self.assertEqual(order[order.index("chunk") - 1], "result")
        self.assertLess(order.index("message_stop"), order.index("chunk"))
        self.assertEqual(order.count("chunk"), 2)  # still the runtime's own deltas, in order

    def test_internal_step_keeps_the_last_message_and_its_calls_park_with_their_identity(self):
        chunks = list(self.request("__internal_step_tool__", tools=[TOOL], stream=True))
        calls = [c.choices[0].delta.tool_calls[0] for c in chunks if getattr(c.choices[0].delta, "tool_calls", None)]
        self.assertEqual([(c.id, c.function.name) for c in calls if getattr(c, "id", None)], [("toolu_real", "read_file")])
        self.assertEqual(json.loads("".join(c.function.arguments for c in calls)), {"path": "/synthetic/real"})
        self.assertEqual(self.text(chunks), "Checking.")  # the first message's text is kept, not dropped
        self.assertEqual(chunks[-1].choices[0].finish_reason, "tool_calls")
        self.assertEqual({c.id for c in chunks}, {"msg_step_1"})
        self.assertEqual(self.decisions(), [(KEEP_LAST, "internal_step")])
        entry = next(a for a in self.c.audit if a["stage"] == "second_message")
        self.assertEqual({k: entry[k] for k in ("answered", "answered_errors", "requested", "dropped_calls", "dropped_text_chars")},
                         {"answered": 1, "answered_errors": 1, "requested": False, "dropped_calls": 1, "dropped_text_chars": 0})
        self.assertEqual(self.c._pending["tool_use_id"], "toolu_real")
        messages = [*self.c._history.messages, {"role": "tool", "tool_call_id": "toolu_real", "content": "OWNER RESULT"}]
        answer = self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        self.assertEqual(answer.choices[0].message.content, "Got OWNER RESULT")
        self.assertEqual(self.audits(), [])

    def test_internal_step_then_a_text_reply(self):
        response = self.request("__internal_step_text__", tools=[TOOL])
        self.assertEqual(response.choices[0].message.content, "Checking.Answer.")
        self.assertEqual(response.choices[0].finish_reason, "stop")
        self.assertIsNone(response.choices[0].message.tool_calls)
        self.assertEqual(self.decisions(), [(KEEP_LAST, "internal_step")])

    def test_replay_keeps_the_first_once(self):
        chunks = list(self.request("__replay__", stream=True))
        self.assertEqual(self.text(chunks), "Same.")
        self.assertEqual(chunks[-1].choices[0].finish_reason, "stop")
        self.assertEqual(self.decisions(), [(KEEP_FIRST, "replay")])
        self.assertEqual(self.c._history.messages[-1], {"role": "assistant", "content": "Same."})

    def test_cut_off_reply_is_appended_with_combined_usage(self):
        for prompt in ("__cut_off__", "__cut_off_repeat__"):
            with self.subTest(prompt):
                self.c.close()
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                response = self.request(prompt)
                self.assertEqual(response.choices[0].message.content, "Part one and two.")
                self.assertEqual(response.choices[0].finish_reason, "stop")
                self.assertEqual(response.usage.completion_tokens, 4)
                self.assertEqual(self.decisions(), [(APPEND, "continuation")])

    def test_fail_rows_raise_with_an_audit_and_forward_nothing(self):
        for prompt, row in (("__dup__", "complete_not_replay"), ("__no_step__", "tool_use_without_internal_step"),
                            ("__replays__", "too_many_messages")):
            with self.subTest(prompt):
                for path in self.audits():
                    path.unlink()
                self.c.close()
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                chunks = []
                with self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
                    for chunk in self.request(prompt, tools=[TOOL], stream=True):
                        chunks.append(chunk)
                self.assertEqual(chunks, [])
                self.assertEqual(self.decisions()[-1], (FAIL, row))
                [path] = self.audits()
                record = json.loads(path.read_text())
                self.assertEqual(record["audit"][-1]["row"], row)
                self.assertTrue(all(m["forwarded_chars"] == 0 for m in record["stream"]["messages"]))

    def test_internal_step_with_a_non_error_runtime_answer_fails_with_an_audit_and_forwards_nothing(self):
        for prompt, errors in (("__internal_step_success__", 0), ("__internal_step_unmarked__", 0),
                               ("__internal_step_mixed__", 1)):
            with self.subTest(prompt):
                for path in self.audits():
                    path.unlink()
                self.c.close()
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                chunks = []
                with self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
                    for chunk in self.request(prompt, tools=[TOOL], stream=True):
                        chunks.append(chunk)
                self.assertEqual(chunks, [])
                self.assertIsNone(self.c._pending)
                self.assertFalse(any(a["stage"] in ("tool_parked", "result_delivered") for a in self.c.audit))
                self.assertEqual(self.decisions(), [(FAIL, "internal_step_non_error_result")])
                entry = next(a for a in self.c.audit if a["stage"] == "second_message")
                self.assertEqual((entry["answered"], entry["answered_errors"], entry["requested"], entry["dropped_calls"]),
                                 (1 + errors, errors, False, 0))
                [path] = self.audits()
                record = json.loads(path.read_text())
                self.assertEqual(record["audit"][-1]["row"], "internal_step_non_error_result")
                self.assertEqual(record["audit"][-1]["answered_errors"], errors)
                self.assertTrue(all(m["forwarded_chars"] == 0 for m in record["stream"]["messages"]))

    def test_a_continuation_carries_its_per_id_error_evidence_into_the_kept_message(self):
        response = self.request("__chained_step_rejected__", tools=[TOOL])
        self.assertEqual(response.choices[0].message.content, "Part more.Answer.")
        self.assertEqual(self.decisions(), [(APPEND, "continuation"), (KEEP_LAST, "internal_step")])
        steps = [a for a in self.c.audit if a["stage"] == "second_message"]
        self.assertEqual([(a["answered"], a["answered_errors"]) for a in steps], [(0, 0), (1, 1)])
        self.c.close()
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)
        chunks = []
        with self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
            for chunk in self.request("__chained_step_success__", tools=[TOOL], stream=True):
                chunks.append(chunk)
        self.assertEqual(chunks, [])
        self.assertEqual(self.decisions(), [(APPEND, "continuation"), (FAIL, "internal_step_non_error_result")])
        [path] = self.audits()
        self.assertEqual(json.loads(path.read_text())["audit"][-1]["row"], "internal_step_non_error_result")


def synthetic_runtime(argv):
    """Inert event producer for second-message shapes; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    tools = [client.PREFIX + "read_file"] if config["mcpServers"] else []
    model = argv[argv.index("--model") + 1]
    bridge = None
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit({"type": "stream_event", "event": {"type": kind, **kwargs}})
    def message(message_id, blocks, stop="end_turn", answered=(), marks=None):
        ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})
        for index, value in enumerate(blocks):
            if value["type"] == "text":
                ev("content_block_start", index=index, content_block={"type": "text", "text": ""})
                for fragment in (value["text"][:2], value["text"][2:]):
                    ev("content_block_delta", index=index, delta={"type": "text_delta", "text": fragment})
            else:
                ev("content_block_start", index=index, content_block={**value, "input": {}})
                ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": json.dumps(value["input"])})
            emit({"type": "assistant", "message": {"id": message_id, "model": model, "content": [value], "usage": {"output_tokens": 1}}})
            ev("content_block_stop", index=index)
        for number, tool_use_id in enumerate(answered):  # the CLI answers a call itself, as in the live audits
            mark = {"is_error": True} if marks is None else marks[number]  # the live audits: always a rejection
            emit({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": "synthetic answer", **mark}]}})
        ev("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2})
        ev("message_stop")
    def result():
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
              "modelUsage": {model: {"canonicalModel": model, "provider": "firstParty"}}})
    def text(value):
        return {"type": "text", "text": value}
    def call(tool_use_id, path):
        return {"type": "tool_use", "id": tool_use_id, "name": client.PREFIX + "read_file", "input": {"path": path}}
    for ordinal, line in enumerate(sys.stdin):
        content = json.loads(line)["message"]["content"]
        prompt = content if isinstance(content, str) else ""
        if ordinal == 0:
            emit({"type": "system", "subtype": "init", "model": model, "tools": tools, "apiKeySource": "none",
                  "claude_code_version": "2.1.283"})
        if prompt == "__plain__":
            message("msg_plain", [text("Fine")])
            result()
        elif prompt == "__internal_step_tool__":
            message("msg_step_1", [text("Checking."), call("toolu_rejected", "/synthetic/rejected")], "tool_use", ["toolu_rejected"])
            message("msg_step_2", [call("toolu_real", "/synthetic/real")], "tool_use")
            cfg = config["mcpServers"]["hermes"]
            bridge = subprocess.Popen([cfg["command"]] + cfg["args"], env=cfg["env"], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, text=True)
            for request in ({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                            {"id": 2, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "/synthetic/real"}}}):
                bridge.stdin.write(json.dumps(request) + "\n")
                bridge.stdin.flush()
                reply = json.loads(bridge.stdout.readline())
            emit({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_real"}]}})
            message("msg_step_3", [text("Got " + reply["result"]["content"][0]["text"])])
            result()
        elif prompt == "__internal_step_text__":
            message("msg_t1", [text("Checking."), call("toolu_rejected", "/synthetic/rejected")], "tool_use", ["toolu_rejected"])
            message("msg_t2", [text("Answer.")])
            result()
        elif prompt in ("__internal_step_success__", "__internal_step_unmarked__", "__internal_step_mixed__"):
            # The runtime answered the call itself but not with a rejection: something may have run.
            answered, marks = {"__internal_step_success__": (["toolu_ran"], [{"is_error": False}]),
                               "__internal_step_unmarked__": (["toolu_ran"], [{}]),
                               "__internal_step_mixed__": (["toolu_ran", "toolu_ran"], [{"is_error": True}, {}])}[prompt]
            message("msg_s1", [text("Checking."), call("toolu_ran", "/synthetic/ran")], "tool_use", answered, marks)
            message("msg_s2", [text("Answer.")])
            result()
        elif prompt in ("__chained_step_rejected__", "__chained_step_success__"):
            # A cut-off message, its continuation with a call the runtime answers itself, then the reply.
            mark = {"is_error": prompt == "__chained_step_rejected__"}
            message("msg_k1", [text("Part")], "max_tokens")
            message("msg_k2", [text(" more."), call("toolu_k", "/synthetic/k")], "tool_use", ["toolu_k"], [mark])
            message("msg_k3", [text("Answer.")])
            result()
        elif prompt == "__replay__":
            message("msg_r1", [text("Same.")])
            message("msg_r2", [text("Same.")])
            result()
        elif prompt == "__replays__":
            for number in range(6):
                message(f"msg_rr{number}", [text("Same.")])
            result()
        elif prompt in ("__cut_off__", "__cut_off_repeat__"):
            message("msg_c1", [text("Part one")], "max_tokens")
            message("msg_c2", [text(" and two." if prompt == "__cut_off__" else "Part one and two.")])
            result()
        elif prompt == "__dup__":
            message("msg_d1", [text("Alpha.")])
            message("msg_d2", [text("Alpha. More.")])
            result()
        elif prompt == "__no_step__":
            message("msg_n1", [call("toolu_n1", "/synthetic/n1")], "tool_use")
            message("msg_n2", [call("toolu_n2", "/synthetic/n2")], "tool_use")
            result()
    if bridge:
        bridge.terminate()
        bridge.wait(timeout=2)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
