"""Offline tests for scripts/orchestrator-board-check.

Every board database, Git repository, settings file and state file is made under
a temporary directory. All card ids, profiles, user ids and titles are synthetic.
The settings files in deployment/orchestrator-board-check/ are only read as text
and compared with roster.yaml; no live board database or live repository is read.
The provider_watch tests make synthetic profile homes whose state.db holds only a
session_model_usage table and whose agent.log files hold only synthetic log
records; neither contains message text, and no live profile home is read.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/orchestrator-board-check"
NOTIFY_CHECK = ROOT / "scripts/check-notify-subscriptions"
SETTINGS_DIR = ROOT / "deployment/orchestrator-board-check"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


check = load("orchestrator_board_check", SCRIPT)

NOW = 1_800_000_000
HOUR = 3600
REVIEWER = "example-reviewer"
WAKE = ("notify+wake", "example-orchestrator", "example-user")
WAKE_FALSE = '{"wakeAgent": false}'
HEADER = "Board example-board check for example-orchestrator:"
MARKER = "PRIVATE-MARKER-7f3a"

GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Example Author",
    "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Example Author",
    "GIT_COMMITTER_EMAIL": "author@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


def git(repo, *args):
    env = dict(os.environ, **GIT_ENV)
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            env=env, check=True)
    return result.stdout.strip()


def make_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    return path


def commit(repo, name, message=None):
    (repo / name).write_text(name + "\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message or name)
    return git(repo, "rev-parse", "HEAD")


def ref_snapshot(repo):
    return (git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
            git(repo, "symbolic-ref", "HEAD"), git(repo, "rev-parse", "HEAD"))


class Board:
    """A temporary board database with the tables and columns the script reads."""

    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT,"
            " status TEXT, created_at INTEGER);"
            "CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT, status TEXT,"
            " outcome TEXT, summary TEXT, metadata TEXT, started_at INTEGER, ended_at INTEGER);"
            "CREATE TABLE task_events (id INTEGER PRIMARY KEY, task_id TEXT, kind TEXT, payload TEXT,"
            " created_at INTEGER);"
            "CREATE TABLE task_comments (id INTEGER PRIMARY KEY, task_id TEXT, author TEXT, body TEXT,"
            " created_at INTEGER);"
            "CREATE TABLE kanban_notify_subs (task_id TEXT, delivery_mode TEXT, notifier_profile TEXT,"
            " user_id TEXT);")
        self.conn.commit()
        self.order = 0

    def card(self, task_id, status, title="Example card", *, assignee="example-worker",
             created_at=None, body="", wake=True):
        self.order += 1
        self.conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                          (task_id, title, body, assignee, status,
                           NOW - HOUR + self.order if created_at is None else created_at))
        if wake:
            self.sub(task_id, *WAKE)
        self.conn.commit()

    def sub(self, task_id, mode, profile, user):
        self.conn.execute("INSERT INTO kanban_notify_subs VALUES (?, ?, ?, ?)", (task_id, mode, profile, user))
        self.conn.commit()

    def run(self, task_id, *, profile=REVIEWER, outcome="completed", ended_at=NOW - HOUR,
            metadata=None, summary=""):
        text = metadata if isinstance(metadata, str) or metadata is None else json.dumps(metadata)
        self.conn.execute("INSERT INTO task_runs (task_id, profile, status, outcome, summary, metadata,"
                          " started_at, ended_at) VALUES (?, ?, 'done', ?, ?, ?, ?, ?)",
                          (task_id, profile, outcome, summary, text, ended_at - 60, ended_at))
        self.conn.commit()

    def event(self, task_id, created_at, payload=""):
        self.conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, 'edited', ?, ?)",
                          (task_id, payload, created_at))
        self.conn.commit()

    def comment(self, task_id, created_at, body=""):
        self.conn.execute("INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, 'x', ?, ?)",
                          (task_id, body, created_at))
        self.conn.commit()

    def close(self):
        self.conn.close()


class OrchestratorBoardCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.board = Board(self.dir / "kanban.db")
        self.addCleanup(self.board.close)
        self.repo_a = make_repo(self.dir / "repo-a")
        self.base_a = commit(self.repo_a, "base-a")
        self.repo_b = make_repo(self.dir / "repo-b")
        self.base_b = commit(self.repo_b, "base-b")
        self.state_dir = self.dir / "cron"
        self.state_dir.mkdir()
        self.state = self.state_dir / "orchestrator_board_check_state.json"
        self.settings = {
            "board": "example-board",
            "db": str(self.board.path),
            "orchestrator_profile": "example-orchestrator",
            "reviewer_profile": REVIEWER,
            "repositories": [str(self.repo_a), str(self.repo_b)],
            "main_branch": "main",
            "state_file": str(self.state),
            "stale_after_seconds": 2 * HOUR,
            "report_again_seconds": 12 * HOUR,
            "approved_lookback_seconds": 7 * 24 * HOUR,
        }
        self.config = self.dir / "settings.json"
        self.write_settings()

    def write_settings(self, settings=None):
        self.config.write_text(json.dumps(self.settings if settings is None else settings))

    def run_check(self, now=NOW):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check.main(["--config", str(self.config), "--now", str(now)])
        self.assertEqual(err.getvalue(), "")
        return code, out.getvalue().splitlines()

    def findings(self, now=NOW):
        """Run with no state file and return the finding lines after the header."""
        if self.state.exists():
            self.state.unlink()
        code, out = self.run_check(now)
        self.assertEqual(code, 0)
        if out == [WAKE_FALSE]:
            return []
        self.assertEqual(out[0], HEADER, out)
        return out[1:]

    def side_commit(self, repo, name, message=None):
        """Commit on a branch that is not merged into main; return the commit."""
        git(repo, "checkout", "-q", "-b", "side-" + name, "main")
        sha = commit(repo, name, message)
        git(repo, "checkout", "-q", "main")
        return sha

    def approved(self, task_id, candidate, **run):
        self.board.card(task_id, "done", "Approved " + task_id)
        self.board.run(task_id, metadata={"candidate_commit": candidate}, **run)

    # NO-WAKE-SUBSCRIPTION

    def test_open_card_without_wake_subscription_is_reported_and_covered_card_is_not(self):
        self.board.card("t_0001", "running", "Covered")
        self.board.card("t_0002", "review", "Notify only", assignee=None, wake=False)
        self.board.sub("t_0002", "notify", "example-orchestrator", "example-user")
        self.board.card("t_0003", "ready", "Empty notifier", wake=False)
        self.board.sub("t_0003", "notify+wake", "", "example-user")
        self.board.card("t_0004", "done", "Done without subscription", wake=False)
        self.board.card("t_0005", "archived", "Archived without subscription", wake=False)
        self.assertEqual(self.findings(), [
            "NO-WAKE-SUBSCRIPTION t_0002 review - Notify only",
            "NO-WAKE-SUBSCRIPTION t_0003 ready example-worker Empty notifier",
        ])

    def test_wake_rule_is_the_same_as_check_notify_subscriptions(self):
        notify_check = load("check_notify_subscriptions_for_board_check", NOTIFY_CHECK)
        self.assertEqual(check.WAKING_CARDS_SQL, notify_check.WAKING_CARDS_SQL)
        self.assertEqual(check.OPEN_CARDS_SQL, notify_check.OPEN_CARDS_SQL)
        self.assertEqual(check.CLOSED_STATUSES, notify_check.CLOSED_STATUSES)

    # APPROVED-NOT-INTEGRATED

    def test_approved_candidate_not_on_main_is_reported(self):
        candidate = self.side_commit(self.repo_a, "feature")
        self.approved("t_0010", candidate)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0010 done example-worker Approved t_0010 commit {candidate}"])

    def test_candidate_integrated_by_ancestry_is_not_reported(self):
        candidate = self.side_commit(self.repo_a, "feature")
        git(self.repo_a, "merge", "-q", "--ff-only", "side-feature")
        self.approved("t_0011", candidate)
        self.assertEqual(self.findings(), [])

    def test_candidate_integrated_by_cherry_pick_line_is_not_reported(self):
        candidate = self.side_commit(self.repo_a, "picked")
        git(self.repo_a, "cherry-pick", "-x", candidate)
        self.assertNotEqual(subprocess.run(
            ["git", "-C", str(self.repo_a), "merge-base", "--is-ancestor", candidate, "main"]).returncode, 0)
        self.approved("t_0012", candidate)
        self.assertEqual(self.findings(), [])

    def test_cherry_pick_line_without_the_commit_object_counts_as_integrated(self):
        candidate = "c" * 40
        commit(self.repo_a, "picked-elsewhere", f"Picked\n\n(cherry picked from commit {candidate})")
        self.approved("t_0013", candidate)
        self.assertEqual(self.findings(), [])

    def test_candidate_integrated_in_second_listed_repository_is_not_reported(self):
        candidate = commit(self.repo_b, "second-repo-change")
        self.approved("t_0014", candidate)
        self.assertEqual(self.findings(), [])

    def test_candidate_in_no_listed_repository_is_reported_as_not_found(self):
        candidate = "0123456789abcdef0123456789abcdef01234567"
        self.approved("t_0015", candidate)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0015 done example-worker Approved t_0015 commit {candidate}"
            " (commit not found)"])

    def test_candidate_that_is_not_40_hex_is_skipped(self):
        for number, value in enumerate(["none (card makes no commit)", "ABCDEF" + "0" * 34, "abc1234", 12]):
            task_id = f"t_002{number}"
            self.board.card(task_id, "done", "Skipped")
            self.board.run(task_id, metadata={"candidate_commit": value})
        self.board.card("t_0029", "done", "No metadata")
        self.board.run("t_0029", metadata=None)
        self.board.card("t_0030", "done", "Metadata not JSON")
        self.board.run("t_0030", metadata="not json")
        self.assertEqual(self.findings(), [])

    def test_review_older_than_lookback_is_skipped(self):
        candidate = self.side_commit(self.repo_a, "old")
        self.approved("t_0031", candidate, ended_at=NOW - 7 * 24 * HOUR - 1)
        self.assertEqual(self.findings(), [])
        self.board.conn.execute("UPDATE task_runs SET ended_at = ? WHERE task_id = 't_0031'",
                                (NOW - 7 * 24 * HOUR,))
        self.board.conn.commit()
        self.assertEqual(len(self.findings()), 1)

    def test_first_present_metadata_key_is_used(self):
        not_on_main = self.side_commit(self.repo_a, "first-key")
        on_main = commit(self.repo_a, "on-main")
        self.board.card("t_0032", "done", "Candidate key first")
        self.board.run("t_0032", metadata={"commit": on_main, "candidate": on_main,
                                           "candidate_commit": not_on_main})
        self.board.card("t_0033", "done", "Candidate before commit")
        self.board.run("t_0033", metadata={"commit": on_main, "candidate": not_on_main})
        self.board.card("t_0034", "done", "First present key is not hex")
        self.board.run("t_0034", metadata={"candidate_commit": "none", "commit": not_on_main})
        self.board.card("t_0035", "done", "Only commit key")
        self.board.run("t_0035", metadata={"commit": not_on_main})
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0032 done example-worker Candidate key first commit {not_on_main}",
            f"APPROVED-NOT-INTEGRATED t_0033 done example-worker Candidate before commit commit {not_on_main}",
            f"APPROVED-NOT-INTEGRATED t_0035 done example-worker Only commit key commit {not_on_main}",
        ])

    def test_only_the_latest_completed_reviewer_run_of_a_done_card_counts(self):
        candidate = self.side_commit(self.repo_a, "runs")
        self.board.card("t_0040", "done", "Later reviewer run blocked")
        self.board.run("t_0040", metadata={"candidate_commit": candidate})
        self.board.run("t_0040", outcome="blocked", metadata={"candidate_commit": candidate})
        self.board.card("t_0041", "done", "Worker run only")
        self.board.run("t_0041", profile="example-worker", metadata={"candidate_commit": candidate})
        self.board.card("t_0042", "running", "Not done")
        self.board.run("t_0042", metadata={"candidate_commit": candidate})
        self.board.card("t_0043", "done", "Later worker run")
        self.board.run("t_0043", metadata={"candidate_commit": candidate})
        self.board.run("t_0043", profile="example-worker", outcome="crashed")
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0043 done example-worker Later worker run commit {candidate}"])

    # APPROVED-NOT-INTEGRATED: tree comparison for squash merges and rebase merges

    def tree(self, repo, rev):
        return git(repo, "rev-parse", rev + "^{tree}")

    def assert_not_ancestor_and_no_cherry_pick_line(self, repo, candidate, branch="main"):
        self.assertEqual(subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", candidate, branch]).returncode, 1)
        self.assertEqual(git(repo, "log", "--format=%H", "--fixed-strings",
                             "--grep=cherry picked from commit " + candidate, branch), "")

    def squash_merge(self, repo, branch, message, extra_file=None):
        """Squash-merge branch into the checked-out branch as one new commit; return it."""
        git(repo, "merge", "-q", "--squash", branch)
        if extra_file:
            (repo / extra_file).write_text(extra_file + "\n")
            git(repo, "add", extra_file)
        git(repo, "commit", "-q", "-m", message)
        return git(repo, "rev-parse", "HEAD")

    def copy_commit(self, repo, source, message):
        """Apply source's change as a new commit with another message (no cherry-pick line)."""
        git(repo, "cherry-pick", "--no-commit", source)
        git(repo, "commit", "-q", "-m", message)
        return git(repo, "rev-parse", "HEAD")

    def test_squash_merge_with_the_candidate_tree_is_not_reported(self):
        git(self.repo_a, "checkout", "-q", "-b", "side-squash", "main")
        commit(self.repo_a, "squash-part-1")
        candidate = commit(self.repo_a, "squash-part-2")
        git(self.repo_a, "checkout", "-q", "main")
        squashed = self.squash_merge(self.repo_a, "side-squash", "Squash merge of side-squash")
        self.assertEqual(git(self.repo_a, "rev-parse", squashed + "^"), self.base_a)
        self.assertEqual(self.tree(self.repo_a, squashed), self.tree(self.repo_a, candidate))
        self.assert_not_ancestor_and_no_cherry_pick_line(self.repo_a, candidate)
        self.approved("t_0200", candidate)
        refs_before = ref_snapshot(self.repo_a)
        self.assertEqual(self.findings(), [])
        self.assertEqual(ref_snapshot(self.repo_a), refs_before)

    def test_squash_merge_with_a_different_tree_is_reported(self):
        # The branch reference received another change before the squash merge.
        after_change = self.side_commit(self.repo_a, "approved-before-main-moved")
        commit(self.repo_a, "other-change-on-main")
        self.squash_merge(self.repo_a, "side-approved-before-main-moved", "Squash after main moved")
        # The squash merge commit itself contains one more file.
        with_extra = self.side_commit(self.repo_a, "approved-then-extended")
        self.squash_merge(self.repo_a, "side-approved-then-extended", "Squash with extra file",
                          extra_file="extra-in-squash")
        log_trees = git(self.repo_a, "log", "--format=%T", "main").split()
        for candidate in (after_change, with_extra):
            self.assert_not_ancestor_and_no_cherry_pick_line(self.repo_a, candidate)
            self.assertNotIn(self.tree(self.repo_a, candidate), log_trees)
        self.approved("t_0201", after_change)
        self.approved("t_0202", with_extra)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0201 done example-worker Approved t_0201 commit {after_change}",
            f"APPROVED-NOT-INTEGRATED t_0202 done example-worker Approved t_0202 commit {with_extra}",
        ])

    def test_rebase_merge_with_the_candidate_tree_is_not_reported(self):
        git(self.repo_a, "checkout", "-q", "-b", "side-rebase", "main")
        first = commit(self.repo_a, "rebase-part-1")
        candidate = commit(self.repo_a, "rebase-part-2")
        git(self.repo_a, "checkout", "-q", "main")
        rewritten_first = self.copy_commit(self.repo_a, first, "rebase-part-1 (rewritten)")
        rewritten = self.copy_commit(self.repo_a, candidate, "rebase-part-2 (rewritten)")
        commit(self.repo_a, "later-change-on-main")
        self.assertNotEqual(rewritten_first, first)
        self.assertNotEqual(rewritten, candidate)
        self.assertEqual(self.tree(self.repo_a, rewritten), self.tree(self.repo_a, candidate))
        self.assert_not_ancestor_and_no_cherry_pick_line(self.repo_a, candidate)
        self.assert_not_ancestor_and_no_cherry_pick_line(self.repo_a, first)
        self.approved("t_0203", candidate)
        self.approved("t_0204", first)
        self.assertEqual(self.findings(), [])

    def test_same_tree_reachable_only_through_a_second_parent_is_reported(self):
        candidate = self.side_commit(self.repo_a, "second-parent")
        git(self.repo_a, "checkout", "-q", "-b", "side-merged", self.base_a)
        self.copy_commit(self.repo_a, candidate, "copy of second-parent")
        commit(self.repo_a, "more-on-side-merged")
        git(self.repo_a, "checkout", "-q", "main")
        git(self.repo_a, "merge", "-q", "--no-ff", "-m", "Merge side-merged", "side-merged")
        candidate_tree = self.tree(self.repo_a, candidate)
        self.assertIn(candidate_tree, git(self.repo_a, "log", "--format=%T", self.base_a + "..main").split())
        self.assertNotIn(candidate_tree, git(self.repo_a, "log", "--first-parent", "--format=%T",
                                             self.base_a + "..main").split())
        self.assert_not_ancestor_and_no_cherry_pick_line(self.repo_a, candidate)
        self.approved("t_0205", candidate)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0205 done example-worker Approved t_0205 commit {candidate}"])

    def test_candidate_without_common_ancestor_is_reported_even_with_an_equal_tree(self):
        git(self.repo_a, "checkout", "-q", "--orphan", "unrelated")
        git(self.repo_a, "commit", "-q", "-m", "Unrelated history with the same files")
        candidate = git(self.repo_a, "rev-parse", "HEAD")
        git(self.repo_a, "checkout", "-q", "main")
        self.assertEqual(self.tree(self.repo_a, candidate), self.tree(self.repo_a, "main"))
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo_a), "merge-base", candidate, "main"],
                                        capture_output=True).returncode, 1)
        self.approved("t_0206", candidate)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0206 done example-worker Approved t_0206 commit {candidate}"])

    def test_squash_merge_onto_remote_tracking_override_is_not_reported(self):
        repo_c = self.remote_tracking_repo("repo-c")
        self.settings["repositories"] = [str(self.repo_a), str(repo_c)]
        self.settings["repository_branches"] = {str(repo_c): "origin/main"}
        self.write_settings()
        git(repo_c, "checkout", "-q", "-b", "side-squashed", "origin/main")
        squashed_candidate = commit(repo_c, "squashed-feature")
        git(repo_c, "checkout", "-q", "-b", "side-open", "origin/main")
        open_candidate = commit(repo_c, "open-feature")
        git(repo_c, "checkout", "-q", "-b", "integration", "origin/main")
        self.squash_merge(repo_c, "side-squashed", "Squash merge of side-squashed")
        git(repo_c, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(repo_c, "checkout", "-q", "work")
        self.assert_not_ancestor_and_no_cherry_pick_line(repo_c, squashed_candidate, "origin/main")
        self.approved("t_0207", squashed_candidate)
        self.approved("t_0208", open_candidate)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0208 done example-worker Approved t_0208 commit {open_candidate}"])

    def test_failing_tree_comparison_git_command_prints_one_error_line(self):
        candidate = self.side_commit(self.repo_a, "synthetic-failure")
        self.approved("t_0210", candidate)
        real_run_git = check.run_git
        cases = [
            ("rev-parse", lambda args: args[0] == "rev-parse"),
            ("merge-base", lambda args: args[0] == "merge-base" and "--is-ancestor" not in args),
            ("log", lambda args: args[0] == "log" and "--first-parent" in args),
        ]
        for command, matches in cases:
            with self.subTest(command=command):
                calls = []

                def fake_run_git(repository, *args, matches=matches, calls=calls):
                    if matches(args):
                        calls.append(args)
                        return 128, ""
                    return real_run_git(repository, *args)

                with mock.patch.object(check, "run_git", side_effect=fake_run_git):
                    line = self.assert_error()
                self.assertEqual(len(calls), 1, calls)
                self.assertEqual(line, f"Board check error: git {command} failed in {self.repo_a} (exit 128)")

    # STALE-BLOCKED and STALE-REVIEW

    def test_old_blocked_and_review_cards_are_reported(self):
        old = NOW - 2 * HOUR - 1
        self.board.card("t_0050", "blocked", "Old blocked", created_at=old)
        self.board.card("t_0051", "review", "Old review", created_at=old - 100, assignee="example-reviewer")
        self.board.event("t_0051", old)
        self.board.card("t_0052", "running", "Old running", created_at=old)
        self.board.card("t_0053", "blocked", "Exactly at the limit", created_at=NOW - 2 * HOUR)
        self.assertEqual(self.findings(), [  # ordered by card created_at
            "STALE-REVIEW t_0051 review example-reviewer Old review",
            "STALE-BLOCKED t_0050 blocked example-worker Old blocked",
        ])

    def test_recent_comment_or_event_keeps_a_card_from_being_stale(self):
        old = NOW - 10 * HOUR
        self.board.card("t_0060", "blocked", "Recent comment", created_at=old)
        self.board.comment("t_0060", NOW - 60)
        self.board.event("t_0060", old)
        self.board.card("t_0061", "blocked", "Recent event", created_at=old)
        self.board.event("t_0061", NOW - 60)
        self.board.card("t_0062", "review", "Recent review event", created_at=old)
        self.board.event("t_0062", NOW - 60)
        self.board.card("t_0063", "blocked", "Old activity only", created_at=old)
        self.board.comment("t_0063", old + 1)
        self.board.event("t_0063", old + 2)
        self.assertEqual(self.findings(), ["STALE-BLOCKED t_0063 blocked example-worker Old activity only"])

    def test_title_is_printed_on_one_line(self):
        self.board.card("t_0070", "todo", "Two\nlines\tof title", assignee=None, wake=False)
        self.assertEqual(self.findings(), ["NO-WAKE-SUBSCRIPTION t_0070 todo - Two lines of title"])

    # Repeat control

    def read_state(self):
        return json.loads(self.state.read_text())["reported"]

    def test_repeat_control_reports_once_per_interval_and_drops_resolved_keys(self):
        self.board.card("t_0080", "running", "No wake", wake=False)
        self.board.card("t_0081", "blocked", "Old blocked", created_at=NOW - 3 * HOUR)
        first = [HEADER, "NO-WAKE-SUBSCRIPTION t_0080 running example-worker No wake",
                 "STALE-BLOCKED t_0081 blocked example-worker Old blocked"]
        self.assertEqual(self.run_check(NOW), (0, first))
        self.assertEqual(self.read_state(), {"NO-WAKE-SUBSCRIPTION:t_0080": NOW, "STALE-BLOCKED:t_0081": NOW})

        self.assertEqual(self.run_check(NOW + 12 * HOUR - 1), (0, [WAKE_FALSE]))
        self.assertEqual(self.read_state(), {"NO-WAKE-SUBSCRIPTION:t_0080": NOW, "STALE-BLOCKED:t_0081": NOW})

        later = NOW + 12 * HOUR
        self.assertEqual(self.run_check(later), (0, first))
        self.assertEqual(self.read_state(), {"NO-WAKE-SUBSCRIPTION:t_0080": later, "STALE-BLOCKED:t_0081": later})

        # t_0081 gets a comment, so its finding is resolved; a new finding for t_0082 appears.
        self.board.comment("t_0081", later + 10)
        self.board.card("t_0082", "ready", "New gap", wake=False)
        self.assertEqual(self.run_check(later + 20), (0, [
            HEADER, "NO-WAKE-SUBSCRIPTION t_0080 running example-worker No wake",
            "NO-WAKE-SUBSCRIPTION t_0082 ready example-worker New gap"]))
        self.assertEqual(self.read_state(), {"NO-WAKE-SUBSCRIPTION:t_0080": later,
                                             "NO-WAKE-SUBSCRIPTION:t_0082": later + 20})

        self.board.sub("t_0080", *WAKE)
        self.board.sub("t_0082", *WAKE)
        self.assertEqual(self.run_check(later + 30), (0, [WAKE_FALSE]))
        self.assertEqual(self.read_state(), {})

    def test_no_finding_prints_only_the_wake_line_and_leaves_no_temporary_file(self):
        self.board.card("t_0090", "running", "Covered")
        self.assertEqual(self.run_check(), (0, [WAKE_FALSE]))
        self.state.write_text(json.dumps({"reported": {"STALE-REVIEW:t_gone": NOW - 1}}))
        self.assertEqual(self.run_check(), (0, [WAKE_FALSE]))
        self.assertEqual(self.read_state(), {})
        self.assertEqual(sorted(p.name for p in self.state_dir.iterdir()), [self.state.name])

    # Errors

    def assert_error(self):
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("Board check error:"), out)
        self.assertNotIn("wakeAgent", out[0])
        return out[0]

    def test_missing_database_prints_error_and_creates_no_file(self):
        missing = self.dir / "absent" / "kanban.db"
        self.settings["db"] = str(missing)
        self.write_settings()
        self.assertIn("database file not found", self.assert_error())
        self.assertFalse(missing.parent.exists())
        self.assertFalse(self.state.exists())

    def test_database_without_needed_table_prints_error(self):
        self.board.conn.execute("DROP TABLE task_comments")
        self.board.conn.commit()
        self.assert_error()

    def test_settings_with_missing_key_prints_error(self):
        for key in list(self.settings):
            settings = dict(self.settings)
            del settings[key]
            self.write_settings(settings)
            self.assertIn(key, self.assert_error())

    def test_settings_with_wrong_type_prints_error(self):
        for key, value in [("board", 5), ("repositories", "/tmp/repo"), ("repositories", ["relative"]),
                           ("repositories", []), ("stale_after_seconds", "7200"),
                           ("report_again_seconds", True), ("db", "relative.db"),
                           ("main_branch", "--output=x")]:
            self.write_settings(dict(self.settings, **{key: value}))
            self.assertIn(key, self.assert_error())

    def test_missing_or_invalid_settings_file_prints_error(self):
        self.config.unlink()
        self.assert_error()
        self.config.write_text("{not json")
        self.assert_error()

    def test_git_error_prints_error(self):
        self.approved("t_0100", "b" * 40)
        not_a_repo = self.dir / "not-a-repo"
        not_a_repo.mkdir()
        self.settings["repositories"] = [str(not_a_repo)]
        self.write_settings()
        self.assertIn("not-a-repo", self.assert_error())
        self.settings["repositories"] = [str(self.repo_a)]
        self.settings["main_branch"] = "trunk"
        self.write_settings()
        self.assertIn("trunk", self.assert_error())

    # repository_branches

    def remote_tracking_repo(self, name):
        """Make a repository that has refs/remotes/origin/main and no local branch main."""
        repo = make_repo(self.dir / name)
        commit(repo, "base-" + name)
        git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(repo, "checkout", "-q", "-b", "work")
        git(repo, "branch", "-q", "-D", "main")
        self.assertNotEqual(subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "refs/heads/main"],
            capture_output=True).returncode, 0)
        return repo

    def test_override_with_remote_tracking_reference_counts_ancestry_and_cherry_pick_line(self):
        repo_c = self.remote_tracking_repo("repo-c")
        self.settings["repositories"] = [str(self.repo_a), str(repo_c)]
        self.settings["repository_branches"] = {str(repo_c): "origin/main"}
        self.write_settings()

        git(repo_c, "checkout", "-q", "-b", "side-ancestor", "origin/main")
        by_ancestry = commit(repo_c, "ancestor")
        git(repo_c, "update-ref", "refs/remotes/origin/main", by_ancestry)

        git(repo_c, "checkout", "-q", "-b", "side-picked", "origin/main")
        by_cherry_pick = commit(repo_c, "picked")
        git(repo_c, "checkout", "-q", "-b", "integration", "origin/main")
        git(repo_c, "cherry-pick", "-x", by_cherry_pick)
        git(repo_c, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertNotEqual(subprocess.run(
            ["git", "-C", str(repo_c), "merge-base", "--is-ancestor", by_cherry_pick, "origin/main"]
        ).returncode, 0)

        git(repo_c, "checkout", "-q", "-b", "side-open", "origin/main")
        not_integrated = commit(repo_c, "open")
        git(repo_c, "checkout", "-q", "work")

        self.approved("t_0150", by_ancestry)
        self.approved("t_0151", by_cherry_pick)
        self.approved("t_0152", not_integrated)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0152 done example-worker Approved t_0152 commit {not_integrated}"])

    def test_repository_without_override_still_uses_main_branch(self):
        repo_c = self.remote_tracking_repo("repo-c")
        self.settings["repositories"] = [str(self.repo_a), str(repo_c)]
        self.settings["repository_branches"] = {str(repo_c): "origin/main"}
        self.write_settings()
        # In repo_a, origin/main contains the candidate and main does not, so the
        # candidate is integrated only if repo_a were checked against origin/main.
        candidate = self.side_commit(self.repo_a, "only-on-origin-main")
        git(self.repo_a, "update-ref", "refs/remotes/origin/main", candidate)
        on_main = commit(self.repo_a, "on-main-a")
        self.approved("t_0160", candidate)
        self.approved("t_0161", on_main)
        self.assertEqual(self.findings(), [
            f"APPROVED-NOT-INTEGRATED t_0160 done example-worker Approved t_0160 commit {candidate}"])

    def test_missing_override_reference_prints_error_naming_repository_and_reference(self):
        self.settings["repository_branches"] = {str(self.repo_b): "origin/main"}
        self.write_settings()
        self.approved("t_0170", self.base_a)
        line = self.assert_error()
        self.assertIn(str(self.repo_b), line)
        self.assertIn("origin/main", line)
        self.assertNotIn(str(self.repo_a) + " ", line)

    def test_invalid_repository_branches_prints_error(self):
        repo_a = str(self.repo_a)
        for value in [["origin/main"], "origin/main", 5, None,
                      {str(self.dir / "not-listed"): "origin/main"},
                      {repo_a + "/": "origin/main"},
                      {repo_a: ""},
                      {repo_a: 5},
                      {repo_a: "-x"},
                      {repo_a: "--output=x"}]:
            with self.subTest(value=value):
                self.write_settings(dict(self.settings, repository_branches=value))
                self.assertIn("repository_branches", self.assert_error())

    def test_invalid_state_file_prints_error(self):
        self.board.card("t_0110", "running", "No wake", wake=False)
        self.state.write_text("{not json")
        self.assert_error()
        self.assertEqual(self.state.read_text(), "{not json")

    # Read-only behaviour and output content

    def test_database_bytes_and_git_refs_are_unchanged_after_a_run(self):
        candidate = self.side_commit(self.repo_a, "readonly")
        picked = self.side_commit(self.repo_a, "readonly-picked")
        git(self.repo_a, "cherry-pick", "-x", picked)
        self.approved("t_0120", candidate)
        self.approved("t_0121", picked)
        self.approved("t_0122", commit(self.repo_b, "readonly-b"))
        self.approved("t_0123", "d" * 40)
        self.board.card("t_0124", "blocked", "Old", created_at=NOW - 3 * HOUR, wake=False)
        self.board.close()
        db_before = self.board.path.read_bytes()
        db_dir_before = sorted(p.name for p in self.dir.iterdir())
        refs_before = [ref_snapshot(self.repo_a), ref_snapshot(self.repo_b)]
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(out[0], HEADER)
        self.assertEqual(len(out), 5, out)
        self.assertEqual(self.board.path.read_bytes(), db_before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), db_dir_before)
        self.assertEqual([ref_snapshot(self.repo_a), ref_snapshot(self.repo_b)], refs_before)
        self.board.conn = sqlite3.connect(self.board.path)

    def test_marker_in_body_comment_summary_and_metadata_never_appears_in_output(self):
        candidate = self.side_commit(self.repo_a, "marker")
        self.board.card("t_0130", "done", "Marker done", body=MARKER, wake=False)
        self.board.run("t_0130", summary=MARKER, metadata={"candidate_commit": candidate, "note": MARKER})
        self.board.card("t_0131", "blocked", "Marker blocked", body=MARKER, created_at=NOW - 3 * HOUR,
                        wake=False)
        self.board.comment("t_0131", NOW - 3 * HOUR, MARKER)
        self.board.event("t_0131", NOW - 3 * HOUR, MARKER)
        self.board.run("t_0131", profile="example-worker", summary=MARKER, outcome="blocked")
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(out, [
            HEADER,
            "NO-WAKE-SUBSCRIPTION t_0131 blocked example-worker Marker blocked",
            f"APPROVED-NOT-INTEGRATED t_0130 done example-worker Marker done commit {candidate}",
            "STALE-BLOCKED t_0131 blocked example-worker Marker blocked",
        ])
        self.assertNotIn(MARKER, "\n".join(out))
        self.assertNotIn(MARKER, self.state.read_text())

    def test_script_source_uses_read_only_database_and_only_the_listed_git_commands(self):
        source = SCRIPT.read_text()
        self.assertIn('"?mode=ro", uri=True', source)
        self.assertEqual(source.count("sqlite3.connect("), 1)
        for word in ("INSERT", "UPDATE", "DELETE", "CREATE", "fetch", "push", "os.system", "socket",
                     "urlopen", "shell=True"):
            self.assertIsNone(re.search(r"\b" + re.escape(word) + r"\b", source, re.IGNORECASE), word)
        self.assertEqual(source.count("subprocess.run("), 1)
        self.assertEqual(set(re.findall(r'run_git\(path, "([a-z-]+)"', source)),
                         {"cat-file", "merge-base", "log", "rev-parse"})
        self.assertEqual(len(re.findall(r"run_git\(", source)), 8)  # definition and seven calls
        self.assertIn('"--fixed-strings"', source)
        self.assertIn('"--is-ancestor"', source)
        self.assertIn('"--first-parent"', source)
        self.assertIn("os.replace(", source)

    # Deployment layout and settings files

    def test_script_is_executable_and_reads_settings_next_to_itself_without_arguments(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        self.assertTrue(SCRIPT.read_text().startswith("#!/usr/bin/env python3\n"))
        scripts = self.dir / "profile-home" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(SCRIPT, scripts / "orchestrator_board_check.py")
        (scripts / "orchestrator_board_check.json").write_text(json.dumps(self.settings))
        self.board.card("t_0140", "running", "Covered")
        result = subprocess.run([sys.executable, str(scripts / "orchestrator_board_check.py")],
                                capture_output=True, text=True, cwd=str(self.dir), check=False)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, WAKE_FALSE + "\n", ""))
        (scripts / "orchestrator_board_check.json").unlink()
        result = subprocess.run([sys.executable, str(scripts / "orchestrator_board_check.py")],
                                capture_output=True, text=True, cwd=str(self.dir), check=False)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith("Board check error:"), result.stdout)
        self.assertIn("orchestrator_board_check.json", result.stdout)


