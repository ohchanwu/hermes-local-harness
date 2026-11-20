#!/usr/bin/env python3
"""The jev plugin when a Hermes name that Hermes does not document is absent.

Decision record docs/decisions/261120-plugin-behaviour-across-hermes-updates.md,
section 4 change 2, rows J6, J8, J16, J19, J21, J22 and J23. One case per row:
the Hermes name is absent, the feature of the row is off, exactly one Python
``logging`` record at level WARNING is written per process, and the Hermes call
result is unchanged. A second part of each case shows that nothing is written
when the name is present.

Offline: no live /Users/chanbla11mit/.hermes reads, no board, no network and no
model calls. Logs and state go to a temporary directory; the ``hermes`` command
of rows J16 and J19 is a fake program or a replaced ``show_card``.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import shlex
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins"))

SECRET = "JEVSECRET5d2e"  # card text, tool output and payload text; never in a WARNING record
BOARD = "harness"
GLM_WORKER = "harness-worker-glm-1"
CLAUDE_WORKER = "harness-worker"
GLM_REVIEWER = "harness-reviewer-glm"
OPUS_REVIEWER = "harness-reviewer"
TASK = "t_0a1b2c3d"

FAKE_HERMES = """\
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_HERMES_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if "--help" in args:
    reclaim = "[--reclaim] " if os.environ.get("FAKE_HELP_HAS_RECLAIM") else ""
    print("usage: hermes kanban reassign [-h] " + reclaim + "task_id profile")
    sys.exit(0)
if "reassign" in args:
    sys.stderr.write("hermes: error: unrecognized arguments: --reclaim\\n")
    sys.exit(2)
