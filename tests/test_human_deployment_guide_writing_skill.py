"""The human-deployment-guide-writing shared skill: frontmatter, snapshot declaration, docs index
line, the twelve rules with one reason each, and the absence of project-specific hosts, accounts
and values.

Offline checks of tracked bytes and of scripts/verify-state in fixture mode only.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/devops/human-deployment-guide-writing/SKILL.md"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
README = ROOT / "docs/README.md"
NAME = "human-deployment-guide-writing"
VERSION = "1.0.0"
TRIGGER = "Use when writing steps a person runs against production."
DEPLOY_PROFILES = ["jobcron-orchestrator", "jobcron-worker", "jobcron-worker-2", "jobcron-reviewer"]
README_LINE = (
    "- [Human deployment guide writing](../skills/devops/human-deployment-guide-writing/SKILL.md) — "
    "shared skill `human-deployment-guide-writing` (version 1.0.0): twelve rules for a guide that a "
    "person runs against production; declared for jobcron-orchestrator, jobcron-worker, "
    "jobcron-worker-2 and jobcron-reviewer; live deployment is a separate card.")

# For each of the twelve owner-approved rules (2026-10-31), phrases that the rule text must contain.
RULE_PHRASES = {
    1: ["Check the operator's machine before you write any step", "the AWS profile and its SSO sign-in",
        "the CLI plugins", "the tool versions", "the shell (zsh)", "whether the repository is clean",
        "Make anything that is missing step 0 of the guide, with its exact command."],
    2: ["Fill in every value in every command.",
        "Use a placeholder only for a value that is created during the run",
        "store it in a shell variable"],
    3: ["Write every step as a command, never as a description of something to do."],
    4: ["a concise explanation of what it does, why it is needed, and what it prints when it works",
        "so that the operator learns from the guide", "Add no other text: no summary, no decisions, "
        "no history, no statements of what does not change, and no failure sections."],
    5: ["longer than a few lines", "contains text to paste", "a script file or a `pbcopy` block",
        "prepare that file or block before you hand over the guide"],
    6: ["Test every command locally up to the point where it would touch production",
        "the syntax and the quoting", "every `sudo` command that contains a file name pattern",
        "run every check on made-up data"],
    7: ["Make the guide self-contained", "do not refer to any other document"],
    8: ["Read every secret with a silent prompt",
        '"Store X in your password manager under entry Y."'],
    9: ["Before a step that cannot be undone", "save only the values that are needed to undo that step"],
    10: ["one file at a fixed location", "send that file once as an attachment",
         "Never send commands through chat.", 'send the file again with the one line "changed step N"'],
    11: ["Before the operator receives the guide", "the reviewer that the board designates",
         "on a card of the project board", "the companion skill `human-deployment-guide-review`",
         "Fix every requested change in the file, and have the file reviewed again."],
    12: ["give short replies that answer the question that the operator asked",
         "ask before you change anything on the operator's machine"],
}

# Project names, hosts, accounts and values that a project-neutral skill must not contain.
FORBIDDEN_WORDS = ["jobcron", "chapt", "cha pt", "cha-pt", "cha-webpt", "jev", "telegram",
                   "release_sha", "invalidclienttokenid", "1.24.4", "1.26.3", "/users/", ".hermes",
                   "hermes-local-harness"]
FORBIDDEN_PATTERNS = [
    (r"(?<!\d)\d{12}(?!\d)", "AWS account ID"),
    (r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "IPv4 address"),
    (r"\barn:aws", "AWS resource name"),
    (r"\b[0-9a-f]{7,40}\b", "commit ID or other hexadecimal value"),
    (r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|dev|app|kr|co|cloud|internal)\b", "host name"),
    (r"\b(?:i|vpc|subnet|sg)-[0-9a-f]{8,17}\b", "EC2 resource ID"),
    (r"\b(?:ap|us|eu|sa|ca|me|af)-[a-z]+-\d\b", "AWS region"),
]


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
    sequences, nested by two-space indentation (PyYAML is not installed in this environment)."""
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


