#!/usr/bin/env python3
"""The change request counting of handle_request_changes (card t_eea37bed).

Offline tests of the jev plugin only: no live /Users/chanbla11mit/.hermes reads, no board
access other than a temporary database, no network and no model calls. Every test sets
its own environment with mock.patch.dict(os.environ, ...) and writes plugin logs only
to a temporary directory, so the result does not depend on the profile that runs them.

The board database is synthetic and every board change goes through the fake
``hermes`` command of tests/test_jev_client.py, which applies ``set-model`` and
``reassign`` to it, as the tests of tests/test_jev_routing.py do. The reviewer of
each ``changes_requested`` event is written to its payload, as the Hermes
``request_changes`` function writes it (``hermes_cli/kanban_db.py``).
"""
from __future__ import annotations

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

# The names of board ``harness`` in the shipped configuration, used unchanged: the
# GLM reviewer, the Opus reviewer, the GLM worker that holds the cards below, the
# one GLM worker of the `hard` route (limit 3), and the Claude workers.
GLM_REVIEWER = "harness-reviewer-glm"
OPUS_REVIEWER = "harness-reviewer"
GLM_CARD = "t_5a1e0001"          # of harness-worker-glm-easy-1; easy and medium, limit 5
HARD_CARD = "t_5a1e0003"         # of harness-worker-glm-hard-1; the hard route, limit 3
CLAUDE_WORKER = "harness-worker"


def event_payload(reviewer=None):
    """The payload of one ``changes_requested`` event: an unreadable text for
    ``"broken"``, a payload without ``reviewer`` for None, else a payload that
    names the reviewer, as Hermes writes it."""
    if reviewer == "broken":
        return "{not json"
    if reviewer is None:
        return json.dumps({"implementer": "harness-worker-glm-easy-1", "reason": "fix"})
    return json.dumps({"reason": "fix", "implementer": "harness-worker-glm-easy-1", "reviewer": reviewer})


