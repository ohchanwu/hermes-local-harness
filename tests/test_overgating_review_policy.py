#!/usr/bin/env python3
"""Offline contracts for the reviewer overgating checklist and reviewer SOULs.

Checks tracked repository text and pins only; no model call, no live profile read.
"""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "policies/overgating-review.md"
CHECKLIST_ABS = "/Users/chanbla11mit/hermes-local-harness/policies/overgating-review.md"
REVIEWERS = ("harness-reviewer", "chapt-reviewer", "jobcron-reviewer")
EVIDENCE = (
    "261007-jobcron-upgrade-orchestration-repeated-first-launch-ceremony.md",
    "261013-chapt-calendar-rollout-overcomplicated-bootstrap-plan.md",
    "261013-jobcron-over-gating-readonly-incident-assessment.md",
    "261017-repair-history-formatting-blocked-approved-completion.md",
)
ITEMS = {
    1: ("approval", "already-authorized local, reversible, or read-only work", "bookkeeping"),
    2: ("Bookkeeping or format validity", "completion, integration, or dispatch prerequisite"),
    3: ("Aggregate numeric ceilings", "reserved-slot arithmetic", "harmless actions"),
    4: ("campaign deadlines", "latest-start cutoffs", "authorization expiry", "worst-case timing"),
    5: ("Setup-only holds", "claim-then-block"),
    6: ("campaign-wide halt", "named dependency"),
    7: ("First-launch/migration-grade ceremony", "re-verifying unchanged accepted evidence",
        "missing operator prose treated as missing implementation"),
    8: ("only accumulate", "never retired"),
}
DO_NOT_FLAG = (
    "External writes (push, PR, deploy)", "Credentials/MFA", "provider credential expiry",
    "Live profile, skill, policy, board, or gateway changes", "Production/cloud mutation",
    "non-idempotent migration", "nonempty/clinical data", "Ambiguous provider/transaction outcomes",
    "Real cost/rate limits", "Network/subprocess timeouts and watchdogs", "User stop",
    "Removing overgating must never weaken those controls.",
)
# Existing rules each SOUL must keep verbatim.
PRESERVED = {
    "harness-reviewer": (
        "Accept review only for a card on board `harness`",
        "Reject and block any boundary mismatch.",
        "Never edit implementation code.",
        "Use `kanban_complete` for approval and `kanban_request_changes` for actionable same-card rework.",
        "Files under `docs/bugs/` are evidence and triage input, not automatic implementation authorization.",
        "Harness work is local-only by default. Never access Jobcron, Cha PT, another board or repository, deploy live profile or skill policy, change board or gateway state, access credentials, push, open a PR, mutate production/cloud state, or perform another external action without explicit human authorization.",
    ),
    "chapt-reviewer": (
        "Accept review only for a card on board `cha-pt`",
        "Reject and block any boundary mismatch or in-place repository switch.",
        "Never edit implementation code.",
        "Any operator-protected path change requires explicit human authorization naming those paths on the exact card; passing protected checks is not authorization.",
        "Reject any other push, merge, PR, preview, deployment, cloud, production, or external-write statement, or an undeclared/protected path.",
        "Never access Jobcron, another board, production/cloud state, credentials, deployments, pushes, PRs, or external systems without explicit human authorization.",
    ),
    "jobcron-reviewer": (
        "Accept review only for a card on board `jobcron`",
        "Preserve and verify the actual implementer provenance; never relabel a run.",
        "Owner-authorized prospective specification/plan readiness reviews may review documents authored by `jobcron-orchestrator`.",
        "This narrow exception does not admit controller-authored application implementation for code review, relax worker provenance requirements, resume implementation, clear another card's HUMAN_BLOCK, or grant production authority.",
        "Never edit implementation code or the reviewed documents.",
        "return consolidated document corrections to its author on the same card without manufacturing implementer provenance.",
        "Never access Cha PT, another board, production/cloud state, credentials, deployments, pushes, or PRs.",
    ),
}


