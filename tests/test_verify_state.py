#!/usr/bin/env python3
import importlib.util
import hashlib
import io
import json
import shutil
import tempfile
from importlib.machinery import SourceFileLoader
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-state"
FORCED_SKILLS = ROOT / "scripts" / "check-forced-skills"
FIXTURES = ROOT / "tests" / "fixtures"


def check(*args, code=0, text=None):
    result = subprocess.run([str(VERIFY), *args], text=True, capture_output=True)
    assert result.returncode == code, result.stdout + result.stderr
    if text:
        assert text in result.stdout, result.stdout


# baseline: plugins plus a shared producer outbox and the loaded worker pass.
check("--fixture", str(FIXTURES / "clean.yaml"))
# plugin enablement alone is insufficient: every producer must expose the shared
# absolute outbox and the rendered, loaded worker must match it.
spec = importlib.util.spec_from_loader("verify_state", SourceFileLoader("verify_state", str(VERIFY)))
assert spec and spec.loader
verify_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_state)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_terminal_notification_runtime(errors, {}, ["default"])
assert "terminal notification runtime pending default" in errors[0]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_terminal_notification_runtime(errors, {
        "shared_environment": {"outbox": "/private/outbox.sqlite3"},
        "worker": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/kanban.db", "plist_rendered": True, "loaded": True},
    }, ["default"])
assert errors == ["terminal notification runtime pending worker: loaded LaunchAgent arguments/environment do not match the shared paths"], errors
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_terminal_notification_runtime(errors, {
        "shared_environment": {"outbox": "/private/other.sqlite3"},
        "worker": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/kanban.db", "plist_rendered": True, "loaded": True, "loaded_state_matches": True},
    }, ["default"])
assert errors == ["terminal notification runtime drift: producers and worker must share one outbox"], errors

# live-observation boundary, end to end against a stubbed command runner:
# false green #1 — launchd domain set (or plugins enabled) but the running multiplex
# gateway never inherited the shared environment because it was not restarted.
OUTBOX, KANBAN = "/private/hermes/terminal/outbox.sqlite3", "/private/hermes/kanban/kanban.db"
HERMES_EXE = shutil.which("hermes")
assert HERMES_EXE and Path(HERMES_EXE).is_absolute()
WORKER_PATH = f"{Path(HERMES_EXE).parent}:/usr/bin:/bin:/usr/sbin:/sbin"
PLIST_EXTRACTS = {"EnvironmentVariables.HERMES_TERMINAL_OUTBOX": OUTBOX,
                  "EnvironmentVariables.HERMES_KANBAN_DB": KANBAN,
                  "EnvironmentVariables.PATH": WORKER_PATH,
                  "ProgramArguments.3": OUTBOX, "ProgramArguments.5": KANBAN}


