#!/usr/bin/env python3
"""The five <board>-reviewer-glm profiles of card t_cca306ca (repository only).

Offline checks of tracked repository files and fixture-mode verification only:
no live profile, board, network or model observation, and no write under
/Users/chanbla11mit/.hermes. The card declares the five GLM reviewer profiles in
roster.yaml, scripts/verify-state, snapshots/sanitized-current-state.yaml and the
regenerated fixtures; a later deployment card changes the live profiles.
"""
from contextlib import redirect_stdout
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "roster.yaml"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
VERIFY = ROOT / "scripts/verify-state"
FIXTURES = ROOT / "tests/fixtures"

# Board -> (profile prefix, board). The GLM reviewer of a board is <prefix>-reviewer-glm.
FLEETS = {"jobcron": "jobcron", "cha-pt": "chapt", "harness": "harness",
          "jss-genr": "jss", "anki": "anki"}
GLM_REVIEWERS = ("jobcron-reviewer-glm", "chapt-reviewer-glm", "harness-reviewer-glm",
                 "jss-reviewer-glm", "anki-reviewer-glm")
# The five names in the order of the dispatch lists: appended after the third GLM workers.
GLM_REVIEWERS_IN_DISPATCH_ORDER = GLM_REVIEWERS
# The fixtures of the card and their one expected FAIL line.
CARD_FIXTURES = (
    ("glm-reviewer-jev-plugin-missing.yaml",
     "plugin drift harness-reviewer-glm: required jev not enabled (actual None)"),
    ("glm-reviewer-skill-missing.yaml",
     "GLM reviewer skill missing harness-reviewer-glm: sdlc-review is not installed"),
    ("glm-reviewer-dispatch-missing.yaml",
     "GLM reviewer missing from dispatch_profiles: harness-reviewer-glm"),
    ("glm-reviewer-model-drift.yaml",
     "model drift harness-reviewer-glm: expected glm-5.3, actual claude-opus-5-5"),
    ("launch-agent-not-loaded.yaml",
     "LaunchAgent com.nous.hermes-jev-peak-hold is not loaded: the pass of a card from "
     "the GLM reviewer to the independent reviewer of a board needs this LaunchAgent"),
)


def load(path):
    return json.loads(Path(path).read_text())


