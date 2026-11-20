"""Hermes plugin ``jev``: card model routing, peak-hours hold, tool result filter, usage logs.

Registered callbacks:
- ``tool_execution`` middleware: ``kanban_create`` (routing and peak-hours hold,
  ``routing.handle_create``), ``kanban_unblock`` (peak-hours hold instead of
  ``ready`` inside the window, ``routing.handle_unblock``),
  ``kanban_request_review`` (model override cleared before the review
  handoff, ``routing.handle_request_review``) and ``kanban_request_changes``
  (after the call, a GLM card with at least its change request limit change
  requests goes to a Claude worker; a route can carry its own limit,
  ``routing.handle_request_changes``). In a GLM reviewer session
  (``glm_review.is_glm_reviewer``), ``kanban_complete`` and
  ``kanban_request_review`` are refused with an error result and the tool is
  not called (``glm_review.handle_refused_tool``), and ``kanban_block`` with a
  reason that starts with ``jev-glm-review-pass`` blocks the card with the
  kind that keeps it out of ``triage``
  (``glm_review.handle_pass_block``). In a GLM review run that the dispatcher
  started inside the active peak-hours hold window, every tool other than
  ``kanban_block``, ``kanban_complete`` and ``kanban_request_review`` is
  refused with an error result, and ``kanban_block`` blocks the card with the
  hold reason (``glm_review.hold_action``, ``glm_review.handle_hold_block``).
  Every other tool passes through unchanged.
- ``llm_request`` middleware: the reasoning effort of the card from its body
  line ``Reasoning effort EXACT <level>.``, applied to each model request of a
  board worker (``reasoning_effort.llm_request``; decision record
  docs/decisions/261120-per-card-reasoning-effort.md). ``kanban_create`` adds a
  notice to its result when the body has an unusable line of this kind.
- ``transform_tool_result`` hook: calls ``tool_filter.transform`` (imported
  lazily); a missing module or any exception leaves the result unchanged.
- ``post_auxiliary_call`` hook: one ``auxiliary`` log record per call.

``config.json`` beside this file is read on every call, so a changed setting
applies without a restart. Each section turns off with its ``enabled`` value.

When a Hermes name that Hermes does not document is absent (decision record
docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, change 2),
jev turns off only the feature that needs it, leaves the Hermes call result
unchanged and writes one Python ``logging`` record at level WARNING per process
and name (``peak_hold.warn_missing_hermes_name``, logger ``jev``).
"""
from __future__ import annotations

import functools
import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from . import glm_review, jev_client, jev_log, peak_hold, reasoning_effort, routing

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# The argument names that jev reads or writes, per Kanban tool (decision record
# docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, row J21).
KANBAN_TOOL_ARGUMENTS = {
    "kanban_create": ("title", "body", "assignee", "model", "provider", "board"),
    "kanban_unblock": ("task_id", "board"),
    "kanban_request_review": ("task_id", "board", "reviewer"),
    "kanban_request_changes": ("task_id", "board"),
    "kanban_complete": ("task_id",),
    "kanban_block": ("task_id", "reason", "kind", "board"),
}
# Tool name to the first argument name that its registered schema lacks, or None.
_ABSENT_ARGUMENT: Dict[str, Optional[str]] = {}


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


def _absent_argument(tool_name: str) -> Optional[str]:
    """The first name of ``KANBAN_TOOL_ARGUMENTS[tool_name]`` that the Hermes
    schema of the tool (``tools.registry.registry.get_schema``) does not list,
    or None. Read once per tool per process. When the registry cannot be
    imported or has no schema for the tool (as in the offline tests), the
    answer is None and is not kept."""
    if tool_name in _ABSENT_ARGUMENT:
        return _ABSENT_ARGUMENT[tool_name]
    try:
        from tools.registry import registry  # type: ignore[import-not-found]
        schema = registry.get_schema(tool_name)
    except Exception:
        return None
    if not isinstance(schema, dict):
        return None
    parameters = schema.get("parameters")
    properties = parameters.get("properties") if isinstance(parameters, dict) else None
    names = properties if isinstance(properties, dict) else {}
    absent = next((name for name in KANBAN_TOOL_ARGUMENTS[tool_name] if name not in names), None)
    _ABSENT_ARGUMENT[tool_name] = absent
    if absent is not None:
        peak_hold.warn_missing_hermes_name(f"argument {absent} of the Hermes tool {tool_name}",
                                           f"the jev handling of {tool_name}")
    return absent


