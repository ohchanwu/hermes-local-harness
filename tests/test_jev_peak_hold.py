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
]


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
        self.db = self.dir / "kanban.db"
        build_board_db(self.db, CARDS)
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        self.log_dir = self.dir / "logs"
        self.env = isolated_env(self.dir)
        self.env.update({"FAKE_HERMES_LOG": str(self.calls_log), "FAKE_KANBAN_DB": str(self.db)})
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config_path = self.dir / "config.json"
        self.config = json.loads(json.dumps(CONFIG))
        self.save_config()

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def script(self, *args, now=WEDNESDAY_16, extra_env=None):
        env = {**os.environ, **(extra_env or {})}
        argv = [sys.executable, str(SCRIPT), *args, "--board", "harness", "--kanban-db", str(self.db),
                "--config", str(self.config_path), "--hermes", self.hermes, "--now", now]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
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

    def test_release_only_marker_held_cards(self):
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

    def next_call_factory(self):
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            self.counter += 1
            task_id = f"t_new{self.counter}"
            args = payload or {}
            status = "blocked" if args.get("initial_status") == "blocked" else "ready"
            conn = sqlite3.connect(self.db)
            conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, ?, ?, ?)",
                         (task_id, "synthetic", status, args.get("assignee") or "harness-worker"))
            conn.commit()
            conn.close()
            return json.dumps({"ok": True, "task_id": task_id})

        return next_call, calls

    def create(self, route, now, assignee="harness-worker"):
        self.fake.choice(route, {"easy": 0.0, "medium": 0.0, "hard": 0.0, route: 0.9})
        next_call, calls = self.next_call_factory()
        ask = functools.partial(jev_client.ask, settings=self.config["jev"])
        routing.handle_create({"title": "t", "body": "b", "assignee": assignee, "board": "harness"}, next_call,
                              config=self.config, ask=ask, now=datetime.fromisoformat(now))
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


if __name__ == "__main__":
    unittest.main()
