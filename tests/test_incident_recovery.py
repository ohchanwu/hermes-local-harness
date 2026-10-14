#!/usr/bin/env python3
"""Synthetic/static contracts and real inert R10 children, NOT model behavior.

Behavioral acceptance additionally needs actual baseline/candidate responses and
independent semantic review. No reference classifier or model answers live here.
"""
import builtins
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import (
    BoundaryError, LocalReads, ROOT,
    exercise, load_verifier, main as fixture_main, matches,
)

CASES = ROOT / "tests/fixtures/incident-recovery-cases.json"
ORACLE = ROOT / "tests/fixtures/incident-recovery-expectations.json"
ACTIVATIONS = ("JOBCRON_TEST_POSTGRES_URL", "SYNTHETIC_BROWSER_OPT_IN", "SYNTHETIC_FIXTURE_OPT_IN")


def inert_child(parent, permitted=()):
    # Selected names come from this inspected synthetic surface, not a global
    # blacklist. Start with synthetic inputs only, never os.environ.copy().
    child = dict(parent)
    for name in ACTIVATIONS:
        child.pop(name, None)
    for name in permitted:
        if name not in ACTIVATIONS:
            raise ValueError("uninspected activation")
        if name in parent:
            child[name] = parent[name]
    result = subprocess.run(
        [sys.executable, "-I", "-c",
         "import json,os; print(json.dumps(sorted(k for k in os.environ if k in " + repr(ACTIVATIONS) + ")))"],
        cwd=ROOT, env=child, capture_output=True, text=True, timeout=10, check=True,
    )
    return json.loads(result.stdout)


class IncidentRecoveryTests(unittest.TestCase):
    def test_scenario_completeness_and_oracle_separation(self):
        inputs = json.loads(CASES.read_text())
        expected = json.loads(ORACLE.read_text())["expectations"]
        ids = [case["id"] for case in inputs["cases"]]
        self.assertEqual(set(ids), {"R1", "R2", "R3-project", "R3-credential", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "authority-precedence"})
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(expected))
        for case in inputs["cases"]:
            self.assertEqual(set(case) - {"profile_contract"}, {"id", "actor_state", "authority", "dependency", "evidence"})
            self.assertTrue(all(isinstance(value, str) and value for value in case.values()))
        text = CASES.read_text()
        for forbidden in ("/Users/", "postgres://", "https://", "expected_actions", "expectations"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(len(inputs["policy_sources"]), 4)
        self.assertTrue(all((ROOT / path).is_file() for path in inputs["policy_sources"]))
        self.assertIn("infrastructure_retries 1", inputs["common"]["repair_history"])

    def test_decision_point_policy_and_retained_gates(self):
        inputs = json.loads(CASES.read_text())
        for path in inputs["policy_sources"]:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                section = text.split("## Incident recovery", 1)[1].split("\n## ", 1)[0]
                for clause in ("Contain", "diagnosis, remediation, and independent implementation",
                               "actor, target, effects, access, authority, and dependencies",
                               "smallest useful", "same card", "pending semantic attempt",
                               "infrastructure retry", "unknown", "historical impact",
                               "profile prohibition", "User stop remains global", "delayed callbacks",
                               "concrete dependency", "explicitly remove"):
                    self.assertIn(clause, section)
                if path.endswith("SKILL.md"):
                    self.assertLess(text.index("## Incident recovery"), text.index("## Worker Contract") if "## Worker Contract" in text else text.index("## Review and Integration"))

    def test_r10_absent_and_contaminated_parent(self):
        parent = {name: "inert-synthetic-marker" for name in ACTIVATIONS}
        observations = {
            "absent": inert_child({}),
            "broad": inert_child(parent),
            "targeted-db": inert_child(parent, (ACTIVATIONS[0],)),
            "targeted-browser": inert_child(parent, (ACTIVATIONS[1],)),
        }
        self.assertEqual(observations["absent"], [])
        self.assertEqual(observations["broad"], [])
        self.assertEqual(set(parent), set(ACTIVATIONS))
        self.assertEqual(observations["targeted-db"], [ACTIVATIONS[0]])
        self.assertEqual(observations["targeted-browser"], [ACTIVATIONS[1]])
        with self.assertRaises(ValueError):
            inert_child(parent, ("UNINSPECTED_OPT_IN",))
        print("R10 observed: " + json.dumps(observations, sort_keys=True))

    def test_exact_fixture_results(self):
        for name in ("clean.yaml", "incomplete-empty.yaml", "deployed-skill-divergence.yaml"):
            actual_name, code, output = exercise(ROOT / "tests/fixtures" / name)
            self.assertTrue(matches(actual_name, code, output), (name, code, output))

    def test_wrapper_fails_closed(self):
        self.assertFalse(matches("clean.yaml", 1, "OK: desired state matches observed state"))
        self.assertFalse(matches("clean.yaml", 0, "OK: desired state matches observed state\nFAIL: surprise"))
        self.assertFalse(matches("clean.yaml", False, "OK: desired state matches observed state"))
        self.assertFalse(matches("incomplete-empty.yaml", 0, "incomplete fixture"))
        self.assertFalse(matches("incomplete-empty.yaml", 1, "unrelated failure"))
        self.assertFalse(matches("deployed-skill-divergence.yaml", 2, "deployed skill hash mismatch"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(fixture_main([]), 2)
            self.assertEqual(fixture_main(["../foreign.yaml"]), 2)
            with patch("incident_recovery_verify_fixture.exercise", side_effect=BoundaryError("escaped")):
                self.assertEqual(fixture_main([str(ROOT / "tests/fixtures/clean.yaml")]), 2)

    def test_resource_fence(self):
        # No foreign access actually occurs: all negatives must fail before I/O.
        with LocalReads():
            self.assertTrue(CASES.read_text())
            for operation in (lambda: Path("/synthetic-foreign/resource").is_file(),
                              lambda: Path("/synthetic-foreign/resource").read_text(),
                              lambda: builtins.open(CASES, "w"),
                              lambda: os.open(CASES, os.O_WRONLY),
                              lambda: subprocess.run([sys.executable, "-V"])):
                with self.assertRaises(BoundaryError):
                    operation()

    def test_production_policy_fixture_negative_control(self):
        verifier = load_verifier()
        expected = json.loads((ROOT / "roster.yaml").read_text())["repository_policies"]
        errors = []
        with LocalReads(), redirect_stdout(io.StringIO()):
            verifier.check_repository_policies(errors, expected,
                                               {"cha-pt-frontend": "0" * 64}, live=False)
        self.assertEqual(errors, ["repository policy drift cha-pt-frontend"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