def stub_runner(ps_output, launchctl_output, plist_values):
    import tempfile
    plist = Path(tempfile.mkdtemp(prefix="hermes-verify-")) / "worker.plist"
    plist.write_text("stub")
    ps_lines = ps_output if isinstance(ps_output, list) else [ps_output]
    def runner(*args):
        if args[:3] == ("ps", "axeww", "-o"):
            return subprocess.CompletedProcess(args, 0, stdout="".join(f"4860{i} {line}" for i, line in enumerate(ps_lines)), stderr="")
        if args[:2] == ("plutil", "-extract"):
            want = plist_values.get(args[2])
            code, out = (0, want) if want is not None else (1, "")
            return subprocess.CompletedProcess(args, code, stdout=out, stderr="")
        if args[:2] == ("launchctl", "print"):
            code = 0 if launchctl_output is not None else 1
            return subprocess.CompletedProcess(args, code, stdout=launchctl_output or "", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
    return runner, plist


def live_errors(ps_output, launchctl_output, plist_values):
    runner, plist = stub_runner(ps_output, launchctl_output, plist_values)
    errors = []
    with redirect_stdout(io.StringIO()):
        runtime = verify_state.build_live_terminal_runtime(errors, runner, ["default"], plist=plist)
        verify_state.check_terminal_notification_runtime(errors, runtime, ["default"])
    return errors, runtime


PS_ENV_SET = (f"/venv/bin/python -I -c launcher gateway run --external-supervisor "
              f"HERMES_TERMINAL_OUTBOX={OUTBOX} PATH=/bin\n")
PS_ENV_PINNED = PS_ENV_SET.replace(" PATH=/bin", f" HERMES_KANBAN_DB={KANBAN} PATH=/bin")
PS_WRAPPER = "/venv/bin/python --run-module hermes_cli.stderr_timestamp -- /venv/bin/hermes gateway run --external-supervisor PATH=/bin\n"
PS_ENV_MISSING = "/venv/bin/python -m hermes_cli.main gateway run --external-supervisor PATH=/bin\n"
LOADED_MATCHING = (f"gui/501/label = {{\n\tstate = running\n\n\targuments = {{\n\t\t/venv/bin/python\n\t\t/worker.py\n\t\t--db\n\t\t{OUTBOX}\n"
                   f"\t\t--kanban-db\n\t\t{KANBAN}\n\t}}\n\n\tenvironment = {{\n"
                   f"\t\tHERMES_TERMINAL_OUTBOX => {OUTBOX}\n\t\tHERMES_KANBAN_DB => {KANBAN}\n\t}}\n}}\n")
LOADED_MATCHING = LOADED_MATCHING.replace(
    f"\t\tHERMES_KANBAN_DB => {KANBAN}\n", f"\t\tHERMES_KANBAN_DB => {KANBAN}\n\t\tPATH => {WORKER_PATH}\n")
LOADED_STALE = (f"gui/501/label = {{\n\tstate = running\n\n\targuments = {{\n\t\t/venv/bin/python\n\t\t/worker.py\n\t\t--db\n\t\t/old/outbox.sqlite3\n"
                f"\t\t--kanban-db\n\t\t/old/kanban.db\n\t}}\n\n\tenvironment = {{\n"
                f"\t\tHERMES_TERMINAL_OUTBOX => /old/outbox.sqlite3\n\t\tHERMES_KANBAN_DB => /old/kanban.db\n\t}}\n}}\n")

# gateway present but outbox env not inherited stays red
errors, _ = live_errors(PS_ENV_MISSING, LOADED_MATCHING, PLIST_EXTRACTS)
assert any("running gateway has not inherited" in e for e in errors), errors
# a legacy single-DB pin on the gateway is incompatible with multi-board dispatch
errors, _ = live_errors(PS_ENV_PINNED, LOADED_MATCHING, PLIST_EXTRACTS)
assert any("must not inherit HERMES_KANBAN_DB" in e for e in errors), errors
# rendered plist matches but the loaded job is stale stays red
errors, _ = live_errors(PS_ENV_SET, LOADED_STALE, PLIST_EXTRACTS)
assert any("loaded LaunchAgent arguments/environment do not match" in e for e in errors), errors
# fully rolled out (env inherited, plist rendered, loaded job effective state matches) passes
errors, runtime = live_errors(PS_ENV_SET, LOADED_MATCHING, PLIST_EXTRACTS)
assert errors == [], errors
# a supervisor wrapper may omit producer env; only the actual gateway process is authoritative
errors, _ = live_errors([PS_WRAPPER, PS_ENV_SET], LOADED_MATCHING, PLIST_EXTRACTS)
assert errors == [], errors
# the worker PATH is validated structurally from the rendered plist itself; the
# verifier caller's own shutil.which("hermes") directory is irrelevant because
# deployment validly resolved a different Hermes at render time.
import tempfile
deployed_bin = Path(tempfile.mkdtemp(prefix="hermes-deployed-bin-"))
hermes_helper = deployed_bin / "hermes"
hermes_helper.write_text("#!/bin/sh\nexit 0\n")
hermes_helper.chmod(0o755)
DEPLOYED_PATH = f"{deployed_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
assert deployed_bin != Path(HERMES_EXE).parent  # caller and deployment genuinely differ
plist_other_helper = {**PLIST_EXTRACTS, "EnvironmentVariables.PATH": DEPLOYED_PATH}
loaded_other_helper = LOADED_MATCHING.replace(WORKER_PATH, DEPLOYED_PATH)
errors, _ = live_errors(PS_ENV_SET, loaded_other_helper, plist_other_helper)
assert errors == [], errors  # differing caller PATH vs valid deployed PATH passes
# structurally invalid rendered PATH stays red with a specific diagnostic
plist_relative = {**PLIST_EXTRACTS, "EnvironmentVariables.PATH": ".local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
errors, _ = live_errors(PS_ENV_SET, LOADED_MATCHING.replace(WORKER_PATH, ".local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
                        plist_relative)
assert any("rendered LaunchAgent PATH" in e for e in errors), errors
plist_short_suffix = {**PLIST_EXTRACTS, "EnvironmentVariables.PATH": f"{deployed_bin}:/usr/bin:/bin"}
errors, _ = live_errors(PS_ENV_SET, LOADED_MATCHING, plist_short_suffix)
assert any("rendered LaunchAgent PATH" in e for e in errors), errors
# helper dir without a usable Hermes executable stays red
empty_bin = Path(tempfile.mkdtemp(prefix="hermes-empty-bin-"))
missing_helper_path = f"{empty_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
plist_no_helper = {**PLIST_EXTRACTS, "EnvironmentVariables.PATH": missing_helper_path}
errors, _ = live_errors(PS_ENV_SET, LOADED_MATCHING.replace(WORKER_PATH, missing_helper_path), plist_no_helper)
assert any("no usable Hermes executable" in e for e in errors), errors
noexec_bin = Path(tempfile.mkdtemp(prefix="hermes-noexec-bin-"))
noexec_helper = noexec_bin / "hermes"
noexec_helper.write_text("#!/bin/sh\nexit 0\n")  # present but not executable
noexec_helper_path = f"{noexec_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
plist_noexec_helper = {**PLIST_EXTRACTS, "EnvironmentVariables.PATH": noexec_helper_path}
errors, _ = live_errors(PS_ENV_SET, LOADED_MATCHING.replace(WORKER_PATH, noexec_helper_path), plist_noexec_helper)
assert any("no usable Hermes executable" in e for e in errors), errors
# a missing rendered PATH stays red with its own diagnostic
plist_without_path = {key: value for key, value in PLIST_EXTRACTS.items()
                      if key != "EnvironmentVariables.PATH"}
errors, _ = live_errors(PS_ENV_SET, LOADED_MATCHING, plist_without_path)
assert any("rendered LaunchAgent PATH missing" in e for e in errors), errors
# a stale PATH in the loaded job stays red against the validated rendered PATH
loaded_without_path = LOADED_MATCHING.replace(f"\t\tPATH => {WORKER_PATH}\n", "")
errors, _ = live_errors(PS_ENV_SET, loaded_without_path, PLIST_EXTRACTS)
assert any("loaded LaunchAgent arguments/environment do not match" in e for e in errors), errors
loaded_stale_path = LOADED_MATCHING.replace(f"PATH => {WORKER_PATH}", "PATH => /usr/bin:/bin")
errors, _ = live_errors(PS_ENV_SET, loaded_stale_path, PLIST_EXTRACTS)
assert any("loaded LaunchAgent arguments/environment do not match" in e for e in errors), errors
# gateway processes disagreeing on the shared environment is drift
PS_DISAGREE = [PS_ENV_SET.replace(OUTBOX, "/a.sqlite3"), PS_ENV_SET]
errors, _ = live_errors(PS_DISAGREE, LOADED_MATCHING, PLIST_EXTRACTS)
assert any("gateway processes disagree" in e for e in errors), errors
# model drift on a known profile fails
check("--fixture", str(FIXTURES / "behavior-changing-model-drift.yaml"), code=1, text="model drift")
# running unexpected profile fails
check("--fixture", str(FIXTURES / "active-extra.yaml"), code=1, text="behavior-changing unexpected profile")
# stopped unexpected profile only warns
check("--fixture", str(FIXTURES / "dormant-extra.yaml"), text="WARN: dormant")
# enabled unexpected plugin on a roster profile fails
check("--fixture", str(FIXTURES / "unexpected-plugin.yaml"), code=1, text="behavior-changing unexpected plugin")
# disabled required plugin fails
check("--fixture", str(FIXTURES / "missing-plugin.yaml"), code=1, text="plugin drift")
# command approval policy drift fails
check("--fixture", str(FIXTURES / "approval-mode-drift.yaml"), code=1,
      text="approval mode drift jobcron-worker")
# desired deployment stays red until every terminal-notification producer is observed enabled
check("--fixture", str(FIXTURES / "terminal-deployment-pending.yaml"), code=1, text="terminal notification deployment pending")
# rollback observation is also red against the authorized deployment declaration
check("--fixture", str(FIXTURES / "terminal-notification-rollback.yaml"), code=1, text="terminal notification deployment pending")
# enabled required plugin at wrong pin/version fails
check("--fixture", str(FIXTURES / "plugin-pin-drift.yaml"), code=1, text="expected pinned 4.8.4@16f29800")
# deployed skill hash divergence from tracked canonical source fails
check("--fixture", str(FIXTURES / "deployed-skill-divergence.yaml"), code=1, text="deployed skill hash mismatch")
# The canonical orchestration policy is versioned and its source-to-live hash
# enforcement covers the default profile's deployed orchestrator skill.
orchestrator = (ROOT / "skills" / "multi-agent-coding-orchestrator" / "SKILL.md").read_text()
assert "version: 0.6.4" in orchestrator
assert "Routing validation and dispatch receipt" in orchestrator
assert "Authentication expiry blocks a fresh observation" in orchestrator
assert "currently_actionable" in orchestrator
assert "jobcron-orchestrator" in orchestrator
assert "chapt-reviewer" in orchestrator
assert "gpt-6.1-sol" in orchestrator
# Terminal retry remains an explicit card-scoped v2 policy, never the default.
assert "version: 0.6.4" in orchestrator
assert "RETRY_TERMINAL" in orchestrator
assert "terminal_retry_policy: astra-until-approve-v1" in orchestrator
assert "glm-review-v2" in orchestrator
assert "HUMAN_BLOCK" in orchestrator
assert "Provider, quota, crash, timeout, unavailable-model, and context-exhaustion" in orchestrator
roster = json.loads((ROOT / "roster.yaml").read_text())
assert roster["schema_version"] == 2
assert roster["ladder_version"] == "glm-review-v2"
assert roster["terminal_retry"]["default"] == "bounded-human-block"
assert roster["terminal_retry"]["supported_opt_in"] == "astra-until-approve-v1"
assert roster["project_fleets"]["jobcron"]["reviewer"] == "jobcron-reviewer"
assert roster["project_fleets"]["cha-pt"]["orchestrator"] == "chapt-orchestrator"
assert roster["project_fleets"]["jobcron"]["workers"] == [
    "jobcron-worker", "jobcron-worker-glm-1", "jobcron-worker-glm-2"]
assert roster["project_fleets"]["cha-pt"]["workers"] == [
    "chapt-worker", "chapt-worker-glm-1", "chapt-worker-glm-2"]
assert roster["project_fleets"]["cha-pt"]["repositories"] == [
    "/Users/chanbla11mit/projects/cha-pt",
    "/Users/chanbla11mit/projects/cha-pt-frontend",
]
assert roster["project_fleets"]["cha-pt"]["frontend_project"] == "cha-pt-frontend"
snapshot = json.loads((ROOT / "snapshots" / "sanitized-current-state.yaml").read_text())
project_repair_policy = {
    "version": "bounded-convergence-v1",
    "requires_authorization_mode": "autonomous",
    "max_approaches": 3,
    "max_attempts_per_approach": 3,
    "max_infrastructure_retries_per_attempt": 1,
    "project_boards": ["jobcron", "cha-pt"],
}
assert roster["project_repair_policy"] == project_repair_policy
assert snapshot["project_repair_policy"] == project_repair_policy
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_policy(errors, project_repair_policy, project_repair_policy)
assert errors == [], errors
drifted_repair_policy = json.loads(json.dumps(project_repair_policy))
drifted_repair_policy["max_attempts_per_approach"] = 2
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_policy(
        errors, project_repair_policy, drifted_repair_policy)
assert errors == ["project repair policy observed mapping drift"], errors
check("--fixture", str(FIXTURES / "project-repair-policy-drift.yaml"), code=1,
      text="project repair policy observed mapping drift")
assert "bounded-convergence-v1" in orchestrator
assert "max_attempts_per_approach: 3" in orchestrator
assert "max_infrastructure_retries_per_attempt: 1" in orchestrator
assert "changing a worker, model, card, branch, or worktree" in orchestrator

repair_strategy = "Use transaction fencing around the retry clock"
valid_repair_history = [{
    "approach_id": "transaction-fence",
    "strategy": repair_strategy,
    "strategy_sha256": hashlib.sha256(repair_strategy.encode()).hexdigest(),
    "material_difference_review_run_id": None,
    "attempts": [{
        "candidate_commit": None,
        "implementation_run_id": "run-worker-1",
        "review_run_id": None,
        "infrastructure_retries": 0,
        "outcome": "pending",
    }],
}]
valid_repair_card = {
    "id": "t_repair", "board": "jobcron",
    "body": "authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1",
    "comments": [{
        "body": f"repair_history: {json.dumps(valid_repair_history, separators=(',', ':'))}",
    }],
}
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [valid_repair_card])
assert errors == [], errors
completed_repair_history = json.loads(json.dumps(valid_repair_history))
completed_repair_history[0]["attempts"][0].update({
    "candidate_commit": "2" * 40,
    "review_run_id": "run-review-1",
    "outcome": "revise",
})
assert verify_state.project_repair_transition_valid(
    valid_repair_history, completed_repair_history)
next_attempt_history = json.loads(json.dumps(completed_repair_history))
next_attempt_history[0]["attempts"].append({
    "candidate_commit": None,
    "implementation_run_id": "run-worker-2",
    "review_run_id": None,
    "infrastructure_retries": 0,
    "outcome": "pending",
})
assert verify_state.project_repair_transition_valid(
    completed_repair_history, next_attempt_history)
retried_history = json.loads(json.dumps(valid_repair_history))
retried_history[0]["attempts"][0].update({
    "implementation_run_id": "run-worker-retry",
    "infrastructure_retries": 1,
})
assert verify_state.project_repair_transition_valid(valid_repair_history, retried_history)
infrastructure_failed_history = json.loads(json.dumps(retried_history))
infrastructure_failed_history[0]["attempts"][0]["outcome"] = "infrastructure_failed"
assert verify_state.project_repair_transition_valid(
    retried_history, infrastructure_failed_history)
blocked_history = json.loads(json.dumps(valid_repair_history))
blocked_history[0]["attempts"][0]["outcome"] = "blocked"
assert verify_state.project_repair_transition_valid(valid_repair_history, blocked_history)
whitespace_review_history = json.loads(json.dumps(completed_repair_history))
whitespace_review_history[0]["attempts"][0]["review_run_id"] = " run-review-1 "
assert not verify_state.valid_project_repair_history(whitespace_review_history)
reset_history = json.loads(json.dumps(valid_repair_history))
reset_history[0]["approach_id"] = "fresh-reset"
reset_strategy = "Rename the old idea and reset its counters"
reset_history[0]["strategy"] = reset_strategy
reset_history[0]["strategy_sha256"] = hashlib.sha256(reset_strategy.encode()).hexdigest()
reset_card = dict(
    valid_repair_card,
    comments=[
        {"body": f"repair_history: {json.dumps(completed_repair_history, separators=(',', ':'))}"},
        {"body": f"repair_history: {json.dumps(reset_history, separators=(',', ':'))}"},
    ],
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [reset_card])
assert errors == ["project repair contract drift t_repair: invalid repair history"], errors
batched_transition_card = dict(
    valid_repair_card,
    comments=[{
        "body": (f"repair_history: {json.dumps(valid_repair_history, separators=(',', ':'))}\n"
                 f"repair_history: {json.dumps(completed_repair_history, separators=(',', ':'))}"),
    }],
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [batched_transition_card])
assert errors == ["project repair contract drift t_repair: invalid repair history"], errors
unauthorized_batched_card = dict(
    batched_transition_card,
    body="Legacy card without repair authorization",
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [unauthorized_batched_card])
assert errors == ["project repair contract drift t_repair: exact authorization missing"], errors
missing_authorization = dict(
    valid_repair_card,
    body=valid_repair_card["body"].replace("authorization_mode: autonomous\n", ""),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [missing_authorization])
assert errors == ["project repair contract drift t_repair: exact authorization missing"], errors
too_many_attempts = json.loads(json.dumps(valid_repair_history))
too_many_attempts[0]["attempts"] *= 2
over_budget_card = dict(
    valid_repair_card,
    comments=[{
        "body": f"repair_history: {json.dumps(too_many_attempts, separators=(',', ':'))}",
    }],
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [over_budget_card])
assert errors == ["project repair contract drift t_repair: invalid repair history"], errors
duplicate_strategy = json.loads(json.dumps(valid_repair_history))
duplicate_strategy.append({
    "approach_id": "renamed-approach",
    "strategy": repair_strategy,
    "strategy_sha256": hashlib.sha256(repair_strategy.encode()).hexdigest(),
    "material_difference_review_run_id": "run-material-review-1",
    "attempts": [{
        "candidate_commit": None,
        "implementation_run_id": "run-worker-3",
        "review_run_id": None,
        "infrastructure_retries": 0,
        "outcome": "pending",
    }],
})
duplicate_strategy_card = dict(
    valid_repair_card,
    comments=[{
        "body": f"repair_history: {json.dumps(duplicate_strategy, separators=(',', ':'))}",
    }],
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [duplicate_strategy_card])
assert errors == ["project repair contract drift t_repair: invalid repair history"], errors
prefixed_authorization = dict(
    valid_repair_card,
    body="not_authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1",
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [prefixed_authorization])
assert errors == ["project repair contract drift t_repair: exact authorization missing"], errors
legacy_policy_mention = {
    "id": "t_legacy", "board": "jobcron",
    "body": "Legacy note: do not add repair_policy: bounded-convergence-v1",
    "comments": [],
}
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [legacy_policy_mention])
assert errors == [], errors
infra_failed_without_retry = json.loads(json.dumps(valid_repair_history))
infra_failed_without_retry[0]["attempts"][0]["outcome"] = "infrastructure_failed"
bad_infra_card = dict(
    valid_repair_card,
    comments=[{
        "body": f"repair_history: {json.dumps(infra_failed_without_retry, separators=(',', ':'))}",
    }],
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_repair_cards(errors, [bad_infra_card])
assert errors == ["project repair contract drift t_repair: invalid repair history"], errors
check("--fixture", str(FIXTURES / "project-repair-card-drift.yaml"), code=1,
      text="project repair contract drift t_fixture_repair: exact authorization missing")
assert roster["repository_policies"] == snapshot["repository_policies"]
frontend_policy = roster["repository_policies"]["cha-pt-frontend"]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_repository_policies(errors, roster["repository_policies"], {
        "cha-pt-frontend": frontend_policy["sha256"]})
assert errors == [], errors
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_repository_policies(errors, roster["repository_policies"], {
        "cha-pt-frontend": "0" * 64})
assert errors == ["repository policy drift cha-pt-frontend"], errors
redirected_policy = json.loads(json.dumps(roster["repository_policies"]))
redirected_policy["cha-pt-frontend"]["path"] = "/Users/chanbla11mit/projects/cha-pt-frontend/CLAUDE.md"
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_repository_policies(errors, redirected_policy)
assert errors == ["repository policy path drift cha-pt-frontend"], errors
redirected_soul = json.loads(json.dumps(roster["profile_souls"]))
redirected_soul["chapt-worker"]["live"] = str(
    ROOT / redirected_soul["chapt-worker"]["source"])
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_souls(errors, redirected_soul)
assert errors == ["profile SOUL path drift chapt-worker"], errors
check("--fixture", str(FIXTURES / "frontend-repository-policy-drift.yaml"), code=1,
      text="repository policy drift cha-pt-frontend")
assert roster["project_dispatch_allowlist"] == [
    "jobcron-worker", "jobcron-worker-glm-1", "jobcron-worker-glm-2", "jobcron-reviewer",
    "chapt-worker", "chapt-worker-glm-1", "chapt-worker-glm-2", "chapt-reviewer"]
roster_profiles = {profile["name"]: profile for profile in roster["profiles"]}
assert roster["approval_policy"]["mode"] == "off"
assert roster["approval_policy"]["profiles"] == list(roster_profiles)
assert not roster_profiles["jobcron-orchestrator"]["dispatch_eligible"]
assert not roster_profiles["chapt-orchestrator"]["dispatch_eligible"]
project_workers = (
    "jobcron-worker", "jobcron-worker-glm-1", "jobcron-worker-glm-2",
    "chapt-worker", "chapt-worker-glm-1", "chapt-worker-glm-2")
for profile in (*project_workers, "jobcron-reviewer", "chapt-reviewer"):
    assert roster_profiles[profile]["dispatch_eligible"]
for profile in ("jobcron-worker-glm-1", "jobcron-worker-glm-2",
                "chapt-worker-glm-1", "chapt-worker-glm-2"):
    assert roster_profiles[profile]["model"] == "glm-5.3"
    assert roster_profiles[profile]["provider"] == "zai"
for profile in ("jobcron-orchestrator", *project_workers, "jobcron-reviewer",
                "chapt-orchestrator", "chapt-reviewer"):
    assert "hermes-terminal-outcome-notification" in roster_profiles[profile]["installed_disabled_plugins"]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_isolation(errors, roster["project_fleets"], roster["project_fleets"])
assert errors == [], errors
extra_repo = json.loads(json.dumps(roster["project_fleets"]))
extra_repo["cha-pt"]["repositories"].append("/Users/chanbla11mit/projects/not-authorized")
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_project_isolation(errors, extra_repo, extra_repo)
assert "project repository allowlist drift: cha-pt" in errors, errors
check("--fixture", str(FIXTURES / "project-repository-allowlist-drift.yaml"), code=1,
      text="project repository allowlist drift: cha-pt")

valid_card = {
    "id": "t_example", "status": "running", "assignee": "chapt-worker",
    "workspace_kind": "worktree",
    "workspace_path": "/Users/chanbla11mit/projects/cha-pt/.worktrees/t_example",
    "body": ("Repository /Users/chanbla11mit/projects/cha-pt ONLY. "
             "Baseline EXACT 0123456789abcdef0123456789abcdef01234567. "
             "Independent reviewer chapt-reviewer.\n## Test contract\n`go test ./...`"),
}
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [valid_card])
assert errors == [], errors
legacy_p4_card = dict(
    valid_card,
    id="t_4d3c8997",
    workspace_path="/Users/chanbla11mit/projects/cha-pt/.worktrees/t_4d3c8997",
    body=("Repository /Users/chanbla11mit/projects/cha-pt ONLY. "
          "Baseline EXACT 0123456789abcdef0123456789abcdef01234567. "
          "Independent reviewer chapt-reviewer.\n## Execution resource/test ownership\n"
          "Full go test -json ./... -count=1 and go test -race -json ./... -count=1; "
          "vet/production scratch build/read-only gofmt/whitespace."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [legacy_p4_card])
assert errors == [], errors
frontend_card = dict(
    valid_card,
    project_id="cha-pt-frontend",
    workspace_path="/Users/chanbla11mit/projects/cha-pt-frontend/.worktrees/t_example",
    body=("Repository /Users/chanbla11mit/projects/cha-pt-frontend ONLY. "
          "Baseline EXACT 0123456789abcdef0123456789abcdef01234567. "
          "Independent reviewer chapt-reviewer. Follow AGENTS.md; operator-protected paths require "
          "explicit human authorization.\n"
          "Frontend project EXACT cha-pt-frontend.\n"
          "Frontend editable paths EXACT site/index.html, site/static/styles/main.css.\n"
          "External writes PROHIBITED without separate explicit human authorization on this card.\n"
          "## Test contract\n`python3 checks/run.py --all`"),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [frontend_card])
assert errors == [], errors
invalid_card = dict(valid_card, body=valid_card["body"].replace("## Test contract\n`go test ./...`", ""))
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [invalid_card])
assert errors == ["Cha PT card contract drift t_example: explicit test contract missing"], errors
keyword_only_test = dict(
    valid_card,
    body=("Repository /Users/chanbla11mit/projects/cha-pt ONLY. "
          "Baseline EXACT 0123456789abcdef0123456789abcdef01234567. "
          "Independent reviewer chapt-reviewer.\n## Test contract\n"
          "No executable test command is specified; pnpm is only mentioned as the package manager."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [keyword_only_test])
assert errors == ["Cha PT card contract drift t_example: explicit test contract missing"], errors
negated_test_command = dict(
    valid_card,
    body=valid_card["body"].replace("`go test ./...`", "Do not run go test ./..."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_test_command])
assert errors == ["Cha PT card contract drift t_example: explicit test contract missing"], errors
negated_baseline = dict(
    valid_card,
    body=valid_card["body"].replace("Baseline EXACT", "No baseline exact"),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_baseline])
assert errors == ["Cha PT card contract drift t_example: exact baseline missing"], errors
negated_frontend_policy = dict(
    frontend_card,
    body=frontend_card["body"].replace(
        "Follow AGENTS.md; operator-protected paths require explicit human authorization.",
        "Do not follow AGENTS.md; operator-protected paths require explicit human authorization."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_frontend_policy])
assert errors == ["Cha PT card contract drift t_example: frontend protected-path contract missing"], errors
negated_repository = dict(
    valid_card,
    body=valid_card["body"].replace("Repository ", "Do not use Repository "),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_repository])