def _tool_execution(**kwargs: Any) -> Any:
    next_call = kwargs["next_call"]
    tool_name = kwargs.get("tool_name")
    try:
        # Row J21: a Kanban tool whose schema lacks an argument name that jev uses passes through unchanged.
        pass_through = tool_name in KANBAN_TOOL_ARGUMENTS and _absent_argument(tool_name) is not None
    except Exception:
        pass_through = False
    if pass_through:
        return next_call()
    if tool_name in ("kanban_complete", "kanban_request_review"):
        try:
            if glm_review.is_glm_reviewer(jev_log.profile_name(), load_config()):
                return glm_review.handle_refused_tool(tool_name, kwargs.get("args"))
        except Exception:
            return glm_review.REFUSAL_ERROR
    # The peak-hours hold of a GLM review run that started inside the hold
    # window (glm_review.hold_action): every tool other than kanban_block is
    # refused, and kanban_block blocks the card with the hold reason. An
    # exception in this part means the baseline behaviour for this call;
    # ``next_call`` runs outside the ``try``, at most once.
    hold_block: Any = None
    hold_result: Any = None
    try:
        hold = glm_review.hold_action(tool_name, kwargs.get("args"), load_config())
        if hold is not None:
            if hold["action"] == "blocked" and isinstance(hold["payload"], dict):
                hold_block = hold
            elif hold["action"] == "refused" and isinstance(hold["result"], str):
                hold_result = hold["result"]
    except Exception:
        hold_block = None
        hold_result = None
    if hold_result is not None:
        return hold_result
    if hold_block is not None:
        return glm_review.handle_hold_block(hold_block, next_call)
    if tool_name == "kanban_block":
        # The pass of a review without findings (glm_review.handle_pass_block):
        # only in a GLM reviewer session and only for a reason that starts with
        # the identifier of the decision document. ``next_call`` runs outside
        # the ``try`` so it is called exactly once on every path.
        args = kwargs.get("args")
        pass_config: Any = None
        try:
            reason = args.get("reason") if isinstance(args, dict) else None
            if isinstance(reason, str) and reason.startswith(glm_review.PASS_REASON):
                config = load_config()
                if glm_review.is_glm_reviewer(jev_log.profile_name(), config):
                    pass_config = config
        except Exception:
            pass_config = None
        if pass_config is not None:
            return glm_review.handle_pass_block(args, next_call, config=pass_config)
        return next_call()
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
            warn=peak_hold.warn_missing_hermes_name,
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
        if isinstance(usage, dict) and not {"prompt_tokens", "input_tokens", "output_tokens"} & usage.keys():
            peak_hold.warn_missing_hermes_name(
                "usage keys prompt_tokens, input_tokens and output_tokens of the Hermes hook post_auxiliary_call",
                "the token counts of the jev auxiliary log")
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


def _llm_request(**kwargs: Any) -> Any:
    try:
        return reasoning_effort.llm_request(config=load_config(), **kwargs)
    except Exception:
        return None


def register(ctx: Any) -> None:
    ctx.register_middleware("tool_execution", _tool_execution)
    ctx.register_middleware("llm_request", _llm_request)
    ctx.register_hook("transform_tool_result", _transform_tool_result)
    ctx.register_hook("post_auxiliary_call", _post_auxiliary_call)