PRIMARY = "example-primary"
FALLBACK = "example-fallback"
SESSION_TAG = "20270115_000000_abcd12"


def local_text(epoch):
    return time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(epoch))


def log_record(epoch, model, provider, *, old_model="example-old-model", milliseconds=0,
               session=SESSION_TAG, logger="agent.chat_completion_helpers", level="INFO"):
    """One synthetic agent.log line in the Hermes default format; holds no message text."""
    tag = f" [{session}]" if session else ""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))
    return (f"{stamp},{milliseconds:03d} {level}{tag} {logger}: "
            f"Fallback activated: {old_model} \u2192 {model} ({provider})")


def other_record(epoch, text):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))
    return f"{stamp},000 INFO [{SESSION_TAG}] agent.example: {text}"


class ProfileHome:
    """A temporary profile home with a state.db usage table and agent.log files only."""

    def __init__(self, path):
        self.path = path
        (path / "logs").mkdir(parents=True)
        self.db = path / "state.db"

    def usage_table(self):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE IF NOT EXISTS session_model_usage (session_id TEXT NOT NULL,"
                     " model TEXT NOT NULL, billing_provider TEXT NOT NULL DEFAULT '',"
                     " billing_base_url TEXT NOT NULL DEFAULT '', billing_mode TEXT NOT NULL DEFAULT '',"
                     " task TEXT NOT NULL DEFAULT '', api_call_count INTEGER NOT NULL DEFAULT 0,"
                     " first_seen REAL, last_seen REAL)")
        conn.commit()
        return conn

    def route(self, provider, model, last_seen, *, task="", session="example-session"):
        conn = self.usage_table()
        conn.execute("INSERT INTO session_model_usage (session_id, model, billing_provider, task,"
                     " api_call_count, first_seen, last_seen) VALUES (?, ?, ?, ?, 1, ?, ?)",
                     (session, model, provider, task, last_seen - 60, last_seen))
        conn.commit()
        conn.close()

    def log(self, name, lines, mtime=NOW):
        path = self.path / "logs" / name
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path


class ProviderWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.board = Board(self.dir / "kanban.db")
        self.addCleanup(self.board.close)
        self.state = self.dir / "cron" / "orchestrator_board_check_state.json"
        self.state.parent.mkdir()
        self.homes = {name: ProfileHome(self.dir / "profiles" / name)
                      for name in ("example-a", "example-b")}
        self.settings = {
            "board": "example-board",
            "db": str(self.board.path),
            "orchestrator_profile": "example-orchestrator",
            "reviewer_profile": REVIEWER,
            "repositories": [str(self.dir / "no-repository-is-read")],
            "main_branch": "main",
            "state_file": str(self.state),
            "stale_after_seconds": 2 * HOUR,
            "report_again_seconds": 12 * HOUR,
            "approved_lookback_seconds": 7 * 24 * HOUR,
            "provider_watch": [{"profile": name, "home": str(home.path), "primary_provider": PRIMARY}
                               for name, home in self.homes.items()],
        }
        self.config = self.dir / "settings.json"
        self.write_settings()

    def write_settings(self, settings=None):
        self.config.write_text(json.dumps(self.settings if settings is None else settings))

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check.main(["--config", str(self.config), *args])
        self.assertEqual((code, err.getvalue()), (0, ""))
        return out.getvalue().splitlines()

    def run_check(self, now=NOW):
        return self.main("--now", str(now))

    def status(self):
        return self.main("--status")

    # Primary, fallback and no evidence

    def test_primary_route_in_database_is_primary_and_wakes_nobody(self):
        self.homes["example-a"].route(PRIMARY, "example-model", NOW - 600)
        self.homes["example-a"].route(FALLBACK, "example-fallback-model", NOW - 900)
        self.homes["example-b"].route(PRIMARY.upper(), "example-model", NOW - 300)
        self.assertEqual(self.run_check(), [WAKE_FALSE])
        self.assertEqual(self.status(), [f"example-a: primary {PRIMARY}",
                                         f"example-b: primary {PRIMARY.upper()}"])

    def test_fallback_route_in_database_is_a_finding_and_a_status_line(self):
        self.homes["example-a"].route(PRIMARY, "example-model", NOW - 900)
        self.homes["example-a"].route(FALLBACK, "example-fallback-model", NOW - 600.5)
        self.homes["example-b"].route(PRIMARY, "example-model", NOW - 300)
        self.assertEqual(self.run_check(), [
            HEADER, f"ON-FALLBACK example-a: {FALLBACK}/example-fallback-model at {local_text(NOW - 601)}"])
        self.assertEqual(json.loads(self.state.read_text()), {"reported": {"ON-FALLBACK:example-a": NOW}})
        self.assertEqual(self.status(), [
            f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 601)}",
            f"example-b: primary {PRIMARY}"])

    def test_auxiliary_task_rows_and_rows_without_provider_are_not_evidence(self):
        home = self.homes["example-a"]
        home.route(PRIMARY, "example-model", NOW - 900)
        home.route(FALLBACK, "example-compression-model", NOW - 60, task="compression")
        home.route("", "unknown", NOW - 30)
        self.assertEqual(self.status()[0], f"example-a: primary {PRIMARY}")
        self.assertEqual(self.run_check(), [WAKE_FALSE])

    def test_fallback_log_record_newer_than_the_database_route_is_fallback(self):
        home = self.homes["example-a"]
        home.route(PRIMARY, "example-model", NOW - 900)
        home.log("agent.log", [log_record(NOW - 120, "example-fallback-model", FALLBACK, milliseconds=250)])
        self.assertEqual(self.status()[0],
                         f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 120)}")
        self.assertEqual(self.run_check()[1:], [
            f"ON-FALLBACK example-a: {FALLBACK}/example-fallback-model at {local_text(NOW - 120)}"])

    def test_primary_call_after_the_fallback_log_record_is_primary_again(self):
        # The next turn restores the primary provider; its call is newer than the record.
        home = self.homes["example-a"]
        home.log("agent.log", [log_record(NOW - 900, "example-fallback-model", FALLBACK)])
        home.route(FALLBACK, "example-fallback-model", NOW - 850)
        home.route(PRIMARY, "example-model", NOW - 60)
        self.assertEqual(self.status()[0], f"example-a: primary {PRIMARY}")
        self.assertEqual(self.run_check(), [WAKE_FALSE])

    def test_log_record_without_a_database_is_fallback(self):
        self.homes["example-a"].log("agent.log", [log_record(NOW - 30, "example-fallback-model", FALLBACK,
                                                             session="")])
        self.assertEqual(self.status()[0],
                         f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 30)}")

    def test_no_evidence(self):
        home = self.homes["example-a"]
        home.usage_table().close()
        home.log("agent.log", [
            other_record(NOW - 50, "Primary runtime restored for new turn: example-model (example-primary)"),
            other_record(NOW - 40, f"Fallback activated after empty responses: now using x on {FALLBACK}"),
            log_record(NOW - 30, "example-fallback-model", FALLBACK, level="WARNING"),
            log_record(NOW - 20, "example-fallback-model", FALLBACK, logger="agent.other_module"),
            log_record(NOW - 10, "model with spaces", FALLBACK),
            "  " + log_record(NOW - 5, "example-fallback-model", FALLBACK),
        ])
        shutil.rmtree(self.homes["example-b"].path)
        self.assertEqual(self.status(), ["example-a: no evidence", "example-b: no evidence"])
        self.assertEqual(self.run_check(), [WAKE_FALSE])
        self.assertFalse(self.homes["example-b"].path.exists())

    def test_settings_without_provider_watch_behave_as_before(self):
        del self.settings["provider_watch"]
        self.write_settings()
        self.assertEqual(self.run_check(), [WAKE_FALSE])
        self.assertEqual(self.status(), ["No profile is listed in settings key provider_watch."])

    # Unreadable database or log

    def test_unreadable_database_is_a_board_check_error_and_a_status_error_line(self):
        home = self.homes["example-a"]
        home.db.write_bytes(b"not a database file " * 50)
        self.homes["example-b"].route(FALLBACK, "example-fallback-model", NOW - 60)
        out = self.run_check()
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"Board check error: cannot read database {home.db}:"), out)
        self.assertFalse(self.state.exists())
        status = self.status()
        self.assertEqual(len(status), 2, status)
        self.assertTrue(status[0].startswith(f"example-a: error cannot read database {home.db}:"), status)
        self.assertEqual(status[1], f"example-b: fallback {FALLBACK}/example-fallback-model"
                                    f" at {local_text(NOW - 60)}")

    def test_database_without_the_usage_table_is_an_error(self):
        conn = sqlite3.connect(self.homes["example-a"].db)
        conn.execute("CREATE TABLE sessions (id TEXT, model TEXT, billing_provider TEXT)")
        conn.commit()
        conn.close()
        out = self.run_check()
        self.assertEqual(len(out), 1, out)
        self.assertIn("session_model_usage", out[0])
        self.assertTrue(out[0].startswith("Board check error: cannot read database"), out)

    def test_unreadable_log_file_is_an_error(self):
        (self.homes["example-a"].path / "logs" / "agent.log").mkdir()
        out = self.run_check()
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("Board check error: cannot read log file"), out)

    # Rotated logs

    def test_record_in_a_rotated_log_is_found_when_newer_files_have_none(self):
        home = self.homes["example-a"]
        home.log("agent.log", [other_record(NOW - 10, "Example unrelated record")])
        home.log("agent.log.2", [log_record(NOW - 7200, "example-old-fallback", FALLBACK),
                                 log_record(NOW - 3600, "example-fallback-model", FALLBACK)])
        self.assertEqual(self.status()[0],
                         f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 3600)}")

    def test_newest_log_file_with_a_record_is_used_and_older_files_are_not_read(self):
        home = self.homes["example-a"]
        home.log("agent.log", [log_record(NOW - 300, "example-fallback-model", FALLBACK)])
        home.log("agent.log.1", [log_record(NOW - 30, "example-rotated-model", "example-rotated")])
        (home.path / "logs" / "agent.log.2").mkdir()  # would be an error if it were read
        self.assertEqual(self.status()[0],
                         f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 300)}")

    def test_log_files_older_than_the_database_route_are_not_read(self):
        home = self.homes["example-a"]
        home.route(PRIMARY, "example-model", NOW - 600)
        # The record text claims a later time, but the file was last written before the route.
        home.log("agent.log", [log_record(NOW - 60, "example-fallback-model", FALLBACK)], mtime=NOW - 601)
        (home.path / "logs" / "agent.log.1").mkdir()
        self.assertEqual(self.status()[0], f"example-a: primary {PRIMARY}")
        home.log("agent.log", [log_record(NOW - 60, "example-fallback-model", FALLBACK)], mtime=NOW - 59)
        self.assertEqual(self.status()[0],
                         f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 60)}")

    # Repeat control

    def test_on_fallback_repeats_after_12_hours_and_clears_when_primary_returns(self):
        home = self.homes["example-a"]
        home.route(FALLBACK, "example-fallback-model", NOW - 60)
        line = f"ON-FALLBACK example-a: {FALLBACK}/example-fallback-model at {local_text(NOW - 60)}"
        self.assertEqual(self.run_check(NOW), [HEADER, line])
        self.assertEqual(self.run_check(NOW + 12 * HOUR - 1), [WAKE_FALSE])
        self.assertEqual(self.run_check(NOW + 12 * HOUR), [HEADER, line])
        self.assertEqual(json.loads(self.state.read_text()),
                         {"reported": {"ON-FALLBACK:example-a": NOW + 12 * HOUR}})
        home.route(PRIMARY, "example-model", NOW + 12 * HOUR + 10, session="example-later-session")
        self.assertEqual(self.run_check(NOW + 12 * HOUR + 20), [WAKE_FALSE])
        self.assertEqual(json.loads(self.state.read_text()), {"reported": {}})
        # A new fallback is reported at once, together with the board findings.
        home.route(FALLBACK, "example-fallback-model", NOW + 12 * HOUR + 30, session="example-third")
        self.board.card("t_0300", "running", "No wake", wake=False)
        self.assertEqual(self.run_check(NOW + 12 * HOUR + 40), [
            HEADER, "NO-WAKE-SUBSCRIPTION t_0300 running example-worker No wake",
            f"ON-FALLBACK example-a: {FALLBACK}/example-fallback-model at {local_text(NOW + 12 * HOUR + 30)}"])

    # --status, read-only behaviour and output content

    def test_status_reads_neither_board_nor_state_file_and_writes_nothing(self):
        self.homes["example-a"].route(FALLBACK, "example-fallback-model", NOW - 60)
        self.homes["example-a"].log("agent.log", [log_record(NOW - 120, "example-fallback-model", FALLBACK)])
        self.settings["db"] = str(self.dir / "absent" / "kanban.db")
        self.write_settings()
        self.state.write_text("{not json")
        before = {p: p.read_bytes() for p in self.dir.rglob("*") if p.is_file()}
        self.assertEqual(self.status(), [
            f"example-a: fallback {FALLBACK}/example-fallback-model at {local_text(NOW - 60)}",
            "example-b: no evidence"])
        self.assertEqual({p: p.read_bytes() for p in self.dir.rglob("*") if p.is_file()}, before)

    def test_scheduled_run_leaves_profile_files_unchanged(self):
        home = self.homes["example-a"]
        home.route(FALLBACK, "example-fallback-model", NOW - 60)
        home.log("agent.log", [log_record(NOW - 120, "example-fallback-model", FALLBACK)])
        before = {p: p.read_bytes() for p in home.path.rglob("*") if p.is_file()}
        self.assertEqual(len(self.run_check()), 2)
        self.assertEqual({p: p.read_bytes() for p in home.path.rglob("*") if p.is_file()}, before)

    def test_only_time_provider_and_model_of_a_record_reach_the_output(self):
        home = self.homes["example-a"]
        home.log("agent.log", [
            other_record(NOW - 200, MARKER),
            log_record(NOW - 100, "example-fallback-model", FALLBACK, old_model="example-old-" + MARKER),
            other_record(NOW - 50, "Example record " + MARKER),
        ])
        out = self.run_check()
        self.assertEqual(out, [
            HEADER, f"ON-FALLBACK example-a: {FALLBACK}/example-fallback-model at {local_text(NOW - 100)}"])
        status = self.status()
        for text in ("\n".join(out), "\n".join(status), self.state.read_text()):
            self.assertNotIn(MARKER, text)
            self.assertNotIn(SESSION_TAG, text)
            self.assertNotIn("example-old", text)

    def test_database_query_reads_only_provider_model_and_last_seen(self):
        self.assertTrue(check.LATEST_ROUTE_SQL.startswith(
            "SELECT billing_provider, model, last_seen FROM session_model_usage WHERE task = ''"))
        for word in ("session_id", "message", "title", "content", "sessions "):
            self.assertNotIn(word, check.LATEST_ROUTE_SQL)

    # Settings

    def test_invalid_provider_watch_prints_error(self):
        entry = {"profile": "example-a", "home": str(self.homes["example-a"].path), "primary_provider": PRIMARY}
        for value in [{"example-a": entry}, "example-a", [["example-a"]], [dict(entry, extra="x")],
                      [{"profile": "example-a", "home": entry["home"]}], [dict(entry, profile="")],
                      [dict(entry, primary_provider=5)], [dict(entry, home="relative/home")],
                      [entry, dict(entry)]]:
            with self.subTest(value=value):
                self.write_settings(dict(self.settings, provider_watch=value))
                for args in ((), ("--status",)):
                    out = self.main(*args)
                    self.assertEqual(len(out), 1, out)
                    self.assertTrue(out[0].startswith("Board check error: settings key provider_watch"), out)


