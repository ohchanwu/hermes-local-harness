#!/usr/bin/env python3
"""The reviewer choice of handle_request_review (card t_b668f19c).

Offline tests of the jev plugin only: no live /Users/chanbla11mit/.hermes reads, no board
access other than a temporary database, no network and no model calls. Every test sets
HERMES_PROFILE itself with mock.patch.dict(os.environ, ...) and writes plugin logs only to
a temporary directory, so the result does not depend on the profile that runs the tests.

The temporary Kanban database holds the Hermes schema columns that the code reads
(tasks, task_events with payload). The set-model command is replaced by the fake hermes
command of tests/test_jev_client.py, as the tests of tests/test_jev_routing.py do.
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
sys.path.insert(0, str(ROOT / "tests"))

import routing  # noqa: E402
from test_jev_client import (  # noqa: E402
    build_board_db, fake_hermes_calls, isolated_env, read_records, write_fake_hermes,
)

CONFIG = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
BOARD_OF = {"jobcron": "jobcron", "cha-pt": "chapt", "harness": "harness", "jss-genr": "jss",
            "anki": "anki"}
OPUS_OF = {"jobcron": "jobcron-reviewer", "cha-pt": "chapt-reviewer", "harness": "harness-reviewer",
           "jss-genr": "jss-reviewer", "anki": "anki-reviewer"}
GLM_OF = {"jobcron": "jobcron-reviewer-glm", "cha-pt": "chapt-reviewer-glm",
          "harness": "harness-reviewer-glm", "jss-genr": "jss-reviewer-glm",
          "anki": "anki-reviewer-glm"}
RECORD_FIELDS = ("board", "task_id", "original_assignee", "reviewer", "opus_change_requests",
                 "glm_change_requests", "switch", "applied", "not_applied_reason")
# The fields of the decisions stream that the record of this card does not use; the
# log writer adds each of them as null.
STREAM_NULL_FIELDS = ("new_assignee", "orchestrator_model", "route", "probabilities", "confidence",
                      "jev_latency_ms", "jev_input_tokens", "error_class", "applied_route",
                      "glm_probability_sum", "held_until")
CARD = "t_0a1b2c3d"


def switch_config(enabled, max_glm_review_change_requests=2, board="harness"):
    """A deep copy of the shipped configuration with routing.glm_review replaced."""
    config = json.loads(json.dumps(CONFIG))
    config["routing"]["glm_review"] = {"enabled": enabled,
                                       "max_glm_review_change_requests": max_glm_review_change_requests}
    return config


class ReviewChoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = isolated_env(self.dir)
        env["HERMES_KANBAN_BOARD"] = ""
        env["HERMES_KANBAN_TASK"] = ""
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log_dir = self.dir / "logs"
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        env["FAKE_HERMES_LOG"] = str(self.calls_log)
        self.db_dir = self.dir / "kanban-home" / "kanban" / "boards"

    # --- helpers ---------------------------------------------------------------

    def build_db(self, board, task_id=CARD, assignee="harness-worker-glm-1", events=()):
        """A temporary board database with one card and changes_requested events.

        events: iterable of (reviewer, payload) pairs; a payload of None writes
        the kind with a payload that has no reviewer.
        """
        path = self.db_dir / board / "kanban.db"
        build_board_db(path, [(task_id, "ready", assignee)])
        import sqlite3
        conn = sqlite3.connect(path)
        for reviewer, payload in events:
            content = payload if payload is not None else json.dumps({"implementer": "x"})
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, 0)",
                         (task_id, "changes_requested", content))
        conn.commit()
        conn.close()
        return path

    def review(self, profile, args=None, config=None, board="harness"):
        """Run handle_request_review as the middleware calls it; returns (calls, result)."""
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return "tool result"

        env = {"HERMES_PROFILE": profile, "FAKE_HERMES_LOG": str(self.calls_log)}
        if board is not None:
            env["HERMES_KANBAN_BOARD"] = board
        with mock.patch.dict(os.environ, env):
            result = routing.handle_request_review(args if args is not None else {"summary": "done"},
                                                   next_call, config=config or switch_config(True),
                                                   command=self.hermes)
        return calls, result

    def choice_records(self):
        return [r for r in read_records(self.log_dir, "decisions") if r.get("event") == "review_choice"]

    def clear_records(self):
        return [r for r in read_records(self.log_dir, "decisions") if r.get("event") == "clear_override"]

    def add_events(self, board, task_id, reviewers, payload=None):
        import sqlite3
        conn = sqlite3.connect(self.db_dir / board / "kanban.db")
        for reviewer in reviewers:
            content = payload if payload is not None else json.dumps(
                {"reviewer": reviewer, "implementer": "x", "reason": "fix"})
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, 0)",
                         (task_id, "changes_requested", content))
        conn.commit()
        conn.close()

    # --- switch on: no change requests ------------------------------------------

    def test_switch_on_no_change_requests_passes_the_glm_reviewer(self):
        self.build_db("harness")
        args = {"task_id": CARD, "board": "harness"}
        frozen = dict(args)
        calls, result = self.review("harness-worker-glm-1", args)
        self.assertEqual(result, "tool result")
        self.assertEqual(calls, [{"task_id": CARD, "board": "harness", "reviewer": "harness-reviewer-glm"}])
        self.assertEqual(args, frozen)  # the original args object is unchanged
        [record] = self.choice_records()
        self.assertEqual({k: record[k] for k in RECORD_FIELDS},
                         {"board": "harness", "task_id": CARD, "original_assignee": "harness-worker-glm-1",
                          "reviewer": "harness-reviewer-glm", "opus_change_requests": 0,
                          "glm_change_requests": 0, "switch": True, "applied": True,
                          "not_applied_reason": None})

    def test_switch_on_second_board_jobcron_passes_its_glm_reviewer(self):
        self.build_db("jobcron", assignee="jobcron-worker-glm-1")
        calls, _ = self.review("jobcron-worker-glm-2", {"task_id": CARD, "board": "jobcron"},
                               board="jobcron")
        self.assertEqual(calls, [{"task_id": CARD, "board": "jobcron", "reviewer": "jobcron-reviewer-glm"}])
        [record] = self.choice_records()
        self.assertEqual((record["board"], record["reviewer"]), ("jobcron", "jobcron-reviewer-glm"))

    def test_switch_on_second_board_cha_pt_passes_its_glm_reviewer(self):
        self.build_db("cha-pt", assignee="chapt-worker-glm-1")
        calls, _ = self.review("chapt-worker-glm-1", {"task_id": CARD, "board": "cha-pt"}, board="cha-pt")
        self.assertEqual(calls[0]["reviewer"], "chapt-reviewer-glm")
        self.assertEqual(calls[0]["board"], "cha-pt")

    # --- switch on: the two counts and the limit ---------------------------------

    def test_switch_on_one_glm_change_request_still_passes_the_glm_reviewer(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer-glm"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer-glm")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (0, 1))

    def test_switch_on_two_glm_change_requests_pass_the_opus_reviewer(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer-glm", "harness-reviewer-glm"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (0, 2))

    def test_switch_on_limit_zero_passes_the_opus_reviewer(self):
        self.build_db("harness")
        config = switch_config(True, max_glm_review_change_requests=0)
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")

    def test_switch_on_limit_missing_passes_the_opus_reviewer(self):
        self.build_db("harness")
        config = switch_config(True)
        del config["routing"]["glm_review"]["max_glm_review_change_requests"]
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")

    def test_switch_on_one_opus_change_request_passes_the_opus_reviewer(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (1, 0))

    def test_switch_on_opus_change_request_with_glm_change_requests_passes_the_opus_reviewer(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer-glm", "harness-reviewer",
                                          "harness-reviewer-glm"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (1, 2))

    def test_switch_on_change_request_of_another_board_reviewer_is_not_counted(self):
        # A changes_requested event whose reviewer is neither the board's Opus
        # reviewer nor one of its glm_reviewers counts towards neither A nor G.
        self.build_db("harness")
        self.add_events("harness", CARD, ["jobcron-reviewer", "jss-reviewer-glm"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer-glm")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (0, 0))

    # --- switch on: a reviewer argument already given ----------------------------

    def test_switch_on_a_given_reviewer_argument_is_replaced(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1",
                               {"task_id": CARD, "board": "harness", "reviewer": "harness-reviewer"})
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer-glm")

    # --- switch on: other sessions keep the arguments unchanged ------------------

    def test_switch_on_claude_worker_keeps_arguments_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls, [None])
        self.assertEqual(self.choice_records(), [])

    def test_switch_on_reviewer_session_keeps_arguments_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-reviewer", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls, [None])
        self.assertEqual(self.choice_records(), [])

    def test_switch_on_orchestrator_session_keeps_arguments_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-orchestrator", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls, [None])
        self.assertEqual(self.choice_records(), [])

    def test_switch_on_routing_disabled_keeps_arguments_unchanged(self):
        self.build_db("harness")
        config = switch_config(True)
        config["routing"]["enabled"] = False
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls, [None])
        self.assertEqual(self.choice_records(), [])
        self.assertEqual(self.clear_records(), [])

    # --- switch on: missing data -------------------------------------------------

    def test_switch_on_missing_opus_reviewer_keeps_arguments_unchanged(self):
        self.build_db("harness")
        config = switch_config(True)
        del config["routing"]["boards"]["harness"]["opus_reviewer"]
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "reviewer_not_configured"))

    def test_switch_on_missing_glm_reviewers_keeps_arguments_unchanged(self):
        self.build_db("harness")
        config = switch_config(True)
        del config["routing"]["boards"]["harness"]["glm_reviewers"]
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "reviewer_not_configured"))

    def test_switch_on_unknown_board_keeps_arguments_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "not-a-board"})
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "board_not_configured"))

    def test_switch_on_unrecognized_task_id_keeps_arguments_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1", {"task_id": "not-a-task-id", "board": "harness"})
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]),
                         (False, "task_id_not_recognized"))

    def test_switch_on_database_read_error_keeps_arguments_unchanged(self):
        self.build_db("harness")
        (self.db_dir / "harness" / "kanban.db").unlink()
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "read_error"))

    # --- switch off ---------------------------------------------------------------

    def test_switch_off_no_change_requests_and_no_reviewer_argument_is_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"},
                               config=switch_config(False))
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["switch"], record["applied"], record["not_applied_reason"]),
                         (False, False, None))

    def test_switch_off_missing_glm_review_section_is_unchanged(self):
        self.build_db("harness")
        config = switch_config(False)
        del config["routing"]["glm_review"]
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"}, config=config)
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual(record["switch"], False)

    def test_switch_off_reviewer_argument_naming_the_glm_reviewer_passes_the_opus_reviewer(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1",
                               {"task_id": CARD, "board": "harness", "reviewer": "harness-reviewer-glm"},
                               config=switch_config(False))
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")
        [record] = self.choice_records()
        self.assertEqual(record["applied"], True)

    def test_switch_off_latest_change_request_by_the_glm_reviewer_passes_the_opus_reviewer(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer", "harness-reviewer-glm"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"},
                               config=switch_config(False))
        self.assertEqual(calls[0]["reviewer"], "harness-reviewer")
        [record] = self.choice_records()
        self.assertEqual((record["opus_change_requests"], record["glm_change_requests"]), (1, 1))

    def test_switch_off_latest_change_request_by_the_opus_reviewer_is_unchanged(self):
        self.build_db("harness")
        self.add_events("harness", CARD, ["harness-reviewer-glm", "harness-reviewer"])
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"},
                               config=switch_config(False))
        self.assertEqual(calls, [None])
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["reviewer"]), (False, None))

    def test_switch_off_reviewer_argument_naming_the_opus_reviewer_is_unchanged(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1",
                               {"task_id": CARD, "board": "harness", "reviewer": "harness-reviewer"},
                               config=switch_config(False))
        self.assertEqual(calls, [None])

    # --- the clear_override step still runs ----------------------------------------

    def test_the_clear_override_step_still_runs_once_and_writes_its_record(self):
        self.build_db("harness")
        calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "set-model", CARD, "none"]])
        [record] = self.clear_records()
        self.assertEqual((record["event"], record["task_id"], record["applied"]),
                         ("clear_override", CARD, True))

    def test_switch_off_still_clears_the_override(self):
        self.build_db("harness")
        self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"},
                    config=switch_config(False))
        self.assertEqual(fake_hermes_calls(self.calls_log),
                         [["kanban", "--board", "harness", "set-model", CARD, "none"]])
        self.assertEqual(len(self.clear_records()), 1)

    # --- the record fields ----------------------------------------------------------

    def test_the_record_has_exactly_the_fields_of_the_card(self):
        # The record holds ts and profile (added by the log writer), event, the
        # fields of the card and the unused fields of the decisions stream as null.
        self.build_db("harness")
        self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        [record] = self.choice_records()
        self.assertEqual(set(record), {"ts", "profile", "event", *RECORD_FIELDS, *STREAM_NULL_FIELDS})
        self.assertEqual(record["event"], "review_choice")
        self.assertTrue(all(record[field] is None for field in STREAM_NULL_FIELDS))

    def test_no_other_argument_value_is_written(self):
        self.build_db("harness")
        self.review("harness-worker-glm-1",
                    {"task_id": CARD, "board": "harness", "summary": "SUMMARY-SENTINEL",
                     "metadata": {"a": "METADATA-SENTINEL"}, "artifacts": ["ARTIFACT-SENTINEL"]})
        logged = "\n".join(path.read_text(encoding="utf-8") for path in self.log_dir.rglob("*.jsonl"))
        for sentinel in ("SUMMARY-SENTINEL", "METADATA-SENTINEL", "ARTIFACT-SENTINEL"):
            self.assertNotIn(sentinel, logged)

    # --- next_call exactly once --------------------------------------------------------

    def test_next_call_is_called_exactly_once_on_every_path(self):
        self.build_db("harness")
        for config in (switch_config(True), switch_config(False)):
            with self.subTest(switch=config["routing"]["glm_review"]["enabled"]):
                self.calls_log.unlink(missing_ok=True)
                calls, _ = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"},
                                       config=config)
                self.assertEqual(len(calls), 1)

    def test_next_call_runs_once_with_unchanged_arguments_when_the_new_code_raises(self):
        self.build_db("harness")
        with mock.patch.object(routing, "_review_payload", side_effect=RuntimeError("boom")):
            calls, result = self.review("harness-worker-glm-1", {"task_id": CARD, "board": "harness"})
        self.assertEqual(calls, [None])
        self.assertEqual(result, "tool result")
        [record] = self.choice_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "read_error"))

    # --- the shipped configuration -------------------------------------------------------

    def test_shipped_config_names_the_opus_reviewer_of_every_board(self):
        boards = CONFIG["routing"]["boards"]
        self.assertEqual(sorted(boards), sorted(BOARD_OF))
        for board, name in OPUS_OF.items():
            with self.subTest(board=board):
                self.assertEqual(boards[board]["opus_reviewer"], name)
                self.assertNotIn(name, boards[board]["glm_reviewers"])
        # Card t_e61ee47c turned GLM review on (owner approval of 2026-11-15).
        self.assertEqual(CONFIG["routing"]["glm_review"],
                         {"enabled": True, "max_glm_review_change_requests": 2})


if __name__ == "__main__":
    unittest.main()
