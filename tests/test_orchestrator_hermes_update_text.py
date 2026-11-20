#!/usr/bin/env python3
"""Card t_642b5ce9: the five orchestrator skills state the owner rule on manual Hermes updates and
on the repair of a harness plugin after a Hermes update, in one paragraph at the end of
`## Operational Discipline` (anki, harness, jss) or of `## Operating Principles` (chapt, jobcron,
whose list item "Upgrade safety" is their rule on Hermes upgrades), and the version of each skill
is raised by one. In the harness skill the card also changes three Hermes line references to the
lines of the installed Hermes v0.23.3 (commit caafe5389ae585ef77387a962aee05b1bcf17029), where
the referenced text is the same as at the earlier lines.

reverse_hermes_update_text_edits() reverses these edits so that the tests of earlier cards, which
recover the bytes of an earlier commit, can still do so. This module imports no other test module,
so any test module can import it without a circular import.

Run: python3 tests/test_orchestrator_hermes_update_text.py
"""
import hashlib
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISION = "/Users/chanbla11mit/hermes-local-harness/docs/decisions/261120-plugin-behaviour-across-hermes-updates.md"
OWNER_UPDATE_QUOTATION = (
    "We're doing the Hermes update, no question. It's just: if that causes a plugin break, then we "
    "repair the plugin according to a new update. Or, better yet, we rework the plugin so it doesn't "
    "break from changes with updates. We must never stop an update for a plugin. Update compatibility "
    "is a must for our harness, non-negotiable.")
OWNER_MANUAL_QUOTATION = "No, we don't want auto-updates though. Updates should still be manual."
PARAGRAPH = (
    "The owner runs every Hermes update manually; no profile turns on automatic Hermes updates. "
    "A Hermes update is never held back because of a plugin or model provider of the harness "
    "repository. After an update, a plugin or provider that no longer works is repaired for the new "
    "Hermes release, or changed so that it keeps working or turns off only the one feature that "
    "needs the missing Hermes name and writes one Python `logging` record at level WARNING, as `"
    + DECISION + "` describes. Owner, Telegram direct message to `harness-orchestrator`, 2026-11-20 "
    "(verbatim): \"" + OWNER_UPDATE_QUOTATION + "\" Owner, 2026-11-20 (verbatim): \""
    + OWNER_MANUAL_QUOTATION + "\""
)
# skill directory prefix: (section that ends with the paragraph, heading that follows the section,
# version before, version after, SHA-256 of the file at baseline bcd4f1c61a12602915f9fc35ff3e03d0a23ac0ec)
SKILLS = {
    "anki": ("Operational Discipline", "Completion Gate", "0.6.10-anki.15", "0.6.10-anki.16",
             "257db0f0f98d2eaef69d184567553e2d1270bc05a8d3e0921bd1cf1c05c3c333"),
    "harness": ("Operational Discipline", "Completion Gate", "0.6.7-harness.18", "0.6.7-harness.19",
                "f713d3b846fdeac6269b6e0b2db31e2df89577fee6a4d901e0262aa56d94077f"),
    "jss": ("Operational Discipline", "Completion Gate", "0.6.7-jss.21", "0.6.7-jss.22",
            "8a3ba0c7e4af130514e82bc1474630bba5750938043ff43a3d55d0a5beedc693"),
    "chapt": ("Operating Principles", "Authorization Modes", "0.6.7-chapt.19", "0.6.7-chapt.20",
              "deceea872709c7a56bddb33334d6f95a1d9f28d4b8e54ee58b01374cd0cad181"),
    "jobcron": ("Operating Principles", "Authorization Modes", "0.6.9-jobcron.20", "0.6.9-jobcron.21",
                "c1179e7af39ca70d10ad866a9b9de476fef8bf4727baa2b14f2c2a793bd20306"),
}
# Harness skill only: (text after this card, text before). Lines of
# /Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/kanban_db.py in Hermes v0.23.3: BLOCK_RECURRENCE_LIMIT
# line 115, _route_block lines 3230 to 3240, the assignee update of assign_task lines 1469 to 1474.
LINE_REFERENCE_EDITS = (
    ("`, line 115), and the function `_route_block` (lines 3230 to 3240 of the same file)",
     "`, line 114), and the function `_route_block` (lines 3397 to 3407 of the same file)"),
    ("(function `assign_task`, lines 1469 to 1474 of", "(function `assign_task`, lines 1639 to 1644 of"),
)
SKILL_PATH = re.compile(r"^policies/profile-skills/([a-z]+)-orchestrator/autonomous-ai-agents/"
                        r"multi-agent-coding-orchestrator/SKILL\.md$")


