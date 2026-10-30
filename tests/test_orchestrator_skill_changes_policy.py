#!/usr/bin/env python3
"""The "## Skill Changes" section in the five orchestrator skills (t_0a8674fe).

Offline checks of tracked bytes only: no live ~/.hermes reads, board access,
network or model calls. Each orchestrator skill states that it is pinned into
the system prompt by skills.auto_load, that skills.write_approval stages a
skill_manage call instead of applying it, and that a lesson or correction is
proposed as a card on board harness (harness-bug-report, or Card Setup for
harness-orchestrator) and reaches the live copy only through a reviewed
repository commit and a deployment card.

SKILL_CHANGES_EDITS lists the exact (new, old) text this card changed in each
skill file, so tests that pin older bytes of these files can reverse the change
byte for byte with reverse_skill_changes_edits(). This module imports no other
test module, so any test module can import it.
"""
import hashlib
import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
HARNESS = f"policies/profile-skills/harness-orchestrator/{RELATIVE}"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
JSS = f"policies/profile-skills/jss-orchestrator/{RELATIVE}"
ANKI = f"policies/profile-skills/anki-orchestrator/{RELATIVE}"
SKILL_FILES = (HARNESS, JOBCRON, CHAPT, JSS, ANKI)
PROFILES = {HARNESS: "harness-orchestrator", JOBCRON: "jobcron-orchestrator", CHAPT: "chapt-orchestrator",
            JSS: "jss-orchestrator", ANKI: "anki-orchestrator"}

# Version lines stay unchanged: tests outside this card pin them, and an increment
# is optional on this card.
VERSIONS = {
    HARNESS: "0.6.7-harness.6",
    JOBCRON: "0.6.9-jobcron.7",
    CHAPT: "0.6.7-chapt.7",
    JSS: "0.6.7-jss.8",
    ANKI: "0.6.10-anki.4",
}

# Bytes of each file at baseline a391e38a1d20ac14022a20189363931440cf22c9,
# recovered by reversing SKILL_CHANGES_EDITS.
PRE_SKILL_CHANGES_SHA256 = {
    HARNESS: "568b278cf49f0051f6e64672a2feba7fe9ed9c47c18657234bb697babc13bce6",
    JOBCRON: "1b675e5371e2ebbaa7bf9545c3fe636c27072f9f198a7e9462867fe47b67b80f",
    CHAPT: "f6f74d9681972c2e21126954ad0f22a57d845a1618400eaebfe014f6021235ce",
    JSS: "c77f4bbe1859ef823aee96f56d008fe910f6e76a6ef450a9a78508f221c9eca9",
    ANKI: "09c149762b8845956f469d6191d5d4f2eaae4ba8972a8e006c91667e865912e6",
}

PINNED_BULLET = (
    "- This skill is pinned into the system prompt by `skills.auto_load` and is the reviewed repository copy. "
    "Do not edit any live skill, SOUL.md, or profile config of this profile with skill_manage, write_file, "
    "patch, or the terminal, even when Hermes's built-in prompt suggests updating a skill.\n"
)
STAGED_BULLET = (
    "- `skills.write_approval` is true, so a skill_manage call is staged, not applied. "
    "Do not ask the owner to approve a staged skill edit.\n"
)
REACHES_LIVE = ("The change reaches the live copy only through a reviewed repository commit and a "
                "deployment card.\n")
PROJECT_PROPOSAL_BULLET = (
    "- To propose a lesson or a correction, file one card on board harness under the skill "
    "harness-bug-report. " + REACHES_LIVE
)
HARNESS_PROPOSAL_BULLET = (
    "- To propose a lesson or a correction, create one card on board harness under Card Setup in this skill "
    "(the other orchestrators file such a card under the skill harness-bug-report). " + REACHES_LIVE
)
HEADING = "## Skill Changes\n"


def section(path):
    proposal = HARNESS_PROPOSAL_BULLET if path == HARNESS else PROJECT_PROPOSAL_BULLET
    return HEADING + "\n" + PINNED_BULLET + STAGED_BULLET + proposal + "\n"


# The section is inserted directly before the heading that follows "## Skills".
NEXT_HEADING = {HARNESS: "## Bounded Autonomous Repair\n", JOBCRON: "## Routing Rubric\n",
                CHAPT: "## Routing Rubric\n", JSS: "## Bounded Autonomous Repair\n",
                ANKI: "## Bounded Autonomous Repair\n"}


# File -> ((new text, old text), ...). Each new text occurs exactly once.
SKILL_CHANGES_EDITS = {
    path: (("\n" + section(path) + NEXT_HEADING[path], "\n" + NEXT_HEADING[path]),)
    for path in SKILL_FILES
}


def reverse_skill_changes_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in SKILL_CHANGES_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def section_text(text):
    match = re.search(r"^## Skill Changes\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "## Skill Changes"
    return match.group(0)


class SkillChangesSection(unittest.TestCase):
    def setUp(self):
        self.text = {path: (ROOT / path).read_text() for path in SKILL_FILES}

    def test_each_skill_has_one_section_with_the_required_words(self):
        for path in SKILL_FILES:
            with self.subTest(path=path):
                text = self.text[path]
                self.assertEqual(len(re.findall(r"^## Skill Changes$", text, re.M)), 1)
                body = section_text(text)
                for words in ("skills.auto_load", "harness-bug-report", "skills.write_approval",
                              "skill_manage", "write_file", "patch", "the terminal", "SOUL.md",
                              "Do not ask the owner to approve a staged skill edit.",
                              "reviewed repository commit and a deployment card"):
                    self.assertIn(words, body)
                self.assertEqual(body, section(path))

    def test_section_follows_the_skills_section(self):
        for path in SKILL_FILES:
            with self.subTest(path=path):
                headings = re.findall(r"^## .*$", self.text[path], re.M)
                index = headings.index("## Skill Changes")
                self.assertEqual(headings[index - 1], "## Skills")
                self.assertEqual(headings[index + 1] + "\n", NEXT_HEADING[path])

    def test_project_orchestrators_file_under_harness_bug_report(self):
        for path in (JOBCRON, CHAPT, JSS, ANKI):
            with self.subTest(path=path):
                self.assertIn(PROJECT_PROPOSAL_BULLET, section_text(self.text[path]))
        self.assertIn(HARNESS_PROPOSAL_BULLET, section_text(self.text[HARNESS]))
        self.assertIn("## Card Setup\n", self.text[HARNESS])

    def test_version_lines_are_unchanged(self):
        for path, version in VERSIONS.items():
            with self.subTest(path=path):
                self.assertRegex(self.text[path], rf"(?m)^version: {re.escape(version)}$")

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path in SKILL_FILES:
            with self.subTest(path=path):
                original = reverse_skill_changes_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), PRE_SKILL_CHANGES_SHA256[path])

    def test_new_text_is_ascii_and_uses_no_coined_compound(self):
        for path in SKILL_FILES:
            text = section(path)
            text.encode("ascii")
            self.assertIsNone(re.search(r"[Vv]alue-blind|citation-gated", text))

    def test_skill_name_in_section_is_the_pinned_auto_load_skill(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        pinned = roster["orchestrator_profile_settings"]["settings"]["skills.auto_load"]
        self.assertEqual(pinned, ["multi-agent-coding-orchestrator"])
        for path in SKILL_FILES:
            with self.subTest(path=path):
                self.assertRegex(self.text[path], r"(?m)^name: multi-agent-coding-orchestrator$")
                self.assertIn(PROFILES[path], roster["orchestrator_profile_settings"]["profiles"])


if __name__ == "__main__":
    unittest.main()
