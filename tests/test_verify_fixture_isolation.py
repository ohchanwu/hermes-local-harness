#!/usr/bin/env python3
"""Exercise real fixture main() under pre-I/O guards; live checks use owned files."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import BoundaryError, LocalReads, ROOT, load_verifier


class ObservedReads(LocalReads):
    def __init__(self, extra_paths=()):
        super().__init__()
        self.allowed.update(os.path.abspath(os.fspath(path)) for path in extra_paths)
        self.attempts = []

    def check(self, path):
        self.attempts.append(os.path.abspath(os.fsdecode(path)) if not isinstance(path, int) else path)
        super().check(path)


def fixture_result(path):
    verifier = load_verifier()
    output = io.StringIO()
    guard = ObservedReads((path,))
    with guard, patch.object(sys, "argv", ["verify-state", "--fixture", str(path)]), redirect_stdout(output):
        code = verifier.main()
    return code, output.getvalue(), guard


class FixtureIsolationTests(unittest.TestCase):
    def test_clean_fixture_uses_real_main_without_foreign_observation(self):
        path = ROOT / "tests/fixtures/clean.yaml"
        code, output, guard = fixture_result(path)
        self.assertEqual(code, 0, output)
        self.assertIn("OK: desired state matches observed state", output)
        self.assertNotIn("FAIL:", output)
        self.assertIn(str(path), guard.attempts)
        self.assertIn(str(ROOT / "roster.yaml"), guard.attempts)
        self.assertIn(str(ROOT / "snapshots/sanitized-current-state.yaml"), guard.attempts)
        self.assertTrue(guard.attempts)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_existing_negative_fixtures_remain_red(self):
        for name, diagnostic in (
                ("incomplete-empty.yaml", "incomplete fixture"),
                ("deployed-skill-divergence.yaml", "deployed skill hash mismatch")):
            with self.subTest(name=name):
                code, output, _ = fixture_result(ROOT / "tests/fixtures" / name)
                self.assertEqual(code, 1, output)
                self.assertIn(diagnostic, output)
                self.assertNotIn("OK: desired state matches observed state", output)

    def test_missing_and_malformed_fixture_inputs(self):
        # An explicitly empty path is still fixture mode, never a live fallback.
        code, output, _ = fixture_result("")
        self.assertEqual(code, 2, output)
        self.assertIn("malformed fixture", output)
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            code, output, _ = fixture_result(path)
            self.assertEqual(code, 2, output)
            self.assertIn("malformed fixture", output)
            for content in ("{not JSON", "null", "[]", '"not a mapping"'):
                with self.subTest(content=content):
                    path.write_text(content)
                    code, output, _ = fixture_result(path)
                    self.assertEqual(code, 2, output)
                    self.assertIn("malformed fixture", output)

    def test_policy_observations_fail_closed_without_falling_back_to_live(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            for observation, diagnostic in (
                    ({}, "repository policy drift"),
                    ({"cha-pt-frontend": "0" * 64}, "repository policy drift"),
                    ([], "repository policy observed state malformed"),
                    (None, "repository policy observed state malformed"),
                    ({**clean["repository_policy_hashes"], "unknown": "0" * 64},
                     "unexpected repository policy observation")):
                with self.subTest(observation=observation):
                    fixture = {**clean, "repository_policy_hashes": observation}
                    path.write_text(json.dumps(fixture))
                    code, output, _ = fixture_result(path)
                    self.assertEqual(code, 1, output)
                    self.assertIn(diagnostic, output)
            fixture = dict(clean)
            del fixture["repository_policy_hashes"]
            path.write_text(json.dumps(fixture))
            code, output, _ = fixture_result(path)
            self.assertEqual(code, 1, output)
            self.assertIn("missing required section 'repository_policy_hashes'", output)

    def test_malformed_observation_sections_never_select_live_or_skip_checks(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            for section, wrong_container in (
                    ("adapters", {}), ("skill_files", []),
                    ("profile_soul_hashes", []), ("profile_local_skill_overrides", []),
                    ("project_isolation", []), ("project_repair_policy", [])):
                for observation in (None, wrong_container, "not an observation", False, 1):
                    with self.subTest(section=section, observation=observation):
                        path.write_text(json.dumps({**clean, section: observation}))
                        code, output, guard = fixture_result(path)
                        self.assertEqual(code, 2, output)
                        self.assertIn(f"malformed fixture: section '{section}'", output)
                        self.assertNotIn("OK: desired state matches observed state", output)
                        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_adapter_entries_must_be_observation_mappings(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            for entry in (None, [], "not an adapter", False, 1):
                with self.subTest(entry=entry):
                    path.write_text(json.dumps({**clean, "adapters": [entry]}))
                    code, output, _ = fixture_result(path)
                    self.assertEqual(code, 2, output)
                    self.assertIn("malformed fixture: section 'adapters'", output)

    def test_missing_and_empty_observation_sections_remain_incomplete(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            for section in ("adapters", "skill_files", "profile_soul_hashes",
                            "profile_local_skill_overrides", "project_isolation",
                            "project_repair_policy"):
                with self.subTest(section=section, observation="missing"):
                    fixture = dict(clean)
                    del fixture[section]
                    path.write_text(json.dumps(fixture))
                    code, output, _ = fixture_result(path)
                    self.assertEqual(code, 1, output)
                    self.assertIn(f"missing required section '{section}'", output)
                with self.subTest(section=section, observation="empty"):
                    path.write_text(json.dumps({**clean, section: [] if section == "adapters" else {}}))
                    code, output, _ = fixture_result(path)
                    self.assertEqual(code, 1, output)
                    self.assertNotIn("OK: desired state matches observed state", output)

    def test_project_helpers_preserve_desired_only_validation(self):
        verifier = load_verifier()
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())
        for check, section, diagnostic in (
                (verifier.check_project_isolation, "project_isolation", "project isolation mapping"),
                (verifier.check_project_repair_policy, "project_repair_policy", "project repair policy desired")):
            with self.subTest(section=section), ObservedReads(), redirect_stdout(io.StringIO()):
                errors = []
                check(errors, snapshot[section])
                self.assertEqual(errors, [])
                check(errors, {}, None)
                self.assertTrue(any(diagnostic in error for error in errors), errors)

    def test_required_section_null_sweep_has_no_false_ok_or_live_fallback(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        results = {}
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-") as directory:
            path = Path(directory) / "observation.yaml"
            for section in (
                    "profile_models", "profile_providers", "profile_approval_modes", "plugins",
                    "dispatch_profiles", "kanban", "skill_files", "profile_local_skill_overrides",
                    "profile_soul_hashes", "repository_policy_hashes", "adapters",
                    "terminal_notification_runtime", "terminal_retry_policy", "project_isolation",
                    "project_repair_policy", "project_repair_cards"):
                with self.subTest(section=section):
                    self.assertIn(section, clean)
                    path.write_text(json.dumps({**clean, section: None}))
                    verifier = load_verifier()
                    output = io.StringIO()
                    guard = ObservedReads((path,))
                    with guard, patch.object(sys, "argv", ["verify-state", "--fixture", str(path)]), redirect_stdout(output):
                        try:
                            code = verifier.main()
                        except (TypeError, AttributeError) as exc:
                            # Existing malformed-input crashes fail, but are not graceful
                            # diagnostics. Record honestly; general schema hardening is not
                            # this sentinel-isolation contract. BoundaryError is NOT caught.
                            results[section] = {"exception": type(exc).__name__}
                        else:
                            results[section] = {"verifier_exit": code}
                            self.assertIn(code, (1, 2), output.getvalue())
                    self.assertNotIn("OK: desired state matches observed state", output.getvalue())
                    self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))
        print("Required-section null sweep observed: " + json.dumps(results, sort_keys=True))

    def test_guard_rejects_foreign_metadata_reads_commands_and_network_before_io(self):
        path = Path("/synthetic-foreign/never-accessed")
        with ObservedReads():
            for operation in (
                    lambda: path.is_file(), lambda: path.read_text(),
                    lambda: os.stat(path), lambda: os.access(path, os.R_OK),
                    lambda: subprocess.run([sys.executable, "-V"]),
                    lambda: socket.socket(),
                    lambda: socket.getaddrinfo("synthetic.invalid", 443)):
                with self.subTest(operation=operation), self.assertRaises(BoundaryError):
                    operation()


class SyntheticLivePolicyTests(unittest.TestCase):
    def test_live_file_hash_and_required_markers(self):
        verifier = load_verifier()
        name = "cha-pt-frontend"  # Declaration key only; path is always owned synthetic input.
        content = "\n".join(verifier.REPOSITORY_POLICY_MARKERS[name]) + "\n"
        with tempfile.TemporaryDirectory(prefix="fixture-isolation-live-") as directory:
            path = Path(directory) / "AGENTS.md"
            desired = {name: {"path": str(path), "sha256": hashlib.sha256(content.encode()).hexdigest()}}

            def check():
                errors = []
                guard = ObservedReads((path,))
                with guard, patch.dict(verifier.REPOSITORY_POLICY_PATHS, {name: str(path)}, clear=True), \
                        redirect_stdout(io.StringIO()):
                    verifier.check_repository_policies(errors, desired)
                self.assertIn(str(path), guard.attempts)
                return errors

            self.assertTrue(any("repository policy missing" in error for error in check()))
            path.write_text(content)
            self.assertEqual(check(), [])
            path.write_text(content + "changed\n")
            self.assertEqual(check(), [f"repository policy drift {name}"])
            path.write_text("synthetic policy without markers\n")
            desired[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            errors = check()
            self.assertEqual(len(errors), len(verifier.REPOSITORY_POLICY_MARKERS[name]))
            self.assertTrue(all("repository policy marker missing" in error for error in errors))

    def test_fixture_comparison_still_validates_desired_path_and_hash(self):
        verifier = load_verifier()
        desired = json.loads((ROOT / "roster.yaml").read_text())["repository_policies"]
        for change, diagnostic in (
                ({"path": "/synthetic-foreign/unexpected"}, "repository policy path drift"),
                ({"sha256": "not-a-sha"}, "repository policy mapping malformed")):
            with self.subTest(change=change):
                changed = {name: {**entry, **change} for name, entry in desired.items()}
                errors = []
                with ObservedReads(), redirect_stdout(io.StringIO()):
                    verifier.check_repository_policies(errors, changed, {}, live=False)
                self.assertTrue(any(diagnostic in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
