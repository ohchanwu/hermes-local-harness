"""Offline tests for the GLM peak-hours hold (Part E) and the owner's on/off switch.

Board changes go through a fake ``hermes`` command (tests/test_jev_client.py)
that records its arguments and applies ``schedule`` and ``unblock`` to a
synthetic board database. Jev is the local fake TypeSafe endpoint. Nothing
touches a live board, the live switch file or the live logs.
"""
from __future__ import annotations

import functools
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "plugins" / "jev"))

from test_jev_client import (  # noqa: E402
    FakeTypeSafe, build_board_db, fake_hermes_calls, isolated_env, read_records, task_statuses, write_fake_hermes,
)

import jev_client  # noqa: E402
import peak_hold  # noqa: E402
import routing  # noqa: E402

SCRIPT = ROOT / "scripts" / "jev-peak-hold"
KST = ZoneInfo("Asia/Seoul")
CONFIG = json.loads((ROOT / "plugins" / "jev" / "config.json").read_text(encoding="utf-8"))
WEDNESDAY_16 = "2026-11-11T16:00:00+09:00"
WEDNESDAY_19 = "2026-11-11T19:00:00+09:00"
SATURDAY_16 = "2026-11-14T16:00:00+09:00"
MARK = "jev-peak-hold until 2026-11-11T19:00:00+09:00"

CARDS = [
    ("t_glm_ready", "ready", "harness-worker-glm-1"),
    ("t_glm_todo", "todo", "harness-worker-glm-2"),
    ("t_glm_running", "running", "harness-worker-glm-1"),
    ("t_claude_ready", "ready", "harness-worker"),
    ("t_other_blocked", "blocked", "harness-worker-glm-1"),
    ("t_other_sched", "scheduled", "harness-worker-glm-2", "waiting for the owner's release window"),
    ("t_lookalike", "scheduled", "harness-worker-glm-2", "not jev-peak-hold"),
    # IDs of the Hermes form `t_<hexadecimal digits>` for the kanban_unblock middleware, which uses only such IDs.
    ("t_0b10c4ed", "blocked", "harness-worker-glm-2"),
    ("t_c1a0de00", "blocked", "harness-worker"),
]
USR_BIN_PYTHON3 = "/usr/bin/python3"


class WindowTests(unittest.TestCase):
    cfg = CONFIG["peak_hold"]

    def at(self, text):
        return datetime.fromisoformat(text)

    def test_weekday_window_bounds(self):
        self.assertTrue(peak_hold.in_window(self.at("2026-11-11T15:00:00+09:00"), self.cfg))
        self.assertTrue(peak_hold.in_window(self.at("2026-11-11T18:59:59+09:00"), self.cfg))
        self.assertFalse(peak_hold.in_window(self.at("2026-11-11T14:59:59+09:00"), self.cfg))
        self.assertFalse(peak_hold.in_window(self.at("2026-11-11T19:00:00+09:00"), self.cfg))

    def test_every_weekday_and_no_weekend(self):
        for day in range(9, 14):  # Monday 9 to Friday 13 November 2026
            self.assertTrue(peak_hold.in_window(datetime(2026, 11, day, 16, tzinfo=KST), self.cfg), day)
        for day in (14, 15):
            self.assertFalse(peak_hold.in_window(datetime(2026, 11, day, 16, tzinfo=KST), self.cfg), day)

    def test_other_time_zones_are_converted(self):
        self.assertTrue(peak_hold.in_window(datetime(2026, 11, 11, 6, 30, tzinfo=timezone.utc), self.cfg))
        self.assertFalse(peak_hold.in_window(datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc), self.cfg))

    def test_held_until_is_end_of_same_day(self):
        self.assertEqual(peak_hold.held_until(self.at("2026-11-11T15:10:00+09:00"), self.cfg),
                         "2026-11-11T19:00:00+09:00")


