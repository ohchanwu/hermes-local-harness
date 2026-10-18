#!/usr/bin/env python3
"""Offline source/scenario/pin/fixture contracts, NOT agent behavior or rollout.

Behavioral acceptance needs real source-bound baseline/two candidate trials and
independent semantic review of the separate oracle. No model call lives here.
"""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier

CASES = ROOT / "tests/fixtures/upgrade-proportionality-cases.json"
ORACLE = ROOT / "tests/fixtures/upgrade-proportionality-expectations.json"
DEPLOYMENT = "skills/devops/production-deployment/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
OVERRIDES = {
    profile: f"policies/profile-skills/{profile}/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
    for profile in ("jobcron-orchestrator", "chapt-orchestrator")
}
# Independently specified from the existing fixture contracts, never inferred
# from a fixture's current hash or from the generator's implementation.
FIXTURE_RESULTS = {
    "clean.yaml": (0, "OK: desired state matches observed state"),
    "astra-local-override.yaml": (0, "OK: desired state matches observed state"),
    "dormant-extra.yaml": (0, "WARN: dormant"),
    "retired-glm-dispatch-drift.yaml": (1, "retired profile back in dispatch_profiles: harness-worker-glm-1"),
    "behavior-changing-model-drift.yaml": (1, "model drift"),
    "active-extra.yaml": (1, "behavior-changing unexpected profile"),
    "unexpected-plugin.yaml": (1, "behavior-changing unexpected plugin"),
    "missing-plugin.yaml": (1, "plugin drift"),
    "approval-mode-drift.yaml": (1, "approval mode drift jobcron-worker"),
    "compression-drift.yaml": (1, "managed setting drift advisor compression.threshold_tokens"),
    "terminal-deployment-pending.yaml": (1, "terminal notification deployment pending"),
    "terminal-notification-rollback.yaml": (1, "terminal notification deployment pending"),
    "plugin-pin-drift.yaml": (1, "expected pinned 4.8.4@16f29800"),
    "deployed-skill-divergence.yaml": (1, "deployed skill hash mismatch"),
    "project-repair-policy-drift.yaml": (1, "project repair policy observed mapping drift"),
    "project-repair-card-drift.yaml": (1, "project repair contract drift t_fixture_repair: exact authorization missing"),
    "frontend-repository-policy-drift.yaml": (1, "repository policy drift cha-pt-frontend"),
    "project-repository-allowlist-drift.yaml": (1, "project repository allowlist drift: cha-pt"),
    "chapt-profile-soul-drift.yaml": (1, "profile SOUL drift chapt-reviewer"),
    "terminal-retry-default-drift.yaml": (1, "terminal retry default drift"),
    "terminal-retry-missing-scope.yaml": (1, "terminal retry policy missing required scope"),
    "terminal-retry-missing-human-gate.yaml": (1, "terminal retry policy missing human/infrastructure exclusion"),
    "ponytail-enabled-drift.yaml": (1, "must be disabled"),
    "ponytail-absent-drift.yaml": (1, "required-disabled ponytail absent"),
    "skill-deployment-missing.yaml": (1, "deployed skill copy missing"),
    "deployment-skill-supporting-file-drift.yaml": (1, "deployed skill hash mismatch"),
    "adapter-missing.yaml": (1, "repository adapter missing"),
    "adoption-status-drift.yaml": (1, "adoption status drift"),
    "adoption-record-drift.yaml": (1, "tracked adoption record status drift"),
    "incomplete-empty.yaml": (1, "incomplete fixture: missing required section"),
    "incomplete-omits-profile.yaml": (1, "incomplete fixture: profile_models omits worker-sol"),
}


def fixture_result(name):
    verifier = load_verifier()
    output = io.StringIO()
    with LocalReads(), patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(ROOT / "tests/fixtures" / name)]), redirect_stdout(output):
        code = verifier.main()
    return code, output.getvalue()


def fixture_matches(name, code, output):
    expected, diagnostic = FIXTURE_RESULTS[name]
    return (type(code) is int and code == expected and diagnostic in output
            and (code != 0 or "FAIL:" not in output))


