#!/usr/bin/env python3
"""Offline source contract for three texts of the harness-orchestrator skill (card t_40028345).

Checks tracked repository text only; it does not observe live profiles, boards or agent behavior.
Part 1 (Operational Discipline): recovery of a review card that the respawn guard holds with the
reason `blocker_auth`. Part 2 (Card Setup): no planned hand-back block of a card. Part 3 (Role
Separation): the steps on other boards that the owner authorized.
"""
from pathlib import Path
import re
import subprocess
import unittest

from harness_orchestrator_recovery_edits import HARNESS_RECOVERY_EDITS, SKILL as SKILL_RELATIVE, reverse_harness_recovery_edits
from rule_text import assert_rule, raw_section

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "policies/profile-skills/harness-orchestrator"
         / "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md")
CRON_PROMPT = ROOT / "deployment/orchestrator-board-check/cron-prompt.md"
KANBAN_DB = "/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/kanban_db.py"
OWNER_QUOTATION = ("You (harness-orchestrator) run the card reads, moves and comments on the five boards "
                   "from your session. The worker does the renames, policy texts, .env lines and copies. "
                   "No Hermes limit is removed.")


def flat(text):
    return " ".join(text.split())


class HarnessOrchestratorRecoveryRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SKILL.read_text()

    def test_version(self):
        self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.raw), ["0.6.7-harness.17"])

    def test_part1_respawn_guarded_recovery_in_operational_discipline(self):
        section = raw_section(self.raw, "Operational Discipline")
        items = [line for line in section.splitlines() if line.startswith("- ") and "`blocker_auth`" in line]
        self.assertEqual(len(items), 1, items)
        item = flat(items[0])
        for marker in (
            "`respawn_guarded`",
            "`kanban_request_review` does not clear",
            "RESPAWN-GUARDED",
            "which `harness-orchestrator` does not run",
            "the status is `review`",
            "`review_requested`",
            "hermes kanban --board harness assign <card id> none",
            "hermes kanban --board harness assign <card id> <the previous assignee>",
            "`kanban_show(..., board: harness)`",
            "`last_failure_error`",
            "`assign_task`",
            KANBAN_DB,
            "In every other case report the card to the owner and change nothing.",
        ):
            self.assertIn(marker, item)
        # The text of the repository sections is outside Operational Discipline.
        for heading in ("Card Setup", "Role Separation"):
            self.assertNotIn("assign <card id> none", raw_section(self.raw, heading))

    def test_part1_uses_the_conditions_of_the_cron_prompt(self):
        line = CRON_PROMPT.read_text().splitlines()[12]
        self.assertTrue(line.startswith("5. RESPAWN-GUARDED:"), line)
        for phrase in ("`respawn_guarded`", "`blocker_auth`", "the status is `review`", "`review_requested`",
                       "assign <card id> none"):
            self.assertIn(phrase, line)

    def test_part2_no_planned_hand_back_block_in_card_setup(self):
        section = raw_section(self.raw, "Card Setup")
        paragraphs = [flat(p) for p in section.split("\n\n") if p.startswith("Do not plan a stop")]
        self.assertEqual(len(paragraphs), 1, paragraphs)
        paragraph = paragraphs[0]
        for marker in (
            "blocks the card to hand it back to harness-orchestrator",
            "`needs_input`",
            "`triage`",
            "`BLOCK_RECURRENCE_LIMIT` is 2",
            "`_route_block`",
            KANBAN_DB,
            "line 114",
            "lines 3397 to 3407",
            "split the work into two cards and link them",
        ):
            self.assertIn(marker, paragraph)
        # The paragraph follows the paragraph that forbids a block as a setup hold.
        hold = "Never claim a card and `kanban_block` it as a setup hold."
        self.assertEqual(len(re.findall(r"(?m)^Never claim a card and `kanban_block` it as a setup hold\.", section)), 1)
        self.assertLess(section.index(hold), section.index("Do not plan a stop"))
        between = section[section.index(hold):section.index("Do not plan a stop")]
        self.assertEqual(between.count("\n\n"), 1)

    def test_part3_owner_quotation_in_role_separation(self):
        section = raw_section(self.raw, "Role Separation")
        paragraphs = [flat(p) for p in section.split("\n\n") if p.startswith("A worker that the dispatcher starts")]
        self.assertEqual(len(paragraphs), 1, paragraphs)
        paragraph = paragraphs[0]
        self.assertIn(f"\"{OWNER_QUOTATION}\"", paragraph)
        self.assertIn("can read and change cards of its own board only", paragraph)
        self.assertIn("records each in a comment on the card", paragraph)
        self.assertIn("the worker does every other step", paragraph)
        self.assertIn("2026-11-16", paragraph)
        self.assertIn("This gives no access to another board beyond the steps that the owner authorized "
                      "for that card.", paragraph)
        assert_rule(self, section, "A worker that the dispatcher starts", "its own board only")

    def test_the_quotation_is_in_the_role_separation_section_only(self):
        self.assertEqual(self.raw.count(OWNER_QUOTATION), 1)

    def test_reversal_gives_the_baseline_bytes(self):
        baseline = "f619325bc0e141ce7dbd117c25232670eee4bd16"
        before = subprocess.run(["git", "show", f"{baseline}:{SKILL_RELATIVE}"], cwd=ROOT,
                                capture_output=True, check=True).stdout
        data = SKILL.read_bytes()
        original = reverse_harness_recovery_edits(SKILL_RELATIVE, data)
        self.assertEqual(original, before)
        self.assertEqual(reverse_harness_recovery_edits(SKILL_RELATIVE, data.decode()), before.decode())
        self.assertIs(reverse_harness_recovery_edits(SKILL_RELATIVE, original), original)
        for new, _old in HARNESS_RECOVERY_EDITS:
            with self.assertRaises(AssertionError):
                reverse_harness_recovery_edits(SKILL_RELATIVE, data.decode() + new)
        other = b"unchanged"
        self.assertIs(reverse_harness_recovery_edits("README.md", other), other)


if __name__ == "__main__":
    unittest.main()