class _BoardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = isolated_env(self.dir)
        # The Hermes board layout under the test Kanban home: <home>/kanban/boards/<board>/kanban.db
        self.db = Path(self.env["HERMES_KANBAN_HOME"]) / "kanban" / "boards" / "harness" / "kanban.db"
        build_board_db(self.db, CARDS)
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        self.log_dir = self.dir / "logs"
        self.env.update({"FAKE_HERMES_LOG": str(self.calls_log), "FAKE_KANBAN_DB": str(self.db)})
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config_path = self.dir / "config.json"
        self.config = json.loads(json.dumps(CONFIG))
        self.save_config()

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def script(self, *args, now=WEDNESDAY_16, extra_env=None, python=None, returncode=0, boards=("harness",),
               kanban_db=True):
        env = {**os.environ, **(extra_env or {})}
        argv = [python or sys.executable, str(SCRIPT), *args]
        for board in boards:
            argv += ["--board", board]
        if kanban_db:
            argv += ["--kanban-db", str(self.db)]
        argv += ["--config", str(self.config_path), "--hermes", self.hermes, "--now", now]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, returncode, proc.stdout + proc.stderr)
        return proc.stdout

    def statuses(self):
        return task_statuses(self.db)

    def decisions(self, event=None):
        records = read_records(self.log_dir, "decisions")
        return [r for r in records if event is None or r["event"] == event]


