"""Offline tests for scripts/check-notify-subscriptions on synthetic board databases.

Each database is built under a temporary directory with only the columns the
script reads. All card ids, profiles and user ids are synthetic.
"""
import importlib.machinery
import importlib.util
import io
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check-notify-subscriptions"
loader = importlib.machinery.SourceFileLoader("check_notify_subscriptions", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
check = importlib.util.module_from_spec(spec)
loader.exec_module(check)

WAKE = ("notify+wake", "example-orchestrator", "example-user")


def build_db(path, tasks, subs, *, with_tasks=True, with_subs=True):
    """tasks: (id, status, assignee, title, created_at); subs: (task_id, mode, profile, user)."""
    conn = sqlite3.connect(path)
    try:
        if with_tasks:
            conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, assignee TEXT,"
                         " status TEXT, created_at INTEGER)")
            conn.executemany("INSERT INTO tasks (id, status, assignee, title, created_at)"
                             " VALUES (?, ?, ?, ?, ?)", tasks)
        if with_subs:
            conn.execute("CREATE TABLE kanban_notify_subs (task_id TEXT, delivery_mode TEXT,"
                         " notifier_profile TEXT, user_id TEXT)")
            conn.executemany("INSERT INTO kanban_notify_subs VALUES (?, ?, ?, ?)", subs)
        conn.commit()
    finally:
        conn.close()


class CheckNotifySubscriptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "kanban.db"

    def run_check(self, db=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check.main(["--db", str(db or self.db)])
        return code, out.getvalue().splitlines(), err.getvalue().splitlines()

    def assert_single_gap(self, sub_row):
        build_db(self.db, [("t_aaaa0001", "running", "example-worker", "Covered card", 1),
                           ("t_aaaa0002", "review", "example-reviewer", "Uncovered card", 2)],
                 [("t_aaaa0001", *WAKE), *([sub_row] if sub_row else [])])
        code, out, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(out, ["NO-WAKE-SUBSCRIPTION t_aaaa0002 review example-reviewer Uncovered card"])
        self.assertEqual(err, [])

    def test_all_open_cards_covered_exits_zero(self):
        build_db(self.db, [("t_aaaa0001", "running", "example-worker", "First", 1),
                           ("t_aaaa0002", "blocked", None, "Second", 2)],
                 [("t_aaaa0001", *WAKE), ("t_aaaa0002", "notify", "p", "u"), ("t_aaaa0002", *WAKE)])
        code, out, err = self.run_check()
        self.assertEqual((code, out, err),
                         (0, ["OK: 2 open cards, each with a notify+wake subscription"], []))

    def test_card_without_any_row_is_listed(self):
        self.assert_single_gap(None)

    def test_row_with_notify_mode_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "notify", "example-orchestrator", "example-user"))

    def test_row_with_wake_only_mode_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "wake", "example-orchestrator", "example-user"))

    def test_row_with_empty_notifier_profile_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "notify+wake", "", "example-user"))

    def test_row_with_null_notifier_profile_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "notify+wake", None, "example-user"))

    def test_row_with_empty_user_id_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "notify+wake", "example-orchestrator", ""))

    def test_row_with_null_user_id_is_listed(self):
        self.assert_single_gap(("t_aaaa0002", "notify+wake", "example-orchestrator", None))

    def test_done_and_archived_cards_are_ignored(self):
        build_db(self.db, [("t_aaaa0001", "ready", "example-worker", "Open", 1),
                           ("t_aaaa0002", "done", "example-worker", "Done", 2),
                           ("t_aaaa0003", "archived", "example-worker", "Archived", 3)],
                 [("t_aaaa0001", *WAKE)])
        code, out, _ = self.run_check()
        self.assertEqual((code, out), (0, ["OK: 1 open cards, each with a notify+wake subscription"]))

    def test_every_open_status_is_checked_and_order_is_created_at_then_id(self):
        statuses = ["triage", "todo", "scheduled", "ready", "running", "blocked", "review"]
        tasks = [(f"t_bbbb000{i}", status, "example-worker", f"Card {status}", 10 - i // 2)
                 for i, status in enumerate(statuses)]
        build_db(self.db, tasks, [])
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        expected = sorted(tasks, key=lambda t: (t[4], t[0]))
        self.assertEqual(out, [f"NO-WAKE-SUBSCRIPTION {t[0]} {t[1]} example-worker {t[3]}"
                               for t in expected])

    def test_missing_assignee_prints_dash_and_title_stays_on_one_line(self):
        build_db(self.db, [("t_aaaa0001", "todo", None, "Two\nlines", 1)], [])
        code, out, _ = self.run_check()
        self.assertEqual((code, out), (1, ["NO-WAKE-SUBSCRIPTION t_aaaa0001 todo - Two lines"]))

    def test_missing_file_exits_two_and_file_stays_absent(self):
        missing = self.dir / "absent" / "kanban.db"
        code, out, err = self.run_check(missing)
        self.assertEqual(code, 2)
        self.assertEqual(out, [])
        self.assertEqual(len(err), 1)
        self.assertTrue(err[0].startswith("ERROR:"))
        self.assertFalse(missing.exists())
        self.assertFalse(missing.parent.exists())
        sibling = self.dir / "kanban.db"
        code, _, _ = self.run_check(sibling)
        self.assertEqual(code, 2)
        self.assertFalse(sibling.exists())

    def test_missing_subscription_table_exits_two(self):
        build_db(self.db, [("t_aaaa0001", "running", "example-worker", "Open", 1)], [], with_subs=False)
        code, out, err = self.run_check()
        self.assertEqual(code, 2)
        self.assertEqual(out, [])
        self.assertEqual(len(err), 1)
        self.assertTrue(err[0].startswith("ERROR:"))

    def test_missing_tasks_table_exits_two(self):
        build_db(self.db, [], [("t_aaaa0001", *WAKE)], with_tasks=False)
        code, out, err = self.run_check()
        self.assertEqual((code, out, len(err)), (2, [], 1))
        self.assertTrue(err[0].startswith("ERROR:"))

    def test_file_that_is_not_a_database_exits_two(self):
        self.db.write_bytes(b"not a database file\n" * 64)
        code, out, err = self.run_check()
        self.assertEqual((code, out, len(err)), (2, [], 1))
        self.assertTrue(err[0].startswith("ERROR:"))

    def test_database_bytes_and_directory_unchanged_after_run(self):
        build_db(self.db, [("t_aaaa0001", "running", "example-worker", "Covered", 1),
                           ("t_aaaa0002", "running", "example-worker", "Uncovered", 2)],
                 [("t_aaaa0001", *WAKE)])
        before = self.db.read_bytes()
        names_before = sorted(p.name for p in self.dir.iterdir())
        code, _, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), names_before)

    def test_script_is_executable_and_runs_as_its_own_process(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        self.assertTrue(SCRIPT.read_text().startswith("#!/usr/bin/env python3\n"))
        build_db(self.db, [("t_aaaa0001", "running", "example-worker", "Covered", 1)],
                 [("t_aaaa0001", *WAKE)])
        result = subprocess.run([sys.executable, str(SCRIPT), "--db", str(self.db)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "OK: 1 open cards, each with a notify+wake subscription\n")

    def test_db_argument_is_required(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                check.main([])
        self.assertEqual(raised.exception.code, 2)

    def test_script_source_opens_read_only_and_has_no_write_statement_or_child_process(self):
        source = SCRIPT.read_text()
        self.assertIn('"?mode=ro", uri=True', source)
        self.assertEqual(source.count("sqlite3.connect("), 1)
        for word in ("INSERT", "UPDATE", "DELETE", "CREATE", "subprocess", "os.system", "socket", "urlopen"):
            self.assertIsNone(re.search(r"\b" + re.escape(word) + r"\b", source, re.IGNORECASE), word)


if __name__ == "__main__":
    unittest.main()
