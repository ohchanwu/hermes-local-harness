#!/usr/bin/env python3
"""Card contract lines at any line start, Python test commands, and the owner
shell command path rule in the orchestrator skills (t_bd860536).

Offline checks of tracked bytes and of the scripts/verify-state card contract
checks only: no live ~/.hermes reads, board access, network or model calls.
All cards are synthetic.

scripts/verify-state finds the `Repository <path> ONLY`, `Baseline EXACT <40 hex>`
and reviewer lines at the start of any line of the card body, or after
sentence-ending punctuation. TEST_COMMAND_LINE also accepts `python` or
`python3` with interpreter options that take no argument, followed by a check or
test script or by `-m unittest` or `-m pytest`.

OWNER_PATH_EDITS lists the exact (new, old) text this card changed in each skill
file, so tests that pin older bytes of these files can reverse the change byte
for byte with reverse_owner_path_edits().
"""
import hashlib
import io
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from test_anki_apply_tool_card_contracts_reference import reverse_apply_tool_reference_edits
from test_orchestrator_skill_changes_policy import reverse_skill_changes_edits
from test_repair_history_candidate_rules_policy import reverse_candidate_rule_edits

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
HARNESS = f"policies/profile-skills/harness-orchestrator/{RELATIVE}"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
JSS = f"policies/profile-skills/jss-orchestrator/{RELATIVE}"
ANKI = f"policies/profile-skills/anki-orchestrator/{RELATIVE}"
GENERIC_FILES = (SHARED, HARNESS, CHAPT, JSS, ANKI)

JOBCRON_BULLET = (
    "- Shell commands given to the owner to run themselves must use absolute paths (for example "
    "`/Users/<user>/...` and an explicit keychain path), never `~` or `$HOME`. The owner's shell can "
    "inherit `HOME` set to a Hermes profile directory, so `~` resolves to the wrong place and `security` "
    "cannot find the login keychain. Check the exact paths with `stat` before sending the command."
)
GENERIC_BULLET = (
    "- Shell commands given to the owner to run themselves must use absolute paths (for example "
    "`/Users/<user>/...`), never `~` or `$HOME`. The owner's shell can inherit `HOME` set to a Hermes "
    "profile directory, so `~` resolves to the wrong place. Check the exact paths with `stat` before "
    "sending the command."
)
# SHA-256 of the live Jobcron skill: the repository file with its version line
# set back to the live version line.
JOBCRON_LIVE_SHA256 = "7c568f8d025ddd41f7fa0a48723187a98d754df3892cd73cf8f6407121c72b69"
JOBCRON_LIVE_VERSION = "version: 0.6.9-jobcron.5\n"

PITFALLS = "## Pitfalls\n\n"
# A file with no Pitfalls section gets one at the end of the file.
APPENDED_SECTION = "\n" + PITFALLS + GENERIC_BULLET + "\n"


def _version(new, old):
    return (f"version: {new}\n", f"version: {old}\n")


# File -> ((new text, old text), ...). Each new text occurs exactly once.
OWNER_PATH_EDITS = {
    SHARED: (_version("0.6.12", "0.6.11"), (PITFALLS + GENERIC_BULLET + "\n", PITFALLS)),
    JOBCRON: (_version("0.6.9-jobcron.6", "0.6.9-jobcron.5"),
              (PITFALLS + JOBCRON_BULLET + "\n\n", PITFALLS)),
    CHAPT: (_version("0.6.7-chapt.6", "0.6.7-chapt.5"), (PITFALLS + GENERIC_BULLET + "\n", PITFALLS)),
    HARNESS: (_version("0.6.7-harness.5", "0.6.7-harness.4"), (APPENDED_SECTION, "")),
    JSS: (_version("0.6.7-jss.7", "0.6.7-jss.6"), (APPENDED_SECTION, "")),
    ANKI: (_version("0.6.10-anki.3", "0.6.10-anki.2"), (APPENDED_SECTION, "")),
}

# Bytes of each file at baseline 4e1d8464827284e6b32a4041fd92a704d958c105,
# recovered by reversing OWNER_PATH_EDITS.
PRE_OWNER_PATH_SHA256 = {
    SHARED: "63f09638ab7bd3a64ddd7fead65126472f40fca6ede6ca337540bbffec9a3526",
    HARNESS: "3a7dfcd9a9dde18ed3825b8b68741ca3e91bb5269fb2a5a2b59b420712ccb4b2",
    JOBCRON: "197eb3636354c8f58270b4b5a7fe99c1174019aa8581c4bf7cabbfcb58bf7361",
    CHAPT: "d49d65f860e2e2f0b9107bfc294c443917278bffce959695cbe12a470a264d6c",
    JSS: "989a6939f36a32a688672ac4ec50489438c39c27dd29800224893d11be3b1b04",
    ANKI: "45a511e44480898d9cd1cae638f6a6299796bc14bbecf24aef76de1282976da3",
}


def reverse_owner_path_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in OWNER_PATH_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def load_verifier():
    source = ROOT / "scripts/verify-state"
    module = types.ModuleType("verify_state_line_start")
    module.__file__ = str(source)
    exec(compile(source.read_text(), str(source), "exec"), module.__dict__)
    return module


