#!/usr/bin/env python3
"""Orchestrator skill settings group in roster.yaml and its verify-state check (t_0a8674fe).

roster.yaml orchestrator_profile_settings requires, on each of the five project
orchestrators, skills.auto_load: ["multi-agent-coding-orchestrator"],
skills.write_approval: true, security.protected_instruction_files: true and
security.protected_instruction_extra_patterns: ["SKILL.md"]. The existing
managed_profile_settings group (compression settings, which also covers advisor
and default) stays unchanged; check_managed_setting_groups checks both groups
with one reader in fixture mode and in live mode.

Fixture runs go through the real verifier main() under the fixture-isolation guard;
the live path is exercised only with a stubbed command runner (no Hermes, no ~/.hermes).
All observations are synthetic.
"""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT, load_verifier
from test_verify_fixture_isolation import ObservedReads, fixture_result

ORCHESTRATORS = ["harness-orchestrator", "jobcron-orchestrator", "chapt-orchestrator",
                 "jss-orchestrator", "anki-orchestrator"]
SETTINGS = {
    "skills.auto_load": ["multi-agent-coding-orchestrator"],
    "skills.write_approval": True,
    "security.protected_instruction_files": True,
    "security.protected_instruction_extra_patterns": ["SKILL.md"],
}
COMPRESSION_PROFILES = ["advisor", "jobcron-orchestrator", "chapt-orchestrator", "harness-orchestrator", "default"]
# A value of the right shape that Hermes reads as a different setting, per key.
WRONG = {
    "skills.auto_load": [],
    "skills.write_approval": False,
    "security.protected_instruction_files": False,
    "security.protected_instruction_extra_patterns": [],
}
FIXTURES = ROOT / "tests/fixtures"
DRIFT_MESSAGES = [
    "FAIL: managed setting drift jobcron-orchestrator skills.auto_load: "
    "expected ['multi-agent-coding-orchestrator'], actual []",
    "FAIL: managed setting drift anki-orchestrator skills.write_approval: expected True, actual <unreadable>",
]


def load_json(rel):
    return json.loads((ROOT / rel).read_text())


def fail_lines(output):
    return [line for line in output.splitlines() if line.startswith("FAIL:")]


def clean_fixture():
    return json.loads((FIXTURES / "clean.yaml").read_text())


class DesiredStateTests(unittest.TestCase):
    def setUp(self):
        self.roster = load_json("roster.yaml")

    def test_roster_declares_exact_profiles_values_and_types(self):
        group = self.roster["orchestrator_profile_settings"]
        self.assertEqual(group, {"profiles": ORCHESTRATORS, "settings": SETTINGS})
        self.assertIs(group["settings"]["skills.write_approval"], True)
        self.assertIs(group["settings"]["security.protected_instruction_files"], True)
        snapshot = load_json("snapshots/sanitized-current-state.yaml")
        self.assertEqual({fleet["orchestrator"] for fleet in snapshot["project_isolation"].values()},
                         set(ORCHESTRATORS))

    def test_compression_group_is_unchanged_and_keeps_advisor_and_default(self):
        managed = self.roster["managed_profile_settings"]
        self.assertEqual(managed["profiles"], COMPRESSION_PROFILES)
        self.assertEqual(set(managed["settings"]), {
            "compression.threshold_tokens", "compression.proactive_prune_tokens",
            "compression.min_tail_user_messages", "compression.idle_compact_after_seconds"})
        for profile in ("advisor", "default"):
            self.assertNotIn(profile, self.roster["orchestrator_profile_settings"]["profiles"])


