"""Offline tests for the jev plugin's TypeSafe client, log writer and plugin frame.

A local fake of the TypeSafe endpoint (``http.server`` on 127.0.0.1) answers
every request; no test calls TypeSafe, Z.ai or any other live model. The API
key is a synthetic test value set in the process environment.
"""
from __future__ import annotations

import importlib
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "jev"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(ROOT / "plugins"))

import jev_client  # noqa: E402
import jev_log  # noqa: E402

TEST_KEY = "jev-test-key-0123456789-not-a-real-credential"


class FakeTypeSafe:
    """Local fake of ``POST /v1/systemone``.

    ``mode``: ``ok`` (returns ``response``), ``http_error`` (HTTP 500),
    ``timeout`` (sleeps past the client timeout), ``not_json``, ``no_answers``.
    ``requests`` keeps (authorization header, parsed body) for each request.
    """

    def __init__(self) -> None:
        self.mode = "ok"
        self.response: dict = {"answers": {}, "usage": {"input_tokens": 1, "output_tokens": 0}}
        self.requests: list = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except Exception:
                    body = None
                fake.requests.append((self.headers.get("Authorization"), body))
                if fake.mode == "timeout":
                    time.sleep(1.0)
                if fake.mode == "http_error":
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'{"error":"server"}')
                    return
                if fake.mode == "not_json":
                    payload = b"<html>not json</html>"
                elif fake.mode == "no_answers":
                    payload = b'{"model": "jev-1.14.0"}'
                else:
                    payload = json.dumps(fake.response).encode("utf-8")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):  # silence the default stderr access log
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1/systemone"

    def settings(self, timeout: float = 0.5) -> dict:
        return {"endpoint": self.url, "model": "jev-1.14.0", "timeout_seconds": timeout,
                "api_key_env": "TYPESAFE_API_KEY"}

    def choice(self, choice: str, probabilities: dict, confidence: float = 0.8, question: str = "route") -> None:
        self.mode = "ok"
        self.response = {"model": "jev-1.14.0",
                         "answers": {question: {"type": "choice", "choice": choice, "confidence": confidence,
                                                "probabilities": probabilities}},
                         "usage": {"input_tokens": 321, "output_tokens": 30}}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def isolated_env(tmp: Path) -> dict:
    """Environment for one test: logs, switch and Kanban home under ``tmp``."""
    env = {
        "HERMES_JEV_LOG_DIR": str(tmp / "logs"),
        "HERMES_JEV_STATE_DIR": str(tmp / "state"),
        "HERMES_KANBAN_HOME": str(tmp / "kanban-home"),
        "HERMES_PROFILE": "harness-orchestrator",
        "TYPESAFE_API_KEY": TEST_KEY,
    }
    return env


FAKE_HERMES = r'''
import json, os, sqlite3, sys, time
argv = sys.argv[1:]
with open(os.environ["FAKE_HERMES_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
code = int(os.environ.get("FAKE_HERMES_EXIT", "0"))
db = os.environ.get("FAKE_KANBAN_DB")
if code == 0 and db and argv[:1] == ["kanban"]:
    rest = argv[1:]
    if rest[:1] == ["--board"]:
        rest = rest[2:]
    conn = sqlite3.connect(db)
    now = int(time.time())
    verb, task_id = rest[0], rest[1]
    if verb == "schedule":
        reason = " ".join(rest[2:])
        cur = conn.execute("UPDATE tasks SET status='scheduled' WHERE id=? AND status IN "
                           "('todo','ready','running','blocked')", (task_id,))
        if cur.rowcount != 1:
            code = 1
        else:
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                         (task_id, "scheduled", json.dumps({"reason": reason}), now))
    elif verb == "unblock":
        cur = conn.execute("UPDATE tasks SET status='ready' WHERE id=? AND status IN ('blocked','scheduled')",
                           (task_id,))
        if cur.rowcount != 1:
            code = 1
        else:
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                         (task_id, "unblocked", None, now))
    elif verb == "set-model":
        conn.execute("UPDATE tasks SET model_override=NULL, provider_override=NULL WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
sys.exit(code)
'''


