#!/usr/bin/env python3
"""Fallback providers (t_54fc49fb): roster declaration schema, verify-state drift check in
fixture and live modes, and scripts/switch-profile-model --apply-fallbacks / --clear-fallbacks.

Every profile, model identifier and credential value here is synthetic. Fixture runs go
through the real verifier main() under the fixture-isolation guard; the live path runs only
with a stubbed command runner, and the switch script only against a temporary home with a
fake hermes that records its arguments.
"""
import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT, load_verifier
from test_verify_fixture_isolation import ObservedReads, fixture_result

FIXTURES = ROOT / "tests/fixtures"
JOBCRON_PROFILES = ("jobcron-orchestrator", "jobcron-worker", "jobcron-worker-2", "jobcron-reviewer")
SECRET = "synthetic-credential-value"
PROVIDERS = [{"provider": "anthropic", "model": "synthetic-main-fallback"}]
CHAINS = {
    "compression": [{"provider": "anthropic", "model": "synthetic-large-model", "timeout": 120}],
    "title_generation": [{"provider": "anthropic", "model": "synthetic-small-model"}],
}
DRIFT_MESSAGES = [
    'FAIL: fallback drift jobcron-worker fallback_providers: expected [], actual '
    '[{"provider": "anthropic", "model": "synthetic-fallback-model"}]',
    'FAIL: fallback drift harness-worker auxiliary.title_generation.fallback_chain: expected [], actual '
    '[{"provider": "anthropic", "model": "synthetic-helper-model", "api_key": "<not shown>"}]',
    "FAIL: fallback drift anki-worker auxiliary: expected a readable auxiliary mapping, actual <unreadable>",
]


