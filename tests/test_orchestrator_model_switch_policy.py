#!/usr/bin/env python3
"""Manual model switch policy for the five project orchestrators (t_822da1dd).

Owner decision of 2026-11-14: a project orchestrator on claude-subscription may
run claude-opus-5-5 as its observed main model while the roster still declares
claude-fable-5-2; verify-state accepts it and prints one warning. Every other
profile keeps the baseline comparison. Checks the fixture path of the verifier
only; no live profile, board, network or model observation.
"""
from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier

ORCHESTRATORS = ("harness-orchestrator", "chapt-orchestrator", "jobcron-orchestrator",
                 "jss-orchestrator", "anki-orchestrator")
FABLE, OPUS = "claude-fable-5-2", "claude-opus-5-5"
MANUAL_SWITCH_WARNING = ("manual model switch {name}: model.default is {observed}, "
                         "roster declares {roster}")


def fixture_main(fixture):
    verifier = load_verifier()
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="model-switch-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(fixture))
        guard = LocalReads()
        guard.allowed.add(os.path.abspath(path))
        with guard, patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
            code = verifier.main()
    return code, output.getvalue()


class SharedRule(unittest.TestCase):
    """The rule lives in one constant and one function used by both paths."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.source = (ROOT / "scripts/verify-state").read_text()

    def test_manual_switch_models_constant(self):
        self.assertEqual(self.verifier.MANUAL_SWITCH_MODELS, (FABLE, OPUS))

    def test_rule_covers_exactly_the_five_project_orchestrators(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        allowed = {p["name"] for p in roster["profiles"]
                   if self.verifier.manual_model_switch_allowed(p)}
        self.assertEqual(allowed, set(ORCHESTRATORS))

    def test_one_shared_function_serves_both_paths(self):
        # Definition plus exactly two call sites: the fixture path and the live path.
        self.assertEqual(self.source.count("check_model_observation("), 3)
        for call_site in ('check_model_observation(errors, warnings, name, profile, models[name],',
                          'check_model_observation(errors, warnings, name, profile,'):
            self.assertIn(call_site, self.source)


class FixtureMode(unittest.TestCase):
    """Real verifier main() under the no-command/no-network/worktree-only guard."""

    @classmethod
    def setUpClass(cls):
        cls.clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        assert all(cls.clean["profile_models"][name] == FABLE for name in ORCHESTRATORS)

    def observed(self, observed, providers=None):
        fixture = copy.deepcopy(self.clean)
        fixture["profile_models"].update(observed)
        for name, provider in (providers or {}).items():
            fixture["profile_providers"][name] = provider
        return fixture_main(fixture)

    def test_clean_fixture_has_no_manual_model_switch_line(self):
        code, output = fixture_main(copy.deepcopy(self.clean))
        self.assertEqual(code, 0, output)
        self.assertNotIn("manual model switch", output)

    def test_one_orchestrator_on_opus_is_accepted_with_one_warning(self):
        code, output = self.observed({"harness-orchestrator": OPUS})
        self.assertEqual(code, 0, output)
        self.assertNotIn("model drift", output)
        warning = MANUAL_SWITCH_WARNING.format(
            name="harness-orchestrator", observed=OPUS, roster=FABLE)
        self.assertEqual(output.count(f"WARN: {warning}"), 1)
        self.assertEqual(output.count("WARN: manual model switch"), 1)

    def test_all_five_orchestrators_on_opus_give_five_warnings(self):
        code, output = self.observed({name: OPUS for name in ORCHESTRATORS})
        self.assertEqual(code, 0, output)
        self.assertNotIn("model drift", output)
        self.assertEqual(output.count("WARN: manual model switch"), 5)
        for name in ORCHESTRATORS:
            self.assertIn(f"WARN: {MANUAL_SWITCH_WARNING.format(name=name, observed=OPUS, roster=FABLE)}",
                          output)

    def test_orchestrator_on_any_other_model_fails(self):
        for name, model in (("jss-orchestrator", "claude-haiku-5-5"),
                            ("harness-orchestrator", "gpt-6.1-sol")):
            with self.subTest(name=name, model=model):
                code, output = self.observed({name: model})
                self.assertEqual(code, 1, output)
                self.assertTrue(any(
                    line.startswith(f"FAIL: model drift {name}: expected {FABLE} or {OPUS}")
                    for line in output.splitlines()), output)
                self.assertNotIn("manual model switch", output)

    def test_other_profiles_keep_the_baseline_comparison(self):
        for name in ("default", "advisor", "harness-worker"):
            roster_model = next(p["model"] for p in json.loads((ROOT / "roster.yaml").read_text())["profiles"]
                                if p["name"] == name)
            observed_model = FABLE if roster_model == OPUS else OPUS
            with self.subTest(name=name):
                code, output = self.observed({name: observed_model})
                self.assertEqual(code, 1, output)
                self.assertIn(f"FAIL: model drift {name}: expected {roster_model}, "
                              f"actual {observed_model}", output)
                self.assertNotIn("manual model switch", output)

    def test_orchestrator_model_switch_does_not_mask_provider_drift(self):
        code, output = self.observed({"harness-orchestrator": OPUS},
                                     providers={"harness-orchestrator": "anthropic"})
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: provider drift harness-orchestrator: expected claude-subscription, "
                      "actual anthropic", output)
        self.assertIn(f"WARN: {MANUAL_SWITCH_WARNING.format(name='harness-orchestrator', observed=OPUS, roster=FABLE)}",
                      output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
