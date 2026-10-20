#!/usr/bin/env python3
"""Staleness guard for derived skill/SOUL expectations (t_76a2134d).

Desired state declares only structure; expected bytes are hashed from the
tracked sources at check time. These tests run the real verifier main() in
fixture mode under the worktree-only read guard (no commands, network or live
~/.hermes reads). Cases that change a tracked source do so in a temporary
copy of the repository, never in the worktree.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT

RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
OK = "OK: desired state matches observed state"


class TreeReads(LocalReads):
    """LocalReads over an arbitrary repository tree plus explicit extra files."""

    def __init__(self, root, extra=()):
        self.allowed = {str(root)}
        for path in root.rglob("*"):
            if path.is_symlink():
                raise AssertionError(f"symlink in test tree: {path}")
            self.allowed.add(str(path))
        self.allowed.update(os.path.abspath(path) for path in extra)
        self.stack = ExitStack()


def tree_verifier(root):
    source = root / "scripts/verify-state"
    module = types.ModuleType("derived_expectations_verifier")
    module.__file__ = str(source)
    exec(compile(source.read_text(), str(source), "exec"), module.__dict__)
    return module


def run_main(root, fixture):
    """(exit code, set of FAIL lines, full output) of fixture-mode main() over root."""
    verifier = tree_verifier(root)
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="derived-expectations-obs-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(fixture))
        with TreeReads(root, (path,)), patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), \
                redirect_stdout(output):
            code = verifier.main()
    text = output.getvalue()
    return code, {line[len("FAIL: "):] for line in text.splitlines() if line.startswith("FAIL: ")}, text


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def redeployed(verifier, fixture):
    """The observation after a redeploy of every tracked source: hashes derived now."""
    fixture = copy.deepcopy(fixture)
    snapshot = load(verifier.ROOT / "snapshots/sanitized-current-state.yaml")
    overrides = snapshot["skill"]["profile_local_skill_overrides"]
    fixture["profile_local_skill_overrides"] = {
        profile: {path: verifier.local_override_expected(profile, path, declared)
                  for path, declared in files.items()}
        for profile, files in overrides.items()}
    for entry in snapshot["skill"]["shared_skills"]:
        expected = verifier.shared_skill_expected(entry)
        for profile, files in fixture["skill_files"][entry["name"]].items():
            for rel in files:
                owned = [fixture["profile_local_skill_overrides"][profile][path]
                         for path in overrides.get(profile, {}) if f"/{path}".endswith(f"/{entry['name']}/{rel}")]
                files[rel] = owned[0] if owned else expected[rel]
    fixture["profile_soul_hashes"] = {
        profile: verifier.profile_soul_expected(entry) for profile, entry in snapshot["profile_souls"].items()}
    return fixture


class TempTree:
    """A throwaway copy of the repository (no .git, worktrees or caches)."""

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="derived-expectations-tree-")
        self.root = Path(self.directory.name).resolve() / "repo"
        shutil.copytree(ROOT, self.root, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".worktrees", "__pycache__"))
        return self.root

    def __exit__(self, *args):
        self.directory.cleanup()


class DerivedExpectations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = load(ROOT / "tests/fixtures/clean.yaml")
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")
        cls.verifier = tree_verifier(ROOT)
        cls.retired = set(cls.verifier.roster_retired(cls.roster))

    # (a)
    def test_clean_fixture_passes(self):
        code, fails, output = run_main(ROOT, self.clean)
        self.assertEqual((code, fails), (0, set()), output)
        self.assertIn(OK, output)

    def test_desired_state_carries_structure_not_hash_pins(self):
        for label, souls in (("roster", self.roster["profile_souls"]), ("snapshot", self.snapshot["profile_souls"])):
            for profile, entry in souls.items():
                with self.subTest(source=label, profile=profile):
                    self.assertEqual(set(entry), {"source", "live"})
        for entry in self.snapshot["skill"]["shared_skills"]:
            with self.subTest(skill=entry["name"]):
                self.assertIsInstance(entry["files"], list)
                self.assertTrue((ROOT / entry["source"]).is_dir())
        tracked = ROOT / "policies/profile-skills"
        for profile, files in self.snapshot["skill"]["profile_local_skill_overrides"].items():
            for path, declared in files.items():
                with self.subTest(profile=profile, path=path):
                    # A pin is legal only where no tracked source exists.
                    has_source = (tracked / profile / path).is_file() if (tracked / profile).is_dir() else False
                    self.assertEqual(declared == "tracked-source", has_source)

    def test_hand_pins_reintroduced_are_rejected(self):
        with TempTree() as root:
            snapshot = load(root / "snapshots/sanitized-current-state.yaml")
            roster = load(root / "roster.yaml")
            entry = next(e for e in snapshot["skill"]["shared_skills"] if e["name"] == "minimal-implementation")
            entry["files"] = {"SKILL.md": self.verifier.shared_skill_expected(entry)["SKILL.md"]}
            pin = self.verifier.local_override_expected("harness-orchestrator", RELATIVE, "tracked-source")
            snapshot["skill"]["profile_local_skill_overrides"]["harness-orchestrator"][RELATIVE] = pin
            for souls in (snapshot["profile_souls"], roster["profile_souls"]):
                souls["jss-worker"]["sha256"] = self.verifier.profile_soul_expected(souls["jss-worker"])
            write(root / "snapshots/sanitized-current-state.yaml", snapshot)
            write(root / "roster.yaml", roster)
            code, fails, output = run_main(root, self.clean)
        self.assertEqual(code, 1, output)
        self.assertIn("malformed shared skill declaration: 'minimal-implementation' "
                      "(expected a tracked skills/ source and a file list, no hash pins)", fails)
        self.assertIn(f"duplicated profile-local skill override pin: harness-orchestrator/{RELATIVE} "
                      "(a tracked source exists; declare 'tracked-source')", fails)
        self.assertIn("malformed profile SOUL policy: jss-worker (declare only source and live; "
                      "the expected hash is derived from the tracked source)", fails)

    def test_undeclared_tracked_source_files_are_red(self):
        with TempTree() as root:
            (root / "skills/minimal-implementation/references").mkdir()
            (root / "skills/minimal-implementation/references/new.md").write_text("new\n")
            extra = root / "policies/profile-skills/jobcron-orchestrator/software-development/extra/SKILL.md"
            extra.parent.mkdir(parents=True)
            extra.write_text("extra\n")
            code, fails, output = run_main(root, self.clean)
        self.assertEqual(code, 1, output)
        self.assertEqual(fails, {
            "undeclared tracked skill file: minimal-implementation/references/new.md",
            "undeclared tracked profile-local skill override: "
            "jobcron-orchestrator/software-development/extra/SKILL.md",
        })

    # (b)
    def test_tracked_source_change_needs_no_pin_edit_and_reddens_unchanged_live(self):
        with TempTree() as root:
            for rel in ("skills/devops/production-deployment/SKILL.md",
                        "policies/profile-souls/harness-reviewer/SOUL.md",
                        f"policies/profile-skills/harness-orchestrator/{RELATIVE}"):
                with open(root / rel, "a") as handle:
                    handle.write("\nReviewed policy change.\n")
            code, fails, output = run_main(root, self.clean)  # live still has the old bytes
            entry = next(e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "production-deployment")
            stale = {f"deployed skill hash mismatch: production-deployment {profile}/SKILL.md"
                     for profile in entry["deploy_profiles"] if profile not in self.retired}
            # Tracked side stays green: only the live-vs-repository comparison is red.
            self.assertEqual(code, 1, output)
            self.assertEqual(fails, stale | {
                "profile SOUL drift harness-reviewer",
                f"profile-local skill override drift: harness-orchestrator/{RELATIVE}",
            })
            self.assertEqual(len(stale), 12)
            # Redeploying the changed sources (new observation, still no pin edit) is green.
            code, fails, output = run_main(root, redeployed(tree_verifier(root), self.clean))
            self.assertEqual((code, fails), (0, set()), output)

    # (c)
    def test_live_copy_differing_from_repository_source_fails(self):
        fixture = copy.deepcopy(self.clean)
        fixture["skill_files"]["simplification-review"]["jss-worker"]["SKILL.md"] = "1" * 64
        fixture["skill_files"]["production-deployment"]["chapt-reviewer"]["references/extra.md"] = "2" * 64
        fixture["profile_soul_hashes"]["jss-reviewer"] = "3" * 64
        fixture["profile_local_skill_overrides"]["chapt-orchestrator"][RELATIVE] = "4" * 64
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual(code, 1, output)
        # The override owns the orchestrator's SKILL.md: reported once, by the override check.
        self.assertEqual(fails, {
            "deployed skill hash mismatch: simplification-review jss-worker/SKILL.md",
            "unexpected deployed skill file: production-deployment chapt-reviewer/references/extra.md",
            "profile SOUL drift jss-reviewer",
            f"profile-local skill override drift: chapt-orchestrator/{RELATIVE}",
        })

    def test_override_owned_file_must_match_the_override_not_the_shared_skill(self):
        fixture = copy.deepcopy(self.clean)
        shared = self.verifier.shared_skill_expected(next(
            e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "multi-agent-coding-orchestrator"))
        fixture["profile_local_skill_overrides"]["harness-orchestrator"][RELATIVE] = shared["SKILL.md"]
        fixture["skill_files"]["multi-agent-coding-orchestrator"]["harness-orchestrator"]["SKILL.md"] = shared["SKILL.md"]
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual((code, fails), (1, {f"profile-local skill override drift: harness-orchestrator/{RELATIVE}"}),
                         output)

    # (d)
    def test_retired_profile_divergence_is_excluded_live_profile_is_not(self):
        for name in ("worker-flash-1", "worker-sol", "worker-astra"):
            self.assertIn(name, self.retired)
        self.assertNotIn("harness-worker", self.retired)
        fixture = copy.deepcopy(self.clean)
        fixture["skill_files"]["minimal-implementation"]["worker-flash-1"]["SKILL.md"] = "5" * 64
        del fixture["skill_files"]["simplification-review"]["worker-sol"]
        fixture["skill_files"]["production-deployment"]["worker-astra"]["references/extra.md"] = "6" * 64
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual((code, fails), (0, set()), output)
        fixture["skill_files"]["minimal-implementation"]["harness-worker"]["SKILL.md"] = "7" * 64
        del fixture["skill_files"]["simplification-review"]["harness-worker-2"]
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual((code, fails), (1, {
            "deployed skill hash mismatch: minimal-implementation harness-worker/SKILL.md",
            "deployed skill copy missing: simplification-review harness-worker-2",
        }), output)

    # (e)
    def test_profile_present_live_but_absent_from_roster_fails(self):
        ghost = "harness-worker-glm-3"  # GLM-like name, but not a retired roster profile
        self.assertNotIn(ghost, self.retired)
        fixture = copy.deepcopy(self.clean)
        fixture["profile_models"][ghost] = "glm-5.3"
        fixture["skill_files"]["minimal-implementation"][ghost] = copy.deepcopy(
            fixture["skill_files"]["minimal-implementation"]["harness-worker"])
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual(code, 1, output)
        self.assertIn(f"behavior-changing unexpected profile: {ghost}", fails)
        self.assertIn(f"unexpected deployed skill copy: minimal-implementation {ghost}", fails)

    def test_each_profile_has_its_own_skill_home(self):
        entry = next(e for e in self.snapshot["skill"]["shared_skills"] if e["name"] == "multi-agent-coding-orchestrator")
        self.assertEqual(entry["path"], "/Users/chanbla11mit/.hermes/profiles/<profile>/skills/"
                                        "autonomous-ai-agents/multi-agent-coding-orchestrator")
        self.assertEqual(self.verifier.deployed_skill_root(entry["path"], "default"),
                         Path("/Users/chanbla11mit/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator"))
        self.assertEqual(self.verifier.deployed_skill_root(entry["path"], "jss-orchestrator"),
                         Path("/Users/chanbla11mit/.hermes/profiles/jss-orchestrator/skills/"
                              "autonomous-ai-agents/multi-agent-coding-orchestrator"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
