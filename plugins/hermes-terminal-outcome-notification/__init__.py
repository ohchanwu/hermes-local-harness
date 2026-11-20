"""Hermes plugin entry point for terminal outcome notifications."""
from __future__ import annotations

import logging
from typing import Any

from .core import Store, shared_outbox_path

_LOG = logging.getLogger(__name__)
_SESSION_LISTING = "persistence_assembly.open_persistence_reader and store.sessions.list_gateway_sessions"
_warned: set[str] = set()


def _store() -> Store:
    return Store(shared_outbox_path())


def _session_id(kwargs: dict[str, Any]) -> str:
    parent = kwargs.get("parent_agent")
    return str(kwargs.get("session_id") or getattr(parent, "session_id", "") or "")


def _session_ids_for_key(session_key: str) -> list[str]:
    """Session IDs of the live gateway session for one session key, read through the documented
    Hermes storage interface (plugin guide, "hermes_state deprecated: the storage interface
    replacements"). Each entry is a SessionRecencyEntry; its `session` carries `session_key` and
    `session_id`. Read-only. When the interface is absent or the read fails, return [] (recovery
    then classifies the turn `unknown`) and write one WARNING record per process."""
    if not session_key:
        return []
    try:
        from persistence_assembly import open_persistence_reader, profile_scope
        with open_persistence_reader(profile_scope().profile_dir) as store:
            return [str(entry.session.session_id)
                    for entry in store.sessions.list_gateway_sessions(active_only=True)
                    if entry.session.session_key == session_key]
    except Exception as exc:  # any Hermes failure must not raise into Hermes
        if _SESSION_LISTING not in _warned:
            _warned.add(_SESSION_LISTING)
            _LOG.warning("terminal outcome notification: Hermes %s failed (%s: %s); agent_loop_stopped "
                         "stop evidence is recorded only by session key", _SESSION_LISTING, type(exc).__name__, exc)
        return []


def arm_campaign(params: dict[str, Any], **kwargs: Any) -> str:
    """Deterministic arming interface. The HOST supplies the real opaque session_id at tool
    dispatch (tools/registry.dispatch → handler(args, session_id=..., task_id=...)), so the watch
    binds to exactly the session that asked; no cross-session claiming is possible."""
    session_id = _session_id(kwargs)
    if not session_id:
        # ponytail: fail closed — without host session identity arming is impossible; never guess.
        return '{"success":false,"error":"session identity unavailable from host tool dispatch"}'
    title = str(params.get("title") or "Direct Hermes campaign")
    # lane is reserved for session-key-level identity; tool dispatch has no platform/session_key,
    # and a platform value here would make lane matches cross-session.
    campaign_id = _store().arm_direct(session_id, title)
    return f'{{"success":true,"campaign_id":"{campaign_id}"}}'


def campaign_terminal(params: dict[str, Any], **kwargs: Any) -> str:
    status, summary = params.get("status"), params.get("summary")
    if not isinstance(status, str) or not isinstance(summary, str):
        return '{"success":false,"error":"status and summary are required"}'
    if not _store().proposal(_session_id(kwargs), status, summary):
        return '{"success":false,"error":"no armed direct campaign"}'
    return '{"success":true,"armed":true}'


def watch_terminal_task(params: dict[str, Any], **kwargs: Any) -> str:
    task_id = str(params.get("task_id") or "").strip()
    if not task_id:
        return '{"success":false,"error":"task_id is required"}'
    title = str(params.get("title") or f"Kanban campaign {task_id}")
    campaign_id = _store().watch_task(task_id, title)
    return f'{{"success":true,"campaign_id":"{campaign_id}"}}'


def arm_command(raw_args: str) -> str:
    """Slash commands receive only raw text on every surface (CLI/gateway/TUI) — no session
    identity, so deterministic binding is impossible. Fail closed and point at the tool."""
    return ("Slash arming is not supported: plugin slash handlers get no session identity. "
            "Ask the agent to call the arm_campaign tool, which binds Hermes's real session ID.")


def watch_command(raw_args: str) -> str:
    task_id, _, title = raw_args.strip().partition(" ")
    if not task_id:
        return "Usage: /watch-terminal-task TASK_ID [title]"
    _store().watch_task(task_id, title or f"Kanban campaign {task_id}")
    return f"Terminal notification armed for watched Kanban task {task_id}."


