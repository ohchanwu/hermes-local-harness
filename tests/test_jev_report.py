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

    def test_line_with_invalid_utf8_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = os.path.join(tmp, "logs")
            os.makedirs(logs)
            good = json.dumps(route("t_a", "easy", True, 1000)).encode("utf-8")
            with open(os.path.join(logs, "decisions.jsonl"), "wb") as handle:
                handle.write(b'{"ts": "\xff"}\n\xff\xfe not json\n' + good + b"\n")
            records = report.read_log(logs, "decisions", 0)
            self.assertEqual([r["task_id"] for r in records], ["t_a"])
            env = dict(os.environ, HERMES_JEV_LOG_DIR=logs)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--kanban-db", os.devnull, "--state-db", os.devnull,
                 "--since", "100000"],
                capture_output=True, text=True, encoding="utf-8", env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")

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


WORKER_DB_SCHEMA = """
    CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at REAL NOT NULL,
                           profile_name TEXT, cwd TEXT, parent_session_id TEXT, model TEXT,
                           input_tokens INTEGER, output_tokens INTEGER,
                           cache_read_tokens INTEGER, cache_write_tokens INTEGER,
                           title TEXT, system_prompt TEXT);
    CREATE TABLE session_model_usage (session_id TEXT NOT NULL, model TEXT NOT NULL,
                           task TEXT, input_tokens INTEGER, output_tokens INTEGER,
                           cache_read_tokens INTEGER, cache_write_tokens INTEGER);
"""


