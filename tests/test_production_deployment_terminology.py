#!/usr/bin/env python3
"""Wording in the production-deployment skill and the Jobcron override (t_36e8bf0c).

Offline checks of tracked bytes only: no live ~/.hermes reads, board access,
network or model calls. The baseline bytes are read with `git show` from the
repository that contains this file.

The coined term "value-blind" must not appear in the shared skill, its
live-state reference, the Jobcron override or either release-ci-portability.md
copy. REWRITES lists the exact (old, new) text this card changed, so the
baseline bytes can be recovered from the current bytes and compared.
"""
import re
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "bcf811b63da0393484b4a4403eb9ae4e1e7286c0"
P = "skills/devops/production-deployment/SKILL.md"
R = "skills/devops/production-deployment/references/live-state-reconciliation.md"
O = "policies/profile-skills/jobcron-orchestrator/devops/production-deployment/SKILL.md"
CHECKED = (
    P, R, O,
    "skills/devops/production-deployment/references/release-ci-portability.md",
    "policies/profile-skills/jobcron-orchestrator/devops/production-deployment/references/release-ci-portability.md",
)
FORBIDDEN = re.compile(r"[Vv]alue-blind")

# (old text, new text) for sentences that occur in both P and O.
SHARED_REWRITES = (
    ("Keep value-blind acquisition audit events,",
     "Keep acquisition audit events that record no secret or identifying values,"),
    ("Identify the dependent credential/capability sequence value-blind before requesting an execution window",
     "Identify the dependent credential/capability sequence, recording no secret or identifying values, "
     "before requesting an execution window"),
    ("the agent validates repository state, plans, value-blind evidence, and ordered gates.",
     "the agent validates repository state, plans, evidence that contains no secret or identifying values, "
     "and ordered gates."),
    ("Ask the operator for necessary value-blind confirmations such as correct account/region,",
     "Ask the operator for necessary confirmations that do not reveal secret or identifying values, "
     "such as correct account/region,"),
    ("Verify automatic lock cleanup value-blind against the exact lock object;",
     "Verify automatic lock cleanup against the exact lock object without revealing secret or identifying values;"),
    ("keep committed fixtures synthetic and value-blind.",
     "keep committed fixtures synthetic and free of secret or identifying values."),
    ("Keep approved remote diagnostics value-blind and tolerant of expected inactive states",
     "Keep approved remote diagnostics free of secret or identifying values and tolerant of expected inactive states"),
)
REWRITES = {
    P: SHARED_REWRITES,
    O: SHARED_REWRITES + (
        ("Verify the resulting selected identity and relevant capability value-blindly before declaring setup complete.",
         "Verify the resulting selected identity and relevant capability without revealing secret or identifying values "
         "before declaring setup complete."),
    ),
    R: (
        ("Record value-blind facts:", "Record facts that contain no secret or identifying values:"),
        ("Generate a fresh value-blind reconciliation checkpoint for recovery modes.",
         "Generate a fresh reconciliation checkpoint, free of secret or identifying values, for recovery modes."),
        ("Produce a concise value-blind packet containing:",
         "Produce a concise packet free of secret or identifying values, containing:"),
        ("- exact plan digest and value-blind action summary when authorized;",
         "- exact plan digest and action summary free of secret or identifying values when authorized;"),
    ),
}


def baseline_text(path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{path}"],
                          check=True, capture_output=True, text=True).stdout


def reverse_rewrites(path, text):
    for old, new in REWRITES[path]:
        if text.count(new) != 1:
            raise AssertionError(f"{path}: expected one occurrence of {new[:80]!r}")
        text = text.replace(new, old, 1)
    return text


def reverse_rewrites_in_line(line):
    for old, new in SHARED_REWRITES:
        line = line.replace(new, old)
    return line


class ProductionDeploymentTerminologyTests(unittest.TestCase):
    def test_no_coined_term(self):
        for path in CHECKED:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                hits = [(number, line[:120]) for number, line in enumerate(text.splitlines(), 1)
                        if FORBIDDEN.search(line)]
                self.assertEqual(hits, [])

    def test_reversing_the_rewrites_recovers_the_baseline(self):
        # Proves that no text other than the listed phrases changed.
        for path in REWRITES:
            with self.subTest(path=path):
                self.assertEqual(reverse_rewrites(path, (ROOT / path).read_text()), baseline_text(path))

    def test_override_keeps_every_shared_line_it_had_at_the_baseline(self):
        override_lines = set((ROOT / O).read_text().splitlines())
        baseline_override_lines = set(baseline_text(O).splitlines())
        new_texts = [new for _, new in SHARED_REWRITES]
        for line in (ROOT / P).read_text().splitlines():
            if any(new in line for new in new_texts):
                # A rewritten sentence of P stays byte-identical in O when O had the old sentence.
                expected = reverse_rewrites_in_line(line) in baseline_override_lines
            else:
                expected = line in baseline_override_lines
            if expected:
                with self.subTest(line=line[:80]):
                    self.assertIn(line, override_lines)

    def test_every_shared_rewrite_is_in_both_files(self):
        for path in (P, O):
            text = (ROOT / path).read_text()
            for _, new in SHARED_REWRITES:
                with self.subTest(path=path, new=new[:60]):
                    self.assertEqual(text.count(new), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