class SettingsFilesTests(unittest.TestCase):
    def test_each_settings_file_matches_roster_project_fleets(self):
        fleets = json.loads((ROOT / "roster.yaml").read_text())["project_fleets"]
        orchestrators = sorted(fleet["orchestrator"] for fleet in fleets.values())
        self.assertEqual(orchestrators, sorted(["harness-orchestrator", "jobcron-orchestrator",
                                                "chapt-orchestrator", "jss-orchestrator",
                                                "anki-orchestrator"]))
        self.assertEqual(sorted(p.name for p in SETTINGS_DIR.glob("*.json")),
                         sorted(name + ".json" for name in orchestrators))
        for fleet in fleets.values():
            orchestrator = fleet["orchestrator"]
            with self.subTest(orchestrator=orchestrator):
                settings = json.loads((SETTINGS_DIR / f"{orchestrator}.json").read_text())
                expected_branches = {}
                if orchestrator == "chapt-orchestrator":
                    expected_branches = {"repository_branches": {
                        "/Users/chanbla11mit/projects/cha-pt-frontend": "origin/main"}}
                expected_watch = {}
                if orchestrator == "jobcron-orchestrator":
                    profiles = [orchestrator, *fleet["workers"], fleet["reviewer"]]
                    self.assertEqual(profiles, ["jobcron-orchestrator", "jobcron-worker", "jobcron-worker-2",
                                                "jobcron-reviewer"])
                    expected_watch = {"provider_watch": [
                        {"profile": profile, "home": f"/Users/chanbla11mit/.hermes/profiles/{profile}",
                         "primary_provider": "claude-subscription"} for profile in profiles]}
                self.assertEqual(settings, {
                    **expected_branches,
                    **expected_watch,
                    "board": fleet["board"],
                    "db": f"/Users/chanbla11mit/.hermes/kanban/boards/{fleet['board']}/kanban.db",
                    "orchestrator_profile": orchestrator,
                    "reviewer_profile": fleet["reviewer"],
                    "repositories": fleet["repositories"],
                    "main_branch": "main",
                    "state_file": f"/Users/chanbla11mit/.hermes/profiles/{orchestrator}/cron/"
                                  "orchestrator_board_check_state.json",
                    "stale_after_seconds": 7200,
                    "report_again_seconds": 43200,
                    "approved_lookback_seconds": 604800,
                })
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "settings.json"
                    path.write_text(json.dumps(settings))
                    self.assertEqual(check.load_settings(str(path)), settings)


if __name__ == "__main__":
    unittest.main()
