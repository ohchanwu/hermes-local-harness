#!/usr/bin/env python3
"""Offline source contract for the Jobcron and Cha PT autonomy-rule ports.

Mirrors tests/test_harness_autonomy_policy.py for the two project fleets:
checks tracked repository text and pins only; it does not observe live
profiles, boards, or agent behavior.
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
SKILLS = {
    board: ROOT / f"policies/profile-skills/{profile}-orchestrator" / RELATIVE
    for board, profile in (("jobcron", "jobcron"), ("cha-pt", "chapt"))
}
VERSIONS = {"jobcron": "0.6.9-jobcron.6", "cha-pt": "0.6.7-chapt.6"}
BASELINE_SKILL_LINES = {"jobcron": 429, "cha-pt": 434}
# Live-only Jobcron rules reconciled verbatim from the installed
# jobcron-orchestrator skill (0.6.5-jobcron.1) into the repository copy.
LIVE_ONLY_MARKERS = (
    "Do not manufacture an architecture pivot to unlock budget for a localized defect in an exhausted approach",
    "Before creating a card, first check that intended reviewer skills actually exist",
    "an unnecessary worker-only forced skill can otherwise become an uneditable inherited review blocker",
    "For a completed candidate escalated to `triage` by block-loop detection",
    "Use the documented native dashboard PATCH status interface to recover an inactive card to `ready`",
    "### Documentation-only closeout",
    "Protected-file approval prompts remain separate security gates",
    "never treat a timeout as consent or bypass a refusal",
)
BOARD_CONTROL_MARKERS = {
    "jobcron": (
        "The Jobcron owner removed owner/controller-imposed time limits",
        "env -u JOBCRON_TEST_POSTGRES_URL",
        "Apply Incident recovery at fixture-boundary failures",
        "Keep provider/scraper denial explicit",
        "When the user says stop, terminate every owned background worker, reviewer, preview server, and watcher",
    ),
    "cha-pt": (
        "Operator-protected paths require explicit human authorization naming the protected scope on that card",
        "Frontend cards must follow `/Users/chanbla11mit/projects/cha-pt-frontend/AGENTS.md`",
        "checks/run.py --all` performs static validation",
        "Represent a tracked symlink by its link text",
        "explicitly authorized operator exception must be reported as an exception, not green CI",
        "When the user says stop, terminate every owned background worker, reviewer, preview server, and watcher",
    ),
}
REVIEWERS = {"jobcron": "jobcron-reviewer", "cha-pt": "chapt-reviewer"}


def flat(text):
    return " ".join(text.split())


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, heading
    return flat(match.group(1))


class FleetAutonomyPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {board: SKILLS[board].read_text() for board in SKILLS}
        cls.text = {board: flat(cls.raw[board]) for board in SKILLS}

    def test_versions_and_bounded_growth(self):
        for board, skill in SKILLS.items():
            with self.subTest(board=board):
                self.assertRegex(self.raw[board], rf"(?m)^version: {re.escape(VERSIONS[board])}$")
                # The 0.6.7-rule port itself stays within the same growth budget
                # the harness port allowed; jobcron additionally carries the
                # verbatim live-only reconciliation, so bound the whole file
                # more loosely but the ported sections tightly.
                port_lines = 0
                for heading in ("Card Setup", "Autonomy", "Completion Gate"):
                    match = re.search(rf"^## {heading}\n(.*?)(?=^## |\Z)", self.raw[board], re.M | re.S)
                    assert match is not None, heading
                    port_lines += match.group(1).count("\n")
                self.assertLessEqual(port_lines, 65)
                self.assertLessEqual(len(self.raw[board].splitlines()),
                                     BASELINE_SKILL_LINES[board] + 90)

    def test_rule1_card_setup_without_setup_hold(self):
        for board in SKILLS:
            with self.subTest(board=board):
                setup = section(self.raw[board], "Card Setup")
                order = [
                    f"`kanban_create(..., board: {board}, initial_status: blocked)`",
                    "write the exact ID, worktree path, and branch into the body",
                    "Pin the approved baseline commit for that exact card before dispatch",
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
                    "A root value before claim is expected, not a mismatch",
                ):
                    self.assertIn(marker, setup)
                # No contradictory second setup-hold rule anywhere.
                self.assertEqual(self.raw[board].count("setup hold"), 1)

    def test_rule2_bookkeeping_never_gates_semantic_gates_remain(self):
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                for marker in (
                    "Bookkeeping never gates.",
                    "`repair_history`, ledger, receipt, or handoff formatting",
                    "appending a valid successor that preserves the original",
                    "never a completion or integration prerequisite and never an owner question",
                    "Semantic gates are unchanged and still block: required tests, exact-candidate independent review, candidate drift, real budgets, and authority/external-write limits.",
                ):
                    self.assertIn(marker, autonomy)
                gate = section(self.raw[board], "Completion Gate")
                self.assertIn("semantic validity, not bookkeeping-format validity", gate)
                self.assertIn("Required focused and broader tests pass.", gate)
                self.assertIn(f"reviewed by `{REVIEWERS[board]}` on the same card", gate)

    def test_rule3_ask_and_dont_ask_lists(self):
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                never_all, ask = autonomy.split("Ask only for:", 1)
                never = never_all.split("Never ask the owner about:", 1)[1]
                only = ask.split("These lists never override", 1)[0]
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
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                for marker in (
                    f"Stale callbacks: run one `kanban_show(..., board: {board})`.",
                    "already moved past the notified status, reply in at most one line",
                    "do nothing else",
                    "`notify-subscribe` has no per-event filter (verified from CLI help on 2026-10-17)",
                    "would need a Hermes patch, which the upgrade-safety rule forbids",
                ):
                    self.assertIn(marker, autonomy)
                self.assertIn("Never modify the installed Hermes source.", self.text[board])

    def test_rule5_proportional_handoff_checks(self):
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                for marker in (
                    "Trust successful tool results, and do not read back your own comments.",
                    "Do not re-hash what the reviewer already verified; one exact-candidate/diff check at integration is enough.",
                    "controller comments to about 5 lines or fewer",
                    "Batch independent checks in one response; serialize only when a call depends on an earlier result.",
                ):
                    self.assertIn(marker, autonomy)

    def test_rule6_no_caps_on_harmless_actions(self):
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                rules = raw_section(self.raw[board], "Autonomy")
                assert_rule(self, rules, "No numeric caps", "harmless actions", "local reads", "local tests",
                            "anonymous public reads")
                assert_rule(self, rules, "Keep caps only", "cost", "rate", "mutation", "ambiguity")
                # Real repair budgets survive unchanged.
                self.assertIn("max_approaches: 3", self.text[board])
                self.assertIn("max_attempts_per_approach: 3", self.text[board])
                self.assertIn("max_infrastructure_retries_per_attempt: 1", self.text[board])

    def test_rule7_never_ask_list_preserves_board_specific_gates(self):
        for board in SKILLS:
            with self.subTest(board=board):
                autonomy = section(self.raw[board], "Autonomy")
                self.assertIn("These lists never override a", autonomy)
                assert_rule(self, raw_section(self.raw[board], "Autonomy"), "security gate", "consent",
                            "never treat a timeout", "refusal")
                for marker in BOARD_CONTROL_MARKERS[board]:
                    self.assertIn(marker, self.text[board])
                # GPT-era policy files are not referenced by these skills, so
                # the Harness legacy-policies bullet has no equivalent here.
                for path in ("policies/concurrency.md", "policies/escalation-ladder.md",
                             "procedures/hermes-terminal-outcome-notifications.md"):
                    self.assertNotIn(f"`{path}`", self.raw[board])

    def test_rule8_no_harness_board_routing(self):
        for board in SKILLS:
            with self.subTest(board=board):
                for forbidden in ("board: harness", "--board harness", "board `harness`",
                                  "harness-orchestrator", "harness-reviewer", "harness-worker",
                                  "hermes-local-harness"):
                    self.assertNotIn(forbidden, self.raw[board])

    def test_jobcron_live_only_rules_reconciled_verbatim(self):
        text = self.raw["jobcron"]
        for marker in LIVE_ONLY_MARKERS:
            self.assertIn(marker, text)
        # All repo-only 0.6.8 content is retained.
        for marker in (
            "## Routine upgrade selection",
            "Derive the concise next useful authorized action from current verified state",
            "An incident neither grants new authority nor automatically revokes unrelated authority",
            "Derive names from the actual test surface, not a universal blacklist",
        ):
            self.assertIn(marker, text)

    def test_existing_section_order_retained(self):
        for board in SKILLS:
            with self.subTest(board=board):
                headings = re.findall(r"^## (.+)$", self.raw[board], re.M)
                for required in ("Card Setup", "Autonomy", "Completion Gate"):
                    self.assertIn(required, headings)
                # The three new sections sit at the same anchor points chosen
                # for the harness skill: before Task Construction, Worker
                # Contract, and Verification respectively.
                self.assertLess(headings.index("Card Setup"), headings.index("Task Construction"))
                self.assertLess(headings.index("Autonomy"), headings.index("Worker Contract"))
                self.assertLess(headings.index("Completion Gate"), headings.index("Verification"))

    def test_snapshot_and_fixture_pins_match_tracked_bytes(self):
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())
        overrides = snapshot["skill"]["profile_local_skill_overrides"]
        profile_for = {"jobcron": "jobcron-orchestrator", "cha-pt": "chapt-orchestrator"}
        for board, profile in profile_for.items():
            with self.subTest(board=board):
                # Expected bytes are derived from the tracked source (no hand pin).
                self.assertEqual(overrides[profile][RELATIVE], "tracked-source")
        unpinned = set()
        for path in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = resolved_fixture(path)  # "tracked-source" resolved as verify-state does
            pinned = (data.get("profile_local_skill_overrides") or {})
            if "jobcron-orchestrator" not in pinned:
                unpinned.add(path.name)
                continue
            for board, profile in profile_for.items():
                with self.subTest(fixture=path.name, board=board):
                    actual = hashlib.sha256(SKILLS[board].read_bytes()).hexdigest()
                    self.assertEqual(pinned[profile][RELATIVE], actual)
        # Only the deliberately empty fixture omits the pin.
        self.assertEqual(unpinned, {"incomplete-empty.yaml"})


if __name__ == "__main__":
    unittest.main()