def write_fake_hermes(directory: Path) -> str:
    """Write the fake ``hermes`` command; return the command string for ``--hermes``.

    It appends its arguments to ``$FAKE_HERMES_LOG`` and, when ``$FAKE_KANBAN_DB``
    is set, applies ``schedule``, ``unblock`` and ``set-model`` to that database.
    ``$FAKE_HERMES_EXIT`` sets a non-zero exit code (the change is then not applied).
    """
    script = directory / "fake_hermes.py"
    script.write_text(FAKE_HERMES, encoding="utf-8")
    return f"{sys.executable} {script}"


def fake_hermes_calls(log_path: Path) -> list:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_board_db(path: Path, tasks) -> None:
    """Synthetic board database with the columns the jev plugin reads.

    ``tasks``: iterable of (id, status, assignee) or (id, status, assignee, scheduled_reason).
    """
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, status TEXT, assignee TEXT,"
                 " model_override TEXT, provider_override TEXT)")
    conn.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER,"
                 " kind TEXT, payload TEXT, created_at INTEGER)")
    for row in tasks:
        task_id, status, assignee = row[:3]
        conn.execute("INSERT INTO tasks (id, title, status, assignee) VALUES (?, ?, ?, ?)",
                     (task_id, "synthetic card", status, assignee))
        if len(row) > 3:
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, 0)",
                         (task_id, "scheduled", json.dumps({"reason": row[3]})))
    conn.commit()
    conn.close()


def task_statuses(path: Path) -> dict:
    import sqlite3
    conn = sqlite3.connect(path)
    try:
        return dict(conn.execute("SELECT id, status FROM tasks").fetchall())
    finally:
        conn.close()


def read_records(log_dir: Path, stream: str) -> list:
    path = log_dir / f"{stream}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def all_text_under(directory: Path) -> str:
    chunks = []
    for path in directory.rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


class JevClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeTypeSafe()

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()

    def setUp(self):
        self.fake.requests.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, isolated_env(Path(self.tmp.name)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_successful_call_returns_answers_tokens_and_latency(self):
        self.fake.choice("easy", {"easy": 0.9, "hard": 0.1})
        result = jev_client.ask({"title": "x"}, {"route": {"type": "choice"}}, settings=self.fake.settings())
        self.assertEqual(result.answers["route"]["choice"], "easy")
        self.assertEqual((result.input_tokens, result.output_tokens), (321, 30))
        self.assertGreaterEqual(result.latency_ms, 0)
        authorization, body = self.fake.requests[-1]
        self.assertEqual(authorization, "Bearer " + TEST_KEY)
        self.assertEqual(body["model"], "jev-1.14.0")
        self.assertEqual(body["state"], {"title": "x"})
        self.assertIn("route", body["questions"])

    def assert_error(self, error_class, **settings_overrides):
        settings = {**self.fake.settings(), **settings_overrides}
        with self.assertRaises(jev_client.JevError) as caught:
            jev_client.ask("state", {"q": {"type": "noul", "instructions": "?"}}, settings=settings)
        self.assertEqual(caught.exception.error_class, error_class)
        self.assertNotIn(TEST_KEY, str(caught.exception))
        self.assertNotIn(TEST_KEY, repr(caught.exception))
        return caught.exception

    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            self.assert_error("MissingKey")
        self.assertEqual(self.fake.requests, [])

    def test_timeout(self):
        self.fake.mode = "timeout"
        self.assert_error("Timeout", timeout_seconds=0.2)

    def test_http_error(self):
        self.fake.mode = "http_error"
        error = self.assert_error("HTTPError")
        self.assertEqual(error.status, 500)

    def test_unexpected_response_not_json(self):
        self.fake.mode = "not_json"
        self.assert_error("UnexpectedResponse")

    def test_unexpected_response_without_answers(self):
        self.fake.mode = "no_answers"
        self.assert_error("UnexpectedResponse")

    def test_connection_refused(self):
        self.assert_error("URLError", endpoint="http://127.0.0.1:9/v1/systemone")

    def test_default_settings_are_the_typesafe_endpoint(self):
        self.assertEqual(jev_client.DEFAULT_ENDPOINT, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(jev_client.DEFAULT_MODEL, "jev-1.14.0")
        self.assertEqual(jev_client.DEFAULT_TIMEOUT_SECONDS, 5.0)
        config = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["jev"]["endpoint"], "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(config["jev"]["timeout_seconds"], 5)


class JevLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, isolated_env(Path(self.tmp.name)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log_dir = Path(self.tmp.name) / "logs"

    def test_write_creates_private_files_and_fills_fields(self):
        self.assertTrue(jev_log.write("decisions", {"event": "route", "board": "harness"}))
        path = self.log_dir / "decisions.jsonl"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.log_dir.stat().st_mode), 0o700)
        record = read_records(self.log_dir, "decisions")[0]
        self.assertEqual(list(record)[:2], ["ts", "profile"])
        self.assertEqual(record["profile"], "harness-orchestrator")
        self.assertRegex(record["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        for field in jev_log.STREAM_FIELDS["decisions"]:
            self.assertIn(field, record)
        self.assertIsNone(record["task_id"])

    def test_one_line_per_record(self):
        jev_log.write("auxiliary", {"aux_task": "a"})
        jev_log.write("auxiliary", {"aux_task": "b"})
        self.assertEqual([r["aux_task"] for r in read_records(self.log_dir, "auxiliary")], ["a", "b"])

    def test_invalid_stream_name_is_refused(self):
        self.assertFalse(jev_log.write("../escape", {}))
        self.assertFalse((Path(self.tmp.name) / "escape.jsonl").exists())

    def test_profile_from_hermes_home(self):
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "",
                                          "HERMES_HOME": "/Users/example/.hermes/profiles/jobcron-worker"}):
            self.assertEqual(jev_log.profile_name(), "jobcron-worker")
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "", "HERMES_HOME": "/Users/example/.hermes"}):
            self.assertEqual(jev_log.profile_name(), "default")

    def test_default_log_dir(self):
        with mock.patch.dict(os.environ, {"HERMES_JEV_LOG_DIR": ""}):
            self.assertEqual(str(jev_log.log_dir()), "/Users/chanbla11mit/.hermes/jev/logs")


class _Ctx:
    def __init__(self):
        self.middleware, self.hooks = [], []

    def register_middleware(self, kind, callback):
        self.middleware.append((kind, callback))

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


class PluginFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, isolated_env(Path(self.tmp.name)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log_dir = Path(self.tmp.name) / "logs"
        self.plugin = importlib.import_module("jev")

    def config_with(self, **sections):
        config = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
        for name, values in sections.items():
            config[name].update(values)
        return config

    def test_register_declares_middleware_and_hooks(self):
        ctx = _Ctx()
        self.plugin.register(ctx)
        self.assertEqual([k for k, _ in ctx.middleware], ["tool_execution"])
        self.assertEqual(sorted(n for n, _ in ctx.hooks), ["post_auxiliary_call", "transform_tool_result"])
        manifest = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("name: jev", manifest)
        self.assertIn('version: "0.1.0"', manifest)

    def test_config_sections_each_have_enabled(self):
        config = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
        for section in ("routing", "peak_hold", "tool_results", "auxiliary_log"):
            self.assertIs(config[section]["enabled"], True, section)
        self.assertEqual(config["tool_results"]["tools"], ["terminal", "execute_code", "search_files", "browser_exec"])
        for key, value in (("min_chars", 8000), ("max_chars", 100000), ("chunk_lines", 40), ("chunk_chars", 2000),
                           ("args_chars", 2000), ("keep_threshold", 0.3), ("max_kept_ratio", 0.8)):
            self.assertEqual(config["tool_results"][key], value, key)

    def test_auxiliary_record(self):
        self.plugin._post_auxiliary_call(
            aux_task="title_generation", provider="claude-subscription", model="claude-opus-5-5",
            usage={"input_tokens": 100, "cache_read_tokens": 20, "prompt_tokens": 120, "output_tokens": 9},
            error_type=None, streaming=False, request_messages=[{"content": "PRIVATE-TEXT"}])
        self.plugin._post_auxiliary_call(aux_task="compression", provider="p", model="m", usage=None,
                                         error_type="TimeoutError", streaming=False)
        records = read_records(self.log_dir, "auxiliary")
        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual({k: first[k] for k in ("aux_task", "provider", "model", "input_tokens", "output_tokens",
                                                 "status")},
                         {"aux_task": "title_generation", "provider": "claude-subscription",
                          "model": "claude-opus-5-5", "input_tokens": 120, "output_tokens": 9, "status": "ok"})
        self.assertEqual(records[1]["status"], "error")
        self.assertIsNone(records[1]["input_tokens"])
        self.assertNotIn("PRIVATE-TEXT", all_text_under(self.log_dir))

    def test_auxiliary_log_turns_off(self):
        with mock.patch.object(self.plugin, "load_config", return_value=self.config_with(auxiliary_log={"enabled": False})):
            self.plugin._post_auxiliary_call(aux_task="t", provider="p", model="m", usage=None)
        self.assertEqual(read_records(self.log_dir, "auxiliary"), [])

    def test_transform_wrapper_returns_none_when_module_missing_or_raising(self):
        kwargs = dict(tool_name="terminal", args={}, result="x" * 9000, session_id="s1")
        with mock.patch.object(self.plugin.importlib, "import_module", side_effect=ModuleNotFoundError("tool_filter")):
            self.assertIsNone(self.plugin._transform_tool_result(**kwargs))
        broken = mock.Mock()
        broken.transform.side_effect = RuntimeError("boom")
        with mock.patch.object(self.plugin.importlib, "import_module", return_value=broken):
            self.assertIsNone(self.plugin._transform_tool_result(**kwargs))

    def test_transform_wrapper_passes_the_shared_interface(self):
        seen = {}

        def transform(**kwargs):
            seen.update(kwargs)
            return "filtered"

        module = mock.Mock(transform=transform)
        with mock.patch.object(self.plugin.importlib, "import_module", return_value=module), \
                mock.patch.dict(os.environ, {"HERMES_HOME": str(Path(self.tmp.name) / "home")}):
            out = self.plugin._transform_tool_result(tool_name="terminal", args={"command": "ls"}, result="r",
                                                     session_id="s1", task_id="", duration_ms=1)
        self.assertEqual(out, "filtered")
        self.assertEqual(sorted(seen), ["args", "ask", "cache_dir", "log", "profile", "result", "session_id",
                                        "settings", "tool_name"])
        self.assertEqual(seen["cache_dir"], Path(self.tmp.name) / "home" / "cache" / "jev")
        self.assertIs(seen["log"], self.plugin.jev_log.write)
        self.assertEqual(seen["settings"]["min_chars"], 8000)

    def test_tool_results_turns_off(self):
        module = mock.Mock(transform=mock.Mock(return_value="filtered"))
        with mock.patch.object(self.plugin, "load_config", return_value=self.config_with(tool_results={"enabled": False})), \
                mock.patch.object(self.plugin.importlib, "import_module", return_value=module):
            self.assertIsNone(self.plugin._transform_tool_result(tool_name="terminal", args={}, result="r",
                                                                 session_id="s"))
        module.transform.assert_not_called()

    def test_middleware_passes_other_tools_through(self):
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return "result"

        out = self.plugin._tool_execution(tool_name="terminal", args={"command": "ls"}, next_call=next_call)
        self.assertEqual(out, "result")
        self.assertEqual(calls, [None])
        self.assertEqual(read_records(self.log_dir, "decisions"), [])


if __name__ == "__main__":
    unittest.main()