def load_verifier():
    spec = importlib.util.spec_from_loader(
        "verify_state", importlib.machinery.SourceFileLoader("verify_state", str(VERIFY)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quiet(function, *args, **kwargs):
    errors = []
    with redirect_stdout(io.StringIO()):
        function(errors, *args, **kwargs)
    return errors


def fail_lines(output):
    return [line[len("FAIL: "):] for line in output.splitlines() if line.startswith("FAIL: ")]


def run_fixture(path):
    result = subprocess.run([sys.executable, str(VERIFY), "--fixture", str(path)],
                            text=True, capture_output=True)
    return result.returncode, result.stdout + result.stderr


class Roster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROSTER)
        cls.profiles = {p["name"]: p for p in cls.roster["profiles"]}
        cls.names = [p["name"] for p in cls.roster["profiles"]]

    def test_each_glm_reviewer_entry(self):
        for board, prefix in FLEETS.items():
            name, reviewer = f"{prefix}-reviewer-glm", f"{prefix}-reviewer"
            with self.subTest(profile=name):
                self.assertIn(name, self.profiles)
                entry = self.profiles[name]
                self.assertEqual(entry["role"], "project GLM reviewer")
                self.assertEqual((entry["model"], entry["provider"]), ("glm-5.3", "zai"))
                self.assertTrue(entry["installed"])
                self.assertTrue(entry["dispatch_eligible"])
                self.assertTrue(entry["in_dispatch_pool"])
                self.assertEqual(entry["lifecycle"], "project-active")
                self.assertEqual(entry["concurrency_limit"], 1)
                self.assertEqual(entry["modes"], self.profiles[reviewer]["modes"])
                self.assertEqual(entry["toolsets"], "review")
                self.assertTrue(entry["credential_required"])
                self.assertIsNone(entry["credential_present"])
                self.assertEqual(entry["required_plugins"], ["jev"])
                self.assertEqual(entry["installed_disabled_plugins"], [])
                for field in ("auxiliary_models", "fallback_providers", "auxiliary_fallback_chain"):
                    self.assertNotIn(field, entry)

    def test_entry_placement(self):
        # Each GLM reviewer is listed directly after the third GLM worker of its board,
        # and the third GLM worker is the last GLM worker of the board.
        for board, prefix in FLEETS.items():
            anchor = f"{prefix}-worker-glm-3"
            with self.subTest(prefix=prefix):
                self.assertEqual(self.names[self.names.index(anchor) + 1], f"{prefix}-reviewer-glm")

    def test_the_lists_that_name_every_glm_worker(self):
        self.assertEqual(self.roster["approval_policy"]["profiles"], self.names)
        allowlist = self.roster["project_dispatch_allowlist"]
        for name in GLM_REVIEWERS:
            self.assertIn(name, self.roster["approval_policy"]["profiles"])
            self.assertIn(name, allowlist)
        self.assertEqual(allowlist[-5:], list(GLM_REVIEWERS_IN_DISPATCH_ORDER))

    def test_glm_reviewer_profile_settings(self):
        groups = list(self.roster)
        settings = self.roster["glm_reviewer_profile_settings"]
        self.assertEqual(settings["profiles"], list(GLM_REVIEWERS))
        self.assertEqual(settings["settings"], {"agent.reasoning_effort": "max"})
        # Placed directly after glm_worker_reasoning_effort_settings.
        self.assertEqual(groups[groups.index("glm_worker_reasoning_effort_settings") + 1],
                         "glm_reviewer_profile_settings")

    def test_profile_souls_names_four_glm_reviewers(self):
        # Card t_92a5f02e added the SOUL entries of the GLM reviewers whose board's reviewer has an
        # entry; jobcron-reviewer-glm has none, as jobcron-reviewer has none
        # (tests/test_glm_reviewer_souls.py).
        self.assertEqual([name for name in self.roster["profile_souls"] if name in GLM_REVIEWERS],
                         ["chapt-reviewer-glm", "harness-reviewer-glm", "jss-reviewer-glm", "anki-reviewer-glm"])


class Verifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.roster = load(ROSTER)

    def test_constants(self):
        self.assertEqual(self.verifier.PROJECT_GLM_REVIEWERS, {
            "jobcron": "jobcron-reviewer-glm", "cha-pt": "chapt-reviewer-glm",
            "harness": "harness-reviewer-glm", "jss-genr": "jss-reviewer-glm",
            "anki": "anki-reviewer-glm"})
        self.assertEqual(self.verifier.GLM_REVIEWER_ROLE, "project GLM reviewer")
        self.assertEqual(self.verifier.glm_reviewer_profiles(), GLM_REVIEWERS)
        self.assertEqual(self.verifier.JEV_PEAK_HOLD_LABEL, "com.nous.hermes-jev-peak-hold")
        self.assertEqual(self.verifier.GLM_REVIEWER_SKILL, "sdlc-review")
        self.assertEqual(self.verifier.GLM_REVIEWER_TOOLSETS,
                         ["browser", "clarify", "code_execution", "file", "memory", "skills",
                          "terminal", "todo", "vision", "web"])
        for assignees, prefix in ((self.verifier.CHAPT_ASSIGNEES, "chapt"),
                                  (self.verifier.HARNESS_ASSIGNEES, "harness"),
                                  (self.verifier.JSS_ASSIGNEES, "jss"),
                                  (self.verifier.ANKI_ASSIGNEES, "anki")):
            with self.subTest(prefix=prefix):
                self.assertIn(f"{prefix}-reviewer-glm", assignees)

    def test_the_glm_reviewers_are_outside_model_policy_by_role(self):
        self.assertNotIn(self.verifier.GLM_REVIEWER_ROLE, self.verifier.MODEL_POLICY_BY_ROLE)
        self.assertEqual(quiet(self.verifier.check_model_policy, self.roster), [])
        roster = json.loads(json.dumps(self.roster))
        entry = next(p for p in roster["profiles"] if p["name"] == "harness-reviewer-glm")
        entry.update(model="claude-opus-5-5", provider="claude-subscription")
        self.assertEqual(quiet(self.verifier.check_model_policy, roster), [
            "roster model policy drift harness-reviewer-glm: expected glm-5.3 on zai, "
            "declared claude-opus-5-5 on claude-subscription"])

    def test_glm_reviewer_profile_checks(self):
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_profiles, self.roster), [])
        roster = json.loads(json.dumps(self.roster))
        entry = next(p for p in roster["profiles"] if p["name"] == "harness-reviewer-glm")
        entry["toolsets"] = "implementation"
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_profiles, roster), [
            "GLM reviewer toolsets drift harness-reviewer-glm: expected 'review', "
            "declared 'implementation'"])
        roster = json.loads(json.dumps(self.roster))
        entry = next(p for p in roster["profiles"] if p["name"] == "harness-reviewer-glm")
        entry["modes"] = ["project-isolated", "harness", "extra"]
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_profiles, roster), [
            "GLM reviewer modes drift harness-reviewer-glm: expected the modes of "
            "harness-reviewer, declared ['project-isolated', 'harness', 'extra']"])

    def test_the_glm_reviewers_are_jev_profiles(self):
        # 41 profiles: the 21 Claude subscription profiles, the 15 GLM workers and the
        # five GLM reviewers (card t_cca306ca).
        self.assertEqual(len(set(self.verifier.jev_required_profiles())), 41)
        self.assertEqual(set(self.verifier.glm_reviewer_profiles()), set(GLM_REVIEWERS))
        self.assertEqual(quiet(self.verifier.check_jev_plugin_declarations, self.roster), [])

    def test_the_settings_group_is_checked(self):
        merged = {}
        for group in (self.roster["managed_profile_settings"],
                      self.roster["orchestrator_profile_settings"],
                      self.roster["claude_worker_profile_settings"],
                      self.roster["glm_worker_reasoning_effort_settings"],
                      self.roster["glm_reviewer_profile_settings"]):
            for profile in group["profiles"]:
                merged.setdefault(profile, {}).update(group["settings"])
        reader = lambda profile, key: merged.get(profile, {}).get(key)
        fleets = load(SNAPSHOT)["project_isolation"]
        roster_profiles = {p["name"]: p for p in self.roster["profiles"]}
        self.assertEqual(quiet(self.verifier.check_managed_setting_groups, self.roster, fleets,
                               roster_profiles, reader), [])
        wrong = lambda profile, key: (
            "high" if (profile.endswith("-reviewer-glm") and key == "agent.reasoning_effort")
            else merged.get(profile, {}).get(key))
        self.assertEqual(quiet(self.verifier.check_managed_setting_groups, self.roster, fleets,
                               roster_profiles, wrong), [
            "managed setting drift jobcron-reviewer-glm agent.reasoning_effort: expected 'max', "
            "actual 'high'",
            "managed setting drift chapt-reviewer-glm agent.reasoning_effort: expected 'max', "
            "actual 'high'",
            "managed setting drift harness-reviewer-glm agent.reasoning_effort: expected 'max', "
            "actual 'high'",
            "managed setting drift jss-reviewer-glm agent.reasoning_effort: expected 'max', "
            "actual 'high'",
            "managed setting drift anki-reviewer-glm agent.reasoning_effort: expected 'max', "
            "actual 'high'"])

    def test_dispatch_requires_each_glm_reviewer(self):
        fleets = load(SNAPSHOT)["project_isolation"]
        dispatch = load(SNAPSHOT)["kanban"]["dispatch_profiles"]
        check = self.verifier.check_fleet_dispatch
        self.assertEqual(quiet(check, "kanban.dispatch_profiles", fleets, dispatch), [])
        for name in GLM_REVIEWERS:
            with self.subTest(missing=name):
                listing = [entry for entry in dispatch if entry != name]
                self.assertEqual(quiet(check, "kanban.dispatch_profiles", fleets, listing),
                                 [f"GLM reviewer missing from kanban.dispatch_profiles: {name}"])

    def test_a_card_assigned_to_the_glm_reviewer_is_valid(self):
        # The Reviewer EXACT line still names the independent reviewer; the GLM reviewer
        # of the board is an allowed assignee (the first reviewer of the review pipeline).
        def harness_card(assignee, reviewer="harness-reviewer"):
            body = ("Repository /Users/chanbla11mit/hermes-local-harness ONLY.\n"
                    f"Baseline EXACT {'a' * 40}.\nAssigned worker EXACT {assignee}.\n"
                    f"Reviewer EXACT {reviewer}.\n## Tests\n- `python3 tests/test_x.py`\n")
            return {"id": "t_gr", "board": "harness", "body": body, "assignee": assignee,
                    "workspace_kind": "worktree",
                    "workspace_path": "/Users/chanbla11mit/hermes-local-harness/.worktrees/t_gr"}
        for assignee in ("harness-reviewer-glm", "harness-worker-glm-1", "harness-worker"):
            with self.subTest(assignee=assignee):
                self.assertEqual(
                    quiet(self.verifier.check_harness_card_contract, [harness_card(assignee)]), [])
        # The GLM reviewer of another board is not an allowed assignee.
        self.assertEqual(
            quiet(self.verifier.check_harness_card_contract, [harness_card("chapt-reviewer-glm")]),
            ["Harness card contract drift t_gr: Harness worker assignment invalid"])

    def test_the_launch_agent_and_skill_checks(self):
        message = (f"LaunchAgent com.nous.hermes-jev-peak-hold is not loaded: the pass of a card "
                   "from the GLM reviewer to the independent reviewer of a board needs this LaunchAgent")
        self.assertEqual(quiet(self.verifier.check_jev_peak_hold_agent, {"loaded": True}), [])
        self.assertEqual(quiet(self.verifier.check_jev_peak_hold_agent, {"loaded": False}), [message])
        self.assertEqual(quiet(self.verifier.check_jev_peak_hold_agent), [
            "incomplete fixture: missing required section 'jev_peak_hold_agent'"])
        skill_line = ("GLM reviewer skill missing harness-reviewer-glm: sdlc-review is not installed")
        observed = {name: True for name in GLM_REVIEWERS}
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_skills, observed), [])
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_skills, {**observed, "harness-reviewer-glm": False}),
                         [skill_line])
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_skills), [
            "incomplete fixture: missing required section 'glm_reviewer_skills'"])

    def test_glm_workers_of_board_excludes_the_glm_reviewers(self):
        for board in FLEETS:
            with self.subTest(board=board):
                self.assertNotIn(f"{FLEETS[board]}-reviewer-glm",
                                 self.verifier.glm_workers_of_board(self.roster, board))


class Snapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load(SNAPSHOT)
        cls.roster = load(ROSTER)

    def test_the_snapshot_carries_the_five_profiles_and_lists(self):
        self.assertEqual(self.snapshot["profiles"], [p["name"] for p in self.roster["profiles"]])
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])
        self.assertEqual(self.snapshot["kanban"]["dispatch_profiles"],
                         self.roster["project_dispatch_allowlist"])
        for name in GLM_REVIEWERS:
            self.assertIn(name, self.snapshot["profiles"])
            self.assertIn(name, self.snapshot["approvals"]["profiles"])
            self.assertIn(name, self.snapshot["kanban"]["dispatch_profiles"])

    def test_the_snapshot_carries_the_launch_agent_value(self):
        self.assertEqual(self.snapshot["jev_peak_hold_agent"], {"loaded": True})


class Fixtures(unittest.TestCase):
    def test_the_clean_fixture_passes(self):
        code, output = run_fixture(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: desired state matches observed state", output)

    def test_each_new_fixture_fails_with_its_expected_line(self):
        for name, expected in CARD_FIXTURES:
            with self.subTest(name=name):
                code, output = run_fixture(FIXTURES / name)
                self.assertEqual(code, 1, output)
                self.assertNotIn("OK: desired state matches observed state", output)
                lines = fail_lines(output)
                # The dispatch fixture also prints the generic dispatch drift line first,
                # as the GLM worker fixture of card t_f4ce916d does.
                if name == "glm-reviewer-dispatch-missing.yaml":
                    self.assertEqual(len(lines), 2)
                    self.assertTrue(lines[0].startswith("dispatch drift: expected "))
                    self.assertEqual(lines[1], expected)
                else:
                    self.assertEqual(lines, [expected])


if __name__ == "__main__":
    unittest.main()
