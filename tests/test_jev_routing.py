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
ALL_ROUTES = {"easy": 0.0, "medium": 0.0, "hard": 0.0, "very_hard": 0.0}


def probs(**values):
    return {**ALL_ROUTES, **values}


def glm_workers_route_config():
    """A deep copy of the shipped configuration in which the routes ``easy`` and
    ``medium`` of every board name ``glm_workers`` in ``assignee_from``, as they
    did before card t_cf518fd0, so that the two workers of ``glm_workers`` take
    turns. Card t_cf518fd0 gave ``easy`` the list ``easy_route_workers`` and
    ``medium`` the list ``medium_route_workers``; the turns of a two-name list
    are still code that the plugin runs for any list that a route names."""
    config = json.loads(json.dumps(CONFIG))
    for board in config["routing"]["boards"].values():
        for route in board["routes"]:
            if route["name"] in ("easy", "medium"):
                route["assignee_from"] = "glm_workers"
    return config


def two_list_config():
    """A deep copy of the configuration of ``glm_workers_route_config`` changed for
    board ``harness`` only: ``harness-worker-glm-hard-1`` moves from ``glm_workers`` to
    the new list ``glm_max_workers``, and the route ``hard`` names that list in
    ``assignee_from`` with ``model`` ``glm-5.3`` and ``provider`` ``zai``."""
    config = glm_workers_route_config()
    board = config["routing"]["boards"]["harness"]
    board["glm_workers"] = ["harness-worker-glm-easy-1", "harness-worker-glm-medium-1"]
    board["glm_max_workers"] = ["harness-worker-glm-hard-1"]
    route = next(r for r in board["routes"] if r["name"] == "hard")
    route["assignee_from"] = "glm_max_workers"
    route["model"] = "glm-5.3"
    route["provider"] = "zai"
    return config


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
        self.fake.choice("easy", probs(easy=0.9, medium=0.08, hard=0.01, very_hard=0.01))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-easy-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3-flash", "zai"))
        record = self.last_decision()
        self.assertEqual((record["event"], record["route"], record["applied"]), ("route", "easy", True))
        self.assertEqual((record["original_assignee"], record["new_assignee"]), ("harness-worker", "harness-worker-glm-easy-1"))
        self.assertEqual(record["task_id"], "t_0a1b2c3d")
        self.assertEqual(record["board"], "harness")
        self.assertEqual(record["jev_input_tokens"], 321)
        self.assertIsNotNone(record["jev_latency_ms"])
        self.assertAlmostEqual(record["probabilities"]["easy"], 0.9)
        question = self.fake.requests[-1][1]["questions"]["route"]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(sorted(question["criteria"]), ["easy", "hard", "medium", "very_hard"])

    def test_medium_route_applied(self):
        self.fake.choice("medium", probs(medium=0.7, hard=0.3))
        create, _ = self.create(self.card(board="jobcron", assignee="jobcron-worker-2"))
        sent = create.calls[0]
        # Card t_cf518fd0: a `medium` card goes to the second GLM worker of the board.
        self.assertEqual(sent["assignee"], "jobcron-worker-glm-medium-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        self.assertTrue(self.last_decision()["applied"])

    def test_hard_route_applies_the_worker_of_glm_max_workers(self):
        # Card t_3c7a581d: a `hard` card goes to the profile of the board's
        # `glm_max_workers` list, with model `glm-5.3` and provider `zai`. Card
        # t_18a2dc93 gave that list two names; the first card gets the first name.
        self.fake.choice("hard", probs(hard=0.95, medium=0.05))
        args = self.card(board="cha-pt", assignee="chapt-worker")
        create, _ = self.create(args)
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "chapt-worker-glm-hard-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["applied_route"], record["new_assignee"]),
                         ("hard", True, "hard", "chapt-worker-glm-hard-1"))
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counters"], {"cha-pt:glm_max_workers": 1})

    def test_very_hard_route_changes_nothing(self):
        # A `very_hard` card is created exactly as the orchestrator asked: the
        # Claude worker the orchestrator named, with that profile's own model.
        self.fake.choice("very_hard", probs(very_hard=0.95, medium=0.05))
        args = self.card(board="cha-pt", assignee="chapt-worker")
        create, _ = self.create(args)
        self.assertEqual(create.calls, [None])
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["applied_route"], record["new_assignee"],
                          record["glm_probability_sum"], record["not_applied_reason"]),
                         ("very_hard", True, "very_hard", "chapt-worker", 0.05, None))

    # --- two worker lists: the second list that a route names in assignee_from ----------

    def test_hard_route_applies_the_worker_of_the_second_list(self):
        config = two_list_config()
        config["jev"] = self.fake.settings()
        self.fake.choice("hard", probs(hard=0.95, medium=0.05))
        create, _ = self.create(self.card(), config=config)
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-hard-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        record = self.last_decision()
        self.assertEqual((record["event"], record["applied"], record["applied_route"], record["new_assignee"]),
                         ("route", True, "hard", "harness-worker-glm-hard-1"))
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counters"], {"harness:glm_max_workers": 0})

    def test_second_list_card_does_not_advance_the_glm_workers_counter(self):
        config = two_list_config()
        config["jev"] = self.fake.settings()
        answers = (("easy", probs(easy=0.95)), ("hard", probs(hard=0.95, medium=0.05)),
                   ("easy", probs(easy=0.95)), ("easy", probs(easy=0.95)))
        assignees = []
        for route, probabilities in answers:
            self.fake.choice(route, probabilities)
            assignees.append(self.create(self.card(), config=config)[0].calls[0]["assignee"])
        self.assertEqual(assignees, ["harness-worker-glm-easy-1", "harness-worker-glm-hard-1",
                                     "harness-worker-glm-medium-1", "harness-worker-glm-easy-1"])
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counters"], {"harness": 1, "harness:glm_max_workers": 0})

    def test_second_list_profile_is_recorded_as_original_assignee(self):
        config = two_list_config()
        config["jev"] = self.fake.settings()
        self.fake.choice("easy", probs(easy=0.9))
        create, _ = self.create(self.card(assignee="harness-worker-glm-hard-1"), config=config)
        record = self.assert_unchanged(create, "assignee_not_listed")
        self.assertEqual((record["original_assignee"], record["new_assignee"]),
                         ("harness-worker-glm-hard-1", "harness-worker-glm-hard-1"))

    def test_state_is_title_and_body_cut_at_limit(self):
        self.fake.choice("hard", probs(hard=1.0))
        self.create(self.card(body="b" * 70000))
        state = self.fake.requests[-1][1]["state"]
        self.assertEqual(state["title"], "Fix a typo")
        self.assertEqual(len(state["body"]), 60000)

    # --- the GLM sum rule (card t_92e29d10) ----------------------------------------

    def test_glm_sum_at_threshold_applies_the_highest_glm_route(self):
        # a: easy 0.2, medium 0.3, hard 0.1, very_hard 0.4, Jev chose medium;
        # no single GLM route reaches 0.6, the GLM sum 0.6 does, and medium is
        # the highest GLM route.
        self.fake.choice("medium", probs(easy=0.2, medium=0.3, hard=0.1, very_hard=0.4))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        # Card t_cf518fd0: a `medium` card goes to the second GLM worker of the board.
        self.assertEqual(sent["assignee"], "harness-worker-glm-medium-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["not_applied_reason"]),
                         ("medium", True, None))
        self.assertEqual(record["applied_route"], "medium")
        self.assertEqual(record["glm_probability_sum"], 0.6)

    def test_glm_sum_below_threshold_and_very_hard_below_threshold_is_unchanged(self):
        # b: easy 0.3, medium 0.2, hard 0.09, very_hard 0.41, Jev chose
        # very_hard; the GLM sum 0.59 is below 0.6 and the chosen very_hard
        # 0.41 too, so the card is unchanged.
        self.fake.choice("very_hard", probs(easy=0.3, medium=0.2, hard=0.09, very_hard=0.41))
        create, _ = self.create(self.card())
        record = self.assert_unchanged(create, "below_threshold")
        self.assertEqual(record["route"], "very_hard")
        self.assertIsNone(record["applied_route"])
        self.assertEqual(record["glm_probability_sum"], 0.59)

    def test_glm_sum_carries_a_chosen_very_hard_card_and_the_tie_goes_to_hard(self):
        # c: medium 0.31, hard 0.31, very_hard 0.38, Jev chose very_hard; the
        # GLM sum 0.62 is at the threshold, and the tie between the GLM routes
        # goes to the route listed last (`hard`).
        self.fake.choice("very_hard", probs(medium=0.31, hard=0.31, very_hard=0.38))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-hard-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3", "zai"))
        self.assertIn("\nAssigned worker EXACT harness-worker-glm-hard-1.\n", sent["body"])
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["not_applied_reason"]),
                         ("very_hard", True, None))
        self.assertEqual(record["applied_route"], "hard")
        self.assertEqual(record["glm_probability_sum"], 0.62)

    def test_the_specification_example_applies_hard(self):
        # The example of the specification (card t_3c7a581d): medium 0.25,
        # hard 0.36, very_hard 0.39, Jev chose very_hard; the GLM sum 0.61 is
        # at the threshold, so `hard` is applied although very_hard is the
        # single most probable route.
        self.fake.choice("very_hard", probs(medium=0.25, hard=0.36, very_hard=0.39))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-hard-1")
        record = self.last_decision()
        self.assertEqual(record["applied_route"], "hard")
        self.assertEqual(record["glm_probability_sum"], 0.61)

    def test_glm_sum_with_easy_higher_applies_easy(self):
        # d: easy 0.45, medium 0.2, very_hard 0.35, Jev chose easy.
        self.fake.choice("easy", probs(easy=0.45, medium=0.2, very_hard=0.35))
        create, _ = self.create(self.card())
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-easy-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3-flash", "zai"))
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["applied_route"]),
                         ("easy", True, "easy"))
        self.assertEqual(record["glm_probability_sum"], 0.65)

    def test_very_hard_at_threshold_is_applied_as_the_chosen_route(self):
        # e: very_hard 0.95, medium 0.05; the GLM sum 0.05 is below 0.6 and the
        # chosen very_hard is at the threshold, so the card is unchanged.
        self.fake.choice("very_hard", probs(very_hard=0.95, medium=0.05))
        create, _ = self.create(self.card())
        self.assertEqual(create.calls, [None])
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["applied_route"],
                          record["not_applied_reason"]), ("very_hard", True, "very_hard", None))
        self.assertEqual(record["new_assignee"], "harness-worker")
        self.assertEqual(record["glm_probability_sum"], 0.05)

    def test_control_group_counts_the_applied_route_and_not_the_chosen_one(self):
        # f: two cards with the probabilities of case c and control_group_every
        # 2; the first goes to the `glm_max_workers` profile, the second is the
        # control card, and its counter is under the applied route `hard`.
        self.config["routing"]["control_group_every"] = 2
        self.fake.choice("very_hard", probs(medium=0.31, hard=0.31, very_hard=0.38))
        first, _ = self.create(self.card())
        second, _ = self.create(self.card())
        self.assertEqual(first.calls[0]["assignee"], "harness-worker-glm-hard-1")
        self.assertIsNone(second.calls[0])  # the control card is created exactly as asked
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["not_applied_reason"]),
                         ("very_hard", False, "control_group"))
        self.assertEqual(record["applied_route"], "hard")
        self.assertEqual(record["glm_probability_sum"], 0.62)
        self.assertEqual(self.control_state()["control_group_counters"], {"harness": {"hard": 0}})
        # The `glm_max_workers` alternation advanced once (for the first card) only; since card
        # t_18a2dc93 the list has two names, so the next card gets the second.
        self.assertEqual(self.control_state()["counters"], {"harness:glm_max_workers": 1})

    def test_records_that_do_not_apply_have_the_new_fields(self):
        # g: model_set and assignee_not_listed carry the GLM sum; a jev_error
        # record has both new fields null.
        self.fake.choice("easy", probs(easy=0.7, medium=0.2, very_hard=0.1))
        create, _ = self.create(self.card(model="glm-5.3"))
        record = self.assert_unchanged(create, "model_set")
        self.assertEqual(record["glm_probability_sum"], 0.9)
        self.assertIsNone(record["applied_route"])
        self.fake.choice("easy", probs(easy=0.7, medium=0.2, very_hard=0.1))
        create, _ = self.create(self.card(assignee="harness-reviewer"))
        record = self.assert_unchanged(create, "assignee_not_listed")
        self.assertEqual(record["glm_probability_sum"], 0.9)
        self.assertIsNone(record["applied_route"])
        self.fake.mode = "http_error"
        create, _ = self.create(self.card())
        record = self.assert_unchanged(create, "jev_error")
        self.assertIsNone(record["glm_probability_sum"])
        self.assertIsNone(record["applied_route"])

    def test_the_glm_sum_rule_is_checked_before_the_chosen_route_rule(self):
        # h: threshold 0.4, easy 0.25, medium 0.2, very_hard 0.55, Jev chose
        # very_hard; the GLM sum 0.45 is at the threshold, so easy is applied
        # although the chosen very_hard 0.55 is above the threshold too.
        config = json.loads(json.dumps(self.config))
        config["routing"]["threshold"] = 0.4
        self.fake.choice("very_hard", probs(easy=0.25, medium=0.2, very_hard=0.55))
        create, _ = self.create(self.card(), config=config)
        sent = create.calls[0]
        self.assertEqual(sent["assignee"], "harness-worker-glm-easy-1")
        self.assertEqual((sent["model"], sent["provider"]), ("glm-5.3-flash", "zai"))
        record = self.last_decision()
        self.assertEqual((record["route"], record["applied"], record["applied_route"]),
                         ("very_hard", True, "easy"))
        self.assertEqual(record["glm_probability_sum"], 0.45)

    def test_glm_probability_sum_is_rounded_to_six_places(self):
        # i: 0.1 + 0.2 is 0.30000000000000004 as a float; the record holds 0.3.
        self.fake.choice("very_hard", probs(easy=0.1, medium=0.2, very_hard=0.7))
        create, _ = self.create(self.card())
        record = self.last_decision()
        self.assertEqual(record["glm_probability_sum"], 0.3)
        self.assertEqual((record["route"], record["applied"], record["applied_route"]),
                         ("very_hard", True, "very_hard"))


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
        # Card t_92e29d10: below_threshold needs a GLM sum below 0.6 (and no
        # chosen non-GLM route at 0.6 or more), not only a chosen route below 0.6.
        self.fake.choice("easy", probs(easy=0.3, medium=0.29, very_hard=0.41))
        create, _ = self.create(self.card())
        record = self.assert_unchanged(create, "below_threshold")
        self.assertEqual(record["route"], "easy")
        self.assertIsNone(record["applied_route"])
        self.assertEqual(record["glm_probability_sum"], 0.59)

    def test_routing_disabled(self):
        self.config["routing"]["enabled"] = False
        create, _ = self.create(self.card())
        self.assert_unchanged(create, "routing_disabled")
        self.assertEqual(self.fake.requests, [])

    def test_every_board_has_glm_routing(self):
        # Card t_71b4ef4a: jss-genr and anki have GLM workers and the same routes
        # as the other three boards. Card t_f4ce916d named three GLM worker
        # profiles per board; card t_3c7a581d moved the third of each board into
        # the new list `glm_max_workers` and gave `hard` that list in
        # `assignee_from` with model `glm-5.3` and provider `zai`. Card t_18a2dc93
        # gave the GLM workers the names of their routes and added the second
        # worker of each route: `glm_workers` names the four `easy` and `medium`
        # workers and `glm_max_workers` the two `hard` workers.
        boards = self.config["routing"]["boards"]
        self.assertEqual(sorted(boards), ["anki", "cha-pt", "harness", "jobcron", "jss-genr"])
        prefixes = {"jobcron": "jobcron", "cha-pt": "chapt", "harness": "harness", "jss-genr": "jss",
                    "anki": "anki"}
        glm_workers = {board: [f"{prefix}-worker-glm-{suffix}"
                               for suffix in ("easy-1", "easy-2", "medium-1", "medium-2")]
                       for board, prefix in prefixes.items()}
        glm_max_workers = {board: [f"{prefix}-worker-glm-hard-1", f"{prefix}-worker-glm-hard-2"]
                           for board, prefix in prefixes.items()}
        reference = boards["harness"]["routes"]
        for board, entry in boards.items():
            with self.subTest(board=board):
                self.assertEqual(entry["glm_workers"], glm_workers[board])
                self.assertEqual(entry["glm_max_workers"], glm_max_workers[board])
                self.assertEqual(entry["routes"], reference)
                self.assertEqual({r["name"]: r["enabled"] for r in entry["routes"]},
                                 {"easy": True, "medium": True, "hard": True, "very_hard": True})

    def test_jss_and_anki_routes_applied(self):
        cases = (("jss-genr", "jss-worker", "easy", "jss-worker-glm-easy-1", "glm-5.3-flash"),
                 ("anki", "anki-worker-2", "medium", "anki-worker-glm-medium-1", "glm-5.3"))  # glm-2: card t_cf518fd0
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
        self.assertEqual(create.calls[0]["assignee"], "harness-worker-glm-easy-1")

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

    # --- route criteria (card t_df87b851, card t_3c7a581d) ----------------------------

    def test_route_criteria_are_the_part_2_texts_on_every_board(self):
        expected = {
            "easy": ("The card names the exact files to change and the exact command that checks the result, "
                     "and the worker has no behaviour to work out. The topic of the card does not matter."),
            "medium": ("A fully specified change across several files with no design decision. This includes "
                       "tests, fixtures, user-facing text and wiring inside security, migration or deployment "
                       "features."),
            "hard": ("Everything that is not easy, medium or very hard: a design decision, a fault with an "
                     "unknown cause, or logic for authentication, secrets, payment, a database migration or "
                     "deployment when the card states the required behaviour. The topic alone does not make "
                     "a card very hard."),
            "very_hard": ("Work on authentication, secrets, payment, a database migration or production "
                          "systems, and in addition either the card leaves the required behaviour or the "
                          "approach undecided, or the problem is very complex: many parts that depend on "
                          "each other and must be worked out together. Also any card whose worker itself "
                          "runs commands against production or against the live Hermes installation."),
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
        # Card t_3c7a581d: the workers of `glm_workers` take turns for the
        # `easy` cards of the board. Card t_cf518fd0 gave the shipped `easy`
        # route its own list, so this test uses the configuration in which `easy`
        # still names `glm_workers`, to show that the control card does not
        # advance the turns. Since card t_18a2dc93 `glm_workers` has four names.
        self.config = glm_workers_route_config()
        self.config["jev"] = self.fake.settings()
        self.fake.choice("easy", probs(easy=0.9, medium=0.05, hard=0.05))
        sent = [self.create(self.card())[0].calls[0] for _ in range(10)]
        four = ["harness-worker-glm-easy-1", "harness-worker-glm-easy-2", "harness-worker-glm-medium-1",
                "harness-worker-glm-medium-2"]
        self.assertEqual([s["assignee"] for s in sent[:9]], four + four + four[:1])
        self.assertIsNone(sent[9])  # the tenth card is created exactly as the orchestrator asked
        record = self.last_decision()
        self.assertEqual((record["event"], record["applied"], record["not_applied_reason"], record["route"]),
                         ("route", False, "control_group", "easy"))
        self.assertAlmostEqual(record["probabilities"]["easy"], 0.9)
        self.assertEqual((record["original_assignee"], record["new_assignee"]), ("harness-worker", "harness-worker"))
        self.assertEqual(record["task_id"], "t_0a1b2c3d")
        # The alternation counter did not advance for the control card: the eleventh card gets the
        # second name of `glm_workers`.
        self.assertEqual(self.control_state()["counters"], {"harness": 1})
        self.assertEqual(self.create(self.card())[0].calls[0]["assignee"], "harness-worker-glm-easy-2")
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
        self.fake.choice("easy", probs(easy=0.3, medium=0.29, hard=0.41))
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
        # Card t_cf518fd0 gave the shipped `easy` route its own list; the turns of a
        # route that names the list `glm_workers` (four names since card
        # t_18a2dc93) are tested with the configuration in which `easy` still
        # names that list.
        self.config = glm_workers_route_config()
        self.config["jev"] = self.fake.settings()
        self.fake.choice("easy", probs(easy=0.9))
        chosen = [self.create(self.card())[0].calls[0]["assignee"] for _ in range(3)]
        # The workers of `glm_workers` take turns in the order of the list (card
        # t_3c7a581d; the `hard` profiles of each board are in `glm_max_workers`).
        self.assertEqual(chosen, ["harness-worker-glm-easy-1", "harness-worker-glm-easy-2", "harness-worker-glm-medium-1"])
        other = self.create(self.card(board="cha-pt", assignee="chapt-worker"))[0].calls[0]["assignee"]
        self.assertEqual(other, "chapt-worker-glm-easy-1")
        state = json.loads((self.log_dir / "routing-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counters"], {"harness": 3, "cha-pt": 1})
        self.assertEqual(state["control_group_counters"], {"harness": {"easy": 3}, "cha-pt": {"easy": 1}})

    def test_next_glm_worker_returns_each_worker_once_per_list_in_order(self):
        # Card t_3c7a581d: every board has the list `glm_workers` and the list
        # `glm_max_workers`; each list has its own counter under the section
        # `counters` of routing-state.json. Since card t_18a2dc93 `glm_workers`
        # has four names and `glm_max_workers` two.
        for board, entry in CONFIG["routing"]["boards"].items():
            with self.subTest(board=board), tempfile.TemporaryDirectory(prefix="jev-rotation-") as directory:
                workers = entry["glm_workers"]
                max_workers = entry["glm_max_workers"]
                self.assertEqual(len(workers), 4)
                self.assertEqual(len(max_workers), 2)
                chosen = [routing.next_glm_worker(board, workers, Path(directory)) for _ in range(4)]
                self.assertEqual(chosen, workers)
                # The fifth call with `glm_workers` starts the next turn with the first worker.
                self.assertEqual(routing.next_glm_worker(board, workers, Path(directory)), workers[0])
                # The list `glm_max_workers` takes its turns under its own counter.
                self.assertEqual(routing.next_glm_worker(board, max_workers, Path(directory), "glm_max_workers"),
                                 max_workers[0])
                self.assertEqual(routing.next_glm_worker(board, max_workers, Path(directory), "glm_max_workers"),
                                 max_workers[1])
                # The `glm_workers` turn continued where it was.
                self.assertEqual(routing.next_glm_worker(board, workers, Path(directory)), workers[1])
                state = json.loads((Path(directory) / "routing-state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["counters"], {board: 2, f"{board}:glm_max_workers": 0})

    def test_next_glm_worker_with_three_arguments_uses_the_key_of_the_board_name(self):
        # Three positional arguments keep the counter under the board name alone,
        # so the live state files written before the second list existed stay valid.
        with tempfile.TemporaryDirectory(prefix="jev-rotation-") as directory:
            workers = ["harness-worker-glm-easy-1", "harness-worker-glm-medium-1"]
            self.assertEqual(routing.next_glm_worker("harness", workers, Path(directory)),
                             "harness-worker-glm-easy-1")
            state = json.loads((Path(directory) / "routing-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["counters"], {"harness": 1})

    def test_assigned_worker_line_rewrite(self):
        self.fake.choice("medium", probs(medium=0.8))
        body = ("Repository /x ONLY.\nAssigned worker EXACT harness-worker.\nReviewer EXACT harness-reviewer.\n"
                "Text that mentions Assigned worker EXACT harness-worker inside a line.\n")
        create, _ = self.create(self.card(body=body, reviewer="harness-reviewer"))
        sent = create.calls[0]
        # Card t_cf518fd0: a `medium` card goes to the second GLM worker of the board.
        self.assertIn("\nAssigned worker EXACT harness-worker-glm-medium-1.\n", sent["body"])
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
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "harness-worker-glm-easy-1", "FAKE_HERMES_LOG": str(calls_log),
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
        calls = self.review("harness-worker-glm-medium-1")
        self.assertEqual(calls, [None])
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "set-model", "t_feedc0de", "none"]])
        # Card t_b668f19c: a review_choice record follows the clear_override
        # record in a GLM worker session, so the clear_override record is
        # selected by its event.
        record = next(r for r in read_records(self.dir / "logs", "decisions")
                      if r["event"] == "clear_override")
        self.assertEqual((record["event"], record["task_id"], record["applied"]), ("clear_override", "t_feedc0de", True))

    def test_second_list_worker_clears_override_before_review(self):
        # Two-list configuration: a session of the second list (glm_max_workers)
        # clears the model override too.
        self.config = two_list_config()
        calls = self.review("harness-worker-glm-hard-1")
        self.assertEqual(calls, [None])
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "set-model", "t_feedc0de", "none"]])
        record = next(r for r in read_records(self.dir / "logs", "decisions")
                      if r["event"] == "clear_override")
        self.assertEqual((record["event"], record["task_id"], record["applied"]), ("clear_override", "t_feedc0de", True))

    def test_claude_worker_does_not_clear(self):
        self.assertEqual(self.review("harness-worker"), [None])
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_board_not_configured_is_not_used_or_logged(self):
        calls = []
        with mock.patch.dict(os.environ, {"HERMES_PROFILE": "harness-worker-glm-easy-1"}):
            routing.handle_request_review({"board": "not-a-configured-board"}, lambda p=None: calls.append(p),
                                          config=self.config, command=self.hermes)
        self.assertEqual(calls, [None])
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        record = read_records(self.dir / "logs", "decisions")[-1]
        self.assertEqual((record["board"], record["applied"], record["not_applied_reason"]),
                         (None, False, "board_not_configured"))

    def test_failed_clear_still_requests_review(self):
        with mock.patch.dict(os.environ, {"FAKE_HERMES_EXIT": "3"}):
            calls = self.review("jobcron-worker-glm-easy-1")
        self.assertEqual(calls, [None])
        # Card t_b668f19c: the review_choice record is the last record of the
        # call, so the clear_override record is selected by its event.
        record = next(r for r in read_records(self.dir / "logs", "decisions")
                      if r["event"] == "clear_override")
        self.assertEqual((record["applied"], record["error_class"]), (False, "CommandFailed"))


