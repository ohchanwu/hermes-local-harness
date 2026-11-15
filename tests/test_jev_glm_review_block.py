#!/usr/bin/env python3
"""The kanban_block pass middleware of a GLM reviewer session (card t_50e10b37).

Offline tests of the jev plugin only: no live /Users/chanbla11mit/.hermes reads, no board
access other than a temporary database, no network and no model calls. Every test sets
HERMES_PROFILE itself with mock.patch.dict(os.environ, ...) and writes plugin logs only to
a temporary directory, so the result does not depend on the profile that runs the tests.

Every test goes through ``jev._tool_execution``. The temporary Kanban database holds the
one column that the new code reads: ``tasks.block_kind``.
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

from test_jev_client import isolated_env, read_records  # noqa: E402

CARD = "t_0a1b2c3d"
PASS_REASON = "jev-glm-review-pass"
REASON = PASS_REASON + " no findings"
OK_RESULT = json.dumps({"ok": True, "task_id": CARD, "status": "blocked", "block_kind": "needs_input"})
ERROR_RESULT = json.dumps({"error": "could not block " + CARD})
# The fields of item 1.e of the card (the event plus the eight data fields).
RECORD_FIELDS = ("event", "board", "task_id", "profile", "kind", "applied", "not_applied_reason",
                 "error_class", "tool_error")
# The fields of the decisions stream that this card does not use; the log writer
# adds each of them as null.
STREAM_NULL_FIELDS = ("original_assignee", "new_assignee", "orchestrator_model", "route",
                      "probabilities", "confidence", "applied_route", "glm_probability_sum",
                      "jev_latency_ms", "jev_input_tokens", "held_until")


def build_board_db(path: Path, task_id, block_kind) -> None:
    """A temporary board database whose ``tasks`` table has ``block_kind``."""
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT,"
                 " assignee TEXT, block_kind TEXT)")
    conn.execute("INSERT INTO tasks (id, title, status, assignee, block_kind) VALUES (?, ?, ?, ?, ?)",
                 (task_id, "synthetic card", "running", "harness-reviewer-glm", block_kind))
    conn.commit()
    conn.close()


class GlmReviewPassBlockTests(unittest.TestCase):
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
        self.board_dir = self.dir / "kanban-home" / "kanban" / "boards"
        self.plugin = importlib.import_module("jev")

    # --- helpers ---------------------------------------------------------------

    def build_db(self, board="harness", task_id=CARD, block_kind=None, with_card=True) -> Path:
        path = self.board_dir / board / "kanban.db"
        if with_card:
            build_board_db(path, task_id, block_kind)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
        return path

    def call(self, profile, args, result=OK_RESULT, env=None):
        """Run ``kanban_block`` through ``_tool_execution`` as ``profile``; returns (calls, out)."""
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return result

        full_env = {"HERMES_PROFILE": profile, "HERMES_KANBAN_BOARD": "harness"}
        full_env.update(env or {})
        with mock.patch.dict(os.environ, full_env):
            out = self.plugin._tool_execution(tool_name="kanban_block", args=args, next_call=next_call)
        return calls, out

    def pass_records(self) -> list:
        return [r for r in read_records(self.log_dir, "decisions") if r.get("event") == "glm_review_pass_block"]

    def pass_args(self, **extra):
        args = {"task_id": CARD, "reason": REASON}
        args.update(extra)
        return args

    # --- the kind rule -----------------------------------------------------------

    def test_pass_reason_and_null_block_kind_passes_kind_needs_input(self):
        self.build_db(block_kind=None)
        args = self.pass_args()
        frozen = dict(args)
        calls, out = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [{**frozen, "kind": "needs_input"}])
        self.assertEqual(args, frozen)  # the original args object is unchanged
        self.assertEqual(len(calls), 1)  # next_call is called exactly once
        [record] = self.pass_records()
        self.assertEqual((record["kind"], record["applied"], record["not_applied_reason"]),
                         ("needs_input", True, None))

    def test_pass_reason_and_block_kind_needs_input_passes_kind_capability(self):
        self.build_db(block_kind="needs_input")
        calls, _ = self.call("harness-reviewer-glm", self.pass_args())
        self.assertEqual(calls[0]["kind"], "capability")
        [record] = self.pass_records()
        self.assertEqual((record["kind"], record["applied"]), ("capability", True))

    def test_a_kind_given_by_the_model_is_replaced(self):
        self.build_db(block_kind=None)
        calls, _ = self.call("harness-reviewer-glm", self.pass_args(kind="transient"))
        self.assertEqual(calls[0]["kind"], "needs_input")

    def test_the_reason_text_and_every_other_argument_are_unchanged(self):
        self.build_db(block_kind="capability")
        args = self.pass_args(kind="transient", board="harness", summary="a summary")
        frozen = dict(args)
        calls, _ = self.call("harness-reviewer-glm", args)
        self.assertEqual(args, frozen)
        # ``kind`` is the one argument that the middleware replaces; every other
        # value, also the reason text, reaches the tool unchanged.
        payload = dict(calls[0])
        kind = payload.pop("kind")
        without_kind = {k: v for k, v in frozen.items() if k != "kind"}
        self.assertEqual(payload, without_kind)
        self.assertEqual(kind, "needs_input")

    def test_the_board_argument_of_the_environment_is_used(self):
        self.build_db(block_kind=None)
        calls, _ = self.call("harness-reviewer-glm", {"task_id": CARD, "reason": REASON})
        self.assertEqual(calls[0]["kind"], "needs_input")
        [record] = self.pass_records()
        self.assertEqual(record["board"], "harness")

    # --- the note on the tool result ----------------------------------------------

    def test_the_note_is_added_to_an_ok_result_and_names_the_opus_reviewer(self):
        self.build_db(block_kind=None)
        _calls, out = self.call("harness-reviewer-glm", self.pass_args())
        note = json.loads(out)
        self.assertTrue(note.pop("ok"))
        self.assertEqual(note.pop("task_id"), CARD)
        self.assertEqual(note.pop("status"), "blocked")
        self.assertEqual(note.pop("block_kind"), "needs_input")
        self.assertEqual(set(note), {"jev_note"})
        self.assertIn("harness-reviewer", note["jev_note"])
        self.assertIn("The GLM reviewer ends its run now and calls no other tool.", note["jev_note"])

    def test_no_note_and_no_change_on_an_error_result(self):
        self.build_db(block_kind=None)
        _calls, out = self.call("harness-reviewer-glm", self.pass_args(), result=ERROR_RESULT)
        self.assertEqual(out, ERROR_RESULT)
        [record] = self.pass_records()
        self.assertTrue(record["tool_error"])

    def test_no_note_on_a_result_that_is_not_json(self):
        self.build_db(block_kind=None)
        _calls, out = self.call("harness-reviewer-glm", self.pass_args(), result="tool result")
        self.assertEqual(out, "tool result")
        [record] = self.pass_records()
        self.assertFalse(record["tool_error"])

    def test_the_note_names_no_reviewer_when_the_board_has_no_opus_reviewer(self):
        self.build_db(block_kind=None)
        config = json.loads((PLUGIN_DIR / "config.json").read_text(encoding="utf-8"))
        del config["routing"]["boards"]["harness"]["opus_reviewer"]
        with mock.patch.object(self.plugin, "load_config", return_value=config):
            _calls, out = self.call("harness-reviewer-glm", self.pass_args())
        note = json.loads(out)["jev_note"]
        self.assertIn("Opus reviewer of the board", note)
        self.assertNotIn("harness-reviewer", note)

    # --- step a fails: unchanged arguments -----------------------------------------

    def test_unknown_board_keeps_the_arguments_unchanged(self):
        self.build_db(block_kind=None)
        args = self.pass_args(board="not-a-board")
        frozen = dict(args)
        calls, _ = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        self.assertEqual(args, frozen)
        [record] = self.pass_records()
        self.assertEqual((record["board"], record["applied"], record["not_applied_reason"]),
                         (None, False, "board_not_configured"))

    def test_unrecognized_task_id_keeps_the_arguments_unchanged(self):
        self.build_db(block_kind=None)
        args = self.pass_args(task_id="not-a-task-id")
        calls, _ = self.call("harness-reviewer-glm", args, env={"HERMES_KANBAN_TASK": ""})
        self.assertEqual(calls, [None])
        [record] = self.pass_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]),
                         (False, "task_id_not_recognized"))

    def test_the_task_id_of_the_environment_is_used(self):
        self.build_db(block_kind=None)
        args = {"reason": REASON}  # no task_id argument
        calls, _ = self.call("harness-reviewer-glm", args, env={"HERMES_KANBAN_TASK": CARD})
        self.assertEqual(calls[0]["kind"], "needs_input")
        [record] = self.pass_records()
        self.assertEqual(record["task_id"], CARD)

    def test_missing_card_keeps_the_arguments_unchanged(self):
        self.build_db(block_kind=None, task_id="t_0000ffff")  # the database has another card
        args = self.pass_args()
        calls, _ = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        [record] = self.pass_records()
        self.assertEqual((record["applied"], record["not_applied_reason"]), (False, "card_not_found"))

    def test_database_read_error_keeps_the_arguments_unchanged(self):
        self.build_db(block_kind=None)
        (self.board_dir / "harness" / "kanban.db").unlink()
        args = self.pass_args()
        calls, _ = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        [record] = self.pass_records()
        self.assertEqual((record["applied"], record["not_applied_reason"], record["error_class"]),
                         (False, "read_error", "FileNotFoundError"))

    # --- every other call passes through --------------------------------------------

    def test_another_reason_passes_through_unchanged(self):
        self.build_db(block_kind=None)
        args = self.pass_args(reason="needs a decision")
        calls, out = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        self.assertEqual(out, OK_RESULT)
        self.assertEqual(self.pass_records(), [])

    def test_args_that_are_not_a_dict_pass_through_unchanged(self):
        self.build_db(block_kind=None)
        for args in (["t_0a1b2c3d"], "t_0a1b2c3d", None):
            with self.subTest(args=args):
                calls, out = self.call("harness-reviewer-glm", args)
                self.assertEqual(calls, [None])
                self.assertEqual(out, OK_RESULT)
        self.assertEqual(self.pass_records(), [])

    def test_other_sessions_with_the_pass_reason_pass_through_unchanged(self):
        self.build_db(block_kind=None)
        for profile in ("harness-worker", "harness-worker-glm-1", "harness-reviewer",
                        "harness-orchestrator"):
            with self.subTest(profile=profile):
                calls, out = self.call(profile, self.pass_args())
                self.assertEqual(calls, [None])
                self.assertEqual(out, OK_RESULT)
        self.assertEqual(self.pass_records(), [])

    def test_kanban_complete_and_kanban_request_review_are_still_refused(self):
        self.build_db(block_kind=None)
        for tool_name in ("kanban_complete", "kanban_request_review"):
            with self.subTest(tool_name=tool_name):
                calls = []

                def next_call(payload=None):
                    calls.append(payload)
                    return OK_RESULT

                with mock.patch.dict(os.environ, {"HERMES_PROFILE": "harness-reviewer-glm",
                                                  "HERMES_KANBAN_TASK": CARD}):
                    out = self.plugin._tool_execution(tool_name=tool_name, args={"task_id": CARD},
                                                      next_call=next_call)
                self.assertEqual(calls, [])
                self.assertIn("error", json.loads(out))

    # --- the record ------------------------------------------------------------------

    def test_the_record_has_exactly_the_fields_of_the_card(self):
        self.build_db(block_kind=None)
        _calls, _out = self.call("harness-reviewer-glm", self.pass_args())
        [record] = self.pass_records()
        self.assertEqual({k: record[k] for k in RECORD_FIELDS},
                         {"event": "glm_review_pass_block", "board": "harness", "task_id": CARD,
                          "profile": "harness-reviewer-glm", "kind": "needs_input", "applied": True,
                          "not_applied_reason": None, "error_class": None, "tool_error": False})
        for field in STREAM_NULL_FIELDS:
            self.assertIsNone(record[field], field)
        self.assertEqual(set(record) - {"ts"}, set(RECORD_FIELDS) | set(STREAM_NULL_FIELDS))
        self.assertNotIn(REASON, json.dumps(record))  # no reason text is written

    # --- an exception of the new code ---------------------------------------------------

    def test_an_exception_in_the_dispatch_check_calls_next_call_once_unchanged(self):
        self.build_db(block_kind=None)
        args = self.pass_args()
        with mock.patch.object(self.plugin, "load_config", side_effect=OSError("unreadable")):
            calls, out = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        self.assertEqual(out, OK_RESULT)
        self.assertEqual(self.pass_records(), [])

    def test_an_exception_inside_the_handler_calls_next_call_once_unchanged(self):
        self.build_db(block_kind=None)
        args = self.pass_args()
        frozen = dict(args)
        with mock.patch.object(self.plugin.glm_review.peak_hold, "connect_readonly",
                               side_effect=OSError("no database")):
            calls, out = self.call("harness-reviewer-glm", args)
        self.assertEqual(calls, [None])
        self.assertEqual(args, frozen)
        # The kind was not applied, and the ok result still carries the note.
        self.assertIn("The hold script passes this card to the Opus reviewer", json.loads(out)["jev_note"])
        [record] = self.pass_records()
        self.assertEqual((record["applied"], record["not_applied_reason"], record["error_class"]),
                         (False, "read_error", "OSError"))


if __name__ == "__main__":
    unittest.main()
