#!/usr/bin/env python3
"""The peak-hours hold of a GLM review run and its release by the hold script.

Decision document ``docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md``,
section 5, way 2, and item 6 of "What the plugin cards must implement":

- Part A (the plugin, ``jev._tool_execution``): a GLM review run that the
  dispatcher started inside the active hold window is refused every tool other
  than ``kanban_block``, ``kanban_complete`` and ``kanban_request_review``, and
  its ``kanban_block`` blocks the card with the hold reason and a kind that
  keeps the card out of ``triage``.
- Part B (``scripts/jev-peak-hold``): a ``blocked`` card of the board's first
  GLM reviewer whose newest ``blocked`` event carries the marker and records
  ``source_status: review`` is released with ``hermes kanban unblock`` when the
  hold is not active or the time in its reason has passed.

Offline: a temporary Kanban database, a temporary switch file and log
directory, a fixed time, and a stand-in ``hermes`` command
(``kanban.hermes_command``) that answers ``show --json`` and ``list --json``
from the database and, for part B, records and applies the changes. Every
test sets ``HERMES_PROFILE``, ``HERMES_KANBAN_TASK`` and
``HERMES_KANBAN_RUN_ID`` itself with ``mock.patch.dict(os.environ, ...)``.
Nothing touches a live board, the live switch file or the live logs.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "jev"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(ROOT / "plugins"))
sys.path.insert(0, str(ROOT / "tests"))

import jev_log  # noqa: E402
import peak_hold  # noqa: E402
from test_jev_client import write_fake_hermes  # noqa: E402
from test_jev_glm_review_pass import STAND_IN_HERMES, build_pass_db  # noqa: E402

SCRIPT = ROOT / "scripts" / "jev-peak-hold"
CONFIG = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
KST = ZoneInfo("Asia/Seoul")
BOARD = "harness"
CARD = "t_0a1b2c3d"
RUN_ID = "71"
GLM_REVIEWER = "harness-reviewer-glm"
OPUS_REVIEWER = "harness-reviewer"
GLM_WORKER = "harness-worker-glm-easy-1"
UNTIL = "2026-11-11T19:00:00+09:00"
HOLD_REASON = "jev-peak-hold until " + UNTIL
# Wednesday 2026-11-11; the window is 15:00 to 19:00 Asia/Seoul.
NOW_INSIDE = datetime(2026, 11, 11, 16, 30, tzinfo=KST)
STARTED_INSIDE = int(datetime(2026, 11, 11, 16, 0, tzinfo=KST).timestamp())
STARTED_BEFORE = int(datetime(2026, 11, 11, 14, 50, tzinfo=KST).timestamp())
STARTED_DAY_BEFORE = int(datetime(2026, 11, 10, 16, 0, tzinfo=KST).timestamp())
WEDNESDAY_16 = "2026-11-11T16:00:00+09:00"
WEDNESDAY_19 = "2026-11-11T19:00:00+09:00"
OK_RESULT = json.dumps({"ok": True, "task_id": CARD, "status": "blocked"})
ERROR_RESULT = json.dumps({"error": "could not block " + CARD})
TOOL_RESULT = json.dumps({"output": "tool output"})
# The fields of item A.6 of the card.
REFUSED_FIELDS = {"event", "board", "task_id", "profile", "tool", "action", "held_until", "error_class"}
BLOCKED_FIELDS = REFUSED_FIELDS | {"kind"}
# The fixed fields of every decisions record (jev_log.build_record).
STREAM_FIELDS = set(jev_log.STREAM_FIELDS["decisions"]) | {"ts", "profile"}


def read_records(log_dir: Path, event=None) -> list:
    path = log_dir / "decisions.jsonl"
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in records if event is None or r.get("event") == event]


def build_run_db(path: Path, *, block_kind=None, started_at=STARTED_INSIDE, run_task=CARD) -> None:
    """A board database with the card, ``task_runs`` (``started_at``) and, when
    ``block_kind`` is set, an earlier ``blocked`` event whose payload ``kind`` is
    ``block_kind`` (the plugin reads the block kind from the newest such event)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT, assignee TEXT)")
    conn.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER,"
                 " kind TEXT, payload TEXT, created_at INTEGER)")
    conn.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT,"
                 " status TEXT, started_at INTEGER NOT NULL, ended_at INTEGER, outcome TEXT)")
    conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, ?, ?, ?)",
                 (CARD, "synthetic card", "running", GLM_REVIEWER))
    if block_kind is not None:
        conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, 'blocked', ?, 0)",
                     (CARD, json.dumps({"reason": "earlier block", "kind": block_kind, "source_status": "review"})))
    conn.execute("INSERT INTO task_runs (id, task_id, profile, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                 (int(RUN_ID), run_task, GLM_REVIEWER, started_at))
    conn.commit()
    conn.close()


# --- part A: the plugin ------------------------------------------------------------

class PluginHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log_dir = self.dir / "logs"
        env = {"HERMES_JEV_LOG_DIR": str(self.log_dir), "HERMES_JEV_STATE_DIR": str(self.dir / "state"),
               "HERMES_KANBAN_HOME": str(self.dir / "kanban-home"), "HERMES_KANBAN_BOARD": BOARD,
               "HERMES_PROFILE": GLM_REVIEWER, "HERMES_KANBAN_TASK": CARD, "HERMES_KANBAN_RUN_ID": RUN_ID,
               "HERMES_DELEGATED_CHILD_CONTEXT": ""}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plugin = importlib.import_module("jev")
        self.glm_review = self.plugin.glm_review
        self.glm_review._RUN_STARTED_AT.clear()
        self.addCleanup(self.glm_review._RUN_STARTED_AT.clear)
        self.now = NOW_INSIDE
        now_patcher = mock.patch.object(self.glm_review, "_now", side_effect=lambda: self.now)
        now_patcher.start()
        self.addCleanup(now_patcher.stop)
        self.db = self.dir / "kanban-home" / "kanban" / "boards" / BOARD / "kanban.db"
        build_run_db(self.db)
        self.hermes = write_fake_hermes(self.dir)
        self.config = self.with_fake_hermes(CONFIG)
        config_patcher = mock.patch.object(self.plugin, "load_config", side_effect=lambda: self.config)
        config_patcher.start()
        self.addCleanup(config_patcher.stop)

    def with_fake_hermes(self, config):
        """A copy of ``config`` that reads the board through the stand-in ``hermes``."""
        config = json.loads(json.dumps(config))
        config["kanban"]["hermes_command"] = self.hermes
        return config

    def call(self, tool, args=None, result=None, profile=None, config=None):
        """One call through ``jev._tool_execution``; returns (next_call arguments, result)."""
        calls = []

        def next_call(*payload):
            calls.append(payload)
            if result is not None:
                return result
            return OK_RESULT if tool == "kanban_block" else TOOL_RESULT

        env = {"HERMES_PROFILE": profile} if profile else {}
        with mock.patch.dict(os.environ, env):
            if config is not None:
                with mock.patch.object(self.plugin, "load_config", return_value=self.with_fake_hermes(config)):
                    out = self.plugin._tool_execution(tool_name=tool, args=args, next_call=next_call)
            else:
                out = self.plugin._tool_execution(tool_name=tool, args=args, next_call=next_call)
        return calls, out

    def assert_baseline_tool(self, calls, out):
        self.assertEqual(calls, [()])
        self.assertEqual(out, TOOL_RESULT)

    # --- a run that started inside the window ------------------------------------------

    def test_another_tool_is_refused_with_the_hold_reason(self):
        for tool in ("terminal", "read_file", "kanban_show", "kanban_heartbeat", "kanban_comment",
                     "kanban_create", "kanban_unblock", "kanban_request_changes"):
            with self.subTest(tool=tool):
                calls, out = self.call(tool, {"task_id": CARD})
                self.assertEqual(calls, [])
                error = json.loads(out)["error"]
                self.assertIn(f"Peak hours are in effect until {UNTIL}.", error)
                self.assertIn(f"Call kanban_block once now with the reason \"{HOLD_REASON}\".", error)
                self.assertIn("end the run and call no other tool", error)

    def test_kanban_block_gets_the_hold_reason_and_kind_needs_input(self):
        args = {"task_id": CARD, "reason": "review finished", "kind": "transient"}
        frozen = dict(args)
        calls, out = self.call("kanban_block", args)
        self.assertEqual(calls, [({"task_id": CARD, "reason": HOLD_REASON, "kind": "needs_input"},)])
        self.assertEqual(args, frozen)
        parsed = json.loads(out)
        self.assertEqual({k: v for k, v in parsed.items() if k != "jev_note"}, json.loads(OK_RESULT))
        self.assertIn(f"returns this card to review at {UNTIL}", parsed["jev_note"])
        self.assertIn("ends its run now", parsed["jev_note"])

    def test_kanban_block_kind_capability_when_block_kind_is_needs_input(self):
        build_run_db(self.db, block_kind="needs_input")
        calls, _out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
        self.assertEqual(calls[0][0]["kind"], "capability")
        [record] = read_records(self.log_dir, "glm_review_hold")
        self.assertEqual((record["action"], record["kind"], record["error_class"]),
                         ("blocked", "capability", None))

    def test_kanban_block_with_the_pass_reason_also_gets_the_hold_reason(self):
        calls, _out = self.call("kanban_block", {"task_id": CARD, "reason": "jev-glm-review-pass no findings"})
        self.assertEqual(calls[0][0]["reason"], HOLD_REASON)
        self.assertEqual(read_records(self.log_dir, "glm_review_pass_block"), [])

    def test_kanban_block_error_result_is_returned_unchanged(self):
        calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"}, result=ERROR_RESULT)
        self.assertEqual(len(calls), 1)
        self.assertEqual(out, ERROR_RESULT)
        self.assertEqual(len(read_records(self.log_dir, "glm_review_hold")), 1)

    def test_block_kind_read_error_gives_needs_input(self):
        build_run_db(self.db, block_kind="needs_input")
        self.call("terminal", {})  # the run start is read and kept for this run
        with mock.patch.dict(os.environ, {"FAKE_HERMES_READ_EXIT": "1"}):
            calls, _out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
        self.assertEqual(calls[0][0]["kind"], "needs_input")
        record = read_records(self.log_dir, "glm_review_hold")[-1]
        self.assertEqual(record["error_class"], "CommandFailed")

    def test_the_newest_blocked_event_gives_the_block_kind(self):
        build_run_db(self.db, block_kind="capability")
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, 'blocked', ?, 1)",
                     (CARD, json.dumps({"reason": "later block", "kind": "needs_input"})))
        conn.commit()
        conn.close()
        calls, _out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
        self.assertEqual(calls[0][0]["kind"], "capability")

    def test_kanban_complete_and_request_review_stay_refused_as_at_the_baseline(self):
        for tool in ("kanban_complete", "kanban_request_review"):
            with self.subTest(tool=tool):
                calls, out = self.call(tool, {"task_id": CARD})
                self.assertEqual(calls, [])
                self.assertEqual(out, self.glm_review.refusal(tool))
        self.assertEqual(len(read_records(self.log_dir, "glm_reviewer_refusal")), 2)
        self.assertEqual(read_records(self.log_dir, "glm_review_hold"), [])

    def test_the_records_have_exactly_the_fields_of_item_a6(self):
        self.call("terminal", {"command": "secret argument value"})
        self.call("kanban_block", {"task_id": CARD, "reason": "reason text of the model"})
        refused, blocked = read_records(self.log_dir, "glm_review_hold")
        self.assertEqual(set(refused) - STREAM_FIELDS, REFUSED_FIELDS - STREAM_FIELDS)
        self.assertTrue(REFUSED_FIELDS <= set(refused))
        self.assertNotIn("kind", refused)
        self.assertEqual(set(blocked) - STREAM_FIELDS, BLOCKED_FIELDS - STREAM_FIELDS)
        self.assertTrue(BLOCKED_FIELDS <= set(blocked))
        self.assertEqual({k: refused[k] for k in REFUSED_FIELDS},
                         {"event": "glm_review_hold", "board": BOARD, "task_id": CARD, "profile": GLM_REVIEWER,
                          "tool": "terminal", "action": "refused", "held_until": UNTIL, "error_class": None})
        self.assertEqual({k: blocked[k] for k in BLOCKED_FIELDS},
                         {"event": "glm_review_hold", "board": BOARD, "task_id": CARD, "profile": GLM_REVIEWER,
                          "tool": "kanban_block", "action": "blocked", "held_until": UNTIL,
                          "kind": "needs_input", "error_class": None})
        text = json.dumps([refused, blocked])
        for value in ("secret argument value", "reason text of the model", "synthetic card", HOLD_REASON):
            self.assertNotIn(value, text)

    def test_a_failure_to_write_the_record_is_ignored(self):
        with mock.patch.object(self.plugin.glm_review.jev_log, "write", side_effect=OSError("disk full")):
            calls, out = self.call("terminal", {})
            self.assertEqual(calls, [])
            self.assertIn("error", json.loads(out))
            calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
            self.assertEqual(len(calls), 1)
            self.assertIn("jev_note", json.loads(out))

    def test_the_run_start_is_read_once_and_the_switch_on_every_call(self):
        hold_module = self.glm_review.peak_hold
        with mock.patch.object(hold_module, "show_card", wraps=hold_module.show_card) as read:
            self.call("terminal", {})
            self.call("read_file", {})
            self.assertEqual(read.call_count, 1)
            hold_module.write_switch(False, "owner")
            calls, out = self.call("terminal", {})
            self.assert_baseline_tool(calls, out)
            self.assertEqual(read.call_count, 1)

    # --- runs and sessions that are not held -----------------------------------------------

    def test_a_run_that_started_before_the_window_is_not_held(self):
        for started in (STARTED_BEFORE, STARTED_DAY_BEFORE):
            with self.subTest(started=started):
                self.glm_review._RUN_STARTED_AT.clear()
                build_run_db(self.db, started_at=started)
                self.assert_baseline_tool(*self.call("terminal", {}))
                calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
                self.assertEqual((calls, out), ([()], OK_RESULT))
        self.assertEqual(read_records(self.log_dir, "glm_review_hold"), [])

    def test_the_pass_block_of_a_run_that_is_not_held_is_unchanged(self):
        build_run_db(self.db, started_at=STARTED_BEFORE)
        args = {"task_id": CARD, "reason": "jev-glm-review-pass no findings"}
        calls, out = self.call("kanban_block", args)
        self.assertEqual(calls, [({**args, "kind": "needs_input"},)])
        self.assertIn("Opus reviewer", json.loads(out)["jev_note"])
        self.assertEqual(len(read_records(self.log_dir, "glm_review_pass_block")), 1)

    def test_outside_the_window_is_not_held(self):
        for now in (datetime(2026, 11, 11, 19, 0, tzinfo=KST), datetime(2026, 11, 11, 14, 59, tzinfo=KST),
                    datetime(2026, 11, 14, 16, 30, tzinfo=KST)):
            with self.subTest(now=now.isoformat()):
                self.now = now
                self.assert_baseline_tool(*self.call("terminal", {}))

    def test_switch_off_is_not_held(self):
        self.glm_review.peak_hold.write_switch(False, "owner")
        self.assert_baseline_tool(*self.call("terminal", {}))
        calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
        self.assertEqual((calls, out), ([()], OK_RESULT))

    def test_peak_hold_enabled_false_is_not_held(self):
        config = json.loads(json.dumps(CONFIG))
        config["peak_hold"]["enabled"] = False
        self.assert_baseline_tool(*self.call("terminal", {}, config=config))

    def test_other_sessions_are_never_held(self):
        for profile in (GLM_WORKER, "harness-worker", OPUS_REVIEWER, "harness-orchestrator"):
            with self.subTest(profile=profile):
                self.assert_baseline_tool(*self.call("terminal", {}, profile=profile))
                calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"}, profile=profile)
                self.assertEqual((calls, out), ([()], OK_RESULT))
        self.assertEqual(read_records(self.log_dir, "glm_review_hold"), [])

    def test_board_read_error_is_not_held(self):
        # The stand-in `hermes kanban show --json` exits 1 on a damaged database.
        self.db.unlink()
        self.db.write_bytes(b"this file is not a SQLite database" * 200)
        self.assert_baseline_tool(*self.call("terminal", {}))

    def test_missing_or_other_values_are_not_held(self):
        cases = [("no run id", {"HERMES_KANBAN_RUN_ID": ""}),
                 ("no task id", {"HERMES_KANBAN_TASK": ""}),
                 ("run of another task", {"HERMES_KANBAN_TASK": "t_feedc0de"}),
                 ("board not configured", {"HERMES_KANBAN_BOARD": "another-board"}),
                 ("another board of the configuration", {"HERMES_KANBAN_BOARD": "anki"})]
        for name, env in cases:
            with self.subTest(name=name), mock.patch.dict(os.environ, env):
                self.glm_review._RUN_STARTED_AT.clear()
                self.assert_baseline_tool(*self.call("terminal", {}))

    def test_an_exception_in_the_new_code_gives_the_baseline_behaviour(self):
        with mock.patch.object(self.glm_review, "hold_action", side_effect=RuntimeError("boom")):
            self.assert_baseline_tool(*self.call("terminal", {}))
            calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
            self.assertEqual((calls, out), ([()], OK_RESULT))
        with mock.patch.object(self.glm_review, "_hold_kind", side_effect=RuntimeError("boom")):
            calls, out = self.call("kanban_block", {"task_id": CARD, "reason": "x"})
            self.assertEqual((calls, out), ([()], OK_RESULT))


