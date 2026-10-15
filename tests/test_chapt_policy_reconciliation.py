#!/usr/bin/env python3
"""Offline tracked-byte preservation checks, not agent behavior or live rollout.

Frozen hashes bind the approved paragraph and e3aa92a source without private
controller inputs, installed profiles, Git history, network or model calls.
"""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SOURCE = ROOT / "policies/profile-skills/chapt-orchestrator" / RELATIVE
BASELINE_SHA256 = "3fa1151192959b77e23921a813994517cb3cad8c655c901e425f0f958fb7674c"
RULE_SHA256 = "0b3349307eaaf7bc4de6716198dfdd5e72d3f99862ee335a0fdc4124ad5e1d5e"
UPGRADE_SHA256 = "0e9c5f1f07e50dd3653fc51ffba481427bb237d5805d3213aa209169ac64cd94"
MERGED_SHA256 = "575419e386187a028b7c449bf6da7f298e88dfa3d4250619c06caa8d5a52e330"
HEADING = b"## Operator Effort and Evidence Lifecycle\n\n"
RULE_START = b"Distinguish worker-stop conditions from controller-disposition points and actual human authorization boundaries."


def digest(content):
    return hashlib.sha256(content).hexdigest()


class ChaptPolicyReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_bytes()
        self.skill = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_bytes())["skill"]

    def retained_rule(self):
        self.assertEqual(self.source.count(RULE_START), 1)
        self.assertEqual(self.source.count(HEADING), 1)
        following = self.source.split(HEADING, 1)[1]
        self.assertTrue(following.startswith(RULE_START))
        # Preserve the installed paragraph's terminating LF and separating blank
        # line. Its frozen hash detects any wording/whitespace substitution.
        paragraph, rest = following.split(b"\n\n", 1)
        self.assertTrue(rest.startswith(b"Do not add unrelated collaborator-role or whole-governance audits"))
        rule = paragraph + b"\n"
        self.assertEqual(digest(rule), RULE_SHA256)
        self.assertEqual(self.source.count(rule), 1)
        return rule

    def test_exact_rule_once_at_existing_semantic_location(self):
        self.retained_rule()

    def test_entire_reviewed_source_is_preserved(self):
        rule = self.retained_rule()
        self.assertEqual(self.source.count(b"version: 0.6.5-chapt.4\n"), 1)
        original = self.source.replace(rule + b"\n", b"", 1).replace(
            b"version: 0.6.5-chapt.4\n", b"version: 0.6.5-chapt.3\n", 1)
        # Frozen full-source identity, not a keyword-only preservation claim.
        self.assertEqual(digest(original), BASELINE_SHA256)
        self.assertEqual(digest(self.source), MERGED_SHA256)

    def test_upgrade_selection_is_byte_unchanged(self):
        section = self.source.split(b"## Routine upgrade selection", 1)[1].split(b"\n## ", 1)[0]
        self.assertEqual(digest(section), UPGRADE_SHA256)
        self.assertIn(b"independent review of the exact saved plan before apply", section)
        self.assertIn(b"separately from owner authorization", section)
        self.assertIn(b"not an extra gate for unchanged-platform app-only updates", section)

    def test_owner_caps_stop_and_authority_are_retained(self):
        rule = self.retained_rule()
        for clause in (
            b"preserve explicit owner caps and activated hard campaign budgets",
            b"Preserve counters, failed evidence and acceptance pins",
            b"never unlimited retries or a history reset",
            b"prohibited effect, unsafe/unowned state, capability limit or exhausted authorized recovery path",
            b"An explicit user stop always controls until a later resumption.",
        ):
            self.assertIn(clause, rule)
        for clause in (
            b"max_approaches: 3", b"max_attempts_per_approach: 3",
            b"max_infrastructure_retries_per_attempt: 1",
            b"Exhausting three approaches always human-blocks",
            b"credentials/MFA", b"policy/legal/security decisions still human-block immediately",
            b"It never covers pushes, PR creation, deployments, production mutations",
            b"When the user says stop, terminate every owned background worker",
            b"Never push, open a PR, deploy, mutate production, or bypass review.",
        ):
            self.assertIn(clause, self.source)

    def test_single_desired_override_pin_and_additive_provenance(self):
        overrides = self.skill["profile_local_skill_overrides"]["chapt-orchestrator"]
        self.assertEqual(overrides, {RELATIVE: MERGED_SHA256})
        self.assertEqual(overrides[RELATIVE], digest(self.source))
        provenance = self.skill["source_pin_provenance"]
        self.assertEqual(provenance["baseline"], "84d91a7ba698d38bb31c5b80e04dea0dd002d15f")
        self.assertEqual(provenance["upgrade_proportionality"]["baseline"], "fdc59293262e15c0376cfaa9f25244e7c317fc58")
        self.assertEqual(provenance["chapt_policy_reconciliation"], {
            "baseline": "e3aa92a20227c780fde4c09d3b3a1402a7115db9",
            "protected_reference": "refs/harness/baselines/t_acb614c0",
            "installed_input_sha256": "e1e5d81f39353eabc49850354d4d76964587cd8b884de2276751b89018edb4f1",
            "retained_rule_sha256": RULE_SHA256,
            "status": "repository-only preservation merge and desired-source pin, not observed deployment; live rollout unperformed and live verification pending",
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