class PeakHoldScriptTests(_BoardCase):
    def test_dry_run_is_default_and_changes_nothing(self):
        before = self.statuses()
        out = self.script()
        self.assertIn("planned hold harness t_glm_ready", out)
        self.assertIn("planned hold harness t_glm_todo", out)
        self.assertEqual(self.statuses(), before)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.decisions(), [])

    def test_glm_cards_held_inside_window(self):
        self.script("--apply")
        statuses = self.statuses()
        self.assertEqual(statuses["t_glm_ready"], "scheduled")
        self.assertEqual(statuses["t_glm_todo"], "scheduled")
        self.assertEqual(statuses["t_glm_running"], "running")  # a run that already started continues
        self.assertEqual(statuses["t_claude_ready"], "ready")  # Claude cards are never held
        self.assertEqual(statuses["t_other_blocked"], "blocked")
        self.assertIn(["kanban", "--board", "harness", "schedule", "t_glm_ready", MARK], fake_hermes_calls(self.calls_log))
        holds = self.decisions("hold")
        self.assertEqual(sorted(r["task_id"] for r in holds), ["t_glm_ready", "t_glm_todo"])
        self.assertTrue(all(r["held_until"] == "2026-11-11T19:00:00+09:00" and r["applied"] for r in holds))

    def test_hold_is_idempotent(self):
        self.script("--apply")
        calls = len(fake_hermes_calls(self.calls_log))
        out = self.script("--apply")
        self.assertIn("nothing to hold or release", out)
        self.assertEqual(len(fake_hermes_calls(self.calls_log)), calls)
        self.assertEqual(len(self.decisions("hold")), 2)

    def test_not_held_outside_window_or_on_weekend(self):
        for now in ("2026-11-11T14:59:00+09:00", WEDNESDAY_19, SATURDAY_16):
            with self.subTest(now=now):
                self.script("--apply", now=now)
                self.assertEqual(self.statuses()["t_glm_ready"], "ready")
        self.assertEqual(self.decisions("hold"), [])

    def test_release_only_cards_held_with_the_marker(self):
        self.script("--apply")
        self.script("--apply", now=WEDNESDAY_19)
        statuses = self.statuses()
        self.assertEqual(statuses["t_glm_ready"], "ready")
        self.assertEqual(statuses["t_glm_todo"], "ready")  # the fake has no parents; Hermes re-gates to todo
        self.assertEqual(statuses["t_other_sched"], "scheduled")
        self.assertEqual(statuses["t_lookalike"], "scheduled")
        self.assertEqual(statuses["t_other_blocked"], "blocked")
        released = self.decisions("release")
        self.assertEqual(sorted(r["task_id"] for r in released), ["t_glm_ready", "t_glm_todo"])
        self.assertEqual(released[0]["held_until"], "2026-11-11T19:00:00+09:00")
        unblocks = [c for c in fake_hermes_calls(self.calls_log) if "unblock" in c]
        self.assertEqual(sorted(c[-1] for c in unblocks), ["t_glm_ready", "t_glm_todo"])

    def test_card_reassigned_to_claude_is_released_inside_window(self):
        self.script("--apply")
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE tasks SET assignee='harness-worker' WHERE id='t_glm_ready'")
        conn.commit()
        conn.close()
        self.script("--apply")
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")
        self.assertEqual(self.statuses()["t_glm_todo"], "scheduled")

    def test_config_disabled_holds_nothing_and_releases(self):
        self.script("--apply")
        self.config["peak_hold"]["enabled"] = False
        self.save_config()
        self.script("--apply")
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")
        self.assertEqual(len(self.decisions("hold")), 2)

    def test_failed_command_is_reported(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), "--apply", "--board", "harness", "--kanban-db", str(self.db),
             "--config", str(self.config_path), "--hermes", self.hermes, "--now", WEDNESDAY_16],
            capture_output=True, text=True, env={**os.environ, "FAKE_HERMES_EXIT": "2"}, timeout=120)
        self.assertEqual(out.returncode, 1)
        self.assertIn("failed hold harness t_glm_ready error_class=CommandFailed", out.stdout)
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")
        self.assertFalse(self.decisions("hold")[0]["applied"])

    def prepare_wal_without_side_files(self):
        """Put the board database in the state the reviewer found on the live board:
        WAL mode, and no -wal and -shm files.

        Some SQLite builds remove the two files when the last connection closes;
        the macOS system SQLite keeps the -wal file (persistent WAL). After a
        TRUNCATE checkpoint and close, the -wal file holds no data, so removing
        the two files gives the same state with every SQLite build.
        """
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        for suffix in ("-wal", "-shm"):
            side = Path(str(self.db) + suffix)
            if side.exists():
                side.unlink()
        # File header bytes 18 and 19 are 2 in WAL mode; reading them opens no connection.
        header = self.db.read_bytes()[:20]
        self.assertEqual((header[18], header[19]), (2, 2))
        for suffix in ("-wal", "-shm"):
            self.assertFalse(Path(str(self.db) + suffix).exists(), suffix)

    def test_wal_database_without_wal_and_shm_files(self):
        # Hermes board databases are in WAL mode, and the -wal and -shm files can be
        # absent when no connection is open. /usr/bin/python3 (older SQLite)
        # refused a mode=ro connection in that state.
        self.prepare_wal_without_side_files()
        self.script("--apply")
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")
        self.prepare_wal_without_side_files()
        self.script("--apply", now=WEDNESDAY_19)
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")

    @unittest.skipUnless(os.path.exists(USR_BIN_PYTHON3), "no /usr/bin/python3")
    def test_wal_database_under_usr_bin_python3(self):
        self.prepare_wal_without_side_files()
        self.assertIn("held cards: 0", self.script("status", python=USR_BIN_PYTHON3))
        self.prepare_wal_without_side_files()
        self.script("--apply", python=USR_BIN_PYTHON3)
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")
        self.prepare_wal_without_side_files()
        self.script("--apply", now=WEDNESDAY_19, python=USR_BIN_PYTHON3)
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")

    def test_unreadable_board_does_not_stop_other_boards(self):
        broken = self.db.parent.parent / "jobcron" / "kanban.db"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"this file is not a SQLite database" * 200)
        out = self.script("--apply", boards=("jobcron", "harness"), kanban_db=False, returncode=1)
        self.assertIn("failed read jobcron error_class=DatabaseError", out)
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")
        errors = self.decisions("read_error")
        self.assertEqual([(r["board"], r["error_class"]) for r in errors], [("jobcron", "DatabaseError")])
        status = self.script("status", boards=("jobcron", "harness"), kanban_db=False, returncode=1)
        self.assertIn("held cards: 2 (boards that could not be read are not counted)", status)

    def test_unreadable_board_writes_one_read_error_record_per_hour(self):
        broken = self.db.parent.parent / "jobcron" / "kanban.db"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"this file is not a SQLite database" * 200)
        runs = ("2026-11-11T16:00:00+09:00", "2026-11-11T16:00:10+09:00", "2026-11-11T16:59:59+09:00",
                "2026-11-11T17:00:00+09:00", "2026-11-11T17:30:00+09:00")
        for now in runs:
            with self.subTest(now=now):
                out = self.script("--apply", boards=("jobcron", "harness"), kanban_db=False, returncode=1, now=now)
                self.assertIn("failed read jobcron error_class=DatabaseError", out)
        errors = self.decisions("read_error")
        self.assertEqual([(r["board"], r["error_class"]) for r in errors],
                         [("jobcron", "DatabaseError"), ("jobcron", "DatabaseError")])
        state_file = self.log_dir / "read-error-state.json"
        self.assertEqual(json.loads(state_file.read_text(encoding="utf-8")),
                         {"jobcron": "2026-11-11T17:00:00+09:00"})
        self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)
        # A dry run prints the error and exits 1 but writes no record and no state.
        self.script(boards=("jobcron", "harness"), kanban_db=False, returncode=1, now="2026-11-11T18:30:00+09:00")
        self.assertEqual(len(self.decisions("read_error")), 2)
        # off logs read errors under the same limit.
        self.script("off", boards=("jobcron", "harness"), kanban_db=False, returncode=1,
                    now="2026-11-11T17:10:00+09:00")
        self.assertEqual(len(self.decisions("read_error")), 2)

    def test_read_error_limit_is_per_board(self):
        now = datetime.fromisoformat(WEDNESDAY_16)
        with mock.patch.dict(os.environ, {"HERMES_JEV_LOG_DIR": str(self.log_dir)}):
            self.assertEqual(peak_hold.log_read_errors([{"board": "jobcron", "error_class": "DatabaseError"}], now), 1)
            self.assertEqual(peak_hold.log_read_errors([
                {"board": "jobcron", "error_class": "DatabaseError"},
                {"board": "cha-pt", "error_class": "OperationalError"},
            ], now), 1)
            # An earlier time that is later than now (a clock that moved back) does not suppress the record.
            earlier = datetime.fromisoformat("2026-11-11T15:00:00+09:00")
            self.assertEqual(peak_hold.log_read_errors([{"board": "jobcron", "error_class": "DatabaseError"}],
                                                       earlier), 1)
            # An unreadable state file means no earlier time.
            (self.log_dir / "read-error-state.json").write_text("not json", encoding="utf-8")
            self.assertEqual(peak_hold.log_read_errors([{"board": "jobcron", "error_class": "DatabaseError"}], now), 1)
            self.assertEqual(peak_hold.log_read_errors([], now), 0)
        records = self.decisions("read_error")
        self.assertEqual([r["board"] for r in records], ["jobcron", "cha-pt", "jobcron", "jobcron"])
        state = json.loads((self.log_dir / "read-error-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"jobcron": "2026-11-11T16:00:00+09:00"})

    def test_read_is_query_only(self):
        conn = peak_hold.connect_readonly(self.db)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("UPDATE tasks SET status='done'")
        finally:
            conn.close()
        with self.assertRaises(FileNotFoundError):
            peak_hold.connect_readonly(self.dir / "missing.db")
        self.assertFalse((self.dir / "missing.db").exists())


class OwnerSwitchTests(_BoardCase):
    def switch_file(self):
        return self.dir / "state" / "peak-hold.json"

    def test_absent_switch_means_on(self):
        self.assertFalse(self.switch_file().exists())
        out = self.script("status")
        self.assertIn("peak-hours hold: on", out)
        self.assertIn("(absent, means on)", out)
        self.script("--apply")
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")

    def test_off_releases_at_once_and_stops_new_holds(self):
        self.script("--apply")
        out = self.script("off", "--by", "owner")
        self.assertIn("peak-hours hold turned off", out)
        content = json.loads(self.switch_file().read_text(encoding="utf-8"))
        self.assertEqual((content["enabled"], content["changed_by"]), (False, "owner"))
        self.assertIn("changed_at", content)
        self.assertEqual(stat.S_IMODE(self.switch_file().stat().st_mode), 0o600)
        statuses = self.statuses()
        self.assertEqual((statuses["t_glm_ready"], statuses["t_glm_todo"]), ("ready", "ready"))
        self.assertEqual(statuses["t_other_sched"], "scheduled")
        toggles = self.decisions("toggle")
        self.assertEqual([t["enabled"] for t in toggles], [False])
        self.script("--apply")  # still inside the window
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")
        self.assertIn("peak-hours hold: off", self.script("status"))

    def test_off_and_on_are_idempotent(self):
        self.script("off")
        self.script("off")
        self.script("on")
        self.script("on")
        self.assertEqual([t["enabled"] for t in self.decisions("toggle")], [False, True])

    def test_on_holds_again_inside_window(self):
        self.script("off")
        self.script("on", "--by", "owner")
        self.assertTrue(json.loads(self.switch_file().read_text(encoding="utf-8"))["enabled"])
        self.assertEqual(self.statuses()["t_glm_ready"], "ready")  # on does not hold by itself
        self.script("--apply")
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")

    def test_malformed_switch_is_on_and_logs_error_class(self):
        self.switch_file().parent.mkdir(parents=True)
        self.switch_file().write_text("{not json", encoding="utf-8")
        out = self.script("--apply")
        self.assertIn("switch file error: JSONDecodeError", out)
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")
        errors = self.decisions("switch_error")
        self.assertEqual(errors[0]["error_class"], "JSONDecodeError")
        self.switch_file().write_text('{"enabled": "no"}', encoding="utf-8")
        enabled, _content, error_class = peak_hold.read_switch()
        self.assertEqual((enabled, error_class), (True, "InvalidSwitchFile"))

    def test_status_counts_held_cards(self):
        self.script("--apply")
        out = self.script("status")
        self.assertIn("held cards: 2", out)
        self.assertIn("inside window now: true", out)

    def test_off_dry_run_changes_nothing(self):
        self.script("--apply")
        out = self.script("off", "--dry-run")
        self.assertIn("planned release harness t_glm_ready", out)
        self.assertFalse(self.switch_file().exists())
        self.assertEqual(self.statuses()["t_glm_ready"], "scheduled")


class CreationHoldTests(_BoardCase):
    """``kanban_create`` inside the window: the card is created blocked, then moved to
    ``scheduled`` with the marker, so the dispatcher never sees it as ready."""

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeTypeSafe()

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()

    def setUp(self):
        super().setUp()
        self.config["jev"] = self.fake.settings()
        self.config["kanban"]["hermes_command"] = self.hermes
        self.counter = 0

    def next_call_factory(self, existing=None):
        """Stands in for the Hermes tool. With ``existing`` it behaves like a
        repeated create with a known idempotency key: it returns that card."""
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            conn = sqlite3.connect(self.db)
            try:
                if existing is not None:
                    task_id = existing
                else:
                    self.counter += 1
                    task_id = f"t_new{self.counter}"
                    args = payload or {}
                    status = "blocked" if args.get("initial_status") == "blocked" else "ready"
                    conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, ?, ?, ?)",
                                 (task_id, "synthetic", status, args.get("assignee") or "harness-worker"))
                    conn.commit()
                landed = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()[0]
            finally:
                conn.close()
            return json.dumps({"ok": True, "task_id": task_id, "status": landed})

        return next_call, calls

    def create(self, route, now, assignee="harness-worker", existing=None, **extra):
        self.fake.choice(route, {"easy": 0.0, "medium": 0.0, "hard": 0.0, route: 0.9})
        next_call, calls = self.next_call_factory(existing)
        ask = functools.partial(jev_client.ask, settings=self.config["jev"])
        args = {"title": "t", "body": "b", "assignee": assignee, "board": "harness", **extra}
        routing.handle_create(args, next_call, config=self.config, ask=ask, now=datetime.fromisoformat(now))
        return calls[0]

    def test_glm_card_held_at_creation_inside_window(self):
        sent = self.create("easy", WEDNESDAY_16)
        self.assertEqual(sent["initial_status"], "blocked")
        self.assertEqual(self.statuses()["t_new1"], "scheduled")
        hold = self.decisions("hold")[-1]
        self.assertEqual((hold["task_id"], hold["applied"], hold["held_until"]),
                         ("t_new1", True, "2026-11-11T19:00:00+09:00"))
        self.assertEqual(self.decisions("route")[-1]["task_id"], "t_new1")
        self.script("--apply", now=WEDNESDAY_19)
        self.assertEqual(self.statuses()["t_new1"], "ready")

    def test_glm_card_not_held_outside_window_or_on_weekend(self):
        for now in (WEDNESDAY_19, SATURDAY_16):
            sent = self.create("medium", now)
            self.assertNotIn("initial_status", sent)
        self.assertEqual(self.decisions("hold"), [])

    def test_hard_route_claude_card_never_held(self):
        sent = self.create("hard", WEDNESDAY_16)
        self.assertIsNone(sent)
        self.assertEqual(self.statuses()["t_new1"], "ready")
        self.assertEqual(self.decisions("hold"), [])

    def test_switch_off_stops_creation_hold(self):
        peak_hold.write_switch(False, "owner")
        sent = self.create("easy", WEDNESDAY_16)
        self.assertNotIn("initial_status", sent)
        self.assertEqual(self.statuses()["t_new1"], "ready")

    def test_failed_schedule_returns_card_to_ready(self):
        with mock.patch.object(peak_hold, "hold_card", return_value=(False, "CommandFailed")):
            self.create("easy", WEDNESDAY_16)
        self.assertEqual(self.statuses()["t_new1"], "ready")
        hold = self.decisions("hold")[-1]
        self.assertEqual((hold["applied"], hold["error_class"]), (False, "CommandFailed"))

    # --- the creation-time hold acts only on a card this call created blocked ----------

    def set_existing(self, task_id, status, assignee):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, ?, ?, ?)",
                     (task_id, "synthetic", status, assignee))
        conn.commit()
        conn.close()

    def test_known_idempotency_key_never_schedules_an_existing_card(self):
        # Hermes returns the existing card for a known key. A card blocked for an
        # owner decision and a running GLM card must keep their status.
        self.set_existing("t_0dec1de0", "blocked", "harness-worker")
        self.set_existing("t_0a11ce00", "running", "harness-worker-glm-1")
        for existing, status in (("t_0dec1de0", "blocked"), ("t_0a11ce00", "running")):
            with self.subTest(existing=existing):
                sent = self.create("easy", WEDNESDAY_16, existing=existing, idempotency_key="key-1")
                self.assertNotIn("initial_status", sent)
                self.assertEqual(self.statuses()[existing], status)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.decisions("hold"), [])
        self.script("--apply", now=WEDNESDAY_19)
        self.assertEqual(self.statuses()["t_0dec1de0"], "blocked")

    def test_new_card_with_idempotency_key_is_left_to_the_script(self):
        sent = self.create("easy", WEDNESDAY_16, idempotency_key="key-2")
        self.assertNotIn("initial_status", sent)
        self.assertEqual(self.statuses()["t_new1"], "ready")
        self.script("--apply")
        self.assertEqual(self.statuses()["t_new1"], "scheduled")

    def test_result_status_other_than_blocked_is_not_scheduled(self):
        # The plugin set initial_status, but Hermes reports another status
        # (for example an existing card): nothing is scheduled.
        self.set_existing("t_0a11ce01", "running", "harness-worker-glm-2")
        sent = self.create("easy", WEDNESDAY_16, existing="t_0a11ce01")
        self.assertEqual(sent["initial_status"], "blocked")
        self.assertEqual(self.statuses()["t_0a11ce01"], "running")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_worker_session_card_is_created_as_requested_and_held_by_the_script(self):
        # In a dispatcher-started worker session hermes kanban schedule and unblock
        # refuse other cards, so the plugin does not create the card blocked.
        with mock.patch.dict(os.environ, {"HERMES_KANBAN_TASK": "t_feedc0de"}):
            sent = self.create("easy", WEDNESDAY_16)
        self.assertNotIn("initial_status", sent)
        self.assertEqual(sent["assignee"], "harness-worker-glm-1")
        self.assertEqual(self.statuses()["t_new1"], "ready")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.script("--apply")
        self.assertEqual(self.statuses()["t_new1"], "scheduled")

    def test_unresolvable_command_card_is_created_as_requested(self):
        self.config["kanban"]["hermes_command"] = str(self.dir / "no-such-hermes")
        sent = self.create("easy", WEDNESDAY_16)
        self.assertNotIn("initial_status", sent)
        self.assertEqual(self.statuses()["t_new1"], "ready")

    def test_card_created_blocked_by_the_caller_is_not_scheduled_at_creation(self):
        sent = self.create("easy", WEDNESDAY_16, initial_status="blocked")
        self.assertEqual(sent["initial_status"], "blocked")
        self.assertEqual(self.statuses()["t_new1"], "blocked")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])