def skill(prefix):
    return (f"policies/profile-skills/{prefix}-orchestrator/autonomous-ai-agents/"
            "multi-agent-coding-orchestrator/SKILL.md")


def reverse_hermes_update_text_edits(relative_path, text):
    """Return text with the t_642b5ce9 edits reversed; text may be str or bytes.

    relative_path is the path after this card. A path that this card did not change, and a text
    without this card's edits, is returned as the same object, so a second call changes nothing.
    """
    if isinstance(text, bytes):
        decoded = text.decode("utf-8")
        result = reverse_hermes_update_text_edits(relative_path, decoded)
        return text if result is decoded else result.encode("utf-8")
    match = SKILL_PATH.match(relative_path)
    if match is None or match.group(1) not in SKILLS:
        return text
    _section, _next, old_version, new_version, _sha256 = SKILLS[match.group(1)]
    result = text.replace("version: " + new_version + "\n", "version: " + old_version + "\n", 1)
    result = result.replace(PARAGRAPH + "\n\n", "", 1)
    if match.group(1) == "harness":
        for new, old in LINE_REFERENCE_EDITS:
            result = result.replace(new, old, 1)
    return text if result == text else result


class OrchestratorHermesUpdateText(unittest.TestCase):
    def test_each_skill_has_the_paragraph_once_at_the_end_of_its_section(self):
        for prefix, (section, next_heading, _old, version, _sha256) in SKILLS.items():
            with self.subTest(skill=prefix):
                text = (ROOT / skill(prefix)).read_text(encoding="utf-8")
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", text), [version])
                self.assertEqual(text.count(PARAGRAPH), 1)
                self.assertEqual(text.count(OWNER_UPDATE_QUOTATION), 1)
                self.assertEqual(text.count(OWNER_MANUAL_QUOTATION), 1)
                self.assertEqual(text.count(DECISION), 1)
                # The paragraph is the last block of its section, directly before the next heading.
                self.assertIn(f"\n## {section}\n", text)
                after_section = text.split(f"\n## {section}\n", 1)[1]
                self.assertTrue(after_section.split("\n## ", 1)[1].startswith(next_heading + "\n"))
                self.assertTrue(after_section.split("\n## ", 1)[0].endswith("\n" + PARAGRAPH + "\n"))

    def test_harness_line_references_name_the_v0_23_3_lines(self):
        text = (ROOT / skill("harness")).read_text(encoding="utf-8")
        for new, old in LINE_REFERENCE_EDITS:
            self.assertEqual(text.count(new), 1)
            self.assertEqual(text.count(old), 0)
        for prefix in ("anki", "jss", "chapt", "jobcron"):
            other = (ROOT / skill(prefix)).read_text(encoding="utf-8")
            self.assertNotIn("kanban_db.py", other)

    def test_reversal_gives_the_baseline_bytes(self):
        for prefix, (*_rest, sha256) in SKILLS.items():
            with self.subTest(skill=prefix):
                data = (ROOT / skill(prefix)).read_bytes()
                reversed_once = reverse_hermes_update_text_edits(skill(prefix), data)
                self.assertEqual(hashlib.sha256(reversed_once).hexdigest(), sha256)
                self.assertIs(reverse_hermes_update_text_edits(skill(prefix), reversed_once), reversed_once)
                self.assertEqual(reverse_hermes_update_text_edits(skill(prefix), data.decode()),
                                 reversed_once.decode())

    def test_other_paths_are_unchanged(self):
        text = "version: 0.6.7-harness.19\n" + PARAGRAPH + "\n\n"
        self.assertIs(reverse_hermes_update_text_edits("policies/profile-souls/harness-worker/SOUL.md", text),
                      text)


if __name__ == "__main__":
    unittest.main()
