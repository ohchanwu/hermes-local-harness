#!/usr/bin/env python3
"""Offline source contract for the 2026-10-18 GLM worker retirement.

Checks tracked repository text, desired state, pins and fixture-mode
verification only; no live profile, board, or model observation.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.machinery
import importlib.util
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
GLM = tuple(f"{prefix}-worker-glm-{n}" for prefix in FLEETS.values() for n in (1, 2))
GLM_NAME = re.compile(r"\b(?:jobcron|chapt|harness|jss)-worker-glm-\d\b")
GLM_LANE = re.compile(r"(?i)GLM Full workers?|idle GLM worker|both GLM workers|GLM workers may|three-(?:worker|profile) pool")
# Legacy/default-board GLM lanes archived 2026-10-18 (t_56d81c3a).
LEGACY_GLM_NAME = re.compile(r"\bworker-flash-\d\b|\bworker-glm-full\b")
LEGACY_LANE_LIST = re.compile(r"(?i)implementation profiles, in escalation order|control profiles remain installed")
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PROFILE_SKILLS = {
    profile: ROOT / "policies/profile-skills" / profile / RELATIVE
    for profile in ("jobcron-orchestrator", "chapt-orchestrator", "harness-orchestrator", "jss-orchestrator")
}
SHARED_SKILL = ROOT / "skills/multi-agent-coding-orchestrator/SKILL.md"
VERSIONS = {
    PROFILE_SKILLS["jobcron-orchestrator"]: "0.6.9-jobcron.4",
    PROFILE_SKILLS["chapt-orchestrator"]: "0.6.7-chapt.4",
    PROFILE_SKILLS["harness-orchestrator"]: "0.6.7-harness.3",
    PROFILE_SKILLS["jss-orchestrator"]: "0.6.7-jss.5",
    SHARED_SKILL: "0.6.10",
}
PROCEDURE = ROOT / "procedures/switching-hermes-models.md"
JOBCRON_SOUL = ROOT / "policies/profile-souls/jobcron-orchestrator/SOUL.md"
JOBCRON_SOUL_LIVE = "/Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/SOUL.md"
# The upstream live SOUL read once for t_56d81c3a; the tracked copy differs only
# in its implementation pool sentence (GLM workers removed, t_56d81c3a;
# second worker added, t_b12ba0d9).
JOBCRON_SOUL_UPSTREAM_SHA256 = "c1a69bf14dccd1ea413ba4002ae7526af7fbb38f40d125e617608d0e42c306ea"
JOBCRON_SOUL_EDIT = (
    b"Assign implementation only to `jobcron-worker` or `jobcron-worker-2`; assign same-card review only to "
    b"`jobcron-reviewer`.",
    b"Assign implementation only to the Jobcron pool: `jobcron-worker`, `jobcron-worker-glm-1`, or "
    b"`jobcron-worker-glm-2`; assign same-card review only to `jobcron-reviewer`.",
)
RETIREMENT_FIXTURE = "retired-glm-dispatch-drift.yaml"
CURRENT_STATE_DOCS = (
    "adoption/cha-pt.md", "adoption/harness.md", "adoption/jobcron.md", "adoption/jss-genr.md",
    "procedures/manual-apply.md", "procedures/rollback-restore.md",
    "procedures/hermes-terminal-outcome-notifications.md",
    "deployment/hermes-terminal-outcome-notification.example.yaml",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(content):
    return hashlib.sha256(content).hexdigest()


def load(path):
    return json.loads(path.read_text())


def quiet(function, *args):
    errors = []
    with redirect_stdout(io.StringIO()):
        function(errors, *args)
    return errors


class DesiredState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")
        cls.verifier = load_verifier()

    def test_no_glm_worker_in_any_roster_list(self):
        # Owner decision 2026-10-19: keep the GLM workers and mark them retired.
        # They are declared roster profiles (and so in the approval list) with
        # the retired lifecycle, and appear in no dispatch list, pool or fleet.
        profiles = {profile["name"]: profile for profile in self.roster["profiles"]}
        for name in GLM:
            with self.subTest(retired=name):
                self.assertEqual(profiles[name]["lifecycle"], "retired")
                self.assertEqual(profiles[name]["retired_on"], "2026-10-18")
                self.assertFalse(profiles[name]["dispatch_eligible"])
                self.assertFalse(profiles[name]["in_dispatch_pool"])
                self.assertIn(name, self.roster["approval_policy"]["profiles"])
        lists = {
            "project_dispatch_allowlist": self.roster["project_dispatch_allowlist"],
            "implementation_allowlist": self.roster["dispatch_pool"]["implementation_allowlist"],
            "dispatch_allowlist": self.roster["dispatch_pool"]["dispatch_allowlist"],
            "profile_souls": list(self.roster["profile_souls"]),
        }
        for project, fleet in self.roster["project_fleets"].items():
            lists[f"fleet {project}"] = [fleet["orchestrator"], fleet["worker"], fleet["reviewer"], *fleet["workers"]]
        for label, listing in lists.items():
            with self.subTest(list=label):
                self.assertEqual([name for name in listing if name in GLM], [])
        self.assertEqual(quiet(self.verifier.check_retired_profiles, self.roster), [])

    def test_no_glm_worker_in_snapshot(self):
        self.assertEqual(self.snapshot["profiles"], [p["name"] for p in self.roster["profiles"]])
        lists = {
            "dispatch_profiles": self.snapshot["kanban"]["dispatch_profiles"],
            "profile_souls": list(self.snapshot["profile_souls"]),
        }
        for entry in self.snapshot["skill"]["shared_skills"]:
            lists[f"deploy {entry['name']}"] = entry["deploy_profiles"]
        for label, listing in lists.items():
            with self.subTest(list=label):
                self.assertEqual([name for name in listing if name in GLM], [])
        self.assertEqual(self.snapshot["project_isolation"], self.roster["project_fleets"])
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])

    def test_each_fleet_has_its_two_workers_and_its_reviewer(self):
        dispatch = self.snapshot["kanban"]["dispatch_profiles"]
        for project, prefix in FLEETS.items():
            fleet = self.roster["project_fleets"][project]
            with self.subTest(project=project):
                self.assertEqual(fleet["worker"], f"{prefix}-worker")
                self.assertEqual(fleet["workers"], [f"{prefix}-worker", f"{prefix}-worker-2"])
                self.assertEqual(fleet["reviewer"], f"{prefix}-reviewer")
                for worker in fleet["workers"]:
                    self.assertIn(worker, dispatch)
                self.assertIn(fleet["reviewer"], dispatch)
        self.assertEqual(self.roster["project_dispatch_allowlist"], [
            "jobcron-worker", "jobcron-reviewer", "chapt-worker", "chapt-reviewer",
            "harness-worker", "harness-reviewer", "jss-worker", "jss-reviewer",
            "harness-worker-2", "chapt-worker-2", "jobcron-worker-2", "jss-worker-2"])
        self.assertEqual(dispatch[-12:], self.roster["project_dispatch_allowlist"])

    def test_verifier_constants(self):
        self.assertEqual(set(self.verifier.RETIRED_PROFILES), set(GLM))
        for name in GLM:
            with self.subTest(profile=name):
                self.assertNotIn(name, self.verifier.PROFILE_SOUL_PATHS)
                for assignees in (self.verifier.CHAPT_ASSIGNEES, self.verifier.HARNESS_ASSIGNEES,
                                  self.verifier.JSS_ASSIGNEES):
                    self.assertNotIn(name, assignees)
        self.assertEqual(self.verifier.HARNESS_ASSIGNEES, {"harness-worker", "harness-worker-2", "harness-reviewer"})
        self.assertEqual(self.verifier.CHAPT_ASSIGNEES, {"chapt-worker", "chapt-worker-2", "chapt-reviewer"})
        self.assertEqual(self.verifier.JSS_ASSIGNEES, {"jss-worker", "jss-worker-2", "jss-reviewer"})

    def test_verifier_rejects_glm_reentry(self):
        fleets = copy.deepcopy(self.roster["project_fleets"])
        fleets["harness"]["workers"].append("harness-worker-glm-1")
        self.assertIn("project worker pool mapping malformed: harness",
                      quiet(self.verifier.check_project_isolation, fleets))
        self.assertEqual(quiet(self.verifier.check_project_isolation, self.roster["project_fleets"]), [])
        for label in ("kanban.dispatch_profiles", "project_dispatch_allowlist"):
            self.assertEqual(
                quiet(self.verifier.check_retired_dispatch, label, ["harness-worker", "jss-worker-glm-2"]),
                [f"retired profile back in {label}: jss-worker-glm-2"])
        self.assertEqual(quiet(self.verifier.check_retired_dispatch, "x", self.roster["project_dispatch_allowlist"]), [])
        body = ("Repository /Users/chanbla11mit/hermes-local-harness ONLY.\n"
                f"Baseline EXACT {'a' * 40}.\n## Tests\n- `python3 tests/test_x.py`\n"
                "Reviewer EXACT harness-reviewer.\n")
        card = {"id": "t_glm", "board": "harness", "body": body, "assignee": "harness-worker",
                "workspace_kind": "worktree",
                "workspace_path": "/Users/chanbla11mit/hermes-local-harness/.worktrees/t_glm"}
        self.assertEqual(quiet(self.verifier.check_harness_card_contract, [card]), [])
        card["assignee"] = "harness-worker-glm-2"
        self.assertIn("Harness card contract drift t_glm: Harness worker assignment invalid",
                      quiet(self.verifier.check_harness_card_contract, [card]))


class PolicyText(unittest.TestCase):
    def test_active_souls_name_no_glm_worker(self):
        souls = load(ROOT / "roster.yaml")["profile_souls"]
        for profile, entry in souls.items():
            text = (ROOT / entry["source"]).read_text()
            with self.subTest(profile=profile):
                self.assertIsNone(GLM_NAME.search(text))
                self.assertIsNone(GLM_LANE.search(text))

    def test_orchestrator_and_reviewer_souls_name_only_the_remaining_worker(self):
        for prefix in FLEETS.values():
            for role in ("orchestrator", "reviewer"):
                path = ROOT / f"policies/profile-souls/{prefix}-{role}/SOUL.md"
                with self.subTest(profile=f"{prefix}-{role}"):
                    self.assertTrue(path.is_file())
                    self.assertIn(f"`{prefix}-worker`", path.read_text())

    def test_no_repo_soul_names_a_glm_or_legacy_glm_lane(self):
        souls = sorted((ROOT / "policies/profile-souls").glob("*/SOUL.md"))
        self.assertIn(JOBCRON_SOUL, souls)
        for path in souls:
            text = path.read_text()
            with self.subTest(soul=path.parent.name):
                self.assertIsNone(GLM_NAME.search(text))
                self.assertIsNone(LEGACY_GLM_NAME.search(text))

    def test_jobcron_orchestrator_soul_routes_only_to_its_worker(self):
        text = JOBCRON_SOUL.read_bytes()
        self.assertEqual(text.count(JOBCRON_SOUL_EDIT[0]), 1)
        self.assertNotIn(b"glm", text.lower())
        self.assertIn(b"assign same-card review only to `jobcron-reviewer`", text)
        # t_a1208da3 appended the writing rules (the upstream copy ended without LF).
        appended = b"\n\n" + (ROOT / "policies/writing-rules.md").read_bytes()
        self.assertTrue(text.endswith(appended))
        text = text[:-len(appended)]
        # Every other byte is the upstream live SOUL, verbatim.
        self.assertEqual(sha_bytes(text.replace(*JOBCRON_SOUL_EDIT, 1)), JOBCRON_SOUL_UPSTREAM_SHA256)

    def test_no_orchestrator_skill_names_a_legacy_glm_lane(self):
        for path in PROFILE_SKILLS.values():
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(GLM_NAME.search(text))
                self.assertIsNone(LEGACY_GLM_NAME.search(text))
                self.assertIsNone(LEGACY_LANE_LIST.search(text))
        for profile in ("jobcron-orchestrator", "chapt-orchestrator"):
            text = PROFILE_SKILLS[profile].read_text()
            with self.subTest(note=profile):
                note = next(p for p in text.split("\n\n") if p.startswith("Legacy/default-board lanes are retired"))
                for marker in ("retired and inert", "2026-10-18", "`reviewer-sol`",
                               "Never assign, escalate, or route review to them.",
                               "`~/.hermes/profile-exports/`", "`procedures/switching-hermes-models.md`"):
                    self.assertIn(marker, note)
                self.assertIn("\n- `advisor`: read/analyze advisor; not a Kanban implementation lane.\n", text)
                self.assertNotIn("`default`: legacy", text)
                self.assertNotIn("rollback/spare lane", text)

    def test_skills_route_only_to_the_remaining_worker(self):
        for path, version in VERSIONS.items():
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertRegex(text, rf"(?m)^version: {re.escape(version)}$")
                self.assertIsNone(GLM_NAME.search(text))
                self.assertIsNone(GLM_LANE.search(text))
        for prefix in ("harness", "jss"):
            text = PROFILE_SKILLS[f"{prefix}-orchestrator"].read_text()
            self.assertIn(f"The implementation workers are `{prefix}-worker` and `{prefix}-worker-2`.", text)
        for path in (PROFILE_SKILLS["jobcron-orchestrator"], PROFILE_SKILLS["chapt-orchestrator"], SHARED_SKILL):
            text = path.read_text()
            self.assertIn("Each project has two implementation workers.", text)
            self.assertIn("implementation workers `jobcron-worker`", text)

    def test_current_state_docs_list_no_glm_worker(self):
        for rel in CURRENT_STATE_DOCS:
            with self.subTest(path=rel):
                self.assertIsNone(GLM_NAME.search((ROOT / rel).read_text()))

    def test_retirement_note(self):
        text = PROCEDURE.read_text()
        section = text.split("## Where the GLM worker profiles are kept", 1)[1].split("\n## ", 1)[0]
        self.assertIn("retired the GLM workers on 2026-10-18", section)
        for name in GLM:
            self.assertIn(f"`{name}`", section)
        for marker in ("~/.hermes/profile-exports/<name>-20261018-*.tar.gz", "`hermes profile export`",
                       "`hermes profile import <archive>`", "`hermes -p <profile> auth add zai`",
                       "`scripts/switch-profile-model --profile <profile> --to glm --dispatch add`",
                       "They are inert.", "exclude `.env` and `auth.json`"):
            self.assertIn(marker, section)
        self.assertIn("Every provider stays switchable", text)
        self.assertIn("`glm`: `zai`, default `glm-5.3`.", text)


class Pins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")

    def test_pins_equal_tracked_bytes(self):
        self.assertEqual(self.snapshot["profile_souls"], self.roster["profile_souls"])
        # Expectations are derived from the tracked bytes (t_76a2134d): no hand pins.
        verifier = load_verifier()
        for profile, entry in self.roster["profile_souls"].items():
            with self.subTest(soul=profile):
                self.assertNotIn("sha256", entry)
                self.assertEqual(verifier.profile_soul_expected(entry), sha(ROOT / entry["source"]))
        overrides = self.snapshot["skill"]["profile_local_skill_overrides"]
        for profile, path in PROFILE_SKILLS.items():
            with self.subTest(skill=profile):
                self.assertEqual(overrides[profile], {RELATIVE: verifier.TRACKED_SOURCE})
                self.assertEqual(verifier.local_override_expected(profile, RELATIVE, overrides[profile][RELATIVE]),
                                 sha(path))
        shared = next(e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "multi-agent-coding-orchestrator")
        self.assertEqual(shared["version"], "0.6.10")
        self.assertEqual(shared["source"], "skills/multi-agent-coding-orchestrator")
        for rel, want in verifier.shared_skill_expected(shared).items():
            self.assertEqual(want, sha(SHARED_SKILL.parent / rel))
        provenance = self.snapshot["skill"]["source_pin_provenance"]["glm_worker_retirement"]
        self.assertEqual(provenance["baseline"], "1799a9b728681c3672fc29239dff9bf5564280f4")
        self.assertEqual(provenance["protected_reference"], "refs/harness/baselines/t_f953035b")
        self.assertIn("not observed deployment", provenance["status"])
        followup = self.snapshot["skill"]["source_pin_provenance"]["glm_retirement_followup"]
        self.assertEqual(followup["baseline"], "0bca93283a8030e729ec82c05a0c64e8958bfabd")
        self.assertEqual(followup["protected_reference"], "refs/harness/baselines/t_56d81c3a")
        self.assertEqual(followup["upstream_live_sha256"],
                         {"jobcron-orchestrator/SOUL.md": JOBCRON_SOUL_UPSTREAM_SHA256})
        self.assertIn("not observed deployment", followup["status"])

    def test_jobcron_orchestrator_soul_is_pinned(self):
        entry = self.roster["profile_souls"]["jobcron-orchestrator"]
        self.assertEqual(entry, {
            "source": "policies/profile-souls/jobcron-orchestrator/SOUL.md",
            "live": JOBCRON_SOUL_LIVE,
        })
        self.assertEqual(self.snapshot["profile_souls"]["jobcron-orchestrator"], entry)
        verifier = load_verifier()
        self.assertEqual(verifier.PROFILE_SOUL_PATHS["jobcron-orchestrator"],
                         {"source": entry["source"], "live": entry["live"]})
        self.assertEqual(quiet(verifier.check_profile_souls, self.roster["profile_souls"]), [])
        self.assertEqual(verifier.profile_soul_expected(entry), sha(JOBCRON_SOUL))
        drifted = {profile: sha(ROOT / soul["source"]) for profile, soul in self.roster["profile_souls"].items()}
        drifted["jobcron-orchestrator"] = JOBCRON_SOUL_UPSTREAM_SHA256  # the undeployed live GLM pool
        self.assertEqual(quiet(verifier.check_profile_souls, self.roster["profile_souls"], drifted),
                         ["profile SOUL drift jobcron-orchestrator"])

    def test_fixture_pins_and_observations(self):
        souls = {profile: sha(ROOT / entry["source"]) for profile, entry in self.roster["profile_souls"].items()}
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = load(fixture)
            if fixture.name == "incomplete-empty.yaml":
                continue
            with self.subTest(fixture=fixture.name):
                want = dict(souls)
                if fixture.name == "chapt-profile-soul-drift.yaml":  # its intended drift
                    want["chapt-reviewer"] = "0" * 64
                self.assertEqual(data["profile_soul_hashes"], want)
                for profile, path in PROFILE_SKILLS.items():
                    self.assertEqual(data["profile_local_skill_overrides"][profile][RELATIVE], sha(path))
                # Retired GLM workers are observed installed profiles (owner decision
                # 2026-10-19) but never carry a skill deployment or a fleet slot.
                observed = {key: data[key] for key in ("skill_files", "project_isolation")}
                self.assertIsNone(GLM_NAME.search(json.dumps(observed)))
                if "profile_models" in data:
                    self.assertEqual({n: data["profile_models"].get(n) for n in GLM},
                                     {n: "glm-5.3" for n in GLM})
                dispatch = [name for name in data["dispatch_profiles"] if name in GLM]
                self.assertEqual(dispatch, ["harness-worker-glm-1"] if fixture.name == RETIREMENT_FIXTURE else [])


def fixture_main(path):
    verifier = load_verifier()
    output = io.StringIO()
    with LocalReads(), patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
        code = verifier.main()
    return code, output.getvalue()


class FixtureMode(unittest.TestCase):
    """Real verifier main() under the no-command/no-network/worktree-only guard."""

    def test_clean_is_green(self):
        code, output = fixture_main(ROOT / "tests/fixtures/clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertNotIn("FAIL:", output)

    def test_glm_back_in_dispatch_is_red(self):
        code, output = fixture_main(ROOT / "tests/fixtures" / RETIREMENT_FIXTURE)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: retired profile back in dispatch_profiles: harness-worker-glm-1", output)
        self.assertIn("FAIL: dispatch drift", output)
        self.assertIn("WARN: dormant unexpected profile: harness-worker-glm-1", output)

    def test_installed_inert_glm_profile_is_only_a_dormant_warning(self):
        fixture = load(ROOT / "tests/fixtures/clean.yaml")
        fixture["dormant_extras"] = list(GLM)
        with tempfile.TemporaryDirectory(prefix="glm-retirement-") as directory:
            path = Path(directory) / "observation.yaml"
            path.write_text(json.dumps(fixture))
            verifier = load_verifier()
            output = io.StringIO()
            guard = LocalReads()
            guard.allowed.add(os.path.abspath(path))
            with guard, patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
                code = verifier.main()
        self.assertEqual(code, 0, output.getvalue())
        for name in GLM:
            self.assertIn(f"WARN: dormant unexpected profile: {name}", output.getvalue())


class SwitchStillSupportsGlm(unittest.TestCase):
    def test_switch_profile_model_accepts_to_glm(self):
        loader = importlib.machinery.SourceFileLoader("switch_profile_model_glm", str(ROOT / "scripts/switch-profile-model"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None
        switch = importlib.util.module_from_spec(spec)
        loader.exec_module(switch)
        self.assertEqual(switch.TARGETS["glm"][:3], ("zai", "https://api.z.ai/api/coding/paas/v4", "glm-5.3"))
        with tempfile.TemporaryDirectory(prefix="glm-switch-") as directory:
            root = Path(directory)
            (root / "profiles/harness-worker-glm-1").mkdir(parents=True)
            (root / "profiles/harness-worker-glm-1/config.yaml").write_text("model:\n  default: x\n")
            with redirect_stdout(io.StringIO()) as out:
                code = switch.main(["--home-root", str(root), "--hermes", str(root / "absent-hermes"),
                                    "--profile", "harness-worker-glm-1", "--to", "glm", "--dispatch", "add",
                                    "--dry-run"])
            self.assertEqual(code, 0)
            self.assertIn("config set model.provider zai", out.getvalue())
            self.assertIn("config set model.default glm-5.3", out.getvalue())
            self.assertEqual(sorted(p.name for p in (root / "profiles/harness-worker-glm-1").iterdir()),
                             ["config.yaml"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
