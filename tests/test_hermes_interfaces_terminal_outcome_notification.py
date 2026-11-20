#!/usr/bin/env python3
"""Hermes interfaces that plugins/hermes-terminal-outcome-notification uses, checked against the
installed Hermes (docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, section 3.2,
change 6; card t_12d9630d).

Run from the repository root after every Hermes update:

    python3 tests/test_hermes_interfaces_terminal_outcome_notification.py

The installed Hermes runs in a new temporary HERMES_HOME that tests/hermes_isolated_home.py
provides; its child processes cannot open network sockets and no live state is read or written.
A copy of the plugin is placed in <HERMES_HOME>/plugins and enabled in <HERMES_HOME>/config.yaml.
The output has one line per dependency ID of section 1.2, starting with PASS or FAIL, and the exit
status is 1 when any line is FAIL. When the installed Hermes cannot be provided or imported, every
ID is FAIL: a missing dependency must not pass the check after an update.

N8 is not covered: change 3 (card t_955528ca) removed the plugin's use of it. N11 is not in the
list of section 3.2. N15 runs only `hermes send --help`; no message is sent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))
import hermes_isolated_home as hih  # noqa: E402

PLUGIN = "hermes-terminal-outcome-notification"
TOOLSET = "terminal_outcome_notifications"
TOOLS = ("arm_campaign", "campaign_terminal", "watch_terminal_task")
COMMANDS = ("notify-on-terminal", "watch-terminal-task")
HOOKS_BY_ID = {"N5": ("pre_llm_call", "post_llm_call"), "N6": ("on_session_end",),
               "N7": ("on_session_reset",), "N9": ("agent_loop_stopped",),
               "N10": ("kanban_task_claimed", "kanban_task_completed", "kanban_task_blocked")}
HOOKS = tuple(hook for hooks in HOOKS_BY_ID.values() for hook in hooks)
IDS = ("N1", "N2", "N3", "N4", "N5", "N6", "N7", "N9", "N10", "N12", "N13", "N14", "N15")
RESULT_MARKER = "TERMINAL_OUTCOME_INTERFACES:"
# A task ID with the Hermes format that the test board does not contain.
MISSING_TASK = "t_00000000"

# Plugin discovery, tool dispatch and the storage interface, in one process of the installed
# Hermes. Each fact is collected separately, so that one missing interface does not hide another.
_PROBE = hih._CHILD_GUARD + """
import json, sys
sys.path.insert(0, {root!r})
import hermes_bootstrap  # noqa: F401
from hermes_cli.plugins import VALID_HOOKS, get_plugin_commands, get_plugin_manager, has_hook

facts = {{}}

def fact(name, read):
    try:
        facts[name] = read()
    except Exception as exc:  # the parent reports the failure under the dependency ID
        facts[name] = {{"error": f"{{type(exc).__name__}}: {{exc}}"}}

def plugin_entry():
    manager = get_plugin_manager()
    manager.discover_and_load()
    return next((p for p in manager.list_plugins() if p["name"] == {plugin!r}), None)

def tools():
    from tools.registry import registry
    return {{name: getattr(registry.get_entry(name), "toolset", None) for name in {tools!r}}}

def commands():
    return {{name: {{"plugin": entry.get("plugin"), "callable": callable(entry.get("handler"))}}
            for name, entry in get_plugin_commands().items()}}

def dispatch(**kwargs):
    from tools.registry import registry
    result = registry.dispatch("arm_campaign", {{}}, **kwargs)
    return json.loads(result) if isinstance(result, str) else result

def gateway_sessions():
    from persistence_assembly import open_persistence, open_persistence_reader, profile_scope
    from persistence.conversation.sessions import NewSession
    with open_persistence(profile_scope()) as store:
        store.sessions.create(NewSession(session_id="n12-open", source="telegram", session_key="n12-key-open"))
        store.sessions.create(NewSession(session_id="n12-ended", source="telegram", session_key="n12-key-ended"))
        store.sessions.end("n12-ended", "test")
    with open_persistence_reader(profile_scope().profile_dir) as store:
        return [[entry.session.session_key, entry.session.session_id]
                for entry in store.sessions.list_gateway_sessions(active_only=True)]

fact("plugin", plugin_entry)
fact("valid_hooks", lambda: [hook for hook in {hooks!r} if hook in VALID_HOOKS])
fact("registered_hooks", lambda: [hook for hook in {hooks!r} if has_hook(hook)])
fact("tools", tools)
fact("commands", commands)
fact("dispatch_with_session_id", lambda: dispatch(session_id="n3-session"))
fact("dispatch_without_session_id", dispatch)
fact("gateway_sessions", gateway_sessions)
print({marker!r} + json.dumps(facts))
"""

# One `hermes` command of the installed Hermes; the arguments follow the script path.
_COMMAND = hih._CHILD_GUARD + """
import sys
sys.path.insert(0, {root!r})
import hermes_bootstrap  # noqa: F401
import hermes_cli.main
sys.argv = ["hermes"] + sys.argv[1:]
try:
    rc = hermes_cli.main.main()