assert errors == ["Cha PT card contract drift t_example: expected exactly one repository"], errors
negated_reviewer = dict(
    valid_card,
    body=valid_card["body"].replace(
        "Independent reviewer chapt-reviewer.", "Do not request chapt-reviewer."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_reviewer])
assert errors == ["Cha PT card contract drift t_example: independent review contract missing"], errors
negated_legacy_test = dict(
    legacy_p4_card,
    body=legacy_p4_card["body"].replace("Full go test", "Do not run Full go test"),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [negated_legacy_test])
assert errors == ["Cha PT card contract drift t_4d3c8997: explicit test contract missing"], errors
malformed_assignee = dict(valid_card, assignee=[])
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [malformed_assignee])
assert errors == ["Cha PT card contract drift t_example: independent review contract missing"], errors
missing_frontend_scope = dict(
    frontend_card,
    project_id=None,
    body=frontend_card["body"].replace(
        "Frontend project EXACT cha-pt-frontend.\n"
        "Frontend editable paths EXACT site/index.html, site/static/styles/main.css.\n"
        "External writes PROHIBITED without separate explicit human authorization on this card.\n",
        ""),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [missing_frontend_scope])
assert errors == ["Cha PT card contract drift t_example: frontend authorization contract missing"], errors
protected_frontend_path = dict(
    frontend_card,
    body=frontend_card["body"].replace(
        "site/index.html, site/static/styles/main.css", "checks/**"),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [protected_frontend_path])
