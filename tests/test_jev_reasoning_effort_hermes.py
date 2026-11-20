#!/usr/bin/env python3
"""The jev llm_request middleware through the real Hermes middleware (card t_caf5dba0).

Run from the repository root with the installed Hermes interpreter:

    /Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I tests/test_jev_reasoning_effort_hermes.py

Steps (procedures/isolated-hermes-test-home.md):
1. HOME, HERMES_HOME and TMPDIR point at a new temporary directory before any
   Hermes import; HERMES_DISABLE_LAZY_INSTALLS=true; the Kanban and profile
   variables of the calling session are removed.
2. A copy of plugins/jev of this repository is placed in
   <HERMES_HOME>/plugins/jev and enabled in <HERMES_HOME>/config.yaml
   (`plugins.enabled`), the documented way to install a user plugin. The real
   Hermes plugin discovery loads it and its register() adds the callback to the
   real middleware registry.
3. The card read is a test double: an executable `hermes` script in a
   temporary directory at the start of PATH prints the JSON of a synthetic
   card. No real board and no /Users/chanbla11mit/.hermes/kanban file is read.
4. The real hermes_cli.middleware.apply_llm_request_middleware is called with
   a GLM request whose reasoning fields come from the real `zai` provider
   profile, and with a claude-subscription request.

When Hermes cannot be imported (for example under /opt/homebrew/bin/python3),
it prints one line saying so and exits 0.
"""
import atexit
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HERMES_SOURCE = Path("/Users/chanbla11mit/.hermes/hermes-agent")
CLEAR_VARS = ("HERMES_PROFILE", "HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_HOME",
              "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_WORKSPACE",
              "HERMES_KANBAN_WORKSPACES_ROOT", "HERMES_SESSION_ID", "HERMES_JEV_LOG_DIR",
              "HERMES_CLAUDE_SUBSCRIPTION_EFFORT", "HERMES_SAFE_MODE")
CARDS = {"t_aaaa0001": "Repository x.\nReasoning effort EXACT xhigh.\n",
         "t_aaaa0002": "Repository x.\nReasoning effort EXACT high.\n",
         "t_aaaa0003": "Repository x.\nNo reasoning effort line.\n"}
FAKE_HERMES = """#!/bin/sh
# Test double of `hermes kanban --board <board> show <task> --json`.
echo "$*" >> "{log}"
if [ "$1 $2 $3 $4 $6" != "kanban --board harness show --json" ]; then exit 2; fi
case "$5" in
{cases}
  *) exit 1 ;;
esac
"""


def remove_quietly(path):
    shutil.rmtree(path, ignore_errors=True)


def hermes_importable():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(HERMES_SOURCE))
    try:
        import yaml  # noqa: F401
        import hermes_cli.middleware  # noqa: F401
        import hermes_cli.plugins  # noqa: F401
        import providers  # noqa: F401
    except Exception as exc:  # any import failure means this interpreter cannot run the test
        print(f"SKIP: Hermes is not importable with {sys.executable} ({type(exc).__name__}); "
              "run this file with /Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I")
        return False
    return True