def load_switch():
    loader = importlib.machinery.SourceFileLoader("switch_profile_model_fallbacks",
                                                  str(ROOT / "scripts/switch-profile-model"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def fail_lines(output):
    return [line for line in output.splitlines() if line.startswith("FAIL:")]


def synthetic_roster(**declarations):
    """A roster of two synthetic active profiles and one retired one; keyword arguments are
    added to the first profile's entry."""
    return {"profiles": [
        {"name": "synthetic-worker", "lifecycle": "project-active", **declarations},
        {"name": "synthetic-reviewer", "lifecycle": "project-active"},
        {"name": "synthetic-retired", "lifecycle": "retired",
         "fallback_providers": [{"provider": "anthropic", "model": "never-checked"}]},
    ]}


def observation(providers=None, chains=None):
    """Observed values as the fixture reader returns them (absent chains = no auxiliary fallback)."""
    return {"fallback_providers": copy.deepcopy(providers if providers is not None else []),
            "auxiliary": {task: {"fallback_chain": copy.deepcopy(chain)} for task, chain in (chains or {}).items()}}


class DeclarationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()

    def errors(self, **declarations):
        return self.verifier.fallback_declaration_errors({"name": "synthetic-worker", **declarations})

    def test_valid_and_absent_declarations_have_no_errors(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.errors(fallback_providers=PROVIDERS, auxiliary_fallback_chain=CHAINS), [])
        self.assertEqual(self.errors(fallback_providers=[], auxiliary_fallback_chain={}), [])
        self.assertEqual(self.errors(auxiliary_fallback_chain={"vision": [
            {"provider": "anthropic", "model": "m", "timeout": 1.5}]}), [])

    def test_credential_like_and_other_extra_fields_are_errors_without_their_values(self):
        for field in ("api_key", "key_env", "access_token", "client_secret", "API_KEY"):
            with self.subTest(field=field):
                errors = self.errors(fallback_providers=[{**PROVIDERS[0], field: SECRET}])
                self.assertEqual(errors, [
                    f"fallback declaration invalid synthetic-worker fallback_providers[0]: credential-like field "
                    f"{field!r} is not allowed (allowed: provider, model)"])
                errors = self.errors(auxiliary_fallback_chain={"review": [
                    {"provider": "anthropic", "model": "m", field: SECRET}]})
                self.assertEqual(len(errors), 1)
                self.assertIn(f"credential-like field {field!r}", errors[0])
                self.assertNotIn(SECRET, " ".join(errors))
        errors = self.errors(fallback_providers=[{**PROVIDERS[0], "base_url": "https://example.invalid"}])
        self.assertEqual(errors, [
            "fallback declaration invalid synthetic-worker fallback_providers[0]: field 'base_url' is not allowed "
            "(allowed: provider, model)"])
        # timeout is an auxiliary fallback_chain field only
        errors = self.errors(fallback_providers=[{**PROVIDERS[0], "timeout": 30}])
        self.assertIn("field 'timeout' is not allowed (allowed: provider, model)", errors[0])

    def test_unknown_auxiliary_task_name_is_an_error(self):
        for task in ("web_extract", "moa_aggregator", "Compression", ""):
            with self.subTest(task=task):
                self.assertEqual(self.errors(auxiliary_fallback_chain={task: CHAINS["compression"]}), [
                    f"fallback declaration invalid synthetic-worker auxiliary_fallback_chain: "
                    f"unknown auxiliary task {task!r}"])

    def test_malformed_shapes_missing_fields_and_bad_timeouts_are_errors(self):
        cases = (
            ({"fallback_providers": {"provider": "anthropic"}}, "fallback_providers: expected a list of entries"),
            ({"fallback_providers": ["anthropic"]}, "fallback_providers[0]: expected an object"),
            ({"fallback_providers": [{"provider": "anthropic"}]}, "fallback_providers[0]: model must be a non-empty string"),
            ({"fallback_providers": [{"provider": " ", "model": "m"}]}, "provider must be a non-empty string"),
            ({"auxiliary_fallback_chain": []}, "auxiliary_fallback_chain: expected an object keyed by auxiliary task name"),
            ({"auxiliary_fallback_chain": {"vision": {"provider": "anthropic", "model": "m"}}},
             "auxiliary_fallback_chain.vision: expected a list of entries"),
        )
        for declaration, message in cases:
            with self.subTest(declaration=declaration):
                errors = self.errors(**declaration)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(message, errors[0])
        for timeout in (0, -5, True, "30", None, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                errors = self.errors(auxiliary_fallback_chain={"vision": [
                    {"provider": "anthropic", "model": "m", "timeout": timeout}]})
                self.assertEqual(errors, [
                    "fallback declaration invalid synthetic-worker auxiliary_fallback_chain.vision[0]: "
                    "timeout must be a positive number of seconds"])

    def test_check_fallback_declarations_reports_every_roster_profile_including_retired(self):
        roster = synthetic_roster(fallback_providers=[{**PROVIDERS[0], "api_key": SECRET}])
        roster["profiles"][2]["auxiliary_fallback_chain"] = {"unknown_task": []}
        errors = []
        with redirect_stdout(io.StringIO()) as out:
            self.verifier.check_fallback_declarations(errors, roster)
        self.assertEqual(len(errors), 2)
        self.assertIn("synthetic-worker fallback_providers[0]: credential-like field 'api_key'", errors[0])
        self.assertIn("synthetic-retired auxiliary_fallback_chain: unknown auxiliary task 'unknown_task'", errors[1])
        self.assertNotIn(SECRET, out.getvalue())

    def test_repository_roster_declarations(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_fallback_declarations(errors, roster)
        self.assertEqual(errors, [])
        # The model identifiers are not verified yet: the Jobcron entries declare no fallback.
        for profile in roster["profiles"]:
            if profile["name"] in JOBCRON_PROFILES:
                self.assertNotIn("fallback_providers", profile)
                self.assertNotIn("auxiliary_fallback_chain", profile)

    def test_helper_tasks_have_one_definition(self):
        switch = load_switch()
        self.assertEqual(len(self.verifier.HELPER_TASKS), 16)
        self.assertEqual(switch.HELPER_TASKS, self.verifier.HELPER_TASKS)
        self.assertNotIn("anthropic", {target[0] for target in switch.TARGETS.values()})


class DriftCheckTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()

    def run_check(self, roster, observed):
        errors = []
        with ObservedReads(), redirect_stdout(io.StringIO()) as out:
            self.verifier.check_fallback_settings(errors, roster, self.verifier.fixture_setting_reader(observed))
        self.assertEqual(fail_lines(out.getvalue()), [f"FAIL: {e}" for e in errors])
        return errors

    def test_matching_values_pass(self):
        roster = synthetic_roster(fallback_providers=PROVIDERS, auxiliary_fallback_chain=CHAINS)
        observed = {"synthetic-worker": observation(PROVIDERS, CHAINS), "synthetic-reviewer": observation()}
        self.assertEqual(self.run_check(roster, observed), [])
        # An undeclared profile accepts an empty list, no value, and other auxiliary fields.
        observed["synthetic-reviewer"] = {"fallback_providers": None, "auxiliary": {
            "vision": {"provider": "claude-subscription", "fallback_chain": []}, "compression": None,
            "transient_retries": 2}}
        self.assertEqual(self.run_check(roster, observed), [])

    def test_missing_live_value_is_drift(self):
        roster = synthetic_roster(fallback_providers=PROVIDERS, auxiliary_fallback_chain=CHAINS)
        observed = {"synthetic-worker": observation([], {"compression": CHAINS["compression"]}),
                    "synthetic-reviewer": observation()}
        self.assertEqual(self.run_check(roster, observed), [
            'fallback drift synthetic-worker fallback_providers: expected '
            '[{"provider": "anthropic", "model": "synthetic-main-fallback"}], actual []',
            'fallback drift synthetic-worker auxiliary.title_generation.fallback_chain: expected '
            '[{"provider": "anthropic", "model": "synthetic-small-model"}], actual unset',
        ])

    def test_extra_live_value_is_drift_and_hides_other_field_values(self):
        roster = synthetic_roster()
        extra = [{"provider": "anthropic", "model": "synthetic-extra", "api_key": SECRET, "timeout": 30}]
        observed = {"synthetic-worker": observation(extra, {"mcp": extra, "moa_reference": extra}),
                    "synthetic-reviewer": observation()}
        shown = '[{"provider": "anthropic", "model": "synthetic-extra", "api_key": "<not shown>", "timeout": 30}]'
        errors = self.run_check(roster, observed)
        self.assertEqual(errors, [
            f"fallback drift synthetic-worker fallback_providers: expected [], actual {shown}",
            f"fallback drift synthetic-worker auxiliary.mcp.fallback_chain: expected [], actual {shown}",
            f"fallback drift synthetic-worker auxiliary.moa_reference.fallback_chain: expected [], actual {shown}",
        ])
        self.assertNotIn(SECRET, " ".join(errors))

    def test_changed_value_and_type_are_drift(self):
        roster = synthetic_roster(auxiliary_fallback_chain=CHAINS)
        changed = copy.deepcopy(CHAINS)
        changed["compression"][0]["timeout"] = 120.0
        changed["title_generation"][0]["model"] = "synthetic-other-model"
        observed = {"synthetic-worker": observation([], changed), "synthetic-reviewer": observation()}
        errors = self.run_check(roster, observed)
        self.assertEqual([e.split(":")[0] for e in errors], [
            "fallback drift synthetic-worker auxiliary.compression.fallback_chain",
            "fallback drift synthetic-worker auxiliary.title_generation.fallback_chain"])

    def test_unreadable_and_malformed_observations_fail_closed(self):
        roster = synthetic_roster()
        for observed in (None, {}, {"synthetic-worker": None},
                         {"synthetic-worker": {"fallback_providers": []}},
                         {"synthetic-worker": {"fallback_providers": "not a list", "auxiliary": []}}):
            with self.subTest(observed=observed):
                errors = self.run_check(roster, observed)
                # No observation of synthetic-reviewer exists in any case, so both profiles fail.
                for name in ("synthetic-worker", "synthetic-reviewer"):
                    self.assertTrue(any(e.startswith(f"fallback drift {name} ") for e in errors), errors)
                self.assertFalse(any("synthetic-retired" in e for e in errors), errors)

    def test_unknown_task_declaration_and_retired_profiles_are_not_compared(self):
        roster = synthetic_roster(auxiliary_fallback_chain={"not_a_helper_task": CHAINS["compression"]})
        observed = {"synthetic-reviewer": observation()}  # synthetic-worker and the retired profile unread
        self.assertEqual(self.run_check(roster, observed), [])

    def test_live_path_reads_two_keys_per_profile_through_json_config(self):
        roster = synthetic_roster(fallback_providers=PROVIDERS, auxiliary_fallback_chain=CHAINS)
        live = {("synthetic-worker", "fallback_providers"): PROVIDERS,
                ("synthetic-worker", "auxiliary"): observation(chains=CHAINS)["auxiliary"],
                ("synthetic-reviewer", "fallback_providers"): []}
        calls = []

        def fake_run(*args):
            calls.append(args)
            key = (args[2], args[-1])
            if key not in live:  # e.g. the auxiliary read of synthetic-reviewer fails
                return subprocess.CompletedProcess(args, 1, "", "synthetic failure")
            return subprocess.CompletedProcess(args, 0, json.dumps(live[key]), "")

        errors = []
        with patch.dict(self.verifier.__dict__, {"run": fake_run}), redirect_stdout(io.StringIO()):
            self.verifier.check_fallback_settings(errors, roster, self.verifier.json_config)
        self.assertEqual(calls, [("hermes", "-p", profile, "config", "get", "--json", key)
                                 for profile in ("synthetic-worker", "synthetic-reviewer")
                                 for key in ("fallback_providers", "auxiliary")])
        self.assertEqual(errors, ["fallback drift synthetic-reviewer auxiliary: expected a readable auxiliary "
                                  "mapping, actual <unreadable>"])


class FixtureTests(unittest.TestCase):
    def test_clean_fixture_mirrors_roster_and_passes(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        active = [p["name"] for p in roster["profiles"] if p.get("lifecycle") != "retired"]
        self.assertEqual(list(clean["profile_fallback_settings"]), active)
        code, output, guard = fixture_result(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertNotIn("fallback", output)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_drift_fixture_differs_only_in_fallback_settings_and_goes_red(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        drift = json.loads((FIXTURES / "fallback-drift.yaml").read_text())
        drift.pop("profile_fallback_settings")
        clean.pop("profile_fallback_settings")
        self.assertEqual(drift, clean)
        code, output, guard = fixture_result(FIXTURES / "fallback-drift.yaml")
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), DRIFT_MESSAGES)
        self.assertNotIn("synthetic-value-not-shown", output)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_missing_section_is_incomplete(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        del clean["profile_fallback_settings"]
        with tempfile.TemporaryDirectory(prefix="fallback-settings-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(clean))
            code, output, _ = fixture_result(path)
        self.assertEqual(code, 1, output)
        self.assertIn("incomplete fixture: missing required section 'profile_fallback_settings'", output)
        self.assertTrue(any(line.endswith("auxiliary: expected a readable auxiliary mapping, actual <unreadable>")
                            for line in fail_lines(output)))


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.switch = load_switch()
        self.tmp = tempfile.TemporaryDirectory(prefix="switch-fallbacks-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "profiles/synthetic-worker/config.yaml"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("model:\n  default: synthetic\n")
        self.calls = self.root / "calls.jsonl"
        self.fake = self.root / "hermes"
        self.fake.write_text(f"#!{sys.executable}\nimport json, sys\n"
                             f"open({str(self.calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n")
        self.fake.chmod(0o700)
        self.roster = self.root / "roster.yaml"
        self.write_roster(synthetic_roster(model="claude-opus-5-5", provider="claude-subscription",
                                           fallback_providers=PROVIDERS, auxiliary_fallback_chain=CHAINS))

    def write_roster(self, roster):
        self.roster.write_text(json.dumps(roster, indent=2) + "\n")
        self.roster_text = self.roster.read_text()

    def run_switch(self, *args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                code = self.switch.main(["--home-root", str(self.root), "--hermes", str(self.fake),
                                         "--roster", str(self.roster), "--profile", "synthetic-worker", *args])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def calls_made(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def backups(self):
        return list(self.config.parent.glob("config.yaml.pre-switch-*"))

    def fallback_calls(self, providers, chains):
        calls = [["-p", "synthetic-worker", "config", "set", "fallback_providers", json.dumps(providers)]]
        return calls + [["-p", "synthetic-worker", "config", "set", f"auxiliary.{task}.fallback_chain",
                         json.dumps(chains.get(task, []))] for task in self.switch.HELPER_TASKS]

    def test_apply_fallbacks_writes_both_keys_from_the_roster_and_backs_up(self):
        code, out, _ = self.run_switch("--apply-fallbacks")
        self.assertEqual(code, 0)
        calls = self.calls_made()
        self.assertEqual(calls, self.fallback_calls(PROVIDERS, CHAINS))
        self.assertEqual(len(calls), 17)
        for call in calls:  # each value is a JSON list literal that `hermes config set` parses as a list
            self.assertTrue(call[5].startswith("["))
            self.assertIsInstance(json.loads(call[5]), list)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.roster.read_text(), self.roster_text)
        self.assertIn("fallbacks: applied the", out)

    def test_apply_fallbacks_with_to_sets_the_model_first_with_one_backup(self):
        code, _, _ = self.run_switch("--to", "claude-opus", "--apply-fallbacks")
        self.assertEqual(code, 0)
        calls = self.calls_made()
        self.assertEqual(calls[0][4], "model.provider")
        self.assertEqual(len(calls), 3 + 2 * 16 + 17)
        self.assertEqual(calls[-17:], self.fallback_calls(PROVIDERS, CHAINS))
        self.assertEqual(len(self.backups()), 1)

    def test_dry_run_writes_nothing(self):
        for args in (("--apply-fallbacks",), ("--clear-fallbacks",), ("--to", "claude-opus", "--apply-fallbacks")):
            with self.subTest(args=args):
                code, out, _ = self.run_switch(*args, "--dry-run")
                self.assertEqual(code, 0)
                self.assertIn(f"config set fallback_providers {json.dumps([] if '--clear-fallbacks' in args else PROVIDERS)}",
                              out)
                self.assertIn("(dry run: nothing written)", out)
                self.assertFalse(self.calls.exists())
                self.assertEqual(self.backups(), [])
                self.assertEqual(self.roster.read_text(), self.roster_text)
                self.assertEqual(self.config.read_text(), "model:\n  default: synthetic\n")

    def test_clear_fallbacks_sets_every_key_to_an_empty_list(self):
        code, out, _ = self.run_switch("--clear-fallbacks")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls_made(), self.fallback_calls([], {}))
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.roster.read_text(), self.roster_text)
        self.assertIn("still declares fallbacks for synthetic-worker", out)
        # Without a roster declaration there is nothing to remind about.
        self.calls.unlink()
        self.write_roster(synthetic_roster())
        code, out, _ = self.run_switch("--clear-fallbacks")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls_made(), self.fallback_calls([], {}))
        self.assertNotIn("still declares", out)

    def test_invalid_roster_declaration_writes_nothing_and_hides_values(self):
        for declarations, message in (
                ({"fallback_providers": [{**PROVIDERS[0], "api_key": SECRET}]}, "credential-like field 'api_key'"),
                ({"auxiliary_fallback_chain": {"web_extract": CHAINS["compression"]}}, "unknown auxiliary task"),
                ({"auxiliary_fallback_chain": {"vision": [{"provider": "anthropic", "model": "m",
                                                           "key_env": SECRET}]}}, "credential-like field 'key_env'")):
            with self.subTest(declarations=declarations):
                self.write_roster(synthetic_roster(**declarations))
                code, out, err = self.run_switch("--apply-fallbacks")
                self.assertEqual(code, 2)
                self.assertIn(message, err)
                self.assertNotIn(SECRET, out + err)
                self.assertFalse(self.calls.exists())
                self.assertEqual(self.backups(), [])

    def test_option_combinations(self):
        for args, message in ((("--dry-run",), "give --to, --apply-fallbacks or --clear-fallbacks"),
                              (("--apply-fallbacks", "--clear-fallbacks"), "not allowed with argument"),
                              (("--apply-fallbacks", "--model", "m"), "--model needs --to"),
                              (("--clear-fallbacks", "--dispatch", "add"), "--dispatch needs --to")):
            with self.subTest(args=args):
                code, _, err = self.run_switch(*args)
                self.assertEqual(code, 2)
                self.assertIn(message, err)
        self.write_roster({"profiles": []})
        code, _, err = self.run_switch("--apply-fallbacks", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("synthetic-worker is not declared", err)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
