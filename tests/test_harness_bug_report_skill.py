"""The harness-bug-report shared skill: frontmatter, snapshot declaration, body rules and index line."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/harness-bug-report/SKILL.md"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
README = ROOT / "docs/README.md"
DESCRIPTION = ("Use when a Hermes or harness defect is suspected. File a harness-board card with "
               "evidence; never write outside your own repository.")
ORCHESTRATORS = ["jobcron-orchestrator", "chapt-orchestrator", "harness-orchestrator",
                 "jss-orchestrator", "anki-orchestrator"]
README_LINE = ("- Harness defects found by project orchestrators arrive as cards on the harness board "
               "assigned to `harness-worker`, filed under the `harness-bug-report` skill "
               "([skill source](../skills/harness-bug-report/SKILL.md)); harness workers write the "
               "`docs/bugs/` entries from those cards.")


def parse_scalar(text):
    """A YAML plain scalar, double-quoted scalar, or flow sequence of plain scalars."""
    if text.startswith('"'):
        if not text.endswith('"') or len(text) < 2:
            raise ValueError(f"unterminated double-quoted scalar: {text!r}")
        return json.loads(text)
    if text.startswith("["):
        if not text.endswith("]"):
            raise ValueError(f"unterminated flow sequence: {text!r}")
        return [item.strip() for item in text[1:-1].split(",") if item.strip()]
    if text == "":
        raise ValueError("empty scalar")
    return text


def parse_frontmatter(text):
    """Parse the YAML subset that skill frontmatter uses: block mappings of scalars and flow
    sequences, nested by two-space indentation. Anything outside that subset raises ValueError
    (PyYAML is not installed in this environment)."""
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter opening line")
    block = text[4:].split("\n---\n", 1)
    if len(block) != 2:
        raise ValueError("no frontmatter closing line")
    root = {}
    stack = [(-1, root)]
    for line in block[0].split("\n"):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 or "\t" in line:
            raise ValueError(f"unsupported indentation: {line!r}")
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?: (.*))?", line.strip())
        if match is None:
            raise ValueError(f"unsupported line: {line!r}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        key, value = match.group(1), match.group(2)
        if key in parent:
            raise ValueError(f"duplicate key: {key}")
        if value is None:
            parent[key] = {}
            stack.append((indent, parent[key]))
        else:
            parent[key] = parse_scalar(value.strip())
    return root, block[1]


def section(body, number):
    match = re.search(rf"^## {number}\. .*?(?=^## |\Z)", body, re.M | re.S)
    assert match is not None, f"section {number} missing"
    return match.group(0)


class HarnessBugReportSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.frontmatter, cls.body = parse_frontmatter(cls.text)
        cls.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    # (1)
    def test_frontmatter_fields(self):
        self.assertEqual(self.frontmatter, {
            "name": "harness-bug-report",
            "description": DESCRIPTION,
            "version": "1.0.0",
            "author": "chanbla11mit, Hermes Agent",
            "license": "MIT",
            "platforms": ["macos", "linux", "windows"],
            "metadata": {"hermes": {"tags": ["kanban", "bug-report", "harness"]}},
        })
        reference, _ = parse_frontmatter(
            (ROOT / "skills/minimal-implementation/SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(self.frontmatter["platforms"], reference["platforms"])
        self.assertEqual(DESCRIPTION[:57], "Use when a Hermes or harness defect is suspected. File a ")

    def test_parser_rejects_unsupported_yaml(self):
        for bad in ("---\nname: a\n  : b\n---\n", "---\nname: [a\n---\n", "---\nname: a\nname: b\n---\n",
                    "---\nname: a\n"):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                parse_frontmatter(bad)

    # (2)
    def test_snapshot_declaration(self):
        entries = [e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "harness-bug-report"]
        self.assertEqual(entries, [{
            "name": "harness-bug-report",
            "path": "/Users/chanbla11mit/.hermes/profiles/<profile>/skills/autonomous-ai-agents/harness-bug-report",
            "source": "skills/harness-bug-report",
            "deploy_profiles": ORCHESTRATORS,
            "version": "1.0.0",
            "files": ["SKILL.md"],
        }])
        self.assertEqual(sorted(p.name for p in SKILL.parent.rglob("*") if p.is_file()), ["SKILL.md"])

    # (3)
    def test_body_names_the_filing_procedure(self):
        filing = section(self.body, 4)
        for phrase in ("`kanban_create`", "board: `harness`", "assignee: `harness-worker`",
                       "title: `<project>: <one-line defect>`",
                       "Do not use the command-line create (`hermes kanban ... create`)",
                       "does not subscribe the caller to the card",
                       "Do not write any file under `/Users/chanbla11mit/hermes-local-harness`",
                       "Do not create a cron job", "Do not send a message to the Harness Orchestrator directly"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, filing)
        self.assertIn("delivery_mode `notify+wake`", section(self.body, 5))
        evidence = section(self.body, 3)
        for phrase in ("`[REDACTED]`", "state what kind of value was removed", "no secret values",
                       "no tokens", "personal data", "no raw `.env` content", "Never guess a session ID"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evidence)

    # (4)
    def test_authority_is_limited_to_create_and_comment_on_the_filed_card(self):
        authority = section(self.body, 2)
        self.assertIn("2026-10-25", authority)
        self.assertIn("board `harness`", authority)
        self.assertEqual(set(re.findall(r"kanban_[a-z_]+", authority)), {"kanban_create", "kanban_comment"})
        self.assertIn("One `kanban_create` call per suspected defect.", authority)
        self.assertIn("`kanban_comment` on a card that the same orchestrator filed.", authority)
        self.assertIn("the only exception to the profile's rule against accessing another board", authority)
        for action in ("no other read", "no other write", "no claim", "no unblock", "no reassignment",
                       "no comment on a card that this orchestrator did not file",
                       "no access to any other board"):
            with self.subTest(action=action):
                self.assertIn(action, authority)
        self.assertIn("The SOUL and the profile-local orchestrator skill still contain the general rule", authority)
        # The harness orchestrator files on its own board without the exception.
        self.assertIn("not needed for it", section(self.body, 7))

    # (5)
    def test_readme_line_once_in_bugs_section(self):
        text = README.read_text(encoding="utf-8")
        self.assertEqual(text.count(README_LINE), 1)
        bugs = re.search(r"^## Bugs\n.*?(?=^## |\Z)", text, re.M | re.S)
        assert bugs is not None
        self.assertIn(README_LINE, bugs.group(0))

    # (6)
    def test_no_coined_or_project_terms(self):
        self.assertIsNone(re.search(r"[Vv]alue-blind", self.text))
        self.assertNotIn("(project term)", self.text)

    # (7)
    def test_clean_fixture_passes_with_the_declaration(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/verify-state"), "--fixture",
                                 str(ROOT / "tests/fixtures/clean.yaml")],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sorted(clean["skill_files"]["harness-bug-report"]), sorted(ORCHESTRATORS))


if __name__ == "__main__":
    unittest.main()
