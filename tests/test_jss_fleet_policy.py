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
from jss_download_install_edits import reverse_download_install_edits
from rule_text import assert_rule
from test_jev_policy_sources import reverse_jev_policy_edits

REPO = "/Users/chanbla11mit/projects/jss-genr"
ORCH, WORKER, WORKER2, REVIEWER = (
    "jss-orchestrator", "jss-worker", "jss-worker-2", "jss-reviewer")
JSS = (ORCH, WORKER, WORKER2, REVIEWER)
WORKERS = (WORKER, WORKER2)
# Back in service for the jev plugin since 2026-11-12 (card t_71b4ef4a); their SOULs are
# tracked sources too.
GLM_WORKERS = ("jss-worker-glm-1", "jss-worker-glm-2", "jss-worker-glm-3")
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

# Owner decision, 2026-11-11 (t_3af6293c): jss-orchestrator and jss-reviewer may read the
# committed content of four other repositories. Each changed source states the exception
# on exactly one line that starts with (or, in the skill, follows "- ") this lead.
EXCEPTION_LEAD = "Read-only repository exception (owner decision, 2026-11-11)"
FOREIGN_REPOS = (
    "/Users/chanbla11mit/projects/jobcron",
    "/Users/chanbla11mit/projects/cha-pt",
    "/Users/chanbla11mit/projects/cha-pt-frontend",
    "/Users/chanbla11mit/projects/cha-webpt-website-sync",
)
PERMITTED_COMMANDS = ("git log", "git show", "git grep", "git ls-tree", "git diff", "git rev-parse",
                      "git merge-base")
PROHIBITED_COMMANDS = ("git fetch", "git pull", "git checkout", "git switch", "git worktree", "git stash",
                       "git commit", "git push")
EXCEPTION_REPOSITORIES = (
    "read the committed content of these four repositories: `/Users/chanbla11mit/projects/jobcron`, "
    "`/Users/chanbla11mit/projects/cha-pt`, `/Users/chanbla11mit/projects/cha-pt-frontend`, and "
    "`/Users/chanbla11mit/projects/cha-webpt-website-sync`.")
EXCEPTION_PERMITTED = (
    "Read from the refs `main` and `origin/main` only, never from the working tree, and only with these "
    "Git commands, which do not write: `git log`, `git show`, `git grep`, `git ls-tree`, `git diff` "
    "between two commits, `git rev-parse`, and `git merge-base`.")
EXCEPTION_PROHIBITED = (
    "Never write in those repositories; never run `git fetch`, `git pull`, `git checkout`, `git switch`, "
    "`git worktree`, `git stash`, `git commit`, or `git push` in them; never read `.worktrees/`, local task "
    "branches, untracked files, `.env` files, files ignored by Git (this includes the per-release deployment "
    "guides and the saved WebPT sign-in state in the `cha-webpt-website-sync` working directory), or anything "
    "under `/Users/chanbla11mit/cha-pt-pipeline/`; never access boards `jobcron` or `cha-pt`, the Jobcron or "
    "Cha PT profiles or their sessions, credentials, or production or cloud state; and never create a card "
    "on board `jss-genr` pinned to any of those repositories.")
EXCEPTION_MERGED_NOT_DEPLOYED = (
    "These repositories show what is merged, not what is deployed: a deploy date or a statement that a "
    "feature is live still needs an owner statement or a deployment record.")
EXCEPTION_SHA_AND_DATE = (
    "Because `git fetch` is prohibited, `origin/main` can be older than GitHub; record the commit SHA and its "
    "commit date with every fact taken from these repositories.")
EXCEPTION_PRIVACY = (
    "The privacy gate applies unchanged to everything read from them: the Jobcron repository is private and "
    "carries an all-rights-reserved notice, and the Cha PT repositories, including the WebPT exporter, "
    "contain clinic operations documents. Nothing read from them is copied into tracked files or commits of "
    "the jss-genr repository")
EXCEPTION_RULES = (EXCEPTION_REPOSITORIES, EXCEPTION_PERMITTED, EXCEPTION_PROHIBITED,
                   EXCEPTION_MERGED_NOT_DEPLOYED, EXCEPTION_SHA_AND_DATE, EXCEPTION_PRIVACY)