GLM_CARD = "t_5a1e0001"
CLAUDE_CARD = "t_c1a0de01"


class RequestChangesTests(unittest.TestCase):
    """Part 4 (card t_df87b851): after the fifth change request a GLM card goes
    to a Claude worker. Card t_52be75ab: a route can carry its own
    ``max_glm_change_requests``, so a `hard` card goes at the third change
    request and an `easy` or `medium` card at the fifth.

    The board database is synthetic and every board change goes through the fake
    ``hermes`` command, which applies ``set-model`` and ``reassign`` to it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = isolated_env(self.dir)
        self.db = Path(env["HERMES_KANBAN_HOME"]) / "kanban" / "boards" / "harness" / "kanban.db"
        build_board_db(self.db, [(GLM_CARD, "ready", "harness-worker-glm-easy-1"),
                                 ("t_5a1e0002", "ready", "harness-worker-glm-medium-1"),
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

    def route_record(self, task_id, route, new_assignee="harness-worker-glm-easy-1",
                     original_assignee="harness-worker-2", applied=True):
        """One `route` record, written as `test_claude_worker_from_the_route_record` writes it."""
        routing.jev_log.write("decisions", {"event": "route", "board": "harness", "task_id": task_id,
                                            "original_assignee": original_assignee, "new_assignee": new_assignee,
                                            "applied": applied, "route": route, "applied_route": route})

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
                                                  "change_requests", "applied", "applied_route",
                                                  "max_glm_change_requests", "error_class")},
                         {"board": "harness", "task_id": GLM_CARD, "original_assignee": "harness-worker-glm-easy-1",
                          "new_assignee": "harness-worker", "change_requests": 5, "applied": True,
                          "applied_route": None, "max_glm_change_requests": 5, "error_class": None})

    def insert_card(self, task_id, assignee, model_override=None):
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO tasks (id, title, status, assignee, model_override) VALUES (?, ?, ?, ?, ?)",
                     (task_id, "synthetic card", "ready", assignee, model_override))
        conn.commit()
        conn.close()

    def test_second_list_card_moves_to_a_claude_worker_after_the_limit(self):
        # Two-list configuration: a card of the second list (glm_max_workers)
        # is moved to a Claude worker at the third change request (card
        # t_52be75ab: the `hard` route carries its own limit 3).
        task_id = "t_3c9d0003"
        self.insert_card(task_id, "harness-worker-glm-hard-1", "glm-5.3")
        self.add_change_requests(task_id, 3)
        self.request_changes({"task_id": task_id, "reason": "again"}, config=two_list_config())
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", task_id, "none"],
            ["kanban", "--board", "harness", "reassign", task_id, "harness-worker", "--reclaim"],
        ])
        self.assertEqual(tuple(self.card(task_id)), ("ready", "harness-worker", None))
        [record] = self.escalations()
        # The card has no `route` record; the worker list of the assignee (the
        # `hard` route alone names `glm_max_workers`) gives the limit 3, so
        # `applied_route` is None and the limit used is 3.
        self.assertEqual((record["change_requests"], record["applied_route"], record["max_glm_change_requests"]),
                         (3, None, 3))
        self.assertEqual((record["event"], record["task_id"], record["original_assignee"], record["applied"]),
                         ("escalate", task_id, "harness-worker-glm-hard-1", True))

    def test_second_list_card_below_the_limit_stays(self):
        task_id = "t_3c9d0004"
        self.insert_card(task_id, "harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 2)
        self.request_changes({"task_id": task_id, "reason": "again"}, config=two_list_config())
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(task_id)[1], "harness-worker-glm-hard-1")
        self.assertEqual(self.escalations(), [])

    def test_fourth_change_request_changes_nothing(self):
        self.add_change_requests(GLM_CARD, 4)
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-easy-1")
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
                                            "new_assignee": "harness-worker-glm-easy-1", "applied": True})
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-2")
        self.assertEqual(self.escalations()[0]["new_assignee"], "harness-worker-2")

    # --- card t_52be75ab: the limit of a card -----------------------------------------

    def result_tuple(self):
        """(change_requests, applied_route, max_glm_change_requests, applied, new_assignee) of the one escalate record."""
        [record] = self.escalations()
        return (record["change_requests"], record["applied_route"], record["max_glm_change_requests"],
                record["applied"], record["new_assignee"])

    def glm3_card(self, model_override="glm-5.3"):
        """A card of `harness-worker-glm-hard-1`, inserted like the second-list tests insert it."""
        task_id = "t_5a1e0003"
        self.insert_card(task_id, "harness-worker-glm-hard-1", model_override)
        return task_id

    def test_hard_card_of_the_glm3_profile_goes_at_the_third_change_request(self):
        task_id = self.glm3_card()
        self.route_record(task_id, "hard", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 2)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.assertEqual(self.card(task_id)[1], "harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 1)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", task_id, "none"],
            ["kanban", "--board", "harness", "reassign", task_id, "harness-worker-2", "--reclaim"],
        ])
        self.assertEqual(tuple(self.card(task_id)), ("ready", "harness-worker-2", None))
        self.assertEqual(self.result_tuple(), (3, "hard", 3, True, "harness-worker-2"))

    def test_medium_card_created_before_the_change_keeps_the_limit_five(self):
        # A card that was created before the configuration change has a `medium`
        # route record; its worker is now the `-glm-3` profile, but the route
        # record decides and `medium` has no limit of its own.
        task_id = self.glm3_card()
        self.route_record(task_id, "medium", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 4)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.add_change_requests(task_id, 1)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(self.result_tuple(), (5, "medium", 5, True, "harness-worker-2"))

    def test_glm3_card_without_a_route_record_goes_at_the_third(self):
        # The worker list of the assignee: only the `hard` route names a list
        # that contains `harness-worker-glm-hard-1`, so its limit 3 applies.
        task_id = self.glm3_card()
        self.add_change_requests(task_id, 2)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.add_change_requests(task_id, 1)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(self.result_tuple(), (3, None, 3, True, "harness-worker"))

    def test_first_list_card_without_a_route_record_keeps_the_limit_five(self):
        # `harness-worker-glm-easy-1` is named by `easy` and `medium`, which have no
        # limit of their own, so the general value 5 applies.
        self.add_change_requests(GLM_CARD, 4)
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.add_change_requests(GLM_CARD, 1)
        self.request_changes()
        self.assertEqual(self.result_tuple(), (5, None, 5, True, "harness-worker"))

    def test_easy_route_record_of_a_first_list_card_keeps_the_limit_five(self):
        self.route_record(GLM_CARD, "easy")
        self.add_change_requests(GLM_CARD, 4)
        self.request_changes()
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.add_change_requests(GLM_CARD, 1)
        self.request_changes()
        self.assertEqual(self.result_tuple(), (5, "easy", 5, True, "harness-worker-2"))

    def test_route_own_limit_that_is_zero_or_invalid_falls_back_to_the_general_value(self):
        task_id = self.glm3_card()
        self.route_record(task_id, "hard", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 4)
        for value in (0, "3", -1, True, "absent"):
            with self.subTest(value=value):
                self.calls_log.unlink(missing_ok=True)
                config = json.loads(json.dumps(self.config))
                route = next(r for r in config["routing"]["boards"]["harness"]["routes"] if r["name"] == "hard")
                if value == "absent":
                    del route["max_glm_change_requests"]
                else:
                    route["max_glm_change_requests"] = value
                self.request_changes({"task_id": task_id, "reason": "again"}, config=config)
                self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
                self.assertEqual(self.escalations(), [])
        # After a fifth change request, with the value 0, the general value 5
        # gives the limit and the route record still names the route.
        self.calls_log.unlink(missing_ok=True)
        self.add_change_requests(task_id, 1)
        config = json.loads(json.dumps(self.config))
        route = next(r for r in config["routing"]["boards"]["harness"]["routes"] if r["name"] == "hard")
        route["max_glm_change_requests"] = 0
        self.request_changes({"task_id": task_id, "reason": "again"}, config=config)
        self.assertEqual(self.result_tuple(), (5, "hard", 5, True, "harness-worker-2"))

    def test_general_value_zero_turns_the_reassignment_off_for_every_route(self):
        task_id = self.glm3_card()
        self.route_record(task_id, "hard", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 9)
        config = json.loads(json.dumps(self.config))
        config["routing"]["max_glm_change_requests"] = 0
        self.request_changes({"task_id": task_id, "reason": "again"}, config=config)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.assertEqual(self.escalations(), [])

    def test_route_record_with_a_name_the_board_does_not_have_uses_the_worker_list(self):
        task_id = self.glm3_card()
        self.route_record(task_id, "gone", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 3)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(self.result_tuple(), (3, None, 3, True, "harness-worker-2"))

    def test_route_record_of_another_board_task_or_not_applied_is_not_used(self):
        task_id = self.glm3_card()
        # Only these three records: another board, `applied` false, another task.
        routing.jev_log.write("decisions", {"event": "route", "board": "cha-pt", "task_id": task_id,
                                            "original_assignee": "chapt-worker", "new_assignee": "chapt-worker-glm-hard-1",
                                            "applied": True, "route": "medium", "applied_route": "medium"})
        self.route_record(task_id, "medium", new_assignee="harness-worker-glm-hard-1", applied=False)
        self.route_record("t_5a1e0004", "medium", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 3)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(self.result_tuple()[:4], (3, None, 3, True))

    def test_worker_list_with_two_routes_of_different_limits_uses_the_general_value(self):
        config = json.loads(json.dumps(self.config))
        route = next(r for r in config["routing"]["boards"]["harness"]["routes"] if r["name"] == "medium")
        route["max_glm_change_requests"] = 2
        # `harness-worker-glm-easy-1` is named by `easy` (limit 5) and `medium`
        # (limit 2); the limits differ, so the general value 5 applies.
        self.add_change_requests(GLM_CARD, 4)
        self.request_changes(config=config)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.assertEqual(self.escalations(), [])
        # `harness-worker-glm-medium-1` has a `medium` route record, so the first rule
        # gives the limit 2 of `medium`.
        self.route_record("t_5a1e0002", "medium", new_assignee="harness-worker-glm-medium-1")
        self.add_change_requests("t_5a1e0002", 2)
        self.request_changes({"task_id": "t_5a1e0002", "reason": "again"}, config=config)
        self.assertEqual(self.result_tuple(), (2, "medium", 2, True, "harness-worker-2"))

    def test_last_route_record_decides(self):
        task_id = self.glm3_card()
        self.route_record(task_id, "hard", new_assignee="harness-worker-glm-hard-1")
        self.route_record(task_id, "medium", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 3)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.assertEqual(self.escalations(), [])

    def test_route_record_without_applied_route_uses_the_route_field(self):
        # A record written before card t_92e29d10 has no `applied_route`: the
        # line is written directly as JSON, with no such key.
        task_id = self.glm3_card()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / "decisions.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "route", "board": "harness", "task_id": task_id,
                                     "original_assignee": "harness-worker", "new_assignee": "harness-worker-glm-hard-1",
                                     "applied": True, "route": "medium"}) + "\n")
        self.add_change_requests(task_id, 4)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])  # nothing happens
        self.add_change_requests(task_id, 1)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(self.result_tuple(), (5, "medium", 5, True, "harness-worker"))

    def test_workspace_and_branch_are_unchanged_by_the_reassignment(self):
        # Part 4 step 4: the reassignment changes only tasks.assignee, the model
        # override and the body line; the card keeps its workspace and branch.
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("ALTER TABLE tasks ADD COLUMN workspace_kind TEXT")
        conn.execute("ALTER TABLE tasks ADD COLUMN workspace_path TEXT")
        conn.execute("ALTER TABLE tasks ADD COLUMN branch_name TEXT")
        task_id = "t_5a1e0005"
        conn.execute("INSERT INTO tasks (id, title, status, assignee, model_override, workspace_kind, workspace_path,"
                     " branch_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (task_id, "synthetic card", "ready", "harness-worker-glm-hard-1", "glm-5.3", "worktree",
                      f"/Users/chanbla11mit/hermes-local-harness/.worktrees/{task_id}", f"wt/{task_id}"))
        conn.commit()
        conn.close()
        self.route_record(task_id, "hard", new_assignee="harness-worker-glm-hard-1")
        self.add_change_requests(task_id, 3)
        self.request_changes({"task_id": task_id, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", task_id, "none"],
            ["kanban", "--board", "harness", "reassign", task_id, "harness-worker-2", "--reclaim"],
        ])
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT workspace_kind, workspace_path, branch_name, assignee FROM tasks WHERE id=?",
                           (task_id,)).fetchone()
        conn.close()
        self.assertEqual(row, ("worktree", f"/Users/chanbla11mit/hermes-local-harness/.worktrees/{task_id}",
                               f"wt/{task_id}", "harness-worker-2"))
        self.assertEqual(self.result_tuple(), (3, "hard", 3, True, "harness-worker-2"))

    def test_procedure_states_the_two_sentences_of_the_card(self):
        procedure = (ROOT / "procedures" / "jev-plugin.md").read_text(encoding="utf-8")
        self.assertEqual(procedure.count("A route can have its own `max_glm_change_requests`; the route `hard` has "
                                          "`3`, and the routes `easy` and `medium` use the general value `5`."), 1)
        self.assertEqual(procedure.count("A run that ends by a crash, a timeout or a usage limit is not a change "
                                          "request and is not counted."), 1)

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
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-easy-1")
        [record] = self.escalations()
        self.assertEqual((record["applied"], record["error_class"], record["new_assignee"]),
                         (False, "CommandFailed", "harness-worker-glm-easy-1"))

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
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-easy-1")

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
                      body="Repository /tmp/x ONLY.\nAssigned worker EXACT harness-worker-glm-easy-1.\n"
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
        body = ("Note: the plugin wrote Assigned worker EXACT harness-worker-glm-easy-1 at creation.\n"
                "Assigned worker EXACT harness-worker-glm-easy-1.\n"
                "Assigned worker EXACT harness-worker-glm-10 (other card).\n"
                "  Assigned worker EXACT harness-worker-glm-easy-1 (indented).\n")
        self.set_card(GLM_CARD, body=body)
        self.add_change_requests(GLM_CARD, 5)
        self.request_changes()
        self.assertEqual(self.body(GLM_CARD), body.replace(
            "\nAssigned worker EXACT harness-worker-glm-easy-1.\n", "\nAssigned worker EXACT harness-worker.\n"))

    def test_card_without_the_line_gets_no_edit_command(self):
        for body in (None, "Repository /tmp/x ONLY.\nAssigned worker EXACT harness-worker-2.\n"):
            with self.subTest(body=body):
                self.calls_log.unlink(missing_ok=True)
                (self.log_dir / "decisions.jsonl").unlink(missing_ok=True)
                self.set_card(GLM_CARD, assignee="harness-worker-glm-easy-1", body=body)
                self.add_change_requests(GLM_CARD, 5)
                self.request_changes()
                self.assertEqual([c[3] for c in fake_hermes_calls(self.calls_log)], ["set-model", "reassign"])
                self.assertEqual(self.body(GLM_CARD), body)
                [record] = self.escalations()
                self.assertEqual((record["applied"], record["assigned_worker_line"]), (True, "no_line"))

    def test_failed_edit_is_logged_and_result_and_card_unchanged(self):
        body = f"{SENTINEL}\nAssigned worker EXACT harness-worker-glm-easy-1.\n"
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
        body = "Assigned worker EXACT harness-worker-glm-easy-1.\n" + "x" * routing.MAX_BODY_ARGUMENT_BYTES
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
            out = routing.rewrite_body_after_escalation(self.config, "harness", GLM_CARD, "harness-worker-glm-easy-1",
                                                        "harness-worker", self.hermes)
        self.assertEqual(out, {"assigned_worker_line": "failed", "assigned_worker_line_error_class": "OSError"})
        with mock.patch.object(routing, "rewrite_assigned_worker", side_effect=RuntimeError("x")):
            out = routing.rewrite_body_after_escalation(self.config, "harness", GLM_CARD, "harness-worker-glm-easy-1",
                                                        "harness-worker", self.hermes)
        self.assertEqual(out["assigned_worker_line_error_class"], "RuntimeError")
        self.assertEqual(fake_hermes_calls(self.calls_log), [])

    def test_body_with_sentinel_never_reaches_a_log_file(self):
        self.set_card(GLM_CARD, body=f"{SENTINEL} intro\n-{SENTINEL}\nAssigned worker EXACT harness-worker-glm-easy-1.\n")
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
