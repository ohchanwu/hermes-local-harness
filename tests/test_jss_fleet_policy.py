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

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier, resolved_fixture
from rule_text import assert_rule

REPO = "/Users/chanbla11mit/projects/jss-genr"
ORCH, WORKER, WORKER2, REVIEWER = (
    "jss-orchestrator", "jss-worker", "jss-worker-2", "jss-reviewer")
JSS = (ORCH, WORKER, WORKER2, REVIEWER)
WORKERS = (WORKER, WORKER2)
# Retired from dispatch but still deployed; their SOULs are tracked sources too.
GLM_WORKERS = ("jss-worker-glm-1", "jss-worker-glm-2")
NON_ORCH_SOULS = (WORKER, WORKER2, REVIEWER, *GLM_WORKERS)
SITE = "/Users/chanbla11mit/mystuff/projects/ohchanwu.dev"
FLEETS = {"jobcron", "cha-pt", "harness", "jss-genr", "anki"}
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SKILL = ROOT / "policies/profile-skills" / ORCH / RELATIVE
RUN_SCRIPT = ROOT / "scripts/run-jss-orchestrator"
ADOPTION = ROOT / "adoption/jss-genr.md"
CHECKLIST_ABS = "/Users/chanbla11mit/hermes-local-harness/policies/overgating-review.md"
RETIRED_MODEL = re.compile(r"(?i)\bgpt\b|gpt-\d|\b(?:sol|astra|luna|terra)\b|openai-codex")
# Owner decision, 2026-10-18: private content may appear in local/private channels
# (Telegram replies, cards, comments, handoffs, memory) but never in tracked files or commits.
OWNER_EXCEPTION = "(owner decision, 2026-10-18)"
PRIVACY_FORBID = {
    ORCH: "never copy anything from `profile/`, `companies/`, or `resume/resources/` into tracked files or commits.",
    WORKER: "never copy anything from `profile/`, `companies/`, or `resume/resources/` into tracked files or commits.",
    WORKER2: "never copy anything from `profile/`, `companies/`, or `resume/resources/` into tracked files or commits.",
    REVIEWER: "reject any commit or tracked file that copies anything from `profile/`, `companies/`, or `resume/resources/`.",
}


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

    def test_roster_snapshot_and_verifier_agree_on_five_fleets(self):
        fleets = self.roster["project_fleets"]
        self.assertEqual(set(fleets), FLEETS)
        self.assertEqual(self.snapshot["project_isolation"], fleets)
        self.assertEqual(set(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS), FLEETS)
        self.assertEqual(set(self.verifier.PROJECT_LAUNCHERS), FLEETS)
        self.assertEqual(set(self.verifier.ADOPTION_REPOS), FLEETS)
        self.assertEqual(self.verifier.PROJECT_REPAIR_POLICY, self.roster["project_repair_policy"])
        self.assertEqual(self.snapshot["project_repair_policy"], self.roster["project_repair_policy"])
        self.assertEqual(self.roster["project_repair_policy"]["project_boards"],
                         ["jobcron", "cha-pt", "harness", "jss-genr", "anki"])
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
        four = {key: value for key, value in self.roster["project_fleets"].items() if key != "jss-genr"}
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, four)
        self.assertEqual(errors, [
            "project isolation mapping must contain exactly jobcron, cha-pt, harness, jss-genr, and anki"])

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
                self.assertNotIn("sha256", entry)  # derived from the tracked source at check time
                self.assertEqual(self.verifier.profile_soul_expected(entry), sha(ROOT / entry["source"]))
                self.assertEqual(self.verifier.PROFILE_SOUL_PATHS[profile],
                                 {"source": entry["source"], "live": entry["live"]})
        override = self.snapshot["skill"]["profile_local_skill_overrides"][ORCH]
        self.assertEqual(override, {RELATIVE: self.verifier.TRACKED_SOURCE})
        self.assertEqual(self.verifier.local_override_expected(ORCH, RELATIVE, override[RELATIVE]), sha(SKILL))
        # A hand pin beside a tracked source is a duplicate that could go stale.
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_profile_local_skill_overrides(
                errors, {ORCH: {RELATIVE: "0" * 64}})
        self.assertIn(f"duplicated profile-local skill override pin: {ORCH}/{RELATIVE} "
                      f"(a tracked source exists; declare 'tracked-source')", errors)

    def test_fixture_pins_match_tracked_bytes(self):
        souls = {profile: sha(soul_path(profile)) for profile in JSS}
        skill = sha(SKILL)
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = resolved_fixture(fixture)  # "tracked-source" resolved as verify-state does
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
                self.assertIn(PRIVACY_FORBID[profile], body)
                self.assertIn(OWNER_EXCEPTION, body)
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
                "Telegram replies to the owner, card bodies, comments, handoffs, and memory may contain it "
                "(owner decision, 2026-10-18), because they stay local or private."):
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

    def test_write_scope_is_new_files_under_profile_or_one_company(self):
        # Owner, 2026-10-18: scope widened; create-only and the privacy gate unchanged.
        scope = "declared new files under `profile/` or one `companies/<slug>/`"
        for profile, text in self.souls.items():
            with self.subTest(profile=profile):
                self.assertIn(scope, flat(text))
                self.assertNotIn("declared new numbered files", text)
        for marker in (
                "Each target is a new file at any depth under `profile/` or one `companies/<slug>/`.",
                "new files under `profile/` or one `companies/<slug>/` (or owner-confirmed "
                "`profile/facts.md` / `profile/voice.md`)",
                "the targets must not exist yet",
                "create each target exclusively and fail if it exists",
                "Never overwrite, rename, or delete an existing draft or any other file",
                "only when the card records the owner's confirmation by date and notes-file reference"):
            self.assertIn(marker, self.skill)
        for profile in WORKERS:
            with self.subTest(profile=profile):
                body = flat(self.souls[profile])
                self.assertIn("create each exclusively and block if a target already exists", body)
                self.assertIn("Never overwrite, rename, or delete an existing draft", body)
                assert_rule(self, self.souls[profile], "unless the card records the owner's confirmation",
                            "`CLAUDE.md` step")
        self.assertEqual(soul_path(WORKER).read_bytes(), soul_path(WORKER2).read_bytes())
        self.assertIn(scope + " (normally numbered drafts under `companies/<slug>/drafts/`)",
                      flat(ADOPTION.read_text()))

    def test_workers_carry_identical_privacy_paragraph(self):
        paragraphs = {profile: [p for p in self.souls[profile].split("\n\n") if "Privacy is a hard gate" in p]
                      for profile in WORKERS}
        self.assertEqual(len(paragraphs[WORKER]), 1)
        self.assertEqual(paragraphs[WORKER], paragraphs[WORKER2])
        self.assertIn("Card bodies, comments, handoffs, and memory may contain it", flat(paragraphs[WORKER][0]))

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
        self.assertRegex(self.skill_raw, r"(?m)^version: 0\.6\.7-jss\.6$")
        self.assertLessEqual(len(self.skill_raw.splitlines()), 260)
        self.assertEqual(re.findall(r"^## (.+)$", self.skill_raw, re.M), [
            "Hard Scope", "Privacy Gate", "Card Kinds", "Role Separation", "Card Contract",
            "Card Setup", "Worker Selection", "Worktree and Baseline Gate", "Skills",
            "Bounded Autonomous Repair", "Autonomy", "Incident recovery", "Review and Integration",
            "Operational Discipline", "Completion Gate",
        ])

    def test_skill_board_pinning_and_no_foreign_fleets(self):
        # The one sentence that records the 2026-10-20 stalls (t_b6d0e590) names the
        # Jobcron orchestrator as history only; it routes no work to that fleet.
        history = "This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators."
        self.assertEqual(self.skill_raw.count(history), 1)
        lower = self.skill_raw.replace(history, "").lower()
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
            "`kanban_create(..., board: jss-genr, initial_status: blocked)`",
            "write the exact ID, worktree path, and branch into the body",
            "Pin `refs/jss-genr/baselines/<ID>`",
            "Confirm the kanban_create result reports subscribed: true.",
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
                "Never copy anything from them into tracked files or commits. The repository has a public remote.",
                "Owner decision, 2026-10-18: Telegram replies to the owner, card bodies, comments, handoffs, "
                "`repair_history`, and memory may quote or summarize this content.",
                "A leak into a tracked file or commit is a material defect even when everything else passes. "
                "Reviewers reject it; the controller never integrates it.",
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