BASELINE = "Baseline EXACT " + "a" * 40
# Each fleet: (check function, board, repository, assignee, reviewer, test command,
# extra body lines the fleet requires, error label).
FLEETS = {
    "cha-pt": ("check_chapt_card_contract", "cha-pt", "/Users/chanbla11mit/projects/cha-pt",
               "chapt-worker", "chapt-reviewer", "go test ./...", "", "Cha PT"),
    "harness": ("check_harness_card_contract", "harness", "/Users/chanbla11mit/hermes-local-harness",
                "harness-worker", "harness-reviewer", "python3 tests/test_x.py", "", "Harness"),
    "jss-genr": ("check_jss_card_contract", "jss-genr", "/Users/chanbla11mit/projects/jss-genr",
                 "jss-worker", "jss-reviewer", "make -C resume qa", "Card kind EXACT repository.\n",
                 "jss-genr"),
    "anki": ("check_anki_card_contract", "anki", "/Users/chanbla11mit/projects/anki",
             "anki-worker", "anki-reviewer", "python3 -m unittest discover -s tests -t . -v", "", "anki"),
}
REPOSITORY_ERRORS = ("expected exact repository", "expected exactly one repository")
BASELINE_ERROR = "exact baseline missing"
REVIEWER_ERROR = "independent review contract missing"


def contract_body(repository_line, baseline_line, reviewer_line, extra, command):
    """Each contract line follows a line that has no final punctuation."""
    return (
        "Card ID: t_synthetic\n"
        f"{repository_line}\n"
        "Scope note without final punctuation\n"
        f"{baseline_line}\n"
        "Assigned worker named below\n"
        f"{reviewer_line}\n"
        f"{extra}"
        "## Tests\n"
        f"- `{command}`\n"
    )


class CardContractLineStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()

    def errors(self, fleet, body):
        check, board, repository, assignee, _reviewer, _command, _extra, _label = FLEETS[fleet]
        task = {"id": "t_synthetic", "board": board, "body": body, "assignee": assignee,
                "workspace_kind": "worktree", "workspace_path": f"{repository}/.worktrees/t_synthetic"}
        errors = []
        with redirect_stdout(io.StringIO()):
            getattr(self.verifier, check)(errors, [task])
        return errors

    def body(self, fleet, repository_line=None, baseline_line=None, reviewer_line=None):
        _check, _board, repository, _assignee, reviewer, command, extra, _label = FLEETS[fleet]
        return contract_body(
            repository_line or f"Repository {repository} ONLY.",
            baseline_line or f"{BASELINE}.",
            reviewer_line or f"Reviewer EXACT {reviewer}.",
            extra, command)

    def assert_error(self, errors, fleet, expected):
        label = FLEETS[fleet][-1]
        wanted = [f"{label} card contract drift t_synthetic: {text}" for text in expected]
        self.assertTrue(any(error in wanted for error in errors), errors)

    def test_lines_after_unpunctuated_lines_pass_for_each_fleet(self):
        for fleet in FLEETS:
            with self.subTest(fleet=fleet):
                self.assertEqual(self.errors(fleet, self.body(fleet)), [])

    def test_each_reviewer_wording_passes_at_a_line_start(self):
        for fleet in FLEETS:
            reviewer = FLEETS[fleet][4]
            for wording in ("Independent reviewer", "Independent reviewer EXACT", "Reviewer EXACT"):
                with self.subTest(fleet=fleet, wording=wording):
                    body = self.body(fleet, reviewer_line=f"{wording} {reviewer}.")
                    self.assertEqual(self.errors(fleet, body), [])

    def test_lines_after_sentence_punctuation_still_pass(self):
        for fleet in FLEETS:
            _check, _board, repository, _assignee, reviewer, command, extra, _label = FLEETS[fleet]
            with self.subTest(fleet=fleet):
                body = (f"Synthetic card. Repository {repository} ONLY. {BASELINE}. "
                        f"Reviewer EXACT {reviewer}.\n{extra}## Tests\n- `{command}`\n")
                if fleet != "cha-pt":
                    # The shared check reads the reviewer line only at a line start.
                    body = body.replace(f" Reviewer EXACT {reviewer}.", f"\nReviewer EXACT {reviewer}.")
                self.assertEqual(self.errors(fleet, body), [])

    def test_lines_mid_sentence_after_unpunctuated_text_still_fail(self):
        for fleet in FLEETS:
            repository, reviewer = FLEETS[fleet][2], FLEETS[fleet][4]
            with self.subTest(fleet=fleet, line="repository"):
                body = self.body(fleet, repository_line=f"see Repository {repository} ONLY.")
                self.assert_error(self.errors(fleet, body), fleet, REPOSITORY_ERRORS)
            with self.subTest(fleet=fleet, line="baseline"):
                body = self.body(fleet, baseline_line=f"see {BASELINE}.")
                self.assert_error(self.errors(fleet, body), fleet, (BASELINE_ERROR,))
            with self.subTest(fleet=fleet, line="reviewer"):
                body = self.body(fleet, reviewer_line=f"see Reviewer EXACT {reviewer}.")
                self.assert_error(self.errors(fleet, body), fleet, (REVIEWER_ERROR,))

    def test_repository_exact_wording_still_fails(self):
        for fleet in FLEETS:
            repository = FLEETS[fleet][2]
            with self.subTest(fleet=fleet):
                body = self.body(fleet, repository_line=f"Repository EXACT {repository}.")
                self.assert_error(self.errors(fleet, body), fleet, REPOSITORY_ERRORS)


