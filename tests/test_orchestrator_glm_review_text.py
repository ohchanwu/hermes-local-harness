#!/usr/bin/env python3
"""The five project orchestrator skill sources handle a GLM review run and a block with the
reason `jev-glm-review-pass` (card t_35874d04).

Offline checks of tracked repository files only: no live profile, board, network or model
observation, and no write under /Users/chanbla11mit/.hermes. Each source of
`<prefix>-orchestrator` has the raised version line and, in its review section ("## Review and
Integration" in the harness, jss and anki sources; "## Review Contract" in the chapt and jobcron
sources), one paragraph that names `<prefix>-reviewer-glm`, `<prefix>-reviewer` and
`jev-glm-review-pass`, contains the two hand commands `hermes kanban --board <board> assign
<task id> <prefix>-reviewer` and `hermes kanban --board <board> unblock <task id>` for its own
board, and states that the GLM reviewer cannot approve a card. Reversing the card's edits gives
the bytes of each source at the card's baseline, so the card changed nothing else in the text.
Card t_18a2dc93 later changed the names of the GLM workers in these sources and raised each
version by one more step; the checks read each source with the edits of that card reversed,
and the version check also reads the current version line.
"""
import hashlib
import re
import unittest
from pathlib import Path

from glm_route_worker_names_edits import VERSIONS as ROUTE_NAMES_VERSIONS, text_before_card
from orchestrator_glm_review_edits import (
    BASELINE_SHA256, ORCHESTRATOR_GLM_REVIEW_EDITS, PASS_REASON, PREFIXES, VERSIONS, added_paragraph, approval_sentence,
    reverse_orchestrator_glm_review_edits, skill)
from test_jev_easy_medium_worker_split import VERSIONS as SPLIT_VERSIONS

ROOT = Path(__file__).resolve().parents[1]

# Profile prefix -> (new version line, review section heading, board).
EXPECTED = {
    "harness": ("0.6.7-harness.13", "Review and Integration", "harness"),
    "jss": ("0.6.7-jss.17", "Review and Integration", "jss-genr"),
    "anki": ("0.6.10-anki.11", "Review and Integration", "anki"),
    "chapt": ("0.6.7-chapt.15", "Review Contract", "cha-pt"),
    "jobcron": ("0.6.9-jobcron.16", "Review Contract", "jobcron"),
}
# The two hand commands of item 1.d, written out for each board.
HAND_COMMANDS = {
    "harness": ("hermes kanban --board harness assign <task id> harness-reviewer",
                "hermes kanban --board harness unblock <task id>"),
    "jss": ("hermes kanban --board jss-genr assign <task id> jss-reviewer",
            "hermes kanban --board jss-genr unblock <task id>"),
    "anki": ("hermes kanban --board anki assign <task id> anki-reviewer",
             "hermes kanban --board anki unblock <task id>"),
    "chapt": ("hermes kanban --board cha-pt assign <task id> chapt-reviewer",
              "hermes kanban --board cha-pt unblock <task id>"),
    "jobcron": ("hermes kanban --board jobcron assign <task id> jobcron-reviewer",
                "hermes kanban --board jobcron unblock <task id>"),
}
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"


def source_bytes(prefix):
    """The bytes of the source with the later edits of card t_18a2dc93 reversed."""
    return text_before_card(ROOT, skill(prefix), as_bytes=True)


def section(text, heading):
    """The text of the level 2 section with this heading, up to the next level 2 heading."""
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


class OrchestratorGlmReviewText(unittest.TestCase):
    def text(self, prefix):
        return source_bytes(prefix).decode("utf-8")

    def test_the_prefixes_are_the_five_project_orchestrators(self):
        self.assertEqual(set(PREFIXES), set(EXPECTED))
        self.assertEqual({prefix: new for prefix, (_old, new) in VERSIONS.items()},
                         {prefix: version for prefix, (version, _heading, _board) in EXPECTED.items()})

    def test_version_line_is_raised(self):
        for prefix in PREFIXES:
            # Card t_cf518fd0 raised each version by one more step.
            self.assertEqual(SPLIT_VERSIONS[prefix][0], EXPECTED[prefix][0])
            version = SPLIT_VERSIONS[prefix][1]
            with self.subTest(prefix=prefix):
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.text(prefix)), [version])
                # Card t_18a2dc93 raised each version by one more step.
                self.assertEqual(ROUTE_NAMES_VERSIONS[prefix][0], version)
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", (ROOT / skill(prefix)).read_text()),
                                 [ROUTE_NAMES_VERSIONS[prefix][1]])

    def test_names_both_reviewers_and_the_pass_reason(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn(f"`{prefix}-reviewer-glm`", text)
                self.assertIn(f"`{prefix}-reviewer`", text)
                self.assertIn(f"`{PASS_REASON}`", text)
                self.assertEqual(text.count(PASS_REASON), 1)
                self.assertIn(f"A `blocked` notification whose reason starts with `{PASS_REASON}` means that the GLM "
                              "review had no findings.", text)

    def test_contains_both_hand_commands_for_its_board(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            assign, unblock = HAND_COMMANDS[prefix]
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count(f"`{assign}`"), 1)
                self.assertEqual(text.count(f"`{unblock}`"), 1)
                self.assertIn(f"`{assign}` and then `{unblock}`", text)

    def test_states_that_the_glm_reviewer_cannot_approve(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn("The GLM reviewer cannot approve a card", text)
                self.assertIn(approval_sentence(prefix), text)
                self.assertIn(f"only `kanban_complete` by `{prefix}-reviewer` is the approval", text)

    def test_states_the_mismatch_rule_and_the_routine_rework(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn("Such a run is not an assignee or reviewer mismatch.", text)
                self.assertIn(f"The card's `Reviewer EXACT` line still names the Opus reviewer `{prefix}-reviewer`, "
                              "and that is correct.", text)
                self.assertIn(f"A change request from `{prefix}-reviewer-glm` is routine same-card rework", text)
                self.assertIn("It needs no action and is not an owner question", text)

    def test_paragraph_is_in_the_review_section(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            heading = EXPECTED[prefix][1]
            paragraph = added_paragraph(prefix)
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count(paragraph), 1)
                # In the chapt and jobcron sources the paragraph is the last one of its section.
                self.assertIn(f"\n\n{paragraph}\n", section(text, heading))

    def test_reversal_gives_the_baseline_bytes(self):
        for prefix in PREFIXES:
            relative = skill(prefix)
            data = source_bytes(prefix)
            with self.subTest(prefix=prefix):
                original = reverse_orchestrator_glm_review_edits(relative, data)
                self.assertNotEqual(original, data)
                self.assertEqual(hashlib.sha256(original).hexdigest(), BASELINE_SHA256[relative])
                self.assertEqual(reverse_orchestrator_glm_review_edits(relative, data.decode()), original.decode())
                self.assertIs(reverse_orchestrator_glm_review_edits(relative, original), original)
                self.assertNotIn(PASS_REASON.encode(), original)
                # A text that holds a new text twice fails.
                for new, _old in ORCHESTRATOR_GLM_REVIEW_EDITS[relative]:
                    with self.assertRaises(AssertionError):
                        reverse_orchestrator_glm_review_edits(relative, data.decode() + new)

    def test_reversal_returns_other_paths_unchanged(self):
        data = (ROOT / SHARED).read_bytes()
        self.assertIs(reverse_orchestrator_glm_review_edits(SHARED, data), data)

    def test_shared_fleet_skill_is_not_changed(self):
        self.assertNotIn(PASS_REASON, (ROOT / SHARED).read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
