"""Offline tests for the GLM review pass of ``scripts/jev-peak-hold``.

Decision document ``docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md``,
item 5 of "What the plugin cards must implement": a card that a GLM reviewer
blocked with a reason that starts with ``jev-glm-review-pass`` is passed to the
board's Opus reviewer with ``hermes kanban assign`` and then
``hermes kanban unblock``, on every ``run`` of the script, independent of the
peak-hours hold.

Board changes go through a stand-in ``hermes`` command that records its
arguments and applies ``assign``, ``unblock`` and ``schedule`` to a temporary
Kanban database that has the Hermes columns the code reads (``tasks``,
``task_events`` with ``payload`` and ``run_id``, ``task_runs`` with
``profile``). Nothing touches a live board, the live switch file or the live
logs.
"""
from __future__ import annotations

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
sys.path.insert(0, str(ROOT / "plugins" / "jev"))

import jev_log  # noqa: E402
import peak_hold  # noqa: E402

SCRIPT = ROOT / "scripts" / "jev-peak-hold"
CONFIG = json.loads((ROOT / "plugins" / "jev" / "config.json").read_text(encoding="utf-8"))
KST = ZoneInfo("Asia/Seoul")
WEDNESDAY_16 = "2026-11-11T16:00:00+09:00"
WEDNESDAY_19 = "2026-11-11T19:00:00+09:00"
SATURDAY_16 = "2026-11-14T16:00:00+09:00"
BOARD = "harness"
GLM_REVIEWER = "harness-reviewer-glm"
OPUS_REVIEWER = "harness-reviewer"
GLM_WORKER = "harness-worker-glm-easy-1"
PASS_REASON = "jev-glm-review-pass no findings"
OTHER_REASON = "waiting for the owner"
MARK = "jev-peak-hold until 2026-11-11T19:00:00+09:00"
# The empty database of the card's test contract (python3 scripts/jev-peak-hold
# run --dry-run --board harness --kanban-db ... --hermes /usr/bin/false). The path is the one that
# contract of card t_64f37437 names, in the scratch directory of the live profile
# harness-worker-glm-2; card t_18a2dc93 renames that profile only in the repository, so the path
# keeps the live name.
CONTRACT_EMPTY_DB = Path("/Users/chanbla11mit/.hermes/profiles/harness-worker-glm-2/cache/scratch/"
                         "t_64f37437-empty.db")

# The stand-in hermes command: it records its arguments, applies assign,
# unblock and schedule to $FAKE_KANBAN_DB, and exits 1 for a verb named in
# $FAKE_HERMES_FAIL_VERBS (comma separated). Like Hermes, unblock returns a
# card whose newest blocked event records source_status review to review, and
# every other blocked or scheduled card to ready.
STAND_IN_HERMES = r'''
import json, os, sqlite3, sys, time
argv = sys.argv[1:]
with open(os.environ["FAKE_HERMES_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
code = 0
db = os.environ.get("FAKE_KANBAN_DB")
if argv[:1] == ["kanban"]:
    rest = argv[1:]
    if rest[:1] == ["--board"]:
        rest = rest[2:]
    verb, task_id = rest[0], rest[1]
    fail = set(filter(None, os.environ.get("FAKE_HERMES_FAIL_VERBS", "").split(",")))
    if verb in fail:
        code = 1
    elif db:
        conn = sqlite3.connect(db)
        now = int(time.time())
        if verb == "assign":
            conn.execute("UPDATE tasks SET assignee=? WHERE id=?", (rest[2], task_id))
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                         (task_id, "assigned", json.dumps({"assignee": rest[2]}), now))
        elif verb == "unblock":
            row = conn.execute("SELECT payload FROM task_events WHERE task_id=? AND kind='blocked' "
                               "ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
            status = "ready"
            if row is not None:
                try:
                    status = ("review" if json.loads(row[0] or "{}").get("source_status") == "review"
                              else "ready")
                except Exception:
                    status = "ready"
            cur = conn.execute("UPDATE tasks SET status=? WHERE id=? AND status IN ('blocked','scheduled')",
                               (status, task_id))
            code = 0 if cur.rowcount == 1 else 1
            if cur.rowcount == 1:
                conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                             (task_id, "unblocked", None, now))
        elif verb == "schedule":
            reason = " ".join(rest[2:])
            cur = conn.execute("UPDATE tasks SET status='scheduled' WHERE id=? AND status IN "
                               "('todo','ready','running','blocked')", (task_id,))
            code = 0 if cur.rowcount == 1 else 1
            if cur.rowcount == 1:
                conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                             (task_id, "scheduled", json.dumps({"reason": reason}), now))
        conn.commit()
        conn.close()
sys.exit(code)
'''