assert errors == ["Cha PT card contract drift t_example: frontend authorization contract missing"], errors
for forbidden_path in (
        "site/static/scripts/protected/override.html",
        "site/static/styles/**",
        "site/static/styles/"):
    invalid_path_card = dict(
        frontend_card,
        body=frontend_card["body"].replace(
            "site/index.html, site/static/styles/main.css", forbidden_path),
    )
    errors = []
    with redirect_stdout(io.StringIO()):
        verify_state.check_chapt_card_contract(errors, [invalid_path_card])
    assert errors == [
        "Cha PT card contract drift t_example: frontend authorization contract missing"], errors
contradictory_external_write = dict(
    frontend_card,
    body=frontend_card["body"] + "\nPush is authorized for this local card.",
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [contradictory_external_write])
assert errors == ["Cha PT card contract drift t_example: frontend authorization contract missing"], errors
for contradictory_authority in (
        "You are authorized to push this branch.",
        "PR is permitted for this card.",
        "Merging and an Amplify preview are allowed.",
        "You may push.",
        "Pushes are allowed.",
        "You may merge.",
        "Merging is allowed.",
        "PRs are allowed.",
        "Pull requests are approved.",
        "Pull-requests are approved.",
        "Previews are allowed.",
        "You may deploy.",
        "Deploying is permitted.",
        "Cloud access is granted.",
        "External-writes are allowed.",
        "Authorization is granted to push."):
    contradictory_card = dict(
        frontend_card,
        body=frontend_card["body"] + "\n" + contradictory_authority,
    )
    errors = []
    with redirect_stdout(io.StringIO()):
        verify_state.check_chapt_card_contract(errors, [contradictory_card])
    assert errors == [
        "Cha PT card contract drift t_example: frontend authorization contract missing"], errors
