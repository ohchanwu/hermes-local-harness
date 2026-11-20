#!/usr/bin/env python3
"""The Hermes interfaces that the jev plugin uses, checked against the installed Hermes.

Decision record docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, section 3.1 (change 5).
Run from the repository root with any python3:

    python3 tests/test_hermes_interfaces_jev.py

The file runs in three roles. As the parent it takes the isolated HERMES_HOME, the minimal environment
and the interpreter of the installed Hermes from isolated_hermes_home() of tests/hermes_isolated_home.py,
and runs itself with that interpreter and the argument --child. The child copies plugins/jev into
$HERMES_HOME/plugins/jev, enables it in $HERMES_HOME/config.yaml, loads it through Hermes plugin
discovery, creates a board and cards in the isolated home with the documented `hermes kanban` command
line, and checks J1, J2, J3, J5, J7, J14 to J19, J21, J22 and J23. Each `hermes kanban` command runs as
its own process: this file with the argument --hermes, which calls hermes_cli.main.main() of the
installed Hermes. The parent prints one line per dependency ID with PASS or FAIL, prints a FAIL line for
every ID the child did not report (for example when the installed Hermes cannot be imported), and exits
1 on any FAIL. J6, J8 and two fields of J16 are not covered and are reported as such.

No model inference, no network (the child and every `hermes` process refuse every socket other than
AF_UNIX), no live board database and no live profile: HOME, HERMES_HOME and TMPDIR all point into the
isolated home.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugins" / "jev"
IDS = ("J1", "J2", "J3", "J5", "J7", "J14", "J15", "J16", "J17", "J18", "J19", "J21", "J22", "J23")
NOT_COVERED = {
    "J6": "result fields of the terminal, execute_code, search_files and browser_exec tools; needs a real "
          "tool run",
    "J8": "key names inside usage of post_auxiliary_call; needs a real auxiliary model call",
    "J16 blocked.source_status": "needs a review run by a dispatcher-started worker",
    "J16 changes_requested.reviewer": "needs a review run by a dispatcher-started worker",
}
BOARD = "jev-interfaces"
# The six Kanban tools of row J20.
J20_TOOLS = ("kanban_create", "kanban_unblock", "kanban_request_review", "kanban_request_changes",
             "kanban_complete", "kanban_block")


def block_network():
    import socket

    class UnixOnlySocket(socket.socket):  # a subclass, because ssl and asyncio subclass socket.socket
        def __init__(self, family=socket.AF_INET, *args, **kwargs):
            if family != socket.AF_UNIX:
                raise AssertionError(f"network access attempted (family={family!r})")
            super().__init__(family, *args, **kwargs)
    socket.socket = UnixOnlySocket


def hermes_command():
    """The documented `hermes` command line of the installed Hermes, run in this process."""
    block_network()
    checkout = os.environ["JEV_INTERFACES_CHECKOUT"]
    sys.dont_write_bytecode = True
    sys.path.insert(0, checkout)
    import hermes_bootstrap  # noqa: F401  same import order as the helper's import exercise
    import hermes_cli.main
    sys.argv = ["hermes", *sys.argv[2:]]
    try:
        code = hermes_cli.main.main()
    except SystemExit as exc:
        code = exc.code
    return 0 if code in (0, None) else (code if isinstance(code, int) else 1)


def child():
    """Checks the J IDs inside the isolated home with the interpreter of the installed Hermes."""
    block_network()
    import shutil
    checkout = Path(sys.argv[2])
    home = Path(os.environ["HERMES_HOME"])
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(checkout))
    shutil.copytree(PLUGIN, home / "plugins" / "jev", ignore=shutil.ignore_patterns("__pycache__"))
    (home / "config.yaml").write_text("plugins:\n  enabled:\n    - jev\n", encoding="utf-8")
    env = {**os.environ, "JEV_INTERFACES_CHECKOUT": str(checkout)}

    def report(dep, ok, facts):
        print(f"{'PASS' if ok else 'FAIL'} {dep}: {facts}", flush=True)

    def run(dep, check):
        try:
            ok, facts = check()
        except Exception as exc:  # any error is a FAIL of this one ID; the others still run
            ok, facts = False, f"{type(exc).__name__}: {exc}"
        report(dep, ok, facts)

    def hermes(*args):
        result = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--hermes", *args],
                                env=env, cwd=str(home), capture_output=True, text=True, timeout=180,
                                check=False)
        return result.returncode, result.stdout, result.stderr.strip()[-500:]

    import hermes_bootstrap  # noqa: F401  same import order as the helper's import exercise
    from hermes_cli import plugins as hermes_plugins

    manager = hermes_plugins.get_plugin_manager()
    manager.discover_and_load()
    loaded = manager._plugins.get("jev")

    def from_jev(callbacks):
        return [c for c in callbacks if getattr(c, "__module__", "").split(".")[-1] == "jev"]

    def registered(registry, kind, hook):
        jev_callbacks = from_jev(registry.get(kind, []))
        valid = kind in hermes_plugins.VALID_HOOKS if hook else True
        names = [c.__name__ for c in jev_callbacks]
        return (bool(jev_callbacks) and valid,
                f"jev callbacks {names}" + (f"; in VALID_HOOKS={valid}" if hook else ""))

    def j1():
        error = getattr(loaded, "error", None) if loaded is not None else "not discovered"
        return (loaded is not None and not error,
                f"plugin jev discovered from {home / 'plugins' / 'jev'}; error={error!r}")

    checks = {
        "J1": j1,
        "J2": lambda: registered(manager._middleware, "tool_execution", hook=False),
        "J3": lambda: registered(manager._middleware, "llm_request", hook=False),
        "J5": lambda: registered(manager._hooks, "transform_tool_result", hook=True),
        "J7": lambda: registered(manager._hooks, "post_auxiliary_call", hook=True),
    }
    for dep, check in checks.items():
        run(dep, check)

    # J17, J18, J19: the documented command line in the isolated home; each command must exit 0.
    exits = {}

    def step(label, *args):
        code, out, err = hermes("kanban", "--board", BOARD, *args)
        exits[label] = (code, err)
        return out

    code, _, err = hermes("kanban", "boards", "create", BOARD)
    exits["boards create"] = (code, err)
    created = step("create", "create", "jev interfaces card", "--body", "first body",
                   "--assignee", "worker-one", "--json")
    match = re.search(r'"id":\s*"([^"]+)"', created)
    task = match.group(1) if match else ""
    step("assign", "assign", task, "worker-two")
    step("set-model none", "set-model", task, "none")
    step("edit --body=", "edit", task, "--body=second body")
    step("schedule", "schedule", task, "jev interfaces hold")
    listed = step("list --status scheduled", "list", "--status", "scheduled", "--json")
    step("unblock", "unblock", task)
    step("claim", "claim", task)
    step("reassign --reclaim", "reassign", task, "worker-three", "--reclaim")
    step("block --kind needs_input", "block", task, "jev interfaces question", "--kind", "needs_input")
    shown = step("show --json", "show", task, "--json")

    def exited_zero(*labels):
        bad = {label: exits[label] for label in labels if exits[label][0] != 0}
        return not bad and bool(task), f"exit 0 for {list(labels)}; non-zero: {bad}; task {task!r}"

    try:
        card = json.loads(shown)
    except ValueError:
        card = {}
    events = card.get("events") or []
    runs = card.get("runs") or []

    def payloads(kind):
        return [e.get("payload") for e in events if e.get("kind") == kind and isinstance(e.get("payload"), dict)]

    def j14():
        task_fields = card.get("task") or {}
        missing = [f"task.{name}" for name in ("status", "assignee", "body") if name not in task_fields]
        missing += [f"events[].{name}" for name in ("kind", "payload", "run_id")
                    if not events or any(name not in e for e in events)]
        missing += [f"runs[].{name}" for name in ("profile", "started_at")
                    if not runs or any(name not in r for r in runs)]
        try:
            scheduled = [t.get("id") for t in json.loads(listed)]
        except (ValueError, AttributeError):
            scheduled = []
        ok = (not missing and task in scheduled and task_fields.get("status") == "blocked"
              and task_fields.get("assignee") == "worker-three" and task_fields.get("body") == "second body"
              and "worker-two" in [r.get("profile") for r in runs])
        return ok, (f"missing {missing}; task status={task_fields.get('status')!r} "
                    f"assignee={task_fields.get('assignee')!r} body={task_fields.get('body')!r}; "
                    f"runs profile={[r.get('profile') for r in runs]}; "
                    f"list --status scheduled listed the card={task in scheduled}")

    def j15():
        kinds = [p.get("kind") for p in payloads("blocked")]
        reasons = [p.get("reason") for p in payloads("blocked")]
        return "needs_input" in kinds and any(reasons), f"blocked payload kind={kinds} reason={reasons}"

    def j16():
        reasons = [p.get("reason") for p in payloads("scheduled")]
        return (any(r and "jev interfaces hold" in r for r in reasons),
                f"scheduled payload reason={reasons} (blocked.source_status and changes_requested.reviewer: "
                "not covered)")

    run("J14", j14)
    run("J15", j15)
    run("J16", j16)
    run("J17", lambda: exited_zero("boards create", "create", "assign", "set-model none", "edit --body=",
                                   "unblock", "show --json", "list --status scheduled", "block --kind needs_input"))
    run("J18", lambda: exited_zero("schedule"))
    run("J19", lambda: exited_zero("claim", "reassign --reclaim"))

    import tools.kanban_tools  # noqa: F401  registers the Kanban tools
    from tools.registry import registry
    jev = sys.modules[from_jev(manager._middleware.get("tool_execution", []))[0].__module__]

    def j21():
        absent = {}
        for tool in J20_TOOLS:
            schema = registry.get_schema(tool) or {}
            properties = (schema.get("parameters") or {}).get("properties") or {}
            names = jev.KANBAN_TOOL_ARGUMENTS.get(tool, ())
            if not names or any(n not in properties for n in names):
                absent[tool] = [n for n in names if n not in properties] or "jev lists no argument names"
        return not absent, f"argument names of jev.KANBAN_TOOL_ARGUMENTS absent from the schemas: {absent}"

    result = {}

    def j22():
        raw = registry.dispatch("kanban_create", {"title": "jev interfaces tool card", "body": "tool body",
                                                  "assignee": "worker-one", "board": BOARD})
        result.update(json.loads(raw) if isinstance(raw, str) else raw)
        failure = registry.dispatch("kanban_create", {"title": "no assignee", "board": BOARD})
        failure = json.loads(failure) if isinstance(failure, str) else failure
        ok = result.get("ok") is True and "task_id" in result and "status" in result and "error" in failure
        return ok, (f"success keys {sorted(result)}; failure keys {sorted(failure)}")

    def j23():
        pattern = jev.routing._HERMES_TASK_ID
        ids = [i for i in (task, result.get("task_id")) if i]
        return (len(ids) == 2 and all(pattern.fullmatch(i) for i in ids),
                f"task IDs {ids} against jev routing pattern {pattern.pattern!r}")

    run("J21", j21)
    run("J22", j22)
    run("J23", j23)
    return 0


def parent():
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from hermes_isolated_home import IsolatedHomeError, isolated_hermes_home
    lines, returncode, problem = [], None, None
    try:
        with isolated_hermes_home() as iso:
            command = iso.child_command(Path(__file__).resolve()) + ["--child", str(iso.checkout_root)]
            result = subprocess.run(command, env=iso.env, capture_output=True, text=True, timeout=1200,
                                    check=False, cwd=str(iso.home))
            lines, returncode = result.stdout.splitlines(), result.returncode
            if returncode != 0:
                problem = f"child exited {returncode}: {result.stderr.strip()[-1500:]}"
    except (IsolatedHomeError, OSError, subprocess.SubprocessError) as exc:
        problem = f"installed Hermes not available: {type(exc).__name__}: {exc}"
    reported = {}
    for line in lines:
        status, _, rest = line.partition(" ")
        dep = rest.split(":", 1)[0]
        if status in ("PASS", "FAIL") and dep in IDS:
            reported[dep] = status
            print(line)
    for dep in IDS:
        if dep not in reported:
            reported[dep] = "FAIL"
            print(f"FAIL {dep}: no result for this ID from the installed Hermes")
    for dep, reason in NOT_COVERED.items():
        print(f"NOT COVERED {dep}: {reason} (decision record section 3.1)")
    failed = sorted((d for d, s in reported.items() if s == "FAIL"), key=IDS.index)
    if problem:
        print(f"FAIL child: {problem}")
        failed = failed or ["child"]
    print(f"{'FAILED' if failed else 'OK'}: {len(IDS) - len(failed)} of {len(IDS)} dependencies passed")
    return 1 if failed else 0


if __name__ == "__main__":
    role = sys.argv[1:2]
    raise SystemExit(child() if role == ["--child"] else hermes_command() if role == ["--hermes"] else parent())
