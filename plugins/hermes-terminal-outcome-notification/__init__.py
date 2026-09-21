"""Hermes plugin entry point for terminal outcome notifications."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .core import Store


def _store() -> Store:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return Store(home / "terminal-outcome-notifications" / "outbox.sqlite3")


def _session_id(kwargs: dict[str, Any]) -> str:
    return str(kwargs.get("session_id") or kwargs.get("session_key") or "")


def campaign_terminal(params: dict[str, Any], **kwargs: Any) -> str:
    status, summary = params.get("status"), params.get("summary")
    if not isinstance(status, str) or not isinstance(summary, str):
        return '{"success":false,"error":"status and summary are required"}'
    if not _store().proposal(_session_id(kwargs), status, summary):
        return '{"success":false,"error":"no armed direct campaign"}'
    return '{"success":true,"armed":true}'


def arm_command(args: list[str], **kwargs: Any) -> str:
    session_id = _session_id(kwargs)
    if not session_id:
        return "Cannot arm notification: session identity unavailable."
    title = " ".join(args).strip() or "Direct Hermes campaign"
    _store().arm_direct(session_id, title, lane=str(kwargs.get("session_key") or "") or None)
    return "Terminal notification armed for this turn. Record completed or blocked with campaign_terminal before finishing."


def _post_llm_call(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        _store().candidate(session_id, str(kwargs.get("assistant_response") or ""))


def _on_session_end(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        _store().session_end(session_id, completed=bool(kwargs.get("completed")), failed=bool(kwargs.get("failed")),
                             interrupted=bool(kwargs.get("interrupted")), turn_exit_reason=str(kwargs.get("turn_exit_reason") or ""))


def _on_session_reset(**kwargs: Any) -> None:
    new_session_id = str(kwargs.get("new_session_id") or kwargs.get("session_id") or "")
    if new_session_id:
        _store().reset(new_session_id, str(kwargs.get("old_session_id") or "") or None,
                       str(kwargs.get("session_key") or "") or None)


def _agent_loop_stopped(**kwargs: Any) -> None:
    session_id = _session_id(kwargs)
    if session_id:
        _store().stopped(session_id, str(kwargs.get("reason") or "interrupted"))


def _kanban_completed(**kwargs: Any) -> None:
    _store().kanban_completed(str(kwargs.get("task_id") or ""), str(kwargs.get("summary") or "Campaign completed"))


def _kanban_blocked(**kwargs: Any) -> None:
    _store().kanban_blocked(str(kwargs.get("task_id") or ""), str(kwargs.get("reason") or "Campaign blocked"))


def register(ctx: Any) -> None:
    ctx.register_tool(name="campaign_terminal", toolset="terminal_outcome_notifications", schema={
        "name": "campaign_terminal", "description": "Record the explicit terminal outcome for an armed direct campaign. Does not send a notification.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["completed", "blocked"]},
        "summary": {"type": "string", "maxLength": 240}}, "required": ["status", "summary"]}}, handler=campaign_terminal)
    ctx.register_command("notify-on-terminal", arm_command, "Arm one terminal notification for the current direct turn.")
    for name, callback in (("post_llm_call", _post_llm_call), ("on_session_end", _on_session_end),
                           ("on_session_reset", _on_session_reset), ("agent_loop_stopped", _agent_loop_stopped),
                           ("kanban_task_completed", _kanban_completed), ("kanban_task_blocked", _kanban_blocked)):
        ctx.register_hook(name, callback)
