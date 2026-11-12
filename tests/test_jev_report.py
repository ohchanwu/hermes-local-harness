"""Offline tests for scripts/jev-report (Part D of the jev plugin).

Every log file and database is made under a temporary directory. Card ids,
profiles, paths and token numbers are synthetic. No live log directory, board
database or session database is read: every run passes --log-dir (or
HERMES_JEV_LOG_DIR), --kanban-db and --state-db explicitly.
"""
import datetime
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


report = load("jev_report_under_test", SCRIPT)

NOW = 1_800_000_000
SENTINEL = "SENTINEL-CARD-TEXT-5e2a71"
HEADERS = (
    "== Card model routing (decisions.jsonl event route) ==",
    "== Peak-hours holds (decisions.jsonl events hold, release, toggle) ==",
    "== Tool result filter (tool_results.jsonl) ==",
    "== Auxiliary model calls (auxiliary.jsonl) ==",
    "== Jev usage ==",
)


def ts(seconds_before_now):
    zone = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.fromtimestamp(NOW - seconds_before_now, zone).isoformat(timespec="seconds")


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def route(task_id, name, applied, tokens, age=3600, **extra):
    record = {"ts": ts(age), "profile": "example-orchestrator", "event": "route",
              "board": "harness", "task_id": task_id, "route": name, "applied": applied,
              "jev_input_tokens": tokens, "error_class": None}
    record.update(extra)
    return record


def make_logs(log_dir):
    os.makedirs(log_dir)
    write_jsonl(os.path.join(log_dir, "decisions.jsonl"), [
        route("t_a", "easy", True, 1000),
        route("t_b", "easy", True, 2000),
        route("t_c", "hard", True, 500),
        route("t_d", "medium", False, None, error_class="JevTimeout"),
        route("t_e", "easy", True, 999999, age=40 * 86400),  # outside --since 30
        route(None, "easy", False, None),
        {"ts": ts(100), "profile": "example-orchestrator", "event": "hold", "board": "harness",
         "task_id": "t_a", "held_until": ts(-3600)},
        {"ts": ts(50), "profile": "example-orchestrator", "event": "release", "board": "harness",
         "task_id": "t_a", "held_until": None},
        {"ts": ts(40), "profile": "owner", "event": "toggle", "board": None},
    ])
    with open(os.path.join(log_dir, "decisions.jsonl"), "a", encoding="utf-8") as handle:
        handle.write("not json\n")
        handle.write(json.dumps({"ts": "not a time", "event": "route", "task_id": "t_x"}) + "\n")

    def tool(name, profile, action, before, after, tokens=None, saved=None, reason=None):
        return {"ts": ts(600), "profile": profile, "event": "filter", "session_id": "s",
                "tool": name, "chars_before": before, "chars_after": after, "chunks_kept": None,
                "chunks_total": None, "jev_latency_ms": 90, "jev_input_tokens": tokens,
                "action": action, "reason": reason, "error_class": None, "saved_file": saved}

    write_jsonl(os.path.join(log_dir, "tool_results.jsonl"), [
        tool("terminal", "worker-1", "filtered", 20000, 5000, 3000, "/cache/jev/1.txt"),
        tool("terminal", "worker-2", "filtered", 10000, 4000, 1500, "/cache/jev/2.txt"),
        tool("search_files", "worker-1", "unchanged", 9000, 9000, 500,
             reason="kept_ratio_at_or_above_max"),
        tool("execute_code", "worker-2", "skipped", 100, 100, reason="below_min_chars"),
        {"ts": ts(300), "profile": "worker-1", "event": "saved_read", "tool": "read_file",
         "saved_file": "/cache/jev/1.txt"},
        {"ts": ts(200), "profile": "worker-1", "event": "saved_read", "tool": "read_file",
         "saved_file": "/cache/jev/1.txt"},
    ])
    write_jsonl(os.path.join(log_dir, "auxiliary.jsonl"), [
        {"ts": ts(700), "profile": "worker-1", "aux_task": "title_generation", "provider": "p",
         "model": "claude-opus-5-5", "input_tokens": 100, "output_tokens": 20, "status": "ok"},
        {"ts": ts(650), "profile": "worker-1", "aux_task": "title_generation", "provider": "p",
         "model": "claude-opus-5-5", "input_tokens": 100, "output_tokens": 20, "status": "ok"},
        {"ts": ts(640), "profile": "worker-2", "aux_task": "compression", "provider": "zai",
         "model": "glm-5.3", "input_tokens": 1000, "output_tokens": 200, "status": "ok"},
    ])