def build_pass_db(path: Path, tasks=(), events=(), runs=()) -> None:
    """Synthetic board database with the columns the pass reads.

    ``tasks``: ``(id, status, assignee)``. ``events``: ``(task_id, run_id,
    kind, payload)`` in order, so the last entry is the newest event.
    ``runs``: ``(run_id, profile)``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(path) + suffix)
        if side.exists():
            side.unlink()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT,"
                 " assignee TEXT, model_override TEXT, provider_override TEXT)")
    conn.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,"
                 " run_id INTEGER, kind TEXT, payload TEXT, created_at INTEGER)")
    conn.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT,"
                 " status TEXT, started_at INTEGER, ended_at INTEGER, outcome TEXT)")
    for task_id, status, assignee in tasks:
        conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, 'synthetic card', ?, ?)",
                     (task_id, status, assignee))
    for task_id, run_id, kind, payload in events:
        conn.execute("INSERT INTO task_events (task_id, run_id, kind, payload, created_at) VALUES (?,?,?,?,0)",
                     (task_id, run_id, kind, json.dumps(payload) if payload is not None else None))
    for run_id, profile in runs:
        conn.execute("INSERT INTO task_runs (id, task_id, profile, status, started_at)"
                     " VALUES (?, 't_0none', ?, 'done', 0)", (run_id, profile))
    conn.commit()
    conn.close()


def blocked_event(reason=PASS_REASON, source_status="review"):
    return {"reason": reason, "kind": "needs_input", "source_status": source_status}


class _PassCase(unittest.TestCase):
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

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def rebuild(self, tasks=(), events=(), runs=()):
        build_pass_db(self.db, tasks, events, runs)

    def script(self, *args, now=WEDNESDAY_16, extra_env=None, returncode=0, boards=(BOARD,)):
        """Run the script as a process that no worker started.

        The three environment variables that mark a worker process are removed
        from the child environment unless ``extra_env`` sets one of them.
        """
        env = dict(os.environ)
        for name in peak_hold.WORKER_SESSION_ENV_NAMES:
            env.pop(name, None)
        env.update(extra_env or {})
        argv = [sys.executable, str(SCRIPT), *args]
        for board in boards:
            argv += ["--board", board]
        argv += ["--kanban-db", str(self.db), "--config", str(self.config_path),
                 "--hermes", self.hermes, "--now", now]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, returncode, proc.stdout + proc.stderr)
        return proc.stdout

    def calls(self):
        if not self.calls_log.exists():
            return []
        return [json.loads(line) for line in self.calls_log.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    def decisions(self, event=None):
        path = self.log_dir / "decisions.jsonl"
        if not path.exists():
            return []
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        return [r for r in records if event is None or r.get("event") == event]

    def card_row(self, task_id):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT status, assignee FROM tasks WHERE id=?", (task_id,)).fetchone()
        finally:
            conn.close()


class WorkerSessionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {})
        patcher.start()
        self.addCleanup(patcher.stop)
        # The three names of the card; none may leak in from the environment
        # this test process itself runs in.
        for name in peak_hold.WORKER_SESSION_ENV_NAMES:
            os.environ.pop(name, None)

    def test_covers_the_three_names(self):
        values = {"HERMES_KANBAN_TASK": "t_feedc0de", "HERMES_KANBAN_RUN_ID": "497",
                  "HERMES_DELEGATED_CHILD_CONTEXT": "/Users/chanbla11mit/.hermes"}
        self.assertFalse(peak_hold.worker_session())
        for name, value in values.items():
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: value}):
                self.assertTrue(peak_hold.worker_session())
        for name in values:
            with self.subTest(name=name, whitespace=True), mock.patch.dict(os.environ, {name: "  "}):
                self.assertFalse(peak_hold.worker_session())


class SelectionTests(_PassCase):
    def plan(self, boards=None):
        return peak_hold.plan_glm_review_pass(self.config, boards or {BOARD: self.db})

    def test_selects_a_card_the_glm_reviewer_blocked_with_the_pass_reason(self):
        self.rebuild(tasks=[("t_9a55e551", "blocked", GLM_REVIEWER)],
                     events=[("t_9a55e551", 11, "blocked", blocked_event())],
                     runs=[(11, GLM_REVIEWER)])
        passes, errors = self.plan()
        self.assertEqual(errors, [])
        self.assertEqual([{"board": BOARD, "task_id": "t_9a55e551", "glm_reviewer": GLM_REVIEWER,
                           "opus_reviewer": OPUS_REVIEWER, "assign": True}], passes)

    def test_the_reason_must_start_with_the_prefix(self):
        cases = [(PASS_REASON, True), ("jev-glm-review-pass", True),
                 ("jev-glm-review-pass more text", True),
                 ("jev-glm-review-pas no findings", False),
                 ("xjev-glm-review-pass no findings", False),
                 ("review pass jev-glm-review-pass", False),
                 (None, False)]
        for reason, selected in cases:
            with self.subTest(reason=reason):
                self.rebuild(tasks=[("t_0be57501", "blocked", GLM_REVIEWER)],
                             events=[("t_0be57501", 21, "blocked", blocked_event(reason=reason))],
                             runs=[(21, GLM_REVIEWER)])
                passes, _errors = self.plan()
                self.assertEqual(len(passes) == 1, selected)

    def test_not_selected_cards(self):
        # (task_id, name, status, assignee, event_run_id, event, raw payload)
        cases = [
            ("t_c0de0001", "glm worker run claimed from ready", "blocked", GLM_WORKER,
             31, blocked_event(), None),
            ("t_c0de0002", "run not claimed from review", "blocked", GLM_REVIEWER,
             32, blocked_event(source_status="ready"), None),
            ("t_c0de0003", "glm worker run even from review", "blocked", GLM_WORKER,
             33, blocked_event(), None),
            ("t_c0de0004", "another reason", "blocked", GLM_REVIEWER,
             34, blocked_event(reason=OTHER_REASON), None),
            ("t_c0de0005", "no blocked event", "blocked", GLM_REVIEWER, None, None, None),
            ("t_c0de0006", "run id absent", "blocked", GLM_REVIEWER,
             None, blocked_event(), None),
            ("t_c0de0007", "run row absent", "blocked", GLM_REVIEWER,
             36, blocked_event(), None),
            ("t_c0de0008", "run of another profile", "blocked", GLM_REVIEWER,
             37, blocked_event(), None),
            ("t_c0de0009", "assignee is a glm worker", "blocked", GLM_WORKER,
             38, blocked_event(), None),
            ("t_c0de000a", "unparsable payload", "blocked", GLM_REVIEWER,
             40, blocked_event(), "{not json"),
        ]
        for status in ("triage", "ready", "review", "running", "scheduled", "todo", "done"):
            cases.append(("t_c0de000b", f"status {status}", status, GLM_REVIEWER,
                          39, blocked_event(), None))
        for task_id, name, status, assignee, run_id, event, raw_payload in cases:
            with self.subTest(name=name):
                runs = {31: GLM_WORKER, 32: GLM_REVIEWER, 33: GLM_WORKER, 34: GLM_REVIEWER,
                        36: "a profile that is not the GLM reviewer of the board", 37: "harness-reviewer-2",
                        38: GLM_REVIEWER, 39: GLM_REVIEWER, 40: GLM_REVIEWER}
                events = [] if event is None else [(task_id, run_id, "blocked", event)]
                self.rebuild(tasks=[(task_id, status, assignee)], events=events,
                             runs=[(rid, profile) for rid, profile in runs.items() if rid is not None])
                if raw_payload is not None:
                    conn = sqlite3.connect(self.db)
                    conn.execute("UPDATE task_events SET payload=? WHERE task_id=?",
                                 (raw_payload, task_id))
                    conn.commit()
                    conn.close()
                passes, errors = self.plan()
                self.assertEqual(errors, [])
                self.assertEqual(passes, [])

    def test_newest_blocked_event_decides(self):
        self.rebuild(tasks=[("t_0dada001", "blocked", GLM_REVIEWER)],
                     events=[("t_0dada001", 41, "blocked", blocked_event()),
                             ("t_0dada001", 42, "blocked", blocked_event(reason=OTHER_REASON))],
                     runs=[(41, GLM_REVIEWER), (42, GLM_REVIEWER)])
        self.assertEqual(self.plan()[0], [])
        self.rebuild(tasks=[("t_0dada002", "blocked", GLM_REVIEWER)],
                     events=[("t_0dada002", 43, "blocked", blocked_event(reason=OTHER_REASON)),
                             ("t_0dada002", 44, "blocked", blocked_event())],
                     runs=[(43, GLM_REVIEWER), (44, GLM_REVIEWER)])
        self.assertEqual(len(self.plan()[0]), 1)

    def test_board_without_reviewers_is_skipped_without_a_read(self):
        for remove in ("glm_reviewers", "opus_reviewer"):
            with self.subTest(remove=remove):
                self.config = json.loads(json.dumps(CONFIG))
                del self.config["routing"]["boards"][BOARD][remove]
                self.save_config()
                self.rebuild(tasks=[("t_0fa11001", "blocked", GLM_REVIEWER)],
                             events=[("t_0fa11001", 51, "blocked", blocked_event())],
                             runs=[(51, GLM_REVIEWER)])
                passes, errors = self.plan()
                self.assertEqual((passes, errors), ([], []))

    def test_read_error_leaves_the_cards_and_reports_the_board(self):
        self.db.write_bytes(b"this file is not a SQLite database" * 200)
        passes, errors = self.plan()
        self.assertEqual(passes, [])
        self.assertEqual(errors, [{"board": BOARD, "error_class": "DatabaseError"}])


class ApplyTests(_PassCase):
    def setUp(self):
        super().setUp()
        self.rebuild(tasks=[("t_9a55e551", "blocked", GLM_REVIEWER)],
                     events=[("t_9a55e551", 11, "blocked", blocked_event())],
                     runs=[(11, GLM_REVIEWER)])

    def planned(self):
        passes, _errors = peak_hold.plan_glm_review_pass(self.config, {BOARD: self.db})
        return passes

    def test_assign_then_unblock(self):
        results = peak_hold.apply_glm_review_pass(self.config, self.planned(), self.hermes,
                                                  {BOARD: self.db})
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER],
                                        ["kanban", "--board", BOARD, "unblock", "t_9a55e551"]])
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))
        self.assertEqual([(r["task_id"], r["assigned"], r["unblocked"], r["skipped"], r["error_class"])
                          for r in results], [("t_9a55e551", True, True, False, None)])
        self.assertEqual(len(self.decisions("glm_review_pass")), 1)

    def test_assignee_already_the_opus_reviewer_gets_only_unblock(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE tasks SET assignee=? WHERE id='t_9a55e551'", (OPUS_REVIEWER,))
        conn.commit()
        conn.close()
        passes = self.planned()
        self.assertEqual([p["assign"] for p in passes], [False])
        results = peak_hold.apply_glm_review_pass(self.config, passes, self.hermes, {BOARD: self.db})
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "unblock", "t_9a55e551"]])
        record = self.decisions("glm_review_pass")[0]
        self.assertEqual((record["assigned"], record["unblocked"], record["skipped"]), (None, True, False))
        self.assertEqual(results[0]["assigned"], None)

    def test_failed_assign_runs_no_unblock(self):
        with mock.patch.dict(os.environ, {"FAKE_HERMES_FAIL_VERBS": "assign"}):
            results = peak_hold.apply_glm_review_pass(self.config, self.planned(), self.hermes,
                                                      {BOARD: self.db})
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER]])
        self.assertEqual(self.card_row("t_9a55e551"), ("blocked", GLM_REVIEWER))
        record = self.decisions("glm_review_pass")[0]
        self.assertEqual((record["assigned"], record["unblocked"], record["skipped"], record["error_class"]),
                         (False, False, False, "CommandFailed"))
        self.assertEqual([(r["assigned"], r["unblocked"]) for r in results], [(False, False)])

    def test_failed_unblock_is_tried_again_with_only_unblock(self):
        with mock.patch.dict(os.environ, {"FAKE_HERMES_FAIL_VERBS": "unblock"}):
            self.script("--apply", returncode=1)
        self.assertEqual(self.card_row("t_9a55e551"), ("blocked", OPUS_REVIEWER))
        records = self.decisions("glm_review_pass")
        self.assertEqual([(r["assigned"], r["unblocked"], r["error_class"]) for r in records],
                         [(True, False, "CommandFailed")])
        out = self.script("--apply")
        self.assertIn("passed harness t_9a55e551", out)
        # The card is already assigned to the Opus reviewer, so this run ran only unblock.
        self.assertEqual(self.calls()[-1], ["kanban", "--board", BOARD, "unblock", "t_9a55e551"])
        self.assertNotIn(["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER],
                         self.calls()[2:])
        self.assertEqual(self.decisions("glm_review_pass")[-1]["unblocked"], True)
        # A third run has nothing left to pass.
        self.assertIn("no card to pass to the Opus reviewer", self.script("--apply"))

    def test_card_changed_between_selection_and_commands_is_skipped(self):
        passes = self.planned()
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE tasks SET status='review' WHERE id='t_9a55e551'")
        conn.commit()
        conn.close()
        results = peak_hold.apply_glm_review_pass(self.config, passes, self.hermes, {BOARD: self.db})
        self.assertEqual(self.calls(), [])
        self.assertEqual([(r["skipped"], r["error_class"]) for r in results], [(True, None)])
        record = self.decisions("glm_review_pass")[0]
        self.assertEqual((record["skipped"], record["assigned"], record["unblocked"]), (True, None, False))

    def test_read_error_before_the_commands_skips_the_card(self):
        passes = self.planned()
        with mock.patch.object(peak_hold, "connect_readonly",
                               side_effect=sqlite3.OperationalError("locked")):
            results = peak_hold.apply_glm_review_pass(self.config, passes, self.hermes, {BOARD: self.db})
        self.assertEqual(self.calls(), [])
        self.assertEqual([(r["skipped"], r["error_class"]) for r in results], [(True, "OperationalError")])

    def test_the_record_has_exactly_the_fields_of_item_6(self):
        peak_hold.apply_glm_review_pass(self.config, self.planned(), self.hermes, {BOARD: self.db})
        record = self.decisions("glm_review_pass")[0]
        item6 = {"event", "board", "task_id", "glm_reviewer", "opus_reviewer", "assigned",
                 "unblocked", "skipped", "error_class"}
        known = set(jev_log.STREAM_FIELDS["decisions"]) | {"ts", "profile"}
        # Every field of item 6 is present, and no field outside item 6 and the
        # fixed fields of the decisions stream.
        self.assertEqual(set(record) - known, item6 - known)
        self.assertEqual(item6 <= set(record), True)
        self.assertEqual((record["event"], record["board"], record["task_id"], record["glm_reviewer"],
                          record["opus_reviewer"], record["assigned"], record["unblocked"],
                          record["skipped"], record["error_class"]),
                         ("glm_review_pass", BOARD, "t_9a55e551", GLM_REVIEWER, OPUS_REVIEWER,
                          True, True, False, None))
        # No card text and no reason text is written.
        self.assertNotIn(PASS_REASON, json.dumps(record))
        self.assertNotIn("synthetic card", json.dumps(record))

    def test_a_failure_to_write_the_record_is_ignored(self):
        passes = self.planned()
        with mock.patch.object(jev_log, "write", side_effect=OSError("disk full")):
            results = peak_hold.apply_glm_review_pass(self.config, passes, self.hermes, {BOARD: self.db})
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))
        self.assertEqual(results[0]["unblocked"], True)


class ScriptTests(_PassCase):
    @classmethod
    def setUpClass(cls):
        # The empty database of the card's test contract, created here with the
        # Hermes schema (no rows).
        CONTRACT_EMPTY_DB.parent.mkdir(parents=True, exist_ok=True)
        build_pass_db(CONTRACT_EMPTY_DB)

    def rebuild_with_pass_card(self):
        self.rebuild(tasks=[("t_9a55e551", "blocked", GLM_REVIEWER)],
                     events=[("t_9a55e551", 11, "blocked", blocked_event())],
                     runs=[(11, GLM_REVIEWER)])

    def test_run_apply_passes_the_card(self):
        self.rebuild_with_pass_card()
        out = self.script("--apply")
        self.assertIn("passed harness t_9a55e551 to harness-reviewer", out)
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER],
                                        ["kanban", "--board", BOARD, "unblock", "t_9a55e551"]])
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))
        self.assertEqual(len(self.decisions("glm_review_pass")), 1)

    def test_dry_run_prints_the_plan_and_runs_no_command(self):
        self.rebuild_with_pass_card()
        out = self.script()
        self.assertIn("planned pass harness t_9a55e551 to harness-reviewer (assign then unblock)", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.decisions(), [])
        self.assertEqual(self.card_row("t_9a55e551"), ("blocked", GLM_REVIEWER))

    def test_dry_run_of_a_card_already_on_the_opus_reviewer(self):
        self.rebuild(tasks=[("t_9a55e552", "blocked", OPUS_REVIEWER)],
                     events=[("t_9a55e552", 12, "blocked", blocked_event())],
                     runs=[(12, GLM_REVIEWER)])
        out = self.script()
        self.assertIn("planned pass harness t_9a55e552 to harness-reviewer (unblock)", out)
        self.script("--apply")
        self.assertEqual(self.calls(), [["kanban", "--board", BOARD, "unblock", "t_9a55e552"]])

    def test_pass_with_the_hold_switch_off(self):
        peak_hold.write_switch(False, "owner")
        self.rebuild_with_pass_card()
        self.script("--apply")
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))

    def test_pass_with_peak_hold_enabled_false(self):
        self.config["peak_hold"]["enabled"] = False
        self.save_config()
        self.rebuild_with_pass_card()
        self.script("--apply")
        self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))

    def test_pass_outside_the_window_and_on_the_weekend(self):
        for now in ("2026-11-11T14:59:00+09:00", WEDNESDAY_19, SATURDAY_16):
            with self.subTest(now=now):
                self.rebuild_with_pass_card()
                self.calls_log.unlink(missing_ok=True)
                self.script("--apply", now=now)
                self.assertEqual(self.card_row("t_9a55e551"), ("review", OPUS_REVIEWER))

    def test_each_worker_environment_variable_refuses_the_pass(self):
        values = {"HERMES_KANBAN_TASK": "t_feedc0de", "HERMES_KANBAN_RUN_ID": "497",
                  "HERMES_DELEGATED_CHILD_CONTEXT": "/Users/chanbla11mit/.hermes"}
        for name, value in values.items():
            with self.subTest(name=name):
                self.rebuild_with_pass_card()
                self.calls_log.unlink(missing_ok=True)
                out = self.script("--apply", extra_env={name: value})
                self.assertIn("pass refused: this process was started by a worker", out)
                self.assertEqual(self.calls(), [])
                self.assertEqual(self.card_row("t_9a55e551"), ("blocked", GLM_REVIEWER))
                self.assertEqual(self.decisions("glm_review_pass"), [])

    def test_holds_and_releases_are_unchanged_in_a_run_with_both_kinds_of_cards(self):
        self.rebuild(tasks=[("t_h01d0001", "ready", GLM_WORKER),
                            ("t_9a55e551", "blocked", GLM_REVIEWER)],
                     events=[("t_9a55e551", 11, "blocked", blocked_event())],
                     runs=[(11, GLM_REVIEWER)])
        out = self.script("--apply")
        self.assertIn("held harness t_h01d0001", out)
        self.assertIn("passed harness t_9a55e551 to harness-reviewer", out)
        self.assertEqual(self.calls(), [
            ["kanban", "--board", BOARD, "schedule", "t_h01d0001", MARK],
            ["kanban", "--board", BOARD, "assign", "t_9a55e551", OPUS_REVIEWER],
            ["kanban", "--board", BOARD, "unblock", "t_9a55e551"],
        ])
        self.assertEqual([(r["event"], r["task_id"], r["applied"]) for r in self.decisions("hold")],
                         [("hold", "t_h01d0001", True)])
        self.script("--apply", now=WEDNESDAY_19)
        self.assertEqual(self.calls()[-1], ["kanban", "--board", BOARD, "unblock", "t_h01d0001"])
        self.assertEqual([(r["event"], r["task_id"], r["applied"]) for r in self.decisions("release")],
                         [("release", "t_h01d0001", True)])
        self.assertEqual(len(self.decisions("glm_review_pass")), 1)
        self.assertEqual(self.card_row("t_h01d0001"), ("ready", GLM_WORKER))

    def test_board_without_reviewers_runs_without_pass_and_without_error(self):
        self.config = json.loads(json.dumps(CONFIG))
        del self.config["routing"]["boards"][BOARD]["glm_reviewers"]
        self.save_config()
        self.rebuild_with_pass_card()
        out = self.script("--apply")
        self.assertIn("no card to pass to the Opus reviewer", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.card_row("t_9a55e551"), ("blocked", GLM_REVIEWER))

    def test_empty_database_runs_no_command(self):
        self.rebuild()
        out = self.script()
        self.assertIn("no card to pass to the Opus reviewer", out)
        self.assertIn("nothing to hold or release", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.decisions(), [])


if __name__ == "__main__":
    unittest.main()