def rules(body):
    """Number -> (rule text, reason text) for each numbered item of the `## Rules` section."""
    match = re.search(r"^## Rules\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    assert match is not None, "## Rules section missing"
    items = re.split(r"^(\d+)\. ", match.group(1), flags=re.M)
    assert items[0].strip() == "", "text before the first rule"
    result = {}
    for number, item in zip(items[1::2], items[2::2]):
        lines = [line.strip() for line in item.strip().split("\n")]
        reasons = [line for line in lines if line.startswith("Reason: ")]
        assert len(reasons) == 1, f"rule {number}: expected one reason line, found {len(reasons)}"
        assert lines[-1] == reasons[0], f"rule {number}: the reason is not the last line"
        result[int(number)] = (" ".join(lines[:-1]), reasons[0][len("Reason: "):])
    return result


class HumanDeploymentGuideWritingSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.frontmatter, cls.body = parse_frontmatter(cls.text)
        cls.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.rules = rules(cls.body)

    def test_frontmatter_fields_and_trigger(self):
        self.assertEqual(self.frontmatter["name"], NAME)
        self.assertEqual(self.frontmatter["version"], VERSION)
        self.assertTrue(self.frontmatter["description"].startswith(TRIGGER))
        self.assertEqual(self.frontmatter["author"], "chanbla11mit, Hermes Agent")
        self.assertEqual(self.frontmatter["license"], "MIT")
        self.assertEqual(self.frontmatter["platforms"], ["macos", "linux"])
        self.assertIn("deployment", self.frontmatter["metadata"]["hermes"]["tags"])
        self.assertEqual(sorted(self.frontmatter),
                         ["author", "description", "license", "metadata", "name", "platforms", "version"])

    def test_parser_rejects_unsupported_yaml(self):
        for bad in ("---\nname: a\n  : b\n---\n", "---\nname: [a\n---\n", "---\nname: a\nname: b\n---\n",
                    "---\nname: a\n"):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                parse_frontmatter(bad)

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

    def test_readme_index_line_once_in_current_entries(self):
        text = README.read_text(encoding="utf-8")
        self.assertEqual(text.count(README_LINE), 1)
        current = re.search(r"^## Current entries\n.*?(?=^## |\Z)", text, re.M | re.S)
        assert current is not None
        self.assertIn(README_LINE, current.group(0))
        self.assertTrue((README.parent / "../skills/devops/human-deployment-guide-writing/SKILL.md").is_file())

    def test_twelve_rules_in_order_each_with_one_reason_sentence(self):
        self.assertEqual(list(self.rules), list(range(1, 13)))
        for number, (rule, reason) in self.rules.items():
            with self.subTest(rule=number):
                # A rule can end with a quoted sentence, for example rule 8.
                self.assertTrue(rule.endswith((".", '."')), rule)
                self.assertTrue(reason.endswith("."), reason)
                # One sentence: no sentence end before the final full stop.
                self.assertIsNone(re.search(r"[.!?] [A-Z]", reason), reason)

    def test_each_rule_states_the_approved_text(self):
        for number, phrases in RULE_PHRASES.items():
            rule = self.rules[number][0]
            for phrase in phrases:
                with self.subTest(rule=number, phrase=phrase):
                    self.assertIn(phrase, rule)

    def test_rule_examples_quote_the_observed_failures(self):
        self.assertIn("`sudo sha256sum /root/dir/*`", self.rules[6][1])
        self.assertIn("`sudo sh -c 'sha256sum /root/dir/*'`", self.rules[6][1])
        self.assertIn("`read -rs 'DB_PASSWORD?Database password: '`", self.rules[8][0])
        self.assertIn("masking a secret name as `***`", self.rules[10][1])
        self.assertIn("`pbcopy <<'EOF'`", self.rules[5][0])

    def test_no_project_specific_host_account_or_value(self):
        lowered = self.text.lower()
        for word in FORBIDDEN_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, lowered)
        for pattern, kind in FORBIDDEN_PATTERNS:
            with self.subTest(kind=kind):
                self.assertEqual(re.findall(pattern, lowered), [])

    def test_forbidden_patterns_detect_synthetic_values(self):
        samples = {"AWS account ID": "account 123456789012", "IPv4 address": "host 10.0.0.1",
                   "AWS resource name": "arn:aws:iam::x", "commit ID or other hexadecimal value": "sha 0123abc",
                   "host name": "api.example.com", "EC2 resource ID": "i-0123456789abcdef0",
                   "AWS region": "region ap-northeast-2"}
        for pattern, kind in FORBIDDEN_PATTERNS:
            with self.subTest(kind=kind):
                self.assertTrue(re.search(pattern, samples[kind]))

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