# --- part B: the release by the hold script ------------------------------------------------

def blocked_event(reason=HOLD_REASON, source_status="review"):
    return {"reason": reason, "kind": "needs_input", "source_status": source_status}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log_dir = self.dir / "logs"
        self.db = self.dir / "kanban.db"
        self.calls_log = self.dir / "hermes-calls.jsonl"
        stand_in = self.dir / "stand_in_hermes.py"
        stand_in.write_text(STAND_IN_HERMES, encoding="utf-8")
        self.hermes = f"{sys.executable} {stand_in}"
        self.config_path = self.dir / "config.json"
        self.config = json.loads(json.dumps(CONFIG))
        self.save_config()
        env = {"HERMES_JEV_LOG_DIR": str(self.log_dir), "HERMES_JEV_STATE_DIR": str(self.dir / "state"),
               "HERMES_KANBAN_HOME": str(self.dir / "kanban-home"), "HERMES_PROFILE": "harness-orchestrator",
               "FAKE_HERMES_LOG": str(self.calls_log), "FAKE_KANBAN_DB": str(self.db)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in peak_hold.WORKER_SESSION_ENV_NAMES:
            os.environ.pop(name, None)

    def save_config(self):
        # The script reads the board with kanban.hermes_command; --hermes is
        # used for the change commands.
        self.config["kanban"]["hermes_command"] = self.hermes
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def rebuild_held(self, task_id="t_4e1d0001", status="blocked", assignee=GLM_REVIEWER, event=None):
        build_pass_db(self.db, tasks=[(task_id, status, assignee)],
                      events=[(task_id, 11, "blocked", event or blocked_event())],
                      runs=[(11, GLM_REVIEWER)])

    def script(self, *args, now=WEDNESDAY_19, extra_env=None, returncode=0):
        env = dict(os.environ)
        env.update(extra_env or {})
        argv = [sys.executable, str(SCRIPT), *args, "--board", BOARD, "--kanban-db", str(self.db),
                "--config", str(self.config_path), "--hermes", self.hermes, "--now", now]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, returncode, proc.stdout + proc.stderr)
        return proc.stdout

    def calls(self):
        if not self.calls_log.exists():
            return []
        return [json.loads(line) for line in self.calls_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def card_row(self, task_id="t_4e1d0001"):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT status, assignee FROM tasks WHERE id=?", (task_id,)).fetchone()
        finally:
            conn.close()

    def plan(self, now=WEDNESDAY_19):
        return peak_hold.plan_review_release(self.config, datetime.fromisoformat(now), {BOARD: self.db})

    def test_release_outside_the_window(self):
        for now in (WEDNESDAY_19, "2026-11-11T14:59:00+09:00", "2026-11-14T16:00:00+09:00"):
            with self.subTest(now=now):
                self.rebuild_held()
                self.calls_log.unlink(missing_ok=True)
                out = self.script("--apply", now=now)
                self.assertIn("released harness t_4e1d0001 released_to=review", out)
                self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "unblock", "t_4e1d0001"]])
                self.assertEqual(self.card_row(), ("review", GLM_REVIEWER))
        record = read_records(self.log_dir, "release")[-1]
        self.assertEqual((record["task_id"], record["applied"], record["released_to"], record["held_until"],
                          record["original_assignee"], record["error_class"]),
                         ("t_4e1d0001", True, "review", UNTIL, GLM_REVIEWER, None))

    def test_release_with_the_switch_off_and_with_peak_hold_disabled(self):
        peak_hold.write_switch(False, "owner")
        self.rebuild_held()
        self.script("--apply", now=WEDNESDAY_16)
        self.assertEqual(self.card_row(), ("review", GLM_REVIEWER))
        peak_hold.write_switch(True, "owner")
        self.config["peak_hold"]["enabled"] = False
        self.save_config()
        self.rebuild_held()
        self.script("--apply", now=WEDNESDAY_16)
        self.assertEqual(self.card_row(), ("review", GLM_REVIEWER))

    def test_release_after_the_time_in_the_reason(self):
        self.rebuild_held(event=blocked_event(reason="jev-peak-hold until 2026-11-11T16:30:00+09:00"))
        self.assertEqual(self.plan(now="2026-11-11T16:29:00+09:00")[0], [])
        self.script("--apply", now="2026-11-11T16:45:00+09:00")
        self.assertEqual(self.card_row(), ("review", GLM_REVIEWER))

    def test_no_release_inside_the_window(self):
        self.rebuild_held()
        out = self.script("--apply", now=WEDNESDAY_16)
        self.assertIn("nothing to hold or release", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.card_row(), ("blocked", GLM_REVIEWER))

    def test_cards_that_are_not_selected(self):
        cases = [("another reason", "blocked", GLM_REVIEWER, blocked_event(reason="waiting for the owner")),
                 ("the pass reason", "blocked", GLM_REVIEWER, blocked_event(reason="jev-glm-review-pass")),
                 ("source_status ready", "blocked", GLM_REVIEWER, blocked_event(source_status="ready")),
                 ("the Opus reviewer", "blocked", OPUS_REVIEWER, None),
                 ("a GLM worker", "blocked", GLM_WORKER, None)]
        for status in ("review", "ready", "running", "scheduled", "todo", "triage", "done"):
            cases.append((f"status {status}", status, GLM_REVIEWER, None))
        for name, status, assignee, event in cases:
            with self.subTest(name=name):
                self.rebuild_held(status=status, assignee=assignee, event=event)
                self.assertEqual(self.plan(), ([], []))

    def test_only_the_first_glm_reviewer_of_the_board_is_selected(self):
        self.config["routing"]["boards"][BOARD]["glm_reviewers"] = ["harness-reviewer-glm-0", GLM_REVIEWER]
        self.rebuild_held()
        self.assertEqual(self.plan(), ([], []))

    def test_the_newest_blocked_event_decides(self):
        build_pass_db(self.db, tasks=[("t_4e1d0001", "blocked", GLM_REVIEWER)],
                      events=[("t_4e1d0001", 11, "blocked", blocked_event()),
                              ("t_4e1d0001", 12, "blocked", blocked_event(reason="waiting for the owner"))],
                      runs=[(11, GLM_REVIEWER), (12, GLM_REVIEWER)])
        self.assertEqual(self.plan(), ([], []))

    def test_card_changed_between_selection_and_command_is_skipped(self):
        self.rebuild_held()
        releases, _errors = self.plan()
        self.assertEqual(len(releases), 1)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE tasks SET status='review' WHERE id='t_4e1d0001'")
        conn.commit()
        conn.close()
        results = peak_hold.apply_review_release(self.config, releases, self.hermes, {BOARD: self.db})
        self.assertEqual(self.calls(), [])
        self.assertEqual([(r["skipped"], r["applied"], r["error_class"]) for r in results], [(True, False, None)])
        self.assertEqual(read_records(self.log_dir, "release"), [])
        with mock.patch.dict(os.environ, {"FAKE_HERMES_READ_EXIT": "1"}):
            results = peak_hold.apply_review_release(self.config, releases, self.hermes, {BOARD: self.db})
        self.assertEqual([(r["skipped"], r["error_class"]) for r in results], [(True, "CommandFailed")])
        self.assertEqual(self.calls(), [])

    def test_dry_run_prints_the_release_and_runs_no_command(self):
        self.rebuild_held()
        out = self.script()
        self.assertIn("planned release harness t_4e1d0001 assignee=harness-reviewer-glm released_to=review", out)
        self.assertNotIn("nothing to hold or release", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(read_records(self.log_dir), [])
        self.assertEqual(self.card_row(), ("blocked", GLM_REVIEWER))

    def test_worker_session_runs_no_command(self):
        values = {"HERMES_KANBAN_TASK": "t_feedc0de", "HERMES_KANBAN_RUN_ID": "497",
                  "HERMES_DELEGATED_CHILD_CONTEXT": "/Users/chanbla11mit/.hermes"}
        for name, value in values.items():
            with self.subTest(name=name):
                self.rebuild_held()
                out = self.script("--apply", extra_env={name: value})
                self.assertIn("release to review refused: this process was started by a worker", out)
                self.assertEqual(self.calls(), [])
                self.assertEqual(self.card_row(), ("blocked", GLM_REVIEWER))

    def test_failed_unblock_is_tried_again_on_the_next_run(self):
        self.rebuild_held()
        out = self.script("--apply", extra_env={"FAKE_HERMES_FAIL_VERBS": "unblock"}, returncode=1)
        self.assertIn("failed release harness t_4e1d0001 error_class=CommandFailed", out)
        self.assertEqual(self.card_row(), ("blocked", GLM_REVIEWER))
        self.assertEqual([(r["applied"], r["error_class"]) for r in read_records(self.log_dir, "release")],
                         [(False, "CommandFailed")])
        out = self.script("--apply")
        self.assertIn("released harness t_4e1d0001 released_to=review", out)
        self.assertEqual(self.card_row(), ("review", GLM_REVIEWER))
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "unblock", "t_4e1d0001"]] * 2)

    def test_read_error_goes_through_the_read_error_handling(self):
        # The stand-in `hermes kanban list --json` exits 1 on a damaged database.
        self.db.write_bytes(b"this file is not a SQLite database" * 200)
        self.assertEqual(self.plan(), ([], [{"board": BOARD, "error_class": "CommandFailed"}]))
        out = self.script("--apply", returncode=1)
        self.assertIn("failed read harness error_class=CommandFailed", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual([r["board"] for r in read_records(self.log_dir, "read_error")], [BOARD])

    def test_hold_release_and_pass_outputs_of_a_mixed_run_are_unchanged(self):
        build_pass_db(self.db,
                      tasks=[("t_h01d0001", "ready", GLM_WORKER), ("t_9a55e551", "blocked", GLM_REVIEWER),
                             ("t_4e1d0001", "blocked", GLM_REVIEWER)],
                      events=[("t_9a55e551", 11, "blocked", {"reason": "jev-glm-review-pass no findings",
                                                             "kind": "needs_input", "source_status": "review"}),
                              ("t_4e1d0001", 12, "blocked", blocked_event())],
                      runs=[(11, GLM_REVIEWER), (12, GLM_REVIEWER)])
        out = self.script("--apply", now=WEDNESDAY_16)
        self.assertIn("held harness t_h01d0001", out)
        self.assertIn("passed harness t_9a55e551 to harness-reviewer", out)
        self.assertNotIn("t_4e1d0001", out)
        self.assertEqual(self.calls(), [
            ["kanban", "--board", BOARD, "schedule", "t_h01d0001", HOLD_REASON],
            ["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER],
            ["kanban", "--board", BOARD, "unblock", "t_9a55e551"],
        ])
        out = self.script("--apply", now=WEDNESDAY_19)
        self.assertIn("released harness t_h01d0001\n", out)
        self.assertIn("released harness t_4e1d0001 released_to=review", out)
        self.assertEqual(self.calls()[3:], [["kanban", "--board", BOARD, "unblock", "t_h01d0001"],
                                            ["kanban", "--board", BOARD, "unblock", "t_4e1d0001"]])
        releases = read_records(self.log_dir, "release")
        self.assertEqual([(r["task_id"], r["applied"], r.get("released_to")) for r in releases],
                         [("t_h01d0001", True, None), ("t_4e1d0001", True, "review")])
        self.assertNotIn("released_to", releases[0])
        self.assertEqual(len(read_records(self.log_dir, "glm_review_pass")), 1)
        self.assertEqual(self.card_row("t_h01d0001"), ("ready", GLM_WORKER))
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))
        self.assertEqual(self.card_row("t_4e1d0001"), ("review", GLM_REVIEWER))


if __name__ == "__main__":
    unittest.main()
