#!/usr/bin/env python3
"""Cha PT scraper repository scope and controller-only push (t_b04aef1d).

Synthetic only: in-memory cards, temp git repositories and local bare remotes.
No live board, profile or network access; nothing targets a real remote.
"""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT, load_verifier
from rule_text import assert_rule
from test_chapt_policy_reconciliation import CARD_CREATION_EDITS
from test_orchestrator_skill_terminology import TERMINOLOGY_EDITS, reverse_terminology_edits

BASELINE = "7a4ed4bbb75a9680e11e5fdb70b60268f9a6eaff"
SCRAPER = "/Users/chanbla11mit/projects/cha-webpt-website-sync"
BACKEND = "/Users/chanbla11mit/projects/cha-pt"
FRONTEND = "/Users/chanbla11mit/projects/cha-pt-frontend"
PROJECT = "cha-webpt-website-sync"
DECLARATION = "Scraper project EXACT cha-webpt-website-sync."
HOOK = ROOT / "policies/repository-hooks/cha-webpt-website-sync/pre-push"
HELPER = ROOT / "scripts/chapt-push-scraper-main"
CURLY = chr(0x2019)


def exec_module(name, path, source=None):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(source if source is not None else Path(path).read_text(), str(path), "exec"),
         module.__dict__)
    return module


def baseline_verifier():
    source = subprocess.run(("git", "-C", str(ROOT), "show", f"{BASELINE}:scripts/verify-state"),
                            check=True, text=True, stdout=subprocess.PIPE).stdout
    return exec_module("baseline_verifier", ROOT / "scripts/verify-state", source)


def card_errors(verifier, cards):
    errors = []
    with redirect_stdout(io.StringIO()):
        verifier.check_chapt_card_contract(errors, cards)
    return errors


def scraper_card(body=None, **overrides):
    if body is None:
        body = (f"Repository {SCRAPER} ONLY.\nBaseline EXACT {'a' * 40}.\n{DECLARATION}\n"
                "Reviewer EXACT chapt-reviewer.\n## Tests\n- `pytest -q`\n")
    card = {"id": "t_scr1", "board": "cha-pt", "project_id": PROJECT, "body": body,
            "assignee": "chapt-worker", "workspace_kind": "worktree",
            "workspace_path": f"{SCRAPER}/.worktrees/t_scr1", "status": "running",
            "started_at": 1, "runs": [{"id": 1}]}
    card.update(overrides)
    return card


def backend_card(**overrides):
    body = (f"Repository {BACKEND} ONLY. Baseline EXACT {'b' * 40}. "
            "Independent reviewer chapt-reviewer.\n## Test contract\n`go test ./...`")
    card = {"id": "t_back", "body": body, "assignee": "chapt-worker", "workspace_kind": "worktree",
            "workspace_path": f"{BACKEND}/.worktrees/t_back", "status": "running",
            "started_at": 1, "runs": [{"id": 1}]}
    card.update(overrides)
    return card


def frontend_card(**overrides):
    body = (f"Repository {FRONTEND} ONLY. Baseline EXACT {'c' * 40}. "
            "Independent reviewer chapt-reviewer. Follow AGENTS.md; operator-protected paths require "
            "explicit human authorization.\nFrontend project EXACT cha-pt-frontend.\n"
            "Frontend editable paths EXACT site/index.html, site/static/styles/main.css.\n"
            "External writes PROHIBITED without separate explicit human authorization on this card.\n"
            "## Test contract\n`python3 checks/run.py --all`")
    card = {"id": "t_front", "project_id": "cha-pt-frontend", "body": body,
            "assignee": "chapt-worker-2", "workspace_kind": "worktree",
            "workspace_path": f"{FRONTEND}/.worktrees/t_front", "status": "running",
            "started_at": 1, "runs": [{"id": 1}]}
    card.update(overrides)
    return card