class FixtureVerifierTests(unittest.TestCase):
    def assert_isolated(self, guard):
        self.assertTrue(guard.attempts)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def run_observation(self, fixture):
        with tempfile.TemporaryDirectory(prefix="orchestrator-settings-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            code, output, guard = fixture_result(path)
        self.assert_isolated(guard)
        return code, output

    def test_clean_fixture_carries_the_group_and_passes(self):
        fixture = clean_fixture()
        for profile in ORCHESTRATORS:
            for key, want in SETTINGS.items():
                self.assertEqual(fixture["profile_managed_settings"][profile][key], want)
        code, output, guard = fixture_result(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: desired state matches observed state", output)
        self.assertNotIn("managed setting drift", output)
        self.assertNotIn("orchestrator profile settings", output)
        self.assert_isolated(guard)

    def test_drift_fixture_goes_red_naming_profile_and_key(self):
        code, output, guard = fixture_result(FIXTURES / "orchestrator-skill-settings-drift.yaml")
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), DRIFT_MESSAGES)
        self.assert_isolated(guard)

    def test_drift_fixture_differs_only_in_managed_settings(self):
        clean = clean_fixture()
        drift = json.loads((FIXTURES / "orchestrator-skill-settings-drift.yaml").read_text())
        managed = drift.pop("profile_managed_settings")
        expected = clean.pop("profile_managed_settings")
        self.assertEqual(drift, clean)
        expected["jobcron-orchestrator"]["skills.auto_load"] = []
        del expected["anki-orchestrator"]["skills.write_approval"]
        self.assertEqual(managed, expected)

    def test_drift_of_each_key_on_one_orchestrator_fails_naming_profile_and_key(self):
        for key, wrong in WRONG.items():
            with self.subTest(key=key):
                fixture = clean_fixture()
                fixture["profile_managed_settings"]["jss-orchestrator"][key] = wrong
                code, output = self.run_observation(fixture)
                self.assertEqual(code, 1, output)
                self.assertEqual(fail_lines(output), [
                    f"FAIL: managed setting drift jss-orchestrator {key}: expected {SETTINGS[key]!r}, "
                    f"actual {wrong!r}"])

    def test_values_equal_only_after_type_coercion_fail(self):
        for key, value in (("skills.write_approval", 1), ("skills.write_approval", "true"),
                           ("security.protected_instruction_files", 1),
                           ("skills.auto_load", "multi-agent-coding-orchestrator"),
                           ("security.protected_instruction_extra_patterns", ["SKILL.md", "SKILL.md"])):
            with self.subTest(key=key, value=value):
                fixture = clean_fixture()
                fixture["profile_managed_settings"]["harness-orchestrator"][key] = value
                code, output = self.run_observation(fixture)
                self.assertEqual(code, 1, output)
                self.assertEqual(fail_lines(output), [
                    f"FAIL: managed setting drift harness-orchestrator {key}: expected {SETTINGS[key]!r}, "
                    f"actual {value!r}"])

    def test_missing_key_is_unreadable_and_fails(self):
        for key in SETTINGS:
            with self.subTest(key=key):
                fixture = clean_fixture()
                del fixture["profile_managed_settings"]["chapt-orchestrator"][key]
                code, output = self.run_observation(fixture)
                self.assertEqual(code, 1, output)
                self.assertEqual(fail_lines(output), [
                    f"FAIL: managed setting drift chapt-orchestrator {key}: expected {SETTINGS[key]!r}, "
                    "actual <unreadable>"])
        fixture = clean_fixture()
        del fixture["profile_managed_settings"]["jss-orchestrator"]
        code, output = self.run_observation(fixture)
        self.assertEqual(code, 1, output)
        self.assertEqual(len(fail_lines(output)), len(SETTINGS), output)

    def test_advisor_and_default_are_not_required_to_have_the_new_keys(self):
        fixture = clean_fixture()
        for profile in ("advisor", "default"):
            self.assertFalse(set(SETTINGS) & set(fixture["profile_managed_settings"][profile]))
        code, output = self.run_observation(fixture)
        self.assertEqual(code, 0, output)


class CheckFunctionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.roster = load_json("roster.yaml")
        self.fleets = load_json("snapshots/sanitized-current-state.yaml")["project_isolation"]
        self.roster_profiles = {profile["name"]: profile for profile in self.roster["profiles"]}

    def read_desired(self, profile, key):
        for group in (self.roster["managed_profile_settings"], self.roster["orchestrator_profile_settings"]):
            if profile in group["profiles"] and key in group["settings"]:
                return copy.deepcopy(group["settings"][key])
        return self.verifier.UNREADABLE

    def run_groups(self, roster, read=None):
        errors = []
        with ObservedReads(), redirect_stdout(io.StringIO()):
            self.verifier.check_managed_setting_groups(errors, roster, self.fleets, self.roster_profiles,
                                                       read or self.read_desired)
        return errors

    def test_desired_roster_passes_and_reads_no_new_key_on_advisor_or_default(self):
        reads = []

        def read(profile, key):
            reads.append((profile, key))
            return self.read_desired(profile, key)

        self.assertEqual(self.run_groups(self.roster, read), [])
        for profile in ("advisor", "default"):
            self.assertFalse([key for read_profile, key in reads if read_profile == profile and key in SETTINGS])
        self.assertEqual(len(reads), len(COMPRESSION_PROFILES) * 4 + len(ORCHESTRATORS) * len(SETTINGS))

    def test_malformed_group_fails(self):
        for group in (None, {}, [], {"profiles": [], "settings": SETTINGS},
                      {"profiles": ORCHESTRATORS, "settings": {}},
                      {"profiles": ORCHESTRATORS + ["anki-orchestrator"], "settings": SETTINGS},
                      {"profiles": [{"name": "anki-orchestrator"}], "settings": SETTINGS},
                      {"profiles": "anki-orchestrator", "settings": SETTINGS}):
            with self.subTest(group=group):
                roster = copy.deepcopy(self.roster)
                roster["orchestrator_profile_settings"] = group
                errors = self.run_groups(roster)
                self.assertEqual(errors, ["orchestrator profile settings malformed: "
                                          "expected unique profiles and non-empty settings"])
        roster = copy.deepcopy(self.roster)
        del roster["orchestrator_profile_settings"]
        self.assertEqual(self.run_groups(roster), [
            "orchestrator profile settings malformed: expected unique profiles and non-empty settings"])

    def test_group_must_name_every_project_orchestrator(self):
        roster = copy.deepcopy(self.roster)
        roster["orchestrator_profile_settings"]["profiles"].remove("anki-orchestrator")
        errors = self.run_groups(roster)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith("orchestrator profile settings must name exactly the project "
                                             "orchestrators"), errors)
        roster["orchestrator_profile_settings"]["profiles"].append("advisor")
        errors = self.run_groups(roster)
        self.assertEqual(len(errors), len(SETTINGS) + 1, errors)
        self.assertIn("managed setting drift advisor skills.auto_load: "
                      "expected ['multi-agent-coding-orchestrator'], actual <unreadable>", errors)

    def test_a_key_declared_by_both_groups_for_one_profile_fails(self):
        roster = copy.deepcopy(self.roster)
        roster["orchestrator_profile_settings"]["settings"]["compression.threshold_tokens"] = 150000

        def read(profile, key):
            return 150000 if key == "compression.threshold_tokens" else self.read_desired(profile, key)

        errors = self.run_groups(roster, read)
        self.assertEqual(sorted(errors), sorted(
            f"orchestrator profile settings and managed profile settings both declare {profile} "
            "compression.threshold_tokens"
            for profile in ORCHESTRATORS if profile in COMPRESSION_PROFILES))

    def test_malformed_group_fails_through_main(self):
        roster = copy.deepcopy(self.roster)
        roster["orchestrator_profile_settings"] = {"profiles": ORCHESTRATORS, "settings": {}}
        original_load = self.verifier.load

        def load(path):
            return copy.deepcopy(roster) if Path(path) == ROOT / "roster.yaml" else original_load(path)

        output = io.StringIO()
        with patch.dict(self.verifier.__dict__, {"load": load}), ObservedReads(), \
                patch.object(sys, "argv", ["verify-state", "--fixture", str(FIXTURES / "clean.yaml")]), \
                redirect_stdout(output):
            code = self.verifier.main()
        self.assertEqual(code, 1, output.getvalue())
        self.assertEqual(fail_lines(output.getvalue()), [
            "FAIL: orchestrator profile settings malformed: expected unique profiles and non-empty settings"])

    def test_live_path_reads_each_key_through_json_config(self):
        calls = []

        def fake_run(*args):
            calls.append(args)
            profile, key = args[2], args[-1]
            if (profile, key) == ("anki-orchestrator", "skills.write_approval"):
                return subprocess.CompletedProcess(args, 1, "", "synthetic failure")
            if (profile, key) == ("jss-orchestrator", "skills.auto_load"):
                return subprocess.CompletedProcess(args, 0, "[]\n", "")
            value = self.read_desired(profile, key)
            return subprocess.CompletedProcess(args, 0, json.dumps(value) + "\n", "")

        with patch.dict(self.verifier.__dict__, {"run": fake_run}):
            errors = self.run_groups(self.roster, self.verifier.json_config)
        expected_calls = [("hermes", "-p", profile, "config", "get", "--json", key)
                          for group in (self.roster["managed_profile_settings"],
                                        self.roster["orchestrator_profile_settings"])
                          for profile in group["profiles"] for key in group["settings"]]
        self.assertEqual(calls, expected_calls)
        self.assertEqual(errors, [
            "managed setting drift jss-orchestrator skills.auto_load: "
            "expected ['multi-agent-coding-orchestrator'], actual []",
            "managed setting drift anki-orchestrator skills.write_approval: expected True, actual <unreadable>",
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