class UpgradeProportionalityTests(unittest.TestCase):
    def test_frozen_inputs_and_oracle_separation(self):
        inputs = json.loads(CASES.read_text())
        oracle = json.loads(ORACLE.read_text())
        ids = [case["id"] for case in inputs["cases"]]
        self.assertEqual(len(ids), 19)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(oracle["expectations"]))
        self.assertEqual({item.split("-", 1)[0] for item in ids}, {f"U{i}" for i in range(1, 13)})
        self.assertEqual(hashlib.sha256(CASES.read_bytes()).hexdigest(), "ba415e895dac4cc142f92c9c4c929485565a3da6470de1aa0c20412a55eefa9c")
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), "7a3ca137b05744e413a764933bb6b3089c7807233421381bbf1553002a14bf4f")
        for case in inputs["cases"]:
            self.assertEqual(set(case), {"id", "bundle", "state", "authority", "request"})
            self.assertTrue(all(isinstance(value, str) and value for value in case.values()))
            self.assertIn(case["bundle"], inputs["policy_bundles"])
            self.assertTrue(oracle["expectations"][case["id"]])
        # Roster paths belong only to source selectors, never scenario payloads.
        payload = json.dumps({"common": inputs["common"], "cases": inputs["cases"]})
        for forbidden in ("/Users/", "://", "expectations", "expected_actions", "sha256", "JOBCRON_", "CHAPT_"):
            self.assertNotIn(forbidden, payload)
        sources = {path for paths in inputs["policy_bundles"].values() for path in paths}
        self.assertEqual(sources, {DEPLOYMENT, SHARED, *OVERRIDES.values()})
        self.assertTrue(all((ROOT / path).is_file() for path in sources))

    def test_classification_precedes_launch_sequence(self):
        text = (ROOT / DEPLOYMENT).read_text()
        self.assertLess(text.index("## Release change selection"), text.index("## Procedure"))
        section = text.split("## Release change selection", 1)[1].split("## Procedure", 1)[0]
        for clause in ("application-only", "migration-bearing", "infrastructure-changing", "first launch",
                       "Mixed", "smallest material uncertainty", "unchanged platform", "exact-source",
                       "schema-compatible", "current execution prerequisites", "value-blind",
                       "before requesting an execution window", "guessed key names", "missing prose",
                       "publisher", "host replacement", "not a second deployment system"):
            self.assertIn(clause.lower(), section.lower())
        self.assertIn("first-launch sequence", text)
        self.assertIn("only the selected changed surfaces", text)

    def test_applicable_plan_review_is_not_owner_authorization(self):
        deployment = (ROOT / DEPLOYMENT).read_text()
        section = deployment.split("## Release change selection", 1)[1].split("## Procedure", 1)[0]
        for clause in ("concise next-action guidance", "independent review of the exact saved plan before apply",
                       "separately from owner authorization", "not an extra gate for unchanged-platform app-only updates"):
            self.assertIn(clause, section)
        for path in (SHARED, *OVERRIDES.values()):
            section = (ROOT / path).read_text().split("## Routine upgrade selection", 1)[1].split("\n## ", 1)[0]
            for clause in ("independent review of the exact saved plan before apply",
                           "separately from owner authorization", "not an extra gate for unchanged-platform app-only updates"):
                self.assertIn(clause, section)

    def test_shared_rule_and_project_specific_controls(self):
        sections = []
        for path in (SHARED, *OVERRIDES.values()):
            text = (ROOT / path).read_text()
            section = text.split("## Routine upgrade selection", 1)[1].split("\n## ", 1)[0]
            sections.append(section)
            for clause in ("production-deployment", "Release change selection", "application-only", "migration-bearing",
                           "infrastructure-changing", "first launch", "mixed", "unchanged platform",
                           "new-release evidence", "current execution prerequisites", "value-blind", "missing prose",
                           "host replacement", "stale writable database"):
                self.assertIn(clause.lower(), section.lower())
        self.assertTrue(all(section == sections[0] for section in sections))
        jobcron = (ROOT / OVERRIDES["jobcron-orchestrator"]).read_text()
        chapt = (ROOT / OVERRIDES["chapt-orchestrator"]).read_text()
        self.assertIn("owner removed owner/controller-imposed time limits", jobcron)
        self.assertIn("Do not add unrelated collaborator-role or whole-governance audits", chapt)

    def test_retained_safety_clauses(self):
        text = (ROOT / DEPLOYMENT).read_text()
        for clause in ("Preserve global user-stop behavior", "separate external effects", "HUMAN GATE",
                       "independently review the complete action set", "pre-change snapshot",
                       "off-host backup", "successful disposable restore", "exact binary plan",
                       "After the new database accepts writes, keep it authoritative",
                       "not to a stale writable database", "provider-issued credential expiry",
                       "hung-process watchdogs", "minimum stability-observation periods",
                       "Do not create campaign-wide", "stops for reconciliation"):
            self.assertIn(clause, text)
        for path in (SHARED, *OVERRIDES.values()):
            text = (ROOT / path).read_text()
            for clause in ("independent", "credentials/MFA", "When the user says stop", "ambiguous provider response",
                           "Do not create campaign-wide", "provider-issued credential expiry"):
                self.assertIn(clause, text)

    def test_modified_markdown_local_destinations(self):
        with LocalReads():
            for path in (DEPLOYMENT, SHARED, *OVERRIDES.values()):
                text = (ROOT / path).read_text()
                destinations = re.findall(r"\]\(([^)]+)\)", text)
                destinations += re.findall(r"^\s*\[[^\]]+\]:\s+(\S+)", text, re.M)
                for destination in destinations:
                    if "://" not in destination and not destination.startswith("#"):
                        target = (ROOT / path).parent / destination.split("#", 1)[0]
                        self.assertTrue(target.exists(), (path, destination))

    def test_desired_source_pins_not_live_observations(self):
        skill = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())["skill"]
        for name, path in (("production-deployment", DEPLOYMENT), ("multi-agent-coding-orchestrator", SHARED)):
            entry = next(item for item in skill["shared_skills"] if item["name"] == name)
            content = (ROOT / path).read_bytes()
            self.assertEqual(entry["files"]["SKILL.md"], hashlib.sha256(content).hexdigest())
            version = re.search(r"^version: (.+)$", content.decode(), re.M)
            assert version is not None
            self.assertEqual(entry["version"], version.group(1))
        for profile, path in OVERRIDES.items():
            actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            self.assertEqual(skill["profile_local_skill_overrides"][profile]["autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"], actual)
        provenance = skill["source_pin_provenance"]
        self.assertEqual(provenance["baseline"], "84d91a7ba698d38bb31c5b80e04dea0dd002d15f")
        self.assertIn("t_acef09b6", provenance["prior_observed_bindings"])
        self.assertEqual(provenance["upgrade_proportionality"]["baseline"], "fdc59293262e15c0376cfaa9f25244e7c317fc58")
        self.assertIn("not observed deployment", provenance["upgrade_proportionality"]["status"])
        self.assertIn("live rollout unperformed", provenance["upgrade_proportionality"]["status"])

    def test_every_regenerated_fixture_preserves_its_diagnostic(self):
        self.assertEqual({p.name for p in (ROOT / "tests/fixtures").glob("*.yaml")}, set(FIXTURE_RESULTS))
        for name in FIXTURE_RESULTS:
            with self.subTest(name=name):
                code, output = fixture_result(name)
                self.assertTrue(fixture_matches(name, code, output), (code, output))
                # A deliberate mutation must not be hidden by stale desired pins.
                if name not in ("deployed-skill-divergence.yaml", "deployment-skill-supporting-file-drift.yaml", "incomplete-empty.yaml"):
                    self.assertNotIn("deployed skill hash mismatch", output)
                self.assertNotIn("tracked skill hash mismatch", output)
                self.assertNotIn("tracked profile-local skill override hash mismatch", output)
                self.assertNotIn("profile-local skill override declaration drift", output)

    def test_fixture_matching_negative_controls(self):
        for name, (code, diagnostic) in FIXTURE_RESULTS.items():
            with self.subTest(name=name):
                self.assertFalse(fixture_matches(name, 2, diagnostic))
                self.assertFalse(fixture_matches(name, code, "unrelated failure"))
                self.assertFalse(fixture_matches(name, bool(code), diagnostic))
        self.assertFalse(fixture_matches("clean.yaml", 0, "OK: desired state matches observed state\nFAIL: surprise"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
