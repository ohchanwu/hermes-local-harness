#!/usr/bin/env python3
"""Roster/profile reconciliation of 2026-10-19 (t_4a2ded12).

Fixture, temporary-tree and in-memory checks only: no live profile, board or
model observation, and the repository roster.yaml is never written.
"""
from contextlib import redirect_stdout
import copy
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier

# The owner model policy as verify-state records it; the roster is checked against it, not copied.
_POLICY = load_verifier()
OPUS = _POLICY.MODEL_POLICY_BY_ROLE["implementation"]
FABLE = _POLICY.MODEL_POLICY_BY_ROLE["independent reviewer"]
CLAUDE = _POLICY.MODEL_POLICY_PROVIDER
GLM = tuple(f"{prefix}-worker-glm-{n}" for prefix in ("jobcron", "chapt", "harness", "jss") for n in (1, 2))
GPT_ERA = ("reviewer-sol", "worker-flash-1", "worker-flash-2", "worker-flash-3", "worker-luna-1",
           "worker-luna-2", "worker-terra-1", "worker-glm-full", "worker-sol", "worker-astra",
           "worker-terra-2")
PROJECT_DISPATCH = ["jobcron-worker", "jobcron-reviewer", "chapt-worker", "chapt-reviewer",
                    "harness-worker", "harness-reviewer", "jss-worker", "jss-reviewer",
                    "harness-worker-2", "chapt-worker-2", "jobcron-worker-2", "jss-worker-2"]
HARNESS = "/Users/chanbla11mit/hermes-local-harness"


def load(path):
    return json.loads(Path(path).read_text())


def quiet(function, *args):
    errors = []
    with redirect_stdout(io.StringIO()):
        function(errors, *args)
    return errors


