#!/usr/bin/env python3
"""Card t_cf518fd0: on every board the route `easy` goes only to `<prefix>-worker-glm-1` and the
route `medium` only to `<prefix>-worker-glm-2`, so that each GLM worker profile runs one model.

Owner decision of 2026-11-16: Hermes has one `fallback_providers` list per profile, whatever model
the card sets, so `<prefix>-worker-glm-1` takes only `easy` cards (`glm-5.3-flash`) and
`<prefix>-worker-glm-2` takes only `medium` cards (`glm-5.3`). The card added the lists
`easy_route_workers` (the first name of `glm_workers`) and `medium_route_workers` (the second
name) to each board of `plugins/jev/config.json`, made the two routes name them in
`assignee_from`, and kept `glm_workers` with both names for the peak-hours hold, the report and
the change request rules.

Card t_18a2dc93 (owner decision of 2026-11-16) then renamed `<prefix>-worker-glm-1` to
`<prefix>-worker-glm-easy-1`, `-glm-2` to `-glm-medium-1` and `-glm-3` to `-glm-hard-1`, and added the
second worker of each route: `easy_route_workers` names `-glm-easy-1` and `-glm-easy-2`,
`medium_route_workers` names `-glm-medium-1` and `-glm-medium-2`, `glm_workers` names these four and
`glm_max_workers` names `-glm-hard-1` and `-glm-hard-2`. The tests of the shipped configuration and
of the routing check that state, so each profile still runs one model; the tests of the policy text
check this card's text after the edits of card t_18a2dc93 are reversed.

Offline checks only: the Jev answer comes from the local fake TypeSafe server of
tests/test_jev_client.py (no model call), and nothing is written under /Users/chanbla11mit/.hermes.

This module also records the card's edits in the five project orchestrator skill sources
(EASY_MEDIUM_SPLIT_EDITS) so that they can be reversed byte for byte.
orchestrator_glm_review_edits.reverse_orchestrator_glm_review_edits calls
reverse_easy_medium_split_edits first, so every test that recovers the bytes of an earlier commit
reverses this card's edits before the edits of the earlier cards. The later edits of card
t_18a2dc93 (glm_route_worker_names_edits) are reversed first. At module level this module imports
only the standard library and glm_route_worker_names_edits, which imports only the standard
library, so any test module can import it without a circular import; the routing test helpers and
the plugin modules are imported when the tests run.
"""
import functools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from glm_route_worker_names_edits import reverse_glm_route_worker_name_edits
from test_ponytail_policy_text import reverse_ponytail_policy_text_edits
from test_reasoning_effort_skill_text import reverse_reasoning_effort_skill_text_edits

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e7d7583f02e669a4bf79896c1e169ebb31d6b77f"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
# Profile prefix -> Kanban board name.
BOARDS = {"jobcron": "jobcron", "chapt": "cha-pt", "harness": "harness", "jss": "jss-genr", "anki": "anki"}
PREFIXES = tuple(BOARDS)
# Profile prefix -> (version at BASELINE, version after this card).
VERSIONS = {
    "harness": ("0.6.7-harness.13", "0.6.7-harness.14"),
    "jss": ("0.6.7-jss.17", "0.6.7-jss.18"),
    "anki": ("0.6.10-anki.11", "0.6.10-anki.12"),
    "chapt": ("0.6.7-chapt.15", "0.6.7-chapt.16"),
    "jobcron": ("0.6.9-jobcron.16", "0.6.9-jobcron.17"),
}
PROCEDURE = "procedures/jev-plugin.md"
KST = ZoneInfo("Asia/Seoul")
SATURDAY = datetime(2026, 11, 14, 16, 0, tzinfo=KST)  # outside the peak-hours window


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def old_bullet_text(prefix):
    """The part of the `jev` bullet that this card replaced."""
    return (f" to `{prefix}-worker-glm-1` or `{prefix}-worker-glm-2`, taking the two in turn, for work that the "
            f"plugin classifies as `easy` or `medium`, or to `{prefix}-worker-glm-3` for work that it classifies "
            "as `hard`, and set the card's `model` and `provider` (`glm-5.3-flash` or `glm-5.3` on provider `zai`).")


def split_sentence(prefix):
    """The text of item 2 of the card."""
    return (f"`easy` work goes to `{prefix}-worker-glm-1` (model `glm-5.3-flash`) and `medium` work to "
            f"`{prefix}-worker-glm-2` (model `glm-5.3`)")


def new_bullet_text(prefix):
    return (", and set the card's `model` and `provider` (`glm-5.3-flash` or `glm-5.3` on provider `zai`): "
            f"{split_sentence(prefix)}, and work that the plugin classifies as `hard` goes to "
            f"`{prefix}-worker-glm-3`.")