class PythonTestCommands(unittest.TestCase):
    ACCEPTED_NEW = (
        "python3 -m unittest discover -s tests -t . -v",
        "python3 -I -m unittest -v",
        "python -m pytest -q",
        "python3 -I tests/test_x.py",
        "python3 -B -I scripts/check-x",
        "python3 -m unittest",
        "python3 -IB -m pytest tests",
        "python3 -OO -bb tests/test_x.py",
    )
    # Forms accepted at the baseline; they stay accepted.
    ACCEPTED_AT_BASELINE = (
        "pytest -q",
        "go test ./...",
        "python3 tests/test_x.py",
        "python tests/test_x.py",
        "python3 scripts/check-x --strict",
        "npm test",
        "npm run lint",
        "pnpm test",
        "yarn run build",
        "node --test",
        "cargo test",
        "make test",
    )
    REJECTED = (
        "python3 -m py_compile x.py",
        "python3 -I -m py_compile x.py",
        "python3 -c 'print(1)'",
        "python3 -m json.tool x",
        "python3 -m unittestx",
        "python3",
        "python3 -I",
        "python3 -X dev tests/test_x.py",
    )

    @classmethod
    def setUpClass(cls):
        cls.pattern = load_verifier().TEST_COMMAND_LINE

    def matches(self, command):
        return {
            "plain": bool(self.pattern.search(command)),
            "bullet": bool(self.pattern.search(f"- {command}")),
            "code": bool(self.pattern.search(f"- `{command}`")),
        }

    def test_new_python_forms_are_accepted(self):
        for command in self.ACCEPTED_NEW:
            with self.subTest(command=command):
                self.assertEqual(set(self.matches(command).values()), {True})

    def test_baseline_forms_stay_accepted(self):
        for command in self.ACCEPTED_AT_BASELINE:
            with self.subTest(command=command):
                self.assertEqual(set(self.matches(command).values()), {True})

    def test_non_test_python_commands_are_rejected(self):
        for command in self.REJECTED:
            with self.subTest(command=command):
                self.assertEqual(set(self.matches(command).values()), {False})


class OwnerShellCommandPaths(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_bytes()

    def test_jobcron_file_with_live_version_has_the_live_hash(self):
        # The live skill predates the later Skill Changes section (t_0a8674fe) and the
        # repair_history candidate rule change (t_6436ac1c), so reverse those changes first.
        data = reverse_skill_changes_edits(JOBCRON, self.read(JOBCRON).decode())
        data = reverse_candidate_rule_edits(JOBCRON, data)
        self.assertEqual(data.count("version: 0.6.9-jobcron.6\n"), 1)
        live = data.replace("version: 0.6.9-jobcron.6\n", JOBCRON_LIVE_VERSION, 1).encode()
        self.assertEqual(hashlib.sha256(live).hexdigest(), JOBCRON_LIVE_SHA256)

    def test_jobcron_bullet_is_the_first_pitfalls_bullet_once(self):
        data = self.read(JOBCRON).decode()
        self.assertEqual(data.count(JOBCRON_BULLET), 1)
        self.assertEqual(data.count("## Pitfalls\n"), 1)
        self.assertIn(PITFALLS + JOBCRON_BULLET + "\n\n- ", data)
        self.assertNotIn(GENERIC_BULLET, data)

    def test_generic_bullet_once_under_a_pitfalls_heading(self):
        for path in GENERIC_FILES:
            with self.subTest(path=path):
                data = self.read(path).decode()
                self.assertEqual(data.count(GENERIC_BULLET), 1)
                self.assertEqual(data.count("## Pitfalls\n"), 1)
                section = data.split("## Pitfalls\n", 1)[1].split("\n## ", 1)[0]
                self.assertIn(GENERIC_BULLET, section)

    def test_bullets_are_ascii(self):
        for bullet in (JOBCRON_BULLET, GENERIC_BULLET):
            bullet.encode("ascii")

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in PRE_OWNER_PATH_SHA256.items():
            with self.subTest(path=path):
                # Reverse the later apply-tool-card-contracts pointer (t_c9d4d5c8), the Skill
                # Changes section (t_0a8674fe) and repair_history candidate rule change
                # (t_6436ac1c) first.
                current = reverse_apply_tool_reference_edits(path, self.read(path))
                current = reverse_skill_changes_edits(path, current)
                current = reverse_candidate_rule_edits(path, current)
                original = reverse_owner_path_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)


if __name__ == "__main__":
    unittest.main()