def fixture_main(data):
    """Run the real verifier main() on an in-memory fixture under the worktree guard."""
    with tempfile.TemporaryDirectory(prefix="reconcile-roster-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(data))
        verifier = load_verifier()
        guard = LocalReads()
        guard.allowed.add(os.path.abspath(path))
        output = io.StringIO()
        with guard, patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
            code = verifier.main()
    return code, output.getvalue()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")
        cls.profiles = {p["name"]: p for p in cls.roster["profiles"]}
        cls.clean = load(ROOT / "tests/fixtures/clean.yaml")


class ModelPolicy(Base):
    """Item 1: expectations follow the owner model policy; out-of-policy live stays red."""

    def test_live_corrected_expectations(self):
        for name in ("default", "jobcron-orchestrator", "jobcron-worker", "chapt-orchestrator",
                     "chapt-worker", "harness-orchestrator", "harness-worker"):
            self.assertEqual((self.profiles[name]["model"], self.profiles[name]["provider"]), (OPUS, CLAUDE))
        for name in ("advisor", "jobcron-reviewer", "chapt-reviewer", "harness-reviewer"):
            self.assertEqual((self.profiles[name]["model"], self.profiles[name]["provider"]), (FABLE, CLAUDE))

    def test_every_non_retired_profile_is_in_policy(self):
        self.assertEqual(quiet(self.verifier.check_model_policy, self.roster), [])
        for profile in self.roster["profiles"]:
            if profile["lifecycle"] != "retired":
                with self.subTest(profile=profile["name"]):
                    want = FABLE if "reviewer" in profile["role"] or profile["role"] == "advisor" else OPUS
                    self.assertEqual((profile["model"], profile["provider"]), (want, CLAUDE))

    def test_out_of_policy_declaration_fails(self):
        roster = copy.deepcopy(self.roster)
        entry = next(p for p in roster["profiles"] if p["name"] == "harness-worker")
        entry.update(model="gpt-6.1-sol", provider="openai-codex")
        self.assertEqual(quiet(self.verifier.check_model_policy, roster), [
            f"roster model policy drift harness-worker: expected {OPUS} on {CLAUDE}, "
            "declared gpt-6.1-sol on openai-codex"])
        reviewer = next(p for p in roster["profiles"] if p["name"] == "jss-reviewer")
        reviewer["model"] = OPUS  # a reviewer on Opus is outside policy too
        self.assertIn(f"roster model policy drift jss-reviewer: expected {FABLE} on "
                      f"{CLAUDE}, declared {OPUS} on {CLAUDE}",
                      quiet(self.verifier.check_model_policy, roster))

    def test_live_model_outside_policy_still_fails(self):
        data = copy.deepcopy(self.clean)
        data["profile_models"]["harness-worker"] = "gpt-6.1-sol"
        data["profile_providers"]["chapt-reviewer"] = "openai-codex"
        code, output = fixture_main(data)
        self.assertEqual(code, 1, output)
        self.assertIn(f"FAIL: model drift harness-worker: expected {self.profiles['harness-worker']['model']}, "
                      "actual gpt-6.1-sol", output)
        self.assertIn(f"FAIL: provider drift chapt-reviewer: expected {self.profiles['chapt-reviewer']['provider']}, "
                      "actual openai-codex", output)


class RetiredProfiles(Base):
    """Items 2 and 3: retired lifecycle, never dispatchable."""

    def test_glm_and_gpt_era_profiles_are_declared_retired(self):
        for name in (*GLM, *GPT_ERA):
            with self.subTest(profile=name):
                entry = self.profiles[name]
                self.assertEqual(entry["lifecycle"], "retired")
                self.assertEqual(entry["retired_on"], "2026-10-18")
                self.assertFalse(entry["dispatch_eligible"])
                self.assertFalse(entry["in_dispatch_pool"])
        # Retired GLM workers keep the GLM target of scripts/switch-profile-model (no model name copied here).
        loader = importlib.machinery.SourceFileLoader("switch_profile_model_glm_target",
                                                      str(ROOT / "scripts/switch-profile-model"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None
        switch = importlib.util.module_from_spec(spec)
        loader.exec_module(switch)
        glm_provider, _, glm_model, _ = switch.TARGETS["glm"]
        for name in GLM:
            self.assertEqual((self.profiles[name]["model"], self.profiles[name]["provider"]), (glm_model, glm_provider))
            self.assertEqual(self.profiles[name]["lifecycle_before_retirement"], "project-active")
        self.assertEqual(set(self.verifier.roster_retired(self.roster)), set(GLM) | set(GPT_ERA))
        self.assertEqual(quiet(self.verifier.check_retired_profiles, self.roster), [])

    def test_no_retired_profile_in_any_pool(self):
        retired = set(GLM) | set(GPT_ERA)
        pool = self.roster["dispatch_pool"]
        self.assertEqual(pool, {"implementation_allowlist": [], "dispatch_allowlist": [],
                                "reviewer_outside_budget": None})
        self.assertEqual(self.roster["project_dispatch_allowlist"], PROJECT_DISPATCH)
        self.assertEqual(self.snapshot["kanban"]["dispatch_profiles"], PROJECT_DISPATCH)
        self.assertEqual(retired & set(self.snapshot["kanban"]["dispatch_profiles"]), set())
        self.assertEqual(self.roster["approval_policy"]["profiles"], list(self.profiles))
        self.assertEqual(self.snapshot["profiles"], list(self.profiles))

    def test_retired_profile_marked_dispatchable_fails(self):
        roster = copy.deepcopy(self.roster)
        next(p for p in roster["profiles"] if p["name"] == "harness-worker-glm-1")["dispatch_eligible"] = True
        self.assertEqual(quiet(self.verifier.check_retired_profiles, roster), [
            "retired profile dispatchable harness-worker-glm-1: dispatch_eligible and in_dispatch_pool must be false"])
        roster = copy.deepcopy(self.roster)
        next(p for p in roster["profiles"] if p["name"] == "worker-astra")["in_dispatch_pool"] = True
        self.assertEqual(quiet(self.verifier.check_retired_profiles, roster), [
            "retired profile dispatchable worker-astra: dispatch_eligible and in_dispatch_pool must be false"])

    def test_retired_profile_in_a_pool_fails(self):
        roster = copy.deepcopy(self.roster)
        roster["project_dispatch_allowlist"].append("jss-worker-glm-2")
        roster["dispatch_pool"]["dispatch_allowlist"].append("reviewer-sol")
        roster["project_fleets"]["harness"]["workers"].append("harness-worker-glm-1")
        errors = quiet(self.verifier.check_retired_profiles, roster)
        self.assertIn("retired profile back in project_dispatch_allowlist: jss-worker-glm-2", errors)
        self.assertIn("retired profile back in dispatch_pool.dispatch_allowlist: reviewer-sol", errors)
        self.assertIn("retired profile back in project fleet harness: harness-worker-glm-1", errors)

    def test_glm_lifecycle_cannot_be_dropped(self):
        roster = copy.deepcopy(self.roster)
        entry = next(p for p in roster["profiles"] if p["name"] == "chapt-worker-glm-2")
        entry["lifecycle"] = "project-active"
        self.assertIn("retired profile lifecycle drift chapt-worker-glm-2: expected retired",
                      quiet(self.verifier.check_retired_profiles, roster))
        roster["profiles"] = [p for p in roster["profiles"] if p["name"] != "chapt-worker-glm-2"]
        self.assertIn("retired profile lifecycle drift chapt-worker-glm-2: expected retired",
                      quiet(self.verifier.check_retired_profiles, roster))

    def test_retired_profile_back_in_observed_dispatch_fails(self):
        for name in ("worker-astra", "harness-worker-glm-2"):
            data = copy.deepcopy(self.clean)
            data["dispatch_profiles"].append(name)
            code, output = fixture_main(data)
            with self.subTest(profile=name):
                self.assertEqual(code, 1, output)
                self.assertIn(f"FAIL: retired profile back in dispatch_profiles: {name}", output)

    def test_retired_glm_observed_installed_is_green(self):
        self.assertEqual({n: self.clean["profile_models"][n] for n in GLM},
                         {n: self.profiles[n]["model"] for n in GLM})
        code, output = fixture_main(self.clean)
        self.assertEqual(code, 0, output)

    def test_terminal_assignee_is_explicitly_retired(self):
        policy = self.roster["terminal_retry"]
        self.assertEqual((policy["terminal_assignee"], policy["terminal_assignee_lifecycle"]),
                         ("worker-astra", "retired"))
        self.assertEqual(quiet(self.verifier.check_terminal_retry_policy, self.roster), [])
        roster = copy.deepcopy(self.roster)
        del roster["terminal_retry"]["terminal_assignee_lifecycle"]
        self.assertEqual(quiet(self.verifier.check_terminal_retry_policy, roster),
                         ["terminal retry terminal assignee lifecycle drift"])


def harness_card(**overrides):
    body = (f"Repository {HARNESS} ONLY.\nBaseline EXACT {'a' * 40}.\n"
            "## Tests\n- `python3 tests/test_x.py`\nReviewer EXACT harness-reviewer.\n")
    card = {"id": "t_unclaimed", "board": "harness", "body": body, "assignee": "harness-worker",
            "workspace_kind": "worktree", "workspace_path": HARNESS, "status": "blocked",
            "started_at": None, "runs": []}
    card.update(overrides)
    return card


class UnclaimedCards(Base):
    """Item 4: the repository root is accepted only for a never-claimed card."""

    MISMATCH = "Harness card contract drift t_unclaimed: isolated worktree mismatch"

    def check(self, card):
        return quiet(self.verifier.check_harness_card_contract, [card])

    def test_never_claimed_root_workspace_is_accepted(self):
        for status in ("triage", "todo", "ready", "blocked"):
            with self.subTest(status=status):
                self.assertEqual(self.check(harness_card(status=status)), [])

    def test_exact_worktree_is_accepted_after_claim(self):
        card = harness_card(status="running", started_at=1, runs=[{"id": 1, "status": "running"}],
                            workspace_path=f"{HARNESS}/.worktrees/t_unclaimed")
        self.assertEqual(self.check(card), [])

    def test_claimed_card_with_root_workspace_fails(self):
        cases = {
            "running": harness_card(status="running", started_at=1, runs=[{"id": 1}]),
            "review": harness_card(status="review", started_at=1, runs=[{"id": 1}]),
            "done": harness_card(status="done", started_at=1, runs=[{"id": 1}]),
            "ready-after-crash": harness_card(status="ready", started_at=1, runs=[{"id": 1, "status": "crashed"}]),
            "blocked-with-run": harness_card(runs=[{"id": 1}]),
            "running-no-runs": harness_card(status="running"),
            "started": harness_card(started_at=1),
            "runs-unobserved": harness_card(runs=None),
        }
        for label, card in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.check(card), [self.MISMATCH])

    def test_other_wrong_workspaces_still_fail(self):
        for path in (f"{HARNESS}/.worktrees/t_other", "/Users/chanbla11mit/projects/jobcron", f"{HARNESS}/"):
            with self.subTest(path=path):
                self.assertEqual(self.check(harness_card(workspace_path=path)), [self.MISMATCH])
        self.assertEqual(self.check(harness_card(workspace_kind="scratch")), [self.MISMATCH])

    def test_shared_path_covers_jss_and_chapt(self):
        jss = "/Users/chanbla11mit/projects/jss-genr"
        body = (f"Repository {jss} ONLY.\nBaseline EXACT {'b' * 40}.\nCard kind EXACT repository.\n"
                "## Tests\n- `python3 tools/charcount.py x`\nReviewer EXACT jss-reviewer.\n")
        card = {"id": "t_j", "board": "jss-genr", "body": body, "assignee": "jss-worker",
                "workspace_kind": "worktree", "workspace_path": jss, "status": "todo", "runs": []}
        self.assertEqual(quiet(self.verifier.check_jss_card_contract, [card]), [])
        card.update(status="running", runs=[{"id": 2}])
        self.assertEqual(quiet(self.verifier.check_jss_card_contract, [card]),
                         ["jss-genr card contract drift t_j: isolated worktree mismatch"])
        chapt = "/Users/chanbla11mit/projects/cha-pt"
        body = (f"Repository {chapt} ONLY. Baseline EXACT {'c' * 40}. Reviewer EXACT chapt-reviewer.\n"
                "## Tests\n- `go test ./...`\n")
        card = {"id": "t_c", "body": body, "assignee": "chapt-worker", "workspace_kind": "worktree",
                "workspace_path": chapt, "status": "ready", "runs": []}
        self.assertEqual(quiet(self.verifier.check_chapt_card_contract, [card]), [])
        card["runs"] = [{"id": 3}]
        self.assertEqual(quiet(self.verifier.check_chapt_card_contract, [card]),
                         ["Cha PT card contract drift t_c: isolated worktree mismatch"])

    def test_observers_pass_runs_through(self):
        listing = json.dumps([{"id": "t_unclaimed", "status": "blocked"}])
        shown = json.dumps({"task": {k: v for k, v in harness_card().items() if k not in ("board", "runs")},
                            "comments": [], "runs": []})

        class Result:
            def __init__(self, stdout):
                self.returncode, self.stdout = 0, stdout

        def runner(*args):
            if "list" in args:
                return Result(listing if "harness" in args else "[]")
            return Result(shown)

        errors = []
        with redirect_stdout(io.StringIO()):
            cards = self.verifier.observe_open_project_cards(errors, runner)
        self.assertEqual(errors, [])
        self.assertEqual([card["runs"] for card in cards], [[]])
        self.assertEqual(quiet(self.verifier.check_harness_card_contract, cards), [])


class SwitchKeepsRosterInStep(unittest.TestCase):
    """Item 5: switch-profile-model updates a roster copy; dry-run writes nothing."""

    def setUp(self):
        loader = importlib.machinery.SourceFileLoader("switch_profile_model_roster",
                                                      str(ROOT / "scripts/switch-profile-model"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None
        self.switch = importlib.util.module_from_spec(spec)
        loader.exec_module(self.switch)
        tmp = tempfile.TemporaryDirectory(prefix="switch-roster-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "hermes-home"
        (self.home / "profiles/jss-reviewer").mkdir(parents=True)
        (self.home / "profiles/jss-reviewer/config.yaml").write_text("model:\n  default: x\n")
        (self.home / "config.yaml").write_text("kanban:\n  dispatch_profiles: []\n")
        self.fake = self.root / "hermes"
        self.fake.write_text(f"#!{sys.executable}\n")
        self.fake.chmod(0o700)
        self.roster = self.root / "roster.yaml"
        self.original = (ROOT / "roster.yaml").read_text()
        self.roster.write_text(self.original)

    def run_switch(self, *args):
        with redirect_stdout(io.StringIO()) as out:
            code = self.switch.main(["--home-root", str(self.home), "--hermes", str(self.fake),
                                     "--roster", str(self.roster), "--profile", "jss-reviewer", *args])
        return code, out.getvalue()

    def entry(self):
        return next(p for p in load(self.roster)["profiles"] if p["name"] == "jss-reviewer")

    def test_dry_run_shows_live_and_roster_changes_and_writes_nothing(self):
        before = self.entry()
        code, out = self.run_switch("--to", "gpt", "--model", "gpt-6.1-sol", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("config set model.default gpt-6.1-sol", out)
        self.assertIn(f"jss-reviewer model {before['model']} -> gpt-6.1-sol, provider {before['provider']} -> "
                      "openai-codex (dry run: nothing written)", out)
        self.assertEqual(self.roster.read_text(), self.original)
        self.assertEqual(sorted(p.name for p in (self.home / "profiles/jss-reviewer").iterdir()), ["config.yaml"])

    def test_switch_updates_roster_and_out_of_policy_switch_is_then_red(self):
        code, out = self.run_switch("--to", "gpt", "--model", "gpt-6.1-sol")
        self.assertEqual(code, 0)
        self.assertEqual((self.entry()["model"], self.entry()["provider"]), ("gpt-6.1-sol", "openai-codex"))
        self.assertIn("commit the roster.yaml change", out)
        # The verifier refuses to treat an out-of-policy roster as the new expectation.
        self.assertEqual(quiet(load_verifier().check_model_policy, load(self.roster)), [
            f"roster model policy drift jss-reviewer: expected {FABLE} on {CLAUDE}, "
            "declared gpt-6.1-sol on openai-codex"])
        code, _ = self.run_switch("--to", "claude-fable")
        self.assertEqual(code, 0)
        self.assertEqual(self.roster.read_text(), self.original)
        self.assertEqual((ROOT / "roster.yaml").read_text(), self.original)

    def test_undeclared_profile_leaves_roster_alone(self):
        (self.home / "profiles/scratch-profile").mkdir(parents=True)
        (self.home / "profiles/scratch-profile/config.yaml").write_text("model:\n  default: x\n")
        with redirect_stdout(io.StringIO()) as out:
            code = self.switch.main(["--home-root", str(self.home), "--hermes", str(self.fake),
                                     "--roster", str(self.roster), "--profile", "scratch-profile",
                                     "--to", "claude-opus"])
        self.assertEqual(code, 0)
        self.assertIn("scratch-profile is not declared", out.getvalue())
        self.assertEqual(self.roster.read_text(), self.original)


class Fixtures(Base):
    """Item 6: regenerated fixtures keep their intended results."""

    def test_clean_is_green_and_reflects_the_roster(self):
        self.assertEqual(self.clean["profile_models"], {p["name"]: p["model"] for p in self.roster["profiles"]})
        self.assertEqual(self.clean["profile_providers"],
                         {p["name"]: p["provider"] for p in self.roster["profiles"]})
        self.assertEqual(self.clean["dispatch_profiles"], PROJECT_DISPATCH)
        code, output = fixture_main(self.clean)
        self.assertEqual(code, 0, output)
        self.assertNotIn("FAIL:", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