def version_edit(prefix):
    old, new = VERSIONS[prefix]
    return (f"version: {new}\n", f"version: {old}\n")


# File -> ((new text, old text), ...), in the order in which the card applied them. Each new
# text occurs exactly once in the file after this card and not at all at BASELINE.
EASY_MEDIUM_SPLIT_EDITS = {skill(prefix): ((new_bullet_text(prefix), old_bullet_text(prefix)), version_edit(prefix))
                           for prefix in PREFIXES}


def reverse_easy_medium_split_edits(relative_path, text):
    """Return text with the t_cf518fd0 edits reversed; text may be str or bytes. A path that the
    card did not change, and a text that contains none of the new texts, is returned as the same
    object, so a caller may apply it to a text that another caller already reversed. A text that
    contains some of the new texts but not each of them exactly once raises AssertionError. The
    later edits of card t_18a2dc93 are reversed first."""
    text = reverse_reasoning_effort_skill_text_edits(relative_path, text)
    text = reverse_ponytail_policy_text_edits(relative_path, text)
    text = reverse_glm_route_worker_name_edits(relative_path, text)
    edits = EASY_MEDIUM_SPLIT_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    counts = [value.count(new) for new, _old in edits]
    if not any(counts):
        return text
    if counts != [1] * len(edits):
        raise AssertionError(f"{relative_path}: expected one occurrence of each new text, found {counts}")
    for new, old in reversed(edits):
        value = value.replace(new, old, 1)
    return value.encode() if as_bytes else value


def baseline_bytes(relative_path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{relative_path}"],
                          stdout=subprocess.PIPE, check=True).stdout


def shipped_config():
    return json.loads((ROOT / "plugins" / "jev" / "config.json").read_text(encoding="utf-8"))


