#!/usr/bin/env python3
"""Wording in the production-deployment-planning skill (t_0278275a).

Offline checks of tracked bytes only: no live ~/.hermes reads, board access,
network or model calls. The baseline bytes are read with `git show` from the
repository that contains this file.

The coined term "value-blind" must not appear in any file of the skill. Every
line of SKILL.md that did not contain the term at the baseline must still be
present, unchanged and at the same line number. REWRITES lists the exact
(old, new) text this card changed, so the baseline bytes can be recovered from
the current bytes and compared.
"""
import re
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "129dd8a6297ebf8af58564ed0c78e01eb488b53c"
SKILL_DIR = "skills/devops/production-deployment-planning"
Q = f"{SKILL_DIR}/SKILL.md"
FORBIDDEN = re.compile(r"[Vv]alue-blind")

REWRITES = (
    ("Reproduce the rejection with a value-blind predicate,",
     "Reproduce the rejection with a predicate that reveals no secret or identifying values,"),
    ("Keep this integration run value-blind: report predicates,",
     "Limit the output of this integration run: report predicates,"),
    ("produce a human-readable value-blind structural diff,",
     "produce a human-readable structural diff that contains no secret or identifying values,"),
    ("independently review the value-blind design;",
     "independently review the design, under which no secret or identifying values are revealed;"),
    ("Report only fixed status tokens and value-blind counts;",
     "Report only fixed status tokens and counts that reveal no secret or identifying values;"),
)


def baseline_text(path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{path}"],
                          check=True, capture_output=True, text=True).stdout


class ProductionDeploymentPlanningTerminologyTests(unittest.TestCase):
    def test_no_coined_term_in_any_skill_file(self):
        files = sorted(p for p in (ROOT / SKILL_DIR).rglob("*") if p.is_file())
        self.assertIn(ROOT / Q, files)
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text()
                hits = [(number, line[:120]) for number, line in enumerate(text.splitlines(), 1)
                        if FORBIDDEN.search(line)]
                self.assertEqual(hits, [])

    def test_lines_without_the_term_at_the_baseline_are_unchanged(self):
        baseline_lines = baseline_text(Q).splitlines()
        current_lines = (ROOT / Q).read_text().splitlines()
        self.assertEqual(len(current_lines), len(baseline_lines))
        rewritten = 0
        for number, (old, new) in enumerate(zip(baseline_lines, current_lines), 1):
            if FORBIDDEN.search(old):
                rewritten += 1
                continue
            with self.subTest(line=number):
                self.assertEqual(new, old)
        self.assertEqual(rewritten, len(REWRITES))

    def test_reversing_the_rewrites_recovers_the_baseline(self):
        # Proves that no text other than the listed phrases changed.
        text = (ROOT / Q).read_text()
        for old, new in REWRITES:
            with self.subTest(new=new[:60]):
                self.assertEqual(text.count(new), 1)
            text = text.replace(new, old, 1)
        self.assertEqual(text, baseline_text(Q))


if __name__ == "__main__":
    unittest.main(verbosity=2)
