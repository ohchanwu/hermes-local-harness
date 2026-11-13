"""Hermes plugin ``jev``: card model routing, peak-hours hold, tool result filter, usage logs.

Registered callbacks:
- ``tool_execution`` middleware: ``kanban_create`` (routing and peak-hours hold,
  ``routing.handle_create``), ``kanban_unblock`` (peak-hours hold instead of
  ``ready`` inside the window, ``routing.handle_unblock``),
  ``kanban_request_review`` (model override cleared before the review
  handoff, ``routing.handle_request_review``) and ``kanban_request_changes``
  (after the call, a GLM card with ``routing.max_glm_change_requests`` change
  requests goes to a Claude worker, ``routing.handle_request_changes``). Every
  other tool passes through unchanged.
- ``transform_tool_result`` hook: calls ``tool_filter.transform`` (imported
  lazily); a missing module or any exception leaves the result unchanged.
- ``post_auxiliary_call`` hook: one ``auxiliary`` log record per call.

``config.json`` beside this file is read on every call, so a changed setting
applies without a restart. Each section turns off with its ``enabled`` value.
"""
from __future__ import annotations

import functools
import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from . import jev_client, jev_log, routing

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """The plugin configuration; an unreadable file gives an empty configuration (all parts off)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _bound_ask(config: Dict[str, Any]):
    return functools.partial(jev_client.ask, settings=config.get("jev") or {})


def hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        return Path(home)
    try:
        from hermes_constants import get_hermes_home  # type: ignore[import-not-found]
        return Path(get_hermes_home())
    except Exception:
        return Path("/Users/chanbla11mit/.hermes")


def _tool_execution(**kwargs: Any) -> Any:
    next_call = kwargs["next_call"]
    tool_name = kwargs.get("tool_name")
    if tool_name not in ("kanban_create", "kanban_unblock", "kanban_request_review", "kanban_request_changes"):
        return next_call()
    args = kwargs.get("args")
    if not isinstance(args, dict):
        return next_call()
    config = load_config()
    if tool_name == "kanban_create":
        return routing.handle_create(args, next_call, config=config, ask=_bound_ask(config))
    if tool_name == "kanban_unblock":
        return routing.handle_unblock(args, next_call, config=config)
    if tool_name == "kanban_request_changes":
        return routing.handle_request_changes(args, next_call, config=config)
    return routing.handle_request_review(args, next_call, config=config)


def _transform_tool_result(**kwargs: Any) -> Any:
    try:
        config = load_config()
        settings = config.get("tool_results") or {}
        if not settings.get("enabled", False):
            return None
        tool_filter = importlib.import_module(__name__ + ".tool_filter")
        replacement = tool_filter.transform(
            tool_name=kwargs.get("tool_name"), args=kwargs.get("args"), result=kwargs.get("result"),
            session_id=kwargs.get("session_id"), profile=jev_log.profile_name(), settings=settings,
            ask=_bound_ask(config), log=jev_log.write, cache_dir=hermes_home() / "cache" / "jev",
        )
        return replacement if isinstance(replacement, str) else None
    except Exception:
        return None


def _count(usage: Any, *names: str) -> Any:
    if not isinstance(usage, dict):
        return None
    for name in names:
        value = usage.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _post_auxiliary_call(**kwargs: Any) -> None:
    try:
        if not (load_config().get("auxiliary_log") or {}).get("enabled", False):
            return
        usage = kwargs.get("usage")
        if kwargs.get("error_type"):
            status = "error"
        elif kwargs.get("streaming"):
            status = "streaming"
        else:
            status = "ok"
        jev_log.write("auxiliary", {
            "aux_task": kwargs.get("aux_task") if isinstance(kwargs.get("aux_task"), str) else None,
            "provider": kwargs.get("provider") if isinstance(kwargs.get("provider"), str) else None,
            "model": kwargs.get("model") if isinstance(kwargs.get("model"), str) else None,
            # prompt_tokens = input + cache read + cache write (agent/auxiliary_hooks.py _usage_summary)
            "input_tokens": _count(usage, "prompt_tokens", "input_tokens"),
            "output_tokens": _count(usage, "output_tokens"),
            "status": status,
        })
    except Exception:
        pass


def register(ctx: Any) -> None:
    ctx.register_middleware("tool_execution", _tool_execution)
    ctx.register_hook("transform_tool_result", _transform_tool_result)
    ctx.register_hook("post_auxiliary_call", _post_auxiliary_call)