# The jev plugin policy change (t_71b4ef4a) named the four jss-genr implementation profiles; card
# t_f4ce916d added the third GLM worker.
REVIEWER_FIRST_LINE = (
    "You are the independent jss-genr reviewer. Accept review only for a card on board `jss-genr`, "
    "implemented by one of the five jss-genr implementation profiles `jss-worker`, `jss-worker-2`, "
    "`jss-worker-glm-1`, `jss-worker-glm-2` or `jss-worker-glm-3`, and pinned to repository "
    "`/Users/chanbla11mit/projects/jss-genr`.")
# Sentences that limit access to other repositories name the exception instead of contradicting it.
ACCESS_LIMIT = re.compile(r"(?i)never access|or access jobcron|may not probe|operate only on|use only `")
EXCEPTION_REFERENCE = "the reads that the read-only repository exception"
# SHA-256 at baseline f501e8a1dd9908b2efa3c1a9cead187b4fa445de. The four worker SOULs are unchanged
# by t_3af6293c; the three changed sources return to these bytes once its edits are reversed.
BASELINE_SHA256 = {
    "policies/profile-souls/jss-worker/SOUL.md": "cc0c68296eba80371bfca434030db69476f7a57394e84a86f21e1cf5a22c9ca5",
    "policies/profile-souls/jss-worker-2/SOUL.md": "cc0c68296eba80371bfca434030db69476f7a57394e84a86f21e1cf5a22c9ca5",
    "policies/profile-souls/jss-worker-glm-1/SOUL.md": "28d6f9b3459494330b76d18480123d54e0a082c857b29bb207473a4c2bbb9eb2",
    "policies/profile-souls/jss-worker-glm-2/SOUL.md": "4c51476e5a709c1aa3bc6cf1fac9e1e2e8801930311c91d4aab799c783440be6",
    "policies/profile-souls/jss-orchestrator/SOUL.md": "4d6e0736e5ecbfaa94f2c2cee235b85dc8bab3839f7b62f10ebca48d8df2e592",
    "policies/profile-souls/jss-reviewer/SOUL.md": "6d59dda4f71bd06e1a20e5f32b8114c323738c443b74abea61dbae68e0d15dec",
    f"policies/profile-skills/{ORCH}/{RELATIVE}": "963b584080646beeee54a60562bc550025bdf78f5cb99254fab20951cdadc9e7",
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


def exception_line(raw):
    """The one line of a changed source that states the read-only repository exception."""
    lines = [line for line in raw.splitlines() if EXCEPTION_LEAD in line]
    assert len(lines) == 1, f"expected one exception line, found {len(lines)}"
    return lines[0]


def without_exception(raw):
    """The source text with its exception line removed (unchanged when it has none)."""
    return "\n".join(line for line in raw.splitlines() if EXCEPTION_LEAD not in line)


ORCH_SOUL_RELATIVE = f"policies/profile-souls/{ORCH}/SOUL.md"
REVIEWER_SOUL_RELATIVE = f"policies/profile-souls/{REVIEWER}/SOUL.md"
SKILL_RELATIVE = f"policies/profile-skills/{ORCH}/{RELATIVE}"
PERMITS = "the reads that the read-only repository exception below permits"


def _read_only_exception_edits():
    """File -> ((new text, old text), ...) for the t_3af6293c edits. Each new text occurs once."""
    orch = exception_line(soul_path(ORCH).read_text())
    reviewer = exception_line(soul_path(REVIEWER).read_text())
    skill = exception_line(SKILL.read_text())
    return {
        ORCH_SOUL_RELATIVE: (
            (f", apart from {PERMITS}. Load", ". Load"),
            (f"your skill names and {PERMITS}.\n\n{orch}\n", "your skill names.\n"),
        ),
        REVIEWER_SOUL_RELATIVE: (
            (f"without explicit owner authorization, apart from {PERMITS}.\n\n{reviewer}\n",
             "without explicit owner authorization.\n"),
        ),
        SKILL_RELATIVE: (
            (f"`/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`, apart from {PERMITS}.\n",
             "`/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`.\n"),
            (f"profile fleet, or worktree, apart from {PERMITS}. The portfolio",
             "profile fleet, or worktree. The portfolio"),
            (f"\n{skill}\n", "\n"),
            (" and the reads that the read-only repository exception in Hard Scope permits, jss-genr",
             ", jss-genr"),
        ),
    }


READ_ONLY_EXCEPTION_EDITS = _read_only_exception_edits()


def reverse_read_only_exception_edits(relative_path, text):
    """Return text with the t_3af6293c edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in READ_ONLY_EXCEPTION_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


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
            ORCH: ("claude-fable-5-2", "claude-subscription", "orchestrator", False),
            WORKER: ("claude-opus-5-5", "claude-subscription", "implementation", True),
            WORKER2: ("claude-opus-5-5", "claude-subscription", "implementation", True),
            REVIEWER: ("claude-opus-5-5", "claude-subscription", "review", True),
        }
        for name, (model, provider, toolsets, dispatchable) in expected.items():
            with self.subTest(profile=name):
                profile = self.profiles[name]
                self.assertEqual((profile["model"], profile["provider"], profile["toolsets"]),
                                 (model, provider, toolsets))
                self.assertEqual(profile["dispatch_eligible"], dispatchable)
                self.assertEqual(profile["lifecycle"], "project-active")
                self.assertIn("jss-genr", profile["modes"])
                # jev is a required plugin on every Claude project profile (card t_4f7740d0).
                self.assertEqual(profile["required_plugins"], ["jev"])
                self.assertIn("hermes-terminal-outcome-notification", profile["installed_disabled_plugins"])
                self.assertIsNone(RETIRED_MODEL.search(profile["model"] + " " + profile["provider"]))
        self.assertEqual(self.roster["approval_policy"]["profiles"], list(self.profiles))
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])
        self.assertEqual(self.snapshot["profiles"], list(self.profiles))
        for listing in (self.roster["project_dispatch_allowlist"], self.snapshot["kanban"]["dispatch_profiles"]):
            # The second worker was appended after the reviewer in the live dispatch order; the
            # GLM workers were appended for the jev plugin (card t_71b4ef4a).
            self.assertEqual([name for name in listing if name.startswith("jss-")],
                             [WORKER, REVIEWER, WORKER2, *GLM_WORKERS])
            self.assertNotIn(ORCH, listing)
        for name in GLM_WORKERS:
            with self.subTest(glm_worker=name):
                profile = self.profiles[name]
                self.assertEqual((profile["model"], profile["provider"], profile["toolsets"]),
                                 ("glm-5.3", "zai", "implementation"))
                self.assertEqual(profile["lifecycle"], "project-active")
                self.assertTrue(profile["dispatch_eligible"])
                self.assertTrue(profile["in_dispatch_pool"])
                self.assertEqual(profile["modes"], ["project-isolated", "jss-genr"])
                self.assertEqual(profile["required_plugins"], ["jev"])
                self.assertNotIn("retired_on", profile)

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
                # Owner decision, 2026-11-13 (t_89838618): downloads and installs from a reputable source
                # are permitted; DownloadAndInstallOwnerDecision pins the full sentence.
                self.assertIn("never commit dependencies", body)
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
        # Raised by the jev plugin policy change (t_71b4ef4a).
        self.assertRegex(self.skill_raw, r"(?m)^version: 0\.6\.7-jss\.14$")  # raised by t_ac454595, t_46b5e63e, t_89838618, t_f4ce916d and t_c7cc3830
        # 260 lines plus the 4-line Pitfalls section (t_bd860536), the 9 lines of
        # repair_history candidate rules and example (t_6436ac1c), the 6-line
        # Skill Changes section (t_0a8674fe) and the one-line Hard Scope read-only
        # repository exception (t_3af6293c), which fits inside the same cap, plus the
        # jev plugin lines in Hard Scope and Worker Selection (t_71b4ef4a), plus the 5 lines of the card
        # splitting rule (with its blank line) and the 3 jev routing bullets in Worker Selection (t_ac454595),
        # plus the one-line Hard Scope list item of the owner decision of 2026-11-13 (t_89838618).
        self.assertLessEqual(len(self.skill_raw.splitlines()), 281 + 5 + 1)
        self.assertEqual(re.findall(r"^## (.+)$", self.skill_raw, re.M), [
            "Hard Scope", "Privacy Gate", "Card Kinds", "Role Separation", "Card Contract",
            "Card Setup", "Worker Selection", "Worktree and Baseline Gate", "Skills", "Skill Changes",
            "Bounded Autonomous Repair", "Autonomy", "Incident recovery", "Review and Integration",
            "Operational Discipline", "Completion Gate", "Pitfalls",
        ])

    def test_skill_board_pinning_and_no_foreign_fleets(self):
        # The one sentence that records the 2026-10-20 stalls (t_b6d0e590) names the
        # Jobcron orchestrator as history only; it routes no work to that fleet.
        history = "This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators."
        self.assertEqual(self.skill_raw.count(history), 1)
        # The one Hard Scope line of the read-only repository exception (owner decision,
        # 2026-11-11) names the four repositories it may read and the boards it may not
        # access; ReadOnlyRepositoryException pins that line. It routes no work to them.
        self.assertTrue(exception_line(self.skill_raw).startswith(f"- {EXCEPTION_LEAD}: "))
        lower = without_exception(self.skill_raw).replace(history, "").lower()
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
        # The reviewer alone also carries the read-only repository exception (owner decision,
        # 2026-11-11); its `git push` appears only in that line's prohibited-command list.
        # ReadOnlyRepositoryException pins that line, so it is removed before this check.
        for profile in NON_ORCH_SOULS:
            with self.subTest(profile=profile):
                self.assertEqual(soul_path(profile).read_text().count(EXCEPTION_LEAD),
                                 1 if profile == REVIEWER else 0)
        for profile in NON_ORCH_SOULS:
            body = flat(without_exception(soul_path(profile).read_text()))
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


class ReadOnlyRepositoryException(unittest.TestCase):
    """Owner decision, 2026-11-11 (t_3af6293c): jss-orchestrator and jss-reviewer may read the
    committed `main` and `origin/main` content of four other repositories with Git commands
    that do not write. The workers get no such access, and the jss-genr card repository
    allowlist is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.raw = {ORCH_SOUL_RELATIVE: soul_path(ORCH).read_text(),
                   REVIEWER_SOUL_RELATIVE: soul_path(REVIEWER).read_text(),
                   SKILL_RELATIVE: SKILL.read_text()}
        cls.verifier = load_verifier()

    def test_each_changed_source_states_the_whole_exception_on_one_line(self):
        for path, raw in self.raw.items():
            with self.subTest(path=path):
                self.assertEqual(raw.count(EXCEPTION_LEAD), 1)
                line = exception_line(raw)
                lead = f"- {EXCEPTION_LEAD}: " if path == SKILL_RELATIVE else f"{EXCEPTION_LEAD}: "
                self.assertTrue(line.startswith(lead), line[:80])
                for repo in FOREIGN_REPOS:
                    self.assertIn(f"`{repo}`", line)
                for rule in EXCEPTION_RULES:
                    self.assertIn(rule, line)
                # Outside its own line, no source names the four repository paths.
                rest = without_exception(raw)
                for repo in FOREIGN_REPOS:
                    self.assertNotIn(f"`{repo}`", rest)

    def test_permitted_and_prohibited_command_lists_are_exact_and_disjoint(self):
        for path, raw in self.raw.items():
            line = exception_line(raw)
            permitted = line.split("Read from the refs `main` and `origin/main` only", 1)[1]
            permitted = permitted.split("Never write in those repositories;", 1)[0]
            prohibited = line.split("Never write in those repositories;", 1)[1].split(" in them;", 1)[0]
            with self.subTest(path=path):
                self.assertEqual(tuple(re.findall(r"`(git [a-z-]+)`", permitted)), PERMITTED_COMMANDS)
                self.assertEqual(tuple(re.findall(r"`(git [a-z-]+)`", prohibited)), PROHIBITED_COMMANDS)
                self.assertFalse(set(PERMITTED_COMMANDS) & set(PROHIBITED_COMMANDS))
                self.assertIn("never from the working tree", permitted)
                self.assertIn("`git diff` between two commits", permitted)
                # No other Git command and no other ref is named anywhere in the exception.
                self.assertEqual(set(re.findall(r"`(git [a-z-]+)`", line)),
                                 set(PERMITTED_COMMANDS) | set(PROHIBITED_COMMANDS))
                self.assertEqual(set(re.findall(r"`((?:origin/)?main)`", line)), {"main", "origin/main"})

    def test_merged_not_deployed_and_sha_and_date_rules(self):
        for path, raw in self.raw.items():
            line = flat(exception_line(raw))
            with self.subTest(path=path):
                self.assertIn(EXCEPTION_MERGED_NOT_DEPLOYED, line)
                self.assertIn(EXCEPTION_SHA_AND_DATE, line)
                # The rule that the privacy gate applies follows the read rules it limits.
                self.assertLess(line.find(EXCEPTION_SHA_AND_DATE), line.find(EXCEPTION_PRIVACY))

    def test_reviewer_exception_adds_no_review_authority(self):
        raw = self.raw[REVIEWER_SOUL_RELATIVE]
        self.assertEqual(raw.splitlines()[0], REVIEWER_FIRST_LINE)
        line = exception_line(raw)
        self.assertTrue(line.startswith(
            f"{EXCEPTION_LEAD}: only to check citations in the card under review, you may read "))
        self.assertIn("reject any commit or tracked file that copies it.", line)
        self.assertTrue(line.endswith(
            "This exception adds no review authority over those four repositories: accept review only for a card "
            f"pinned to repository `{REPO}`, as the first paragraph of this file states."))
        self.assertEqual(raw.count(f"pinned to repository `{REPO}`"), 2)
        skill = exception_line(self.raw[SKILL_RELATIVE])
        self.assertIn("`jss-reviewer` has the same read access only to check citations in the card under review, "
                      "and it gives the reviewer no review authority over those repositories.", skill)

    def test_orchestrator_sources_limit_the_exception_to_two_profiles_and_card_bodies(self):
        orch = exception_line(self.raw[ORCH_SOUL_RELATIVE])
        skill = exception_line(self.raw[SKILL_RELATIVE])
        self.assertTrue(orch.startswith(
            f"{EXCEPTION_LEAD}: to check or refresh facts about the owner's other projects, you may read "))
        self.assertTrue(skill.startswith(
            f"- {EXCEPTION_LEAD}: to check or refresh facts about the owner's other projects, the orchestrator "
            "may read "))
        self.assertIn("You may relay a fact with its commit SHA and commit date to a worker in a card body, "
                      "because card bodies stay local (owner decision, 2026-10-18).", orch)
        self.assertIn("This exception covers only you and `jss-reviewer`; `jss-worker` and `jss-worker-2` have no "
                      "access to these repositories.", orch)
        self.assertIn("The orchestrator may relay a fact with its commit SHA and commit date to a worker in a card "
                      "body, as the Privacy Gate permits for card bodies.", skill)
        self.assertTrue(skill.endswith("`jss-worker` and `jss-worker-2` have no access to these repositories."))
        # The skill states the exception inside Hard Scope.
        self.assertIn(flat(skill), section(self.raw[SKILL_RELATIVE], "Hard Scope"))

    def test_no_sentence_prohibits_the_permitted_reads(self):
        expected = {ORCH_SOUL_RELATIVE: 2, REVIEWER_SOUL_RELATIVE: 1, SKILL_RELATIVE: 3}
        for path, raw in self.raw.items():
            sentences = [s for s in re.split(r"(?<=[.!?])\s+", flat(without_exception(raw)))
                         if ACCESS_LIMIT.search(s)]
            with self.subTest(path=path):
                self.assertEqual(len(sentences), expected[path], sentences)
                for sentence in sentences:
                    self.assertIn(EXCEPTION_REFERENCE, sentence)
        for old in (
                "Operate only on board `jss-genr` and repository `/Users/chanbla11mit/projects/jss-genr`. Load",
                "beyond the read-only harness references your skill names. ",
                "or another board or repository without explicit owner authorization. ",
                "repository-owned worktrees under `/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`. ",
                "profile fleet, or worktree. The portfolio",
                "reading the portfolio site checkout), jss-genr may not probe"):
            for path, raw in self.raw.items():
                with self.subTest(path=path, old=old[:40]):
                    self.assertNotIn(old, flat(raw) + " ")

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path in self.raw:
            with self.subTest(path=path):
                # The later download and install change (t_89838618) and then the jev plugin policy
                # change (t_71b4ef4a) are reversed first.
                current = reverse_download_install_edits(path, (ROOT / path).read_bytes())
                current = reverse_jev_policy_edits(path, current)
                original = reverse_read_only_exception_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), BASELINE_SHA256[path])

    def test_worker_souls_are_unchanged_and_carry_no_exception(self):
        # The SOUL of the third GLM worker (card t_f4ce916d) is a copy of the first one, which
        # tests/test_third_glm_worker_policy.py checks; it has no bytes at this card's baseline.
        for profile in (*WORKERS, *GLM_WORKERS[:2]):
            relative = f"policies/profile-souls/{profile}/SOUL.md"
            text = soul_path(profile).read_text()
            with self.subTest(profile=profile):
                # The jev plugin policy change (t_71b4ef4a) changed the GLM worker SOULs only. The later
                # download and install change (t_89838618) changed all four and is reversed first.
                current = reverse_download_install_edits(relative, soul_path(profile).read_bytes())
                current = reverse_jev_policy_edits(relative, current)
                self.assertEqual(hashlib.sha256(current).hexdigest(), BASELINE_SHA256[relative])
                self.assertNotIn(EXCEPTION_LEAD, text)
                self.assertNotIn("read-only repository exception", text)
                for repo in FOREIGN_REPOS:
                    self.assertNotIn(repo, text)

    def test_jss_genr_allowlist_unchanged_so_foreign_repository_cards_fail(self):
        self.assertEqual(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS["jss-genr"], [REPO])
        self.assertEqual(load(ROOT / "roster.yaml")["project_fleets"]["jss-genr"]["repositories"], [REPO])
        for repo in FOREIGN_REPOS:
            body = REPOSITORY_BODY.replace(f"Repository {REPO} ONLY.", f"Repository {repo} ONLY.")
            task = card(body, workspace_path=f"{repo}/.worktrees/t_jss")
            errors = []
            with redirect_stdout(io.StringIO()):
                self.verifier.check_jss_card_contract(errors, [task])
            with self.subTest(repo=repo):
                self.assertIn("jss-genr card contract drift t_jss: expected exact repository", errors)
                self.assertIn("jss-genr card contract drift t_jss: isolated worktree mismatch", errors)


