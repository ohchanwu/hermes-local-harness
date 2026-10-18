#!/usr/bin/env python3
"""Offline source contract for the 2026-10-18 second Opus worker in every fleet.

Checks tracked repository text, desired state, pins and fixture-mode
verification only; no live profile, board, or model observation.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier

FLEETS = {"jobcron": "jobcron", "cha-pt": "chapt", "harness": "harness", "jss-genr": "jss"}
POOLS = {project: [f"{prefix}-worker", f"{prefix}-worker-2"] for project, prefix in FLEETS.items()}
SECOND = tuple(pool[1] for pool in POOLS.values())
# Live default-home kanban.dispatch_profiles order after the controller's 2026-10-18 change.
PROJECT_DISPATCH = [
    "jobcron-worker", "jobcron-reviewer", "chapt-worker", "chapt-reviewer",
    "harness-worker", "harness-reviewer", "jss-worker", "jss-reviewer",
    "harness-worker-2", "chapt-worker-2", "jobcron-worker-2", "jss-worker-2",
]
GLM = tuple(f"{prefix}-worker-glm-{n}" for prefix in FLEETS.values() for n in (1, 2))
GLM_NAME = re.compile(r"\b(?:jobcron|chapt|harness|jss)-worker-glm-\d\b")
RULE = ("Spread independent ready cards across the two workers; keep cards that touch the same files "
        "serialized or dependency-linked.")
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PROFILE_SKILLS = {
    prefix: ROOT / "policies/profile-skills" / f"{prefix}-orchestrator" / RELATIVE for prefix in FLEETS.values()
}
SHARED_SKILL = ROOT / "skills/multi-agent-coding-orchestrator/SKILL.md"
VERSIONS = {
    PROFILE_SKILLS["jobcron"]: "0.6.9-jobcron.4",
    PROFILE_SKILLS["chapt"]: "0.6.7-chapt.4",
    PROFILE_SKILLS["harness"]: "0.6.7-harness.3",
    PROFILE_SKILLS["jss"]: "0.6.7-jss.5",
    SHARED_SKILL: "0.6.10",
}
PINNED_WORKERS = ("chapt-worker", "harness-worker", "jss-worker")  # jobcron-worker has no tracked SOUL


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def soul(profile):
    return ROOT / "policies/profile-souls" / profile / "SOUL.md"


def quiet(function, *args, **kwargs):
    errors = []
    with redirect_stdout(io.StringIO()):
        function(errors, *args, **kwargs)
    return errors


def fixture_main(data):
    verifier = load_verifier()
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="second-worker-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(data))
        guard = LocalReads()
        guard.allowed.add(os.path.abspath(path))
        with guard, patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
            code = verifier.main()
    return code, output.getvalue()


class DesiredState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")
        cls.names = [profile["name"] for profile in cls.roster["profiles"]]
        cls.profiles = {profile["name"]: profile for profile in cls.roster["profiles"]}

    def test_second_worker_profile_clones_its_source_on_opus(self):
        for prefix in FLEETS.values():
            first, second = f"{prefix}-worker", f"{prefix}-worker-2"
            with self.subTest(profile=second):
                self.assertEqual(self.names.index(second), self.names.index(first) + 1)
                entry = self.profiles[second]
                self.assertEqual((entry["model"], entry["provider"]), ("claude-opus-5-5", "claude-subscription"))
                self.assertTrue(entry["dispatch_eligible"])
                self.assertTrue(entry["in_dispatch_pool"])
                expected = dict(self.profiles[first], name=second,
                                model="claude-opus-5-5", provider="claude-subscription")
                self.assertEqual(entry, expected)

    def test_every_list_names_both_workers(self):
        self.assertEqual(self.roster["approval_policy"]["profiles"], self.names)
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])
        self.assertEqual(self.snapshot["profiles"], self.names)
        self.assertEqual(self.snapshot["project_isolation"], self.roster["project_fleets"])
        for project, prefix in FLEETS.items():
            fleet = self.roster["project_fleets"][project]
            with self.subTest(project=project):
                self.assertEqual(fleet["worker"], f"{prefix}-worker")
                self.assertEqual(fleet["workers"], POOLS[project])
                self.assertEqual(fleet["reviewer"], f"{prefix}-reviewer")
        self.assertEqual(self.roster["project_dispatch_allowlist"], PROJECT_DISPATCH)
        dispatch = self.snapshot["kanban"]["dispatch_profiles"]
        self.assertEqual(dispatch[-len(PROJECT_DISPATCH):], PROJECT_DISPATCH)
        self.assertEqual(self.snapshot["kanban"]["max_in_progress_per_profile"], 1)
        self.assertEqual(self.roster["project_repair_policy"]["project_boards"], list(FLEETS))
        # The legacy default-board pool never held a project worker.
        for key in ("implementation_allowlist", "dispatch_allowlist"):
            for pool in POOLS.values():
                for name in pool:
                    self.assertNotIn(name, self.roster["dispatch_pool"][key])

    def test_skill_deployment_matrix_mirrors_the_source_worker(self):
        for entry in self.snapshot["skill"]["shared_skills"]:
            deploy = entry["deploy_profiles"]
            for prefix in FLEETS.values():
                with self.subTest(skill=entry["name"], fleet=prefix):
                    self.assertEqual(f"{prefix}-worker" in deploy, f"{prefix}-worker-2" in deploy)

    def test_no_glm_worker_reintroduced(self):
        for name in SECOND:
            self.assertIsNone(GLM_NAME.search(name))
        self.assertNotIn("worker-glm-", json.dumps(self.roster).replace("worker-glm-full", ""))
        for listing in (self.names, self.roster["project_dispatch_allowlist"],
                        self.snapshot["kanban"]["dispatch_profiles"], list(self.roster["profile_souls"])):
            self.assertEqual([name for name in listing if name in GLM], [])
        self.assertEqual(set(load_verifier().RETIRED_PROFILES), set(GLM))


class Verifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.roster = load(ROOT / "roster.yaml")
        cls.fleets = load(ROOT / "snapshots/sanitized-current-state.yaml")["project_isolation"]

    def test_constants(self):
        self.assertEqual(self.verifier.PROJECT_WORKER_POOLS, POOLS)
        for assignees, prefix in ((self.verifier.CHAPT_ASSIGNEES, "chapt"),
                                  (self.verifier.HARNESS_ASSIGNEES, "harness"),
                                  (self.verifier.JSS_ASSIGNEES, "jss")):
            self.assertEqual(assignees, {f"{prefix}-worker", f"{prefix}-worker-2", f"{prefix}-reviewer"})
        for profile in PINNED_WORKERS:
            self.assertEqual(self.verifier.PROFILE_SOUL_PATHS[f"{profile}-2"], {
                "source": f"policies/profile-souls/{profile}-2/SOUL.md",
                "live": f"/Users/chanbla11mit/.hermes/profiles/{profile}-2/SOUL.md"})
        for name in ("jobcron-worker", "jobcron-worker-2"):
            self.assertNotIn(name, self.verifier.PROFILE_SOUL_PATHS)

    def test_worker_pool_is_exactly_two(self):
        self.assertEqual(quiet(self.verifier.check_project_isolation, self.fleets, copy.deepcopy(self.fleets)), [])
        for label, mutate in (
                ("missing second worker", lambda pool: pool.pop()),
                ("unknown extra worker", lambda pool: pool.append("harness-worker-3")),
                ("renamed second worker", lambda pool: pool.__setitem__(1, "harness-worker-3")),
                ("swapped order", lambda pool: pool.reverse()),
                ("retired GLM worker", lambda pool: pool.__setitem__(1, "harness-worker-glm-1"))):
            fleets = copy.deepcopy(self.fleets)
            mutate(fleets["harness"]["workers"])
            with self.subTest(case=label):
                self.assertIn("project worker pool mapping malformed: harness",
                              quiet(self.verifier.check_project_isolation, fleets))

    def test_dispatch_must_list_both_workers_and_nothing_unknown(self):
        check = self.verifier.check_fleet_dispatch
        dispatch = load(ROOT / "snapshots/sanitized-current-state.yaml")["kanban"]["dispatch_profiles"]
        self.assertEqual(quiet(check, "kanban.dispatch_profiles", self.fleets, dispatch), [])
        self.assertEqual(quiet(check, "project_dispatch_allowlist", self.fleets, PROJECT_DISPATCH, exact=True), [])
        for name in SECOND:
            with self.subTest(missing=name):
                listing = [entry for entry in dispatch if entry != name]
                self.assertEqual(quiet(check, "kanban.dispatch_profiles", self.fleets, listing),
                                 [f"project fleet profile missing from kanban.dispatch_profiles: {name}"])
        self.assertEqual(
            quiet(check, "project_dispatch_allowlist", self.fleets, [*PROJECT_DISPATCH, "harness-worker-3"], exact=True),
            ["unexpected profile in project_dispatch_allowlist: harness-worker-3"])

    def test_card_contracts_accept_the_second_worker_only(self):
        base = {"board": "harness", "workspace_kind": "worktree"}
        body = ("Repository /Users/chanbla11mit/hermes-local-harness ONLY.\n"
                f"Baseline EXACT {'a' * 40}.\n## Tests\n- `python3 tests/test_x.py`\n"
                "Reviewer EXACT harness-reviewer.\n")
        for assignee, ok in (("harness-worker-2", True), ("harness-worker-3", False), ("chapt-worker-2", False)):
            card = dict(base, id="t_w2", body=body, assignee=assignee,
                        workspace_path="/Users/chanbla11mit/hermes-local-harness/.worktrees/t_w2")
            with self.subTest(assignee=assignee):
                errors = quiet(self.verifier.check_harness_card_contract, [card])
                self.assertEqual(errors == [], ok, errors)
        jss_body = ("Repository /Users/chanbla11mit/projects/jss-genr ONLY.\n"
                    f"Baseline EXACT {'b' * 40}.\nCard kind EXACT repository.\n"
                    "## Tests\n- `make -C resume qa`\nReviewer EXACT jss-reviewer.\n")
        jss_card = {"id": "t_j2", "board": "jss-genr", "body": jss_body, "assignee": "jss-worker-2",
                    "workspace_kind": "worktree", "workspace_path": "/Users/chanbla11mit/projects/jss-genr/.worktrees/t_j2"}
        self.assertEqual(quiet(self.verifier.check_jss_card_contract, [jss_card]), [])


class FixtureMode(unittest.TestCase):
    """Real verifier main() under the no-command/no-network/worktree-only guard."""

    @classmethod
    def setUpClass(cls):
        cls.clean = load(ROOT / "tests/fixtures/clean.yaml")

    def test_clean_observes_both_workers_and_is_green(self):
        for name in SECOND:
            self.assertEqual(self.clean["profile_models"][name], "claude-opus-5-5")
            self.assertIn(name, self.clean["dispatch_profiles"])
        code, output = fixture_main(self.clean)
        self.assertEqual(code, 0, output)
        self.assertNotIn("FAIL:", output)

    def test_second_worker_missing_from_dispatch_is_red(self):
        fixture = copy.deepcopy(self.clean)
        fixture["dispatch_profiles"].remove("chapt-worker-2")
        code, output = fixture_main(fixture)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: dispatch drift", output)
        self.assertIn("FAIL: project fleet profile missing from dispatch_profiles: chapt-worker-2", output)

    def test_unknown_extra_worker_is_red(self):
        fixture = copy.deepcopy(self.clean)
        fixture["dispatch_profiles"].append("jss-worker-3")
        fixture["dormant_extras"] = [*fixture.get("dormant_extras", []), "jss-worker-3"]
        fixture["project_isolation"]["jss-genr"]["workers"].append("jss-worker-3")
        code, output = fixture_main(fixture)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: dispatch drift", output)
        self.assertIn("FAIL: project isolation observed mapping drift", output)

    def test_second_worker_model_drift_is_red(self):
        fixture = copy.deepcopy(self.clean)
        fixture["profile_models"]["harness-worker-2"] = "gpt-6.1-sol"
        code, output = fixture_main(fixture)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: model drift harness-worker-2: expected claude-opus-5-5, actual gpt-6.1-sol", output)

    def test_retired_glm_dispatch_stays_red(self):
        fixture = copy.deepcopy(self.clean)
        fixture["dispatch_profiles"].append("jss-worker-glm-1")
        code, output = fixture_main(fixture)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: retired profile back in dispatch_profiles: jss-worker-glm-1", output)


class PolicyText(unittest.TestCase):
    def test_orchestrator_and_reviewer_souls_name_both_workers(self):
        for prefix in FLEETS.values():
            for role in ("orchestrator", "reviewer"):
                text = soul(f"{prefix}-{role}").read_text()
                with self.subTest(profile=f"{prefix}-{role}"):
                    self.assertIn(f"`{prefix}-worker` or `{prefix}-worker-2`", text)
                    self.assertIsNone(GLM_NAME.search(text))

    def test_skills_name_both_workers_and_the_spread_rule_once(self):
        for path, version in VERSIONS.items():
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertRegex(text, rf"(?m)^version: {re.escape(version)}$")
                self.assertEqual(" ".join(text.split()).count(RULE), 1)
                self.assertNotIn("one implementation worker", text)
                self.assertNotIn("The sole implementation worker", text)
                self.assertIsNone(GLM_NAME.search(text))
        for prefix in ("harness", "jss"):
            text = PROFILE_SKILLS[prefix].read_text()
            self.assertIn(f"- The implementation workers are `{prefix}-worker` and `{prefix}-worker-2`.\n", text)
        for path, fleets in ((PROFILE_SKILLS["jobcron"], ("jobcron", "chapt")),
                             (PROFILE_SKILLS["chapt"], ("jobcron", "chapt")),
                             (SHARED_SKILL, ("jobcron", "chapt", "harness"))):
            text = path.read_text()
            self.assertIn("Each project has two implementation workers.", text)
            for prefix in fleets:
                self.assertIn(f"implementation workers `{prefix}-worker` (`gpt-6.1-sol`) and "
                              f"`{prefix}-worker-2` (`claude-opus-5-5`);", text)

    def test_current_state_docs_list_both_workers(self):
        for rel, prefix in (("adoption/cha-pt.md", "chapt"), ("adoption/jobcron.md", "jobcron"),
                            ("adoption/harness.md", "harness"), ("adoption/jss-genr.md", "jss")):
            with self.subTest(path=rel):
                self.assertIn(f"the workers `{prefix}-worker` and `{prefix}-worker-2`", (ROOT / rel).read_text())
        procedure = (ROOT / "procedures/switching-hermes-models.md").read_text()
        for name in SECOND:
            self.assertIn(f"`{name}`", procedure)


class Pins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")

    def test_second_worker_souls_are_byte_copies_pinned_like_their_source(self):
        souls = self.roster["profile_souls"]
        self.assertEqual(self.snapshot["profile_souls"], souls)
        for profile in PINNED_WORKERS:
            second = f"{profile}-2"
            with self.subTest(profile=second):
                self.assertFalse(soul(second).is_symlink())
                self.assertEqual(soul(second).read_bytes(), soul(profile).read_bytes())
                self.assertEqual(souls[second], {
                    "source": f"policies/profile-souls/{second}/SOUL.md",
                    "live": f"/Users/chanbla11mit/.hermes/profiles/{second}/SOUL.md",
                    "sha256": sha(soul(second)),
                })
                self.assertEqual(souls[second]["sha256"], souls[profile]["sha256"])
        for name in ("jobcron-worker", "jobcron-worker-2"):
            self.assertNotIn(name, souls)
            self.assertFalse(soul(name).exists())
        verifier = load_verifier()
        self.assertEqual(quiet(verifier.check_profile_souls, souls), [])
        observed = {profile: entry["sha256"] for profile, entry in souls.items()}
        observed["harness-worker-2"] = "0" * 64
        self.assertEqual(quiet(verifier.check_profile_souls, souls, observed),
                         ["profile SOUL drift harness-worker-2"])

    def test_every_pin_equals_tracked_bytes(self):
        for profile, entry in self.roster["profile_souls"].items():
            with self.subTest(soul=profile):
                self.assertEqual(entry["sha256"], sha(ROOT / entry["source"]))
        overrides = self.snapshot["skill"]["profile_local_skill_overrides"]
        for prefix, path in PROFILE_SKILLS.items():
            self.assertEqual(overrides[f"{prefix}-orchestrator"], {RELATIVE: sha(path)})
        shared = next(e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "multi-agent-coding-orchestrator")
        self.assertEqual(shared["version"], "0.6.10")
        self.assertEqual(shared["files"]["SKILL.md"], sha(SHARED_SKILL))
        provenance = self.snapshot["skill"]["source_pin_provenance"]["second_worker"]
        self.assertEqual(provenance["baseline"], "8d660578bedca672f71460222a73215272e136f7")
        self.assertEqual(provenance["protected_reference"], "refs/harness/baselines/t_b12ba0d9")
        self.assertIn("not observed deployment", provenance["status"])

    def test_fixtures_observe_both_workers(self):
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            if fixture.name == "incomplete-empty.yaml":
                continue
            data = load(fixture)
            with self.subTest(fixture=fixture.name):
                for project, pool in POOLS.items():
                    self.assertEqual(data["project_isolation"][project]["workers"], pool)
                for profile in PINNED_WORKERS:
                    self.assertEqual(data["profile_soul_hashes"][f"{profile}-2"],
                                     self.roster["profile_souls"][profile]["sha256"])
                for name in SECOND:
                    self.assertIn(name, data["dispatch_profiles"])
                    if fixture.name != "incomplete-omits-profile.yaml":
                        self.assertEqual(data["profile_models"][name], "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
