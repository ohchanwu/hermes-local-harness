#!/usr/bin/env python3
import importlib.util
import io
from importlib.machinery import SourceFileLoader
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-state"
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
PLIST_EXTRACTS = {"EnvironmentVariables.HERMES_TERMINAL_OUTBOX": OUTBOX,
                  "EnvironmentVariables.HERMES_KANBAN_DB": KANBAN,
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
# enabled Ponytail on an implementation profile fails with its own diagnostic
check("--fixture", str(FIXTURES / "ponytail-enabled-drift.yaml"), code=1, text="must be disabled")
# absent required-disabled Ponytail fails with its own diagnostic
check("--fixture", str(FIXTURES / "ponytail-absent-drift.yaml"), code=1, text="required-disabled ponytail absent")
# a missing per-profile deployed copy fails (dormant profile included)
check("--fixture", str(FIXTURES / "skill-deployment-missing.yaml"), code=1, text="deployed skill copy missing")
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

print("ok")
