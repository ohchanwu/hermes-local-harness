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
        "worker": {"outbox": "/private/outbox.sqlite3", "kanban_db": "/private/other.db", "plist_rendered": True, "loaded": True},
    }, ["default"])
assert errors == ["terminal notification runtime drift: producers and worker must share one outbox and canonical Kanban DB"]
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