except SystemExit as exc:
    rc = exc.code
sys.exit(0 if rc in (0, None) else rc if isinstance(rc, int) else 1)
"""


def one_line(text: str, limit: int = 400) -> str:
    return " ".join(str(text).split())[-limit:]


def run_probe(iso: hih.IsolatedHome) -> dict:
    shutil.copytree(REPO_ROOT / "plugins" / PLUGIN, iso.home / "plugins" / PLUGIN,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (iso.home / "config.yaml").write_text(f"plugins:\n  enabled:\n    - {PLUGIN}\n", encoding="utf-8")
    script = iso.home / "probe.py"
    script.write_text(_PROBE.format(root=str(iso.checkout_root), plugin=PLUGIN, tools=TOOLS, hooks=HOOKS,
                                    marker=RESULT_MARKER), encoding="utf-8")
    # The plugin tools write to this outbox; it stays inside the isolated home.
    env = dict(iso.env, HERMES_TERMINAL_OUTBOX=str(iso.home / "outbox.db"))
    proc = subprocess.run(iso.child_command(script), env=env, capture_output=True, text=True,
                          timeout=180, check=False)
    lines = [line for line in proc.stdout.splitlines() if line.startswith(RESULT_MARKER)]
    if proc.returncode != 0 or not lines:
        raise RuntimeError(f"probe process exit {proc.returncode}: {one_line(proc.stderr or proc.stdout)}")
    return json.loads(lines[-1][len(RESULT_MARKER):])


def hermes_command(iso: hih.IsolatedHome, env: dict, *args: str) -> subprocess.CompletedProcess:
    script = iso.home / "hermes_command.py"
    if not script.exists():
        script.write_text(_COMMAND.format(root=str(iso.checkout_root)), encoding="utf-8")
    return subprocess.run(iso.child_command(script) + list(args), env=env, capture_output=True,
                          text=True, timeout=180, check=False)


def shown(proc: subprocess.CompletedProcess) -> dict:
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}: {one_line(proc.stderr)}")
    return json.loads(proc.stdout)


def check_probe(facts: dict, report) -> None:
    plugin = facts.get("plugin") or {}
    report("N1", isinstance(plugin, dict) and plugin.get("enabled") is True and plugin.get("error") is None,
           f"plugin loaded by discovery from {plugin.get('source')!r}: {json.dumps(plugin, sort_keys=True)}")
    tools = facts.get("tools")
    report("N2", tools == {name: TOOLSET for name in TOOLS} and plugin.get("tools") == len(TOOLS),
           f"tool toolsets {json.dumps(tools, sort_keys=True)}; plugin tool count {plugin.get('tools')}")
    with_id, without_id = facts.get("dispatch_with_session_id"), facts.get("dispatch_without_session_id")
    report("N3", isinstance(with_id, dict) and with_id.get("success") is True
           and isinstance(without_id, dict) and without_id.get("success") is False,
           f"registry.dispatch('arm_campaign', session_id=...) -> {json.dumps(with_id)}; "
           f"without session_id -> {json.dumps(without_id)}")
    commands = facts.get("commands")
    expected_commands = {name: {"plugin": PLUGIN, "callable": True} for name in COMMANDS}
    report("N4", isinstance(commands, dict) and all(commands.get(n) == v for n, v in expected_commands.items())
           and plugin.get("commands") == len(COMMANDS),
           f"plugin commands {json.dumps({n: (commands or {}).get(n) for n in COMMANDS}, sort_keys=True)}; "
           f"plugin command count {plugin.get('commands')}")
    valid, registered = facts.get("valid_hooks"), facts.get("registered_hooks")
    for dependency, hooks in HOOKS_BY_ID.items():
        report(dependency, isinstance(valid, list) and isinstance(registered, list)
               and all(h in valid and h in registered for h in hooks) and plugin.get("hooks") == len(HOOKS),
               f"{', '.join(hooks)}: in VALID_HOOKS {[h for h in hooks if h in (valid or [])]}, "
               f"registered {[h for h in hooks if h in (registered or [])]}; plugin hook count {plugin.get('hooks')}")
    sessions = facts.get("gateway_sessions")
    report("N12", isinstance(sessions, list) and ["n12-key-open", "n12-open"] in sessions
           and not any(row[1] == "n12-ended" for row in sessions),
           f"list_gateway_sessions(active_only=True) -> [session_key, session_id] {json.dumps(sessions)} "
           "(open row n12-open expected, ended row n12-ended not expected)")


def check_board(iso: hih.IsolatedHome, report) -> None:
    board = iso.home / "board" / "kanban.db"
    env = dict(iso.env, HERMES_KANBAN_DB=str(board))
    try:
        task_id = shown(hermes_command(iso, env, "kanban", "create", "N14 test card",
                                       "--assignee", "test-worker", "--json"))["id"]
        claimed = hermes_command(iso, env, "kanban", "claim", task_id)
        running = shown(hermes_command(iso, env, "kanban", "show", task_id, "--json"))
        blocked_cmd = hermes_command(iso, env, "kanban", "block", task_id, "waiting", "--kind", "needs_input")
        blocked = shown(hermes_command(iso, env, "kanban", "show", task_id, "--json"))
        missing = hermes_command(iso, env, "kanban", "show", MISSING_TASK, "--json")
    except (RuntimeError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        report("N13", False, f"hermes kanban with HERMES_KANBAN_DB set failed: {type(exc).__name__}: {exc}")
        report("N14", False, "board not readable; see N13")
        return
    report("N13", board.is_file() and claimed.returncode == 0 and blocked_cmd.returncode == 0,
           f"board file at HERMES_KANBAN_DB exists: {board.is_file()}; claim exit {claimed.returncode}; "
           f"block exit {blocked_cmd.returncode}")
    # The fields that kanban_state in plugins/hermes-terminal-outcome-notification/worker.py reads.
    try:
        open_runs = [run["id"] for run in running["runs"] if run["ended_at"] is None]
        task = blocked["task"]
        block = next(event["payload"] for event in reversed(blocked["events"])
                     if event["kind"] in ("blocked", "block_loop_detected"))
        runs = {run["id"]: run["ended_at"] for run in blocked["runs"]}
        facts = {"open runs after claim": open_runs, "status": task["status"],
                 "last_failure_error present": "last_failure_error" in task,
                 "block kind": block.get("kind"), "block recurrences": block.get("recurrences"),
                 "runs after block (id: ended_at)": runs,
                 "missing task": [missing.returncode, missing.stderr.strip()]}
        ok = (len(open_runs) == 1 and task["status"] == "blocked" and "last_failure_error" in task
              and block.get("kind") == "needs_input" and block.get("recurrences") == 1
              and runs.get(open_runs[0]) is not None and max(runs) == open_runs[0]
              and missing.returncode != 0 and missing.stderr.strip() == f"no such task: {MISSING_TASK}")
    except (KeyError, TypeError, StopIteration, ValueError, IndexError) as exc:
        facts, ok = {"error": f"{type(exc).__name__}: {exc}"}, False
    report("N14", ok, f"hermes kanban show --json: {json.dumps(facts, sort_keys=True)}")


def check_send_help(iso: hih.IsolatedHome, report) -> None:
    proc = hermes_command(iso, iso.env, "send", "--help")
    report("N15", proc.returncode == 0 and "--to" in proc.stdout and "--quiet" in proc.stdout,
           f"hermes send --help exit {proc.returncode}; lists --to: {'--to' in proc.stdout}; "
           f"lists --quiet: {'--quiet' in proc.stdout}")


def main() -> int:
    results: dict[str, bool] = {}

    def report(dependency: str, ok: bool, facts: str) -> None:
        results[dependency] = bool(ok)
        print(f"{'PASS' if ok else 'FAIL'} {dependency}: {facts}", flush=True)

    try:
        with hih.isolated_hermes_home() as iso:
            print(f"installed Hermes {hih.installed_hermes_version(iso.checkout_root)} at {iso.checkout_root}",
                  flush=True)
            try:
                check_probe(run_probe(iso), report)
            except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                for dependency in ("N1", "N2", "N3", "N4", *HOOKS_BY_ID, "N12"):
                    report(dependency, False, f"installed Hermes did not run the plugin probe: {exc}")
            check_board(iso, report)
            check_send_help(iso, report)
    except hih.IsolatedHomeError as exc:
        for dependency in IDS:
            if dependency not in results:
                report(dependency, False, f"installed Hermes not available in an isolated home: {exc}")
    print("NOT COVERED N8: hook on_session_reset field session_key; change 3 (card t_955528ca) "
          "removed the plugin's use of it")
    failed = [dependency for dependency in IDS if not results.get(dependency)]
    print(f"FAILED: {', '.join(failed)}" if failed else f"OK: {len(IDS)} dependencies checked")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
