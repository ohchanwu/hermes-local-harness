#!/usr/bin/env python3
import importlib.util
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


# baseline: plugins plus shared runtime paths and the loaded worker pass.
check("--fixture", str(FIXTURES / "clean.yaml"))
# plugin enablement alone is insufficient: every producer must expose the shared
# absolute runtime paths and the rendered, loaded worker must match them.
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
        "shared_environment": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/kanban.db"},
        "worker": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/kanban.db", "plist_rendered": True, "loaded": True},
    }, ["default"])
assert errors == ["terminal notification runtime pending worker: loaded LaunchAgent arguments/environment do not match the shared paths"], errors
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_terminal_notification_runtime(errors, {
        "shared_environment": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/kanban.db"},
        "worker": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/other.db", "plist_rendered": True, "loaded": True, "loaded_state_matches": True},
    }, ["default"])
assert errors == ["terminal notification runtime drift: producers and worker must share one outbox and canonical Kanban DB"], errors

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


PS_ENV_SET = (f"/venv/bin/python -m hermes_cli.main gateway run --external-supervisor "
              f"HERMES_TERMINAL_OUTBOX={OUTBOX} HERMES_KANBAN_DB={KANBAN} PATH=/bin\n")
PS_ENV_MISSING = "/venv/bin/python -m hermes_cli.main gateway run --external-supervisor PATH=/bin\n"
LOADED_MATCHING = (f"gui/501/label = {{\n\tstate = running\n\n\targuments = {{\n\t\t/venv/bin/python\n\t\t/worker.py\n\t\t--db\n\t\t{OUTBOX}\n"
                   f"\t\t--kanban-db\n\t\t{KANBAN}\n\t}}\n\n\tenvironment = {{\n"
                   f"\t\tHERMES_TERMINAL_OUTBOX => {OUTBOX}\n\t\tHERMES_KANBAN_DB => {KANBAN}\n\t}}\n}}\n")
LOADED_MATCHING = LOADED_MATCHING.replace(
    f"\t\tHERMES_KANBAN_DB => {KANBAN}\n", f"\t\tHERMES_KANBAN_DB => {KANBAN}\n\t\tPATH => {WORKER_PATH}\n")
LOADED_STALE = (f"gui/501/label = {{\n\tstate = running\n\n\targuments = {{\n\t\t/venv/bin/python\n\t\t/worker.py\n\t\t--db\n\t\t/old/outbox.sqlite3\n"
                f"\t\t--kanban-db\n\t\t/old/kanban.db\n\t}}\n\n\tenvironment = {{\n"
                f"\t\tHERMES_TERMINAL_OUTBOX => /old/outbox.sqlite3\n\t\tHERMES_KANBAN_DB => /old/kanban.db\n\t}}\n}}\n")

# gateway present but env not inherited (restart skipped) stays red
errors, _ = live_errors(PS_ENV_MISSING, LOADED_MATCHING, PLIST_EXTRACTS)
assert any("running gateway has not inherited" in e for e in errors), errors
# rendered plist matches but the loaded job is stale stays red
errors, _ = live_errors(PS_ENV_SET, LOADED_STALE, PLIST_EXTRACTS)
assert any("loaded LaunchAgent arguments/environment do not match" in e for e in errors), errors
# fully rolled out (env inherited, plist rendered, loaded job effective state matches) passes
errors, runtime = live_errors(PS_ENV_SET, LOADED_MATCHING, PLIST_EXTRACTS)
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
assert "version: 0.4.0" in orchestrator
assert "Routing validation and dispatch receipt" in orchestrator
assert "Authentication expiry blocks a fresh observation" in orchestrator
assert "currently_actionable" in orchestrator
# Terminal retry remains an explicit card-scoped v2 policy, never the default.
assert "version: 0.4.0" in orchestrator
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
# Astra's three intentional local built-in overrides are declared rather than normalized into fleet drift.
check("--fixture", str(FIXTURES / "astra-local-override.yaml"))
local_overrides = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())["skill"]["profile_local_skill_overrides"]
errors = []
with redirect_stdout(io.StringIO()):
    verify_state.check_profile_local_skill_overrides(errors, local_overrides, local_overrides)
assert errors == [], errors
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

print("ok")
