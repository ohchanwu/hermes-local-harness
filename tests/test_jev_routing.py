"""Offline tests for card model routing (Part A) in the jev plugin.

Jev is the local fake TypeSafe endpoint from tests/test_jev_client.py. The
time is a Saturday so the peak-hours hold never applies here (see
tests/test_jev_peak_hold.py for the hold). All profiles, boards and card ids
are synthetic or taken from the plugin configuration.
"""
from __future__ import annotations

import functools
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "plugins" / "jev"))
sys.path.insert(0, str(ROOT / "plugins"))

from test_jev_client import (  # noqa: E402
    TEST_KEY, FakeTypeSafe, all_text_under, fake_hermes_calls, isolated_env, read_records, write_fake_hermes,
)

import jev_client  # noqa: E402
import routing  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
SATURDAY = datetime(2026, 11, 14, 16, 0, tzinfo=KST)
SENTINEL = "JEVSENTINEL7c41d"
CONFIG = json.loads((ROOT / "plugins" / "jev" / "config.json").read_text(encoding="utf-8"))
ALL_ROUTES = {"easy": 0.0, "medium": 0.0, "hard": 0.0}


def probs(**values):
    return {**ALL_ROUTES, **values}


class FakeCreate:
    """Stands in for ``next_call``: records what the tool would receive."""

    def __init__(self, task_id: "str | None" = "t_0a1b2c3d"):
        self.task_id = task_id
        self.calls = []

    def __call__(self, payload=None):
        self.calls.append(payload)
        if self.task_id is None:
            return json.dumps({"error": "rejected"})
        return json.dumps({"ok": True, "task_id": self.task_id, "status": "ready"})


