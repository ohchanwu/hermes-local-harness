#!/usr/bin/env python3
"""Offline contracts for the Ponytail 5.3.3 policy text (t_0c1ccf16).

Each SOUL under policies/profile-souls/ must contain the wording-rule paragraph
exactly once, inside its "Terminology and wording" section. Each orchestrator
SKILL.md under policies/profile-skills/ must contain the Ponytail skill-policy
paragraph with its own reviewer name, the Card Contract item that replaces the
forced-skill item, and no text of the replaced minimal-implementation policy.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOUL_GLOB = "policies/profile-souls/*/SOUL.md"
SKILL_TEMPLATE = (
    "policies/profile-skills/{orchestrator}/autonomous-ai-agents/"
    "multi-agent-coding-orchestrator/SKILL.md"
)
ORCHESTRATORS = {
    "anki-orchestrator": "anki-reviewer",
    "chapt-orchestrator": "chapt-reviewer",
    "harness-orchestrator": "harness-reviewer",
    "jobcron-orchestrator": "jobcron-reviewer",
    "jss-orchestrator": "jss-reviewer",
}
SOUL_SECTION_START = "\nTerminology and wording\n"
SOUL_SECTION_END = "\nTests that contradict a required change\n"
WORDING_PARAGRAPH = (
    "These wording rules take precedence over the instructions that the Ponytail plugin adds to each turn. "
    "Do not write the Ponytail code comment marker `shortcut:`; write a plain code comment that states the "
    "known limit and the condition for changing the code."
)
CONTRACT_ITEM = "Skill-policy metadata naming each forced skill, or stating that no skill is forced."
CONTRACT_ITEM_LINE = re.compile(r"^(?:\d+\. |- )" + re.escape(CONTRACT_ITEM) + r"$", re.MULTILINE)
SKILL_PARAGRAPH_TEMPLATE = (
    "The Ponytail plugin, version 5.3.3 pinned to commit 7801d061243d7b753bad0e0b3c057cd250b11755, "
    "is enabled at level `full` on every worker, reviewer and orchestrator profile of the five boards. "
    "The line `PONYTAIL_DEFAULT_MODE=full` in each profile's `.env` file sets the level. "
    "Do not force `minimal-implementation` on a card. "
    "The commands `/ponytail-review` and `/ponytail-audit` are not a review of a card; "
    "only same-card review by {reviewer} approves a card."
)
REPLACED_STATE = (
    "Attach `minimal-implementation`",
    "Ponytail never runs as a plugin",
    "minimal_implementation: enabled|disabled",
)


OLD_CONTRACT_ANKI_HARNESS_JSS = "Skill-policy metadata stating whether `minimal-implementation` is enabled."
OLD_CONTRACT_CHAPT_JOBCRON = "Skill policy metadata (`minimal_implementation` enabled/disabled and reason; see Skills)."
OLD_SKILL_ANKI = (
    "Attach `minimal-implementation` only for dependency choice, suspected overengineering, refactoring, "
    "simplification, or shared-function repair where simplification does not weaken required evidence. "
    "Leave it off for deck change cards and for collection-access or add-on install tooling, where exact "
    "boundaries outrank brevity. Record the decision and reason on the card."
)
OLD_SKILL_HARNESS = (
    "Attach `minimal-implementation` only for native-alternative questions, dependency choice, open-ended "
    "UI/component work, suspected overengineering, refactoring, simplification, shared-function repair, or "
    "diagnostic design where simplification does not weaken required evidence.\n\n"
    "Leave it off for acceptance-heavy security, trust-boundary, migration, data-loss, concurrency, "
    "infrastructure, production, or compliance-sensitive work. Record the decision and reason on the card."
)
OLD_SKILL_JSS = (
    "Attach `minimal-implementation` only to repository cards for dependency choice, suspected "
    "overengineering, refactoring, simplification, or shared-function repair where simplification does not "
    "weaken required evidence. Never attach it to writing rounds: fidelity to the owner's draft and the hard "
    "rules outrank brevity. Record the decision and reason on the card."
)
SIMPLIFICATION_REVIEW_ITEM = (
    "- `simplification-review` is a separate, optional post-implementation review skill; it recommends "
    "reductions only and never edits or weakens tests. It is never a substitute for required verification."
)
OLD_PONYTAIL_PARAGRAPH = (
    "Ponytail never runs as a plugin on Hermes profiles. Implementation profiles keep the pinned package "
    "installed but `disabled`; the minimalism behavior lives in the per-card `minimal-implementation` skill "
    "instead (see Skills). The orchestrator, reviewer, and advisor neither load it nor the simplification skill."
)
OLD_SKILL_BLOCK_CHAPT_JOBCRON = "\n".join([
    "`minimal-implementation` is the task-triggered minimalism skill. The orchestrator attaches it per card "
    "(via `skills: [\"minimal-implementation\"]` on the card) using this policy:",
    "",
    "- Attach for: native/platform-alternative questions, dependency or library choice, open-ended UI/component "
    "work, suspected overengineering, refactoring or simplification, and shared-function or root-cause repair.",
    "- Attach for diagnostic design, including infrastructure diagnostics; separate any production/mutation "
    "implementation slice.",
    "- Leave off for ordinary implementation of acceptance-heavy, security or trust-boundary, migration or "
    "data-loss, concurrency or distributed-systems, infrastructure or production, and compliance-sensitive tasks.",
    "- Override: the orchestrator may leave the skill off for any attach-category task.",
    SIMPLIFICATION_REVIEW_ITEM,
    "",
    "Record the decision in card metadata: `skill_policy_version`, `minimal_implementation: enabled|disabled`, "
    "the reason. Reviewer and advisor lanes never load the implementation skill.",
])
# orchestrator: (old version, new version, reviewer, contract item before, skill text before)
SKILL_EDITS = {
    "anki": ("0.6.10-anki.13", "0.6.10-anki.14", "anki-reviewer", OLD_CONTRACT_ANKI_HARNESS_JSS, OLD_SKILL_ANKI),
    "harness": ("0.6.7-harness.16", "0.6.7-harness.17", "harness-reviewer", OLD_CONTRACT_ANKI_HARNESS_JSS,
                OLD_SKILL_HARNESS),
    "jss": ("0.6.7-jss.19", "0.6.7-jss.20", "jss-reviewer", OLD_CONTRACT_ANKI_HARNESS_JSS, OLD_SKILL_JSS),
    "chapt": ("0.6.7-chapt.17", "0.6.7-chapt.18", "chapt-reviewer", OLD_CONTRACT_CHAPT_JOBCRON, None),
    "jobcron": ("0.6.9-jobcron.18", "0.6.9-jobcron.19", "jobcron-reviewer", OLD_CONTRACT_CHAPT_JOBCRON, None),
}
SOUL_PATH = re.compile(r"^policies/profile-souls/[^/]+/SOUL\.md$")
SKILL_PATH = re.compile(r"^policies/profile-skills/([a-z]+)-orchestrator/autonomous-ai-agents/"
                        r"multi-agent-coding-orchestrator/SKILL\.md$")


def reverse_ponytail_policy_text_edits(relative_path, text):
    """Return text with the t_0c1ccf16 edits reversed; text may be str or bytes.

    relative_path is the path after this card. A path that this card did not change is returned
    with the text unchanged. Each replacement applies only when its new text is present, so a
    second call returns the same text.
    """
    if isinstance(text, bytes):
        decoded = text.decode("utf-8")
        result = reverse_ponytail_policy_text_edits(relative_path, decoded)
        return text if result == decoded else result.encode("utf-8")
    if SOUL_PATH.match(relative_path):
        return text.replace("\n" + WORDING_PARAGRAPH + "\n\nTests that contradict", "\nTests that contradict")
    match = SKILL_PATH.match(relative_path)
    if match is None or match.group(1) not in SKILL_EDITS:
        return text
    old_version, new_version, reviewer, old_contract, old_skill = SKILL_EDITS[match.group(1)]
    text = text.replace("version: " + new_version + "\n", "version: " + old_version + "\n", 1)
    # Card Contract item: the list marker is kept, the text is replaced.
    text = re.sub(r"^((?:\d+\. |- )?)" + re.escape(CONTRACT_ITEM) + r"$",
                  lambda m: m.group(1) + old_contract, text, count=1, flags=re.MULTILINE)
    paragraph = SKILL_PARAGRAPH_TEMPLATE.format(reviewer=reviewer)
    if old_skill is not None:
        text = text.replace(paragraph, old_skill)
    else:
        text = text.replace("## Skills\n\n" + paragraph + "\n\n" + SIMPLIFICATION_REVIEW_ITEM,
                            OLD_PONYTAIL_PARAGRAPH + "\n\n## Skills\n\n" + OLD_SKILL_BLOCK_CHAPT_JOBCRON)
    return text


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class SoulWordingParagraphTest(unittest.TestCase):
    def test_every_soul_contains_wording_paragraph_once_in_terminology_section(self):
        files = sorted(ROOT.glob(SOUL_GLOB))
        self.assertEqual(len(files), 47, "expected 47 SOUL files")
        for path in files:
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT)
            with self.subTest(soul=str(rel)):
                self.assertEqual(
                    text.count(WORDING_PARAGRAPH), 1,
                    f"{rel}: wording paragraph must occur exactly once",
                )
                self.assertEqual(text.count(SOUL_SECTION_START), 1, f"{rel}: Terminology section")
                self.assertEqual(text.count(SOUL_SECTION_END), 1, f"{rel}: Tests section")
                start = text.index(SOUL_SECTION_START)
                end = text.index(SOUL_SECTION_END)
                at = text.index(WORDING_PARAGRAPH)
                self.assertTrue(
                    start < at < end,
                    f"{rel}: wording paragraph must lie inside the Terminology and wording section",
                )
                self.assertEqual(
                    text.count(WORDING_PARAGRAPH + "\n\nTests that contradict a required change\n"),
                    1,
                    f"{rel}: wording paragraph must be the last paragraph before the Tests section",
                )


class OrchestratorSkillPolicyTest(unittest.TestCase):
    def test_each_orchestrator_skill_contains_its_own_policy_text(self):
        for orchestrator, reviewer in ORCHESTRATORS.items():
            text = read(SKILL_TEMPLATE.format(orchestrator=orchestrator))
            with self.subTest(skill=orchestrator):
                paragraph = SKILL_PARAGRAPH_TEMPLATE.format(reviewer=reviewer)
                self.assertEqual(
                    text.count(paragraph), 1,
                    f"{orchestrator}: skill-policy paragraph with reviewer {reviewer} must occur once",
                )
                self.assertEqual(
                    len(CONTRACT_ITEM_LINE.findall(text)), 1,
                    f"{orchestrator}: Card Contract item must occur exactly once as a list item",
                )

    def test_each_orchestrator_skill_omits_replaced_minimal_implementation_policy(self):
        for orchestrator in ORCHESTRATORS:
            text = read(SKILL_TEMPLATE.format(orchestrator=orchestrator))
            for phrase in REPLACED_STATE:
                with self.subTest(skill=orchestrator, phrase=phrase):
                    self.assertNotIn(
                        phrase, text,
                        f"{orchestrator}: replaced policy text must not remain: {phrase}",
                    )


if __name__ == "__main__":
    unittest.main()