def soul(profile):
    return (ROOT / f"policies/profile-souls/{profile}/SOUL.md").read_text()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Checklist(unittest.TestCase):
    def setUp(self):
        self.text = CHECKLIST.read_text()

    def test_concise(self):
        self.assertLessEqual(len(self.text.splitlines()), 60)

    def test_scope_and_mechanism_rule(self):
        self.assertIn("specification, implementation plan, procedure/runbook, policy, or card template", self.text)
        self.assertIn("names the concrete failure mechanism it controls", self.text)
        self.assertIn("still live at that step", self.text)

    def test_items_one_to_eight(self):
        for number, markers in ITEMS.items():
            line = next((l for l in self.text.splitlines() if l.startswith(f"{number}. ")), "")
            self.assertTrue(line, number)
            for marker in markers:
                self.assertIn(marker, line, number)

    def test_do_not_flag(self):
        self.assertIn("## Do not flag genuine controls", self.text)
        for marker in DO_NOT_FLAG:
            self.assertIn(marker, self.text)

    def test_verdict_and_authority(self):
        self.assertIn("Material finding: overgating that would block, stall, or add owner prompts to otherwise authorized work", self.text)
        self.assertIn("`kanban_request_changes` naming the gate, why its mechanism is absent or not live, and the proportionate replacement (often deletion)", self.text)
        self.assertIn("Non-blocking note: minor ceremony that blocks nothing", self.text)
        self.assertIn("governs review findings only and grants no new authority", self.text)
        for profile in REVIEWERS:
            self.assertIn(f"`{profile}`", self.text)

    def test_links_resolve(self):
        links = re.findall(r"\]\(([^)]+)\)", self.text)
        self.assertTrue(links)
        for link in links:
            self.assertFalse(link.startswith(("/", "http")), link)
            self.assertTrue((CHECKLIST.parent / link).resolve().is_file(), link)
        for report in EVIDENCE:
            self.assertIn(f"../docs/bugs/{report}", links)

    def test_docs_index(self):
        self.assertIn("(../policies/overgating-review.md)", (ROOT / "docs/README.md").read_text())


class ReviewerSouls(unittest.TestCase):
    def test_reference_and_verdict_rule(self):
        for profile in REVIEWERS:
            text = soul(profile)
            with self.subTest(profile=profile):
                self.assertEqual(text.count(CHECKLIST_ABS), 1)
                self.assertIn("would block, stall, or add owner prompts to otherwise authorized work is a material finding", text)
                self.assertIn("naming the gate, why its mechanism is absent or not live, and the proportionate replacement", text)
                self.assertIn("Minor ceremony that blocks nothing is a non-blocking note in the approval.", text)
                self.assertIn("grants no new authority, and never weakens the boundaries in this file", text)

    def test_model_neutral(self):
        for profile in REVIEWERS:
            text = soul(profile)
            with self.subTest(profile=profile):
                self.assertNotIn("GPT-6 Astra", text)
                self.assertNotRegex(text, r"running (GPT|Fable|Claude|GLM)")

    def test_existing_rules_preserved(self):
        for profile, rules in PRESERVED.items():
            text = soul(profile)
            for rule in rules:
                with self.subTest(profile=profile, rule=rule[:40]):
                    self.assertIn(rule, text)

    def test_paragraph_short(self):
        for profile in REVIEWERS:
            paragraph = next(p for p in soul(profile).split("\n\n") if CHECKLIST_ABS in p)
            self.assertLessEqual(len(paragraph.splitlines()), 6, profile)
            self.assertLessEqual(len(paragraph), 1000, profile)


class SoulPins(unittest.TestCase):
    def test_roster_and_snapshot_match_tracked_bytes(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())["profile_souls"]
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())["profile_souls"]
        self.assertEqual(roster, snapshot)
        for profile in ("harness-reviewer", "chapt-reviewer"):
            self.assertIn(profile, snapshot)
        for profile, entry in snapshot.items():
            with self.subTest(profile=profile):
                self.assertEqual(entry["sha256"], sha(ROOT / entry["source"]))

    def test_fixture_pins(self):
        pins = {p: sha(ROOT / f"policies/profile-souls/{p}/SOUL.md") for p in ("harness-reviewer", "chapt-reviewer")}
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            observed = json.loads(fixture.read_text()).get("profile_soul_hashes")
            if observed is None:
                continue
            for profile, want in pins.items():
                with self.subTest(fixture=fixture.name, profile=profile):
                    if fixture.name == "chapt-profile-soul-drift.yaml" and profile == "chapt-reviewer":
                        self.assertEqual(observed[profile], "0" * 64)  # intentional red
                    else:
                        self.assertEqual(observed[profile], want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