def make_kanban_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT,
                            workspace_path TEXT);
        CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                                profile TEXT, status TEXT NOT NULL, started_at INTEGER NOT NULL,
                                ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT,
                                error TEXT);
    """)
    for task_id in ("t_a", "t_b", "t_c", "t_d"):
        conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?)",
                     (task_id, SENTINEL, SENTINEL, f"/ws/{task_id}"))
    runs = [
        ("t_a", "worker-1", "done", NOW - 5000, NOW - 4000, "changes_requested"),
        ("t_a", "worker-1", "done", NOW - 3000, NOW - 2000, "completed"),
        # Overlaps the run above: session s2 matches both runs and is counted once.
        ("t_a", "worker-1", "done", NOW - 2995, NOW - 2500, "completed"),
        ("t_b", "worker-2", "crashed", NOW - 9000, NOW - 8000, "crashed"),
        ("t_c", "worker-1", "done", NOW - 20000, NOW - 19000, "completed"),
        ("t_d", "worker-1", "blocked", NOW - 30000, NOW - 29000, "blocked"),
    ]
    for run in runs:
        conn.execute("INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, "
                     "outcome, summary, metadata, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (*run, SENTINEL, SENTINEL, SENTINEL))
    conn.commit()
    conn.close()


def make_state_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at REAL NOT NULL,
                               profile_name TEXT, cwd TEXT, title TEXT, system_prompt TEXT);
        CREATE TABLE session_model_usage (session_id TEXT NOT NULL, model TEXT NOT NULL,
                               input_tokens INTEGER, output_tokens INTEGER,
                               cache_read_tokens INTEGER, cache_write_tokens INTEGER);
        CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, content TEXT);
    """)
    sessions = [
        ("s1", "kanban", NOW - 4990, "worker-1", "/ws/t_a"),
        ("s2", "kanban", NOW - 2990, "worker-1", "/ws/t_a/sub"),
        ("s3", "kanban", NOW - 8990, None, "/ws/t_b"),
        ("s4", "cli", NOW - 4990, "worker-1", "/ws/t_a"),          # not a worker session
        ("s5", "kanban", NOW - 4990, "other-profile", "/ws/t_a"),  # other profile
        ("s6", "kanban", NOW - 4990, "worker-1", "/ws/t_a-other"),  # other workspace
        ("s7", "kanban", NOW - 1000, "worker-1", "/ws/t_a"),        # after the runs ended
    ]
    for row in sessions:
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", (*row, SENTINEL, SENTINEL))
        conn.execute("INSERT INTO messages (session_id, content) VALUES (?, ?)", (row[0], SENTINEL))
    usage = [
        ("s1", "claude-opus-5-5", 60, 6, 600, 50),
        ("s1", "claude-haiku-5-5", 40, 4, 400, 0),
        ("s2", "claude-opus-5-5", 200, 20, 0, 0),
        ("s3", "glm-5.3", 300, 30, 3000, 0),
        ("s4", "claude-opus-5-5", 9999, 9999, 9999, 9999),
        ("s5", "claude-opus-5-5", 9999, 9999, 9999, 9999),
        ("s6", "claude-opus-5-5", 9999, 9999, 9999, 9999),
        ("s7", "claude-opus-5-5", 9999, 9999, 9999, 9999),
    ]
    conn.executemany("INSERT INTO session_model_usage VALUES (?, ?, ?, ?, ?, ?)", usage)
    conn.commit()
    conn.close()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EmptyInputTests(unittest.TestCase):
    def assert_all_sections_empty(self, text):
        for header in HEADERS:
            self.assertIn(header, text)
        self.assertEqual(text.count("  no records"), len(HEADERS))

    def test_empty_log_directory_prints_every_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = os.path.join(tmp, "empty-logs")
            os.makedirs(logs)
            env = dict(os.environ, HERMES_JEV_LOG_DIR=logs)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--kanban-db", os.devnull, "--state-db", os.devnull],
                capture_output=True, text=True, encoding="utf-8", env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")
            self.assertIn(f"log directory {logs}", proc.stdout)
            self.assert_all_sections_empty(proc.stdout)

    def test_missing_log_directory_and_databases(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = report.build_report(os.path.join(tmp, "absent"), 30,
                                       [os.path.join(tmp, "absent.db")],
                                       [os.path.join(tmp, "absent-state.db")], now=NOW)
            self.assert_all_sections_empty(text)

    def test_logs_without_databases(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = os.path.join(tmp, "logs")
            make_logs(logs)
            empty = os.path.join(tmp, "empty.db")
            Path(empty).write_bytes(b"")
            text = report.build_report(logs, 30, [empty], [empty], now=NOW)
            self.assertIn("  task_runs: no records", text)
            self.assertIn("    tokens per card: no records", text)
            self.assertIn("  Jev input tokens: 8500", text)


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = cls._tmp.name
        cls.logs = os.path.join(tmp, "logs")
        make_logs(cls.logs)
        cls.kanban_db = os.path.join(tmp, "kanban.db")
        cls.state_db = os.path.join(tmp, "state.db")
        make_kanban_db(cls.kanban_db)
        make_state_db(cls.state_db)
        cls.digests = (digest(cls.kanban_db), digest(cls.state_db))
        cls.text = report.build_report(cls.logs, 30, [cls.kanban_db], [cls.state_db], now=NOW)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def assert_lines(self, *lines):
        for line in lines:
            self.assertIn(line + "\n", self.text)

    def test_every_section_present(self):
        for header in HEADERS:
            self.assertIn(header, self.text)
        self.assertNotIn("no records", self.text.split(HEADERS[1])[1])

    def test_routing_counts_outcomes_and_tokens(self):
        self.assert_lines(
            "  route records: 5; without task_id: 1",
            "  route easy applied=yes: cards 2",
            "    cards with a changes_requested run: 1 of 2 (50.0%)",
            "    cards with a crashed run: 1 of 2 (50.0%)",
            "    cards with a blocked run: 0 of 2 (0.0%)",
            "    tokens per card (average over 2 cards with sessions): total 2355, input 300, "
            "output 30, cache read 2000, cache write 25",
            "  route hard applied=yes: cards 1",
            "  route medium applied=no: cards 1",
            "    cards with a blocked run: 1 of 1 (100.0%)",
        )
        hard = self.text.split("  route hard applied=yes")[1].split("  route medium")[0]
        self.assertIn("    tokens per card: no records", hard)
        self.assertNotIn("t_e", self.text)

    def test_peak_hold_counts(self):
        self.assert_lines("  holds 1, releases 1, toggles 1, distinct held cards 1",
                          "  board harness: holds 1, releases 1")

    def test_tool_result_counts(self):
        self.assert_lines(
            "  tool terminal: results 2, filtered 2, unchanged 0, skipped 0, characters removed 21000",
            "  tool search_files: results 1, filtered 0, unchanged 1, skipped 0, characters removed 0",
            "  tool execute_code: results 1, filtered 0, unchanged 0, skipped 1, characters removed 0",
            "  profile worker-1: characters removed 15000",
            "  profile worker-2: characters removed 6000",
            "  reason skipped below_min_chars: 1",
            "  reason unchanged kept_ratio_at_or_above_max: 1",
            "  saved_read records: 2",
            "  saved files read later: 1 of 2 (50.0%)",
        )

    def test_auxiliary_counts(self):
        self.assert_lines(
            "  aux_task compression model glm-5.3: calls 1, input tokens 1000, output tokens 200",
            "  aux_task title_generation model claude-opus-5-5: calls 2, input tokens 200, "
            "output tokens 40",
        )
        self.assertLess(self.text.index("aux_task compression"),
                        self.text.index("aux_task title_generation"))

    def test_jev_tokens_and_cost(self):
        self.assert_lines(
            "  records with Jev input tokens: 6",
            "  Jev input tokens: 8500",
            "  Jev cost: 0.000357 US dollars (0.042 US dollars per million input tokens)",
        )

    def test_no_card_text_and_databases_unchanged(self):
        self.assertNotIn(SENTINEL, self.text)
        self.assertEqual((digest(self.kanban_db), digest(self.state_db)), self.digests)

    def test_command_line_with_fixture(self):
        env = dict(os.environ)
        env.pop("HERMES_JEV_LOG_DIR", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--log-dir", self.logs, "--since", "100000",
             "--kanban-db", self.kanban_db, "--state-db", self.state_db],
            capture_output=True, text=True, encoding="utf-8", env=env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(SENTINEL, proc.stdout)
        for header in HEADERS:
            self.assertIn(header, proc.stdout)
        self.assertEqual((digest(self.kanban_db), digest(self.state_db)), self.digests)


if __name__ == "__main__":
    unittest.main()