def _pre_llm_call(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        # pre_llm_call supplies platform, never session_key: the surface lane is NOT captured
        # here (a platform value would match every session on that surface). session-key-level
        # identity is resolved through the Hermes storage interface at agent_loop_stopped instead.
        _store().touch(session_id, None, str(kwargs.get("parent_session_id") or "") or None)


def _post_llm_call(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        _store().candidate(session_id, str(kwargs.get("assistant_response") or ""))


def _on_session_end(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        _store().session_end(session_id, completed=bool(kwargs.get("completed")), failed=bool(kwargs.get("failed")),
                             interrupted=bool(kwargs.get("interrupted")),
                             turn_exit_reason=str(kwargs.get("turn_exit_reason") or kwargs.get("reason") or ""))


def _on_session_reset(**kwargs: Any) -> None:
    new_session_id = str(kwargs.get("new_session_id") or kwargs.get("session_id") or "")
    if new_session_id:
        # The hook does not document session_key (hooks.md), so no lane is passed; the gateway
        # passes old_session_id, which Store.reset uses first.
        _store().reset(new_session_id, str(kwargs.get("old_session_id") or "") or None)


def _agent_loop_stopped(**kwargs: Any) -> None:
    # Gateway/TUI supply session_key only. Resolve it to live session ids through the Hermes
    # storage interface and stamp stop evidence so recovery classifies the turn `interrupted`,
    # not `unknown`.
    session_key = str(kwargs.get("session_key") or "")
    reason = str(kwargs.get("reason") or "interrupted")
    store = _store()
    store.stopped(session_key, reason, by_lane=True)
    for session_id in _session_ids_for_key(session_key):
        store.stopped(session_id, reason)


def _kanban_completed(**kwargs: Any) -> None:
    _store().kanban_completed(str(kwargs.get("task_id") or ""), str(kwargs.get("summary") or "Campaign completed"))


def _kanban_blocked(**kwargs: Any) -> None:
    run_id = kwargs.get("run_id")
    # exact positive int only: a boolean payload (True == 1) is not run evidence
    _store().kanban_blocked(str(kwargs.get("task_id") or ""), str(kwargs.get("reason") or "Campaign blocked"),
                            int(run_id) if isinstance(run_id, int) and not isinstance(run_id, bool) else None)


def _kanban_claimed(**kwargs: Any) -> None:
    _store().claimed(str(kwargs.get("task_id") or ""))


def register(ctx: Any) -> None:
    ctx.register_tool(name="arm_campaign", toolset="terminal_outcome_notifications", schema={
        "name": "arm_campaign", "description": "Arm one terminal notification for the CURRENT direct turn (one-shot). Does not send anything.",
        "parameters": {"type": "object", "properties": {"title": {"type": "string", "maxLength": 240}},
                       "required": []}}, handler=arm_campaign)
    ctx.register_tool(name="campaign_terminal", toolset="terminal_outcome_notifications", schema={
        "name": "campaign_terminal", "description": "Record the explicit terminal outcome for an armed direct campaign. Does not send a notification.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["completed", "blocked"]},
        "summary": {"type": "string", "maxLength": 240}}, "required": ["status", "summary"]}}, handler=campaign_terminal)
    ctx.register_tool(name="watch_terminal_task", toolset="terminal_outcome_notifications", schema={
        "name": "watch_terminal_task", "description": "Watch one root or finalizer Kanban task for terminal outcome notification.",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string"},
        "title": {"type": "string", "maxLength": 240}}, "required": ["task_id"]}}, handler=watch_terminal_task)
    ctx.register_command("notify-on-terminal", arm_command, "Arm one terminal notification for the next direct turn.")
    ctx.register_command("watch-terminal-task", watch_command, "Watch one root or finalizer Kanban task.", args_hint="TASK_ID [title]")
    for name, callback in (("pre_llm_call", _pre_llm_call), ("post_llm_call", _post_llm_call),
                           ("on_session_end", _on_session_end), ("on_session_reset", _on_session_reset),
                           ("agent_loop_stopped", _agent_loop_stopped), ("kanban_task_claimed", _kanban_claimed),
                           ("kanban_task_completed", _kanban_completed), ("kanban_task_blocked", _kanban_blocked)):
        ctx.register_hook(name, callback)
