"""The harness-bug-report shared skill: frontmatter, snapshot declaration, body rules, index line,
the kanban_create arguments of section 4, and the card body template.

Offline checks of tracked bytes and of the scripts/verify-state card contract check only. All
cards and values are synthetic.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/harness-bug-report/SKILL.md"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
README = ROOT / "docs/README.md"
REPOSITORY = "/Users/chanbla11mit/hermes-local-harness"
DESCRIPTION = ("Use when a Hermes or harness defect is suspected. File a harness-board card with "
               "evidence; never write outside your own repository.")
ORCHESTRATORS = ["jobcron-orchestrator", "chapt-orchestrator", "harness-orchestrator",
                 "jss-orchestrator", "anki-orchestrator"]
DEPLOY_PROFILES = ORCHESTRATORS + ["advisor"]
VERSION = "1.2.0"
# SHA-256 of sections 1 to 7 (from "## 1." up to "## 8.", trailing newlines removed) as they were
# in version 1.0.0. Version 1.1.0 adds section 8 and leaves sections 1 to 7 unchanged.
SECTIONS_1_TO_7_SHA256 = "0894ba1525519ad6cac21fa6c2e34cd0f139914605fb7f5f46224399e420bc99"
# SHA-256 of the whole file in version 1.1.0. Version 1.2.0 differs from it only by EDITS_1_2_0
# and by the card body template subsection (TEMPLATE_HEADING up to the closing fence).
SKILL_1_1_0_SHA256 = "0ec3b2f9bbdbb8a1c174f776c3d3f3d8922fc94eb5a2a7769acb1c2d6dd78ebd"
INTRO_1_0_0 = ("This skill tells a project orchestrator how to report a suspected defect in Hermes or in the "
               "harness. The result is a card on the harness board. A harness worker then writes the "
               "`docs/bugs/` report and any fix in the harness repository, under the normal review "
               "procedure of the harness board.")
INTRO_ADDED_SENTENCE = (" Section 8 states when the `advisor` profile may take the same two actions that "
                        "section 2 authorizes.")
README_LINE = ("- Harness defects found by project orchestrators arrive as cards on the harness board "
               "assigned to `harness-worker`, filed under the `harness-bug-report` skill "
               "([skill source](../skills/harness-bug-report/SKILL.md)); harness workers write the "
               "`docs/bugs/` entries from those cards.")

WORKSPACE_KIND_ARGUMENT = (
    "- workspace_kind: `worktree`, with no `workspace_path` argument, so that the card uses the default "
    "working directory of the harness board, which is the repository root. This argument is required "
    "because the workspace kind of a card cannot be changed after the card is created.\n")
INITIAL_STATUS_ARGUMENT = (
    "- initial_status: `blocked`. This argument is required because the card must not be dispatched "
    "before harness-orchestrator has checked it.\n")
SECTION_7_ADDED = (
    "A card filed under this skill arrives on the harness board blocked. harness-orchestrator checks the "
    "card against the card contract, writes the worktree path and the branch, which depend on the card "
    "ID, into the body, pins `refs/harness/baselines/<ID>`, may replace the baseline with the current "
    "`main`, and then unblocks the card. Files under `docs/bugs/` and filed cards remain evidence, not "
    "implementation authorization, until harness-orchestrator unblocks the card.\n")
SECTION_7_LAST_SENTENCE = "because the harness board is its own board.\n"
# Version 1.2.0 edits outside the template subsection: (new text, text in version 1.1.0).
# Each new text occurs exactly once.
EDITS_1_2_0 = (
    ("version: 1.2.0\n", "version: 1.1.0\n"),
    (WORKSPACE_KIND_ARGUMENT + INITIAL_STATUS_ARGUMENT
     + "- body: the card body template below, filled in\n\nPass no other argument.\n",
     "- body: the evidence from section 3\n"),
    (SECTION_7_LAST_SENTENCE + "\n" + SECTION_7_ADDED, SECTION_7_LAST_SENTENCE),
    ("The advisor uses the arguments and the card body template of section 4,",
     "The advisor uses the arguments of section 4,"),
)
TEMPLATE_HEADING = "\n### Card body template\n"

ARGUMENT_NAMES = ["board", "assignee", "title", "workspace_kind", "initial_status", "body"]
HEADER_LINES = [
    f"Repository {REPOSITORY} ONLY. Board harness ONLY.",
    "Workspace kind worktree; harness-orchestrator adds the exact path at setup.",
    "Baseline EXACT <40-hex>.",
    "Assigned worker EXACT harness-worker.",
    "Reviewer EXACT harness-reviewer.",
    "Runtime cap 3600s per run.",
    "Skill policy: minimal-implementation disabled; requirements and risk outrank simplification.",
]
HEADINGS = ["## Evidence", "## Suspected location", "## Proposed change", "## Tests", "## Deployment",
            "## Prohibited without separate human authorization"]
FOCUSED_PLACEHOLDER = "python3 tests/<focused test file>.py"
SUITE_LOOP = ('for f in tests/test_*.py; do [ "$f" = tests/test_verify_state.py ] && continue; '
              'LANG=en_US.UTF-8 python3 "$f" >/dev/null 2>&1 || echo "FAIL $f"; '
              'env -u LANG python3 "$f" >/dev/null 2>&1 || echo "FAIL-noLANG $f"; done')
DEPLOYMENT = "Deployment to the live profile copies is out of scope for this card and needs a separate card."
PROHIBITED = ("Push, PR, deployment; any change to live profiles, plugins, skills, SOULs or config; "
              "credentials; network; production or cloud mutations; other repositories and boards; any "
              "other external write. Do not run `scripts/verify-state` without `--fixture`. Never put "
              "secrets, tokens or real transcript content in tests or fixtures.")
DELIVERABLE = ("Deliverable: one local commit on the card's branch whose parent is the baseline, then "
               "`kanban_request_review` with reviewer `harness-reviewer`.")
SYNTHETIC_BASELINE = "0123456789abcdef" * 2 + "01234567"
SYNTHETIC_FILLS = {
    "<40-hex>": SYNTHETIC_BASELINE,
    "<the items of section 3>": "- Synthetic error text: example failure.",
    "<repository file and line numbers at the baseline, or not known>": "not known",
    "<the proposed change, or none>": "none",
}


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
    """Text from the `## <number>. ` heading up to the next `## ` heading outside a fenced block."""
    lines = body.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith(f"## {number}. ")), None)
    assert start is not None, f"section {number} missing"
    in_fence = False
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("```"):
            in_fence = not in_fence
        elif not in_fence and lines[index].startswith("## "):
            return "".join(lines[start:index])
    return "".join(lines[start:])


def template(text):
    """The one fenced card body template, without its fence lines."""
    blocks = re.findall(r"^```text\n(.*?)^```$", text, re.M | re.S)
    assert len(blocks) == 1, f"expected one fenced template, found {len(blocks)}"
    return blocks[0]


def fill(template_text, focused="python3 tests/test_example.py"):
    """The template with every placeholder replaced by a synthetic value."""
    fills = dict(SYNTHETIC_FILLS, **{FOCUSED_PLACEHOLDER: focused})
    for placeholder, value in fills.items():
        assert template_text.count(placeholder) == 1, placeholder
        template_text = template_text.replace(placeholder, value)
    assert "<" not in template_text, "placeholder left in the filled template"
    return template_text


def reverse_1_2_0_edits(text):
    """The version 1.1.0 text: the template subsection removed and EDITS_1_2_0 reversed."""
    assert text.count(TEMPLATE_HEADING) == 1
    start = text.index(TEMPLATE_HEADING)
    end = text.index("\n```\n", text.index("```text\n", start)) + len("\n```\n")
    text = text[:start] + text[end:]
    for new, old in EDITS_1_2_0:
        assert text.count(new) == 1, new[:60]
        text = text.replace(new, old, 1)
    return text


def load_verifier():
    source = ROOT / "scripts/verify-state"
    module = types.ModuleType("verify_state_harness_bug_report")
    module.__file__ = str(source)
    exec(compile(source.read_text(), str(source), "exec"), module.__dict__)
    return module


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
            "version": VERSION,
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
            "deploy_profiles": DEPLOY_PROFILES,
            "version": VERSION,
            "files": ["SKILL.md"],
        }])
        self.assertEqual(entries[0]["deploy_profiles"][-1], "advisor")
        self.assertEqual(entries[0]["version"], self.frontmatter["version"])
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
        self.assertEqual(re.findall(r"board `([a-z-]+)`", authority), ["harness"])
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
        self.assertEqual(sorted(clean["skill_files"]["harness-bug-report"]), sorted(DEPLOY_PROFILES))

    # (8)
    def test_advisor_section_is_limited_to_create_and_comment_on_board_harness(self):
        self.assertEqual(re.findall(r"^## (\d+)\. ", self.body, re.M), [str(n) for n in range(1, 9)])
        advisor = section(self.body, 8)
        self.assertTrue(advisor.startswith("## 8. When the advisor profile loads this skill\n"))
        self.assertIn("The owner explicitly authorized (2026-10-25) the `advisor` profile to take exactly "
                      "the two actions of section 2 on board `harness`:", advisor)
        self.assertEqual(set(re.findall(r"kanban_[a-z_]+", advisor)), {"kanban_create", "kanban_comment"})
        self.assertEqual(re.findall(r"board `([a-z-]+)`", advisor), ["harness"])
        self.assertIn("- One `kanban_create` call per suspected defect.", advisor)
        self.assertIn("- `kanban_comment` on a card that the advisor filed.", advisor)
        self.assertIn("the one owner-authorized exception to the advisor's default of read-only consultation",
                      advisor)
        for action in ("no other board access", "no claim", "no unblock", "no reassignment",
                       "no comment on a card that the advisor did not file", "no file write",
                       "no message to any orchestrator or to any orchestrator session"):
            with self.subTest(action=action):
                self.assertIn(action, advisor)
        self.assertIn("during a consultation, the advisor's own investigation", advisor)
        self.assertIn("meets the test in section 1", advisor)
        self.assertIn("The advisor files the card without first asking the user", advisor)
        self.assertIn("states the ID of the card that it filed in the same reply to the user", advisor)
        self.assertIn("The advisor uses the arguments and the card body template of section 4", advisor)
        self.assertIn("the title `<project>: <one-line defect>`", advisor)
        self.assertIn("or `advisor` when no project is involved", advisor)
        self.assertIn("The session ID is the advisor's own session ID.", advisor)
        self.assertIn("give that profile name and that session ID", advisor)
        self.assertIn("quote only the lines that are needed", advisor)
        self.assertIn("with secret values replaced as section 3 requires", advisor)
        self.assertIn('section 5 applies with "continue the consultation" in place of '
                      '"continue the project work"', advisor)
        self.assertIn("Re-testing is limited to read-only observation.", advisor)

    # (9)
    def test_version_1_2_0_changes_only_the_listed_text(self):
        previous = reverse_1_2_0_edits(self.text)
        self.assertEqual(hashlib.sha256(previous.encode("utf-8")).hexdigest(), SKILL_1_1_0_SHA256)
        _, previous_body = parse_frontmatter(previous)
        match = re.search(r"^## 1\. .*?(?=^## 8\. )", previous_body, re.M | re.S)
        assert match is not None
        digest = hashlib.sha256(match.group(0).rstrip("\n").encode("utf-8")).hexdigest()
        self.assertEqual(digest, SECTIONS_1_TO_7_SHA256)
        intro = self.body.split("\n## 1. ", 1)[0]
        self.assertEqual(intro, "\n# Harness bug report\n\n" + INTRO_1_0_0 + INTRO_ADDED_SENTENCE + "\n")

    # (10)
    def test_section_4_names_exactly_the_six_kanban_create_arguments(self):
        filing = section(self.body, 4)
        arguments = filing.split(TEMPLATE_HEADING, 1)[0]
        self.assertEqual(re.findall(r"^- ([a-z_]+): ", arguments, re.M), ARGUMENT_NAMES)
        for line in ("- board: `harness`\n", "- assignee: `harness-worker`\n", WORKSPACE_KIND_ARGUMENT,
                     INITIAL_STATUS_ARGUMENT, "- body: the card body template below, filled in\n",
                     "\nPass no other argument.\n"):
            with self.subTest(line=line):
                self.assertEqual(arguments.count(line), 1)
        # The template subsection is the end of section 4.
        self.assertIn(TEMPLATE_HEADING, filing)
        self.assertTrue(filing.rstrip("\n").endswith("```"))
        self.assertEqual(template(self.text), template(filing))

    # (11)
    def test_template_has_the_header_lines_and_headings_in_order(self):
        lines = template(self.text).split("\n")
        self.assertEqual(lines[:len(HEADER_LINES)], HEADER_LINES)
        self.assertEqual(lines[len(HEADER_LINES)], "")
        self.assertEqual([line for line in lines if line.startswith("#")], HEADINGS)
        positions = [lines.index(heading) for heading in HEADINGS]
        self.assertEqual(positions, sorted(positions))
        self.assertGreater(positions[0], len(HEADER_LINES))
        filled = [line for line in lines if line]
        self.assertEqual(filled[-1], DELIVERABLE)
        self.assertEqual(lines.count(DELIVERABLE), 1)
        self.assertGreater(lines.index(DELIVERABLE), positions[-1])
        for heading, first_line in (("## Tests", FOCUSED_PLACEHOLDER), ("## Deployment", DEPLOYMENT),
                                    ("## Prohibited without separate human authorization", PROHIBITED)):
            with self.subTest(heading=heading):
                self.assertEqual(lines[lines.index(heading) + 1], first_line)
        tests = lines[lines.index("## Tests") + 1:lines.index("## Deployment")]
        self.assertEqual(tests, [FOCUSED_PLACEHOLDER, SUITE_LOOP,
                                 "Every command exits 0, and the loop prints no FAIL line.", ""])
        self.assertIn("Proposal for harness-orchestrator to accept or rewrite:",
                      lines[lines.index("## Proposed change") + 1])

    # (12)
    def test_filled_template_passes_the_harness_card_contract_check(self):
        verifier = load_verifier()
        self.assertEqual(verifier.PROJECT_REPOSITORY_ALLOWLISTS["harness"][0], REPOSITORY)
        body = fill(template(self.text))
        self.assertIn(f"Baseline EXACT {SYNTHETIC_BASELINE}.\n", body)
        self.assertIn("\n## Tests\npython3 tests/test_example.py\n", body)
        for status in sorted(verifier.NEVER_CLAIMED_STATUSES):
            with self.subTest(status=status):
                task = {"id": "t_synthetic", "board": "harness", "body": body, "assignee": "harness-worker",
                        "workspace_kind": "worktree", "workspace_path": REPOSITORY, "status": status,
                        "runs": []}
                errors, output = [], io.StringIO()
                with redirect_stdout(output):
                    verifier.check_isolated_card(errors, task, "Harness", REPOSITORY,
                                                 verifier.HARNESS_ASSIGNEES, "harness-reviewer",
                                                 (verifier.TEST_COMMAND_LINE,))
                    verifier.check_harness_card_contract(errors, [task])
                self.assertEqual(errors, [])
                self.assertNotIn("FAIL", output.getvalue())

    def test_template_without_a_focused_test_or_with_a_scratch_workspace_fails(self):
        verifier = load_verifier()

        def errors_for(body, workspace_kind):
            task = {"id": "t_synthetic", "board": "harness", "body": body, "assignee": "harness-worker",
                    "workspace_kind": workspace_kind, "workspace_path": REPOSITORY, "status": "blocked",
                    "runs": []}
            errors = []
            with redirect_stdout(io.StringIO()):
                verifier.check_harness_card_contract(errors, [task])
            return errors

        prefix = "Harness card contract drift t_synthetic: "
        not_known = fill(template(self.text), focused="Focused test: not known.")
        self.assertEqual(errors_for(not_known, "worktree"), [prefix + "explicit test contract missing"])
        self.assertEqual(errors_for(fill(template(self.text)), "scratch"),
                         [prefix + "isolated worktree mismatch"])

    # (13)
    def test_template_tests_section_names_no_pytest(self):
        tests = load_verifier().project_card_test_section(fill(template(self.text)))
        self.assertTrue(tests.startswith("python3 tests/test_example.py\n"))
        self.assertNotIn("pytest", tests.lower())
        self.assertNotIn("pytest", template(self.text).lower())
        filing = section(self.body, 4)
        self.assertIn("pytest is not installed in the harness repository, so never write `pytest` or "
                      "`python3 -m pytest`.", filing)
        self.assertIn("each a command that starts with `python3 tests/`", filing)

    # (14)
    def test_baseline_command_is_the_only_read_in_the_harness_repository(self):
        filing = section(self.body, 4)
        self.assertIn("- `<40-hex>`: the output of `git -C /Users/chanbla11mit/hermes-local-harness rev-parse "
                      "main`. This command only reads the repository, and it is the only command that you run "
                      "in that repository.", filing)
        self.assertEqual(re.findall(r"`git [^`]*`", self.text),
                         ["`git -C /Users/chanbla11mit/hermes-local-harness rev-parse main`"])

    # (15)
    def test_section_7_states_the_release_by_harness_orchestrator(self):
        release = section(self.body, 7)
        self.assertEqual(release.count(SECTION_7_ADDED), 1)
        self.assertTrue(release.rstrip("\n").endswith(SECTION_7_ADDED.rstrip("\n")))


if __name__ == "__main__":
    unittest.main()
