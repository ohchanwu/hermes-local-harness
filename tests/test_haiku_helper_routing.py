#!/usr/bin/env python3
"""The six light auxiliary helper tasks on claude-subscription / claude-haiku-5-5 (card t_e7efc35f).

Offline checks of tracked repository files only: the shared light-task definition, the roster
`auxiliary_models` declaration and its validation, the scripts/verify-state drift check in fixture
mode and (with a stubbed command runner) live mode, the planned writes of
scripts/switch-profile-model --dry-run, and the live procedure document. No live ~/.hermes read,
board access, network or model call. Synthetic profile names start with "synthetic-".
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
HAIKU, OPUS, FABLE = "claude-haiku-5-5", "claude-opus-5-5", "claude-fable-5-2"
LIGHT = ("title_generation", "memory_query_rewrite", "tts_audio_tags", "profile_describer", "skills_hub", "vision")
FABLE_PROFILES = ("advisor", "anki-reviewer", "chapt-reviewer", "harness-reviewer", "jobcron-reviewer", "jss-reviewer")
SCOPE = ("advisor", *(f"{project}-{role}" for project in ("anki", "chapt", "harness", "jobcron", "jss")
                      for role in ("orchestrator", "worker", "worker-2", "reviewer")))
DECLARATION = {"light_tasks": HAIKU, "other_tasks": OPUS}
DRIFT_MESSAGES = [
    "FAIL: auxiliary model drift advisor auxiliary.compression.model: expected claude-opus-5-5, actual unset",
    "FAIL: auxiliary model drift harness-worker auxiliary.title_generation.model: expected claude-haiku-5-5, "
    "actual claude-opus-5-5",
    "FAIL: auxiliary model drift jss-reviewer auxiliary.vision.provider: expected claude-subscription, "
    "actual anthropic",
    "FAIL: auxiliary model drift anki-worker auxiliary: expected a readable auxiliary mapping, actual <unreadable>",
]


def load_switch():
    loader = importlib.machinery.SourceFileLoader("switch_profile_model_haiku",
                                                  str(ROOT / "scripts/switch-profile-model"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def load_compat_models():
    namespace = {}
    path = ROOT / "plugins/model-providers/claude-subscription/compat.py"
    exec(compile(path.read_text(), str(path), "exec"), namespace)
    return namespace["MODELS"]


def fail_lines(output):
    return [line for line in output.splitlines() if line.startswith("FAIL:")]


def observed_auxiliary(light=HAIKU, other=OPUS, provider="claude-subscription"):
    """The auxiliary mapping as `hermes config get --json auxiliary` returns it after a Claude switch."""
    return {task: {"provider": provider, "model": light if task in LIGHT else other, "fallback_chain": []}
            for task in load_verifier().HELPER_TASKS}


def synthetic_roster(**declaration):
    return {"profiles": [
        {"name": "synthetic-worker", "provider": "claude-subscription", "lifecycle": "project-active",
         "auxiliary_models": dict(DECLARATION), **declaration},
        {"name": "synthetic-undeclared", "provider": "claude-subscription", "lifecycle": "project-active"},
        {"name": "synthetic-retired", "provider": "claude-subscription", "lifecycle": "retired",
         "auxiliary_models": dict(DECLARATION)},
    ]}


class LightTaskDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()

    def test_light_tasks_are_the_six_owner_tasks_and_members_of_helper_tasks(self):
        self.assertEqual(self.verifier.LIGHT_HELPER_TASKS, LIGHT)
        for task in self.verifier.LIGHT_HELPER_TASKS:
            with self.subTest(task=task):
                self.assertIn(task, self.verifier.HELPER_TASKS)
        self.assertEqual(self.verifier.light_helper_task_errors(), [])
        other = [task for task in self.verifier.HELPER_TASKS if task not in LIGHT]
        self.assertEqual(len(other), 10)
        self.assertIn("compression", other)

    def test_switch_script_uses_the_same_definition(self):
        switch = load_switch()
        self.assertIs(switch.LIGHT_HELPER_TASKS, switch.VERIFIER.LIGHT_HELPER_TASKS)
        self.assertEqual(switch.LIGHT_HELPER_TASKS, LIGHT)

    def test_an_unknown_duplicate_or_empty_definition_is_an_error(self):
        errors = self.verifier.light_helper_task_errors(("title_generation", "web_extract"))
        self.assertEqual(errors, ["light helper task definition invalid: 'web_extract' is not an auxiliary task "
                                  "in HELPER_TASKS"])
        self.assertEqual(self.verifier.light_helper_task_errors(("vision", "vision")),
                         ["light helper task definition invalid: a task is listed more than once"])
        self.assertEqual(self.verifier.light_helper_task_errors(()),
                         ["light helper task definition invalid: no task listed"])

    def test_an_invalid_definition_fails_the_declaration_check_and_skips_the_drift_check(self):
        errors = []
        with patch.dict(self.verifier.__dict__, {"LIGHT_HELPER_TASKS": ("web_extract",)}), \
                redirect_stdout(io.StringIO()) as out:
            self.verifier.check_auxiliary_model_declarations(errors, {"profiles": []}, frozenset({HAIKU, OPUS}))
            self.verifier.check_auxiliary_models(errors, synthetic_roster(), self.fail_on_read, frozenset({HAIKU}))
        self.assertEqual(errors, ["light helper task definition invalid: 'web_extract' is not an auxiliary task "
                                  "in HELPER_TASKS"])
        self.assertEqual(fail_lines(out.getvalue()), [f"FAIL: {e}" for e in errors])

    def fail_on_read(self, profile, key):
        raise AssertionError(f"unexpected read {profile} {key}")


class AllowlistAndDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.allowed = self.verifier.claude_subscription_models()

    def errors(self, profile):
        return self.verifier.auxiliary_model_declaration_errors({"name": "synthetic-worker", **profile}, self.allowed)

    def test_allowlist_is_read_from_compat_without_running_it(self):
        self.assertEqual(self.allowed, frozenset(load_compat_models()))
        self.assertIn(HAIKU, self.allowed)
        self.assertIsNone(self.verifier.claude_subscription_models(ROOT / "tests/fixtures/no-such-compat.py"))
        with tempfile.TemporaryDirectory(prefix="haiku-compat-") as directory:
            path = Path(directory) / "compat.py"
            for text in ("MODELS = dict(a=1)\n", "OTHER = {}\n", "MODELS = {\n", "MODELS = ['claude-opus-5-5']\n"):
                with self.subTest(text=text):
                    path.write_text(text)
                    self.assertIsNone(self.verifier.claude_subscription_models(path))

    def test_valid_and_absent_declarations_have_no_errors(self):
        self.assertEqual(self.errors({"provider": "claude-subscription", "auxiliary_models": DECLARATION}), [])
        self.assertEqual(self.errors({"provider": "zai"}), [])

    def test_invalid_declarations(self):
        prefix = "auxiliary model declaration invalid synthetic-worker"
        cases = (
            ({"auxiliary_models": [HAIKU]}, [f"{prefix}: expected an object with the keys light_tasks and other_tasks"]),
            ({"auxiliary_models": {**DECLARATION, "title_generation": HAIKU}},
             [f"{prefix}: unknown key 'title_generation' (allowed: light_tasks, other_tasks)"]),
            ({"auxiliary_models": {"light_tasks": HAIKU}}, [f"{prefix}: other_tasks must be a non-empty model id"]),
            ({"auxiliary_models": {"light_tasks": " ", "other_tasks": OPUS}},
             [f"{prefix}: light_tasks must be a non-empty model id"]),
            ({"auxiliary_models": {"light_tasks": "claude-haiku-4-5-20251001", "other_tasks": OPUS}},
             [f"{prefix}: light_tasks model 'claude-haiku-4-5-20251001' is not in the claude-subscription allowlist"]),
            ({"auxiliary_models": DECLARATION, "provider": "anthropic"},
             [f"{prefix}: the profile provider 'anthropic' is not claude-subscription"]),
        )
        for profile, want in cases:
            with self.subTest(profile=profile):
                self.assertEqual(self.errors({"provider": "claude-subscription", **profile}), want)

    def test_an_unreadable_allowlist_fails_every_declaration(self):
        errors = self.verifier.auxiliary_model_declaration_errors(
            {"name": "synthetic-worker", "provider": "claude-subscription", "auxiliary_models": DECLARATION}, None)
        self.assertEqual(errors, ["auxiliary model declaration invalid synthetic-worker: the claude-subscription "
                                  "allowlist (MODELS in plugins/model-providers/claude-subscription/compat.py) "
                                  "is unreadable"])

    def test_repository_roster_declares_the_split_for_exactly_the_21_profiles(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_auxiliary_model_declarations(errors, roster, self.allowed)
        self.assertEqual(errors, [])
        declared = {p["name"]: p for p in roster["profiles"] if "auxiliary_models" in p}
        self.assertEqual(len(SCOPE), 21)
        self.assertEqual(sorted(declared), sorted(SCOPE))
        switch = load_switch()
        for name, profile in declared.items():
            with self.subTest(profile=name):
                self.assertEqual(profile["auxiliary_models"], DECLARATION)
                self.assertNotEqual(profile.get("lifecycle"), "retired")
                self.assertEqual(profile["provider"], "claude-subscription")
                target = "claude-fable" if name in FABLE_PROFILES else "claude-opus"
                self.assertEqual(profile["model"], switch.TARGETS[target][2])
                # The roster declaration equals what the switch script writes for the profile's target.
                self.assertEqual(switch.helper_models(target, profile["model"]), (HAIKU, OPUS))
        for name in ("default", "harness-worker-glm-1", "worker-sol"):
            self.assertNotIn(name, declared)


class DriftCheckTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.allowed = self.verifier.claude_subscription_models()

    def run_check(self, roster, observed):
        errors = []
        with ObservedReads(), redirect_stdout(io.StringIO()) as out:
            self.verifier.check_auxiliary_models(errors, roster, self.verifier.fixture_setting_reader(observed),
                                                 self.allowed)
        self.assertEqual(fail_lines(out.getvalue()), [f"FAIL: {e}" for e in errors])
        return errors

    def test_expected_models_per_task(self):
        expected = self.verifier.expected_auxiliary_models(DECLARATION)
        self.assertEqual(list(expected), list(self.verifier.HELPER_TASKS))
        self.assertEqual({task for task, (_, model) in expected.items() if model == HAIKU}, set(LIGHT))
        self.assertEqual({provider for provider, _ in expected.values()}, {"claude-subscription"})

    def test_matching_values_pass_and_only_declared_active_profiles_are_read(self):
        observed = {"synthetic-worker": {"auxiliary": observed_auxiliary()}}
        self.assertEqual(self.run_check(synthetic_roster(), observed), [])

    def test_helpers_still_on_one_model_are_drift_on_the_six_light_tasks(self):
        observed = {"synthetic-worker": {"auxiliary": observed_auxiliary(light=OPUS)}}
        self.assertEqual(self.run_check(synthetic_roster(), observed), [
            f"auxiliary model drift synthetic-worker auxiliary.{task}.model: expected {HAIKU}, actual {OPUS}"
            for task in self.verifier.HELPER_TASKS if task in LIGHT])

    def test_provider_unset_and_malformed_values_are_drift(self):
        auxiliary = observed_auxiliary()
        auxiliary["vision"]["provider"] = "anthropic"
        del auxiliary["compression"]["model"]
        auxiliary["review"] = None
        auxiliary["mcp"]["model"] = 5
        observed = {"synthetic-worker": {"auxiliary": auxiliary}}
        self.assertEqual(self.run_check(synthetic_roster(), observed), [
            "auxiliary model drift synthetic-worker auxiliary.vision.provider: expected claude-subscription, "
            "actual anthropic",
            "auxiliary model drift synthetic-worker auxiliary.compression.model: expected claude-opus-5-5, actual unset",
            "auxiliary model drift synthetic-worker auxiliary.review.provider: expected claude-subscription, "
            "actual unset",
            "auxiliary model drift synthetic-worker auxiliary.review.model: expected claude-opus-5-5, actual unset",
            "auxiliary model drift synthetic-worker auxiliary.mcp.model: expected claude-opus-5-5, actual <int>",
        ])

    def test_unreadable_observations_fail_closed(self):
        for observed in (None, {}, {"synthetic-worker": None}, {"synthetic-worker": {}},
                         {"synthetic-worker": {"auxiliary": []}}):
            with self.subTest(observed=observed):
                errors = self.run_check(synthetic_roster(), observed)
                self.assertEqual(len(errors), 1, errors)
                self.assertTrue(errors[0].startswith("auxiliary model drift synthetic-worker auxiliary: expected a "
                                                     "readable auxiliary mapping, actual <"), errors)

    def test_an_invalid_declaration_is_not_compared(self):
        roster = synthetic_roster(auxiliary_models={"light_tasks": "claude-unlisted", "other_tasks": OPUS})
        self.assertEqual(self.run_check(roster, {}), [])

    def test_live_path_reads_the_auxiliary_mapping_once_per_declared_profile(self):
        calls = []

        def fake_run(*args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps(observed_auxiliary(light=OPUS)), "")

        errors = []
        with patch.dict(self.verifier.__dict__, {"run": fake_run}), redirect_stdout(io.StringIO()):
            self.verifier.check_auxiliary_models(errors, synthetic_roster(), self.verifier.json_config, self.allowed)
        self.assertEqual(calls, [("hermes", "-p", "synthetic-worker", "config", "get", "--json", "auxiliary")])
        self.assertEqual(len(errors), 6)


class FixtureTests(unittest.TestCase):
    def test_clean_fixture_observes_every_declared_profile_and_passes(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        self.assertEqual(sorted(clean["profile_auxiliary_settings"]),
                         sorted(p["name"] for p in roster["profiles"] if "auxiliary_models" in p))
        for name, observed in clean["profile_auxiliary_settings"].items():
            with self.subTest(profile=name):
                self.assertEqual({task: section["model"] for task, section in observed["auxiliary"].items()},
                                 {task: HAIKU if task in LIGHT else OPUS for task in load_verifier().HELPER_TASKS})
        code, output, guard = fixture_result(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertNotIn("auxiliary model", output)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_drift_fixture_differs_only_in_auxiliary_settings_and_goes_red(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        drift = json.loads((FIXTURES / "auxiliary-model-drift.yaml").read_text())
        drift.pop("profile_auxiliary_settings")
        clean.pop("profile_auxiliary_settings")
        self.assertEqual(drift, clean)
        code, output, guard = fixture_result(FIXTURES / "auxiliary-model-drift.yaml")
        self.assertEqual(code, 1, output)
        self.assertEqual(fail_lines(output), DRIFT_MESSAGES)
        self.assertTrue(all(attempt in guard.allowed for attempt in guard.attempts))

    def test_missing_section_is_incomplete(self):
        clean = json.loads((FIXTURES / "clean.yaml").read_text())
        del clean["profile_auxiliary_settings"]
        with tempfile.TemporaryDirectory(prefix="auxiliary-settings-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(clean))
            code, output, _ = fixture_result(path)
        self.assertEqual(code, 1, output)
        self.assertIn("incomplete fixture: missing required section 'profile_auxiliary_settings'", output)
        self.assertEqual(sum(line.endswith("auxiliary: expected a readable auxiliary mapping, actual <unreadable>")
                             and line.startswith("FAIL: auxiliary model drift ") for line in fail_lines(output)), 21)


class SwitchDryRunTests(unittest.TestCase):
    def setUp(self):
        self.switch = load_switch()
        self.tmp = tempfile.TemporaryDirectory(prefix="switch-haiku-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("harness-worker", "harness-reviewer", "synthetic-gpt"):
            (self.root / "profiles" / name).mkdir(parents=True)
            (self.root / "profiles" / name / "config.yaml").write_text("model:\n  default: unchanged\n")
        self.calls = self.root / "calls.jsonl"
        self.fake = self.root / "hermes"
        self.fake.write_text(f"#!{sys.executable}\nimport json, sys\n"
                             f"open({str(self.calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n")
        self.fake.chmod(0o700)
        # A temporary roster copy: the repository roster.yaml is never written by tests.
        self.roster = self.root / "roster.yaml"
        self.roster.write_text((ROOT / "roster.yaml").read_text())

    def run_switch(self, *args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            code = self.switch.main(["--home-root", str(self.root), "--hermes", str(self.fake),
                                     "--roster", str(self.roster), *args])
        return code, out.getvalue()

    def planned(self, output, profile):
        prefix = f"{self.fake} -p {profile} config set "
        return [line[len(prefix):].split(" ", 1) for line in output.splitlines() if line.startswith(prefix)]

    def assert_nothing_written(self, profile):
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.roster.read_text(), (ROOT / "roster.yaml").read_text())
        self.assertEqual(list((self.root / "profiles" / profile).glob("config.yaml.pre-switch-*")), [])

    def expected_writes(self, main_model):
        writes = [["model.provider", "claude-subscription"], ["model.default", main_model],
                  ["model.base_url", "acp://claude-subscription"]]
        for task in self.switch.HELPER_TASKS:
            writes += [[f"auxiliary.{task}.provider", "claude-subscription"],
                       [f"auxiliary.{task}.model", HAIKU if task in LIGHT else OPUS]]
        return writes

    def test_dry_run_for_an_opus_profile(self):
        code, out = self.run_switch("--profile", "harness-worker", "--to", "claude-opus", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(self.planned(out, "harness-worker"), self.expected_writes(OPUS))
        self.assertIn(f"harness-worker model {OPUS} -> {OPUS}, provider claude-subscription -> claude-subscription "
                      "(dry run: nothing written)", out)
        self.assertNotIn("auxiliary_models", out)  # the roster declaration agrees with the writes
        self.assertNotIn("fallback", out)          # a switch writes no fallback key
        self.assert_nothing_written("harness-worker")

    def test_dry_run_for_a_fable_profile(self):
        code, out = self.run_switch("--profile", "harness-reviewer", "--to", "claude-fable", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(self.planned(out, "harness-reviewer"), self.expected_writes(FABLE))
        self.assertIn(f"harness-reviewer model {FABLE} -> {FABLE}, provider claude-subscription -> "
                      "claude-subscription (dry run: nothing written)", out)
        self.assertNotIn("auxiliary_models", out)
        self.assertNotIn("fallback", out)
        self.assert_nothing_written("harness-reviewer")

    def test_gpt_and_glm_targets_keep_every_helper_on_the_main_model(self):
        for target, model in (("gpt", "gpt-5.6-sol"), ("glm", "glm-5.3")):
            with self.subTest(target=target):
                self.assertEqual(self.switch.helper_models(target, model), (model, model))
                helpers = [value for key, value in self.switch.settings(target, None) if key.endswith(".model")]
                self.assertEqual(helpers, [model] * 16)

    def test_switching_a_declared_profile_off_claude_prints_the_roster_reminder(self):
        code, out = self.run_switch("--profile", "harness-worker", "--to", "glm", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn(f"declares auxiliary_models {json.dumps(DECLARATION)} for harness-worker, but this switch writes "
                      "glm-5.3 for the light tasks and glm-5.3 for the other tasks on zai: update or remove that "
                      "declaration, or scripts/verify-state reports auxiliary model drift (dry run: nothing written)",
                      out)
        self.assert_nothing_written("harness-worker")

    def test_apply_summary_names_both_helper_models(self):
        code, out = self.run_switch("--profile", "harness-worker", "--to", "claude-opus")
        self.assertEqual(code, 0)
        self.assertIn(f"harness-worker: claude-opus ({OPUS}); helpers on {HAIKU} for the light tasks "
                      f"({', '.join(LIGHT)}) and on {OPUS} for the other tasks; backup config.yaml.pre-switch-", out)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([call[4:] for call in calls], self.expected_writes(OPUS))
        # The roster copy keeps its content: model, provider and auxiliary_models are unchanged.
        self.assertEqual(json.loads(self.roster.read_text()), json.loads((ROOT / "roster.yaml").read_text()))


class ProcedureTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "procedures/haiku-helper-routing.md").read_text(encoding="utf-8")
        self.flat = " ".join(self.text.split())  # the prose with every line break and indent as one space

    def test_steps_a_to_g_are_present(self):
        for heading in ("### a. Smoke test of claude-haiku-5-5", "### b. Copy the changed plugin files",
                        "### c. Gateway restart by the owner", "### d. Switch each profile",
                        "### e. Live scripts/verify-state", "### f. Acceptance evidence", "### g. Revert"):
            self.assertIn(heading, self.text)
        self.assertIn("smoke.py --cli <dedicated claude CLI path> --model claude-haiku-5-5", self.text)
        self.assertIn("SMOKE PASS cli=2.1.302 model=claude-haiku-5-5", self.text)
        self.assertIn('echo "copies: $n"', self.text)
        self.assertIn("Expected: `copies: 22`", self.text)
        self.assertIn("--dry-run", self.text)
        self.assertIn("auth.adopt_external_logins", self.text)
        self.assertIn("Result: the switch does not rewrite `fallback_providers` or any "
                      "`auxiliary.<task>.fallback_chain`.", self.flat)
        self.assertIn("lines 7536 to 7538", self.flat)
        self.assertNotIn("step 5", self.flat)
        self.assertIn("agent/auxiliary_client.py", self.text)
        self.assertIn("session_model_usage", self.text)
        self.assertIn("config.yaml.pre-haiku55-$TS", self.text)

    def test_profile_lists_match_the_roster(self):
        section = self.text[self.text.index("- Profiles (21)"):self.text.index("- Out of scope")]
        roster_names = {p["name"] for p in json.loads((ROOT / "roster.yaml").read_text())["profiles"]}
        named = [word.strip("`,.:") for word in section.split() if word.startswith("`")]
        named = [name for name in named if name in roster_names]
        self.assertEqual(sorted(named), sorted(SCOPE))  # each of the 21 profiles once
        fable = [word.strip("`,.:") for word in section[:section.index("--to claude-opus")].split()]
        self.assertEqual(sorted(name for name in fable if name in roster_names), sorted(FABLE_PROFILES))
        self.assertNotIn("sk-" + "ant-", self.text)  # Anthropic key prefix, split so this file does not contain it


if __name__ == "__main__":
    unittest.main(verbosity=2)
