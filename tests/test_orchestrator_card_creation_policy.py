#!/usr/bin/env python3
"""Card creation and notification subscription wording in the five orchestrator skills (t_b6d0e590;
anki-orchestrator added by t_0a8674fe).

Offline checks of tracked bytes only: no live ~/.hermes reads, board access,
network or model calls. Each project orchestrator must create cards with the
kanban_create tool (which subscribes the calling session with delivery_mode
notify+wake), may name the CLI create command only in the sentence that forbids
it, and repairs a missing subscription with a notify-subscribe command that
names its own board and its own profile.
"""
import re
from pathlib import Path
import unittest

from rule_text import assert_rule

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
# profile -> board
SKILLS = {
    "harness-orchestrator": "harness",
    "jobcron-orchestrator": "jobcron",
    "chapt-orchestrator": "cha-pt",
    "jss-orchestrator": "jss-genr",
    "anki-orchestrator": "anki",
}
# The text that ends the kanban_create call sentence of step 1. The anki fleet has a second
# repository, reached through the Hermes project anki-addons, so its sentence names that project.
STEP_ONE_CALL_END = {"anki-orchestrator": ", adding `project: anki-addons` for an add-on repository card."}


def skill_text(profile):
    return (ROOT / "policies/profile-skills" / profile / RELATIVE).read_text()


def card_setup(text):
    match = re.search(r"^## Card Setup\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "Card Setup"
    return match.group(1)


def step(setup, number):
    lines = [line for line in setup.splitlines() if line.startswith(f"{number}. ")]
    assert len(lines) == 1, (number, lines)
    return lines[0]


def forbidding_sentence(board):
    return f"Create cards only with the kanban_create tool, never with `hermes kanban --board {board} create`."


def explanation(board):
    return (
        forbidding_sentence(board),
        "The tool auto-subscribes this session to the card with delivery_mode notify+wake, the owner's user ID, "
        "and this profile as notifier_profile, so completion, review-request, and block events wake this "
        "orchestrator and ping the owner.",
        "The CLI create command does not subscribe, and a manual notify-subscribe without flags defaults to "
        "notify with no user ID, which wakes nobody.",
        "This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators.",
    )


def step_four(board, profile):
    return (
        "4. Confirm the kanban_create result reports subscribed: true. Only if it does not, repair the "
        f"subscription with: hermes kanban --board {board} notify-subscribe <id> --platform telegram "
        "--chat-id <owner chat> --user-id <owner user> --chat-type dm "
        f"--notifier-profile {profile} --delivery-mode notify+wake. Re-running notify-subscribe updates an "
        "existing row, so this command also upgrades a wrongly subscribed card."
    )


class OrchestratorCardCreationPolicy(unittest.TestCase):
    def test_cli_create_occurs_only_in_the_sentence_that_forbids_it(self):
        for profile, board in SKILLS.items():
            text = skill_text(profile)
            with self.subTest(profile=profile):
                command = f"hermes kanban --board {board} create"
                occurrences = [match.start() for match in re.finditer(re.escape(command), text)]
                self.assertEqual(len(occurrences), 1, occurrences)
                sentence = forbidding_sentence(board)
                self.assertEqual(text.count(sentence), 1)
                start = text.index(sentence)
                self.assertTrue(start <= occurrences[0] < start + len(sentence))
                # No other spelling of the CLI create command remains anywhere in the skill.
                self.assertIsNone(re.search(r"hermes kanban (--board \S+ )?create\b",
                                            text.replace(sentence, "")))

    def test_step_one_uses_kanban_create_and_carries_the_explanation(self):
        for profile, board in SKILLS.items():
            first = step(card_setup(skill_text(profile)), 1)
            with self.subTest(profile=profile):
                self.assertTrue(first.startswith(
                    f"1. Create it with the kanban_create tool: `kanban_create(..., board: {board}, "
                    "initial_status: blocked)`" + STEP_ONE_CALL_END.get(profile, ".")), first)
                self.assertNotIn("before any notification subscription exists", first)
                assert_rule(self, first, "created blocked", "cannot be dispatched before setup is complete",
                            "notification subscription exists from creation")
                for sentence in explanation(board):
                    self.assertEqual(first.count(sentence), 1, sentence)

    def test_step_four_is_the_confirm_or_repair_text(self):
        for profile, board in SKILLS.items():
            setup = card_setup(skill_text(profile))
            with self.subTest(profile=profile):
                self.assertEqual(step(setup, 4), step_four(board, profile))
                self.assertNotIn("Subscribe the callback", setup)
                order = [setup.find(f"{number}. ") for number in range(1, 6)]
                self.assertNotIn(-1, order, order)
                self.assertEqual(order, sorted(order))

    def test_step_four_command_names_its_own_board_and_profile(self):
        for profile, board in SKILLS.items():
            fourth = step(card_setup(skill_text(profile)), 4)
            with self.subTest(profile=profile):
                command = re.search(r"hermes kanban --board (\S+) notify-subscribe <id> (.*?) "
                                    r"--delivery-mode notify\+wake\.", fourth)
                self.assertIsNotNone(command, fourth)
                self.assertEqual(command.group(1), board)
                flags = command.group(2).split()
                self.assertEqual(flags[flags.index("--notifier-profile") + 1], profile)
                self.assertEqual(flags[flags.index("--user-id") + 1:flags.index("--user-id") + 3],
                                 ["<owner", "user>"])
                for other_profile, other_board in SKILLS.items():
                    if other_profile != profile:
                        self.assertNotIn(other_profile, fourth)
                        self.assertNotIn(f"--board {other_board} ", fourth)


if __name__ == "__main__":
    unittest.main()
