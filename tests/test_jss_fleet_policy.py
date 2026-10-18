#!/usr/bin/env python3
"""Offline source contract for the jss-genr project fleet.

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

REPO = "/Users/chanbla11mit/projects/jss-genr"
ORCH, WORKER, WORKER2, REVIEWER = (
    "jss-orchestrator", "jss-worker", "jss-worker-2", "jss-reviewer")
JSS = (ORCH, WORKER, WORKER2, REVIEWER)
WORKERS = (WORKER, WORKER2)
FLEETS = {"jobcron", "cha-pt", "harness", "jss-genr"}
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SKILL = ROOT / "policies/profile-skills" / ORCH / RELATIVE
RUN_SCRIPT = ROOT / "scripts/run-jss-orchestrator"
ADOPTION = ROOT / "adoption/jss-genr.md"
CHECKLIST_ABS = "/Users/chanbla11mit/hermes-local-harness/policies/overgating-review.md"
RETIRED_MODEL = re.compile(r"(?i)\bgpt\b|gpt-\d|\b(?:sol|astra|luna|terra)\b|openai-codex")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def soul_path(profile):
    return ROOT / f"policies/profile-souls/{profile}/SOUL.md"


def flat(text):
    return " ".join(text.split())


def load(path):
    return json.loads(path.read_text())


def jss_files():
    return [SKILL, RUN_SCRIPT, ADOPTION, *(soul_path(profile) for profile in JSS)]


class FleetDesiredState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT / "roster.yaml")
        cls.snapshot = load(ROOT / "snapshots/sanitized-current-state.yaml")
        cls.verifier = load_verifier()
        cls.profiles = {profile["name"]: profile for profile in cls.roster["profiles"]}

    def test_roster_snapshot_and_verifier_agree_on_four_fleets(self):
        fleets = self.roster["project_fleets"]
        self.assertEqual(set(fleets), FLEETS)
        self.assertEqual(self.snapshot["project_isolation"], fleets)
        self.assertEqual(set(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS), FLEETS)
        self.assertEqual(set(self.verifier.PROJECT_LAUNCHERS), FLEETS)
        self.assertEqual(set(self.verifier.ADOPTION_REPOS), FLEETS)
        self.assertEqual(self.verifier.PROJECT_REPAIR_POLICY, self.roster["project_repair_policy"])
        self.assertEqual(self.snapshot["project_repair_policy"], self.roster["project_repair_policy"])
        self.assertEqual(self.roster["project_repair_policy"]["project_boards"],
                         ["jobcron", "cha-pt", "harness", "jss-genr"])
        self.assertEqual({adapter["repo"] for adapter in self.snapshot["adoption"]["adapters"]}, FLEETS)
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, fleets, copy.deepcopy(fleets))
        self.assertEqual(errors, [])

    def test_jss_fleet_mapping(self):
        self.assertEqual(self.roster["project_fleets"]["jss-genr"], {
            "board": "jss-genr",
            "repository": REPO,
            "repositories": [REPO],
            "orchestrator": ORCH,
            "worker": WORKER,
            "reviewer": REVIEWER,
            "workers": list(WORKERS),
        })
        self.assertEqual(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS["jss-genr"], [REPO])
        self.assertIn("jss-genr", self.verifier.PROJECTS_WITHOUT_PREVIEW_PORT)
        with_port = copy.deepcopy(self.roster["project_fleets"])
        with_port["jss-genr"]["preview_port"] = 19191
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, with_port)
        self.assertIn("project isolation preview port invalid: jss-genr", errors)
        three = {key: value for key, value in self.roster["project_fleets"].items() if key != "jss-genr"}
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, three)
        self.assertEqual(errors, [
            "project isolation mapping must contain exactly jobcron, cha-pt, harness, and jss-genr"])

    def test_profiles_models_and_dispatch(self):
        expected = {
            ORCH: ("claude-opus-5-5", "claude-subscription", "orchestrator", False),
            WORKER: ("claude-opus-5-5", "claude-subscription", "implementation", True),
            WORKER2: ("claude-opus-5-5", "claude-subscription", "implementation", True),
            REVIEWER: ("claude-fable-5-1", "claude-subscription", "review", True),
        }
        for name, (model, provider, toolsets, dispatchable) in expected.items():
            with self.subTest(profile=name):
                profile = self.profiles[name]
                self.assertEqual((profile["model"], profile["provider"], profile["toolsets"]),
                                 (model, provider, toolsets))
                self.assertEqual(profile["dispatch_eligible"], dispatchable)
                self.assertEqual(profile["lifecycle"], "project-active")
                self.assertIn("jss-genr", profile["modes"])
                self.assertEqual(profile["required_plugins"], [])
                self.assertIn("hermes-terminal-outcome-notification", profile["installed_disabled_plugins"])
                self.assertIsNone(RETIRED_MODEL.search(profile["model"] + " " + profile["provider"]))
        self.assertEqual(self.roster["approval_policy"]["profiles"], list(self.profiles))
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])
        self.assertEqual(self.snapshot["profiles"], list(self.profiles))
        for listing in (self.roster["project_dispatch_allowlist"], self.snapshot["kanban"]["dispatch_profiles"]):
            # The second worker was appended after the reviewer in the live dispatch order.
            self.assertEqual([name for name in listing if name.startswith("jss-")], [WORKER, REVIEWER, WORKER2])
            self.assertNotIn(ORCH, listing)

    def test_skill_deployment_matrix(self):
        shared = {entry["name"]: entry for entry in self.snapshot["skill"]["shared_skills"]}
        self.assertIn(ORCH, shared["multi-agent-coding-orchestrator"]["deploy_profiles"])
        for name in ("minimal-implementation", "simplification-review"):
            for profile in WORKERS:
                self.assertIn(profile, shared[name]["deploy_profiles"])
        # A fleet that never deploys gets no deployment skills.
        for name in ("production-deployment", "production-deployment-planning"):
            for profile in JSS:
                self.assertNotIn(profile, shared[name]["deploy_profiles"])
        provenance = self.snapshot["skill"]["source_pin_provenance"]["jss_genr_fleet"]
        self.assertEqual(provenance["baseline"], "8c9cd47d06f1d71dd5e8c448334aa17ebb050a20")
        self.assertIn("not observed deployment", provenance["status"])
        self.assertIn("live setup unperformed", provenance["status"])

    def test_pinned_hashes_equal_tracked_bytes(self):
        souls = self.roster["profile_souls"]
        self.assertEqual(self.snapshot["profile_souls"], souls)
        for profile in JSS:
            with self.subTest(profile=profile):
                entry = souls[profile]
                self.assertEqual(entry["source"], f"policies/profile-souls/{profile}/SOUL.md")
                self.assertEqual(entry["live"], f"/Users/chanbla11mit/.hermes/profiles/{profile}/SOUL.md")
                self.assertEqual(entry["sha256"], sha(ROOT / entry["source"]))
                self.assertEqual(self.verifier.PROFILE_SOUL_PATHS[profile],
                                 {"source": entry["source"], "live": entry["live"]})
        override = self.snapshot["skill"]["profile_local_skill_overrides"][ORCH]
        self.assertEqual(override, {RELATIVE: sha(SKILL)})
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_profile_local_skill_overrides(
                errors, {ORCH: {RELATIVE: "0" * 64}})
        self.assertEqual(errors, [f"tracked profile-local skill override hash mismatch: {ORCH}/{RELATIVE}"])

    def test_fixture_pins_match_tracked_bytes(self):
        souls = {profile: sha(soul_path(profile)) for profile in JSS}
        skill = sha(SKILL)
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = load(fixture)
            if fixture.name == "incomplete-empty.yaml":
                self.assertEqual(data, {})
                continue
            with self.subTest(fixture=fixture.name):
                for profile, want in souls.items():
                    self.assertEqual(data["profile_soul_hashes"][profile], want)
                self.assertEqual(data["profile_local_skill_overrides"][ORCH][RELATIVE], skill)
                self.assertIn("jss-genr", data["project_isolation"])


class RoleContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.souls = {profile: soul_path(profile).read_text() for profile in JSS}
        cls.skill_raw = SKILL.read_text()
        cls.skill = flat(cls.skill_raw)

    def test_run_script(self):
        self.assertEqual(RUN_SCRIPT.read_text(), (
            "#!/bin/sh\n"
            "set -eu\n"
            'exec env HERMES_KANBAN_BOARD=jss-genr jss-orchestrator chat --in /Users/chanbla11mit/projects/jss-genr "$@"\n'))
        self.assertEqual(RUN_SCRIPT.stat().st_mode & 0o777, 0o755)
        self.assertFalse(RUN_SCRIPT.is_symlink())

    def test_no_new_file_names_a_retired_model(self):
        for path in jss_files():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(RETIRED_MODEL.search(path.read_text()))

    def test_souls_are_model_neutral(self):
        for profile, text in self.souls.items():
            with self.subTest(profile=profile):
                self.assertNotRegex(text, r"(?i)running (GPT|Fable|Claude|GLM|Opus)")
                self.assertNotRegex(text, r"(?i)\b(opus|fable|glm-5)")

    def test_hard_scope_in_every_soul(self):
        for profile, text in self.souls.items():
            body = flat(text)
            with self.subTest(profile=profile):
                self.assertIn("board `jss-genr`", body)
                self.assertIn(f"`{REPO}`", body)
                self.assertIn("same-card", body)
                if profile != REVIEWER:
                    self.assertIn("`jss-reviewer`", body)
                if profile in (ORCH, REVIEWER):
                    for worker in WORKERS:
                        self.assertIn(f"`{worker}`", body)

    def test_card_kinds_privacy_overwrite_and_limits_in_every_soul(self):
        for profile, text in self.souls.items():
            body = flat(text)
            lower = body.lower()
            with self.subTest(profile=profile):
                self.assertIn("Repository card", body)
                self.assertIn("Writing-round card", body)
                self.assertIn("companies/<slug>/drafts/", body)
                self.assertIn("Privacy is a hard gate", body)
                for folder in ("`profile/`", "`companies/`", "`resume/resources/`"):
                    self.assertIn(folder, body)
                self.assertIn("beyond the company slug and file names", body)
                self.assertRegex(body, r"[Nn]ever overwrite, rename, or delete an existing draft")
                for limit in ("push", "open a pr", "deploy", "submit an application",
                              "log in to a job site", "credentials", "external write"):
                    self.assertIn(limit, lower)
                for foreign in ("Jobcron", "Cha PT"):
                    self.assertIn(foreign, body)

    def test_orchestrator_soul(self):
        body = flat(self.souls[ORCH])
        for marker in (
                "Load and follow `multi-agent-coding-orchestrator` before routing work.",
                "Pass `board: jss-genr` explicitly on every Kanban operation.",
                "Every card declares exactly one kind.",
                "`profile/facts.md` and `profile/voice.md` change only after the owner's explicit confirmation",
                "Unverified facts, sensitive material, suggestion choices, and \"final\" are owner decisions.",
                "Telegram summaries"):
            self.assertIn(marker, body)

    def test_worker_souls(self):
        for profile in WORKERS:
            body = flat(self.souls[profile])
            with self.subTest(profile=profile):
                self.assertIn("Accept only a dispatcher-assigned card on board `jss-genr`", body)
                self.assertIn("block without editing", body)
                self.assertIn("create each exclusively and block if a target already exists", body)
                self.assertIn("Do not commit.", body)
                self.assertIn("never install, download, or commit dependencies", body)
                self.assertIn("Never delegate", body)

    def test_reviewer_soul_and_overgating_rule(self):
        text = self.souls[REVIEWER]
        body = flat(text)
        self.assertEqual(text.count(CHECKLIST_ABS), 1)
        for marker in (
                "Accept review only for a card on board `jss-genr`",
                "Reject and block any boundary mismatch.",
                "Never edit implementation code or the reviewed drafts.",
                "Use `kanban_complete` for approval and `kanban_request_changes` for actionable same-card rework.",
                "`guides/review.md`", "`.claude/agents/jss-reviewer.md`", "`python3 tools/charcount.py`",
                "`companies/<slug>/reviews/<draft>-review.md`",
                "would block, stall, or add owner prompts to otherwise authorized work is a material finding",
                "naming the gate, why its mechanism is absent or not live, and the proportionate replacement",
                "Minor ceremony that blocks nothing is a non-blocking note in the approval.",
                "grants no new authority, and never weakens the boundaries in this file"):
            self.assertIn(marker, body)
        paragraph = next(p for p in text.split("\n\n") if CHECKLIST_ABS in p)
        self.assertLessEqual(len(paragraph.splitlines()), 6)
        self.assertLessEqual(len(paragraph), 1000)

    def test_skill_version_size_and_sections(self):
        self.assertRegex(self.skill_raw, r"(?m)^version: 0\.6\.7-jss\.3$")
        self.assertLessEqual(len(self.skill_raw.splitlines()), 260)
        self.assertEqual(re.findall(r"^## (.+)$", self.skill_raw, re.M), [
            "Hard Scope", "Privacy Gate", "Card Kinds", "Role Separation", "Card Contract",
            "Card Setup", "Worker Selection", "Worktree and Baseline Gate", "Skills",
            "Bounded Autonomous Repair", "Autonomy", "Incident recovery", "Review and Integration",
            "Operational Discipline", "Completion Gate",
        ])

    def test_skill_board_pinning_and_no_foreign_fleets(self):
        lower = self.skill_raw.lower()
        for foreign in ("jobcron", "cha-pt", "chapt-", "harness-orchestrator", "harness-worker",
                        "harness-reviewer", "board: harness", "--board harness"):
            self.assertNotIn(foreign, lower)
        for line in self.skill_raw.splitlines():
            if "hermes kanban " in line:
                self.assertIn("--board jss-genr", line)
        for call in re.findall(r"kanban_[a-z_]+\(([^)]*)\)", self.skill_raw):
            self.assertIn("board: jss-genr", call)

    def test_skill_required_rules(self):
        setup = flat(self.skill_raw.split("## Card Setup", 1)[1].split("\n## ", 1)[0])
        order = [
            "`hermes kanban --board jss-genr create ... --initial-status blocked` before any notification subscription exists",
            "write the exact ID, worktree path, and branch into the body",
            "Pin `refs/jss-genr/baselines/<ID>`",
            "`hermes kanban --board jss-genr notify-subscribe`",
            "Unblock the card so it becomes `ready`",
        ]
        positions = [setup.find(marker) for marker in order]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Never claim a card and `kanban_block` it as a setup hold.", setup)
        for marker in (
                "Pass `board: jss-genr` on every Kanban tool call.",
                "The sole independent reviewer is `jss-reviewer`.",
                "`Card kind EXACT repository.` or `Card kind EXACT writing-round.`",
                "`Write targets EXACT <files>.`",
                "`Repository /Users/chanbla11mit/projects/jss-genr ONLY.`",
                "`Baseline EXACT <40-hex-commit>.`",
                "`Reviewer EXACT jss-reviewer.`",
                "Privacy is a hard gate on every card.",
                "Never overwrite, rename, or delete an existing draft",
                "Keep at most one open writing-round card per company slug",
                "nothing is ever pushed",
                "submit an application, or log in to a job site",
                "Bookkeeping never gates.",
                "Stale callbacks: run one `kanban_show(..., board: jss-genr)`.",
                "No numeric caps on harmless actions",
                "check semantic validity, not bookkeeping-format validity",
                "reviewed by `jss-reviewer` on the same card",
                "An incident neither grants new authority nor automatically revokes unrelated authority.",
                "User stop remains global",
                "Never modify the installed Hermes source."):
            self.assertIn(marker, self.skill)
        autonomy = flat(self.skill_raw.split("## Autonomy", 1)[1].split("\n## ", 1)[0])
        only = autonomy.split("Ask only for:", 1)[1].split("Stale callbacks:", 1)[0]
        for item in ("unverified facts (`CLAUDE.md` rule 1)", "sensitive material (rule 6)",
                     "which suggestions to adopt", "\"final\"", "`profile/facts.md` or `profile/voice.md`",
                     "a user stop or resume"):
            self.assertIn(item, only)

    def test_adoption_record(self):
        text = ADOPTION.read_text()
        adapter = next(item for item in load(ROOT / "snapshots/sanitized-current-state.yaml")["adoption"]["adapters"]
                       if item["repo"] == "jss-genr")
        self.assertEqual(adapter["path"], f"{REPO}/CLAUDE.md")
        self.assertIn(adapter["path"], text)
        self.assertIn(adapter["record_marker"], text)
        clean = load(ROOT / "tests/fixtures/clean.yaml")
        observed = next(item for item in clean["adapters"] if item["repo"] == "jss-genr")
        # The fixture carries only the public marker line, never other jss-genr content.
        self.assertEqual(observed, {"repo": "jss-genr", "content": adapter["marker"], "record": text})


def card(body, **changes):
    task = {"id": "t_jss", "board": "jss-genr", "body": body, "assignee": WORKER,
            "workspace_kind": "worktree", "workspace_path": f"{REPO}/.worktrees/t_jss"}
    task.update(changes)
    return task


REPOSITORY_BODY = (
    f"Repository {REPO} ONLY.\n"
    f"Baseline EXACT {'b' * 40}.\n"
    "Card kind EXACT repository.\n"
    "## Tests\n- `make -C resume qa`\n"
    "Reviewer EXACT jss-reviewer.\n")
WRITING_BODY = (
    f"Repository {REPO} ONLY.\n"
    f"Baseline EXACT {'c' * 40}.\n"
    "Card kind EXACT writing-round.\n"
    "Write targets EXACT companies/acme-backend/drafts/ko-v2.md, companies/acme-backend/drafts/notes-v2.md.\n"
    "## Tests\n- `python3 tools/charcount.py companies/acme-backend/drafts/ko-v2.md --limit 1000`\n"
    "Reviewer EXACT jss-reviewer.\n")


class CardContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()

    def errors(self, tasks):
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_jss_card_contract(errors, tasks)
        return errors

    def test_valid_cards_of_both_kinds(self):
        self.assertEqual(self.errors([card(REPOSITORY_BODY), card(WRITING_BODY)]), [])
        generic = REPOSITORY_BODY.replace("- `make -C resume qa`", "- `python3 tools/check-materials.py --no-links`")
        self.assertEqual(self.errors([card(generic)]), [])

    def test_boundary_mutations_fail_closed(self):
        for base, changed, expected in (
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY.replace(f"Repository {REPO} ONLY.\n", "")},
                 "expected exact repository"),
                (REPOSITORY_BODY, {"workspace_path": REPO}, "isolated worktree mismatch"),
                (REPOSITORY_BODY, {"workspace_path": f"/Users/chanbla11mit/hermes-local-harness/.worktrees/t_jss"},
                 "isolated worktree mismatch"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY.replace(f"Baseline EXACT {'b' * 40}.\n", "")},
                 "exact baseline missing"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY.replace("- `make -C resume qa`", "Check it by eye.")},
                 "explicit test contract missing"),
                (REPOSITORY_BODY, {"assignee": "harness-worker"}, "jss-genr worker assignment invalid"),
                (REPOSITORY_BODY, {"assignee": ORCH}, "jss-genr worker assignment invalid"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY.replace("Reviewer EXACT jss-reviewer.\n", "")},
                 "independent review contract missing"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY.replace("Card kind EXACT repository.\n", "")},
                 "card kind declaration missing"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY + "Card kind EXACT writing-round.\n"},
                 "card kind declaration missing"),
                (REPOSITORY_BODY, {"body": REPOSITORY_BODY + "Write targets EXACT companies/acme-backend/drafts/ko-v9.md.\n"},
                 "repository card declares write targets"),
                (WRITING_BODY, {"body": re.sub(r"(?m)^Write targets EXACT .*\n", "", WRITING_BODY)},
                 "writing-round write targets invalid")):
            with self.subTest(expected=expected, changed=str(changed)[:60]):
                errors = self.errors([card(**{"body": base, **changed})])
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_write_targets_are_concrete_and_single_company(self):
        valid = self.verifier.jss_write_targets_valid
        self.assertTrue(valid("companies/acme-backend/drafts/ko-v3.md, companies/acme-backend/drafts/notes-v3.md"))
        self.assertTrue(valid("profile/facts.md, companies/acme-backend/final.md"))
        for declaration in (
                "companies/acme-backend/drafts/ko-v3.md, companies/other-role/drafts/ko-v1.md",
                "companies/acme-backend/../other/drafts/ko-v1.md",
                "companies/acme-backend/drafts/*.md",
                "/Users/chanbla11mit/projects/jss-genr/companies/acme-backend/drafts/ko-v3.md",
                "profile/sensitive.md",
                "resume/resume-en/resume-en.html",
                "companies/Acme/drafts/ko-v1.md",
                "companies/acme-backend//drafts/ko-v1.md",
                ""):
            with self.subTest(declaration=declaration):
                self.assertFalse(valid(declaration))

    def test_boards_do_not_cross_check(self):
        harness_card = card(REPOSITORY_BODY, board="harness")
        self.assertEqual(self.errors([harness_card]), [])
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_harness_card_contract(errors, [card(REPOSITORY_BODY)])
        self.assertEqual(errors, [])
        self.assertEqual(self.errors(None), ["jss-genr card contract observation malformed"])


def fixture_main(fixture):
    verifier = load_verifier()
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="jss-fleet-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(fixture))
        guard = LocalReads()
        guard.allowed.add(os.path.abspath(path))
        with guard, patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
            code = verifier.main()
    return code, output.getvalue()


class FixtureMode(unittest.TestCase):
    """Real verifier main() under the no-command/no-network/worktree-only guard."""

    @classmethod
    def setUpClass(cls):
        cls.clean = load(ROOT / "tests/fixtures/clean.yaml")

    def test_clean_with_valid_jss_cards_passes(self):
        fixture = copy.deepcopy(self.clean)
        fixture["project_repair_cards"] = [card(REPOSITORY_BODY), card(WRITING_BODY, id="t_w",
                                                                         workspace_path=f"{REPO}/.worktrees/t_w")]
        code, output = fixture_main(fixture)
        self.assertEqual(code, 0, output)
        self.assertNotIn("FAIL:", output)

    def test_invalid_jss_card_is_red(self):
        fixture = copy.deepcopy(self.clean)
        fixture["project_repair_cards"] = [card(REPOSITORY_BODY, assignee="chapt-worker")]
        code, output = fixture_main(fixture)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: jss-genr card contract drift t_jss: jss-genr worker assignment invalid", output)

    def test_jss_drift_is_red(self):
        for mutate, diagnostic in (
                (lambda d: d["profile_soul_hashes"].__setitem__(REVIEWER, "0" * 64),
                 f"profile SOUL drift {REVIEWER}"),
                (lambda d: d["profile_models"].__setitem__(WORKER, "wrong-model"),
                 f"model drift {WORKER}"),
                (lambda d: d["plugins"][WORKER].__setitem__("ponytail", "enabled      git pinned@16f29800 4.8.4    ponytail"),
                 f"ponytail enabled drift {WORKER}"),
                (lambda d: d["project_isolation"]["jss-genr"]["repositories"].append("/Users/chanbla11mit/projects/other"),
                 "project repository allowlist drift: jss-genr"),
                (lambda d: d["skill_files"]["minimal-implementation"].pop(WORKER),
                 f"deployed skill copy missing: minimal-implementation {WORKER}"),
                (lambda d: next(a for a in d["adapters"] if a["repo"] == "jss-genr").__setitem__("content", "changed"),
                 "adoption status drift jss-genr")):
            with self.subTest(diagnostic=diagnostic):
                fixture = copy.deepcopy(self.clean)
                mutate(fixture)
                code, output = fixture_main(fixture)
                self.assertEqual(code, 1, output)
                self.assertIn(diagnostic, output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
