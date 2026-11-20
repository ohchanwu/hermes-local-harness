"""Reasoning effort of one Kanban card, from one line of the card body (card t_caf5dba0).

Decision record: docs/decisions/261120-per-card-reasoning-effort.md.

The card line is one full body line ``Reasoning effort EXACT <level>.`` with a
level from ``reasoning_effort.allowed_levels`` of ``config.json``.

``llm_request`` is the ``llm_request`` middleware callback of the plugin. It
changes the provider request only in a dispatcher-started worker session
(``HERMES_KANBAN_TASK`` and ``HERMES_KANBAN_BOARD`` set) of a profile that is
in ``implementation_workers``, ``glm_workers`` or ``glm_max_workers`` of that
board, and only when the card body has exactly one valid line:

- provider ``zai`` with a GLM 5.2 or GLM 5.3 model: the top-level
  ``reasoning_effort`` of the request is set to the GLM level of the card level
  (``GLM_5_3_LEVELS`` or ``GLM_5_2_LEVELS``); a request whose
  ``extra_body.thinking.type`` is ``disabled`` is not changed.
- provider ``claude-subscription``: ``extra_body["card_reasoning_effort"]`` is
  set to the card level.

The card is read once per process and task ID with the documented command
``hermes kanban --board <board> show <task> --json``; the result is kept, also
when it is "no level" or a failure. Every failure returns None, so the request
is unchanged and the worker runs at the reasoning effort of its profile.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

try:  # loaded as the plugin package
    from . import jev_log
except ImportError:  # loaded directly by the tests
    import jev_log  # type: ignore[no-redef]

LINE_START = "Reasoning effort"
CARD_LINE = re.compile(r"^Reasoning effort EXACT (\S+)\.$")
DEFAULT_ALLOWED_LEVELS = ("low", "medium", "high", "xhigh", "max")
WORKER_LISTS = ("implementation_workers", "glm_workers", "glm_max_workers")
COMMAND_TIMEOUT_SECONDS = 15
LOG_STREAM = "reasoning_effort"
GLM_PROVIDER = "zai"
CLAUDE_PROVIDER = "claude-subscription"
CLAUDE_KEY = "card_reasoning_effort"
# GLM 5.3 takes low, medium, high and max; GLM 5.2 takes high and max, and a lower
# level is raised to high (the same mapping as plugins/model-providers/zai/__init__.py
# of Hermes, which this plugin does not import).
GLM_5_3_LEVELS = {"low": "low", "medium": "medium", "high": "high", "xhigh": "max", "max": "max"}
GLM_5_2_LEVELS = {"low": "high", "medium": "high", "high": "high", "xhigh": "max", "max": "max"}

# (board, task ID) -> card level or None; one card read per process and task ID.
_card_levels: Dict[Tuple[str, str], Optional[str]] = {}
# (event, task ID) pairs that already have a log record in this process.
_logged: set = set()


class CardReadError(Exception):
    """The card could not be read; the message is the failure type."""


class UnexpectedRequestShape(Exception):
    """The provider request does not have the expected form."""


def allowed_levels(config: Mapping[str, Any]) -> Sequence[str]:
    settings = config.get("reasoning_effort") or {}
    levels = settings.get("allowed_levels")
    return levels if isinstance(levels, list) else DEFAULT_ALLOWED_LEVELS


def parse_card(body: Any, allowed: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    """(level, problem) of a card body: (level, None) for exactly one valid line,
    (None, problem text) for invalid lines, (None, None) when no line starts with
    ``Reasoning effort``."""
    if not isinstance(body, str):
        return None, None
    lines = [line for line in body.splitlines() if line.startswith(LINE_START)]
    if not lines:
        return None, None
    if len(lines) > 1:
        return None, f"{len(lines)} lines start with '{LINE_START}'; the card may have only one"
    match = CARD_LINE.match(lines[0])
    if match is None:
        return None, f"the line does not have the form '{LINE_START} EXACT <level>.'"
    if match.group(1) not in allowed:
        return None, f"the level '{match.group(1)}' is not one of {', '.join(allowed)}"
    return match.group(1), None


def create_notice(body: Any, config: Mapping[str, Any]) -> Optional[str]:
    """The notice text for ``kanban_create`` when the body has an unusable line, else None."""
    _level, problem = parse_card(body, allowed_levels(config))
    if problem is None:
        return None
    return (f"jev: the reasoning effort line of this card cannot be used: {problem}. "
            "The card was created unchanged, and its worker runs at the reasoning effort of its "
            f"profile. The line format is '{LINE_START} EXACT <level>.' with one of the levels "
            f"{', '.join(allowed_levels(config))}; correct the body to use a level for this card.")


def read_card_body(board: str, task_id: str) -> str:
    """The card body from ``hermes kanban --board <board> show <task> --json``."""
    executable = shutil.which("hermes")
    if not executable:
        raise CardReadError("command_not_found")
    try:
        proc = subprocess.run(
            [executable, "kanban", "--board", board, "show", task_id, "--json"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        raise CardReadError("timeout") from None
    if proc.returncode != 0:
        raise CardReadError("nonzero_exit")
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise CardReadError("json_error") from None
    task = data.get("task") if isinstance(data, dict) else None
    if not isinstance(task, dict) or "body" not in task:
        raise CardReadError("missing_field")
    body = task["body"]
    if body is None:
        return ""  # a card without a body
    if not isinstance(body, str):
        raise CardReadError("missing_field")
    return body


def _log_once(event: str, task_id: str, record: Dict[str, Any]) -> None:
    if (event, task_id) in _logged:
        return
    _logged.add((event, task_id))
    jev_log.write(LOG_STREAM, {"event": event, "task_id": task_id, **record})


def _card_level(board: str, task_id: str, config: Mapping[str, Any]) -> Optional[str]:
    key = (board, task_id)
    if key not in _card_levels:
        _card_levels[key] = None  # also a failed read is not repeated in this process
        try:
            level, _problem = parse_card(read_card_body(board, task_id), allowed_levels(config))
        except CardReadError as exc:
            _log_once("card_read_failed", task_id, {"board": board, "error_class": str(exc)})
            return None
        _card_levels[key] = level
    return _card_levels[key]


def _is_worker(profile: str, board: str, config: Mapping[str, Any]) -> bool:
    boards = (config.get("routing") or {}).get("boards") or {}
    board_cfg = boards.get(board) if isinstance(boards, dict) else None
    if not isinstance(board_cfg, dict):
        return False
    return any(isinstance(board_cfg.get(name), list) and profile in board_cfg[name] for name in WORKER_LISTS)


def changed_request(request: Any, provider: Any, model: Any, level: str) -> Optional[Dict[str, Any]]:
    """The request with the card level applied, or None when this provider or model gets no change."""
    if not isinstance(request, dict):
        raise UnexpectedRequestShape("request")
    extra_body = request.get("extra_body")
    if extra_body is None:
        extra_body = {}
    if not isinstance(extra_body, dict):
        raise UnexpectedRequestShape("extra_body")
    if provider == GLM_PROVIDER:
        name = model.lower() if isinstance(model, str) else ""
        if "glm-5.3" in name:
            table = GLM_5_3_LEVELS
        elif "glm-5.2" in name:
            table = GLM_5_2_LEVELS
        else:
            return None
        thinking = extra_body.get("thinking")
        if isinstance(thinking, dict) and thinking.get("type") == "disabled":
            return None
        return {**request, "reasoning_effort": table[level]}
    if provider == CLAUDE_PROVIDER:
        return {**request, "extra_body": {**extra_body, CLAUDE_KEY: level}}
    return None


def llm_request(*, config: Mapping[str, Any], **kwargs: Any) -> Optional[Dict[str, Any]]:
    """``llm_request`` middleware body; None leaves the request unchanged."""
    task_id = ""
    try:
        if (config.get("reasoning_effort") or {}).get("enabled") is not True:
            return None
        task_id = os.environ.get("HERMES_KANBAN_TASK", "").strip()
        board = os.environ.get("HERMES_KANBAN_BOARD", "").strip()
        if not task_id or not board:
            return None
        profile = jev_log.profile_name()
        provider = kwargs.get("provider")
        if provider not in (GLM_PROVIDER, CLAUDE_PROVIDER) or not _is_worker(profile, board, config):
            return None
        level = _card_level(board, task_id, config)
        if level is None:
            return None
        request = changed_request(kwargs.get("request"), provider, kwargs.get("model"), level)
        if request is None:
            return None
        _log_once("applied", task_id, {"board": board, "provider": provider, "level": level})
        return {"request": request, "source": "jev", "reason": "card reasoning effort"}
    except Exception as exc:
        try:
            _log_once("failed", task_id, {"error_class": type(exc).__name__})
        except Exception:
            pass
        return None