def p4_card(**overrides):
    body = (f"Repository {BACKEND} ONLY. Baseline EXACT {'d' * 40}. "
            "Independent reviewer chapt-reviewer.\n## Execution resource/test ownership\n"
            "Full go test -json ./... -count=1 and go test -race -json ./... -count=1; "
            "vet/production scratch build/read-only gofmt/whitespace.")
    card_id = overrides.pop("id", "t_4d3c8997")
    return backend_card(id=card_id, body=body, workspace_path=f"{BACKEND}/.worktrees/{card_id}", **overrides)


class ScraperCardContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.baseline = baseline_verifier()

    def drift(self, card, reason):
        self.assertEqual(card_errors(self.verifier, [card]),
                         [f"Cha PT card contract drift {card['id']}: {reason}"])

    def test_allowlist_is_exactly_three_repositories(self):
        self.assertEqual(self.verifier.PROJECT_REPOSITORY_ALLOWLISTS["cha-pt"], [BACKEND, FRONTEND, SCRAPER])

    def test_roster_scraper_project_mapping(self):
        import copy
        import json
        for source, key in (("roster.yaml", "project_fleets"),
                            ("snapshots/sanitized-current-state.yaml", "project_isolation")):
            fleets = json.loads((ROOT / source).read_text())[key]
            self.assertEqual(fleets["cha-pt"]["scraper_project"], PROJECT)
            errors = []
            with redirect_stdout(io.StringIO()):
                self.verifier.check_project_isolation(errors, fleets)
            self.assertEqual(errors, [], source)
        malformed = "project scraper mapping malformed"
        for project, key, value in (("cha-pt", "scraper_project", None), ("cha-pt", "scraper_project", "cha-pt"),
                                    ("jobcron", "scraper_project", PROJECT)):
            drifted = copy.deepcopy(fleets)
            drifted[project][key] = value
            if value is None:
                del drifted[project][key]
            errors = []
            with redirect_stdout(io.StringIO()):
                self.verifier.check_project_isolation(errors, drifted)
            self.assertIn(f"{malformed}: {project}", errors)

    def test_valid_scraper_card(self):
        self.assertEqual(card_errors(self.verifier, [scraper_card()]), [])
        self.assertEqual(card_errors(self.verifier, [scraper_card(assignee="chapt-worker-2")]), [])

    def test_never_claimed_root_rule(self):
        unclaimed = scraper_card(workspace_path=SCRAPER, status="todo", started_at=None, runs=[])
        self.assertEqual(card_errors(self.verifier, [unclaimed]), [])
        self.drift(scraper_card(workspace_path=SCRAPER), "isolated worktree mismatch")

    def test_scraper_project_and_declaration_required(self):
        missing = "scraper project contract missing"
        self.drift(scraper_card(project_id=None), missing)
        self.drift(scraper_card(project_id="cha-pt-frontend"), missing)
        self.drift(scraper_card(board="jobcron"), missing)
        body = scraper_card()["body"]
        self.drift(scraper_card(body=body.replace(DECLARATION + "\n", "")), missing)
        self.drift(scraper_card(body=body.replace(DECLARATION, DECLARATION + " Extra.")), missing)
        self.drift(scraper_card(body=body.replace(DECLARATION, "Scraper project EXACT cha-pt.")), missing)

    def test_mismatched_boundaries_rejected(self):
        body = scraper_card()["body"]
        self.drift(scraper_card(body=body.replace(SCRAPER, "/Users/chanbla11mit/projects/other")),
                   "expected exactly one repository")
        self.drift(scraper_card(body=body.replace(" ONLY.", f" ONLY. Repository {BACKEND} ONLY.", 1)), "expected exactly one repository")
        for path in (f"{BACKEND}/.worktrees/t_scr1", f"{SCRAPER}/.worktrees/t_other", f"{FRONTEND}/.worktrees/t_scr1"):
            with self.subTest(path=path):
                self.drift(scraper_card(workspace_path=path), "isolated worktree mismatch")
        self.drift(scraper_card(workspace_kind="scratch"), "isolated worktree mismatch")
        self.drift(scraper_card(body=body.replace("a" * 40, "a" * 12)), "exact baseline missing")
        self.drift(scraper_card(body=body.replace("- `pytest -q`\n", "")), "explicit test contract missing")
        self.drift(scraper_card(assignee="jobcron-worker"), "independent review contract missing")
        self.drift(scraper_card(body=body.replace("Reviewer EXACT chapt-reviewer.\n", "")),
                   "independent review contract missing")

    def test_scraper_project_only_on_scraper_repository(self):
        reason = "scraper project on non-scraper repository"
        self.drift(backend_card(project_id=PROJECT), reason)
        self.drift(backend_card(body=backend_card()["body"].replace("\n## Test", f"\n{DECLARATION}\n## Test")),
                   reason)

    def test_backend_frontend_and_p4_verdicts_unchanged(self):
        self.assertEqual(self.verifier.LEGACY_CHAPT_TEST_CONTRACTS, self.baseline.LEGACY_CHAPT_TEST_CONTRACTS)
        front = frontend_card()
        cases = [backend_card(), frontend_card(), p4_card(),
                 backend_card(workspace_path=BACKEND, status="ready", started_at=None, runs=[]),
                 backend_card(workspace_path=BACKEND), backend_card(assignee="jobcron-worker"),
                 backend_card(body=backend_card()["body"].replace("`go test ./...`", "")),
                 p4_card(id="t_other4"), frontend_card(project_id=None),
                 frontend_card(body=front["body"].replace("site/index.html, ", "/etc/x, ")),
                 frontend_card(body=front["body"] + "\nPush to main afterwards."),
                 frontend_card(workspace_path=f"{BACKEND}/.worktrees/t_front")]
        for card in cases:
            with self.subTest(card=card["id"], body=card["body"][-40:]):
                self.assertEqual(card_errors(self.verifier, [card]), card_errors(self.baseline, [card]))
        self.assertEqual(card_errors(self.verifier, cases[:4]), [])


