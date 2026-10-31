"""The human-deployment-guide-review shared skill: frontmatter, snapshot declaration, docs index
line, the six review steps, the instruction to load the skill human-deployment-guide-writing as the
rule list, no copy of the numbered rules of that skill, and the absence of project-specific hosts,
accounts and values.

Offline checks of tracked bytes and of scripts/verify-state in fixture mode only.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

import test_human_deployment_guide_writing_skill as writing

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/devops/human-deployment-guide-review/SKILL.md"
WRITING_SKILL = ROOT / "skills/devops/human-deployment-guide-writing/SKILL.md"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
README = ROOT / "docs/README.md"
NAME = "human-deployment-guide-review"
WRITING_NAME = "human-deployment-guide-writing"
VERSION = "1.0.0"
TRIGGER = "Use when reviewing a guide that a person runs against production."
DEPLOY_PROFILES = ["jobcron-reviewer"]
README_LINE = (
    "- [Human deployment guide review](../skills/devops/human-deployment-guide-review/SKILL.md) — "
    "shared skill `human-deployment-guide-review` (version 1.0.0): six review steps for a guide that "
    "a person runs against production, with the rules of `human-deployment-guide-writing` as the "
    "rule list; declared for jobcron-reviewer; live deployment is a separate card.")

# For each review step of the accepted proposal (card t_db6b8e4b), phrases that the step must contain.
STEP_PHRASES = {
    1: ["Load the skill `human-deployment-guide-writing` with "
        "`skill_view(name=\"human-deployment-guide-writing\")` before you read the guide",
        "use its numbered rules as the rule list", "Do not review from memory or from a copy of the rules."],
    2: ["Check every rule of that skill against the guide line by line.",
        "Report each finding with the line number in the guide",
        "the number of the rule that the line does not meet"],
    3: ["Run the local parts of the guide in a new temporary directory",
        "never in the operator's repository or home directory",
        "Check the syntax of every command and every script",
        "Run every check and every script on made-up data",
        "Compare every filled-in value",
        "with the repository, the Terraform configuration files and the production records of the project"],
    4: ["Check the operator's machine read-only", "the installed tools and their versions",
        "the configured AWS profiles", "whether the repository is clean",
        "Change nothing on the operator's machine.", "Never run anything against cloud accounts or hosts",
        "`aws sts get-caller-identity`", "`terraform plan`"],
    5: ["Reject any text in the guide that is not a concise explanation of a command",
        "what the command does, why it is needed, and what it prints when it works",
        "Reject any statement of what does not change."],
    6: ["Give the verdict on the review card", "approve when there is no finding",
        "request changes with the list of all findings", "Never edit the guide",
        "review the whole file again from step 1"],
}


def normalize(text):
    return " ".join(text.split())


def steps(body):
    """Number -> step text for each numbered item of the `## Review steps` section."""
    match = re.search(r"^## Review steps\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    assert match is not None, "## Review steps section missing"
    items = re.split(r"^(\d+)\. ", match.group(1), flags=re.M)
    assert items[0].strip() == "", "text before the first review step"
    return {int(number): normalize(item) for number, item in zip(items[1::2], items[2::2])}


def writing_rule_sentences():
    """Every sentence of the numbered rules and reasons of the writing skill."""
    _, body = writing.parse_frontmatter(WRITING_SKILL.read_text(encoding="utf-8"))
    rules = writing.rules(body)
    sentences = []
    for rule, reason in rules.values():
        for part in (rule, reason):
            sentences += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`\"])", normalize(part))
                          if s.strip()]
    return rules, sentences


def copied_rule_sentences(text):
    normalized = normalize(text)
    return [s for s in writing_rule_sentences()[1] if s in normalized]


class HumanDeploymentGuideReviewSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.frontmatter, cls.body = writing.parse_frontmatter(cls.text)
        cls.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.steps = steps(cls.body)

    def test_frontmatter_fields_trigger_and_related_skill(self):
        self.assertEqual(self.frontmatter["name"], NAME)
        self.assertEqual(self.frontmatter["version"], VERSION)
        self.assertTrue(self.frontmatter["description"].startswith(TRIGGER))
        self.assertEqual(self.frontmatter["author"], "chanbla11mit, Hermes Agent")
        self.assertEqual(self.frontmatter["license"], "MIT")
        self.assertEqual(self.frontmatter["platforms"], ["macos", "linux"])
        self.assertIn("deployment", self.frontmatter["metadata"]["hermes"]["tags"])
        self.assertIn("review", self.frontmatter["metadata"]["hermes"]["tags"])
        self.assertEqual(self.frontmatter["metadata"]["hermes"]["related_skills"], [WRITING_NAME])
        self.assertEqual(sorted(self.frontmatter),
                         ["author", "description", "license", "metadata", "name", "platforms", "version"])

    def test_snapshot_declaration(self):
        entries = [e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == NAME]
        self.assertEqual(entries, [{
            "name": NAME,
            "path": f"/Users/chanbla11mit/.hermes/profiles/<profile>/skills/devops/{NAME}",
            "source": f"skills/devops/{NAME}",
            "deploy_profiles": DEPLOY_PROFILES,
            "version": VERSION,
            "files": ["SKILL.md"],
        }])
        self.assertEqual(entries[0]["version"], self.frontmatter["version"])
        self.assertEqual(sorted(p.name for p in SKILL.parent.rglob("*") if p.is_file()), ["SKILL.md"])
        roster = {p["name"] for p in json.loads((ROOT / "roster.yaml").read_text(encoding="utf-8"))["profiles"]}
        self.assertLessEqual(set(DEPLOY_PROFILES), roster)
        # The reviewer that loads this skill also carries the skill that holds the rule list.
        writing_entries = [e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == WRITING_NAME]
        self.assertEqual(len(writing_entries), 1)
        self.assertLessEqual(set(DEPLOY_PROFILES), set(writing_entries[0]["deploy_profiles"]))

    def test_readme_index_line_once_in_current_entries(self):
        text = README.read_text(encoding="utf-8")
        self.assertEqual(text.count(README_LINE), 1)
        current = re.search(r"^## Current entries\n.*?(?=^## |\Z)", text, re.M | re.S)
        assert current is not None
        self.assertIn(README_LINE, current.group(0))
        self.assertTrue((README.parent / "../skills/devops/human-deployment-guide-review/SKILL.md").is_file())

    def test_six_review_steps_in_order(self):
        self.assertEqual(list(self.steps), list(range(1, 7)))

    def test_each_review_step_states_the_accepted_text(self):
        for number, phrases in STEP_PHRASES.items():
            for phrase in phrases:
                with self.subTest(step=number, phrase=phrase):
                    self.assertIn(phrase, self.steps[number])

    def test_loads_the_writing_skill_by_name_as_the_rule_list(self):
        self.assertIn("The rule list for the review is the skill `human-deployment-guide-writing`.",
                      normalize(self.body))
        writing_frontmatter, _ = writing.parse_frontmatter(WRITING_SKILL.read_text(encoding="utf-8"))
        self.assertEqual(writing_frontmatter["name"], WRITING_NAME)
        # The writing skill names this skill as its companion review skill (its rule 11).
        self.assertIn(f"the companion skill `{NAME}`", WRITING_SKILL.read_text(encoding="utf-8"))

    def test_no_copy_of_the_numbered_rules_of_the_writing_skill(self):
        rules, sentences = writing_rule_sentences()
        self.assertEqual(list(rules), list(range(1, 13)))
        self.assertGreaterEqual(len(sentences), 24)
        self.assertEqual(copied_rule_sentences(self.text), [])
        self.assertIsNone(re.search(r"^## Rules$", self.body, re.M))
        self.assertIsNone(re.search(r"^\s*Reason: ", self.body, re.M))

    def test_copy_detection_finds_a_copied_rule(self):
        _, body = writing.parse_frontmatter(WRITING_SKILL.read_text(encoding="utf-8"))
        rule, reason = writing.rules(body)[3]
        self.assertEqual(copied_rule_sentences(self.text + "\n" + rule + "\n"), [rule])
        self.assertTrue(copied_rule_sentences(self.text + "\n" + reason + "\n"))

    def test_no_project_specific_host_account_or_value(self):
        lowered = self.text.lower()
        for word in writing.FORBIDDEN_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, lowered)
        for pattern, kind in writing.FORBIDDEN_PATTERNS:
            with self.subTest(kind=kind):
                self.assertEqual(re.findall(pattern, lowered), [])

    def test_no_coined_or_project_terms(self):
        self.assertNotIn("(project term)", self.text)
        self.assertIsNone(re.search(r"[Vv]alue-blind|[Cc]itation-gated", self.text))

    def test_clean_fixture_passes_with_the_declaration(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/verify-state"), "--fixture",
                                 str(ROOT / "tests/fixtures/clean.yaml")],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text(encoding="utf-8"))
        self.assertEqual(clean["skill_files"][NAME],
                         {profile: {"SKILL.md": "tracked-source"} for profile in DEPLOY_PROFILES})


if __name__ == "__main__":
    unittest.main()