class RoutingTests(unittest.TestCase):
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
        self.dir = Path(self.tmp.name)
        env = isolated_env(self.dir)
        env["HERMES_KANBAN_BOARD"] = ""
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log_dir = self.dir / "logs"
        self.config = json.loads(json.dumps(CONFIG))
        self.config["jev"] = self.fake.settings()

    def create(self, args, next_call=None, config=None):
        config = config or self.config
        next_call = next_call or FakeCreate()
        ask = functools.partial(jev_client.ask, settings=config["jev"])
        result = routing.handle_create(args, next_call, config=config, ask=ask, now=SATURDAY)
        return next_call, result

    def card(self, **overrides):
        args = {"title": "Fix a typo", "body": "Repository x.\nAssigned worker EXACT harness-worker.\n"
                "Reviewer EXACT harness-reviewer.\n", "assignee": "harness-worker", "board": "harness"}
        args.update(overrides)
        return args

    def last_decision(self):
        return read_records(self.log_dir, "decisions")[-1]

    # --- routes applied -----------------------------------------------------------

    def test_easy_route_applied(self):
        self.fake.choice("easy", probs(easy=0.9, medium=0.08, hard=0.02))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3-flash", "zai"))
        record = self.last_decision()
        self.assertEqual((record["event"], record["route"], record["applied"]), ("route", "easy", True))
        self.assertEqual((record["original_assignee"], record["new_assignee"]), ("harness-worker", "harness-worker-glm-1"))
        self.assertEqual(record["task_id"], "t_0a1b2c3d")
        self.assertEqual(record["board"], "harness")
        self.assertEqual(record["jev_input_tokens"], 321)
        self.assertIsNotNone(record["jev_latency_ms"])
        self.assertAlmostEqual(record["probabilities"]["easy"], 0.9)
        question = self.fake.requests[-1][1]["questions"]["route"]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(sorted(question["criteria"]), ["easy", "hard", "medium"])

    def test_medium_route_applied(self):
        self.fake.choice("medium", probs(medium=0.7, hard=0.3))
        create, _ = self.create(self.card(board="jobcron", assignee="jobcron-worker-2"))
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "jobcron-worker-glm-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        self.assertTrue(self.last_decision()["applied"])

    def test_hard_route_applied_changes_nothing(self):
        self.fake.choice("hard", probs(hard=0.95, medium=0.05))
        args = self.card(board="cha-pt", assignee="chapt-worker")
        create, _ = self.create(args)
        self.assertEqual(create.calls, [None])
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["new_assignee"]), ("hard", True, "chapt-worker"))

    def test_state_is_title_and_body_cut_at_limit(self):
        self.fake.choice("hard", probs(hard=1.0))
        self.create(self.card(body="b" * 70000))
        state = self.fake.requests[-1][1]["state"]
        self.assertEqual(state["title"], "Fix a typo")
        self.assertEqual(len(state["body"]), 60000)

    # --- routes not applied --------------------------------------------------------

    def assert_unchanged(self, create, reason):
        self.assertEqual(create.calls, [None])
        record = self.last_decision()
        self.assertFalse(record["applied"])
        self.assertEqual(record["not_applied_reason"], reason)
        return record

    def test_not_applied_when_model_set(self):
        self.fake.choice("easy", probs(easy=0.99))
        create, _ = self.create(self.card(model="claude-opus-5-5", provider="claude-subscription"))
        record = self.assert_unchanged(create, "model_set")
        self.assertEqual(record["orchestrator_model"], "claude-opus-5-5")
        self.assertEqual(record["route"], "easy")  # Jev's choice is still logged

    def test_model_not_in_configuration_is_logged_as_unrecognized(self):
        self.fake.choice("easy", probs(easy=0.99))
        create, _ = self.create(self.card(model="some-other-model-1"))
        self.assertEqual(self.assert_unchanged(create, "model_set")["orchestrator_model"], "unrecognized")

    def test_not_applied_when_assignee_not_listed(self):
        self.fake.choice("easy", probs(easy=0.99))
        create, _ = self.create(self.card(assignee="harness-reviewer"))
        record = self.assert_unchanged(create, "assignee_not_listed")
        self.assertIsNone(record["original_assignee"])

    def test_not_applied_below_threshold(self):
        self.fake.choice("easy", probs(easy=0.55, medium=0.45))
        create, _ = self.create(self.card())
        self.assert_unchanged(create, "below_threshold")

    def test_routing_disabled(self):
        self.config["routing"]["enabled"] = False
        create, _ = self.create(self.card())
        self.assert_unchanged(create, "routing_disabled")
        self.assertEqual(self.fake.requests, [])

    def test_every_board_has_glm_routing(self):
        # Card t_71b4ef4a: jss-genr and anki have GLM workers and the easy and medium
        # routes like the other three boards.
        boards = self.config["routing"]["boards"]
        self.assertEqual(sorted(boards), ["anki", "cha-pt", "harness", "jobcron", "jss-genr"])
        glm_workers = {"jobcron": ["jobcron-worker-glm-1", "jobcron-worker-glm-2"],
                       "cha-pt": ["chapt-worker-glm-1", "chapt-worker-glm-2"],
                       "harness": ["harness-worker-glm-1", "harness-worker-glm-2"],
                       "jss-genr": ["jss-worker-glm-1", "jss-worker-glm-2"],
                       "anki": ["anki-worker-glm-1", "anki-worker-glm-2"]}
        reference = boards["harness"]["routes"]
        for board, entry in boards.items():
            with self.subTest(board=board):
                self.assertEqual(entry["glm_workers"], glm_workers[board])
                self.assertEqual(entry["routes"], reference)
                self.assertEqual({r["name"]: r["enabled"] for r in entry["routes"]},
                                 {"easy": True, "medium": True, "hard": True})

    def test_jss_and_anki_routes_applied(self):
        cases = (("jss-genr", "jss-worker", "easy", "jss-worker-glm-1", "glm-5.3-flash"),
                 ("anki", "anki-worker-2", "medium", "anki-worker-glm-1", "glm-5.3"))
        for board, assignee, route, glm_worker, model in cases:
            with self.subTest(board=board):
                self.fake.choice(route, probs(**{route: 0.9, "hard": 0.1}))
                create, _ = self.create(self.card(board=board, assignee=assignee))
                sent = create.calls[0]
                self.assertEqual(sent["assignee"], glm_worker)
                self.assertEqual((sent["model"], sent["provider"]), (model, "zai"))
                record = self.last_decision()
                self.assertEqual((record["board"], record["route"], record["applied"]), (board, route, True))

    def test_board_with_only_the_hard_route_is_not_asked(self):
        for route in self.config["routing"]["boards"]["jss-genr"]["routes"]:
            if route["name"] != "hard":
                route["enabled"] = False
        create, _ = self.create(self.card(board="jss-genr", assignee="jss-worker"))
        self.assert_unchanged(create, "single_route")
        self.assertEqual(self.fake.requests, [])

    def test_board_from_environment(self):
        self.fake.choice("easy", probs(easy=0.9))
        with mock.patch.dict(os.environ, {"HERMES_KANBAN_BOARD": "harness"}):
            create, _ = self.create(self.card(board=None))
        self.assertEqual(create.calls[0]["assignee"], "harness-worker-glm-1")

    # --- Jev failures leave the arguments unchanged -------------------------------------

    def test_jev_failures_leave_arguments_unchanged(self):
        cases = [("http_error", {}, "HTTPError"), ("timeout", {"timeout_seconds": 0.2}, "Timeout"),
                 ("not_json", {}, "UnexpectedResponse"), ("no_answers", {}, "UnexpectedResponse")]
        for mode, overrides, error_class in cases:
            with self.subTest(mode=mode):
                self.fake.mode = mode
                config = json.loads(json.dumps(self.config))
                config["jev"].update(overrides)
                create, _ = self.create(self.card(), config=config)
                record = self.assert_unchanged(create, "jev_error")
                self.assertEqual(record["error_class"], error_class)

    def test_missing_key_leaves_arguments_unchanged(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            create, _ = self.create(self.card())
        self.assertEqual(self.assert_unchanged(create, "jev_error")["error_class"], "MissingKey")

    def test_choice_outside_routes_is_unexpected(self):
        self.fake.choice("impossible", {"impossible": 1.0})
        create, _ = self.create(self.card())
        self.assertEqual(self.assert_unchanged(create, "jev_error")["error_class"], "UnexpectedResponse")

    def test_exception_before_next_call_runs_tool_unchanged(self):
        self.fake.choice("easy", probs(easy=0.9))
        with mock.patch.object(routing.peak_hold, "hold_active", side_effect=RuntimeError("boom")):
            create, _ = self.create(self.card())
        record = self.assert_unchanged(create, "plugin_error")
        self.assertEqual(record["error_class"], "RuntimeError")

    def test_every_call_writes_one_record(self):
        self.fake.choice("easy", probs(easy=0.9))
        self.create(self.card())
        self.create(self.card(model="glm-5.3"))
        self.create(self.card(assignee="harness-reviewer"))
        self.create(self.card(board="unknown-board"))
        records = read_records(self.log_dir, "decisions")
        self.assertEqual([r["event"] for r in records], ["route"] * 4)
        self.assertEqual(records[-1]["not_applied_reason"], "board_not_configured")

    def test_failed_create_records_no_task_id(self):
        self.fake.choice("easy", probs(easy=0.9))
        self.create(self.card(), next_call=FakeCreate(task_id=None))
        record = self.last_decision()
        self.assertIsNone(record["task_id"])
        self.assertEqual(record["not_applied_reason"], "create_failed")

    # --- alternation and body rewrite -----------------------------------------------

    def test_alternation_between_glm_workers(self):
        self.fake.choice("easy", probs(easy=0.9))
        chosen = [self.create(self.card())[0].calls[0]["assignee"] for _ in range(3)]
        self.assertEqual(chosen, ["harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-1"])
        other = self.create(self.card(board="cha-pt", assignee="chapt-worker"))[0].calls[0]["assignee"]
        self.assertEqual(other, "chapt-worker-glm-1")
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"counters": {"harness": 1, "cha-pt": 1}})

    def test_assigned_worker_line_rewrite(self):
        self.fake.choice("medium", probs(medium=0.8))
        body = ("Repository /x ONLY.\nAssigned worker EXACT harness-worker.\nReviewer EXACT harness-reviewer.\n"
                "Text that mentions Assigned worker EXACT harness-worker inside a line.\n")
        create, _ = self.create(self.card(body=body, reviewer="harness-reviewer"))
        sent = create.calls[0]
        self.assertIn("\nAssigned worker EXACT harness-worker-glm-1.\n", sent["body"])
        self.assertIn("\nReviewer EXACT harness-reviewer.\n", sent["body"])
        self.assertIn("mentions Assigned worker EXACT harness-worker inside", sent["body"])
        self.assertEqual(sent["reviewer"], "harness-reviewer")

    # --- logs hold no card text, tool arguments or key --------------------------------

    def test_sentinel_and_key_absent_from_logs(self):
        text_args = {
            "title": f"{SENTINEL} title", "body": f"Body {SENTINEL}\nAssigned worker EXACT harness-worker.\n",
            "tenant": SENTINEL, "workspace_kind": SENTINEL, "workspace_path": f"/tmp/{SENTINEL}",
            "idempotency_key": SENTINEL, "skills": [SENTINEL], "parents": [SENTINEL], "project": SENTINEL,
            "completion_contract": SENTINEL, "session_id": SENTINEL, "reviewer": SENTINEL, "priority": 1,
        }
        self.fake.choice("easy", probs(easy=0.9))
        self.create(self.card(**text_args))
        self.create(self.card(**text_args, model="glm-5.3"))
        self.fake.mode = "http_error"
        self.create(self.card(**text_args))
        # Identifier arguments that are not known profiles or boards are not logged either.
        self.fake.choice("easy", probs(easy=0.9))
        self.create(self.card(**text_args, assignee=SENTINEL))
        self.create(self.card(**text_args, board=SENTINEL))
        # model and provider arguments.
        self.create(self.card(**text_args, model=SENTINEL, provider=SENTINEL))
        self.create(self.card(**text_args, model=f"claude-{SENTINEL}", provider="zai"))
        self.assertEqual([r["orchestrator_model"] for r in read_records(self.log_dir, "decisions")[-2:]],
                         ["unrecognized", "unrecognized"])
        # kanban_request_review in a GLM worker session and kanban_unblock: every argument.
        hermes = write_fake_hermes(self.dir)
        calls_log = self.dir / "hermes-calls.jsonl"
        review_args = [
            {"task_id": SENTINEL, "board": "harness", "summary": SENTINEL, "metadata": {"x": SENTINEL},
             "reviewer": SENTINEL, "artifacts": [SENTINEL]},
            {"task_id": "t_feedc0de", "board": SENTINEL, "summary": SENTINEL},
            {"summary": SENTINEL, "board": f"harness {SENTINEL}"},
        ]
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "harness-worker-glm-1", "FAKE_HERMES_LOG": str(calls_log),
                                          "HERMES_KANBAN_TASK": "t_feedc0de"}):
            for args in review_args:
                routing.handle_request_review(args, lambda payload=None: '{"ok": true}', config=self.config,
                                              command=hermes)
        unblock_now = datetime(2026, 11, 11, 16, 0, tzinfo=KST)  # inside the window
        for args in ({"task_id": SENTINEL, "board": "harness"}, {"task_id": "t_0b10c4ed", "board": SENTINEL}):
            routing.handle_unblock(args, lambda payload=None: '{"ok": true}', config=self.config, now=unblock_now,
                                   command=hermes)
        records = read_records(self.log_dir, "decisions")
        reviews = [r for r in records if r["event"] == "clear_override"]
        self.assertEqual([(r["task_id"], r["board"], r["not_applied_reason"]) for r in reviews],
                         [(None, "harness", "task_id_not_recognized"), ("t_feedc0de", None, "board_not_configured"),
                          ("t_feedc0de", None, "board_not_configured")])
        self.assertEqual(fake_hermes_calls(calls_log), [])  # no command with an argument that was not recognized
        logged = all_text_under(self.log_dir)
        self.assertEqual(len([r for r in records if r["event"] == "route"]), 7)
        self.assertNotIn(SENTINEL, logged)
        self.assertNotIn(TEST_KEY, logged)
        # Jev did receive the card text (it is the state).
        self.assertIn(SENTINEL, json.dumps(self.fake.requests[0][1]))


class ReviewHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        env = isolated_env(self.dir)
        env.update({"FAKE_HERMES_LOG": str(self.calls_log), "HERMES_KANBAN_TASK": "t_feedc0de",
                    "HERMES_KANBAN_BOARD": "harness"})
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = json.loads(json.dumps(CONFIG))

    def review(self, profile):
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return '{"ok": true}'

        with mock.patch.dict(os.environ, {"HERMES_PROFILE": profile}):
            routing.handle_request_review({"summary": "done"}, next_call, config=self.config, command=self.hermes)
        return calls

    def test_glm_worker_clears_override_before_review(self):
        calls = self.review("harness-worker-glm-2")
        self.assertEqual(calls, [None])
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "set-model", "t_feedc0de", "none"]])
        record = read_records(self.dir / "logs", "decisions")[-1]
        self.assertEqual((record["event"], record["task_id"], record["applied"]), ("clear_override", "t_feedc0de", True))

    def test_claude_worker_does_not_clear(self):
        self.assertEqual(self.review("harness-worker"), [None])
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_board_not_configured_is_not_used_or_logged(self):
        calls = []
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "harness-worker-glm-1"}):
            routing.handle_request_review({"board": "not-a-configured-board"}, lambda p=None: calls.append(p),
                                          config=self.config, command=self.hermes)
        self.assertEqual(calls, [None])
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        record = read_records(self.dir / "logs", "decisions")[-1]
        self.assertEqual((record["board"], record["applied"], record["not_applied_reason"]),
                         (None, False, "board_not_configured"))

    def test_failed_clear_still_requests_review(self):
        with mock.patch.dict(os.environ, {"FAKE_HERMES_EXIT": "3"}):
            calls = self.review("jobcron-worker-glm-1")
        self.assertEqual(calls, [None])
        record = read_records(self.dir / "logs", "decisions")[-1]
        self.assertEqual((record["applied"], record["error_class"]), (False, "CommandFailed"))


if __name__ == "__main__":
    unittest.main()