class GitSandbox(unittest.TestCase):
    """Temp checkout cloned from a local bare remote; git config isolated."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scraper-scope-"))
        self.addCleanup(subprocess.run, ("rm", "-rf", str(self.tmp)))
        gitconfig = self.tmp / "gitconfig"
        gitconfig.write_text("")
        self.home = self.tmp / "profiles" / "chapt-orchestrator"
        self.env = {key: value for key, value in os.environ.items() if not key.startswith(("HERMES_", "GIT_"))}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(gitconfig), HERMES_HOME=str(self.home),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
        self.remote = str(self.tmp / "remote.git")
        self.checkout = str(self.tmp / "checkout")
        self.git("init", "-q", "--bare", "-b", "main", self.remote, cwd=self.tmp)
        self.git("clone", "-q", self.remote, self.checkout, cwd=self.tmp)
        self.git("checkout", "-q", "-b", "main")
        self.base = self.commit("base")
        self.git("push", "-q", "origin", "main")
        self.head = self.commit("reviewed")
        hook = Path(self.checkout) / ".git" / "hooks" / "pre-push"
        hook.write_bytes(HOOK.read_bytes())
        hook.chmod(0o755)

    def git(self, *args, cwd=None, env=None, check=True):
        result = subprocess.run(("git", *args), cwd=cwd or self.checkout, env=env or self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            raise AssertionError(f"git {args}: {result.stderr}")
        return result

    def commit(self, message):
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def remote_main(self):
        return self.git("rev-parse", "main", cwd=self.remote).stdout.strip()

    def diverge(self):
        """Move remote main to a commit that does not contain self.head."""
        other = str(self.tmp / "other")
        self.git("clone", "-q", self.remote, other, cwd=self.tmp)
        self.git("commit", "-q", "--allow-empty", "-m", "moved", cwd=other)
        self.git("push", "-q", "origin", "main", cwd=other)
        return self.git("rev-parse", "HEAD", cwd=other).stdout.strip()


class PrePushHook(GitSandbox):
    def push(self, *refspecs, **env):
        environment = dict(self.env, **env)
        return self.git("push", *refspecs, env=environment, check=False)

    def refused(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-push REFUSED", result.stderr)

    def test_dispatched_task_refused(self):
        self.refused(self.push("origin", "main", HERMES_KANBAN_TASK="t_x"))
        self.refused(self.push("origin", "main", HERMES_KANBAN_WORKSPACE=self.checkout))
        self.refused(self.push("origin", "main", HERMES_HOME=str(self.tmp / "profiles" / "chapt-worker")))
        self.refused(self.push("origin", "main", HERMES_PROFILE="chapt-reviewer"))
        self.assertEqual(self.remote_main(), self.base)

    def test_non_main_updates_refused(self):
        self.git("tag", "v1")
        self.refused(self.push("origin", "v1"))
        self.refused(self.push("origin", "HEAD:refs/heads/feature"))
        self.refused(self.push("origin", ":refs/heads/main"))
        self.refused(self.push("--force", "origin", f"{self.base}:refs/heads/other"))
        self.assertEqual(self.remote_main(), self.base)
        self.assertEqual(self.git("ls-remote", self.remote).stdout.split()[1::2], ["HEAD", "refs/heads/main"])

    def test_non_fast_forward_refused_even_forced(self):
        moved = self.diverge()
        self.refused(self.push("--force", "origin", "main"))
        self.assertEqual(self.remote_main(), moved)

    def test_fast_forward_of_main_accepted(self):
        result = self.push("origin", "main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_main(), self.head)


class PushHelper(GitSandbox):
    def setUp(self):
        super().setUp()
        self.helper = exec_module("chapt_push_scraper_main", HELPER)
        self.calls = []
        self.card = {"task": {"id": "t_scr1", "project_id": "p_scr1", "status": "done"},
                     "runs": [{"id": 1, "profile": "chapt-worker", "outcome": "completed",
                               "metadata": {"commit": self.head}},
                              {"id": 2, "profile": "chapt-reviewer", "outcome": "completed",
                               "metadata": {"candidate": self.head}}]}
        self.config = {"checkout": self.checkout, "remote": self.remote, "board": "cha-pt",
                       "project": PROJECT, "load_card": self.load_card,
                       "load_project_id": {PROJECT: "p_scr1"}.get, "runner": self.runner}

    def tearDown(self):
        # Nothing ever targets a non-temp remote or checkout.
        for args in self.calls:
            self.assertNotIn("github.com", " ".join(args))
            self.assertEqual(args[0], "git")
            self.assertIn(self.checkout, args)

    def load_card(self, card_id):
        self.assertEqual(card_id, "t_scr1")
        return self.card

    def runner(self, args):
        self.calls.append(tuple(args))
        return subprocess.run(args, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def approval(self, sha=None):
        return f"Push `{(sha or self.head)[:12]}` to Ray's main"

    def run_helper(self, approval=None, sha=None, environ=None, card="t_scr1"):
        out = io.StringIO()
        code = self.helper.push_scraper_main(self.config, card, sha or self.head,
                                             self.approval() if approval is None else approval,
                                             self.env if environ is None else environ, out)
        return code, out.getvalue()

    def pushes(self):
        return [args for args in self.calls if "push" in args]

    def assert_refused(self, reason, **kwargs):
        code, output = self.run_helper(**kwargs)
        self.assertEqual(code, 1, output)
        self.assertIn("REFUSED", output)
        self.assertIn(reason, output)
        self.assertEqual(self.pushes(), [])
        self.assertNotEqual(self.remote_main(), self.head)

    def test_valid_push_and_readback(self):
        code, output = self.run_helper()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.remote_main(), self.head)
        readback = self.git("ls-remote", self.remote, "refs/heads/main").stdout.split()[0]
        self.assertEqual(readback, self.head)
        self.assertIn(f"ls-remote: {self.head}\trefs/heads/main", output)
        [push] = self.pushes()
        self.assertEqual(push[push.index("push"):], ("push", self.remote, f"{self.head}:refs/heads/main"))
        self.assertEqual(sum(":refs/heads/main" in arg for arg in push), 1)
        self.assertFalse([arg for arg in push if arg.startswith("-") and arg not in ("-c", "-C")])
        self.assertNotIn("+", push[-1])

    def test_typographic_apostrophe_and_repository_names_accepted(self):
        for text in (f"Push {self.head[:7]} to Ray{CURLY}s main", f"push {self.head} to cha-webpt-website-sync main",
                     f"OK: scraper main <- {self.head[:9].upper()} (card t_scr1)"):
            with self.subTest(text=text):
                self.helper.check_approval(text, self.head)

    def test_approval_refusals(self):
        self.assert_refused("must name main", approval="")
        self.assert_refused("must name main", approval="go ahead")
        self.assert_refused("must name main", approval=f"Push {self.head[:12]} to Ray's repository")
        self.assert_refused("scraper repository", approval=f"Push {self.head[:12]} to main")
        self.assert_refused("exact reviewed SHA", approval="Push it to Ray's main")
        self.assert_refused("another SHA", approval=self.approval(self.base))
        self.assert_refused("another SHA", approval=self.approval() + f" and {self.base[:8]}")
        self.assert_refused("another SHA", approval=f"Push {self.head}0 to Ray's main")

    def test_card_refusals(self):
        task, runs = self.card["task"], self.card["runs"]
        for field, value, reason in (("project_id", "cha-pt-frontend", "not in project"),
                                     ("project_id", None, "not in project"),
                                     ("project_id", PROJECT, "not in project"),
                                     ("board", "jobcron", "not on board"), ("status", "review", "not done"),
                                     ("id", "t_other", "not found")):
            with self.subTest(field=field, value=value):
                saved = dict(task)
                task[field] = value
                self.assert_refused(reason)
                task.clear()
                task.update(saved)
        runs[1]["metadata"] = {"candidate": self.base}
        self.assert_refused("is not for")
        runs[1]["metadata"] = {"candidate": self.head, "commit": self.base}
        self.assert_refused("is not for")
        runs[1]["metadata"] = {}
        self.assert_refused("is not for")
        runs[1].update(metadata={"candidate": self.head}, outcome="crashed")
        self.assert_refused("no completed chapt-reviewer run")
        runs[1].update(outcome="completed", profile="chapt-worker")
        self.assert_refused("no completed chapt-reviewer run")
        runs[1]["profile"] = "chapt-reviewer"
        runs.append({"id": 3, "profile": "chapt-reviewer", "outcome": "completed", "ended_at": 9,
                     "metadata": {"candidate": self.base}})
        self.assert_refused("is not for")

    def test_environment_and_input_refusals(self):
        worker_home = str(self.tmp / "profiles" / "chapt-worker")
        for environ in (dict(self.env, HERMES_KANBAN_TASK="t_scr1"),
                        dict(self.env, HERMES_KANBAN_WORKSPACE=self.checkout),
                        dict(self.env, HERMES_HOME=worker_home),
                        dict(self.env, HERMES_PROFILE="chapt-reviewer"),
                        {key: value for key, value in self.env.items() if key != "HERMES_HOME"}):
            with self.subTest(environ=sorted(set(environ) ^ set(self.env))):
                self.assert_refused("", environ=environ)
        self.assertEqual(self.calls, [])
        self.assert_refused("40-character", sha=self.head[:12])
        self.assert_refused("40-character", sha=self.head.upper())
        self.assert_refused("Kanban task id", card="t_scr1; true")
        missing = "f" * 40
        self.card["runs"][1]["metadata"] = {"candidate": missing}
        self.assert_refused("not a local commit", sha=missing, approval=self.approval(missing))

    def test_origin_and_rewrite_refusals(self):
        self.git("remote", "set-url", "origin", self.remote + "/")
        self.assert_refused("origin is not EXACT")
        self.git("remote", "set-url", "origin", self.remote)
        self.git("config", f"url.{self.remote}.insteadOf", "elsewhere:")
        self.assert_refused("insteadOf")

    def test_non_fast_forward_remote_refused(self):
        moved = self.diverge()
        code, output = self.run_helper()
        self.assertEqual((code, self.pushes()), (1, []), output)
        self.assertIn("not an ancestor", output)
        self.assertEqual(self.remote_main(), moved)

    def test_already_pushed_reports_nothing(self):
        self.git("push", "-q", "origin", "main")
        code, output = self.run_helper()
        self.assertEqual((code, self.pushes()), (0, []), output)
        self.assertIn("nothing to push", output)

    def test_rejected_push_not_retried(self):
        hook = Path(self.remote) / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho protected branch >&2\nexit 1\n")
        hook.chmod(0o755)
        code, output = self.run_helper()
        self.assertEqual(code, 1, output)
        self.assertIn("PUSH REJECTED", output)
        self.assertIn("protected branch", output)
        self.assertEqual(len(self.pushes()), 1)
        self.assertEqual(self.remote_main(), self.base)

    def test_command_line_uses_only_constants(self):
        config = self.helper.default_config()
        self.assertEqual((config["checkout"], config["remote"], config["board"], config["project"]),
                         (SCRAPER, "git@github.com:raysong-sudo/cha-webpt-website-sync.git", "cha-pt", PROJECT))
        with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
            for extra in (["--checkout", self.checkout], ["--remote", self.remote]):
                with self.assertRaises(SystemExit):
                    self.helper.main(["--card", "t_scr1", "--sha", self.head, "--approval", "x", *extra])
        # A dispatched task is refused before any card read or git command.
        environ = dict(self.env, HERMES_KANBAN_TASK="t_scr1")
        result = subprocess.run((sys.executable, str(HELPER), "--card", "t_scr1", "--sha", self.head,
                                 "--approval", self.approval()), env=environ, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED: dispatched Kanban tasks", result.stdout)


SOULS = {name: ROOT / f"policies/profile-souls/{name}/SOUL.md" for name in (
    "chapt-orchestrator", "chapt-worker", "chapt-worker-2", "chapt-worker-glm-1", "chapt-worker-glm-2",
    "chapt-reviewer")}
SKILLS = (ROOT / "skills/multi-agent-coding-orchestrator/SKILL.md",
          ROOT / "policies/profile-skills/chapt-orchestrator/autonomous-ai-agents/"
                 "multi-agent-coding-orchestrator/SKILL.md")
PUSH_COMMAND = "git push git@github.com:raysong-sudo/cha-webpt-website-sync.git <sha>:refs/heads/main"


class PolicyText(unittest.TestCase):
    def text(self, path):
        return path.read_text()

    def baseline_text(self, path):
        return subprocess.run(("git", "-C", str(ROOT), "show", f"{BASELINE}:{path.relative_to(ROOT)}"),
                              check=True, text=True, stdout=subprocess.PIPE).stdout

    def test_three_repository_allowlist_and_declaration(self):
        for path in (*SOULS.values(), *SKILLS):
            text = self.text(path)
            with self.subTest(path=path.relative_to(ROOT)):
                for repo in (BACKEND, FRONTEND, SCRAPER):
                    self.assertIn(f"`{repo}`", text)
                self.assertIn(DECLARATION, text)
                self.assertIn(PROJECT, text)
                self.assertNotIn("exactly two repositories", text)
                self.assertNotIn("dual-repository", text)
        for path in SKILLS:
            self.assertIn("Repository allowlist (exactly three)", self.text(path))
        self.assertIn("exactly three repositories", self.text(SOULS["chapt-orchestrator"]))

    def test_workers_and_reviewer_local_only(self):
        for name, path in SOULS.items():
            if name == "chapt-orchestrator":
                continue
            text = self.text(path)
            with self.subTest(profile=name):
                self.assertIn("never push, open a pr, or touch the remote", text.lower())
                self.assertNotIn("chapt-push-scraper-main", text)
                self.assertIn("only `chapt-orchestrator`" if name == "chapt-reviewer" else
                              "belongs only to `chapt-orchestrator` under a per-push owner approval", text)
        for path in SKILLS:
            self.assertIn("Workers and `chapt-reviewer` stay local-only on scraper cards", self.text(path))

    def test_controller_only_per_sha_approval(self):
        text = self.text(SOULS["chapt-orchestrator"])
        for phrase in ("Only you may push, and only a reviewed commit to the scraper repository's `main`",
                       "names the repository, `main`, and the exact reviewed commit SHA",
                       "Approval never carries over to another SHA, branch, or repository",
                       "a general go-ahead is not a push approval", "scripts/chapt-push-scraper-main",
                       PUSH_COMMAND, "never rebase, merge, retry, force-push, delete refs, or push tags"):
            self.assertIn(phrase, text)
        for path in SKILLS:
            text = self.text(path)
            for phrase in ("Only `chapt-orchestrator` may push", "Approval never carries over",
                           "chapt-push-scraper-main --card <id> --sha <sha>", PUSH_COMMAND,
                           "every push, PR and deployment ban for `cha-pt` and `cha-pt-frontend` is unchanged"):
                self.assertIn(phrase, text, path)

    def test_edits_are_surgical_and_preserve_existing_rules(self):
        expected_removed = dict.fromkeys(SOULS.values(), 1)
        expected_removed.update({SKILLS[0]: 3, SKILLS[1]: 4})
        for path, count in expected_removed.items():
            base = self.baseline_text(path).split("\n\n")
            current = self.text(path)
            relative = str(path.relative_to(ROOT))
            if relative in TERMINOLOGY_EDITS:
                # Reverse the later model-name and wording change (t_c836d2a4).
                current = reverse_terminology_edits(relative, current)
            if path == SKILLS[1]:
                # Reverse the later card-creation change (t_b6d0e590) to Card Setup steps 1 and 4.
                for changed, previous in CARD_CREATION_EDITS:
                    self.assertEqual(current.count(changed.decode()), 1)
                    current = current.replace(changed.decode(), previous.decode(), 1)
            new = current.split("\n\n")
            removed = [paragraph for paragraph in base if paragraph not in new]
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(len(removed), count)
                for paragraph in removed:
                    self.assertTrue("cha-pt-frontend" in paragraph or "dual-repository" in paragraph, paragraph)
        for path in SKILLS:
            text = self.text(path)
            assert_rule(self, text, "user says stop", "terminate every owned background worker", "reviewer",
                        "preview server", "watcher", "verify they stopped",
                        "Do not resume", "delayed completion notification")
            assert_rule(self, text, "policy expansion never broadens an active card", "P4 campaign")
        self.assertIn("never restart from delayed callbacks without user resume", self.text(SKILLS[0]))
        self.assertIn("Frontend project EXACT cha-pt-frontend.", self.text(SOULS["chapt-orchestrator"]))

    def test_spec_copied_unchanged_and_ascii_tools(self):
        spec = ROOT / "docs/specs/261020-chapt-scraper-repository-scope-and-push.md"
        self.assertTrue(spec.is_file())
        for path in (HELPER, HOOK):
            self.assertTrue(os.access(path, os.X_OK), path)
            self.assertFalse(path.is_symlink())
            path.read_bytes().decode("ascii")


if __name__ == "__main__":
    unittest.main()