def _plugin_modules():
    """Import the routing test helpers and the plugin modules when the tests run."""
    for path in (ROOT / "plugins", ROOT / "plugins" / "jev", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import jev_client
    import peak_hold
    import routing
    import test_jev_client
    return jev_client, peak_hold, routing, test_jev_client


class FakeCreate:
    """Stands in for ``next_call``: records what the tool would receive (as in tests/test_jev_routing.py)."""

    def __init__(self):
        self.calls = []

    def __call__(self, payload=None):
        self.calls.append(payload)
        return json.dumps({"ok": True, "task_id": "t_0a1b2c3d", "status": "ready"})


def route_names(prefix, route):
    """The two GLM workers of a route of a board after card t_18a2dc93."""
    return [f"{prefix}-worker-glm-{route}-1", f"{prefix}-worker-glm-{route}-2"]


class ShippedConfiguration(unittest.TestCase):
    def test_each_board_names_two_workers_for_each_glm_route(self):
        boards = shipped_config()["routing"]["boards"]
        self.assertEqual(set(boards), set(BOARDS.values()))
        for prefix, board in BOARDS.items():
            entry = boards[board]
            routes = {route["name"]: route for route in entry["routes"]}
            with self.subTest(board=board):
                self.assertEqual(entry["glm_workers"], route_names(prefix, "easy") + route_names(prefix, "medium"))
                self.assertEqual(entry["easy_route_workers"], route_names(prefix, "easy"))
                self.assertEqual(entry["medium_route_workers"], route_names(prefix, "medium"))
                self.assertEqual(entry["glm_max_workers"], route_names(prefix, "hard"))
                self.assertEqual(list(routes), ["easy", "medium", "hard", "very_hard"])
                self.assertEqual((routes["easy"]["assignee_from"], routes["easy"]["model"], routes["easy"]["provider"]),
                                 ("easy_route_workers", "glm-5.3-flash", "zai"))
                self.assertEqual((routes["medium"]["assignee_from"], routes["medium"]["model"],
                                  routes["medium"]["provider"]), ("medium_route_workers", "glm-5.3", "zai"))
                self.assertEqual(routes["hard"]["assignee_from"], "glm_max_workers")
                self.assertNotIn("assignee_from", routes["very_hard"])

    def test_peak_hold_covers_the_six_glm_workers_once_each(self):
        _jev_client, peak_hold, _routing, _helpers = _plugin_modules()
        by_board = peak_hold.glm_workers_by_board(shipped_config())
        self.assertEqual(set(by_board), set(BOARDS.values()))
        for prefix, board in BOARDS.items():
            with self.subTest(board=board):
                self.assertEqual(by_board[board], route_names(prefix, "easy") + route_names(prefix, "medium")
                                 + route_names(prefix, "hard"))


class Routing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jev_client, _peak_hold, cls.routing, cls.helpers = _plugin_modules()
        cls.fake = cls.helpers.FakeTypeSafe()

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()

    def setUp(self):
        self.fake.requests.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = self.helpers.isolated_env(self.dir)
        env["HERMES_KANBAN_BOARD"] = ""
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = shipped_config()
        self.config["jev"] = self.fake.settings()

    def create(self, prefix, board):
        args = {"title": "Change a file", "body": f"Repository x.\nAssigned worker EXACT {prefix}-worker.\n"
                f"Reviewer EXACT {prefix}-reviewer.\n", "assignee": f"{prefix}-worker", "board": board}
        next_call = FakeCreate()
        ask = functools.partial(self.jev_client.ask, settings=self.config["jev"])
        self.routing.handle_create(args, next_call, config=self.config, ask=ask, now=SATURDAY)
        return next_call.calls[0]

    def test_easy_and_medium_cards_take_the_two_workers_of_their_route_in_turn(self):
        cases = (("easy", "glm-5.3-flash"), ("medium", "glm-5.3"))
        for prefix, board in BOARDS.items():
            for route, model in cases:
                self.fake.choice(route, {"easy": 0.0, "medium": 0.0, "hard": 0.0, "very_hard": 0.0, route: 0.9})
                with self.subTest(board=board, route=route):
                    # Two calls in a row get the two workers of the route (card t_18a2dc93), each with
                    # the model of the route.
                    for worker in route_names(prefix, route):
                        sent = self.create(prefix, board)
                        self.assertEqual(sent["assignee"], worker)
                        self.assertEqual((sent["model"], sent["provider"]), (model, "zai"))
                        self.assertIn(f"\nAssigned worker EXACT {worker}.\n", sent["body"])
        self.assertEqual(len(self.fake.requests), 2 * len(cases) * len(BOARDS))


class PolicyText(unittest.TestCase):
    def test_each_orchestrator_skill_states_the_split_and_the_raised_version(self):
        for prefix in PREFIXES:
            current = (ROOT / skill(prefix)).read_text(encoding="utf-8")
            # Card t_18a2dc93 later replaced the split sentence; this card's text is checked with
            # those edits reversed.
            self.assertNotIn(split_sentence(prefix), current)
            text = reverse_glm_route_worker_name_edits(skill(prefix), current)
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count(split_sentence(prefix)), 1)
                self.assertEqual(text.count(new_bullet_text(prefix)), 1)
                self.assertNotIn("taking the two in turn", text)
                self.assertEqual(text.count("\nversion: "), 1)
                self.assertIn(f"\nversion: {VERSIONS[prefix][1]}\n", text)

    def test_reversal_gives_the_baseline_bytes(self):
        for prefix in PREFIXES:
            relative = skill(prefix)
            data = (ROOT / relative).read_bytes()
            with self.subTest(prefix=prefix):
                original = reverse_easy_medium_split_edits(relative, data)
                self.assertNotEqual(original, data)
                self.assertEqual(original, baseline_bytes(relative))
                self.assertEqual(reverse_easy_medium_split_edits(relative, data.decode()), original.decode())
                self.assertIs(reverse_easy_medium_split_edits(relative, original), original)
                for new, _old in EASY_MEDIUM_SPLIT_EDITS[relative]:
                    with self.assertRaises(AssertionError):
                        reverse_easy_medium_split_edits(relative, data.decode() + new)

    def test_reversal_returns_other_paths_unchanged(self):
        data = (ROOT / PROCEDURE).read_bytes()
        self.assertIs(reverse_easy_medium_split_edits(PROCEDURE, data), data)

    def test_procedure_states_the_split_and_its_reason(self):
        text = (ROOT / PROCEDURE).read_text(encoding="utf-8")
        self.assertNotIn("`easy` and `medium` take the two workers of `glm_workers` in turn", text)
        self.assertNotIn("assignee from the board's `glm_workers`", text)
        # Card t_18a2dc93 replaced the sentence of this card with the two workers of each route.
        self.assertNotIn("`easy` goes to the first worker of `glm_workers`", text)
        self.assertIn("`easy` goes to the two workers of the list `easy_route_workers`, "
                      "`<board>-worker-glm-easy-1` and `<board>-worker-glm-easy-2`, with model `glm-5.3-flash`; "
                      "`medium` goes to the two workers of the list `medium_route_workers`, "
                      "`<board>-worker-glm-medium-1` and `<board>-worker-glm-medium-2`, with model `glm-5.3`", text)
        self.assertEqual(text.count("Card `t_cf518fd0`"), 1)
        self.assertIn("on the owner's decision of 2026-11-16", text)
        self.assertIn("Hermes has one `fallback_providers` list per profile", text)


if __name__ == "__main__":
    unittest.main()