class CountedChangeRequestTests(unittest.TestCase):
    """Card t_eea37bed: a change request of the board's GLM reviewer does not
    count towards the GLM worker's change request limit; every other change
    request counts. The counted number is the ``escalate`` record's
    ``change_requests`` value."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = isolated_env(self.dir)
        self.db = Path(env["HERMES_KANBAN_HOME"]) / "kanban" / "boards" / "harness" / "kanban.db"
        build_board_db(self.db, [(GLM_CARD, "ready", "harness-worker-glm-easy-1"),
                                 (HARD_CARD, "ready", "harness-worker-glm-hard-1")])
        self.hermes = write_fake_hermes(self.dir)
        self.calls_log = self.dir / "hermes-calls.jsonl"
        self.log_dir = self.dir / "logs"
        env.update({"FAKE_HERMES_LOG": str(self.calls_log), "FAKE_KANBAN_DB": str(self.db),
                    "HERMES_PROFILE": OPUS_REVIEWER, "HERMES_KANBAN_TASK": GLM_CARD,
                    "HERMES_KANBAN_BOARD": "harness"})
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = json.loads(json.dumps(CONFIG))

    # --- helpers ---------------------------------------------------------------

    def add_events(self, task_id, reviewers):
        """One ``changes_requested`` event per entry of ``reviewers``, written
        to the temporary database with the payload of ``event_payload``."""
        import sqlite3
        conn = sqlite3.connect(self.db)
        for reviewer in reviewers:
            conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, 0)",
                         (task_id, "changes_requested", event_payload(reviewer)))
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

    def request_changes(self, task_id, args=None):
        """Run ``handle_request_changes`` for ``task_id`` as the middleware
        calls it; the card id is passed in ``args`` (not read from the
        environment), so a card other than ``GLM_CARD`` is reached too."""
        result = '{"ok": true, "task_id": "%s", "status": "ready"}' % task_id
        calls = []

        def next_call(payload=None):
            calls.append(payload)
            return result

        out = routing.handle_request_changes(args if args is not None else {"reason": "fix the test"},
                                             next_call, config=self.config, command=self.hermes,
                                             state_dir=self.log_dir)
        self.assertEqual(calls, [None])   # the call runs once, with its own arguments
        self.assertEqual(out, result)     # and its result is returned unchanged
        return out

    def escalations(self):
        return [r for r in read_records(self.log_dir, "decisions") if r["event"] == "escalate"]

    # --- a `hard` card with limit 3: the two GLM reviewer returns stay uncounted ---

    def test_hard_card_two_glm_and_one_opus_change_requests_do_not_reassign(self):
        self.add_events(HARD_CARD, [GLM_REVIEWER, GLM_REVIEWER, OPUS_REVIEWER])
        self.request_changes(HARD_CARD, {"task_id": HARD_CARD, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(HARD_CARD)[1], "harness-worker-glm-hard-1")
        self.assertEqual(self.escalations(), [])

    def test_hard_card_two_more_opus_change_requests_reassign(self):
        # The three counted change requests of the Opus reviewer reach the
        # limit 3 of the `hard` route; the two GLM reviewer change requests
        # before them did not count.
        self.add_events(HARD_CARD, [GLM_REVIEWER, GLM_REVIEWER, OPUS_REVIEWER,
                                    OPUS_REVIEWER, OPUS_REVIEWER])
        self.request_changes(HARD_CARD, {"task_id": HARD_CARD, "reason": "again"})
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", HARD_CARD, "none"],
            ["kanban", "--board", "harness", "reassign", HARD_CARD, CLAUDE_WORKER, "--reclaim"],
        ])
        self.assertEqual(tuple(self.card(HARD_CARD)), ("ready", CLAUDE_WORKER, None))
        [record] = self.escalations()
        self.assertEqual((record["task_id"], record["original_assignee"], record["new_assignee"],
                          record["change_requests"], record["applied"], record["applied_route"],
                          record["max_glm_change_requests"]),
                         (HARD_CARD, "harness-worker-glm-hard-1", CLAUDE_WORKER, 3, True, None, 3))

    # --- an `easy` card with limit 5 ------------------------------------------

    def test_easy_card_two_glm_change_requests_count_zero(self):
        # Two GLM reviewer change requests alone stay under the limit 5 of an
        # `easy` card: counted 0.
        self.add_events(GLM_CARD, [GLM_REVIEWER, GLM_REVIEWER])
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-easy-1")
        self.assertEqual(self.escalations(), [])

    def test_easy_card_five_glm_change_requests_count_zero(self):
        # Five GLM reviewer change requests still count 0 on an `easy` card
        # with limit 5: no reassignment even above the event count of the
        # limit, because no event counts.
        self.add_events(GLM_CARD, [GLM_REVIEWER] * 5)
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.card(GLM_CARD)[1], "harness-worker-glm-easy-1")
        self.assertEqual(self.escalations(), [])

    def test_easy_card_four_glm_and_one_opus_change_request_reassigns(self):
        # One Opus reviewer change request counts 1 on an `easy` card with
        # limit 5, so it stays; five counted Opus requests reach the limit.
        self.add_events(GLM_CARD, [GLM_REVIEWER] * 4 + [OPUS_REVIEWER])
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.add_events(GLM_CARD, [OPUS_REVIEWER] * 4)
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [
            ["kanban", "--board", "harness", "set-model", GLM_CARD, "none"],
            ["kanban", "--board", "harness", "reassign", GLM_CARD, CLAUDE_WORKER, "--reclaim"],
        ])
        [record] = self.escalations()
        self.assertEqual((record["change_requests"], record["max_glm_change_requests"],
                          record["applied"]), (5, 5, True))

    # --- events without a readable reviewer ------------------------------------

    def test_events_without_a_reviewer_are_counted(self):
        # An event whose payload has no `reviewer` and one whose payload cannot
        # be read are counted (the behaviour before this card).
        self.add_events(GLM_CARD, [None, "broken", GLM_REVIEWER])
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.assertEqual(self.escalations(), [])
        # With two more events without a reviewer the counted number reaches 4;
        # one more counted event reaches the limit 5.
        self.add_events(GLM_CARD, [None, None])
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.add_events(GLM_CARD, ["broken"])
        self.request_changes(GLM_CARD)
        [record] = self.escalations()
        self.assertEqual(record["change_requests"], 5)

    def test_a_board_without_glm_reviewers_counts_every_change_request(self):
        # The shipped configuration of the board names the GLM reviewer; a copy
        # of the configuration without the list `glm_reviewers` counts every
        # change request, the number of the card's events (the behaviour
        # before this card).
        self.config["routing"]["boards"]["harness"]["glm_reviewers"] = []
        self.add_events(GLM_CARD, [GLM_REVIEWER, GLM_REVIEWER, GLM_REVIEWER])
        self.request_changes(GLM_CARD)
        self.assertEqual(fake_hermes_calls(self.calls_log), [])
        self.add_events(GLM_CARD, [GLM_REVIEWER, OPUS_REVIEWER])
        self.request_changes(GLM_CARD)
        [record] = self.escalations()
        self.assertEqual((record["change_requests"], record["max_glm_change_requests"],
                          record["applied"]), (5, 5, True))

    def test_the_escalate_record_change_requests_is_the_counted_number(self):
        # Three GLM reviewer events and five Opus reviewer events on an `easy`
        # card: counted 5, the number written to the record. The handler adds
        # no field beyond the fields it wrote before this card.
        import jev_log
        self.add_events(GLM_CARD, [GLM_REVIEWER, GLM_REVIEWER, GLM_REVIEWER,
                                   OPUS_REVIEWER, OPUS_REVIEWER, OPUS_REVIEWER,
                                   OPUS_REVIEWER, OPUS_REVIEWER])
        self.request_changes(GLM_CARD)
        [record] = self.escalations()
        self.assertEqual(record["change_requests"], 5)
        self.assertEqual(set(record), {"ts", "profile"} | set(jev_log.STREAM_FIELDS["decisions"])
                         | {"change_requests", "max_glm_change_requests",
                            "assigned_worker_line", "assigned_worker_line_error_class"})
        self.assertEqual(record["assigned_worker_line"], "no_line")

    def test_change_request_state_still_counts_every_event(self):
        # `change_request_state` keeps its return value: the third item is the
        # number of the card's `changes_requested` events, GLM reviewer events
        # included.
        import sqlite3
        self.add_events(GLM_CARD, [GLM_REVIEWER, GLM_REVIEWER, OPUS_REVIEWER])
        conn = sqlite3.connect(self.db)
        try:
            conn.row_factory = sqlite3.Row
            self.assertEqual(routing.change_request_state(conn, GLM_CARD),
                             ("ready", "harness-worker-glm-easy-1", 3))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