class UnblockHoldTests(_BoardCase):
    """``kanban_unblock`` inside the window moves a blocked GLM card directly to
    ``scheduled`` with the marker (orchestrator Card Setup step 5)."""

    def setUp(self):
        super().setUp()
        self.config["kanban"]["hermes_command"] = self.hermes

    def unblock(self, task_id, now=WEDNESDAY_16, board="harness"):
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return json.dumps({"ok": True, "task_id": task_id, "status": "ready"})

        result = routing.handle_unblock({"task_id": task_id, "board": board}, next_call, config=self.config,
                                        now=datetime.fromisoformat(now))
        return calls, json.loads(result)

    def test_glm_card_goes_from_blocked_to_scheduled_inside_window(self):
        calls, result = self.unblock("t_0b10c4ed")
        self.assertEqual(calls, [])
        self.assertEqual((result["status"], result["held_until"]), ("scheduled", "2026-11-11T19:00:00+09:00"))
        self.assertEqual(self.statuses()["t_0b10c4ed"], "scheduled")
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "schedule", "t_0b10c4ed", MARK]])
        hold = self.decisions("hold")[-1]
        self.assertEqual((hold["task_id"], hold["applied"]), ("t_0b10c4ed", True))
        self.script("--apply", now=WEDNESDAY_19)
        self.assertEqual(self.statuses()["t_0b10c4ed"], "ready")

    def test_card_held_with_the_marker_stays_held(self):
        self.unblock("t_0b10c4ed")
        calls, result = self.unblock("t_0b10c4ed")
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(len(fake_hermes_calls(self.calls_log)), 1)

    def test_unblock_runs_unchanged_otherwise(self):
        cases = [("outside window", "t_0b10c4ed", WEDNESDAY_19, "harness", {}),
                 ("weekend", "t_0b10c4ed", SATURDAY_16, "harness", {}),
                 ("claude card", "t_c1a0de00", WEDNESDAY_16, "harness", {}),
                 ("unknown board", "t_0b10c4ed", WEDNESDAY_16, "other-board", {}),
                 ("worker session", "t_0b10c4ed", WEDNESDAY_16, "harness", {"HERMES_KANBAN_TASK": "t_feedc0de"})]
        for name, task_id, now, board, env in cases:
            with self.subTest(name=name), mock.patch.dict(os.environ, env):
                calls, result = self.unblock(task_id, now=now, board=board)
                self.assertEqual(calls, [None])
                self.assertEqual(result["status"], "ready")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_switch_off_unblocks_unchanged(self):
        peak_hold.write_switch(False, "owner")
        calls, _ = self.unblock("t_0b10c4ed")
        self.assertEqual(calls, [None])

    def test_failed_schedule_unblocks_unchanged(self):
        with mock.patch.dict(os.environ, {"FAKE_HERMES_EXIT": "2"}):
            calls, result = self.unblock("t_0b10c4ed")
        self.assertEqual(calls, [None])
        hold = self.decisions("hold")[-1]
        self.assertEqual((hold["applied"], hold["error_class"]), (False, "CommandFailed"))

    def test_unreadable_board_unblocks_unchanged(self):
        self.db.write_bytes(b"this file is not a SQLite database" * 200)
        calls, _ = self.unblock("t_0b10c4ed")
        self.assertEqual(calls, [None])
        self.assertEqual(self.decisions("hold")[-1]["error_class"], "DatabaseError")


if __name__ == "__main__":
    unittest.main()
