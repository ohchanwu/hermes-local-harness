"""Offline tests for the GLM review section of scripts/jev-report (card C5).

Every database is made under a temporary directory. Card ids, profiles and
paths are synthetic. No live board database and no live settings file is
read: every run passes --kanban-db explicitly. The settings of the boards
come from a settings value given to build_report; only the command line test
reads plugins/jev/config.json of this checkout, which is a repository file.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/jev-report"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(module_spec)
    loader.exec_module(module)
    return module


report = load("jev_report_under_test_glm", SCRIPT)

NOW = 1_800_000_000
SENTINEL = "SENTINEL-CARD-TEXT-8c31af"
HEADER = "== GLM review (kanban databases of the boards with glm_reviewers) =="

GLM_REVIEWER = "harness-reviewer-glm"
OPUS_REVIEWER = "harness-reviewer"
GLM_WORKER = "harness-worker-glm-1"

BOARDS_CONFIG = {
    "routing": {
        "boards": {
            "harness": {
                "glm_reviewers": [GLM_REVIEWER],
                "opus_reviewer": OPUS_REVIEWER,
            },
            "jobcron": {
                "glm_reviewers": ["jobcron-reviewer-glm"],
                "opus_reviewer": "jobcron-reviewer",
            },
        }
    }
}

JOBCRON_ONLY_CONFIG = {"routing": {"boards": {
    "jobcron": {"glm_reviewers": ["jobcron-reviewer-glm"],
                "opus_reviewer": "jobcron-reviewer"}}}}


class Fixture:
    """A temporary board database under <tmp>/kanban/boards/<board>/kanban.db.

    Card rows carry only identifiers and times; run rows carry profile,
    started_at, ended_at and outcome; event rows carry the kind, the run and
    the payload, as Hermes writes them (changes_requested with reviewer in the
    payload, blocked with reason in the payload). A card spec is
    (task_id, runs, events): runs are (profile, started, ended, outcome)
    tuples in order and events are (kind, run_index, created, payload) tuples
    in order; run_index names the run of the card's runs list, None for a task
    scoped event (run_id NULL).
    """

    def __init__(self, tmp, board, specs):
        self.tmp = tmp
        self.board = board
        board_dir = os.path.join(tmp, "kanban", "boards", board)
        os.makedirs(board_dir)
        self.db = os.path.join(board_dir, "kanban.db")
        self.logs = os.path.join(tmp, "empty-logs")
        os.makedirs(self.logs, exist_ok=True)
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT,
                                status TEXT, workspace_path TEXT);
            CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                                    profile TEXT, status TEXT NOT NULL, started_at INTEGER NOT NULL,
                                    ended_at INTEGER, outcome TEXT, summary TEXT);
            CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                                      run_id INTEGER, kind TEXT NOT NULL, payload TEXT,
                                      created_at INTEGER NOT NULL);
        """)
        for task_id, runs, events in specs:
            conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                         (task_id, SENTINEL, SENTINEL, "done", f"/ws/{task_id}"))
            run_ids = []
            for profile, started, ended, outcome in runs:
                cur = conn.execute(
                    "INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, "
                    "outcome, summary) VALUES (?, ?, 'done', ?, ?, ?, ?)",
                    (task_id, profile, started, ended, outcome, SENTINEL))
                run_ids.append(cur.lastrowid)
            for kind, run_index, created, payload in events:
                run_id = run_ids[run_index] if run_index is not None else None
                conn.execute(
                    "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (task_id, run_id, kind, json.dumps(payload), created))
        conn.commit()
        conn.close()

    def text(self, **kwargs):
        return report.build_report(self.logs, 30, [self.db], [], now=NOW,
                                   jev_config=BOARDS_CONFIG, **kwargs)


def pass_reason():
    return "jev-glm-review-pass: candidate sent to harness-reviewer by the hold script"


def card_glm_change_request_pass_approval():
    """A card with a GLM change request, then a pass, then an Opus approval."""
    glm_change_run = (GLM_REVIEWER, NOW - 700, NOW - 600, "changes_requested")
    glm_pass_run = (GLM_REVIEWER, NOW - 500, NOW - 400, "blocked")
    opus_run = (OPUS_REVIEWER, NOW - 300, NOW - 200, "completed")
    events = [
        ("changes_requested", 0, NOW - 600, {"reviewer": GLM_REVIEWER,
                                             "implementer": GLM_WORKER}),
        ("blocked", 1, NOW - 400, {"reason": pass_reason(), "kind": "needs_input",
                                   "source_status": "review"}),
        ("unblocked", 1, NOW - 390, {"source_status": "review"}),
    ]
    return "t_glm_change", [glm_change_run, glm_pass_run, opus_run], events


def card_pass_then_opus_change_request():
    """A card with a pass, then an Opus change request."""
    glm_pass_run = (GLM_REVIEWER, NOW - 800, NOW - 700, "blocked")
    opus_run = (OPUS_REVIEWER, NOW - 600, NOW - 500, "changes_requested")
    events = [
        ("blocked", 0, NOW - 700, {"reason": pass_reason(), "kind": "needs_input",
                                   "source_status": "review"}),
        ("changes_requested", 1, NOW - 500, {"reviewer": OPUS_REVIEWER,
                                             "implementer": GLM_WORKER}),
    ]
    return "t_glm_opus_change", [glm_pass_run, opus_run], events


def card_pass_not_yet_reviewed():
    """A card with a pass and no Opus review run after it."""
    glm_pass_run = (GLM_REVIEWER, NOW - 200, NOW - 100, "blocked")
    events = [("blocked", 0, NOW - 100, {"reason": pass_reason(), "kind": "needs_input",
                                         "source_status": "review"})]
    return "t_glm_pending", [glm_pass_run], events


def card_worker_blocked_with_pass_reason():
    """A GLM worker card whose own run blocked with the pass reason."""
    worker_run = (GLM_WORKER, NOW - 900, NOW - 800, "blocked")
    events = [("blocked", 0, NOW - 800, {"reason": pass_reason(), "kind": "needs_input",
                                         "source_status": "ready"})]
    return "t_worker_block", [worker_run], events


def card_glm_change_request_only():
    """A card with one GLM review run that requested changes, and no pass."""
    glm_change_run = (GLM_REVIEWER, NOW - 950, NOW - 900, "changes_requested")
    events = [("changes_requested", 0, NOW - 900, {"reviewer": GLM_REVIEWER,
                                                   "implementer": GLM_WORKER})]
    return "t_glm_only", [glm_change_run], events


def card_worker_and_reviewer_pass():
    """A card whose GLM worker run and GLM review run both blocked with the
    pass reason: only the event of the GLM reviewer run is a pass."""
    worker_run = (GLM_WORKER, NOW - 900, NOW - 800, "blocked")
    glm_pass_run = (GLM_REVIEWER, NOW - 400, NOW - 300, "blocked")
    events = [
        ("blocked", 0, NOW - 800, {"reason": pass_reason(), "kind": "needs_input",
                                   "source_status": "ready"}),
        ("blocked", 1, NOW - 300, {"reason": pass_reason(), "kind": "needs_input",
                                   "source_status": "review"}),
    ]
    return "t_worker_and_reviewer", [worker_run, glm_pass_run], events


class GlmReviewSectionTests(unittest.TestCase):
    def test_cards_with_change_request_pass_and_each_opus_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_glm_change_request_pass_approval(),
                                               card_pass_then_opus_change_request(),
                                               card_pass_not_yet_reviewed(),
                                               card_glm_change_request_only()])
            text = fixture.text()
            self.assertIn(
                "  board harness: cards with at least one run by a GLM reviewer 4, "
                "change requests by a GLM reviewer 2, passes 3\n", text)
            self.assertIn(
                "    Opus reviewer first outcome after a pass: approved 1, "
                "changes requested 1, not yet reviewed 1\n", text)
            self.assertIn(HEADER, text)
            self.assertNotIn(SENTINEL, text)

    def test_pass_not_yet_reviewed_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_pass_not_yet_reviewed()])
            text = fixture.text()
            self.assertIn("  board harness: cards with at least one run by a GLM reviewer 1, "
                          "change requests by a GLM reviewer 0, passes 1\n", text)
            self.assertIn("    Opus reviewer first outcome after a pass: approved 0, "
                          "changes requested 0, not yet reviewed 1\n", text)

    def test_worker_blocked_event_with_pass_reason_is_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_worker_blocked_with_pass_reason(),
                                               card_worker_and_reviewer_pass()])
            text = fixture.text()
            # The blocked event of the GLM worker run is not a pass, so the
            # board counts the passes of the GLM review run only.
            self.assertIn("  board harness: cards with at least one run by a GLM reviewer 1, "
                          "change requests by a GLM reviewer 0, passes 1\n", text)
            self.assertIn("    Opus reviewer first outcome after a pass: approved 0, "
                          "changes requested 0, not yet reviewed 1\n", text)

    def test_events_outside_the_time_window_are_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_glm_change_request_pass_approval()])
            # --after later than every event and every run start of the card.
            text = fixture.text(after=NOW - 50)
            self.assertIn("  board harness: no GLM reviewer activity\n", text)

    def test_card_older_than_since_days_is_not_counted(self):
        old = NOW - 40 * 86400  # outside the 30 day window of Fixture.text
        old_card = ("t_glm_old",
                    [(GLM_REVIEWER, old - 200, old - 100, "changes_requested"),
                     (GLM_REVIEWER, old - 50, old, "blocked")],
                    [("changes_requested", 0, old - 100, {"reviewer": GLM_REVIEWER}),
                     ("blocked", 1, old, {"reason": pass_reason()})])
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [old_card, card_pass_not_yet_reviewed()])
            text = fixture.text()
            self.assertIn("  board harness: cards with at least one run by a GLM reviewer 1, "
                          "change requests by a GLM reviewer 0, passes 1\n", text)
            self.assertIn("    Opus reviewer first outcome after a pass: approved 0, "
                          "changes requested 0, not yet reviewed 1\n", text)

    def test_board_without_glm_reviewers_prints_no_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_glm_change_request_pass_approval()])
            text = report.build_report(fixture.logs, 30, [fixture.db], [], now=NOW,
                                       jev_config=JOBCRON_ONLY_CONFIG)
            self.assertIn(HEADER + "\n  no records\n", text)

    def test_board_database_without_glm_reviewer_activity_prints_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A board whose only GLM run is a GLM worker run that blocked with
            # the pass reason: no GLM reviewer activity, one line, no figures.
            fixture = Fixture(tmp, "harness", [card_worker_blocked_with_pass_reason()])
            text = fixture.text()
            self.assertIn("  board harness: no GLM reviewer activity\n", text)
            self.assertNotIn("Opus reviewer first outcome", text)

    def test_two_boards_are_printed_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = Fixture(tmp, "harness", [card_glm_change_request_pass_approval()])
            # A second board with the tables and no rows: one line, no figures.
            jobcron = Fixture(tmp, "jobcron", [])
            text = report.build_report(harness.logs, 30, [harness.db, jobcron.db], [],
                                       now=NOW, jev_config=BOARDS_CONFIG)
            self.assertIn("  board harness: cards with at least one run by a GLM reviewer 1, "
                          "change requests by a GLM reviewer 1, passes 1\n", text)
            self.assertIn("  board jobcron: no GLM reviewer activity\n", text)

    def test_existing_sections_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_glm_change_request_pass_approval()])
            write_logs(fixture.logs)
            with_glm = fixture.text()
            without_glm = report.build_report(fixture.logs, 30, [fixture.db], [], now=NOW,
                                              jev_config={"routing": {"boards": {}}})
            sections = split_sections(with_glm)
            self.assertEqual(list(sections), [
                "== Card model routing (decisions.jsonl event route) ==",
                HEADER,
                "== Peak-hours holds (decisions.jsonl events hold, release, toggle) ==",
                "== Tool result filter (tool_results.jsonl) ==",
                "== Auxiliary model calls (auxiliary.jsonl) ==",
                "== Jev usage ==",
            ])
            self.assertIn("  holds 1, releases 0, toggles 0, distinct held cards 1", with_glm)
            self.assertIn("  aux_task compression model glm-5.3: calls 1", with_glm)
            other = split_sections(without_glm)
            self.assertEqual(other.pop(HEADER), ["  no records"])
            sections.pop(HEADER)
            # Every section other than the GLM review section has the same
            # lines whether or not a board has GLM reviewers.
            self.assertEqual(sections, other)
            self.assertEqual(with_glm.splitlines()[0], without_glm.splitlines()[0])

    def test_read_only_report_changes_no_file(self):
        # The command line run reads plugins/jev/config.json of this checkout,
        # whose board harness names harness-reviewer-glm and harness-reviewer.
        boards = report.glm_review_boards(report.load_jev_config())
        self.assertEqual(boards.get("harness"), ([GLM_REVIEWER], OPUS_REVIEWER))
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, "harness", [card_glm_change_request_pass_approval(),
                                               card_pass_then_opus_change_request()])
            before = tree_state(tmp)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--log-dir", fixture.logs, "--since", "100000",
                 "--kanban-db", fixture.db, "--state-db", os.devnull],
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")
            self.assertIn(HEADER, proc.stdout)
            self.assertIn("passes 2", proc.stdout)
            self.assertIn("approved 1, changes requested 1, not yet reviewed 0", proc.stdout)
            self.assertNotIn(SENTINEL, proc.stdout)
            self.assertEqual(tree_state(tmp), before)


