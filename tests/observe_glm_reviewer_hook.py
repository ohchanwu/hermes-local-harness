#!/usr/bin/env python3
"""Observation program: the pre_tool_call shell hook guard for a GLM reviewer.

Card t_85d4fbda (part 6 of card C3). This program makes no live change: it
creates a temporary directory, points HERMES_HOME at it before any Hermes
module is imported, writes a config.yaml with one pre_tool_call shell hook
(the script scripts/jev-glm-reviewer-hook of this repository) and no plugins,
and observes the Hermes code that registers and fires the hook. It deletes
the temporary directory on every exit: a finally block in main() removes it
on success, on the early return and on an exception, and an atexit handler
registered before the first Hermes import removes again, after the atexit
handlers that the Hermes imports register, whatever they create once more
under HERMES_HOME at interpreter exit.

It exits 0 when every expected case of a to d holds, otherwise 1. Case e is
printed and reported; it does not affect the exit status.

Run it from the repository root with the interpreter of the installed Hermes
environment, which installed_hermes_python() of tests/hermes_isolated_home.py
returns (tests/test_jev_glm_reviewer_hook.py does this):

    <interpreter> -I tests/observe_glm_reviewer_hook.py
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "jev-glm-reviewer-hook"

# Variables of a worker or gateway session must not reach the observation: the
# dispatcher's environment decides registration and tool routing. HERMES_HOME
# is set to the temporary directory below, never cleared.
_CLEAR_VARS = (
    "HERMES_PROFILE", "HERMES_ACCEPT_HOOKS",
    "HERMES_KANBAN_DB",
    "HERMES_KANBAN_BOARD", "HERMES_KANBAN_HOME", "HERMES_KANBAN_TASK",
    "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_WORKSPACE", "HERMES_KANBAN_WORKSPACES_ROOT",
    "HERMES_KANBAN_UNBLOCK", "HERMES_SESSION_ID", "HERMES_SESSION_SOURCE",
    "HERMES_DELEGATED_CHILD_CONTEXT",
)

_failures = []


def observed(case, expected, facts):
    """Print one OBSERVED line; collect the cases whose expectation failed."""
    held = expected
    print(f"OBSERVED {case}: {'holds' if held else 'FAILS'}, {facts}")
    if not held:
        _failures.append(case)


def remove_quietly(path):
    """Remove path; print a line when it cannot be removed (never raise)."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"cannot remove temporary directory {path}: {exc}")


def main():
    base = Path(tempfile.mkdtemp(prefix="glm-reviewer-hook-"))
    home = base / "home"
    home.mkdir()
    # Registered now, before any Hermes import, so it runs after the atexit
    # handlers that the Hermes imports register: atexit runs handlers in
    # reverse order of registration. It removes again whatever the Hermes
    # handlers create under HERMES_HOME once more at interpreter exit.
    atexit.register(remove_quietly, base)
    # 1. An empty environment, HERMES_HOME inside the temporary directory,
    #    before any Hermes import.
    os.environ.update({
        "HOME": str(home), "HERMES_HOME": str(home), "TMPDIR": str(home),
        "PATH": "/usr/bin:/bin",
        "HERMES_DISABLE_LAZY_INSTALLS": "true",
    })
    for var in _CLEAR_VARS:
        os.environ.pop(var, None)
    if not SCRIPT.is_file():
        print(f"script missing: {SCRIPT}")
        return 1
    try:
        return observe(base, home)
    finally:
        remove_quietly(base)


