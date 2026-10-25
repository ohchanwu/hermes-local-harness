#!/usr/bin/env python3
"""Offline source contract for the anki project fleet (t_06fc410a).

Checks tracked repository text, desired state and fixture-mode verification
only; no live profile, board, AnkiConnect, network or model observation. The
one Git read checks that the commit that added the anki fleet left the other
fleets' SOUL and skill sources unchanged.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import LocalReads, ROOT, load_verifier, resolved_fixture

REPO = "/Users/chanbla11mit/projects/anki"
ADDONS = "/Users/chanbla11mit/projects/anki-addons"
ORCH, WORKER, WORKER2, REVIEWER = "anki-orchestrator", "anki-worker", "anki-worker-2", "anki-reviewer"
ANKI = (ORCH, WORKER, WORKER2, REVIEWER)
WORKERS = (WORKER, WORKER2)
FLEETS = {"jobcron", "cha-pt", "harness", "jss-genr", "anki"}
BASELINE = "00453fee8fdd4438c185eb97c1279255c7170132"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SKILL = ROOT / "policies/profile-skills" / ORCH / RELATIVE
RUN_SCRIPT = ROOT / "scripts/run-anki-orchestrator"
ADOPTION = ROOT / "adoption/anki.md"
CHECKLIST_ABS = "/Users/chanbla11mit/hermes-local-harness/policies/overgating-review.md"
ADDON_LINE = "Add-on project EXACT anki-addons."
READ_ACTIONS = ("version", "requestPermission", "deckNames", "deckNamesAndIds", "modelNames",
                "modelFieldNames", "findNotes", "notesInfo", "findCards", "cardsInfo", "getTags")
FORBIDDEN_ACTIONS = ("sync", "exportPackage", "importPackage")
APPLY_RULE = ("Only `anki-orchestrator` writes to the collection or applies a change set, and only when the "
              "owner names the change set file and the reviewed commit SHA in chat; approval never carries "
              "over to another change set or SHA.")
NO_PRIVACY_SENTENCE = "There is no privacy rule for note content (owner decision, 2026-10-23)"
CREDENTIALS = "an AnkiConnect `apiKey`, AnkiWeb login data, or any token"
COLLECTION_FILES = "(`*.anki2`, `*.anki21`, `*.anki21b`, `collection.media`)"
RETIRED_MODEL = re.compile(r"(?i)\bgpt\b|gpt-\d|\b(?:sol|astra|luna|terra)\b|openai-codex")
# Words of a note-content privacy, redaction or confidentiality rule (owner decision 2026-10-23
# removed that rule; the only permitted "privacy" text says that there is no such rule).
PRIVACY_RULE_WORDS = re.compile(r"(?i)\bredact|\bconfidential|\bprivacy gate\b|\bsensitive\b|\bhard gate\b")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def soul_path(profile):
    return ROOT / f"policies/profile-souls/{profile}/SOUL.md"


def flat(text):
    return " ".join(text.split())


def load(path):
    return json.loads(path.read_text())


def wording_block():
    text = soul_path("jss-worker").read_text()
    return text[text.index("Terminology and wording\n"):]


def anki_files():
    return [SKILL, RUN_SCRIPT, ADOPTION, *(soul_path(profile) for profile in ANKI)]


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
        for constant in ("PROJECT_REPOSITORY_ALLOWLISTS", "PROJECT_LAUNCHERS", "ADOPTION_REPOS",
                         "PROJECT_WORKER_POOLS"):
            with self.subTest(constant=constant):
                self.assertEqual(set(getattr(self.verifier, constant)), FLEETS)
        self.assertEqual(self.verifier.PROJECT_REPAIR_POLICY, self.roster["project_repair_policy"])
        self.assertEqual(self.snapshot["project_repair_policy"], self.roster["project_repair_policy"])
        self.assertEqual(self.roster["project_repair_policy"]["project_boards"],
                         ["jobcron", "cha-pt", "harness", "jss-genr", "anki"])
        self.assertEqual({adapter["repo"] for adapter in self.snapshot["adoption"]["adapters"]}, FLEETS)
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, fleets, copy.deepcopy(fleets))
        self.assertEqual(errors, [])

    def test_anki_fleet_mapping(self):
        fleet = {
            "board": "anki",
            "repository": REPO,
            "repositories": [REPO, ADDONS],
            "addons_project": "anki-addons",
            "orchestrator": ORCH,
            "worker": WORKER,
            "reviewer": REVIEWER,
            "workers": list(WORKERS),
        }
        self.assertEqual(self.roster["project_fleets"]["anki"], fleet)
        self.assertEqual(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS["anki"], [REPO, ADDONS])
        self.assertEqual(self.verifier.PROJECT_WORKER_POOLS["anki"], list(WORKERS))
        self.assertEqual(self.verifier.PROJECT_LAUNCHERS["anki"], "run-anki-orchestrator")
        self.assertEqual(self.verifier.ADOPTION_REPOS["anki"], "adoption/anki.md")
        self.assertEqual(self.verifier.ANKI_ASSIGNEES, {WORKER, WORKER2, REVIEWER})
        self.assertIn("anki", self.verifier.PROJECTS_WITHOUT_PREVIEW_PORT)
        for mutate, expected in (
                (lambda f: f["anki"].__setitem__("preview_port", 19192),
                 "project isolation preview port invalid: anki"),
                (lambda f: f["anki"].pop("addons_project"), "project add-on mapping malformed: anki"),
                (lambda f: f["anki"].__setitem__("addons_project", "other"),
                 "project add-on mapping malformed: anki"),
                (lambda f: f["jss-genr"].__setitem__("addons_project", "anki-addons"),
                 "project add-on mapping malformed: jss-genr"),
                (lambda f: f["anki"].__setitem__("repositories", [REPO]),
                 "project repository allowlist drift: anki")):
            with self.subTest(expected=expected):
                fleets = copy.deepcopy(self.roster["project_fleets"])
                mutate(fleets)
                errors = []
                with redirect_stdout(io.StringIO()):
                    self.verifier.check_project_isolation(errors, fleets)
                self.assertIn(expected, errors)
        four = {key: value for key, value in self.roster["project_fleets"].items() if key != "anki"}
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_isolation(errors, four)
        self.assertEqual(errors, [
            "project isolation mapping must contain exactly jobcron, cha-pt, harness, jss-genr, and anki"])

    def test_profiles_models_and_dispatch(self):
        expected = {
            ORCH: ("claude-opus-5-5", "project orchestrator", "orchestrator", False),
            WORKER: ("claude-opus-5-5", "project implementation", "implementation", True),
            WORKER2: ("claude-opus-5-5", "project implementation", "implementation", True),
            REVIEWER: ("claude-fable-5-1", "project independent reviewer", "review", True),
        }
        sibling = {ORCH: "jss-orchestrator", WORKER: "jss-worker", WORKER2: "jss-worker-2",
                   REVIEWER: "jss-reviewer"}
        for name, (model, role, toolsets, dispatchable) in expected.items():
            with self.subTest(profile=name):
                profile = self.profiles[name]
                self.assertEqual((profile["model"], profile["provider"], profile["role"], profile["toolsets"]),
                                 (model, "claude-subscription", role, toolsets))
                self.assertEqual(profile["dispatch_eligible"], dispatchable)
                self.assertEqual(profile["in_dispatch_pool"], dispatchable)
                self.assertEqual(profile["lifecycle"], "project-active")
                self.assertEqual(profile["modes"], ["project-isolated", "anki"])
                peer = self.profiles[sibling[name]]
                self.assertEqual(profile["required_plugins"], peer["required_plugins"])
                self.assertEqual(profile["installed_disabled_plugins"], peer["installed_disabled_plugins"])
        self.assertEqual(self.roster["approval_policy"]["profiles"], list(self.profiles))
        self.assertEqual(self.snapshot["approvals"], self.roster["approval_policy"])
        self.assertEqual(self.snapshot["profiles"], list(self.profiles))
        for listing in (self.roster["project_dispatch_allowlist"], self.snapshot["kanban"]["dispatch_profiles"]):
            self.assertEqual([name for name in listing if name.startswith("anki-")], [WORKER, WORKER2, REVIEWER])
            self.assertNotIn(ORCH, listing)
        self.assertEqual(self.roster["dispatch_pool"]["dispatch_allowlist"], [])

    def test_skill_deployment_matrix_and_provenance(self):
        shared = {entry["name"]: entry for entry in self.snapshot["skill"]["shared_skills"]}
        self.assertIn(ORCH, shared["multi-agent-coding-orchestrator"]["deploy_profiles"])
        for name in ("minimal-implementation", "simplification-review"):
            for profile in WORKERS:
                self.assertIn(profile, shared[name]["deploy_profiles"])
        for name in ("production-deployment", "production-deployment-planning"):
            for profile in ANKI:
                self.assertNotIn(profile, shared[name]["deploy_profiles"])
        provenance = self.snapshot["skill"]["source_pin_provenance"]["anki_fleet"]
        self.assertEqual(provenance["baseline"], BASELINE)
        self.assertEqual(provenance["protected_reference"], "refs/harness/baselines/t_06fc410a")
        self.assertIn("not observed deployment", provenance["status"])
        self.assertIn("live setup unperformed", provenance["status"])

    def test_souls_and_skill_are_derived_from_tracked_sources(self):
        souls = self.roster["profile_souls"]
        self.assertEqual(self.snapshot["profile_souls"], souls)
        for profile in ANKI:
            with self.subTest(profile=profile):
                entry = souls[profile]
                self.assertEqual(entry, {"source": f"policies/profile-souls/{profile}/SOUL.md",
                                         "live": f"/Users/chanbla11mit/.hermes/profiles/{profile}/SOUL.md"})
                self.assertEqual(self.verifier.PROFILE_SOUL_PATHS[profile], entry)
                self.assertEqual(self.verifier.profile_soul_expected(entry), sha(ROOT / entry["source"]))
        override = self.snapshot["skill"]["profile_local_skill_overrides"][ORCH]
        self.assertEqual(override, {RELATIVE: self.verifier.TRACKED_SOURCE})
        self.assertEqual(self.verifier.local_override_expected(ORCH, RELATIVE, override[RELATIVE]), sha(SKILL))

    def test_fixtures_resolve_to_tracked_bytes(self):
        souls = {profile: sha(soul_path(profile)) for profile in ANKI}
        for fixture in sorted((ROOT / "tests/fixtures").glob("*.yaml")):
            data = resolved_fixture(fixture)
            if fixture.name == "incomplete-empty.yaml":
                continue
            with self.subTest(fixture=fixture.name):
                for profile, want in souls.items():
                    self.assertEqual(data["profile_soul_hashes"][profile], want)
                self.assertEqual(data["profile_local_skill_overrides"][ORCH][RELATIVE], sha(SKILL))
                self.assertEqual(data["project_isolation"]["anki"], self.roster["project_fleets"]["anki"])


class RoleContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {profile: soul_path(profile).read_text() for profile in ANKI}
        cls.souls = {profile: flat(text) for profile, text in cls.raw.items()}
        cls.skill_raw = SKILL.read_text()
        cls.skill = flat(cls.skill_raw)

    def test_run_script(self):
        self.assertEqual(RUN_SCRIPT.read_text(), (
            "#!/bin/sh\n"
            "set -eu\n"
            'exec env HERMES_KANBAN_BOARD=anki anki-orchestrator chat --in /Users/chanbla11mit/projects/anki "$@"\n'))
        self.assertEqual(RUN_SCRIPT.stat().st_mode & 0o777, 0o755)
        self.assertFalse(RUN_SCRIPT.is_symlink())

    def test_no_new_file_names_a_retired_model_or_is_a_symlink(self):
        for path in anki_files():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(path.is_symlink())
                self.assertIsNone(RETIRED_MODEL.search(path.read_text()))

    def test_souls_end_with_the_wording_block_and_carry_the_writing_rules(self):
        block = wording_block()
        rules = (ROOT / "policies/writing-rules.md").read_text()
        for profile, text in self.raw.items():
            with self.subTest(profile=profile):
                self.assertTrue(text.endswith(block))
                self.assertEqual(text.count("Terminology and wording"), 1)
                self.assertIn(rules, text)

    def test_coined_term_appears_only_inside_the_wording_block(self):
        block = wording_block()
        for path in anki_files():
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                if text.endswith(block):
                    text = text[:-len(block)]
                self.assertIsNone(re.search(r"[Vv]alue-blind", text))

    def test_souls_are_model_neutral(self):
        for profile, text in self.raw.items():
            with self.subTest(profile=profile):
                self.assertNotRegex(text, r"(?i)running (GPT|Fable|Claude|GLM|Opus)")
                self.assertNotRegex(text, r"(?i)\b(opus|fable|glm-5)")

    def test_souls_name_only_board_anki_and_the_two_repositories(self):
        for profile, text in self.raw.items():
            with self.subTest(profile=profile):
                self.assertEqual(set(re.findall(r"board `([^`]+)`", text)), {"anki"})
                self.assertNotRegex(text, r"--board\s")
                paths = set(re.findall(r"/Users/chanbla11mit/[^\s`'(),;]+", text))
                allowed = {REPO, ADDONS} | ({CHECKLIST_ABS} if profile == REVIEWER else set())
                self.assertEqual(paths, allowed)
                self.assertIn(f"`{REPO}`", text)
                self.assertIn(f"`{ADDONS}`", text)
                self.assertIn("same-card", self.souls[profile])
                if profile != REVIEWER:
                    self.assertIn("`anki-reviewer`", text)
                if profile in (ORCH, REVIEWER):
                    for worker in WORKERS:
                        self.assertIn(f"`{worker}`", text)

    def test_souls_carry_collection_access_and_controller_only_apply_rule(self):
        for profile, body in self.souls.items():
            with self.subTest(profile=profile):
                actions = ", ".join(f"`{action}`" for action in READ_ACTIONS)
                self.assertIn(actions, body)
                for action in FORBIDDEN_ACTIONS:
                    self.assertIn(f"`{action}`", body)
                self.assertIn("every action that changes notes, cards, decks, tags, note types, media, or "
                              "configuration", body)
                self.assertIn(APPLY_RULE, body)
                self.assertIn(COLLECTION_FILES, body)
                self.assertIn("http://127.0.0.1:8765", body)
                self.assertIn(ADDON_LINE, body)
                self.assertIn("`changesets/`", body)

    def test_souls_have_no_note_privacy_rule_and_keep_the_credential_exclusion(self):
        for profile, body in self.souls.items():
            with self.subTest(profile=profile):
                self.assertIsNone(PRIVACY_RULE_WORDS.search(body))
                self.assertEqual(body.lower().count("privacy"), 1)
                self.assertIn(NO_PRIVACY_SENTENCE, body)
                self.assertIn("Credentials stay excluded: never read, print, commit, or put on a card "
                              f"{CREDENTIALS}.", body)
        for path in (SKILL, ADOPTION):
            with self.subTest(path=path.relative_to(ROOT)):
                text = flat(path.read_text())
                self.assertIsNone(PRIVACY_RULE_WORDS.search(text))
                self.assertEqual(text.lower().count("privacy"), 1)
                self.assertIn("There is no privacy rule for note content (owner decision, 2026-10-23)", text)
                self.assertIn("AnkiConnect `apiKey`, AnkiWeb login data", text)

    def test_souls_keep_remote_and_external_write_limits(self):
        for profile, body in self.souls.items():
            lower = body.lower()
            with self.subTest(profile=profile):
                for limit in ("add a remote", "push", "open a pr", "sync with ankiweb", "publish to ankiweb",
                              "other installed add-ons", "credentials", "external write"):
                    self.assertIn(limit, lower)
                for foreign in ("Jobcron", "Cha PT", "jss-genr", "Harness work"):
                    self.assertIn(foreign, body)

    def test_role_specific_rules(self):
        orch = self.souls[ORCH]
        for marker in ("Load and follow `multi-agent-coding-orchestrator` before routing work.",
                       "Pass `board: anki` explicitly on every Kanban operation.",
                       "(a) confirm that each note's current value still equals the recorded current value and "
                       "change nothing if any differs",
                       "into the gitignored `private/backups/`",
                       "(d) read every changed value back and report the counts",
                       "apply no change set",
                       "only after the owner approves that add-on and commit SHA"):
            self.assertIn(marker, orch)
        for profile in WORKERS:
            with self.subTest(profile=profile):
                body = self.souls[profile]
                self.assertIn("Accept only a dispatcher-assigned card on board `anki`", body)
                self.assertIn("block without editing", body)
                self.assertIn("test only code that does not import `anki` or `aqt`", body)
                self.assertIn("Never install an add-on build into the Anki `addons21` folder.", body)
                self.assertIn("Never delegate", body)
        self.assertEqual(soul_path(WORKER).read_bytes(), soul_path(WORKER2).read_bytes())
        reviewer_raw = self.raw[REVIEWER]
        reviewer = self.souls[REVIEWER]
        self.assertEqual(reviewer_raw.count(CHECKLIST_ABS), 1)
        for marker in ("Accept review only for a card on board `anki`",
                       "Reject and block any boundary mismatch.",
                       "Never edit implementation code or the reviewed change set.",
                       "Use `kanban_complete` for approval and `kanban_request_changes` for actionable same-card "
                       "rework.",
                       "that the recorded current values match the collection",
                       "would block, stall, or add owner prompts to otherwise authorized work is a material finding",
                       "Minor ceremony that blocks nothing is a non-blocking note in the approval.",
                       "grants no new authority, and never weakens the boundaries in this file"):
            self.assertIn(marker, reviewer)
        paragraph = next(p for p in reviewer_raw.split("\n\n") if CHECKLIST_ABS in p)
        self.assertLessEqual(len(paragraph), 1000)

    def test_skill_version_scope_and_board_pinning(self):
        self.assertRegex(self.skill_raw, r"(?m)^version: 0\.6\.10-anki\.3$")
        history = "This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators."
        self.assertEqual(self.skill_raw.count(history), 1)
        rest = self.skill_raw.replace(history, "")
        for foreign in ("jobcron-orchestrator", "jobcron-worker", "jobcron-reviewer", "chapt-",
                        "jss-orchestrator", "jss-worker", "jss-reviewer", "harness-orchestrator",
                        "harness-worker", "harness-reviewer", "board: harness", "board: jss-genr",
                        "board: cha-pt", "board: jobcron", "--board harness", "--board jss-genr"):
            self.assertNotIn(foreign, rest)
        for line in self.skill_raw.splitlines():
            if "hermes kanban " in line:
                self.assertIn("--board anki", line)
        calls = re.findall(r"kanban_[a-z_]+\(([^)]*)\)", self.skill_raw)
        self.assertTrue(calls)
        for call in calls:
            self.assertIn("board: anki", call)
        harness_paths = set(re.findall(r"/Users/chanbla11mit/hermes-local-harness/[^\s`'(),;]+", self.skill_raw))
        self.assertEqual(harness_paths, {CHECKLIST_ABS,
                                         "/Users/chanbla11mit/hermes-local-harness/scripts/check-forced-skills"})

    def test_skill_card_types_collection_access_and_apply_rules(self):
        actions = ", ".join(f"`{action}`" for action in READ_ACTIONS)
        for marker in (
                "The sole independent reviewer is `anki-reviewer`.",
                "The implementation workers are `anki-worker` and `anki-worker-2`.",
                f"`Repository {REPO} ONLY.`", f"`Repository {ADDONS} ONLY.`",
                f"`{ADDON_LINE}`", "`project: anki-addons`", "`Baseline EXACT <40-hex-commit>.`",
                "`Reviewer EXACT anki-reviewer.`", actions,
                "Only `anki-orchestrator` writes to the collection, only through AnkiConnect, only after a backup",
                "Only `anki-orchestrator` applies a change set, and only when the owner names the change set file "
                "and the reviewed commit SHA in chat.",
                "change nothing and report the differences",
                "including scheduling information, into the gitignored `private/backups/`",
                "Read every changed value back and report the counts.",
                "Approval never carries over to another change set or SHA.",
                "no change set is applied",
                "Deletions of notes, decks, or note types appear only as explicitly listed entries.",
                "pinned to 26.9.2", "test only code that does not import `anki` or `aqt`",
                "only after the owner approves that add-on and its reviewed commit SHA",
                "Never sync with AnkiWeb (the owner syncs), never publish to AnkiWeb",
                "Never add a remote, run `git push` or `gh`, open a PR, or deploy.",
                "Pin `refs/anki/baselines/<ID>` to the baseline in the card's repository.",
                "Never claim a card and `kanban_block` it as a setup hold.",
                "Bookkeeping never gates.", "No numeric caps on harmless actions",
                "check semantic validity, not bookkeeping-format validity",
                "reviewed by `anki-reviewer` on the same card",
                "An incident neither grants new authority nor automatically revokes unrelated authority.",
                "User stop remains global", "Never modify the installed Hermes source."):
            with self.subTest(marker=marker[:60]):
                self.assertIn(marker, self.skill)
        for action in FORBIDDEN_ACTIONS:
            self.assertIn(f"`{action}`", self.skill)

    def test_adoption_record(self):
        text = ADOPTION.read_text()
        adapter = next(item for item in load(ROOT / "snapshots/sanitized-current-state.yaml")["adoption"]["adapters"]
                       if item["repo"] == "anki")
        self.assertEqual(adapter, {
            "repo": "anki",
            "path": f"{REPO}/README.md",
            "marker": "# Anki tooling and standards",
            "record_marker": "Status: defined in repository source; live setup pending.",
        })
        self.assertIn(adapter["path"], text)
        self.assertIn(adapter["record_marker"], text)
        self.assertIn("`scripts/run-anki-orchestrator`", text)
        clean = load(ROOT / "tests/fixtures/clean.yaml")
        observed = next(item for item in clean["adapters"] if item["repo"] == "anki")
        self.assertEqual(observed, {"repo": "anki", "content": adapter["marker"], "record": text})


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ExistingFleetSourcesUnchanged(unittest.TestCase):
    """The change that adds the anki fleet leaves every other SOUL and skill source unchanged."""

    def test_other_fleet_soul_and_skill_sources_unchanged(self):
        if git("rev-parse", "--git-dir").returncode:
            self.skipTest("not a Git checkout")
        paths = ["policies/profile-souls", "policies/profile-skills", "skills"]
        excluded = [f":(exclude)policies/profile-souls/{profile}" for profile in ANKI]
        excluded.append(f":(exclude)policies/profile-skills/{ORCH}")
        added = git("log", "--format=%H", "--diff-filter=A", "--",
                    f"policies/profile-souls/{ORCH}/SOUL.md").stdout.split()
        if added:
            # Committed: compare the commit that added the anki fleet with its parent.
            commit = added[-1]
            result = git("diff", "--name-only", f"{commit}^", commit, "--", *paths, *excluded)
        else:
            # Not yet committed: compare the working tree with HEAD.
            result = git("diff", "--name-only", "HEAD", "--", *paths, *excluded)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


def card(body, **changes):
    task = {"id": "t_anki", "board": "anki", "body": body, "assignee": WORKER,
            "workspace_kind": "worktree", "workspace_path": f"{REPO}/.worktrees/t_anki"}
    task.update(changes)
    return task


PRIMARY_BODY = (
    f"Repository {REPO} ONLY.\n"
    f"Baseline EXACT {'a' * 40}.\n"
    "## Tests\n- `python3 tests/test_changeset.py`\n"
    "Reviewer EXACT anki-reviewer.\n")
ADDON_BODY = (
    f"Repository {ADDONS} ONLY.\n"
    f"{ADDON_LINE}\n"
    f"Baseline EXACT {'b' * 40}.\n"
    "## Tests\n- `python3 tests/test_addon.py`\n"
    "Reviewer EXACT anki-reviewer.\n")


def addon_card(body=ADDON_BODY, **changes):
    values = {"id": "t_addon", "project_id": "anki-addons", "workspace_path": f"{ADDONS}/.worktrees/t_addon"}
    values.update(changes)
    return card(body, **values)


class CardContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()

    def errors(self, tasks):
        errors = []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_anki_card_contract(errors, tasks)
        return errors

    def assert_fails(self, task, expected):
        errors = self.errors([task])
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_primary_and_addon_cards(self):
        self.assertEqual(self.errors([card(PRIMARY_BODY), addon_card()]), [])
        self.assertEqual(self.errors([card(PRIMARY_BODY, assignee=WORKER2),
                                      addon_card(assignee=REVIEWER)]), [])

    def test_addon_line_required_on_addon_repository_cards(self):
        self.assert_fails(addon_card(ADDON_BODY.replace(f"{ADDON_LINE}\n", "")),
                          "anki card contract drift t_addon: add-on project contract missing")
        self.assert_fails(addon_card(project_id=None), "add-on project contract missing")
        self.assert_fails(addon_card(ADDON_BODY.replace(ADDON_LINE, f"Note: {ADDON_LINE}")),
                          "add-on project contract missing")

    def test_addon_line_forbidden_on_primary_repository_cards(self):
        self.assert_fails(card(PRIMARY_BODY + f"{ADDON_LINE}\n"),
                          "anki card contract drift t_anki: add-on project on primary repository")
        self.assert_fails(card(PRIMARY_BODY, project_id="anki-addons"), "add-on project on primary repository")

    def test_boundary_mutations_fail_closed(self):
        for task, expected in (
                (card(PRIMARY_BODY.replace(f"Repository {REPO} ONLY.\n", "")), "expected exact repository"),
                (card(PRIMARY_BODY + f"Repository {ADDONS} ONLY.\n"), "expected exactly one repository"),
                (card(PRIMARY_BODY, workspace_path=f"{ADDONS}/.worktrees/t_anki"), "isolated worktree mismatch"),
                (addon_card(workspace_path=f"{REPO}/.worktrees/t_addon"), "isolated worktree mismatch"),
                (card(PRIMARY_BODY, workspace_path="/Users/chanbla11mit/hermes-local-harness/.worktrees/t_anki"),
                 "isolated worktree mismatch"),
                (card(PRIMARY_BODY.replace(f"Baseline EXACT {'a' * 40}.\n", "")), "exact baseline missing"),
                (card(PRIMARY_BODY.replace("- `python3 tests/test_changeset.py`", "Check it by eye.")),
                 "explicit test contract missing"),
                (card(PRIMARY_BODY, assignee="jss-worker"), "anki worker assignment invalid"),
                (card(PRIMARY_BODY, assignee=ORCH), "anki worker assignment invalid"),
                (card(PRIMARY_BODY.replace("Reviewer EXACT anki-reviewer.\n", "Reviewer EXACT jss-reviewer.\n")),
                 "independent review contract missing")):
            with self.subTest(expected=expected):
                self.assert_fails(task, expected)

    def test_boards_do_not_cross_check(self):
        self.assertEqual(self.errors([card(PRIMARY_BODY, board="jss-genr")]), [])
        for check in ("check_harness_card_contract", "check_jss_card_contract"):
            errors = []
            with redirect_stdout(io.StringIO()):
                getattr(self.verifier, check)(errors, [card(PRIMARY_BODY), addon_card()])
            self.assertEqual(errors, [])
        self.assertEqual(self.errors(None), ["anki card contract observation malformed"])
        self.assertEqual(self.errors(["x"]), ["anki card contract observation malformed"])


def fixture_main(fixture):
    verifier = load_verifier()
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="anki-fleet-") as directory:
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

    def test_clean_with_valid_anki_cards_passes(self):
        fixture = copy.deepcopy(self.clean)
        fixture["project_repair_cards"] = [card(PRIMARY_BODY), addon_card()]
        code, output = fixture_main(fixture)
        self.assertEqual(code, 0, output)
        self.assertNotIn("FAIL:", output)

    def test_addon_line_rule_is_red_in_both_directions(self):
        for task, diagnostic in (
                (addon_card(ADDON_BODY.replace(f"{ADDON_LINE}\n", "")),
                 "FAIL: anki card contract drift t_addon: add-on project contract missing"),
                (card(PRIMARY_BODY + f"{ADDON_LINE}\n"),
                 "FAIL: anki card contract drift t_anki: add-on project on primary repository")):
            with self.subTest(diagnostic=diagnostic):
                fixture = copy.deepcopy(self.clean)
                fixture["project_repair_cards"] = [task]
                code, output = fixture_main(fixture)
                self.assertEqual(code, 1, output)
                self.assertIn(diagnostic, output)

    def test_anki_drift_is_red(self):
        for mutate, diagnostic in (
                (lambda d: d["profile_soul_hashes"].__setitem__(REVIEWER, "0" * 64),
                 f"profile SOUL drift {REVIEWER}"),
                (lambda d: d["profile_models"].__setitem__(WORKER, "wrong-model"), f"model drift {WORKER}"),
                (lambda d: d["plugins"][WORKER].__setitem__(
                    "ponytail", "enabled      git pinned@16f29800 4.8.4    ponytail"),
                 f"ponytail enabled drift {WORKER}"),
                (lambda d: d["project_isolation"]["anki"]["repositories"].append("/Users/chanbla11mit/projects/x"),
                 "project repository allowlist drift: anki"),
                (lambda d: d["skill_files"]["minimal-implementation"].pop(WORKER2),
                 f"deployed skill copy missing: minimal-implementation {WORKER2}"),
                (lambda d: d["profile_local_skill_overrides"][ORCH].__setitem__(RELATIVE, "0" * 64),
                 f"profile-local skill override drift: {ORCH}/{RELATIVE}"),
                (lambda d: next(a for a in d["adapters"] if a["repo"] == "anki").__setitem__("content", "changed"),
                 "adoption status drift anki")):
            with self.subTest(diagnostic=diagnostic):
                fixture = copy.deepcopy(self.clean)
                mutate(fixture)
                code, output = fixture_main(fixture)
                self.assertEqual(code, 1, output)
                self.assertIn(diagnostic, output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