def section(raw, title):
    return flat(raw.split(f"\n## {title}\n", 1)[1].split("\n## ", 1)[0])


class StandingExceptions(unittest.TestCase):
    """Owner decisions 2026-10-18 (portfolio push) and 2026-10-20 ("grant"): the orchestrator
    SOUL and skill alone carry them; every other jss SOUL keeps no exception."""

    @classmethod
    def setUpClass(cls):
        cls.orch = flat(soul_path(ORCH).read_text())
        cls.others = {profile: flat(soul_path(profile).read_text()) for profile in NON_ORCH_SOULS}
        cls.skill_raw = SKILL.read_text()

    def test_orchestrator_soul_portfolio_exception_and_guardrails(self):
        limits = self.orch.split("The repository has a public remote", 1)[1]
        for marker in (
                "and nothing is ever pushed. Never push, use `gh`, open a PR, deploy",
                "or perform another external write without explicit owner authorization.",
                "Sole standing exception (owner decision, 2026-10-18): when the owner says \"update my portfolio\", "
                "that message authorizes the site change it describes, reviewed site cards, and your own non-force "
                f"`git push origin main` of the reviewed, locally integrated commits in `{SITE}`; it covers nothing "
                "else (no other repository or remote, no force push, no deployment-setting, Terraform, or state "
                "change, no untracked files)."):
            self.assertIn(marker, limits)
        # The exception follows, and never replaces, the general no-push rule.
        self.assertLess(limits.find("nothing is ever pushed"), limits.find("Sole standing exception"))
        self.assertEqual(self.orch.count("update my portfolio"), 1)

    def test_skill_portfolio_exception_and_guardrails(self):
        scope = section(self.skill_raw, "Hard Scope")
        for marker in (
                "nothing is ever pushed",
                "Sole push exception (owner decision, 2026-10-18; this case alone): an owner message saying "
                "\"update my portfolio\" authorizes (a) the site change it describes, (b) reviewed site cards that "
                f"write to `{SITE}` (record the triggering message and date on the card), and (c) the controller's "
                "own `git push origin main` of the reviewed commits after local integration there",
                "`git -C <site> log origin/main..main` shows only the reviewed commits",
                "the diff carries no `profile/`, `companies/`, or `resume/resources/` content",
                "no untracked file (`terraform.tfstate`, `.terraform/`, `docs/` drafts) is staged",
                "Never force-push, push the jss-genr repository, push another branch or remote, use `gh`, "
                "or change deployment settings or Terraform state.",
                "Workers never push.",
                "Anything outside this case still needs explicit owner authorization."):
            self.assertIn(marker, scope)
        self.assertEqual(self.skill_raw.count("update my portfolio"), 2)
        assert_rule(self, self.skill_raw, "- external writes", "push", "PR", "deploy", "application submission",
                    "portfolio-site sync", "except the \"update my portfolio\" site push")

    def test_orchestrator_soul_protected_file_exception_and_guardrails(self):
        role = self.orch.split("Load and follow `multi-agent-coding-orchestrator` before routing work.", 1)[1]
        role = role.split("Every card declares exactly one kind.", 1)[0]
        for marker in (
                "do not edit repository files or write drafts yourself.",
                "Sole edit exception (owner decision, 2026-10-20, \"grant\"): when a dispatched worker cannot get "
                "Hermes's protected-file approval for `AGENTS.md` or `CLAUDE.md`, the worker posts the exact "
                "replacement lines on its card and stops; you apply only those lines, only inside that card's own "
                "`.worktrees/<id>`, only with the file `patch` tool so the owner approves each write through the "
                "Telegram prompt, then unblock the worker to commit, test, and request `jss-reviewer` review.",
                "Never write these files through terminal, scripts, or `execute_code`, never in the main checkout, "
                "and never beyond the card's posted lines; workers never bypass the prompt either."):
            self.assertIn(marker, role)
        self.assertEqual(self.orch.count("\"grant\""), 1)

    def test_skill_protected_file_exception_and_guardrails(self):
        role = section(self.skill_raw, "Role Separation")
        for marker in (
                "Protected-instruction-file exception (owner decision, 2026-10-20, \"grant\")",
                "For repository `AGENTS.md` or `CLAUDE.md` only:",
                "1. The worker posts the exact replacement lines on its card, does not write the file, and blocks "
                "`needs_input`.",
                "2. The controller applies exactly those lines with the file `patch` tool inside that card's "
                "`.worktrees/<id>`, so the owner gets a Telegram Approve prompt for each write. Denied or timed "
                "out: stop and tell the owner; never retry another way.",
                "3. The controller comments what it applied and unblocks the card; the worker commits, tests, and "
                "requests `jss-reviewer` review, which checks the applied lines against the posted text.",
                "Never write these files through terminal, scripts, or `execute_code` (controller or workers), "
                "never in the main checkout, never beyond the posted lines.",
                "workers never bypass the protected-file prompt; they post the lines and block."):
            self.assertIn(marker, role)
        self.assertEqual(self.skill_raw.count("Protected-instruction-file exception"), 1)

    def test_no_other_jss_soul_carries_an_exception(self):
        for profile, body in self.others.items():
            with self.subTest(profile=profile):
                for marker in ("update my portfolio", "ohchanwu.dev", "git push", "Sole standing exception",
                               "Sole edit exception", "\"grant\"", "Protected-instruction-file", "2026-10-20"):
                    self.assertNotIn(marker, body)
                self.assertIn("push", body.lower())
                self.assertIn("without explicit owner authorization", body)

    def test_glm_souls_track_live_worker_contract(self):
        # Same privacy line as every other worker/reviewer; no stale "beyond the company slug" wording.
        line = ("Card bodies, comments, handoffs, and memory may contain it (owner decision, 2026-10-18), "
                "because the board and memory stay local")
        worker_paragraph = next(p for p in soul_path(WORKER).read_text().split("\n\n") if "Privacy is a hard gate" in p)
        for profile, body in self.others.items():
            with self.subTest(profile=profile):
                self.assertEqual(body.count("Privacy is a hard gate"), 1)
                self.assertIn(line, body)
                self.assertNotIn("beyond the company slug", body)
                if profile != REVIEWER:
                    self.assertIn(worker_paragraph, soul_path(profile).read_text())
        for profile in GLM_WORKERS:
            with self.subTest(profile=profile):
                body = self.others[profile]
                self.assertIn("Accept only a dispatcher-assigned card on board `jss-genr`", body)
                self.assertIn(PRIVACY_FORBID[WORKER], body)
                self.assertIn("Do not commit.", body)


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
        # Owner, 2026-10-18: any new file under `profile/` or one `companies/<slug>/`.
        valid = self.verifier.jss_write_targets_valid
        for declaration in (
                "profile/notes.md",
                "profile/research/2026/a.txt",
                "companies/acme/drafts/ko-v3.md",
                "companies/acme/research/x.pdf",
                "companies/acme/a.md, profile/b.md",
                "companies/acme-backend/drafts/ko-v3.md, companies/acme-backend/drafts/notes-v3.md",
                "profile/facts.md, companies/acme-backend/final.md",
                "companies/acme/README"):
            with self.subTest(accept=declaration):
                self.assertTrue(valid(declaration))
        for declaration in (
                "", "companies/acme/a.md,", ",companies/acme/a.md", "companies/acme/a.md,,profile/b.md",
                "/Users/chanbla11mit/projects/jss-genr/companies/acme/drafts/ko-v3.md", "/profile/a.md",
                "profile\\a.md", "companies\\acme\\a.md",
                "profile/a\x07.md", "profile/a\t.md", "profile/a\r.md", "profile/a\x7f.md",
                " profile/a.md", "profile/a.md ", "companies/acme/a.md,  profile/b.md",
                "companies/acme/a.md , profile/b.md", "companies/acme/ a.md",
                "profile/./a.md", "./profile/a.md", "profile/../a.md", "companies/acme/../beta/a.md",
                "companies/acme-backend/../other/drafts/ko-v1.md",
                "profile//a.md", "companies/acme//a.md", "profile/a/", "companies/acme/drafts/",
                "profile", "profile/", "companies/acme", "companies/acme/", "companies",
                "companies/acme/a.md, companies/beta/b.md",
                "companies/acme-backend/drafts/ko-v3.md, profile/a.md, companies/other-role/drafts/ko-v1.md",
                "companies/Acme/drafts/ko-v1.md", "companies/-acme/a.md", "companies/acme_x/a.md",
                "companies/acme-backend/drafts/*.md",
                "resume/resume-en/resume-en.html", "resume/resources/a.pdf", "tools/x.py", "CLAUDE.md",
                "guides/review.md", "profiles/a.md"):
            with self.subTest(reject=declaration):
                self.assertFalse(valid(declaration))

    def test_widened_targets_pass_the_card_contract(self):
        body = WRITING_BODY.replace(
            "Write targets EXACT companies/acme-backend/drafts/ko-v2.md, companies/acme-backend/drafts/notes-v2.md.",
            "Write targets EXACT companies/acme-backend/research/x.pdf, profile/research/2026/a.txt.")
        self.assertEqual(self.errors([card(body)]), [])
        two = WRITING_BODY.replace("companies/acme-backend/drafts/notes-v2.md", "companies/beta/drafts/notes-v2.md")
        self.assertTrue(any("writing-round write targets invalid" in error for error in self.errors([card(two)])))

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