duplicate_prohibition = dict(
    frontend_card,
    body=(frontend_card["body"] + "\n" +
          "External writes PROHIBITED without separate explicit human authorization on this card."),
)
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_chapt_card_contract(errors, [duplicate_prohibition])
assert errors == [
    "Cha PT card contract drift t_example: frontend authorization contract missing"], errors

def failing_kanban_list(*args):
    return subprocess.CompletedProcess(args, 2, stdout="", stderr="unrecognized arguments")

errors = []
with redirect_stdout(io.StringIO()):
    assert verify_state.observe_open_chapt_cards(errors, failing_kanban_list) == []
assert errors == ["unable to read open Cha PT card list"], errors

def malformed_kanban_list(*args):
    return subprocess.CompletedProcess(args, 0, stdout="[null]", stderr="")

errors = []
with redirect_stdout(io.StringIO()):
    assert verify_state.observe_open_chapt_cards(errors, malformed_kanban_list) == []
assert errors == ["unable to read open Cha PT card list"], errors

# The Cha PT fleet has one board but two explicitly allowlisted repositories.
# Every role contract keeps cards pinned to one repository/worktree/baseline/test
# contract, and frontend work retains its protected-path + external-write gates.
assert "`/Users/chanbla11mit/projects/cha-pt-frontend`" in orchestrator
assert "one exact repository" in orchestrator
assert "Operator-protected" in orchestrator
for profile in ("chapt-orchestrator", "chapt-worker", "chapt-worker-glm-1",
                "chapt-worker-glm-2", "chapt-reviewer"):
    contract = (ROOT / "policies" / "profile-souls" / profile / "SOUL.md").read_text()
    assert "/Users/chanbla11mit/projects/cha-pt" in contract
    assert "/Users/chanbla11mit/projects/cha-pt-frontend" in contract
    assert "board `cha-pt`" in contract
    assert "baseline" in contract
    assert "test contract" in contract
    assert "push" in contract and "PR" in contract and "deploy" in contract