def observe(base, home):
    # No bytecode cache may be written into the installed Hermes tree this
    # program imports read only (the same rule as spikes/glm-reviewer-pass).
    sys.dont_write_bytecode = True
    sys.path.insert(0, "/Users/chanbla11mit/.hermes/hermes-agent")

    import yaml  # noqa: F401  (std-lib yaml is part of the Hermes venv)
    import hermes_constants
    import agent.shell_hooks as shell_hooks
    import hermes_cli.kanban_db_dispatch as dispatch
    import model_tools
    from hermes_cli.plugins import get_plugin_manager

    assert str(hermes_constants.get_hermes_home()) == str(home)
    print(f"temporary Hermes home: {home}")
    print(f"Hermes source: /Users/chanbla11mit/.hermes/hermes-agent")

    # 2. config.yaml with the hook of item 1 and no plugins.
    config_path = home / "config.yaml"
    config_path.write_text(
        "hooks:\n"
        "  pre_tool_call:\n"
        f"    - matcher: \"kanban_complete|kanban_request_review\"\n"
        f"      command: \"{SCRIPT}\"\n"
        "      timeout: 10\n"
        "      fail_closed: true\n"
        "platform_toolsets:\n"
        "  cli:\n"
        "    - hermes-cli\n",
        encoding="utf-8",
    )
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # a. Registration.
    shell_hooks.reset_for_tests()
    registered = shell_hooks.register_from_config(cfg, accept_hooks=True)
    allowlist_path = shell_hooks.allowlist_path()
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8-sig"))
    a1 = (len(registered) == 1 and registered[0].event == "pre_tool_call"
          and registered[0].matcher == "kanban_complete|kanban_request_review"
          and registered[0].fail_closed is True)
    entry = shell_hooks.allowlist_entry_for("pre_tool_call", str(SCRIPT))
    a2 = entry is not None and entry.get("event") == "pre_tool_call" and entry.get("command") == str(SCRIPT)
    observed("a1 register_from_config(cfg, accept_hooks=True) registers one pre_tool_call hook for the script",
             a1, f"registered={len(registered)}, matcher={registered[0].matcher if registered else None}, "
                 f"fail_closed={registered[0].fail_closed if registered else None}, "
                 f"spec=agent/shell_hooks.py ShellHookSpec (lines 127 to 136), "
                 f"registered by agent/shell_hooks.py lines 141 to 176")
    observed("a2 the temporary shell-hooks-allowlist.json records the (event, command) pair",
             a2, f"allowlist={allowlist_path}, approvals={len(allowlist.get('approvals', []))}, "
                 f"recorded by agent/shell_hooks.py _prompt_and_record lines 572 to 592 with "
                 f"_record_approval lines 595 to 598, written by save_allowlist lines 535 to 543")

    shell_hooks.reset_for_tests()
    allowlist_path.unlink()
    stdin_tty = sys.stdin.isatty()
    hooks_auto_accept = cfg.get("hooks_auto_accept", False)
    registered_off = shell_hooks.register_from_config(cfg, accept_hooks=False)
    a3 = (registered_off == [] and not stdin_tty and not hooks_auto_accept)
    observed("a3 with accept_hooks=False, no TTY and no hooks_auto_accept, nothing is registered",
             a3, f"registered={len(registered_off)}, stdin is a TTY={stdin_tty}, "
                 f"hooks_auto_accept={hooks_auto_accept}, decision by agent/shell_hooks.py "
                 f"_resolve_effective_accept lines 622 to 627 and _prompt_and_record lines 572 to 579 "
                 f"(sys.stdin.isatty() is False at line 578, so the answer is no without a prompt)")

    # b. Through the Hermes tool call path.
    def drop_pre_tool_call_hooks():
        """Remove every registered pre_tool_call callback (shell_hooks.reset_for_tests()
        clears only the idempotence set of agent/shell_hooks.py lines 203 to 206; the
        callbacks that register_from_config appended to the manager's _hooks list at
        lines 168 to 173 stay live without this)."""
        get_plugin_manager()._hooks.pop("pre_tool_call", None)

    shell_hooks.reset_for_tests()
    drop_pre_tool_call_hooks()
    shell_hooks.register_from_config(cfg, accept_hooks=True)
    manager = get_plugin_manager()
    manager.discover_and_load()
    plugin_names = sorted(p["name"] for p in manager.list_plugins())
    jev_absent = not any("jev" in name for name in plugin_names)
    observed("b0 the jev plugin is not loaded in this process (the temporary home has no plugins directory)",
             jev_absent, f"plugins={plugin_names}, user plugin source directory is "
                         f"get_hermes_home()/'plugins' (hermes_cli/plugins_discovery.py line 209)")

    def call(name, args):
        return json.loads(model_tools.handle_function_call(name, args, session_id="observe"))

    result = call("kanban_complete", {"summary": "observation"})
    b1 = (isinstance(result, dict) and isinstance(result.get("error"), str)
          and "A GLM reviewer may not call" in result["error"])
    observed("b1 kanban_complete through model_tools.handle_function_call is blocked with the script's message",
             b1, f"result={json.dumps(result)[:300]}, tool handler not run, "
                 f"blocked by agent/shell_hooks.py _evaluate_result lines 417 to 423 (exit status 2, "
                 f"BLOCK_EXIT_CODE at line 42), returned as tool_error with error type plugin_block by "
                 f"model_tools.py _pre_dispatch_guards lines 779 to 791")

    result = call("kanban_request_review", {"summary": "observation"})
    b2 = (isinstance(result, dict) and isinstance(result.get("error"), str)
          and "A GLM reviewer may not call" in result["error"])
    observed("b2 kanban_request_review through the same path is blocked with the script's message",
             b2, f"result={json.dumps(result)[:300]}, "
                 f"matched by the matcher of agent/shell_hooks.py matches_tool lines 117 to 124 "
                 f"(re.fullmatch, kanban_complete|kanban_request_review)")

    result = call("kanban_block", {"reason": "jev-glm-review-pass observation"})
    b3 = isinstance(result, dict) and "error" in result and "A GLM reviewer may not call" not in result.get("error", "")
    observed("b3 kanban_block is not blocked by the hook (the tool cannot reach a board: every HERMES_KANBAN_* "
             "variable is unset, so the handler refuses before any database use)",
             b3, f"result={json.dumps(result)[:300]}, "
                 f"hook returned None for this tool name (agent/shell_hooks.py _make_callback lines 368 to 377, "
                 f"matches_tool line 372)")

    result = call("read_file", {"path": str(config_path)})
    b4 = (isinstance(result, dict) and not result.get("error")
          and "A GLM reviewer may not call" not in json.dumps(result)
          and isinstance(result.get("content"), str))
    observed("b4 read_file is not blocked by the hook (the call succeeds and reads the temporary config.yaml)",
             b4, f"result keys={sorted(result) if isinstance(result, dict) else type(result).__name__}, "
                 f"content_length={len(result.get('content', '')) if isinstance(result, dict) else 0}")

    # c. fail_closed with a command path that does not exist.
    missing = home / "does-not-exist-hook"
    cfg_missing = {
        "hooks": {"pre_tool_call": [{
            "matcher": "kanban_complete|kanban_request_review",
            "command": str(missing), "timeout": 10, "fail_closed": True}]},
        "platform_toolsets": {"cli": ["hermes-cli"]},
    }
    shell_hooks.reset_for_tests()
    drop_pre_tool_call_hooks()
    shell_hooks.register_from_config(cfg_missing, accept_hooks=True)
    result = call("kanban_complete", {"summary": "observation"})
    c1 = (isinstance(result, dict) and isinstance(result.get("error"), str)
          and result["error"].startswith(f"hook {missing} failed closed:"))
    observed("c1 with fail_closed true and a command path that does not exist, kanban_complete is blocked",
             c1, f"result={json.dumps(result)[:300]}, spawn error of agent/shell_hooks.py _spawn lines 313 to 365 "
                 f"(command not found), block of _evaluate_result lines 406 to 413 through "
                 f"_fail_closed_block lines 380 to 381")

    cfg_open = {
        "hooks": {"pre_tool_call": [{
            "matcher": "kanban_complete|kanban_request_review",
            "command": str(missing), "timeout": 10, "fail_closed": False}]},
        "platform_toolsets": {"cli": ["hermes-cli"]},
    }
    shell_hooks.reset_for_tests()
    drop_pre_tool_call_hooks()
    shell_hooks.register_from_config(cfg_open, accept_hooks=True)
    result = call("kanban_complete", {"summary": "observation"})
    hook_error = "A GLM reviewer may not call" in result.get("error", "") if isinstance(result, dict) else False
    fc_error = result.get("error", "").startswith(f"hook {missing} failed closed:") if isinstance(result, dict) else False
    c2 = isinstance(result, dict) and "error" in result and not hook_error and not fc_error
    observed("c2 with fail_closed false and the same missing path, kanban_complete is not blocked by the hook "
             "(the hook fails open; what happens next is the tool handler, which refuses because no "
             "HERMES_KANBAN_TASK is set, so no board is reached)",
             c2, f"result={json.dumps(result)[:300]}, the hook returns None (fail open) of agent/shell_hooks.py "
                 f"_evaluate_result lines 406 to 413 (fail_closed is False)")

    # d. _worker_argv contains --accept-hooks.
    task = dispatch._kb.Task(
        id="t_observe", title="observation", body=None, assignee="harness-reviewer-glm",
        status="ready", priority=0, created_by="observer", created_at=0,
        started_at=None, completed_at=None,
        workspace_kind="scratch", workspace_path=None, claim_lock=None, claim_expires=None,
        tenant=None, skills=None, model_override=None, provider_override=None,
        reasoning_effort=None)
    argv = dispatch._worker_argv(task, "harness-reviewer-glm", str(home))
    d1 = "--accept-hooks" in argv
    observed("d1 _worker_argv of a dispatcher-started worker contains --accept-hooks",
             d1, f"argv={argv}, flag at hermes_cli/kanban_db_dispatch.py line 2754, registered in the worker "
                 f"process by hermes_cli/main.py _prepare_agent_startup lines 3012 to 3028 and 3088 to 3093 "
                 f"(register_from_config(load_config(), accept_hooks=_accept_hooks))")

    # e. An exception inside _dispatch_pre_tool_call_hooks.
    with mock.patch("hermes_cli.plugins._dispatch_pre_tool_call_hooks",
                    side_effect=RuntimeError("observation: hook dispatch failed")):
        result = call("kanban_complete", {"summary": "observation"})
    e_text = result.get("error", "") if isinstance(result, dict) else ""
    e1 = not isinstance(result, dict) or ("A GLM reviewer may not call" not in e_text
                                          and "failed closed" not in e_text)
    # Reported, never asserted: case e is the remaining failure case of the
    # second guard. The card's exit status covers cases a to d only, so a
    # Hermes change that makes this exception block (a fix) must not change
    # this program's exit status.
    if e1:
        print(f"OBSERVED e1: holds, an exception inside _dispatch_pre_tool_call_hooks lets the call proceed "
              f"past the guard: the try/except of model_tools.py _pre_dispatch_guards lines 781 to 789 catches "
              f"it, logs it at debug level only and leaves block_message None, so the tool handler runs (here "
              f"it refuses because no HERMES_KANBAN_TASK is set); this is the remaining failure case of the "
              f"second guard, reported, not worked around, result={json.dumps(result)[:300]}")
    else:
        print(f"OBSERVED e1: no longer holds, the call was blocked with result={json.dumps(result)[:300]}; "
              f"a Hermes change now makes an exception inside _dispatch_pre_tool_call_hooks block the call "
              f"(model_tools.py _pre_dispatch_guards); case e does not affect the exit status of this program")
    if _failures:
        print(f"FAILED cases: {', '.join(_failures)}")
        return 1
    print("all expected cases of a to d hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
