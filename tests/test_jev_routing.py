"""Offline tests for card model routing (Part A) in the jev plugin, the control
group and the reassignment after change requests (card t_df87b851).

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
    TEST_KEY, FakeTypeSafe, all_text_under, build_board_db, fake_hermes_calls, isolated_env, read_records,
    write_fake_hermes,
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
        # routes like the other three boards. Card t_f4ce916d: the shipped config.json names
        # exactly three GLM workers on every board.
        boards = self.config["routing"]["boards"]
        self.assertEqual(sorted(boards), ["anki", "cha-pt", "harness", "jobcron", "jss-genr"])
        glm_workers = {"jobcron": ["jobcron-worker-glm-1", "jobcron-worker-glm-2", "jobcron-worker-glm-3"],
                       "cha-pt": ["chapt-worker-glm-1", "chapt-worker-glm-2", "chapt-worker-glm-3"],
                       "harness": ["harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-3"],
                       "jss-genr": ["jss-worker-glm-1", "jss-worker-glm-2", "jss-worker-glm-3"],
                       "anki": ["anki-worker-glm-1", "anki-worker-glm-2", "anki-worker-glm-3"]}
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

    # --- Part 2 criteria (card t_df87b851) --------------------------------------------

    def test_route_criteria_are_the_part_2_texts_on_every_board(self):
        expected = {
            "easy": ("The card names the exact files to change and the exact command that checks the result, "
                     "and the worker has no behaviour to work out. The topic of the card does not matter."),
            "medium": ("A fully specified change across several files with no design decision. This includes "
                       "tests, fixtures, user-facing text and wiring inside security, migration or deployment "
                       "features."),
            "hard": ("Everything else: a design decision, a fault with an unknown cause, logic for authentication, "
                     "secrets or payment, writing a database migration, or commands that will be run against "
                     "production, including deployment guides."),
        }
        for board, entry in CONFIG["routing"]["boards"].items():
            with self.subTest(board=board):
                self.assertEqual({r["name"]: r["criterion"] for r in entry["routes"]}, expected)
        procedure = (ROOT / "procedures" / "jev-plugin.md").read_text(encoding="utf-8")
        for text in expected.values():
            self.assertIn(text, procedure)
        self.fake.choice("hard", probs(hard=1.0))
        self.create(self.card())
        self.assertEqual(self.fake.requests[-1][1]["questions"]["route"]["criteria"], expected)

    # --- control group (Part 3, card t_df87b851) -------------------------------------------

    def control_state(self):
        return json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))

    def test_tenth_qualifying_card_is_the_control_group(self):
        self.fake.choice("easy", probs(easy=0.9, medium=0.05, hard=0.05))
        sent = [self.create(self.card())[0].calls[0] for _ in range(10)]
        self.assertEqual([s["assignee"] for s in sent[:9]],
                         ["harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-3",
                          "harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-3",
                          "harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-3"])
        self.assertIsNone(sent[9])  # the tenth card is created exactly as the orchestrator asked
        record = self.last_decision()
        self.assertEqual((record["event"], record["applied"], record["not_applied_reason"], record["route"]),
                         ("route", False, "control_group", "easy"))
        self.assertAlmostEqual(record["probabilities"]["easy"], 0.9)
        self.assertEqual((record["original_assignee"], record["new_assignee"]), ("harness-worker", "harness-worker"))
        self.assertEqual(record["task_id"], "t_0a1b2c3d")
        # The alternation counter did not advance for the control card: the eleventh card gets glm-1.
        self.assertEqual(self.control_state()["counters"], {"harness": 0})
        self.assertEqual(self.create(self.card())[0].calls[0]["assignee"], "harness-worker-glm-1")
        decisions = read_records(self.log_dir, "decisions")
        self.assertEqual([r["not_applied_reason"] for r in decisions], [None] * 9 + ["control_group", None])

    def test_control_group_counter_is_per_board_and_route(self):
        self.fake.choice("easy", probs(easy=0.9))
        for _ in range(9):
            self.create(self.card())
        self.fake.choice("medium", probs(medium=0.9))
        self.assertIsNotNone(self.create(self.card())[0].calls[0])  # first medium card on harness
        self.fake.choice("easy", probs(easy=0.9))
        for _ in range(9):
            self.assertIsNotNone(self.create(self.card(board="cha-pt", assignee="chapt-worker"))[0].calls[0])
        self.assertIsNone(self.create(self.card())[0].calls[0])  # tenth easy card on harness
        self.assertEqual(self.control_state()["control_group_counters"],
                         {"harness": {"easy": 0, "medium": 1}, "cha-pt": {"easy": 9}})

    def test_cards_that_do_not_qualify_do_not_count(self):
        self.fake.choice("easy", probs(easy=0.9))
        for _ in range(9):
            self.create(self.card())
        self.create(self.card(model="glm-5.3"))                  # model_set
        self.create(self.card(assignee="harness-reviewer"))      # assignee_not_listed
        self.fake.choice("easy", probs(easy=0.55, hard=0.45))
        self.create(self.card())                                 # below_threshold
        self.fake.choice("hard", probs(hard=0.9))
        self.create(self.card())                                 # hard: applied, not counted
        self.fake.choice("easy", probs(easy=0.9))
        self.assertIsNone(self.create(self.card())[0].calls[0])
        self.assertEqual(self.last_decision()["not_applied_reason"], "control_group")

    def test_control_group_every_zero_or_invalid_turns_it_off(self):
        for value in (0, None, "5", -5, True):
            with self.subTest(value=value):
                config = json.loads(json.dumps(self.config))
                if value is None:
                    del config["routing"]["control_group_every"]
                else:
                    config["routing"]["control_group_every"] = value
                self.fake.choice("easy", probs(easy=0.9))
                sent = [self.create(self.card(), config=config)[0].calls[0] for _ in range(6)]
                self.assertTrue(all(s is not None for s in sent))
                self.assertNotIn("control_group",
                                 [r["not_applied_reason"] for r in read_records(self.log_dir, "decisions")])

    def test_control_group_every_two(self):
        self.config["routing"]["control_group_every"] = 2
        self.fake.choice("medium", probs(medium=0.9))
        sent = [self.create(self.card())[0].calls[0] for _ in range(4)]
        self.assertEqual([s is None for s in sent], [False, True, False, True])

    def test_control_group_state_error_leaves_card_unchanged(self):
        self.fake.choice("easy", probs(easy=0.9))
        with mock.patch.object(routing, "control_group_turn", side_effect=OSError("state file")):
            create, _ = self.create(self.card())
        self.assertEqual(self.assert_unchanged(create, "plugin_error")["error_class"], "OSError")

    def test_control_group_jev_error_leaves_card_unchanged(self):
        self.fake.mode = "http_error"
        create, _ = self.create(self.card())
        self.assert_unchanged(create, "jev_error")
        self.assertFalse((self.log_dir / "routing-state.json").exists())

    # --- alternation and body rewrite -----------------------------------------------

    def test_alternation_between_glm_workers(self):
        self.fake.choice("easy", probs(easy=0.9))
        chosen = [self.create(self.card())[0].calls[0]["assignee"] for _ in range(3)]
        # The three GLM workers of the board take turns (card t_f4ce916d).
        self.assertEqual(chosen, ["harness-worker-glm-1", "harness-worker-glm-2", "harness-worker-glm-3"])
        other = self.create(self.card(board="cha-pt", assignee="chapt-worker"))[0].calls[0]["assignee"]
        self.assertEqual(other, "chapt-worker-glm-1")
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counters"], {"harness": 0, "cha-pt": 1})
        self.assertEqual(state["control_group_counters"], {"harness": {"easy": 3}, "cha-pt": {"easy": 1}})

    def test_next_glm_worker_returns_each_of_the_three_workers_once_in_three_calls(self):
        for board, entry in CONFIG["routing"]["boards"].items():
            workers = entry["glm_workers"]
            with self.subTest(board=board), tempfile.TemporaryDirectory(prefix="jev-rotation-") as directory:
                chosen = [routing.next_glm_worker(board, workers, Path(directory)) for _ in range(3)]
                self.assertEqual(len(workers), 3)
                self.assertEqual(chosen, workers)
                # The fourth call starts the next turn with the first worker.
                self.assertEqual(routing.next_glm_worker(board, workers, Path(directory)), workers[0])

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


GLM_CARD = "t_5a1e0001"
CLAUDE_CARD = "t_c1a0de01"


class RequestChangesTests(unittest.TestCase):
    """Part 4 (card t_df87b851): after the fifth change request a GLM card goes to a Claude worker.

    The board database is synthetic and every board change goes through the fake
    ``hermes`` command, which applies ``set-model`` and ``reassign`` to it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = isolated_env(self.dir)
        self.db = Path(env["HERMES_KANBAN_HOME"]) / "kanban" / "boards" / "harness" / "kanban.db"
        build_board_db(self.db, [(GLM_CARD, "ready", "harness-worker-glm-1"),
                                 ("t_5a1e0002", "ready", "harness-worker-glm-2"),
                                 (CLAUDE_CARD, "ready", "harness-worker")])
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        self.log_dir = self.dir / "logs"
        env.update({"FAKE_HERMES_LOG": str(self.calls_log), "FAKE_KANBAN_DB": str(self.db),
                    "HERMES_PROFILE": "harness-reviewer", "HERMES_KANBAN_TASK": GLM_CARD,
                    "HERMES_KANBAN_BOARD": "harness"})
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = json.loads(json.dumps(CONFIG))

    def add_change_requests(self, task_id, count):
        import sqlite3
        conn = sqlite3.connect(self.db)
        for _ in range(count):
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, 0)",
                         (task_id, "changes_requested", json.dumps({"implementer": "x"})))
        conn.commit()
        conn.close()

    def card(self, task_id):
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT status, assignee, model_override FROM tasks WHERE id=?",
                                (task_id,)).fetchone()
        finally:
            conn.close()

    def set_card(self, task_id, **columns):
        import sqlite3
        conn = sqlite3.connect(self.db)
        for column, value in columns.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?", (value, task_id))
        conn.commit()
        conn.close()

    def request_changes(self, args=None, result='{"ok": true, "task_id": "t_5a1e0001", "status": "ready"}',
                        config=None):
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return result

        out = routing.handle_request_changes(args if args is not None else {"reason": "fix the test"}, next_call,
                                             config=config or self.config, command=self.hermes,
                                             state_dir=self.log_dir)
        self.assertEqual(calls, [None])  # the call runs once, with its own arguments
        self.assertEqual(out, result)    # and its result is returned unchanged
        return out

    def escalations(self):
        return [r for r in read_records(self.log_dir, "decisions") if r["event"] == "escalate"]

    def test_fifth_change_request_clears_override_and_reassigns(self):
        self.set_card(GLM_CARD, model_override="glm-5.3-flash")
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", GLM_CARD, "none"],
            ["kanban", "--board", "harness", "reassign", GLM_CARD, "harness-worker", "--reclaim"],
        ])
        self.assertEqual(tuple(self.card(GLM_CARD)), ("ready", "harness-worker", None))
        [record] = self.escalations()
        self.assertEqual({k: record[k] for k in ("board", "task_id", "original_assignee", "new_assignee",
                                                  "change_requests", "applied", "error_class")},
                         {"board": "harness", "task_id": GLM_CARD, "original_assignee": "harness-worker-glm-1",
                          "new_assignee": "harness-worker", "change_requests": 5, "applied": True,
                          "error_class": None})

    def test_fourth_change_request_changes_nothing(self):
        self.add_change_requests(GLM_CARD, 4)
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-1")
        self.assertEqual(self.escalations(), [])

    def test_claude_implemented_card_is_never_reassigned(self):
        self.add_change_requests(CLAUDE_CARD, 7)
        self.request_changes({"task_id": CLAUDE_CARD, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(CLAUDE_CARD)[1], "harness-worker")
        self.assertEqual(self.escalations(), [])

    def test_sixth_change_request_after_escalation_changes_nothing(self):
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.add_change_requests(GLM_CARD, 1)
        self.request_changes()
        self.assertEqual(len(fake_hermes_calls(self.calls_log)), 2)
        self.assertEqual(len(self.escalations()), 1)

    def test_max_glm_change_requests_zero_or_invalid_turns_it_off(self):
        self.add_change_requests(GLM_CARD, 9)
        for value in (0, None, "5", -1, False):
            with self.subTest(value=value):
                config = json.loads(json.dumps(self.config))
                if value is None:
                    del config["routing"]["max_glm_change_requests"]
                else:
                    config["routing"]["max_glm_change_requests"] = value
                self.request_changes(config=config)
        self.config["routing"]["enabled"] = False
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.escalations(), [])

    def test_claude_worker_from_the_route_record(self):
        routing.jev_log.write("decisions", {"event": "route", "board": "harness", "task_id": GLM_CARD,
                                            "original_assignee": "harness-worker-2",
                                            "new_assignee": "harness-worker-glm-1", "applied": True})
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-2")
        self.assertEqual(self.escalations()[0]["new_assignee"], "harness-worker-2")

    def test_claude_workers_alternate_without_a_route_record(self):
        self.add_change_requests(GLM_CARD, 5)
        self.add_change_requests("t_5a1e0002", 5)
        self.request_changes()
        self.request_changes({"task_id": "t_5a1e0002", "reason": "x"})
        self.assertEqual((self.card(GLM_CARD)[1], self.card("t_5a1e0002")[1]),
                         ("harness-worker", "harness-worker-2"))
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["escalation_counters"], {"harness": 0})
        self.assertNotIn("counters", state)  # the GLM worker alternation is a separate section

    def test_card_claimed_by_the_dispatcher_in_between_is_reclaimed(self):
        self.set_card(GLM_CARD, status="running")
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(tuple(self.card(GLM_CARD))[:2], ("ready", "harness-worker"))

    def test_failed_set_model_leaves_card_unchanged(self):
        self.add_change_requests(GLM_CARD, 5)
        with mock.patch.dict(os.environ, {"FAKE_HERMES_EXIT": "3"}):
            self.request_changes()
        self.assertEqual([c[3] for c in fake_hermes_calls(self.calls_log)], ["set-model"])  # no reassign
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-1")
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["error_class"], record["new_assignee"]),
                         (False, "CommandFailed", "harness-worker-glm-1"))

    def test_failed_reassign_is_logged_and_result_unchanged(self):
        self.add_change_requests(GLM_CARD, 5)
        with mock.patch.object(routing.peak_hold, "run_kanban",
                               side_effect=[(True, None), (False, "CommandTimeout")]) as run:
            self.request_changes()
        self.assertEqual(run.call_count, 2)
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["error_class"]), (False, "CommandTimeout"))

    def test_missing_hermes_command_is_logged(self):
        self.add_change_requests(GLM_CARD, 5)
        routing.handle_request_changes({}, lambda payload=None: '{"ok": true}', config=self.config,
                                       command=str(self.dir / "no-such-hermes"), state_dir=self.log_dir)
        self.assertEqual(self.escalations()[0]["error_class"], "CommandNotFound")
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-1")

    def test_failed_call_changes_nothing(self):
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes(result='{"error": "could not request changes"}')
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.escalations(), [])

    def test_board_database_error_leaves_result_unchanged(self):
        self.add_change_requests(GLM_CARD, 5)
        self.db.unlink()
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["not_applied_reason"], record["error_class"]),
                         (False, "plugin_error", "FileNotFoundError"))

    def test_exception_in_next_call_propagates_without_escalation(self):
        self.add_change_requests(GLM_CARD, 5)

        def next_call(payload=None):
            raise RuntimeError("tool failed")

        with self.assertRaises(RuntimeError):
            routing.handle_request_changes({}, next_call, config=self.config, command=self.hermes,
                                           state_dir=self.log_dir)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    # --- step 3: the "Assigned worker EXACT" body line (review round 1 of t_df87b851) ---

    def body(self, task_id):
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
        finally:
            conn.close()

    def test_fifth_change_request_names_the_claude_worker_on_the_assigned_worker_line(self):
        self.set_card(GLM_CARD, model_override="glm-5.3-flash",
                      body="Repository /tmp/x ONLY.\nAssigned worker EXACT harness-worker-glm-1.\n"
                           "Reviewer EXACT harness-reviewer.\n")
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        calls = fake_hermes_calls(self.calls_log)
        self.assertEqual([c[3] for c in calls], ["set-model", "reassign", "edit"])
        self.assertEqual(calls[2][:5], ["kanban", "--board", "harness", "edit", GLM_CARD])
        self.assertEqual(self.body(GLM_CARD), "Repository /tmp/x ONLY.\nAssigned worker EXACT harness-worker.\n"
                                              "Reviewer EXACT harness-reviewer.\n")
        self.assertEqual(tuple(self.card(GLM_CARD)), ("ready", "harness-worker", None))
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["assigned_worker_line"],
                          record["assigned_worker_line_error_class"]), (True, "rewritten", None))

    def test_mention_inside_another_line_and_other_profiles_are_unchanged(self):
        body = ("Note: the plugin wrote Assigned worker EXACT harness-worker-glm-1 at creation.\n"
                "Assigned worker EXACT harness-worker-glm-1.\n"
                "Assigned worker EXACT harness-worker-glm-10 (other card).\n"
                "  Assigned worker EXACT harness-worker-glm-1 (indented).\n")
        self.set_card(GLM_CARD, body=body)
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(self.body(GLM_CARD), body.replace(
            "\nAssigned worker EXACT harness-worker-glm-1.\n", "\nAssigned worker EXACT harness-worker.\n"))

    def test_card_without_the_line_gets_no_edit_command(self):
        for body in (None, "Repository /tmp/x ONLY.\nAssigned worker EXACT harness-worker-2.\n"):
            with self.subTest(body=body):
                self.calls_log.unlink(missing_ok=True)
                (self.log_dir / "decisions.jsonl").unlink(missing_ok=True)
                self.set_card(GLM_CARD, assignee="harness-worker-glm-1", body=body)
                self.add_change_requests(GLM_CARD, 5)
                self.request_changes()
                self.assertEqual([c[3] for c in fake_hermes_calls(self.calls_log)], ["set-model", "reassign"])
                self.assertEqual(self.body(GLM_CARD), body)
                [record] = self.escalations()
                self.assertEqual((record["applied"], record["assigned_worker_line"]), (True, "no_line"))

    def test_failed_edit_is_logged_and_result_and_card_unchanged(self):
        body = f"{SENTINEL}\nAssigned worker EXACT harness-worker-glm-1.\n"
        self.set_card(GLM_CARD, body=body)
        self.add_change_requests(GLM_CARD, 5)
        real_run = routing.peak_hold.run_kanban

        def run_kanban(config, board, args, command=None):
            if args[0] == "edit":
                return False, "CommandFailed"
            return real_run(config, board, args, command)

        with mock.patch.object(routing.peak_hold, "run_kanban", side_effect=run_kanban):
            self.request_changes()  # asserts the result is unchanged
        self.assertEqual(self.body(GLM_CARD), body)
        self.assertEqual(tuple(self.card(GLM_CARD))[:2], ("ready", "harness-worker"))  # reassignment kept
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["error_class"], record["assigned_worker_line"],
                          record["assigned_worker_line_error_class"]), (True, None, "failed", "CommandFailed"))
        self.assertNotIn(SENTINEL, all_text_under(self.log_dir))

    def test_body_too_long_for_one_argument_is_not_sent(self):
        body = "Assigned worker EXACT harness-worker-glm-1.\n" + "x" * routing.MAX_BODY_ARGUMENT_BYTES
        self.set_card(GLM_CARD, body=body)
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual([c[3] for c in fake_hermes_calls(self.calls_log)], ["set-model", "reassign"])
        self.assertEqual(self.body(GLM_CARD), body)
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["assigned_worker_line"],
                          record["assigned_worker_line_error_class"]), (True, "failed", "BodyTooLong"))

    def test_read_error_and_exception_return_failed_without_raising(self):
        with mock.patch.object(routing.peak_hold, "kanban_db_path", side_effect=OSError("unreadable")):
            out = routing.rewrite_body_after_escalation(self.config, "harness", GLM_CARD, "harness-worker-glm-1",
                                                        "harness-worker", self.hermes)
        self.assertEqual(out, {"assigned_worker_line": "failed", "assigned_worker_line_error_class": "OSError"})
        with mock.patch.object(routing, "rewrite_assigned_worker", side_effect=RuntimeError("x")):
            out = routing.rewrite_body_after_escalation(self.config, "harness", GLM_CARD, "harness-worker-glm-1",
                                                        "harness-worker", self.hermes)
        self.assertEqual(out["assigned_worker_line_error_class"], "RuntimeError")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_body_with_sentinel_never_reaches_a_log_file(self):
        self.set_card(GLM_CARD, body=f"{SENTINEL} intro\n-{SENTINEL}\nAssigned worker EXACT harness-worker-glm-1.\n")
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(self.body(GLM_CARD),
                         f"{SENTINEL} intro\n-{SENTINEL}\nAssigned worker EXACT harness-worker.\n")
        self.assertNotIn(SENTINEL, all_text_under(self.log_dir))

    def test_unrecognized_arguments_are_not_used_or_logged(self):
        self.add_change_requests(GLM_CARD, 5)
        for args in ({"task_id": SENTINEL, "reason": SENTINEL}, {"board": SENTINEL, "reason": SENTINEL},
                     {"task_id": "t_ffff0000", "reason": SENTINEL}):  # well formed, no such card
            self.request_changes(args)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.request_changes({"task_id": GLM_CARD, "reason": SENTINEL})
        self.assertEqual(len(self.escalations()), 1)
        self.assertNotIn(SENTINEL, all_text_under(self.log_dir))


if __name__ == "__main__":
    unittest.main()