assert "operator-protected" in (
    ROOT / "policies" / "profile-souls" / "chapt-reviewer" / "SOUL.md").read_text()
assert roster["profile_souls"] == json.loads(
    (ROOT / "snapshots" / "sanitized-current-state.yaml").read_text())["profile_souls"]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_souls(errors, roster["profile_souls"], {
        profile: entry["sha256"] for profile, entry in roster["profile_souls"].items()})
assert errors == [], errors
drifted_souls = {profile: entry["sha256"] for profile, entry in roster["profile_souls"].items()}
drifted_souls["chapt-reviewer"] = "0" * 64
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_souls(errors, roster["profile_souls"], drifted_souls)
assert errors == ["profile SOUL drift chapt-reviewer"], errors
check("--fixture", str(FIXTURES / "chapt-profile-soul-drift.yaml"), code=1,
      text="profile SOUL drift chapt-reviewer")
check("--fixture", str(FIXTURES / "terminal-retry-default-drift.yaml"), code=1,
      text="terminal retry default drift")
check("--fixture", str(FIXTURES / "terminal-retry-missing-scope.yaml"), code=1,
      text="terminal retry policy missing required scope")
check("--fixture", str(FIXTURES / "terminal-retry-missing-human-gate.yaml"), code=1,
      text="terminal retry policy missing human/infrastructure exclusion")
