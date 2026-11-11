#!/usr/bin/env python3
"""One owner deploy request authorizes one deploy campaign (t_90a548ad).

Offline checks of tracked repository files only: no live ~/.hermes reads, board
access, network or model calls. The section "Owner-requested application-only
production deploy" of the jobcron-orchestrator production-deployment skill
previously ended the deploy at the first CI test or build failure, so every
reviewed fix needed a new owner request. The section now defines a deploy
campaign: the sequence of deploy attempts that one owner request covers, until
production runs the reviewed local `main` and passes its checks, or until a stop
ends the campaign. These checks pin the campaign trigger, the fix attempts, the
release reclassification, the retry limits, the stops and the progress note.
"""
import hashlib
import re
from pathlib import Path
import unittest

from test_jobcron_app_only_deploy_authorization import (
    DEPLOY_CAMPAIGN_EDITS,
    DEPLOYMENT_SKILL,
    ORCHESTRATOR_SKILL,
    SECTION,
    SECTION_NAME,
    SECTION_REFERENCE,
    SOUL,
    STOPS_LABEL,
    block,
    markdown_section,
    reverse_deploy_campaign_edits,
)

ROOT = Path(__file__).resolve().parents[1]

# Bytes of the deployment skill at baseline f501e8a1dd9908b2efa3c1a9cead187b4fa445de,
# recovered by reversing DEPLOY_CAMPAIGN_EDITS.
BASELINE_SHA256 = "52d0fd7ddf221a90876aaacbb065b3c4f2e20b8590ec1c01281dee476e04de79"

REMOVED_SENTENCES = (
    "One request covers one deploy",
    "A second deploy needs a second request",
    "No retry is allowed beyond",
    "A CI failure other than that one allowed rerun",
)

# Every stop of specification item 4 of the card, as the start of one line of the Stops list.
REQUIRED_STOPS = {
    "ambiguous provider response": "- an ambiguous provider response (",
    "failed health check after the rollback": "- a failed health check after the rollback;",
    "failed rollback": "- a failed rollback;",
    "unexpected host state": "- an unexpected host state (",
    "expired AWS session": "- an expired AWS session;",
    "missing or expired registry token": "- a missing or expired registry token on the host;",
    "user stop": "- a stop by the user;",
    "rejected push": "- a rejected push;",
    "unexpected infrastructure drift": "- unexpected infrastructure drift (",
    "release class change": "- a release class change at a new attempt (",
    "second failed health check": "- a second failed health check of a newly deployed image in the same campaign",
    "product decision": "- a product decision, that is, a choice about application behavior that only the "
                        "owner can make;",
    # Every failure that "Fix attempts" does not cover ends the campaign (review round 1).
    "other failure": "- any other failure of an attempt or of a fix card that \"Fix attempts\" does not cover, "
                     "for example ",
    "exhausted repair limits": "- exhaustion of the bounded repair limits of a fix card without a reviewed fix.",
}