class DownloadAndInstallOwnerDecision(unittest.TestCase):
    """Owner decision, 2026-11-13 (t_89838618): the rule that a download needs explicit owner
    approval is removed, and an install from a reputable source needs no owner approval
    ("Installs too, so long as they're from reputable sources"). An install from another source
    still needs explicit owner authorization, and dependencies are still never committed."""

    DECISION_DATE = "Owner decision, 2026-11-13: "
    DOWNLOAD = ("downloading a file that the work needs (for example icon SVG files, technology logos, reference "
                "images) needs no owner approval, and installing a package from a reputable source needs no owner "
                "approval.")
    DEFINITION = ("\"Reputable sources\" is the owner's wording; a reputable source is the official package registry "
                  "of the language or platform, or the publisher's own distribution channel (for example the npm "
                  "registry, PyPI, Homebrew).")
    OTHER_SOURCE = "An install from any other source still needs explicit owner authorization."
    NOT_COMMITTED = "Dependencies are still never committed."
    LICENCE = "A downloaded file keeps the licence notice that its source requires."
    UNCHANGED_RULES = ("The privacy gate and the jss-genr repository's own rules on where third-party material is "
                       "stored are unchanged.")
    DECISION = " ".join((DECISION_DATE + DOWNLOAD, DEFINITION, OTHER_SOURCE, NOT_COMMITTED, LICENCE, UNCHANGED_RULES))
    WORKER_SENTENCE = (
        "Owner decision, 2026-11-13: you may download a file that the card's work needs and install a package from "
        "a reputable source (the official package registry of the language or platform, or the publisher's own "
        "distribution channel); for an install from any other source, block with the exact need.")
    ORCH_AUTHORIZATION = (
        "Never push, use `gh`, open a PR, deploy, submit an application, log in to a job site, write to the "
        "portfolio site repository, access credentials, change live profile, skill, board, or gateway state, or "
        "perform another external write without explicit owner authorization.")
    SKILL_AUTHORIZATION = (
        "- Credentials, installs from a source that is not reputable, live profile, skill, board, or gateway "
        "changes, and other external writes require separate explicit owner authorization.")
    SKILL_REPOSITORY_CARD = (
        "- Work only in the isolated worktree. It has no `profile/`, `companies/`, or `resume/node_modules`; "
        "reference the main checkout's copies read-only (for example `NODE_PATH`). Never commit dependencies; a "
        "worker may download a file that the card's work needs and may install a package from a reputable source "
        "as Hard Scope defines it; if a build needs an install from another source, block with the exact error.")
    SKILL_CONTRACT_ITEM = (
        "13. The privacy gate and explicit prohibitions on push, PR, deployment, application submission, job-site "
        "login, installs from a source that is not reputable, live policy changes, credentials, and other external "
        "writes without separate owner authorization.")
    SKILL_ASK_ITEM = "- installs from a source that is not reputable"
    # Card t_89838618 item 2: an install from another source without owner authorization is
    # still an unauthorized install, so this Completion Gate line stays unchanged.
    SKILL_COMPLETION_LINE = (
        "- No privacy leak and no unauthorized push, PR, deployment, application submission, job-site login, "
        "install, policy rollout, credential operation, or external write occurred.")
    REMOVED = ("install or download dependencies", "installs or downloads",
               "never install, download, or commit dependencies")
    # SHA-256 of each changed source at baseline f706e5d949a8fe89b29425c2675cc93ac86a1e98.
    BASELINE_SHA256 = {
        ORCH_SOUL_RELATIVE: "7bd7a0fc43941f32c030ede6c583250a38c8c89d1e03b03960215e5f86305984",
        SKILL_RELATIVE: "598f4329c570f6baafa3e6bc32b15b35ae3d7fa266cd57dbd7b83d031e6c47f6",
        "policies/profile-souls/jss-worker/SOUL.md": "917ed645845150d4d69a842eb059dd2ef8e53d15e04072282947ae45556637c2",
        "policies/profile-souls/jss-worker-2/SOUL.md":
            "917ed645845150d4d69a842eb059dd2ef8e53d15e04072282947ae45556637c2",
        "policies/profile-souls/jss-worker-glm-1/SOUL.md":
            "9e0a1e3fc1bf83f23fc512c3f3b7b84b8ca838cdd2cae2671aa0aa5d165f6d9d",
        "policies/profile-souls/jss-worker-glm-2/SOUL.md":
            "f1d8319c613637db122c0e90a9d0e45637caf297a8a19637d65bead0a6372061",
    }
    # The six sources of card t_89838618; the SOUL of the third GLM worker (card t_f4ce916d) is a copy
    # of the first one, which tests/test_third_glm_worker_policy.py checks.
    WORKER_PROFILES = (*WORKERS, *GLM_WORKERS[:2])
    # Sentences of the six sources that name an install or a download and are neither the owner
    # decision nor a sentence that limits an install to a source that is not reputable.
    OTHER_INSTALL_SENTENCES = (
        "the plugin is installed by the normal procedure",
        "Never modify the installed Hermes source.",
        "job-site login, install, policy rollout, credential operation, or external write occurred.",
    )

    @classmethod
    def setUpClass(cls):
        cls.raw = {path: (ROOT / path).read_text() for path in cls.BASELINE_SHA256}
        cls.orch = cls.raw[ORCH_SOUL_RELATIVE]
        cls.skill_raw = cls.raw[SKILL_RELATIVE]

    def worker_text(self, profile):
        return self.raw[f"policies/profile-souls/{profile}/SOUL.md"]

    def test_orchestrator_soul_states_the_owner_decision_after_the_authorization_sentence(self):
        self.assertEqual(self.orch.count(self.DECISION), 1)
        self.assertEqual(self.orch.count(self.DECISION_DATE), 1)
        self.assertIn(f"{self.ORCH_AUTHORIZATION} {self.DECISION} Sole standing exception (owner decision, "
                      "2026-10-18)", self.orch)
        self.assertIn("The repository has a public remote, and nothing is ever pushed. " + self.ORCH_AUTHORIZATION,
                      self.orch)

    def test_skill_hard_scope_states_the_owner_decision_as_its_own_list_item(self):
        lines = self.skill_raw.splitlines()
        self.assertEqual(lines.count(self.SKILL_AUTHORIZATION), 1)
        index = lines.index(self.SKILL_AUTHORIZATION)
        self.assertEqual(lines[index + 1], f"- {self.DECISION}")
        self.assertEqual(self.skill_raw.count(self.DECISION), 1)
        self.assertEqual(self.skill_raw.count(self.DECISION_DATE), 1)
        hard_scope = section(self.skill_raw, "Hard Scope")
        self.assertIn(self.SKILL_AUTHORIZATION, hard_scope)
        self.assertIn(f"- {self.DECISION}", hard_scope)

    def test_decision_pins_the_definition_the_other_source_rule_and_no_committed_dependencies(self):
        for path in (ORCH_SOUL_RELATIVE, SKILL_RELATIVE):
            with self.subTest(path=path):
                text = self.raw[path]
                for statement in (self.DECISION_DATE + self.DOWNLOAD, self.DEFINITION, self.OTHER_SOURCE,
                                  self.NOT_COMMITTED, self.LICENCE, self.UNCHANGED_RULES):
                    self.assertEqual(text.count(statement), 1, statement)
                # The path from the filer's proposal is not written into the sources (card item 7).
                self.assertNotIn("portfolio-examples", text)

    def test_skill_repository_card_contract_and_ask_list(self):
        lines = self.skill_raw.splitlines()
        for line in (self.SKILL_REPOSITORY_CARD, self.SKILL_CONTRACT_ITEM, self.SKILL_ASK_ITEM,
                     self.SKILL_COMPLETION_LINE):
            with self.subTest(line=line[:60]):
                self.assertEqual(lines.count(line), 1)
        ask = section(self.skill_raw, "Autonomy").split("Ask only for:", 1)[1]
        self.assertIn(self.SKILL_ASK_ITEM, ask.split("These owner questions", 1)[0])
        self.assertIn(self.SKILL_REPOSITORY_CARD, section(self.skill_raw, "Card Kinds"))
        self.assertIn(self.SKILL_CONTRACT_ITEM, section(self.skill_raw, "Card Contract"))
        self.assertIn(self.SKILL_COMPLETION_LINE, section(self.skill_raw, "Completion Gate"))

    def test_skill_version_line(self):
        # Card t_f4ce916d raised the version by one more step, and card t_c7cc3830 by one more.
        self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.skill_raw), ["0.6.7-jss.14"])

    def test_no_source_keeps_the_removed_wording(self):
        for path, text in self.raw.items():
            lower = flat(text).lower()
            for phrase in self.REMOVED:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase.lower(), lower)

    def test_no_other_sentence_requires_approval_for_a_download_or_a_reputable_install(self):
        decision = (self.DECISION, self.WORKER_SENTENCE)
        for path, text in self.raw.items():
            for sentence in re.split(r"(?<=[.;])\s+", flat(text)):
                sentence = sentence.removeprefix("- ")
                if not re.search(r"(?i)\b(install|download)", sentence):
                    continue
                with self.subTest(path=path, sentence=sentence[:80]):
                    permitted = (any(sentence in whole for whole in decision)
                                 or "not reputable" in sentence or "another source" in sentence
                                 or "may download a file that the card's work needs" in sentence
                                 or any(other in sentence for other in self.OTHER_INSTALL_SENTENCES))
                    self.assertTrue(permitted, sentence)

    def test_worker_souls_state_the_same_owner_decision_sentence(self):
        sentences = {}
        for profile in self.WORKER_PROFILES:
            text = self.worker_text(profile)
            with self.subTest(profile=profile):
                self.assertEqual(text.count("never commit dependencies"), 1)
                self.assertEqual(text.count(self.WORKER_SENTENCE), 1)
                self.assertIn("reference the main checkout's copies read-only and never commit dependencies. "
                              f"{self.WORKER_SENTENCE} Commit locally after the checks pass", text)
                found = re.findall(r"Owner decision, 2026-11-13: [^\n]*?exact need\.", text)
                self.assertEqual(len(found), 1)
                sentences[profile] = found[0]
        self.assertEqual(set(sentences.values()), {self.WORKER_SENTENCE})

    def test_unchanged_rules_stay(self):
        self.assertIn("Never modify the installed Hermes source.", self.skill_raw)
        self.assertIn("Privacy is a hard gate on every card.", self.skill_raw)
        self.assertIn("Privacy is a hard gate: never copy anything from `profile/`, `companies/`, or "
                      "`resume/resources/` into tracked files or commits.", self.orch)
        for profile in self.WORKER_PROFILES:
            with self.subTest(profile=profile):
                self.assertIn("Never delegate, touch Jobcron, Cha PT, or Harness work, use another board or checkout, "
                              "push, use `gh`, open a PR, deploy, submit an application, log in to a job site, write "
                              "to the portfolio site repository, access credentials, or perform another external "
                              "write without explicit owner authorization.", self.worker_text(profile))

    def test_reversal_returns_the_baseline_bytes_of_each_changed_source(self):
        for path, want in self.BASELINE_SHA256.items():
            with self.subTest(path=path):
                data = (ROOT / path).read_bytes()
                original = reverse_download_install_edits(path, data)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)
                self.assertEqual(reverse_download_install_edits(path, data.decode()), original.decode())

    def test_reversal_leaves_other_paths_unchanged(self):
        for path in (REVIEWER_SOUL_RELATIVE, "policies/profile-souls/anki-orchestrator/SOUL.md"):
            data = (ROOT / path).read_bytes()
            with self.subTest(path=path):
                self.assertEqual(reverse_download_install_edits(path, data), data)
                self.assertEqual(reverse_download_install_edits(path, data.decode()), data.decode())
        self.assertNotIn("2026-11-13", soul_path(REVIEWER).read_text())


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