# enabled Ponytail on an implementation profile fails with its own diagnostic
check("--fixture", str(FIXTURES / "ponytail-enabled-drift.yaml"), code=1, text="must be disabled")
# absent required-disabled Ponytail fails with its own diagnostic
check("--fixture", str(FIXTURES / "ponytail-absent-drift.yaml"), code=1, text="required-disabled ponytail absent")
# a missing per-profile deployed copy fails (dormant profile included)
check("--fixture", str(FIXTURES / "skill-deployment-missing.yaml"), code=1, text="deployed skill copy missing")
# a supporting file in either deployment skill is part of the deployed tree contract
check("--fixture", str(FIXTURES / "deployment-skill-supporting-file-drift.yaml"), code=1,
      text="deployed skill hash mismatch")
# Astra's intentional local learned-skill overrides are declared rather than normalized into fleet drift.
check("--fixture", str(FIXTURES / "astra-local-override.yaml"))
local_overrides = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())["skill"]["profile_local_skill_overrides"]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_local_skill_overrides(errors, local_overrides, local_overrides)
assert errors == [], errors
for profile in ("jobcron-orchestrator", "chapt-orchestrator"):
    rel, want = next(iter(local_overrides[profile].items()))
    tracked = ROOT / "policies" / "profile-skills" / profile / rel
    assert tracked.is_file()
    assert hashlib.sha256(tracked.read_bytes()).hexdigest() == want
drifted_overrides = json.loads(json.dumps(local_overrides))
drifted_overrides["worker-astra"]["software-development/spike/SKILL.md"] = "0" * 64
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_local_skill_overrides(errors, local_overrides, drifted_overrides)
assert errors == ["profile-local skill override declaration drift"], errors
# the implementation skill must not impose Ponytail's mandatory source-comment convention
assert "ponytail:" not in (ROOT / "skills" / "minimal-implementation" / "SKILL.md").read_text(), \
    "minimal-implementation must not mandate ponytail: source comments"
# empty adapter content fails (missing adoption)
check("--fixture", str(FIXTURES / "adapter-missing.yaml"), code=1, text="repository adapter missing")
# adapter present but adoption marker regressed fails
check("--fixture", str(FIXTURES / "adoption-status-drift.yaml"), code=1, text="adoption status drift")
# tracked adoption record with paused/unvalidated status fails
check("--fixture", str(FIXTURES / "adoption-record-drift.yaml"), code=1, text="tracked adoption record status drift")
# the full-commit pin is proven from plugin-manager install metadata, not the truncated display:
# a wrong expected revision or a missing metadata entry must fail closed.
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_adoption(errors, [])  # sanity: fixture path still guards omission
assert any("fixture omits adapter status" in e for e in errors), errors
pinned = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())["plugins"]["hermes-terminal-outcome-notification"]
errors = []
with redirect_stdout(io.StringIO()):
    for message in verify_state.full_pin_errors("default", pinned):
        print(f"FAIL: {message}")
        errors.append(message)
assert errors == [], errors
wrong_pin = dict(pinned, pinned_commit="0" * 40)
messages = verify_state.full_pin_errors("worker-astra", wrong_pin)
assert len(messages) == 1 and "install metadata not pinned at" in messages[0], messages
messages = verify_state.full_pin_errors("worker-terra-2", pinned)
assert len(messages) == 1 and "missing from install metadata" in messages[0], messages
# fail-closed schema: empty fixture cannot pass
check("--fixture", str(FIXTURES / "incomplete-empty.yaml"), code=1, text="incomplete fixture: missing required section")
# fail-closed schema: omitted roster profile cannot pass
check("--fixture", str(FIXTURES / "incomplete-omits-profile.yaml"), code=1, text="incomplete fixture: profile_models omits worker-sol")


# unreadable kanban config must FAIL, not collapse to None (None is a legal desired value for max_in_progress)
def test_unreadable_config(tmp="/tmp/hermes-verify-stub"):
    import os, stat, tempfile
    stub_dir = tempfile.mkdtemp(prefix="hermes-verify-")
    stub = Path(stub_dir) / "hermes"
    stub.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in *config*) exit 1;; esac\n"
        "printf '  default   gpt-5.6-sol   running   -   -\\n'\n"
    )
    stub.chmod(0o700)
    import os as _os
    env = dict(_os.environ, PATH=f"{stub_dir}:{_os.environ['PATH']}")
    result = subprocess.run([str(VERIFY)], text=True, capture_output=True, env=env)
    assert result.returncode == 1 and "unreadable" in result.stdout, result.stdout + result.stderr
    import shutil
    shutil.rmtree(stub_dir)


test_unreadable_config()


def forced_skill_check(*skills):
    home_root = Path(tempfile.mkdtemp(prefix="hermes-forced-skill-home-"))
    skill_root = home_root / "profiles" / "worker" / "skills" / "devops"
    for name in ("production-deployment", "production-deployment-planning"):
        path = skill_root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n")
    result = subprocess.run([str(FORCED_SKILLS), "--profile", "worker", "--skills", *skills,
                             "--home-root", str(home_root), "--source-root",
                             str(Path.home() / ".hermes" / "hermes-agent")], text=True, capture_output=True)
    shutil.rmtree(home_root)
    return result


# Preflight imports the same resolver under the assignee's HERMES_HOME, and rejects
# every incomplete requested set before card creation can exercise Hermes's partial-load behavior.
result = forced_skill_check("production-deployment", "production-deployment-planning")
assert result.returncode == 0 and json.loads(result.stdout)["missing"] == [], result.stdout + result.stderr
result = forced_skill_check("missing")
assert result.returncode == 1 and json.loads(result.stdout)["missing"] == ["missing"], result.stdout + result.stderr
result = forced_skill_check("production-deployment", "missing")
assert result.returncode == 1 and json.loads(result.stdout)["missing"] == ["missing"], result.stdout + result.stderr