def prepare(base):
    home = base / "home"
    home.mkdir()
    bin_dir = base / "bin"
    bin_dir.mkdir()
    log = base / "hermes-calls.log"
    cases = "\n".join(f"  {task}) printf '%s\\n' '{json.dumps({'task': {'id': task, 'body': body}})}' ;;"
                      for task, body in CARDS.items())
    fake = bin_dir / "hermes"
    fake.write_text(FAKE_HERMES.format(log=log, cases=cases), encoding="utf-8")
    fake.chmod(0o755)
    os.environ.update({"HOME": str(home), "HERMES_HOME": str(home), "TMPDIR": str(home),
                       "PATH": f"{bin_dir}:/usr/bin:/bin", "HERMES_DISABLE_LAZY_INSTALLS": "true"})
    for name in CLEAR_VARS:
        os.environ.pop(name, None)
    os.environ.update({"HERMES_PROFILE": "harness-worker", "HERMES_KANBAN_BOARD": "harness",
                       "HERMES_JEV_LOG_DIR": str(base / "jev-logs")})
    shutil.copytree(REPO_ROOT / "plugins" / "jev", home / "plugins" / "jev",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (home / "config.yaml").write_text("plugins:\n  enabled:\n    - jev\n", encoding="utf-8")
    return home, log


def block_network():
    def refused(*_args, **_kwargs):
        raise OSError("network access is blocked in this test")
    socket.socket = refused  # type: ignore[assignment]
    socket.create_connection = refused  # type: ignore[assignment]


def run(base):
    home, log = prepare(base)
    block_network()
    import hermes_constants
    from hermes_cli.middleware import apply_llm_request_middleware
    from hermes_cli.plugins import get_plugin_manager
    from providers import get_provider_profile

    failures = []

    def check(name, condition, facts):
        print(f"{'PASS' if condition else 'FAIL'} {name}: {facts}")
        if not condition:
            failures.append(name)

    check("isolated home", str(hermes_constants.get_hermes_home()) == str(home), str(home))
    zai = get_provider_profile("zai")
    extra_body, top_level = zai.build_api_kwargs_extras(
        reasoning_config={"enabled": True, "effort": "medium"}, model="glm-5.3")
    glm_request = {"model": "glm-5.3", "messages": [{"role": "user", "content": "synthetic"}],
                   **top_level, "extra_body": extra_body}
    check("zai profile request", glm_request.get("reasoning_effort") == "medium"
          and extra_body.get("thinking") == {"type": "enabled"}, json.dumps(glm_request, sort_keys=True))

    os.environ["HERMES_KANBAN_TASK"] = "t_aaaa0001"
    result = apply_llm_request_middleware(glm_request, task_id="session", provider="zai", model="glm-5.3",
                                          api_call_count=1)
    middleware = get_plugin_manager()._middleware.get("llm_request", [])
    check("jev callback registered by real plugin discovery",
          any(getattr(cb, "__module__", "").endswith("jev") for cb in middleware),
          [f"{getattr(cb, '__module__', '?')}.{getattr(cb, '__name__', '?')}" for cb in middleware])
    check("GLM xhigh applied as max", result.payload.get("reasoning_effort") == "max"
          and result.payload.get("extra_body") == {"thinking": {"type": "enabled"}}
          and {"source": "jev", "reason": "card reasoning effort"} in result.trace,
          f"reasoning_effort={result.payload.get('reasoning_effort')!r} trace={result.trace}")
    check("original request unchanged", glm_request.get("reasoning_effort") == "medium", "medium")

    os.environ["HERMES_KANBAN_TASK"] = "t_aaaa0002"
    claude_request = {"model": "claude-opus-5-5", "messages": [{"role": "user", "content": "synthetic"}],
                      "extra_body": {"subscription_session_id": "synthetic-session"}}
    result = apply_llm_request_middleware(claude_request, task_id="session", provider="claude-subscription",
                                          model="claude-opus-5-5", api_call_count=1)
    check("Claude card_reasoning_effort applied",
          result.payload.get("extra_body") == {"subscription_session_id": "synthetic-session",
                                               "card_reasoning_effort": "high"},
          f"extra_body={result.payload.get('extra_body')}")

    os.environ["HERMES_KANBAN_TASK"] = "t_aaaa0003"
    result = apply_llm_request_middleware(glm_request, task_id="session", provider="zai", model="glm-5.3",
                                          api_call_count=1)
    check("no card line: request unchanged", result.payload == glm_request and not any(
        entry.get("source") == "jev" for entry in result.trace), f"trace={result.trace}")

    os.environ["HERMES_PROFILE"] = "harness-reviewer"
    os.environ["HERMES_KANBAN_TASK"] = "t_aaaa0001"
    result = apply_llm_request_middleware(glm_request, task_id="session", provider="zai", model="glm-5.3",
                                          api_call_count=1)
    check("reviewer profile: request unchanged", result.payload == glm_request, f"trace={result.trace}")

    os.environ["HERMES_PROFILE"] = "harness-worker"
    apply_llm_request_middleware(glm_request, task_id="session", provider="zai", model="glm-5.3",
                                 api_call_count=2)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    check("one card read per task", sorted(calls) == sorted(
        f"kanban --board harness show {task} --json" for task in CARDS), calls)

    print("real Hermes middleware test ran: "
          f"{'all checks passed' if not failures else 'failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


def main():
    if not hermes_importable():
        return 0
    base = Path(tempfile.mkdtemp(prefix="jev-reasoning-effort-"))
    atexit.register(remove_quietly, base)
    try:
        return run(base)
    finally:
        remove_quietly(base)


if __name__ == "__main__":
    raise SystemExit(main())
