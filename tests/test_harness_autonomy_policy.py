#!/usr/bin/env python3
"""Offline source contract for the Harness orchestrator autonomy rules.

Checks tracked repository text and pins only; it does not observe live
profiles, the board, or agent behavior.
"""
import hashlib
import json
from pathlib import Path
import re
import unittest

from rule_text import assert_rule, raw_section

from incident_recovery_verify_fixture import resolved_fixture

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SKILL = ROOT / "policies/profile-skills/harness-orchestrator" / RELATIVE
LEGACY = (
    "policies/concurrency.md",
    "policies/escalation-ladder.md",
    "procedures/hermes-terminal-outcome-notifications.md",
)
BASELINE_SKILL_LINES = 161


def flat(text):
    return " ".join(text.split())


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, heading
    return flat(match.group(1))


class HarnessAutonomyPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SKILL.read_text()
        cls.text = flat(cls.raw)

    def test_version_and_bounded_growth(self):
        self.assertRegex(self.raw, r"(?m)^version: 0\.6\.7-harness\.6$")
        # Plus the 9 lines of repair_history candidate rules and example (t_6436ac1c).
        self.assertLessEqual(len(self.raw.splitlines()), BASELINE_SKILL_LINES + 70 + 9)

    def test_rule1_card_setup_without_setup_hold(self):
        setup = section(self.raw, "Card Setup")
        order = [
            "`kanban_create(..., board: harness, initial_status: blocked)`",
            "write the exact ID, worktree path, and branch into the body",
            "Pin `refs/harness/baselines/<ID>`",
            "Confirm the kanban_create result reports subscribed: true.",
            "Unblock the card so it becomes `ready`",
        ]
        positions = [setup.find(marker) for marker in order]
        self.assertNotIn(-1, positions, positions)
        self.assertEqual(positions, sorted(positions))
        for marker in (
            "Never claim a card and `kanban_block` it as a setup hold.",
            "verifies `$HERMES_KANBAN_TASK`, worktree path, branch, and baseline",
            "blocks only on a real mismatch",
            "records `workspace_path` as the repository root",
            "claim materializes `.worktrees/<ID>`",
            "`t_7d9c0343`",
            "A root value before claim is expected, not a mismatch",
        ):
            self.assertIn(marker, setup)

    def test_rule2_bookkeeping_never_gates_semantic_gates_remain(self):
        autonomy = section(self.raw, "Autonomy")
        for marker in (
            "Bookkeeping never gates.",
            "`repair_history`, ledger, receipt, or handoff formatting",
            "appending a valid successor that preserves the original",
            "never a completion or integration prerequisite and never an owner question",
            "Semantic gates are unchanged and still block: required tests, exact-candidate independent review, candidate drift, real budgets, and authority/external-write limits.",
        ):
            self.assertIn(marker, autonomy)
        gate = section(self.raw, "Completion Gate")
        self.assertIn("semantic validity, not bookkeeping-format validity", gate)
        self.assertIn("Required focused and broader tests pass.", gate)
        self.assertIn("reviewed by `harness-reviewer` on the same card", gate)

    def test_rule3_ask_and_dont_ask_lists(self):
        autonomy = section(self.raw, "Autonomy")
        never, only = autonomy.split("Ask only for:", 1)
        never = never.split("Never ask the owner about:", 1)[1]
        only = only.split("Stale callbacks:", 1)[0]
        for item in (
            "bookkeeping corrections", "historical test-order disclosures", "retry or budget accounting",
            "infrastructure retries", "read-only local diagnosis", "routine same-card rework",
            "local integration after approval",
        ):
            self.assertIn(f"- {item}", never)
        for item in (
            "external writes (push, PR, deploy)", "credentials or MFA",
            "live profile, skill, policy, board, or gateway changes", "product decisions",
            "money or billing", "genuine capability limits", "a user stop or resume",
        ):
            self.assertIn(f"- {item}", only)

    def test_rule4_stale_callbacks(self):
        autonomy = section(self.raw, "Autonomy")
        for marker in (
            "Stale callbacks: run one `kanban_show(..., board: harness)`.",
            "already moved past the notified status, reply in at most one line",
            "do nothing else",
            "`notify-subscribe` has no per-event filter (verified from CLI help on 2026-10-17)",
            "would need a Hermes patch, which the upgrade-safety rule forbids",
        ):
            self.assertIn(marker, autonomy)
        self.assertIn("Never modify the installed Hermes source.", self.text)

    def test_rule5_proportional_handoff_checks(self):
        autonomy = section(self.raw, "Autonomy")
        for marker in (
            "Trust successful tool results, and do not read back your own comments.",
            "Do not re-hash what the reviewer already verified; one exact-candidate/diff check at integration is enough.",
            "controller comments to about 5 lines or fewer",
            "Batch independent checks in one response; serialize only when a call depends on an earlier result.",
        ):
            self.assertIn(marker, autonomy)

    def test_rule6_no_caps_on_harmless_actions(self):
        autonomy = section(self.raw, "Autonomy")
        rules = raw_section(self.raw, "Autonomy")
        assert_rule(self, rules, "No numeric caps", "harmless actions", "local reads", "local tests",
                    "anonymous public reads")
        assert_rule(self, rules, "Keep caps only", "cost", "rate", "mutation", "ambiguity")
        # Real repair budgets survive.
        repair = section(self.raw, "Bounded Autonomous Repair")
        self.assertIn("At most three materially distinct approaches.", repair)
        self.assertIn("At most one infrastructure retry per pending attempt.", repair)

    def test_rule7_legacy_policies_named_and_bannered(self):
        autonomy = section(self.raw, "Autonomy")
        for path in LEGACY:
            self.assertIn(f"`{path}`", autonomy)
        self.assertIn("retired GPT-era fleet (Flash/Luna/Terra/Sol/Astra)", autonomy)
        self.assertIn("do not govern Harness board routing", autonomy)
        for path in LEGACY:
            first = (ROOT / path).read_text().splitlines()[0]
            with self.subTest(path=path):
                self.assertTrue(first.startswith("> Legacy:"), first)
                for marker in ("retired GPT-era fleet", "retired 2026-10-18", "Retained for history",
                               "does not govern current Harness routing"):
                    self.assertIn(marker, first)

    def test_existing_rules_retained(self):
        for marker in (
            "Pass `board: harness` on every Kanban tool call.",
            "Never autonomously modify or deploy this profile's active live policy.",
            "live rollout is a separate attended operation",
            "The sole independent reviewer is `harness-reviewer`.",
            "It never edits implementation code.",
            "`Reviewer EXACT harness-reviewer.`",
            "`Baseline EXACT <40-hex-commit>.`",
            "Exhaustion requires a human block",
            "An incident neither grants new authority nor automatically revokes unrelated authority.",
            "User stop remains global",
            "The reviewed commit exactly matches the reviewed diff.",
            "Local integration does not authorize a push, PR, deployment, live profile/skill update",
            "No unauthorized push, PR, deployment, policy rollout",
        ):
            self.assertIn(marker, self.text)
        headings = re.findall(r"^## (.+)$", self.raw, re.M)
        self.assertEqual(headings, [
            "Hard Scope", "Role Separation", "Card Contract", "Card Setup", "Worker Selection",
            "Worktree and Baseline Gate", "Skills", "Bounded Autonomous Repair", "Autonomy",
            "Incident recovery", "Review and Integration", "Operational Discipline", "Completion Gate",
            "Pitfalls",
        ])

    def test_snapshot_and_fixture_pins_match_tracked_bytes(self):
        actual = hashlib.sha256(SKILL.read_bytes()).hexdigest()
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())
        overrides = snapshot["skill"]["profile_local_skill_overrides"]
        # Expected bytes are derived from the tracked source (no hand pin).
        self.assertEqual(overrides["harness-orchestrator"][RELATIVE], "tracked-source")
        unpinned = set()
        for path in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = resolved_fixture(path)  # "tracked-source" resolved as verify-state does
            pinned = (data.get("profile_local_skill_overrides") or {}).get("harness-orchestrator")
            if pinned is None:
                unpinned.add(path.name)
                continue
            with self.subTest(fixture=path.name):
                self.assertEqual(pinned[RELATIVE], actual)
        # Only the deliberately empty fixture omits the pin.
        self.assertEqual(unpinned, {"incomplete-empty.yaml"})


if __name__ == "__main__":
    unittest.main()
