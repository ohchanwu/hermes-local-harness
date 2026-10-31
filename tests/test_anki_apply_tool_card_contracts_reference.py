#!/usr/bin/env python3
"""The anki-orchestrator reference file references/apply-tool-card-contracts.md (t_c9d4d5c8).

anki-orchestrator wrote this file into its live skill tree on 2026-10-30; this
card adopts it byte for byte as a tracked profile-local override and names it
in the "## Card Contract" section of the anki orchestrator skill.

Offline checks of tracked bytes and fixture-mode verify-state only: no live
~/.hermes reads, board access, network or model calls. The fixture-mode run
writes its observation into a TemporaryDirectory.

APPLY_TOOL_REFERENCE_EDITS lists the exact (new, old) text this card changed in
the anki skill file, so tests that pin older bytes of that file can reverse the
change byte for byte with reverse_apply_tool_reference_edits(). This module
imports no other test module, so any test module can import it.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "anki-orchestrator"
SKILL_DIR = "autonomous-ai-agents/multi-agent-coding-orchestrator"
SKILL_RELATIVE = f"{SKILL_DIR}/SKILL.md"
REFERENCE_RELATIVE = f"{SKILL_DIR}/references/apply-tool-card-contracts.md"
ANKI = f"policies/profile-skills/{PROFILE}/{SKILL_RELATIVE}"
REFERENCE = ROOT / "policies/profile-skills" / PROFILE / REFERENCE_RELATIVE
# sha256 and size of the live file that anki-orchestrator wrote on 2026-10-30.
REFERENCE_SHA256 = "ce8a2f5b8aae6300815ed7172129d24fd01f1249c78a3e63089ffa8f6d05fdc2"
REFERENCE_SIZE = 2039
TRACKED_SOURCE = "tracked-source"

POINTER = ("For a card that extends `scripts/apply_changeset.py` (a new AnkiConnect action or a new change set "
           "entry type), read `references/apply-tool-card-contracts.md` and write the exceptions it lists into "
           "the card body before dispatch.\n")

# Bytes of the anki skill file at baseline 80521880b12bdba5686b0b1970378a6c99713522,
# recovered by reversing APPLY_TOOL_REFERENCE_EDITS.
PRE_APPLY_TOOL_REFERENCE_SHA256 = {
    ANKI: "7abca5932f5672bd9e5708eea1f08d3576fe6a2fbb9abbb9c27d5bb490c0e944",
}

# File -> ((new text, old text), ...). Each new text occurs exactly once.
# The pointer paragraph is the last paragraph of "## Card Contract".
APPLY_TOOL_REFERENCE_EDITS = {
    ANKI: (("\n" + POINTER + "\n## Card Setup\n", "\n## Card Setup\n"),),
}


def reverse_apply_tool_reference_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in APPLY_TOOL_REFERENCE_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def card_contract_section(text):
    match = re.search(r"^## Card Contract\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "## Card Contract"
    return match.group(0)


def verify(fixture):
    """(exit code, FAIL lines, output) of `python3 scripts/verify-state --fixture <fixture>`."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "scripts/verify-state", "--fixture", str(fixture)], cwd=ROOT,
                            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.returncode, [line for line in result.stdout.splitlines() if line.startswith("FAIL")], result.stdout


class TrackedReferenceFile(unittest.TestCase):
    def test_reference_file_has_the_live_bytes(self):
        self.assertTrue(REFERENCE.is_file())
        self.assertFalse(REFERENCE.is_symlink())
        data = REFERENCE.read_bytes()
        self.assertEqual(len(data), REFERENCE_SIZE)
        self.assertEqual(hashlib.sha256(data).hexdigest(), REFERENCE_SHA256)

    def test_reference_file_is_declared_tracked_source(self):
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())
        overrides = snapshot["skill"]["profile_local_skill_overrides"][PROFILE]
        self.assertEqual(overrides, {SKILL_RELATIVE: TRACKED_SOURCE, REFERENCE_RELATIVE: TRACKED_SOURCE})

    def test_clean_fixture_carries_the_reference_file(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        self.assertEqual(clean["profile_local_skill_overrides"][PROFILE][REFERENCE_RELATIVE], TRACKED_SOURCE)
        deployed = clean["skill_files"]["multi-agent-coding-orchestrator"][PROFILE]
        self.assertEqual(deployed["references/apply-tool-card-contracts.md"], TRACKED_SOURCE)

    def test_changed_reference_bytes_are_red_in_fixture_mode(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        code, fails, output = verify(ROOT / "tests/fixtures/clean.yaml")
        self.assertEqual((code, fails), (0, []), output)
        clean["profile_local_skill_overrides"][PROFILE][REFERENCE_RELATIVE] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="anki-apply-tool-reference-") as directory:
            observation = Path(directory) / "observation.yaml"
            observation.write_text(json.dumps(clean))
            code, fails, output = verify(observation)
        self.assertEqual(code, 1, output)
        self.assertIn(f"FAIL: profile-local skill override drift: {PROFILE}/{REFERENCE_RELATIVE}", fails)


class CardContractPointer(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ANKI).read_text()

    def test_card_contract_section_names_the_reference_file(self):
        section = card_contract_section(self.text)
        self.assertIn("`references/apply-tool-card-contracts.md`", section)
        self.assertTrue(section.endswith("\n" + POINTER + "\n"), section[-400:])
        self.assertEqual(self.text.count("references/apply-tool-card-contracts.md"), 1)

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in PRE_APPLY_TOOL_REFERENCE_SHA256.items():
            with self.subTest(path=path):
                original = reverse_apply_tool_reference_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_new_text_is_ascii_and_uses_no_coined_compound(self):
        POINTER.encode("ascii")
        self.assertIsNone(re.search(r"[Vv]alue-blind|citation-gated", POINTER))


if __name__ == "__main__":
    unittest.main(verbosity=2)