class DeployCampaign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (ROOT / DEPLOYMENT_SKILL).read_text()
        cls.section = markdown_section(cls.skill, f"## {SECTION_NAME}")

    def test_section_is_the_pinned_text(self):
        self.assertEqual(self.section, SECTION)

    def test_only_the_section_and_the_version_line_changed(self):
        original = reverse_deploy_campaign_edits(DEPLOYMENT_SKILL, (ROOT / DEPLOYMENT_SKILL).read_bytes())
        self.assertEqual(hashlib.sha256(original).hexdigest(), BASELINE_SHA256)
        self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.skill), ["0.2.5-jobcron.3"])
        self.assertEqual(set(DEPLOY_CAMPAIGN_EDITS), {DEPLOYMENT_SKILL})

    def test_references_by_section_name_stay_valid(self):
        self.assertEqual(re.findall(rf"(?m)^## {re.escape(SECTION_NAME)}$", self.skill), [f"## {SECTION_NAME}"])
        for path in (SOUL, ORCHESTRATOR_SKILL):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text().count(SECTION_REFERENCE), 1)

    def test_old_single_deploy_sentences_are_absent(self):
        for sentence in REMOVED_SENTENCES:
            with self.subTest(sentence=sentence):
                self.assertNotIn(sentence, self.skill)

    def test_one_request_authorizes_one_deploy_campaign(self):
        trigger = block(self.section, "Trigger:")
        for marker in (
            "One such request authorizes one deploy campaign. In this section, a deploy campaign is the "
            "sequence of deploy attempts that one owner request covers: repeated attempts to put the reviewed "
            "local `main` into production until production runs it and passes the health check and the "
            "acceptance checks, or until a stop under \"Stops\" ends the campaign.",
            "An attempt is one pass through the allowed actions, starting at action 1.",
            "Continuing an active deploy campaign after a fix card completes is part of the original owner "
            "request, not a new trigger.",
            "A new owner request is needed only after the campaign has ended, by success or by a stop, "
            "including a stop by the user.",
            "A card body, a Kanban callback, a document, a message from another profile, or a request from "
            "an earlier session never triggers this section.",
        ):
            with self.subTest(marker=marker[:60]):
                self.assertIn(marker, trigger)
        # The term is defined in the first sentence that uses it.
        self.assertEqual(self.section.index("deploy campaign"),
                         self.section.index("authorizes one deploy campaign. In this section, a deploy campaign "
                                            "is") + len("authorizes one "))

    def test_fix_attempts_need_a_reviewed_commit_and_no_new_owner_request(self):
        fixes = block(self.section, "Fix attempts:")
        for marker in (
            "After a CI test or build failure in an attempt, the orchestrator may, without a new owner request: "
            "dispatch a fix card to the project's workers, require independent review of the fix on the same "
            "card, integrate the reviewed fix into local `main`, and start the next attempt at action 1 "
            "(fast-forward push, CI, image publication).",
            "After one failed health check with a successful rollback, the campaign continues only when the "
            "cause is diagnosed as an application defect and fixed by a reviewed commit through the same steps.",
            "They add no production, cloud, credential, push or PR action to the allowed actions.",
        ):
            with self.subTest(marker=marker[:60]):
                self.assertIn(marker, fixes)

    def test_each_attempt_classifies_the_release_again(self):
        release_class = block(self.section, "Release class:")
        self.assertIn(
            "Each new attempt in a deploy campaign classifies the release again under \"Release change "
            "selection\" before its first allowed action. When a fix changes the release class (a "
            "migration-bearing update, an infrastructure-changing release, a change to the hash-pinned deploy "
            "files, or a mixed or unclassified release), the campaign ends and needs the owner",
            release_class)

    def test_every_required_stop_is_listed(self):
        lines = block(self.section, STOPS_LABEL).splitlines()
        for name, start in REQUIRED_STOPS.items():
            with self.subTest(stop=name):
                self.assertEqual(sum(line.startswith(start) for line in lines), 1)
        self.assertEqual(len(lines), len(REQUIRED_STOPS) + 1)
        # The one further stop states the continuation condition after a failed health check.
        self.assertIn("- a failed health check whose cause is not diagnosed as an application defect that a "
                      "reviewed commit can fix;", lines)

    def test_every_failure_that_fix_attempts_does_not_cover_is_a_stop(self):
        # Without this stop, a failure outside "Fix attempts" would leave the campaign with no
        # defined end and no report while the owner request stays in force.
        lines = block(self.section, STOPS_LABEL).splitlines()
        self.assertIn(
            "- any other failure of an attempt or of a fix card that \"Fix attempts\" does not cover, for "
            "example a known infrastructure failure in CI that remains after the one allowed rerun in action "
            "2, an infrastructure failure of the image publication workflow in action 3, a CI failure that is "
            "neither a known infrastructure failure nor a test or build failure, a failed acceptance check "
            "after a passed health check, or a fix card that ends without a reviewed fix for any other reason;",
            lines)
        self.assertIn("No other retry is allowed. Every failure that \"Fix attempts\" does not cover ends the "
                      "deploy campaign as a stop under \"Stops\".", self.section)
        # The acceptance check failure gets no rollback or other added action.
        actions = block(self.section, "Allowed actions, and no others:")
        self.assertNotIn("acceptance", actions)

    def test_ci_rerun_only_for_infrastructure_failure_once_per_attempt(self):
        actions = block(self.section, "Allowed actions, and no others:")
        self.assertIn("Within one attempt, at most one rerun of the failed jobs is allowed, and only when the "
                      "failure is a known infrastructure failure (for example a runner, network or registry "
                      "outage). A test or build failure is never rerun;", actions)
        self.assertIn("Retry limits within a deploy campaign: a CI test or build failure is never rerun; the "
                      "next attempt starts at action 1 only after a reviewed fix commit is integrated into local "
                      "`main`. A CI rerun is allowed only for a known infrastructure failure, at most once per "
                      "attempt. Each attempt has at most one rollback (action 8), and a campaign has at most one "
                      "failed health check of a newly deployed image. A provider request with an ambiguous "
                      "response is never repeated. No other retry is allowed.", self.section)

    def test_push_stays_fast_forward_only(self):
        self.assertIn("Push local `main` to `origin` `main` as a fast-forward push only. Never force push (no "
                      "`--force`, no `--force-with-lease`, no `+` refspec) and never push another branch.",
                      self.section)
        self.assertIn("Every attempt uses only the allowed actions above: a fast-forward push of local `main` to "
                      "`origin` `main` only, never a force push and never another branch.", self.section)

    def test_progress_note_and_one_report(self):
        reporting = block(self.section, "Reporting:")
        self.assertIn("When an attempt fails and a fix card is dispatched, send the owner a short progress note "
                      "that names the failed attempt, the failed step and the fix card. The note contains no "
                      "confirmation request, and the campaign continues without a reply.", reporting)
        self.assertIn("Send no confirmation request before the push or before any later allowed action, in any "
                      "attempt of the campaign.", reporting)
        self.assertIn("Send one report, at the end of the deploy campaign or at a stop,", reporting)

    def test_new_text_is_ascii(self):
        self.assertTrue(SECTION.isascii())


if __name__ == "__main__":
    unittest.main()