def write_logs(log_dir):
    """One record in each log stream, so that the other sections print figures."""
    ts = "2027-01-15T08:00:00+00:00"  # 1_800_000_000 is 2027-01-15T08:00:00Z
    records = {
        "decisions": [{"ts": ts, "event": "hold", "board": "harness", "task_id": "t_glm_change"}],
        "tool_results": [{"ts": ts, "event": "filter", "tool": "terminal", "action": "filtered",
                          "profile": GLM_REVIEWER, "chars_before": 5000, "chars_after": 1000}],
        "auxiliary": [{"ts": ts, "aux_task": "compression", "model": "glm-5.3",
                       "input_tokens": 10, "output_tokens": 2}],
    }
    for stream, lines in records.items():
        with open(os.path.join(log_dir, f"{stream}.jsonl"), "w", encoding="utf-8") as handle:
            for record in lines:
                handle.write(json.dumps(record) + "\n")


def split_sections(text):
    """{section header: [lines]} of a report, in report order."""
    sections = {}
    current = None
    for line in text.splitlines()[1:]:
        if line.startswith("== "):
            current = line
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def tree_state(root):
    """{relative path: (sha256, mtime_ns)} of every file below root."""
    state = {}
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            state[os.path.relpath(path, root)] = (
                hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                os.stat(path).st_mtime_ns)
    return state


if __name__ == "__main__":
    unittest.main()
