#!/usr/bin/env python3
"""The jobcron-orchestrator production-deployment skill is a tracked profile-local override (t_a65417ef).

The override is a three-way merge of the shared skill at 774ec80 (base), the
shared skill on main (version 0.2.5) and the live jobcron-orchestrator copy,
which carries operator lessons that exist only there. These checks read only
tracked repository files; they read nothing under ~/.hermes and use no network.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
PROFILE = "jobcron-orchestrator"
OVERRIDE_ROOT = ROOT / "policies/profile-skills" / PROFILE
SKILL = "devops/production-deployment/SKILL.md"
REFERENCE = "devops/production-deployment/references/release-ci-portability.md"
SHARED_SKILL = ROOT / "skills/devops/production-deployment/SKILL.md"
SHARED_REFERENCE = ROOT / "skills/devops/production-deployment/references/release-ci-portability.md"


class JobcronProductionDeploymentOverride(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overrides = json.loads(SNAPSHOT.read_text())["skill"]["profile_local_skill_overrides"]
        cls.skill = (OVERRIDE_ROOT / SKILL).read_text()
        cls.reference = (OVERRIDE_ROOT / REFERENCE).read_text()

    def test_both_files_exist_and_are_declared_tracked_source(self):
        for path in (SKILL, REFERENCE):
            with self.subTest(path=path):
                self.assertTrue((OVERRIDE_ROOT / path).is_file())
                self.assertFalse((OVERRIDE_ROOT / path).is_symlink())
                self.assertEqual(self.overrides[PROFILE][path], "tracked-source")

    def test_skill_override_version(self):
        self.assertIn("\nversion: 0.2.5-jobcron.1\n", self.skill)

    def test_skill_override_keeps_tracked_side_changes(self):
        for marker in ("## Release change selection", "application-only"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.skill)
        # Every line of the shared 0.2.5 source except its version line is kept, either
        # unchanged or as the start of a line to which the live side appended sentences
        # (for example step 3 of the first-launch sequence).
        override_lines = self.skill.splitlines()
        missing = [line for line in SHARED_SKILL.read_text().splitlines()
                   if not line.startswith("version: ")
                   and not any(other == line or (line and other.startswith(line + " "))
                               for other in override_lines)]
        self.assertEqual(missing, [])

    def test_skill_override_keeps_live_side_lessons(self):
        for marker in ("cmd/jobcron-user", "--pull=never"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.skill)

    def test_reference_override_keeps_both_sides(self):
        for heading in ("## Database timestamp precision", "## Evidence custody versus test-child permissions"):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.reference)
        override_lines = set(self.reference.splitlines())
        missing = [line for line in SHARED_REFERENCE.read_text().splitlines() if line not in override_lines]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
