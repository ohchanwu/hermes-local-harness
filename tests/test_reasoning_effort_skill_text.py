#!/usr/bin/env python3
"""Card t_12797c56: the five orchestrator skills state the rule for the optional card line
"Reasoning effort EXACT <level>." in one paragraph at the end of `## Worker Selection` (anki,
harness, jss) or of `## Card Setup` (chapt, jobcron), with the board name of each skill in the
edit command, and the version of each skill is raised by one.

reverse_reasoning_effort_skill_text_edits() reverses these edits so that the tests of earlier
cards, which recover the bytes of an earlier commit, can still do so. It first reverses the edits
of the later card t_642b5ce9. This module imports only test_orchestrator_hermes_update_text, which
imports no other test module, so any test module can import it without a circular import.
"""
import hashlib
import pathlib
import re
import unittest

from test_orchestrator_hermes_update_text import reverse_hermes_update_text_edits

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISION = "/Users/chanbla11mit/hermes-local-harness/docs/decisions/261120-per-card-reasoning-effort.md"
LINE = "`Reasoning effort EXACT <level>.`"
LEVELS = "`<level>` is one of `low`, `medium`, `high`, `xhigh` and `max`."
PARAGRAPH = (
    "A card may contain one optional full line `Reasoning effort EXACT <level>.`, where `<level>` is one of "
    "`low`, `medium`, `high`, `xhigh` and `max`. Without the line, the worker runs at the reasoning effort of "
    "its profile; write the line only when the card needs a different level than the profile level of the "
    "assigned worker. The `jev` plugin of the worker applies the level to each model request of implementation "
    "workers only; reviewers and orchestrators keep their own level. For GLM, `xhigh` is sent as `max`. "
    "A Claude worker keeps the level of its first request for the whole run, so a changed line applies from "
    "the next run; change the body with `hermes kanban --board {board} edit <task id> --body=<body>`. "
    "When the `kanban_create` result contains a `jev` notice about the line (JSON key `jev_note`), correct the "
    "line before you unblock the card. The full design, its Hermes dependencies and the fallback are in "
    "`" + DECISION + "`."
)
# skill directory prefix: (board name, section that ends with the paragraph, version before, version after,
# SHA-256 of the file at baseline 688b1f61ddc903bf7bb2103a07db24ea2d3987c8)
SKILLS = {
    "anki": ("anki", "Worker Selection", "0.6.10-anki.14", "0.6.10-anki.15",
             "865dcebf06d4242e955102b1c4cccab4d690695d3f7de6d79d8770f15e8af427"),
    "harness": ("harness", "Worker Selection", "0.6.7-harness.17", "0.6.7-harness.18",
                "9cb6079cbc135de721a21dbd2f2c8b4721b22722929ccffdd1ac9d01669d1844"),
    "jss": ("jss-genr", "Worker Selection", "0.6.7-jss.20", "0.6.7-jss.21",
            "318dca53b9e8081a27e510cac40c05df98d3b2b343ca76a0014ef7cfcacc63b6"),
    "chapt": ("cha-pt", "Card Setup", "0.6.7-chapt.18", "0.6.7-chapt.19",
              "3be5a76d9cb236e566407628f0de02d0db9d10dd6332ebdd633d1e11ff52d450"),
    "jobcron": ("jobcron", "Card Setup", "0.6.9-jobcron.19", "0.6.9-jobcron.20",
                "6037093e30ba5105231646c538d89ef348c222a3bdddc3e94a38c7ec5680eea1"),
}
SKILL_PATH = re.compile(r"^policies/profile-skills/([a-z]+)-orchestrator/autonomous-ai-agents/"
                        r"multi-agent-coding-orchestrator/SKILL\.md$")


def skill(prefix):
    return (f"policies/profile-skills/{prefix}-orchestrator/autonomous-ai-agents/"
            "multi-agent-coding-orchestrator/SKILL.md")


def reverse_reasoning_effort_skill_text_edits(relative_path, text):
    """Return text with the t_12797c56 edits reversed; text may be str or bytes.

    relative_path is the path after this card. A path that this card did not change is returned
    with the text unchanged. Each replacement applies only when its new text is present, so a
    second call returns the same text.
    """
    text = reverse_hermes_update_text_edits(relative_path, text)
    if isinstance(text, bytes):
        decoded = text.decode("utf-8")
        result = reverse_reasoning_effort_skill_text_edits(relative_path, decoded)
        return text if result == decoded else result.encode("utf-8")
    match = SKILL_PATH.match(relative_path)
    if match is None or match.group(1) not in SKILLS:
        return text
    board, _section, old_version, new_version, _sha256 = SKILLS[match.group(1)]
    text = text.replace("version: " + new_version + "\n", "version: " + old_version + "\n", 1)
    return text.replace(PARAGRAPH.format(board=board) + "\n\n", "", 1)


class ReasoningEffortSkillText(unittest.TestCase):
    def test_each_skill_has_the_paragraph_once_at_the_end_of_its_section(self):
        for prefix, (board, section, _old, version, _sha256) in SKILLS.items():
            with self.subTest(skill=prefix):
                # Card t_642b5ce9 raised each version by one more step; its edits are reversed first.
                text = reverse_hermes_update_text_edits(skill(prefix),
                                                        (ROOT / skill(prefix)).read_text(encoding="utf-8"))
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", text), [version])
                self.assertEqual(text.count(LINE), 1)
                self.assertEqual(text.count(DECISION), 1)
                match = re.search(rf"(?ms)^## {section}\n(.*?)\n\n(?=^## )", text)
                assert match is not None, f"{prefix}: section {section} not found"
                para = match.group(1).split("\n\n")[-1]
                self.assertEqual(para, PARAGRAPH.format(board=board))
                self.assertEqual(para.count(LEVELS), 1)
                self.assertEqual(para.count(DECISION), 1)
                self.assertEqual(para.count(f"`hermes kanban --board {board} edit <task id> --body=<body>`"), 1)
                self.assertEqual(re.findall(r"--board ([\w-]+) edit", para), [board])

    def test_reversal_gives_the_baseline_bytes(self):
        for prefix, (*_rest, sha256) in SKILLS.items():
            with self.subTest(skill=prefix):
                data = (ROOT / skill(prefix)).read_bytes()
                reversed_once = reverse_reasoning_effort_skill_text_edits(skill(prefix), data)
                self.assertEqual(hashlib.sha256(reversed_once).hexdigest(), sha256)
                self.assertEqual(reverse_reasoning_effort_skill_text_edits(skill(prefix), reversed_once),
                                 reversed_once)

    def test_other_paths_are_unchanged(self):
        text = "version: 0.6.7-harness.18\n"
        self.assertIs(reverse_reasoning_effort_skill_text_edits("policies/profile-souls/harness-worker/SOUL.md", text),
                      text)


if __name__ == "__main__":
    unittest.main()
