#!/usr/bin/env python3
"""The refusal of kanban_complete and kanban_request_review in a GLM reviewer session (card t_4c6f39f4).

Offline tests of the jev plugin only: no live /Users/chanbla11mit/.hermes reads, no board
access, no network and no model calls. Every test sets HERMES_PROFILE itself and writes
plugin logs only to a temporary directory, so the result does not depend on the profile
that runs the tests.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "jev"
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(ROOT / "plugins"))

GLM_REVIEWERS = ("jobcron-reviewer-glm", "chapt-reviewer-glm", "harness-reviewer-glm",
                 "jss-reviewer-glm", "anki-reviewer-glm")
BOARD_OF_GLM_REVIEWER = {"jobcron-reviewer-glm": "jobcron", "chapt-reviewer-glm": "cha-pt",
                         "harness-reviewer-glm": "harness", "jss-reviewer-glm": "jss-genr",
                         "anki-reviewer-glm": "anki"}


def read_records(log_dir: Path, stream: str) -> list:
    path = log_dir / f"{stream}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class GlmReviewerRefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {
            "HERMES_JEV_LOG_DIR": str(Path(self.tmp.name) / "logs"),
            "HERMES_HOME": str(Path(self.tmp.name) / "home"),
            "HERMES_PROFILE": "",
            "HERMES_KANBAN_TASK": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log_dir = Path(self.tmp.name) / "logs"
        self.plugin = importlib.import_module("jev")

    def profile_env(self, name: str, **extra):
        env = {"HERMES_PROFILE": name}
        env.update(extra)
        return mock.patch.dict(os.environ, env)

    def shipped_config(self) -> dict:
        return json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))

    def refuse(self, tool_name: str, args, next_call):
        return self.plugin._tool_execution(tool_name=tool_name, args=args, next_call=next_call)

    def assert_error_result(self, out: str) -> dict:
        self.assertIsInstance(out, str)
        record = json.loads(out)
        self.assertIsInstance(record, dict)
        self.assertIn("error", record)
        return record

    def refusal_records(self) -> list:
        return [r for r in read_records(self.log_dir, "decisions") if r.get("event") == "glm_reviewer_refusal"]

    def new_refusal_record(self, before_count: int) -> dict:
        """The one refusal record written after ``before_count`` records existed."""
        records = self.refusal_records()
        self.assertEqual(len(records), before_count + 1)
        return records[-1]

    def test_each_glm_reviewer_profile_is_refused_for_both_tools(self):
        for profile in GLM_REVIEWERS:
            for tool_name in ("kanban_complete", "kanban_request_review"):
                with self.subTest(profile=profile, tool_name=tool_name), \
                        self.profile_env(profile, HERMES_KANBAN_TASK="t_0a1b2c3d"):
                    before = len(self.refusal_records())
                    calls = []

                    def next_call(payload=None):
                        calls.append(payload)
                        return "tool result"

                    out = self.refuse(tool_name, {"task_id": "t_0a1b2c3d"}, next_call)
                    self.assert_error_result(out)
                    self.assertEqual(calls, [])
                    record = self.new_refusal_record(before)
                    self.assertEqual((record["event"], record["tool"], record["profile"], record["task_id"]),
                                     ("glm_reviewer_refusal", tool_name, profile, "t_0a1b2c3d"))

    def test_refusal_text_names_the_tool_and_the_two_rules(self):
        glm_review = self.plugin.glm_review
        for tool_name in ("kanban_complete", "kanban_request_review"):
            with self.subTest(tool_name=tool_name):
                record = json.loads(glm_review.refusal(tool_name))
                self.assertIn(tool_name, record["error"])
                self.assertIn("kanban_request_changes", record["error"])
                self.assertIn("Opus reviewer", record["error"])
        self.assertIn('"error"', glm_review.REFUSAL_ERROR)

    def test_same_refusal_when_load_config_returns_empty(self):
        with self.profile_env("harness-reviewer-glm"), \
                mock.patch.object(self.plugin, "load_config", return_value={}):
            calls = []
            out = self.refuse("kanban_complete", {"task_id": "t_0a1b2c3d"},
                              lambda payload=None: calls.append(payload))
            self.assert_error_result(out)
            self.assertEqual(calls, [])
            self.assertEqual(len(self.refusal_records()), 1)

    def test_error_result_when_load_config_raises(self):
        # The profile check raises, so the middleware returns the module-level constant
        # result and the tool is not called (the check fails closed).
        with self.profile_env("harness-reviewer-glm"), \
                mock.patch.object(self.plugin, "load_config", side_effect=OSError("unreadable")):
            for tool_name in ("kanban_complete", "kanban_request_review"):
                with self.subTest(tool_name=tool_name):
                    calls = []
                    out = self.refuse(tool_name, {"task_id": "t_0a1b2c3d"},
                                      lambda payload=None: calls.append(payload))
                    self.assertEqual(out, self.plugin.glm_review.REFUSAL_ERROR)
                    self.assert_error_result(out)
                    self.assertEqual(calls, [])
                    self.assertEqual(self.refusal_records(), [])

    def test_same_refusal_when_args_is_not_a_dict(self):
        for args in (["t_0a1b2c3d"], None, "t_0a1b2c3d"):
            with self.subTest(args=args), self.profile_env("jss-reviewer-glm",
                                                           HERMES_KANBAN_TASK="t_0f1e2d3c"):
                before = len(self.refusal_records())
                calls = []
                out = self.refuse("kanban_request_review", args,
                                  lambda payload=None: calls.append(payload))
                self.assert_error_result(out)
                self.assertEqual(calls, [])
                record = self.new_refusal_record(before)
                self.assertEqual(record["task_id"], "t_0f1e2d3c")

    def test_same_refusal_when_writing_the_record_raises(self):
        with self.profile_env("harness-reviewer-glm"), \
                mock.patch.object(self.plugin.jev_log, "write", side_effect=OSError("no log")):
            calls = []
            out = self.refuse("kanban_complete", {"task_id": "t_0a1b2c3d"},
                              lambda payload=None: calls.append(payload))
            self.assertEqual(out, self.plugin.glm_review.refusal("kanban_complete"))
            self.assert_error_result(out)
            self.assertEqual(calls, [])
            self.assertEqual(read_records(self.log_dir, "decisions"), [])

    def test_task_id_argument_that_is_not_of_the_hermes_form_is_written_as_null(self):
        for task_id in ("not-a-task-id", "T_0A1B2C3D", "t_0a1b2c3d extra", 1234, None):
            with self.subTest(task_id=task_id), self.profile_env("harness-reviewer-glm"):
                before = len(self.refusal_records())
                out = self.refuse("kanban_complete", {"task_id": task_id}, lambda payload=None: "tool result")
                self.assert_error_result(out)
                self.assertIsNone(self.new_refusal_record(before)["task_id"])

    def test_a_name_in_a_glm_reviewers_list_that_does_not_match_the_pattern_is_refused(self):
        config = self.shipped_config()
        config["routing"]["boards"]["harness"]["glm_reviewers"] = ["harness-reviewer-two"]
        with self.profile_env("harness-reviewer-two"), \
                mock.patch.object(self.plugin, "load_config", return_value=config):
            calls = []
            out = self.refuse("kanban_complete", {"task_id": "t_0a1b2c3d"},
                              lambda payload=None: calls.append(payload))
            self.assert_error_result(out)
            self.assertEqual(calls, [])
            self.assertEqual(len(self.refusal_records()), 1)
        # The same name with an empty configuration passes through.
        with self.profile_env("harness-reviewer-two"), \
                mock.patch.object(self.plugin, "load_config", return_value={}):
            calls = []
            out = self.refuse("kanban_complete", {"task_id": "t_0a1b2c3d"},
                              lambda payload=None: calls.append(payload) or "tool result")
            self.assertEqual(out, "tool result")
            self.assertEqual(calls, [None])
        self.assertEqual(len(self.refusal_records()), 1)

    def test_other_profiles_are_not_refused(self):
        for profile in ("harness-reviewer", "harness-worker", "harness-worker-glm-1", "harness-orchestrator"):
            with self.subTest(profile=profile), self.profile_env(profile):
                calls = []

                def next_call(payload=None):
                    calls.append(payload)
                    return "tool result"

                out = self.refuse("kanban_complete", {"task_id": "t_0a1b2c3d"}, next_call)
                self.assertEqual(out, "tool result")
                self.assertEqual(calls, [None])
                with mock.patch.object(self.plugin.routing, "handle_request_review",
                                       return_value="handled") as handler:
                    out = self.refuse("kanban_request_review", {"task_id": "t_0a1b2c3d"}, next_call)
                    self.assertEqual(out, "handled")
                    handler.assert_called_once()
                self.assertEqual(self.refusal_records(), [])

    def test_a_glm_reviewer_session_keeps_the_other_tools(self):
        with self.profile_env("harness-reviewer-glm"):
            with mock.patch.object(self.plugin.routing, "handle_request_changes",
                                   return_value="handled") as handler:
                calls = []
                out = self.refuse("kanban_request_changes", {"task_id": "t_0a1b2c3d"},
                                  lambda payload=None: calls.append(payload))
                self.assertEqual(out, "handled")
                handler.assert_called_once()
                self.assertEqual(calls, [])
            for tool_name in ("kanban_block", "terminal"):
                with self.subTest(tool_name=tool_name):
                    calls = []
                    out = self.refuse(tool_name, {"task_id": "t_0a1b2c3d", "reason": "x"},
                                      lambda payload=None: calls.append(payload) or "tool result")
                    self.assertEqual(out, "tool result")
                    self.assertEqual(calls, [None])
            self.assertEqual(self.refusal_records(), [])

    def test_error_result_when_the_profile_check_raises(self):
        for tool_name in ("kanban_complete", "kanban_request_review"):
            with self.subTest(tool_name=tool_name), self.profile_env("harness-reviewer-glm"), \
                    mock.patch.object(self.plugin.jev_log, "profile_name", side_effect=RuntimeError("no profile")):
                calls = []
                out = self.refuse(tool_name, {"task_id": "t_0a1b2c3d"},
                                  lambda payload=None: calls.append(payload))
                self.assertEqual(out, self.plugin.glm_review.REFUSAL_ERROR)
                self.assert_error_result(out)
                self.assertEqual(calls, [])
        # The terminal tool passes through when the profile check raises.
        with self.profile_env("harness-reviewer-glm"), \
                mock.patch.object(self.plugin.jev_log, "profile_name", side_effect=RuntimeError("no profile")):
            calls = []
            out = self.refuse("terminal", {"command": "ls"}, lambda payload=None: calls.append(payload) or "ok")
            self.assertEqual(out, "ok")
            self.assertEqual(calls, [None])

    def test_the_constant_result_is_returned_when_building_the_result_raises(self):
        glm_review = self.plugin.glm_review
        with self.profile_env("harness-reviewer-glm"), \
                mock.patch.object(glm_review.json, "dumps", side_effect=ValueError("no json")):
            out = glm_review.handle_refused_tool("kanban_complete", {"task_id": "t_0a1b2c3d"})
        self.assertEqual(out, glm_review.REFUSAL_ERROR)
        self.assert_error_result(out)

    def test_is_glm_reviewer_pattern_cases(self):
        is_glm_reviewer = self.plugin.glm_review.is_glm_reviewer
        for profile, expected in (("harness-reviewer-glm", True), ("a-reviewer-glm", True),
                                  ("anki-reviewer-glm", True), ("harness-reviewer-glm-2", False),
                                  ("harness-reviewer-glm-", False), ("-reviewer-glm", False),
                                  ("HARNESS-REVIEWER-GLM", False), ("harness reviewer glm", False),
                                  ("harness-reviewer", False), ("", False), (None, False), (7, False)):
            with self.subTest(profile=profile):
                self.assertIs(is_glm_reviewer(profile, {}), expected)
                self.assertIs(is_glm_reviewer(profile, None), expected)
                self.assertIs(is_glm_reviewer(profile, ["not", "a", "dict"]), expected)

    def test_is_glm_reviewer_reads_the_glm_reviewers_lists_and_never_raises(self):
        is_glm_reviewer = self.plugin.glm_review.is_glm_reviewer
        config = {"routing": {"boards": {"harness": {"glm_reviewers": ["harness-reviewer-two"]},
                                         "anki": {"routes": [{"name": "easy"}]}}}}
        self.assertIs(is_glm_reviewer("harness-reviewer-two", config), True)
        self.assertIs(is_glm_reviewer("harness-reviewer-glm", config), True)
        self.assertIs(is_glm_reviewer("harness-reviewer", config), False)
        for broken in ({"routing": None}, {"routing": {"boards": None}}, {"routing": {"boards": {"harness": None}}},
                       {"routing": {"boards": {"harness": {"glm_reviewers": "harness-reviewer-two"}}}},
                       {"routing": {"boards": {"harness": {"glm_reviewers": [None, 7, "harness-reviewer-two"]}}}}):
            with self.subTest(broken=broken):
                self.assertIs(is_glm_reviewer("harness-reviewer-two", broken), broken ==
                              {"routing": {"boards": {"harness": {"glm_reviewers": [None, 7, "harness-reviewer-two"]}}}})

        class RaisesOnGet:
            def get(self, key):
                raise RuntimeError("no config")

        self.assertIs(is_glm_reviewer("harness-reviewer-two", RaisesOnGet()), False)
        self.assertIs(is_glm_reviewer("harness-reviewer-glm", RaisesOnGet()), True)

    def test_shipped_config_lists_the_glm_reviewers_and_the_switch(self):
        routing = self.shipped_config()["routing"]
        for profile, board in BOARD_OF_GLM_REVIEWER.items():
            with self.subTest(board=board):
                self.assertEqual(routing["boards"][board]["glm_reviewers"], [profile])
        self.assertEqual(routing["glm_review"], {"enabled": False, "max_glm_review_change_requests": 2})


if __name__ == "__main__":
    unittest.main()