sys.exit(0)
"""


def schema(*names: str) -> dict:
    return {"name": "tool", "parameters": {"type": "object",
                                           "properties": {name: {"type": "string"} for name in names}}}


FULL_SCHEMAS = {
    "kanban_create": schema("title", "body", "assignee", "model", "provider", "board"),
    "kanban_unblock": schema("task_id", "board"),
    "kanban_request_review": schema("task_id", "summary", "reviewer", "board"),
    "kanban_request_changes": schema("task_id", "reason", "board"),
    "kanban_complete": schema("task_id", "summary", "board"),
    "kanban_block": schema("task_id", "reason", "kind", "board"),
}


class FakeRegistry:
    def __init__(self, schemas: dict):
        self.schemas = schemas

    def get_schema(self, name: str):
        return self.schemas.get(name)


def fake_tools_modules(schemas: dict) -> dict:
    """``sys.modules`` entries for a Hermes ``tools.registry`` with these schemas."""
    tools = types.ModuleType("tools")
    registry_module = types.ModuleType("tools.registry")
    registry_module.registry = FakeRegistry(schemas)  # type: ignore[attr-defined]
    tools.registry = registry_module  # type: ignore[attr-defined]
    return {"tools": tools, "tools.registry": registry_module}


def read_records(log_dir: Path, stream: str) -> list:
    path = log_dir / f"{stream}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def routing_config(max_change_requests: int) -> dict:
    return {
        "peak_hold": {"enabled": True},
        "routing": {"enabled": True, "max_glm_change_requests": max_change_requests, "boards": {BOARD: {
            "implementation_workers": [CLAUDE_WORKER], "glm_workers": [GLM_WORKER],
            "glm_reviewers": [GLM_REVIEWER], "opus_reviewer": OPUS_REVIEWER, "routes": [],
        }}},
    }


def card(status: str, assignee: str, events: list, runs=()) -> dict:
    return {"task": {"id": TASK, "status": status, "assignee": assignee, "body": SECRET},
            "events": list(events), "runs": list(runs)}


class HermesNameWarningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log_dir = self.dir / "logs"
        patcher = mock.patch.dict(os.environ, {
            "HERMES_JEV_LOG_DIR": str(self.log_dir), "HERMES_JEV_STATE_DIR": str(self.dir / "state"),
            "HERMES_HOME": str(self.dir / "home"), "HERMES_KANBAN_HOME": str(self.dir / "kanban"),
            "HERMES_PROFILE": "", "HERMES_KANBAN_TASK": "", "HERMES_KANBAN_RUN_ID": "",
            "HERMES_KANBAN_BOARD": "", "HERMES_DELEGATED_CHILD_CONTEXT": "",
            "FAKE_HERMES_CALLS": str(self.dir / "hermes-calls.jsonl"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plugin = importlib.import_module("jev")
        self.peak_hold = self.plugin.peak_hold
        self.routing = self.plugin.routing
        # Each case starts as a new process would.
        self.peak_hold.WARNED_HERMES_NAMES.clear()
        self.plugin._ABSENT_ARGUMENT.clear()

    def one_warning(self, call, *name_parts: str) -> list:
        """Run ``call`` twice; assert exactly one WARNING record that names the
        Hermes name and holds no secret text. Returns both results."""
        with self.assertLogs("jev", level="WARNING") as captured:
            results = [call(), call()]
        self.assertEqual(len(captured.records), 1, [r.getMessage() for r in captured.records])
        record = captured.records[0]
        self.assertEqual(record.levelno, logging.WARNING)
        message = record.getMessage()
        for part in name_parts:
            self.assertIn(part, message)
        self.assertNotIn(SECRET, message)
        return results

    # --- J6: result field of a Hermes tool ----------------------------------

    def test_j6_result_without_the_text_field(self):
        result = json.dumps({"stdout": SECRET * 400, "exit_code": 0})
        ask = mock.Mock(side_effect=AssertionError("Jev must not be asked"))
        config = {"tool_results": {"enabled": True}}
        with mock.patch.object(self.plugin, "load_config", return_value=config), \
                mock.patch.object(self.plugin.jev_client, "ask", ask):
            def call():
                return self.plugin._transform_tool_result(tool_name="terminal", args={"command": "ls"},
                                                          result=result, session_id="s1")
            # None: Hermes keeps the tool result unchanged; Jev is not asked.
            self.assertEqual(self.one_warning(call, "output", "terminal"), [None, None])
            ask.assert_not_called()
            # Present field, an error result and a short search_files result: no record.
            with self.assertNoLogs("jev", level="WARNING"):
                for tool, other in (("execute_code", {"output": "short", "status": "success"}),
                                    ("browser_exec", {"error": "browser not running"}),
                                    ("search_files", {"total_count": 2, "matches": [{"path": "a"}]})):
                    self.assertIsNone(self.plugin._transform_tool_result(
                        tool_name=tool, args={}, result=json.dumps(other), session_id="s1"))

    # --- J8: usage keys of post_auxiliary_call --------------------------------

    def test_j8_usage_without_token_keys(self):
        config = {"auxiliary_log": {"enabled": True}}
        with mock.patch.object(self.plugin, "load_config", return_value=config):
            def call():
                return self.plugin._post_auxiliary_call(aux_task="title_generation", provider="p", model="m",
                                                        usage={"total_tokens": 12}, error_type=None,
                                                        streaming=False)
            self.assertEqual(self.one_warning(call, "prompt_tokens", "post_auxiliary_call"), [None, None])
            records = read_records(self.log_dir, "auxiliary")
            self.assertEqual([(r["input_tokens"], r["output_tokens"], r["status"]) for r in records],
                             [(None, None, "ok")] * 2)
            with self.assertNoLogs("jev", level="WARNING"):
                self.plugin._post_auxiliary_call(aux_task="t", usage={"prompt_tokens": 5, "output_tokens": 2})
                self.plugin._post_auxiliary_call(aux_task="t", usage=None, error_type="TimeoutError")
            self.assertEqual(read_records(self.log_dir, "auxiliary")[2]["input_tokens"], 5)

    # --- J16: event payload fields ---------------------------------------------

    def test_j16_event_payload_fields(self):
        moment = datetime(2026, 11, 16, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))  # Monday, inside the window
        config = routing_config(5)

        # scheduled.reason: the peak-hours hold does not recognise the card;
        # kanban_unblock runs with the result of Hermes.
        held = card("scheduled", GLM_WORKER, [{"kind": "scheduled", "payload": {"text": SECRET}, "run_id": 1}])
        calls = []

        def unblock():
            calls.append(None)
            return self.routing.handle_unblock({"task_id": TASK, "board": BOARD},
                                               lambda payload=None: '{"ok": true, "status": "ready"}',
                                               config=config, now=moment)
        with mock.patch.object(self.peak_hold, "show_card", return_value=held):
            results = self.one_warning(unblock, "reason", "scheduled")
        self.assertEqual(results, ['{"ok": true, "status": "ready"}'] * 2)
        held_with_reason = card("scheduled", GLM_WORKER, [{"kind": "scheduled", "run_id": 1, "payload": {
            "reason": "jev-peak-hold until 2026-11-16T19:00:00+09:00"}}])
        with mock.patch.object(self.peak_hold, "show_card", return_value=held_with_reason), \
                self.assertNoLogs("jev", level="WARNING"):
            kept = json.loads(self.routing.handle_unblock({"task_id": TASK, "board": BOARD},
                                                          lambda payload=None: "unused", config=config, now=moment))
        self.assertEqual(kept["status"], "scheduled")

        # blocked.source_status: the GLM review pass and the release of a held
        # review run do not select the card; one record for both functions.
        passed = card("blocked", GLM_REVIEWER, [{"kind": "blocked", "run_id": 7, "payload": {
            "reason": "jev-glm-review-pass " + SECRET, "kind": "needs_input"}}], [{"id": 7, "profile": GLM_REVIEWER}])
        in_review = card("blocked", GLM_REVIEWER, [{"kind": "blocked", "run_id": 7, "payload": {
            "reason": "jev-peak-hold until 2026-11-16T19:00:00+09:00", "kind": "needs_input"}}])
        with self.assertLogs("jev", level="WARNING") as captured:
            self.assertFalse(self.peak_hold._card_matches_pass(passed, GLM_REVIEWER, OPUS_REVIEWER))
            self.assertIsNone(self.peak_hold._review_hold_reason(in_review, GLM_REVIEWER, "jev-peak-hold"))
        self.assertEqual(len(captured.records), 1)
        self.assertIn("source_status", captured.records[0].getMessage())
        self.assertNotIn(SECRET, captured.records[0].getMessage())
        passed["events"][0]["payload"]["source_status"] = "review"
        with self.assertNoLogs("jev", level="WARNING"):
            self.assertTrue(self.peak_hold._card_matches_pass(passed, GLM_REVIEWER, OPUS_REVIEWER))

        # changes_requested.reviewer: the events are not counted by reviewer;
        # kanban_request_changes returns the result of Hermes.
        returned = card("ready", GLM_WORKER, [{"kind": "changes_requested", "run_id": 2,
                                               "payload": {"reason": SECRET, "implementer": GLM_WORKER}}])
        with mock.patch.object(self.peak_hold, "show_card", return_value=returned):
            def request_changes():
                return self.routing.handle_request_changes({"task_id": TASK, "board": BOARD, "reason": SECRET},
                                                           lambda payload=None: '{"ok": true}', config=config,
                                                           state_dir=self.dir / "state")
            self.assertEqual(self.one_warning(request_changes, "reviewer", "changes_requested"),
                             ['{"ok": true}'] * 2)
        self.assertEqual(self.routing._card_change_request_reviewers(returned, OPUS_REVIEWER, [GLM_REVIEWER]),
                         (0, 0, None))

    # --- J19: option --reclaim of hermes kanban reassign --------------------------

    def test_j19_reassign_without_reclaim(self):
        script = self.dir / "fake_hermes.py"
        script.write_text(FAKE_HERMES, encoding="utf-8")
        command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
        config = routing_config(1)
        reviewed = card("ready", GLM_WORKER, [{"kind": "changes_requested", "run_id": 2, "payload": {
            "reason": SECRET, "implementer": GLM_WORKER, "reviewer": OPUS_REVIEWER}}])

        def request_changes():
            return self.routing.handle_request_changes({"task_id": TASK, "board": BOARD}, lambda payload=None: "R",
                                                       config=config, command=command, state_dir=self.dir / "state")
        with mock.patch.object(self.peak_hold, "show_card", return_value=reviewed):
            # The help text lists --reclaim: the failure has another cause, no record.
            with mock.patch.dict(os.environ, {"FAKE_HELP_HAS_RECLAIM": "1"}), \
                    self.assertNoLogs("jev", level="WARNING"):
                self.assertEqual(request_changes(), "R")
            self.assertEqual(self.one_warning(request_changes, "--reclaim", "reassign"), ["R", "R"])
        escalations = [r for r in read_records(self.log_dir, "decisions") if r["event"] == "escalate"]
        self.assertEqual([(r["applied"], r["new_assignee"]) for r in escalations], [(False, GLM_WORKER)] * 3)
        calls = [json.loads(line) for line in Path(os.environ["FAKE_HERMES_CALLS"]).read_text().splitlines()]
        # One help read per call until the record is written, none after it.
        self.assertEqual(sum("--help" in c for c in calls), 2)

    # --- J21: Kanban tool argument names ------------------------------------------

    def test_j21_tool_schema_without_an_argument(self):
        schemas = dict(FULL_SCHEMAS, kanban_request_review=schema("task_id", "summary", "board"))
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return "tool result"
        review = mock.Mock(side_effect=AssertionError("jev handling must be off"))
        with mock.patch.dict(sys.modules, fake_tools_modules(schemas)), \
                mock.patch.dict(os.environ, {"HERMES_PROFILE": GLM_REVIEWER}), \
                mock.patch.object(self.routing, "handle_request_review", review):
            def call():
                return self.plugin._tool_execution(tool_name="kanban_request_review", next_call=next_call,
                                                   args={"task_id": TASK, "summary": SECRET})
            # The GLM reviewer refusal and the reviewer choice are off for this tool only.
            self.assertEqual(self.one_warning(call, "reviewer", "kanban_request_review"),
                             ["tool result", "tool result"])
            self.assertEqual(calls, [None, None])
            review.assert_not_called()
            with self.assertNoLogs("jev", level="WARNING"):
                refused = self.plugin._tool_execution(tool_name="kanban_complete", next_call=next_call,
                                                      args={"task_id": TASK})
            self.assertIn("error", json.loads(refused))
            self.assertEqual(calls, [None, None])
        # Every name present: the refusal of the baseline.
        self.plugin._ABSENT_ARGUMENT.clear()
        with mock.patch.dict(sys.modules, fake_tools_modules(FULL_SCHEMAS)), \
                mock.patch.dict(os.environ, {"HERMES_PROFILE": GLM_REVIEWER}), \
                self.assertNoLogs("jev", level="WARNING"):
            refused = self.plugin._tool_execution(tool_name="kanban_request_review", next_call=next_call,
                                                  args={"task_id": TASK})
        self.assertIn("error", json.loads(refused))

    # --- J22: kanban_create result fields --------------------------------------------

    def test_j22_create_result_without_task_id(self):
        args = {"title": SECRET, "body": SECRET, "assignee": CLAUDE_WORKER, "board": BOARD}
        result = '{"ok": true, "id": "t_0a1b2c3d", "status": "ready"}'

        def call():
            return self.routing.handle_create(args, lambda payload=None: result, config={}, ask=mock.Mock())
        self.assertEqual(self.one_warning(call, "task_id", "kanban_create"), [result, result])
        self.assertEqual([r["task_id"] for r in read_records(self.log_dir, "decisions")], [None, None])
        with self.assertNoLogs("jev", level="WARNING"):
            for other in ('{"ok": true, "task_id": "t_0a1b2c3d", "status": "ready"}', '{"error": "no board"}'):
                self.assertEqual(self.routing.handle_create(args, lambda payload=None: other, config={},
                                                            ask=mock.Mock()), other)
        self.assertEqual(read_records(self.log_dir, "decisions")[2]["task_id"], TASK)

    # --- J23: task ID pattern -----------------------------------------------------------

    def test_j23_task_id_pattern(self):
        for value in (TASK, "hm_42", "A-1", "7", "a" * 64):
            self.assertEqual(self.routing._arg_task_id(value), value)
        for value in ("-t_0a1b2c3d", "_t", "a" * 65, "t 1", "", "t_0a1b\n", None, 12):
            self.assertIsNone(self.routing._arg_task_id(value))
        self.assertIs(self.plugin.glm_review._HERMES_TASK_ID, self.routing._HERMES_TASK_ID)


if __name__ == "__main__":
    unittest.main()