class SavingsFixture:
    """Synthetic board database, two profile state databases and a decisions log.

    Every card has one worker run (profile `worker`, sessions in worker.db) and
    one reviewer run (profile `reviewer`, sessions in reviewer.db). A card spec
    is (task_id, board, route, group, worker_claude, worker_glm,
    reviewer_claude, status); group is "glm" (applied route record),
    "control" (control_group record) or "hard" (applied hard route). Each token
    number is split into input, output, cache read and cache write parts in the
    ratio 4:1:4:1, so a number must be a multiple of 10.
    """

    def __init__(self, tmp, specs, extra_records=(), record_age=3600):
        self.tmp = tmp
        self.logs = os.path.join(tmp, "logs")
        os.makedirs(self.logs)
        self.kanban_db = os.path.join(tmp, "kanban.db")
        self.worker_db = os.path.join(tmp, "worker.db")
        self.reviewer_db = os.path.join(tmp, "reviewer.db")
        kanban = sqlite3.connect(self.kanban_db)
        kanban.executescript("""
            CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT,
                                status TEXT, workspace_path TEXT);
            CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                                    profile TEXT, status TEXT NOT NULL, started_at INTEGER NOT NULL,
                                    ended_at INTEGER, outcome TEXT, summary TEXT);
        """)
        worker, reviewer = sqlite3.connect(self.worker_db), sqlite3.connect(self.reviewer_db)
        worker.executescript(WORKER_DB_SCHEMA)
        reviewer.executescript(WORKER_DB_SCHEMA)
        records = []
        for index, spec in enumerate(specs):
            task_id, board, route_name, group, w_claude, w_glm, r_claude, status = spec
            workspace = f"/ws/{task_id}"
            start = NOW - 500000 + index * 1000
            kanban.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                           (task_id, SENTINEL, SENTINEL, status, workspace))
            kanban.execute("INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, "
                           "outcome, summary) VALUES (?, 'worker', 'done', ?, ?, "
                           "'review_requested', ?)", (task_id, start, start + 400, SENTINEL))
            kanban.execute("INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, "
                           "outcome, summary) VALUES (?, 'reviewer', 'done', ?, ?, 'completed', ?)",
                           (task_id, start + 500, start + 900, SENTINEL))
            self.session(worker, f"w-{task_id}", start + 5, "worker", workspace,
                         [("claude-haiku-5-5", w_claude), ("glm-5.3", w_glm)])
            self.session(reviewer, f"r-{task_id}", start + 505, "reviewer", workspace,
                         [("claude-opus-5-5", r_claude)])
            if group == "control":
                records.append(route(task_id, route_name, False, 100, age=record_age, board=board,
                                     not_applied_reason="control_group",
                                     probabilities={route_name: 0.9}))
            else:
                records.append(route(task_id, route_name, True, 100, age=record_age, board=board))
        records.extend(extra_records)
        write_jsonl(os.path.join(self.logs, "decisions.jsonl"), records)
        for conn in (kanban, worker, reviewer):
            conn.commit()
            conn.close()

    @staticmethod
    def session(conn, session_id, started, profile, cwd, usage):
        conn.execute("INSERT INTO sessions (id, source, started_at, profile_name, cwd, title, "
                     "system_prompt) VALUES (?, 'kanban', ?, ?, ?, ?, ?)",
                     (session_id, started, profile, cwd, SENTINEL, SENTINEL))
        for model, total in usage:
            if total:
                conn.execute("INSERT INTO session_model_usage VALUES (?, ?, '', ?, ?, ?, ?)",
                             (session_id, model, total * 4 // 10, total // 10,
                              total * 4 // 10, total // 10))

    def state_dbs(self):
        return [self.worker_db, self.reviewer_db]

    def rows(self, **kwargs):
        return report.route_savings(self.logs, 30, [self.kanban_db], self.state_dbs(),
                                    now=NOW, **kwargs)

    def text(self, **kwargs):
        return report.build_report(self.logs, 30, [self.kanban_db], self.state_dbs(),
                                   now=NOW, **kwargs)


def specs(prefix, count, board, route_name, group, w_claude, w_glm, r_claude, status="done"):
    return [(f"t_{prefix}{i:02d}", board, route_name, group, w_claude, w_glm, r_claude, status)
            for i in range(count)]


def row_for(rows, scope, route_name, board=None):
    matches = [r for r in rows if r["scope"] == scope and r["route"] == route_name
               and r["board"] == board]
    return matches[0] if matches else None


class CardTokenTests(unittest.TestCase):
    """Part 8.1: Claude tokens per card over worker and reviewer profiles, GLM separate."""

    def test_sessions_of_every_profile_and_subagents_are_summed_per_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SavingsFixture(tmp, [("t_one", "harness", "easy", "glm", 100, 5000, 2000, "done")])
            worker = sqlite3.connect(fixture.worker_db)
            # Subagent of the worker session: counted. Session without usage rows: its
            # sessions-row model and tokens are used.
            worker.execute("INSERT INTO sessions (id, source, started_at, profile_name, cwd, "
                           "parent_session_id, model, input_tokens, output_tokens, "
                           "cache_read_tokens, cache_write_tokens) VALUES "
                           "('sub-1', 'subagent', ?, 'worker', '/elsewhere', 'w-t_one', "
                           "'glm-5.3-flash', 10, 20, 30, 40)", (NOW - 400000,))
            worker.execute("INSERT INTO sessions (id, source, started_at, profile_name, cwd, "
                           "parent_session_id, model) VALUES "
                           "('sub-2', 'subagent', ?, 'worker', '/elsewhere', 'sub-1', "
                           "'claude-haiku-5-5')", (NOW - 400000,))
            worker.execute("INSERT INTO session_model_usage VALUES "
                           "('sub-2', 'anthropic/claude-haiku-5-5', '', 1, 2, 3, 4)")
            # Session of another card's workspace and an unrelated cron session: not counted.
            worker.execute("INSERT INTO sessions (id, source, started_at, profile_name, cwd) "
                           "VALUES ('other', 'kanban', ?, 'worker', '/ws/t_two')", (NOW - 499990,))
            worker.execute("INSERT INTO session_model_usage VALUES "
                           "('other', 'claude-opus-5-5', '', 9999, 9999, 9999, 9999)")
            worker.execute("INSERT INTO sessions (id, source, started_at, profile_name, cwd) "
                           "VALUES ('cron', 'cron', ?, 'worker', '/ws/t_one')", (NOW - 499990,))
            worker.execute("INSERT INTO session_model_usage VALUES "
                           "('cron', 'claude-opus-5-5', '', 9999, 9999, 9999, 9999)")
            worker.commit()
            worker.close()
            cards = report.load_runs([fixture.kanban_db], {"t_one"})
            sessions = report.load_sessions(fixture.state_dbs())
            tokens = report.card_tokens(cards["t_one"], sessions, NOW)
            self.assertEqual(tokens["claude"], {"input_tokens": 40 + 800 + 1,
                                                "output_tokens": 10 + 200 + 2,
                                                "cache_read_tokens": 40 + 800 + 3,
                                                "cache_write_tokens": 10 + 200 + 4})
            self.assertEqual(tokens["glm"], {"input_tokens": 2000 + 10, "output_tokens": 500 + 20,
                                             "cache_read_tokens": 2000 + 30,
                                             "cache_write_tokens": 500 + 40})
            self.assertEqual(report.token_sum(tokens, "claude"), 2110)
            self.assertEqual(report.token_sum(tokens, "glm"), 5100)
            self.assertEqual(report.token_sum(tokens, "other"), 0)

    def test_model_family(self):
        self.assertEqual(report.model_family("claude-fable-5-2"), "claude")
        self.assertEqual(report.model_family("anthropic/claude-opus-5-5"), "claude")
        self.assertEqual(report.model_family("glm-5.3-flash"), "glm")
        self.assertEqual(report.model_family("z-ai/GLM-5.3"), "glm")
        self.assertEqual(report.model_family("gpt-6-astra"), "other")
        self.assertEqual(report.model_family(None), "other")

    def test_route_section_prints_claude_and_glm_tokens_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SavingsFixture(tmp, [("t_one", "harness", "easy", "glm", 100, 5000, 2000, "done")])
            text = fixture.text()
            self.assertIn("    Claude tokens per card (average over 1 cards with sessions): "
                          "total 2100, input 840, output 210, cache read 840, cache write 210\n", text)
            self.assertIn("    GLM tokens per card (average over 1 cards with sessions): "
                          "total 5000, input 2000, output 500, cache read 2000, cache write 500\n", text)
            self.assertNotIn(SENTINEL, text)


class SavingsTests(unittest.TestCase):
    """Parts 8.2 to 8.4: groups of done cards, the saved figure and the rule line."""

    def test_saved_figure_per_board_and_over_all_boards(self):
        cards = (specs("ha", 2, "harness", "easy", "glm", 0, 9000, 1000)
                 + specs("ja", 1, "jobcron", "easy", "glm", 2000, 9000, 1000)
                 + specs("hc", 1, "harness", "easy", "control", 6000, 0, 2000)
                 + specs("jc", 1, "jobcron", "easy", "control", 4000, 0, 2000)
                 + specs("hm", 1, "harness", "medium", "glm", 0, 100, 500)
                 + specs("hh", 3, "harness", "hard", "hard", 7000, 0, 1000))
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SavingsFixture(tmp, cards)
            rows = fixture.rows()
            harness = row_for(rows, "board", "easy", "harness")
            self.assertEqual((harness["glm"]["cards"], harness["control"]["cards"]), (2, 1))
            self.assertEqual(harness["glm"]["mean_claude"], 1000)
            self.assertEqual(harness["control"]["mean_claude"], 8000)
            self.assertEqual(harness["glm"]["mean_glm"], 9000)
            self.assertEqual(harness["saved"], (8000 - 1000) * 2)
            jobcron = row_for(rows, "board", "easy", "jobcron")
            self.assertEqual(jobcron["saved"], (6000 - 3000) * 1)
            every = row_for(rows, "all", "easy")
            self.assertEqual((every["glm"]["cards"], every["control"]["cards"]), (3, 2))
            self.assertAlmostEqual(every["glm"]["mean_claude"], 5000 / 3)
            self.assertEqual(every["control"]["mean_claude"], 7000)
            self.assertAlmostEqual(every["saved"], (7000 - 5000 / 3) * 3)
            self.assertFalse(every["rule"])
            medium = row_for(rows, "all", "medium")
            self.assertEqual((medium["glm"]["cards"], medium["control"]["cards"]), (1, 0))
            self.assertIsNone(medium["saved"])
            self.assertIsNone(row_for(rows, "all", "hard"))
            text = fixture.text()
            self.assertIn("  board harness route easy: GLM-routed cards 2, control cards 1, "
                          "saved 14000\n", text)
            self.assertIn("  all boards route easy: GLM-routed cards 3, control cards 2, "
                          "saved 16000\n", text)
            self.assertIn("    mean Claude tokens per GLM-routed card 1667, per control card 7000\n", text)
            self.assertIn("  all boards route medium: GLM-routed cards 1, control cards 0, "
                          "saved none\n", text)
            self.assertNotIn(report.RULE_TEXT, text)
            self.assertNotIn(SENTINEL, text)

    def test_only_done_cards_and_escalated_cards_stay_in_the_glm_group(self):
        cards = (specs("g", 2, "harness", "easy", "glm", 0, 0, 1000)
                 + specs("r", 2, "harness", "easy", "glm", 0, 0, 90000, status="running")
                 + specs("c", 1, "harness", "easy", "control", 3000, 0, 0)
                 + specs("x", 1, "harness", "easy", "control", 90000, 0, 0, status="archived"))
        escalate = {"ts": ts(60), "event": "escalate", "board": "harness", "task_id": "t_g00",
                    "original_assignee": "worker-glm", "new_assignee": "worker",
                    "change_requests": 5, "applied": True, "error_class": None}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SavingsFixture(tmp, cards, extra_records=[escalate])
            every = row_for(fixture.rows(), "all", "easy")
            self.assertEqual((every["glm"]["cards"], every["control"]["cards"]), (2, 1))
            self.assertEqual(every["escalated"], 1)
            self.assertEqual(every["saved"], (3000 - 1000) * 2)
            self.assertIn("done GLM-routed cards moved to a Claude worker by an escalate "
                          "record: 1\n", fixture.text())

    def test_card_with_applied_and_control_records_is_glm_routed(self):
        both = route("t_b00", "medium", False, 100, board="harness",
                     not_applied_reason="control_group")
        with tempfile.TemporaryDirectory() as tmp:
            rows = SavingsFixture(tmp, specs("b", 1, "harness", "easy", "glm", 0, 0, 100),
                                  extra_records=[both]).rows()
            self.assertEqual(row_for(rows, "all", "easy")["glm"]["cards"], 1)
            self.assertIsNone(row_for(rows, "all", "medium"))

    def rule_rows(self, glm_count, control_count, glm_claude, control_claude):
        with tempfile.TemporaryDirectory() as tmp:
            cards = (specs("g", glm_count, "harness", "easy", "glm", 0, 0, glm_claude)
                     + specs("c", control_count, "jobcron", "easy", "control", 0, 0, control_claude))
            fixture = SavingsFixture(tmp, cards)
            return fixture.rows(), fixture.text()

    def test_rule_line_at_both_minimums_with_negative_saved(self):
        rows, text = self.rule_rows(10, 3, 1200, 1000)
        every = row_for(rows, "all", "easy")
        self.assertEqual(every["saved"], -2000)
        self.assertTrue(every["rule"])
        self.assertIn("  route easy: disable this route: owner permission required\n", text)
        self.assertEqual(text.count(report.RULE_TEXT), 1)
        self.assertFalse(row_for(rows, "board", "easy", "harness")["rule"])

    def test_rule_line_when_saved_is_zero(self):
        rows, text = self.rule_rows(10, 3, 1000, 1000)
        self.assertEqual(row_for(rows, "all", "easy")["saved"], 0)
        self.assertIn("  route easy: " + report.RULE_TEXT + "\n", text)

    def test_no_rule_line_below_the_glm_minimum(self):
        rows, text = self.rule_rows(9, 3, 1200, 1000)
        self.assertLess(row_for(rows, "all", "easy")["saved"], 0)
        self.assertFalse(row_for(rows, "all", "easy")["rule"])
        self.assertNotIn(report.RULE_TEXT, text)

    def test_no_rule_line_below_the_control_minimum(self):
        rows, text = self.rule_rows(10, 2, 1200, 1000)
        self.assertLess(row_for(rows, "all", "easy")["saved"], 0)
        self.assertFalse(row_for(rows, "all", "easy")["rule"])
        self.assertNotIn(report.RULE_TEXT, text)

    def test_no_rule_line_when_saved_is_positive(self):
        rows, text = self.rule_rows(10, 3, 900, 1000)
        self.assertEqual(row_for(rows, "all", "easy")["saved"], 1000)
        self.assertNotIn(report.RULE_TEXT, text)

    def test_report_changes_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cards = (specs("g", 10, "harness", "easy", "glm", 0, 0, 1200)
                     + specs("c", 3, "harness", "easy", "control", 0, 0, 1000))
            fixture = SavingsFixture(tmp, cards)
            before = tree_state(tmp)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--log-dir", fixture.logs, "--since", "100000",
                 "--kanban-db", fixture.kanban_db, "--state-db", fixture.worker_db,
                 "--state-db", fixture.reviewer_db],
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("  route easy: " + report.RULE_TEXT + "\n", proc.stdout)
            self.assertNotIn(SENTINEL, proc.stdout)
            self.assertEqual(tree_state(tmp), before)


def tree_state(root):
    """{relative path: (sha256, mtime_ns)} of every file below root."""
    state = {}
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            state[os.path.relpath(path, root)] = (digest(path), os.stat(path).st_mtime_ns)
    return state


class AfterOptionTests(unittest.TestCase):
    """Part 8.5: count only records later than a given date and time."""

    def test_records_at_or_before_the_time_are_not_counted(self):
        deployment = NOW - 7200
        late = specs("l", 2, "harness", "easy", "glm", 0, 0, 1000)
        with tempfile.TemporaryDirectory() as tmp:
            early_record = route("t_early", "easy", True, 100, age=7200 + 60, board="harness")
            exact_record = route("t_exact", "easy", True, 100, age=7200, board="harness")
            fixture = SavingsFixture(tmp, late, extra_records=[early_record, exact_record],
                                     record_age=3600)
            records = report.read_log(fixture.logs, "decisions", 0, deployment)
            self.assertEqual(sorted(r["task_id"] for r in records), ["t_l00", "t_l01"])
            text = fixture.text(after=deployment)
            self.assertIn("  route records: 2; without task_id: 0\n", text)
            self.assertIn("records after 2027-01-15T06:00:00+00:00", text.splitlines()[0])
            self.assertIn("  route records: 4; without task_id: 0\n", fixture.text())

    def test_after_without_since_has_no_day_limit(self):
        old = NOW - 40 * 86400
        args = report.build_parser().parse_args(["--after", "2026-11-14T09:00:00+09:00"])
        log_dir, since, after, _kanban, _state = report.resolve_args(args)
        self.assertIsNone(since)
        self.assertEqual(after, datetime.datetime(2026, 11, 14, 0, 0,
                                                  tzinfo=datetime.timezone.utc).timestamp())
        with tempfile.TemporaryDirectory() as tmp:
            write_jsonl(os.path.join(tmp, "decisions.jsonl"),
                        [route("t_old", "easy", True, 1, age=40 * 86400)])
            text = report.build_report(tmp, None, [], [], now=NOW, after=old - 1)
            self.assertIn("  route records: 1; without task_id: 0\n", text)
            self.assertIn(f"log directory {tmp}, records after ", text)
            text = report.build_report(tmp, 30, [], [], now=NOW, after=old - 1)
            # --since 30 as well: the 40-day-old record is outside the day limit.
            self.assertIn(HEADERS[0] + "\n  no records\n", text)
        defaults = report.resolve_args(report.build_parser().parse_args([]))
        self.assertEqual(defaults[1], 30)
        self.assertIsNone(defaults[2])

    def test_after_needs_a_utc_offset(self):
        for value in ("2026-11-14T09:00:00", "yesterday"):
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--after", value, "--log-dir", os.devnull,
                 "--kanban-db", os.devnull, "--state-db", os.devnull],
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("UTC offset", proc.stderr)
            self.assertEqual(proc.stdout, "")

    def test_help_lists_the_after_option(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True,
                              text=True, encoding="utf-8", check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--after DATETIME", proc.stdout)


if __name__ == "__main__":
    unittest.main()
