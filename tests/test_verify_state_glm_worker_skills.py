#!/usr/bin/env python3
"""Card t_c8c6860f: the GLM workers appear in the shared skill deploy lists, and
scripts/verify-state checks both the deployed copies and the declaration itself.

(a) the unchanged clean fixture passes;
(b) a run-time copy of the clean fixture with one GLM worker's skill_files entry
    removed fails with exactly the deployed-copy-missing line;
(c) a run-time copy with one changed hash fails with exactly the hash-mismatch line;
(d) the declaration rule prints exactly its line when a GLM worker is removed from
    one deploy_profiles list, and when a GLM worker is in a list that does not have
    the Claude worker 1 of the same board.

The changed snapshot of case (d) reaches the verifier through unittest.mock.patch
on the loaded verifier module, the method the existing tests use. The main() runs
need no LocalReads guard here: every fixture-mode code path that this file changes
is exercised under that guard by tests/test_verify_fixture_isolation.py and
tests/test_verify_state_derived_expectations.py, which fail under /usr/bin/python3
3.9 for a reason that predates this card (the guard rejects the opener argument of
that Python version's pathlib); this file must pass under both interpreters.
"""
from contextlib import redirect_stdout
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT, load_verifier

SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
ROSTER = ROOT / "roster.yaml"
CLEAN = ROOT / "tests/fixtures/clean.yaml"
SKILL = "minimal-implementation"
GLM_WORKER = "harness-worker-glm-1"
FILE = "SKILL.md"


def fail_lines(output):
    return {line[len("FAIL: "):] for line in output.splitlines() if line.startswith("FAIL: ")}


def run_fixture(fixture, snapshot=None):
    """(exit code, output) of the real verify-state in fixture mode over a run-time
    observation; a non-None snapshot replaces the tracked snapshot for the run."""
    verifier = load_verifier()
    real_load = verifier.load

    def patched_load(path_argument):
        if snapshot is not None and str(path_argument) == str(SNAPSHOT):
            return snapshot
        return real_load(path_argument)

    output = io.StringIO()
    argv = ["TEST-ONLY", "--fixture", str(fixture)]
    with patch.object(verifier, "load", patched_load), \
            patch.object(sys, "argv", argv), redirect_stdout(output):
        code = verifier.main()
    return code, output.getvalue()


def with_clean(mutate):
    clean = json.loads(CLEAN.read_text())
    mutate(clean)
    return clean


class GLMWorkerSkillDeployment(unittest.TestCase):
    def test_clean_fixture_passes(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/verify-state"), "--fixture", str(CLEAN)],
                                cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "OK: desired state matches observed state")

    def test_removed_glm_worker_skill_entry_fails_with_the_exact_line(self):
        fixture = with_clean(lambda clean: clean["skill_files"][SKILL].pop(GLM_WORKER))
        with tempfile.TemporaryDirectory(prefix="glm-worker-skills-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            code, output = run_fixture(path)
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), {f"deployed skill copy missing: {SKILL} {GLM_WORKER}"})

    def test_changed_glm_worker_skill_hash_fails_with_the_exact_line(self):
        def mutate(clean):
            clean["skill_files"][SKILL][GLM_WORKER][FILE] = "0" * 64
        fixture = with_clean(mutate)
        with tempfile.TemporaryDirectory(prefix="glm-worker-skills-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            code, output = run_fixture(path)
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), {f"deployed skill hash mismatch: {SKILL} {GLM_WORKER}/{FILE}"})

    def test_declaration_rule_reports_a_glm_worker_removed_from_a_list(self):
        snapshot = json.loads(SNAPSHOT.read_text())
        entry = next(e for e in snapshot["skill"]["shared_skills"] if e["name"] == SKILL)
        entry["deploy_profiles"].remove(GLM_WORKER)

        def mutate(clean):  # the observed copy goes with the declaration
            clean["skill_files"][SKILL].pop(GLM_WORKER)
        fixture = with_clean(mutate)
        with tempfile.TemporaryDirectory(prefix="glm-worker-skills-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            code, output = run_fixture(path, snapshot)
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output),
                         {f"GLM worker missing from shared skill deploy_profiles: {SKILL} {GLM_WORKER}"})

    def test_declaration_rule_reports_a_glm_worker_without_the_claude_worker_1(self):
        # production-deployment lists no anki profile; adding one GLM worker of that
        # board to the list must fail on the declaration alone.
        snapshot = json.loads(SNAPSHOT.read_text())
        entry = next(e for e in snapshot["skill"]["shared_skills"]
                     if e["name"] == "production-deployment")
        entry["deploy_profiles"].append("anki-worker-glm-1")

        def mutate(clean):  # the observed copy goes with the declaration
            clean["skill_files"]["production-deployment"]["anki-worker-glm-1"] = {
                rel: "tracked-source" for rel in entry["files"]}
        fixture = with_clean(mutate)
        with tempfile.TemporaryDirectory(prefix="glm-worker-skills-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            code, output = run_fixture(path, snapshot)
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output),
                         {"unexpected GLM worker in shared skill deploy_profiles: "
                          "production-deployment anki-worker-glm-1"})

    def test_declaration_rule_covers_every_board_and_skill_pair(self):
        roster = json.loads(ROSTER.read_text())
        snapshot = json.loads(SNAPSHOT.read_text())
        pairs = set()
        for entry in snapshot["skill"]["shared_skills"]:
            deploy = entry["deploy_profiles"]
            for fleet in roster["project_fleets"].values():
                worker1 = fleet["worker"]
                prefix = worker1[: -len("-worker")]
                for number in (1, 2):
                    profile = f"{prefix}-worker-glm-{number}"
                    if profile in deploy or worker1 in deploy:
                        pairs.add((entry["name"], profile))
        # Every board contributes the two software-development skills for both its GLM
        # workers (2 skills x 10 GLM workers = 20), jobcron/chapt/harness add both
        # deployment skills (2 x 6 = 12) and human-deployment-guide-writing on
        # jobcron/chapt (1 x 4 = 4): 36 (skill, GLM worker) pairs in total.
        self.assertEqual(len(pairs), 36)
        verifier = load_verifier()
        errors = []
        with redirect_stdout(io.StringIO()):
            verifier.check_glm_worker_skill_declarations(errors, snapshot["skill"], roster)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