# Rollback runbook contract: every restore command must name an existing backup
# source and an existing destination parent, and the runbook must never widen
# permissions. Every install -d command must carry the mode its path requires
# (scoped roots 0700, nested payload/skill dirs 0755), appear exactly once per
# path, order all 0700 commands before any 0755 one, and stay non-widening
# against the live directory it would recreate. Guards against the placeholder
# `cp -R` failure mode the human reviewer flagged and the contradictory-mode
# failure mode reviewer-sol flagged in run 376.
def test_rollback_runbook():
    import re as _re
    home = Path.home()
    runbook = (ROOT / "procedures" / "rollback-restore.md").read_text()
    cp_cmds = [ln.strip() for ln in runbook.splitlines() if ln.strip().startswith("cp -p ")]
    required_dirs = set()
    assert len(cp_cmds) >= 65, f"expected >=65 explicit restore commands, got {len(cp_cmds)}"
    for cmd in cp_cmds:
        src = _re.search(r'cp -p "([^"]+)" "([^"]+)"', cmd)
        assert src, f"unparseable restore command: {cmd}"
        source, dest = Path(src.group(1)), Path(src.group(2))
        required_dirs.add(dest.parent)
        parts = dest.relative_to(home / ".hermes").parts
        if parts[0] == "profiles":
            profile_home = home / ".hermes" / "profiles" / parts[1]
            required_dirs.update((profile_home, profile_home / parts[2]))
        else:
            required_dirs.add(home / ".hermes" / parts[0])
        assert source.is_file(), f"restore source missing: {source}"
        assert dest.parent.is_dir(), f"restore destination parent missing: {dest.parent}"
        assert ".." not in cmd and "cp -R" not in cmd, f"non-specific restore command: {cmd}"
        assert str(home) in str(source) and str(home) in str(dest), f"restore outside home: {cmd}"
    assert "cp -R" not in runbook

    # install -d contract: expected mode per path, uniqueness, phase ordering,
    # non-widening vs the live tree.
    def expected_mode(path: Path) -> str:
        parts = path.relative_to(home).parts
        assert parts[0] == ".hermes", f"recreation outside ~/.hermes: {path}"
        if parts in ((".hermes", "plugins"), (".hermes", "skills")):
            return "700"
        if parts[:2] == (".hermes", "profiles") and (
                len(parts) == 3 or (len(parts) == 4 and parts[3] in ("plugins", "skills"))):
            return "700"  # profile home or profile-scoped root
        return "755"      # nested payload/skill directory

    inst = [(m.group(1), Path(m.group(2))) for m in
            _re.finditer(r'^\s+install -d -m (\d{3}) "([^"]+)"$', runbook, _re.M)]
    assert len(inst) >= 30, f"expected >=30 install -d commands, got {len(inst)}"
    seen = {}
    for mode, path in inst:
        key = str(path)
        assert key not in seen, f"duplicate/conflicting install command for {key}"
        seen[key] = mode
        want = expected_mode(path)
        assert mode == want, f"{path}: expected -m {want}, got {mode}"
        if path.is_dir():
            live = path.stat().st_mode & 0o777
            assert (int(mode, 8) & live) == int(mode, 8), \
                f"widening recreation for {path} (live {live:o}, recreate {mode})"
        else:
            assert path.parent.is_dir(), f"recreation target parent missing: {path}"
    modes = [m for m, _ in inst]
    assert "700" in modes and "755" in modes
    last700 = max(i for i, m in enumerate(modes) if m == "700")
    first755 = min(i for i, m in enumerate(modes) if m == "755")
    assert last700 < first755, "every 0700 recreation command must precede every 0755 one"
    assert set(map(Path, seen)) == required_dirs, \
        f"recreation path set mismatch: missing {required_dirs - set(map(Path, seen))}, extra {set(map(Path, seen)) - required_dirs}"
    positions = {path: i for i, (_, path) in enumerate(inst)}
    for path, i in positions.items():
        if path.parent in positions:
            assert positions[path.parent] < i, f"parent must be explicit before child: {path}"

    # Execute only directory creation, remapped into an empty temporary tree.
    # A permissive umask exposes implicit 0755 profile homes on macOS. Check
    # after EACH command so a later chmod cannot hide a widened boundary.
    with tempfile.TemporaryDirectory(prefix="rollback-missing-tree-", dir=ROOT) as tmp:
        sandbox = Path(tmp)
        (sandbox / ".hermes").mkdir(mode=0o700)
        (sandbox / ".hermes/profiles").mkdir(mode=0o755)
        for _ in range(2):  # missing tree, then existing-tree replay
            for mode, path in inst:
                target = sandbox / path.relative_to(home)
                subprocess.run(["install", "-d", "-m", mode, str(target)],
                               check=True, umask=0o022)
                for required in required_dirs:
                    probe = sandbox / required.relative_to(home)
                    if probe.exists():
                        assert probe.stat().st_mode & 0o777 == int(expected_mode(required), 8), \
                            f"wrong recreated mode after {path}: {required}"
            assert all((sandbox / p.relative_to(home)).is_dir() for p in required_dirs)

    # mode contract: files 0644, orchestrator SKILL.md 0600, private trees stay 0700
    for probe in ("harness-drift-backups/20261002T064500+0900",
                  "harness-skill-backups/20261002T063137+0900"):
        tree = home / ".hermes/private" / probe
        assert tree.is_dir(), f"backup tree missing: {tree}"
        assert (tree.stat().st_mode & 0o777) == 0o700, f"backup tree widened: {tree}"
    # the runbook's mode description must match the trees it describes: per-
    # profile dirs 0700, nested dirs 0755, files 0644 (0600 SKILL.md.v0.3.3)
    drift = home / ".hermes/private/harness-drift-backups/20261002T064500+0900"
    assert all((p.stat().st_mode & 0o777) == 0o700
               for p in drift.iterdir() if p.is_dir()), "per-profile backup dirs must be 0700"
    nested = [p for p in drift.rglob("*") if p.is_dir() and p.parent != drift]
    assert nested and all((p.stat().st_mode & 0o777) == 0o755 for p in nested)
    files = [p for p in drift.rglob("*") if p.is_file()]
    assert files and all((p.stat().st_mode & 0o777) == 0o644 for p in files)
    v033 = home / ".hermes/private/harness-skill-backups/20261002T063137+0900/SKILL.md.v0.3.3"
    assert v033.is_file() and (v033.stat().st_mode & 0o777) == 0o600


test_rollback_runbook()

print("ok")
