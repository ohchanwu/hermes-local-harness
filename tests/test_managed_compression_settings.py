#!/usr/bin/env python3
"""Harness-managed compression settings: roster pins, snapshot mirror, fixtures and verifier check.

Fixture runs go through the real verifier main() under the fixture-isolation guard;
the live path is exercised only with a stubbed command runner (no Hermes, no ~/.hermes).
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT, load_verifier
from test_verify_fixture_isolation import ObservedReads, fixture_result

PROFILES = ["advisor", "jobcron-orchestrator", "chapt-orchestrator", "harness-orchestrator", "default"]
SETTINGS = {
    "compression.threshold_tokens": 150000,
    "compression.proactive_prune_tokens": 100000,
    "compression.min_tail_user_messages": 3,
    "compression.idle_compact_after_seconds": 3600,
}
FIXTURES = ROOT / "tests/fixtures"
# The second managed settings group (t_0a8674fe); tests/test_orchestrator_profile_settings.py
# checks it. Fixtures carry both groups merged per profile.
ORCHESTRATOR_GROUP = json.loads((ROOT / "roster.yaml").read_text())["orchestrator_profile_settings"]
DRIFT_FIXTURES = ("compression-drift.yaml", "orchestrator-skill-settings-drift.yaml")
DRIFT_MESSAGES = [
    "FAIL: managed setting drift advisor compression.threshold_tokens: "
    f"expected {SETTINGS['compression.threshold_tokens']!r}, actual 200000",
    "FAIL: managed setting drift harness-orchestrator compression.idle_compact_after_seconds: "
    f"expected {SETTINGS['compression.idle_compact_after_seconds']!r}, actual <unreadable>",
]


def load_json(rel):
    return json.loads((ROOT / rel).read_text())


def fail_lines(output):
    return [line for line in output.splitlines() if line.startswith("FAIL:")]


class DesiredStateTests(unittest.TestCase):
    def setUp(self):
        self.roster = load_json("roster.yaml")
        self.snapshot = load_json("snapshots/sanitized-current-state.yaml")

    def test_roster_pins_exact_profiles_and_values(self):
        managed = self.roster["managed_profile_settings"]
        self.assertEqual(managed, {"profiles": PROFILES, "settings": SETTINGS})
        for value in managed["settings"].values():
            self.assertIs(type(value), int)
        roster_names = {profile["name"] for profile in self.roster["profiles"]}
        self.assertTrue(set(PROFILES) <= roster_names)

    def test_snapshot_mirrors_roster(self):
        self.assertEqual(self.snapshot["managed_profile_settings"], self.roster["managed_profile_settings"])

    def test_native_settings_unchanged(self):
        self.assertEqual(self.roster["native_settings"],
                         {"kanban.max_in_progress": None, "kanban.max_in_progress_per_profile": 1})


class FixtureConsistencyTests(unittest.TestCase):
    def test_every_fixture_carries_matching_values_except_the_drift_fixture(self):
        expected = {profile: dict(SETTINGS) for profile in PROFILES}
        for profile in ORCHESTRATOR_GROUP["profiles"]:
            expected.setdefault(profile, {}).update(ORCHESTRATOR_GROUP["settings"])
        names = sorted(path.name for path in FIXTURES.glob("*.yaml"))
        self.assertIn("compression-drift.yaml", names)
        for name in names:
            if name == "incomplete-empty.yaml" or name in DRIFT_FIXTURES:
                continue
            with self.subTest(fixture=name):
                fixture = json.loads((FIXTURES / name).read_text())
                self.assertEqual(fixture["profile_managed_settings"], expected)

    def test_drift_fixture_differs_only_in_managed_settings(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        drift = json.loads((FIXTURES / "compression-drift.yaml").read_text())
        managed = drift.pop("profile_managed_settings")
        clean.pop("profile_managed_settings")
        self.assertEqual(drift, clean)
        self.assertEqual(managed["advisor"]["compression.threshold_tokens"], 200000)
        self.assertNotIn("compression.idle_compact_after_seconds", managed["harness-orchestrator"])


class FixtureVerifierTests(unittest.TestCase):
    def assert_isolated(self, guard):
        self.assertTrue(guard.attempts)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_clean_fixture_passes(self):
        code, output, guard = fixture_result(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: desired state matches observed state", output)
        self.assertNotIn("managed setting drift", output)
        self.assert_isolated(guard)

    def test_drift_fixture_goes_red_naming_profile_and_key(self):
        code, output, guard = fixture_result(FIXTURES / "compression-drift.yaml")
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), DRIFT_MESSAGES)
        self.assertNotIn("OK: desired state matches observed state", output)
        self.assert_isolated(guard)

    def test_missing_null_and_malformed_observations_fail_closed(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        with tempfile.TemporaryDirectory(prefix="managed-settings-") as directory:
            path = Path(directory) / "observation.yaml"
            fixture = dict(clean)
            del fixture["profile_managed_settings"]
            path.write_text(json.dumps(fixture))
            code, output, guard = fixture_result(path)
            self.assertEqual(code, 1, output)
            self.assertIn("incomplete fixture: missing required section 'profile_managed_settings'", output)
            self.assert_isolated(guard)
            every_key = (len(PROFILES) * len(SETTINGS)
                         + len(ORCHESTRATOR_GROUP["profiles"]) * len(ORCHESTRATOR_GROUP["settings"]))
            for observation in (None, [], {}, "not a mapping"):
                with self.subTest(observation=observation):
                    path.write_text(json.dumps({**clean, "profile_managed_settings": observation}))
                    code, output, guard = fixture_result(path)
                    self.assertEqual(code, 1, output)
                    unreadable = [line for line in fail_lines(output) if line.endswith("actual <unreadable>")]
                    self.assertEqual(len(unreadable), every_key, output)
                    self.assert_isolated(guard)
            broken = json.loads(json.dumps(clean))
            broken["profile_managed_settings"]["default"] = None
            broken["profile_managed_settings"]["chapt-orchestrator"]["compression.min_tail_user_messages"] = "3"
            path.write_text(json.dumps(broken))
            code, output, _ = fixture_result(path)
            self.assertEqual(code, 1, output)
            failures = fail_lines(output)
            for key in SETTINGS:
                self.assertIn(f"FAIL: managed setting drift default {key}: expected {SETTINGS[key]!r}, "
                              "actual <unreadable>", failures)
            self.assertIn("FAIL: managed setting drift chapt-orchestrator compression.min_tail_user_messages: "
                          f"expected {SETTINGS['compression.min_tail_user_messages']!r}, actual '3'", failures)
            self.assertEqual(len(failures), len(SETTINGS) + 1, output)


class CheckFunctionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.roster_profiles = {profile["name"]: profile for profile in load_json("roster.yaml")["profiles"]}

    def run_check(self, managed, read):
        errors = []
        with ObservedReads(), redirect_stdout(io.StringIO()):
            self.verifier.check_managed_profile_settings(errors, managed, self.roster_profiles, read)
        return errors

    def test_malformed_or_unknown_desired_declaration_fails(self):
        read = lambda profile, key: SETTINGS[key]
        for managed in (None, {}, {"profiles": [], "settings": SETTINGS},
                        {"profiles": PROFILES, "settings": {}},
                        {"profiles": ["default", "default"], "settings": SETTINGS}):
            with self.subTest(managed=managed):
                errors = self.run_check(managed, read)
                self.assertEqual(len(errors), 1)
                self.assertIn("managed profile settings malformed", errors[0])
        errors = self.run_check({"profiles": ["not-a-profile"], "settings": SETTINGS}, read)
        self.assertEqual(errors, ["managed profile settings name unknown roster profile: not-a-profile"])

    def test_live_path_reads_each_key_through_json_config(self):
        managed = load_json("roster.yaml")["managed_profile_settings"]
        calls = []

        def fake_run(*args):
            calls.append(args)
            profile, key = args[2], args[-1]
            if profile == "jobcron-orchestrator" and key == "compression.proactive_prune_tokens":
                return subprocess.CompletedProcess(args, 1, "", "synthetic failure")
            value = 90000 if (profile, key) == ("default", "compression.threshold_tokens") else SETTINGS[key]
            return subprocess.CompletedProcess(args, 0, json.dumps(value), "")

        with patch.dict(self.verifier.__dict__, {"run": fake_run}):
            errors = self.run_check(managed, self.verifier.json_config)
        self.assertEqual(calls, [("hermes", "-p", profile, "config", "get", "--json", key)
                                 for profile in PROFILES for key in SETTINGS])
        self.assertEqual(errors, [
            "managed setting drift jobcron-orchestrator compression.proactive_prune_tokens: "
            f"expected {SETTINGS['compression.proactive_prune_tokens']!r}, actual <unreadable>",
            "managed setting drift default compression.threshold_tokens: "
            f"expected {SETTINGS['compression.threshold_tokens']!r}, actual 90000",
        ])
        with patch.dict(self.verifier.__dict__, {
                "run": lambda *args: subprocess.CompletedProcess(args, 0, json.dumps(SETTINGS[args[-1]]), "")}):
            self.assertEqual(self.run_check(managed, self.verifier.json_config), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
