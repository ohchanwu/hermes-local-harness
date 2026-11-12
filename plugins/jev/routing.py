"""Card model routing (Part A) for ``kanban_create``, and the related Kanban steps.

``handle_create`` runs inside the ``tool_execution`` middleware for
``kanban_create``:

1. It asks Jev one Choice question whose criteria are the board's enabled
   routes; the state is the card title and the body cut at
   ``state_max_chars`` characters.
2. It applies the chosen route only when the orchestrator left ``model``
   empty, the ``assignee`` is one of the board's ``implementation_workers``
   and the route's probability is at least ``threshold``. ``easy`` and
   ``medium`` move the card to the next GLM worker of the board (alternating),
   set ``model`` and ``provider``, and rewrite the profile name on a body
   line that starts with ``Assigned worker EXACT ``. ``hard`` changes nothing.
3. Inside the peak-hours window it creates a card assigned to a GLM worker
   as ``blocked`` and then moves it to ``scheduled`` with the
   ``jev-peak-hold`` marker (see ``peak_hold``), but only where both Kanban
   commands can work and only for a card this call creates (see
   ``_creation_hold_blocker``).
4. It writes one ``decisions`` record for every call.

Any exception before ``next_call`` leaves the arguments unchanged.

``handle_unblock`` runs for ``kanban_unblock`` and, inside the window, moves a
blocked card of a GLM worker to ``scheduled`` with the marker instead of
making it ``ready``.

``handle_request_review`` runs for ``kanban_request_review`` in a GLM worker
session and clears the card's model override before the review handoff,
because the dispatcher passes a card's override to the reviewer run too.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

try:  # loaded as the plugin package
    from . import jev_log, peak_hold
    from .jev_client import JevError
except ImportError:  # loaded directly by the tests
    import jev_log  # type: ignore[no-redef]
    import peak_hold  # type: ignore[no-redef]
    from jev_client import JevError  # type: ignore[no-redef]

QUESTION_ID = "route"
ASSIGNED_WORKER_LINE = re.compile(r"^(Assigned worker EXACT )([A-Za-z0-9][A-Za-z0-9_-]*)", re.MULTILINE)
# Hermes task IDs are "t_" plus hexadecimal digits (hermes_cli/kanban_db.py _new_task_id).
_HERMES_TASK_ID = re.compile(r"t_[0-9a-f]{4,32}")
STATE_FILE_NAME = "routing-state.json"


# --- alternation state ----------------------------------------------------------

@contextmanager
def _locked(path: Path):
    jev_log.ensure_private_dir(path.parent)
    fd = os.open(path.with_name(path.name + ".lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def next_glm_worker(board: str, workers: List[str], directory: Optional[Path] = None) -> str:
    """Return the next GLM worker for ``board`` and advance its counter.

    The state file ``<log dir>/routing-state.json`` holds only board names and counters.
    """
    path = (directory or jev_log.log_dir()) / STATE_FILE_NAME
    with _locked(path):
        try:
            counters = json.loads(path.read_text(encoding="utf-8")).get("counters", {})
            if not isinstance(counters, dict):
                counters = {}
        except Exception:
            counters = {}
        index = counters.get(board, 0)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            index = 0
        chosen = workers[index % len(workers)]
        counters[board] = (index + 1) % len(workers)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps({"counters": {str(k): v for k, v in counters.items()
                                                   if isinstance(v, int)}}).encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, path)
    return chosen


# --- helpers -----------------------------------------------------------------

def resolve_board(args: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    """The board this call writes to, following Hermes: the ``board`` argument,
    then ``HERMES_KANBAN_BOARD``, then ``<kanban home>/kanban/current``, then ``default``."""
    explicit = args.get("board")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    env_board = os.environ.get("HERMES_KANBAN_BOARD", "").strip()
    if env_board:
        return env_board
    try:
        current = (peak_hold.kanban_home(config) / "kanban" / "current").read_text(encoding="utf-8-sig").strip()
        if current:
            return current
    except Exception:
        pass
    return "default"


def card_state(args: Mapping[str, Any], max_chars: int) -> Dict[str, str]:
    title = args.get("title")
    body = args.get("body")
    return {"title": title if isinstance(title, str) else "",
            "body": (body if isinstance(body, str) else "")[:max_chars]}


def route_question(routes: Sequence[Mapping[str, Any]], instructions: str) -> Dict[str, Any]:
    return {QUESTION_ID: {
        "type": "choice",
        "instructions": instructions,
        "criteria": {str(r["name"]): str(r.get("criterion") or r["name"]) for r in routes},
    }}


def rewrite_assigned_worker(body: Any, new_assignee: str) -> Any:
    if not isinstance(body, str):
        return body
    return ASSIGNED_WORKER_LINE.sub(lambda m: m.group(1) + new_assignee, body)


def _parse_answer(answers: Mapping[str, Any], names: List[str]) -> Tuple[str, Dict[str, float], Optional[float]]:
    answer = answers.get(QUESTION_ID)
    if not isinstance(answer, dict) or answer.get("choice") not in names:
        raise JevError("UnexpectedResponse")
    raw = answer.get("probabilities")
    if not isinstance(raw, dict):
        raise JevError("UnexpectedResponse")
    probabilities = {}
    for name in names:
        value = raw.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            probabilities[name] = float(value)
    confidence = answer.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else None
    return str(answer["choice"]), probabilities, confidence


def _create_result(result: Any) -> Tuple[Optional[str], Optional[str]]:
    """``(task_id, status)`` from a ``kanban_create`` result (Hermes reports both)."""
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        return None, None
    if not isinstance(parsed, dict):
        return None, None
    task_id = parsed.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", task_id):
        return None, None
    status = parsed.get("status")
    return task_id, status if isinstance(status, str) else None


def known_models(config: Mapping[str, Any]) -> set:
    """``routing.known_models`` plus every model a configured route sets."""
    routing = config.get("routing") or {}
    models = {str(m) for m in routing.get("known_models") or [] if isinstance(m, str)}
    for entry in (routing.get("boards") or {}).values():
        for route in (entry or {}).get("routes") or []:
            if isinstance(route, dict) and isinstance(route.get("model"), str):
                models.add(route["model"])
    return models


def _safe_model(value: Any, config: Mapping[str, Any]) -> Optional[str]:
    """The ``model`` argument for the log: a configured model ID as given,
    ``unrecognized`` for any other text, None when empty."""
    if not isinstance(value, str) or not value:
        return None
    return value if value in known_models(config) else "unrecognized"


def _configured_board(board: Any, config: Mapping[str, Any]) -> Optional[str]:
    """``board`` when it is a board in ``routing.boards``, otherwise None."""
    boards = (config.get("routing") or {}).get("boards") or {}
    return board if isinstance(board, str) and board in boards else None


def _arg_task_id(value: Any) -> Optional[str]:
    """A task ID taken from tool arguments, only when it has the Hermes form ``t_<hex>``."""
    return value if isinstance(value, str) and _HERMES_TASK_ID.fullmatch(value) else None


# --- decision ---------------------------------------------------------------

def decide(args: Mapping[str, Any], config: Mapping[str, Any], ask: Callable[..., Any],
           *, state_dir: Optional[Path] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Return ``(new_args or None, decisions record)`` for one ``kanban_create`` call."""
    routing = config.get("routing") or {}
    board = resolve_board(args, config)
    boards = routing.get("boards") or {}
    board_cfg = boards.get(board)
    assignee = args.get("assignee")
    record: Dict[str, Any] = {
        "event": "route", "board": board if board_cfg is not None else None, "task_id": None,
        "original_assignee": None, "new_assignee": None, "orchestrator_model": _safe_model(args.get("model"), config),
        "route": None, "probabilities": None, "confidence": None, "applied": False,
        "not_applied_reason": None, "jev_latency_ms": None, "jev_input_tokens": None, "error_class": None,
    }
    if not routing.get("enabled", False):
        record["not_applied_reason"] = "routing_disabled"
        return None, record
    if board_cfg is None:
        record["not_applied_reason"] = "board_not_configured"
        return None, record
    workers = [str(w) for w in board_cfg.get("implementation_workers") or []]
    glm = [str(w) for w in board_cfg.get("glm_workers") or []]
    if isinstance(assignee, str) and assignee in workers + glm:
        record["original_assignee"] = assignee
        record["new_assignee"] = assignee
    routes = [r for r in board_cfg.get("routes") or [] if isinstance(r, dict) and r.get("enabled") and r.get("name")]
    names = [str(r["name"]) for r in routes]
    if len(routes) < 2:
        record["not_applied_reason"] = "single_route"
        return None, record

    max_chars = int(routing.get("state_max_chars") or 60000)
    instructions = str(routing.get("question_instructions") or "Which route fits the work this Kanban card asks for?")
    try:
        result = ask(card_state(args, max_chars), route_question(routes, instructions))
        record["jev_latency_ms"] = result.latency_ms
        record["jev_input_tokens"] = result.input_tokens
        route, probabilities, confidence = _parse_answer(result.answers, names)
    except JevError as exc:
        record["error_class"] = exc.error_class
        record["not_applied_reason"] = "jev_error"
        return None, record
    except Exception as exc:
        record["error_class"] = type(exc).__name__
        record["not_applied_reason"] = "jev_error"
        return None, record
    record.update(route=route, probabilities=probabilities, confidence=confidence)

    try:
        threshold = float(routing.get("threshold", 0.6))
    except (TypeError, ValueError):
        threshold = 0.6
    if args.get("model"):
        record["not_applied_reason"] = "model_set"
        return None, record
    if assignee not in workers:
        record["not_applied_reason"] = "assignee_not_listed"
        return None, record
    probability = probabilities.get(route)
    if probability is None or probability < threshold:
        record["not_applied_reason"] = "below_threshold"
        return None, record

    chosen = next(r for r in routes if str(r["name"]) == route)
    if not chosen.get("assignee_from") and not chosen.get("model"):
        record["applied"] = True  # hard: the orchestrator's Claude worker keeps the card unchanged
        return None, record
    new_args = dict(args)
    if chosen.get("assignee_from"):
        pool = [str(w) for w in board_cfg.get(str(chosen["assignee_from"])) or []]
        if not pool:
            record["not_applied_reason"] = "no_glm_workers"
            return None, record
        new_assignee = next_glm_worker(board, pool, state_dir)
        new_args["assignee"] = new_assignee
        new_args["body"] = rewrite_assigned_worker(args.get("body"), new_assignee)
        record["new_assignee"] = new_assignee
    if chosen.get("model"):
        new_args["model"] = str(chosen["model"])
        if chosen.get("provider"):
            new_args["provider"] = str(chosen["provider"])
    record["applied"] = True
    return new_args, record


# --- middleware entry points ---------------------------------------------------

def _creation_hold_blocker(effective: Mapping[str, Any], config: Mapping[str, Any],
                           command: Optional[str]) -> Optional[str]:
    """Why the creation-time hold cannot be used for this call, or None when it can.

    The hold creates the card ``blocked`` and then runs ``hermes kanban
    schedule``; if that fails, ``hermes kanban unblock``. It is used only where
    both commands can work and only for a card this call creates:
    - ``idempotency_key``: Hermes returns an existing card for a known key
      (``hermes_cli/kanban_db.py`` ``create_task``), and that card must not be
      scheduled.
    - a dispatcher-started worker session (``HERMES_KANBAN_TASK`` set): both
      commands refuse every card other than the worker's own.
    - the ``hermes`` command does not resolve to an executable.
    In each of these cases the card is created as requested and
    ``scripts/jev-peak-hold`` holds it on its next run.
    """
    if effective.get("idempotency_key"):
        return "idempotency_key"
    if peak_hold.worker_session():
        return "worker_session"
    if not peak_hold.command_resolves(config, command):
        return "command_not_found"
    return None


def handle_create(args: Mapping[str, Any], next_call: Callable[..., Any], *, config: Mapping[str, Any],
                  ask: Callable[..., Any], now: Optional[datetime] = None, command: Optional[str] = None,
                  state_dir: Optional[Path] = None) -> Any:
    """``tool_execution`` middleware body for ``kanban_create``."""
    new_args: Optional[Dict[str, Any]] = None
    record: Dict[str, Any] = {"event": "route", "applied": False}
    hold_until: Optional[str] = None
    board: Optional[str] = None
    try:
        new_args, record = decide(args, config, ask, state_dir=state_dir)
        board = resolve_board(args, config)
        effective = new_args if new_args is not None else dict(args)
        moment = now or datetime.now().astimezone()
        active, switch_error = peak_hold.hold_active(config, moment)
        peak_hold.log_switch_error(switch_error)
        glm_here = peak_hold.glm_workers_by_board(config).get(board, [])
        # A card the caller creates blocked (orchestrator Card Setup) or in triage
        # is not dispatchable; its later kanban_unblock goes through handle_unblock.
        already_parked = (str(effective.get("initial_status") or "running") == "blocked"
                          or bool(effective.get("triage")))
        if (active and effective.get("assignee") in glm_here and not already_parked
                and _creation_hold_blocker(effective, config, command) is None):
            effective = dict(effective)
            effective["initial_status"] = "blocked"
            new_args = effective
            hold_until = peak_hold.held_until(moment, config.get("peak_hold") or {})
    except Exception as exc:
        new_args, hold_until = None, None
        record = {"event": "route", "applied": False, "not_applied_reason": "plugin_error",
                  "error_class": type(exc).__name__}

    result = next_call(new_args) if new_args is not None else next_call()

    try:
        task_id, status = _create_result(result)
        record["task_id"] = task_id
        if task_id is None and record.get("applied"):
            record["not_applied_reason"] = "create_failed"
        jev_log.write("decisions", record)
        # Schedule only a card that this call created blocked because the plugin
        # set initial_status (Hermes reports the stored status in the result).
        if hold_until is not None and task_id is not None and board is not None and status == "blocked":
            assignee = (new_args or {}).get("assignee")
            ok, error_class = peak_hold.hold_card(config, board, task_id, hold_until, command)
            if not ok:
                # Return the card to the dispatcher; scripts/jev-peak-hold holds it on its next run.
                released, release_error = peak_hold.release_card(config, board, task_id, command)
                error_class = error_class if released else f"{error_class}+{release_error}"
            peak_hold.log_hold(board, task_id, assignee, hold_until, ok, error_class)
    except Exception:
        pass
    return result


def handle_unblock(args: Mapping[str, Any], next_call: Callable[..., Any], *, config: Mapping[str, Any],
                   now: Optional[datetime] = None, command: Optional[str] = None) -> Any:
    """``tool_execution`` middleware body for ``kanban_unblock``.

    Orchestrator Card Setup creates every card ``blocked`` and unblocks it when
    setup is complete. Inside the peak-hours window, unblocking a card assigned
    to a GLM worker of that board would make it ``ready`` for the next
    dispatcher tick. Instead this moves the card from ``blocked`` directly to
    ``scheduled`` with the marker (``hermes kanban schedule`` accepts a blocked
    card), so the card is never ``ready`` inside the window, and returns a
    result that states this. A card that is already held with the marker stays
    held. If the schedule command fails, the unblock runs unchanged and
    ``scripts/jev-peak-hold`` holds the card on its next run.

    ``kanban_unblock`` is an orchestrator tool: Hermes refuses it when
    ``HERMES_KANBAN_TASK`` is set (``tools/kanban_tools.py``
    ``_require_orchestrator_tool``), so the session can run ``hermes kanban schedule``.
    """
    action: Optional[str] = None
    board: Optional[str] = None
    task_id: Optional[str] = None
    assignee: Optional[str] = None
    until: Optional[str] = None
    try:
        moment = now or datetime.now().astimezone()
        active, switch_error = peak_hold.hold_active(config, moment)
        peak_hold.log_switch_error(switch_error)
        if active and not peak_hold.worker_session():
            task_id = _arg_task_id(args.get("task_id"))
            board = _configured_board(resolve_board(args, config), config)
            glm_here = peak_hold.glm_workers_by_board(config).get(board or "", [])
            if task_id and board and glm_here:
                conn = peak_hold.connect_readonly(peak_hold.kanban_db_path(config, board))
                try:
                    state = peak_hold.card_hold_state(conn, task_id, peak_hold.marker(config))
                finally:
                    conn.close()
                if state is not None and state[1] in glm_here:
                    assignee = state[1]
                    until = peak_hold.held_until(moment, config.get("peak_hold") or {})
                    if state[0] == "blocked":
                        action = "hold"
                    elif state[2]:
                        action = "keep"
    except Exception as exc:
        action = None
        jev_log.write("decisions", {"event": "hold", "board": board, "task_id": task_id, "applied": False,
                                    "not_applied_reason": "plugin_error", "error_class": type(exc).__name__})

    if action == "hold":
        try:
            ok, error_class = peak_hold.hold_card(config, board, task_id, until, command)
            peak_hold.log_hold(board, task_id, assignee, until, ok, error_class)
        except Exception:
            ok = False
        if not ok:
            return next_call()
    elif action != "keep":
        return next_call()
    return json.dumps({
        "ok": True, "task_id": task_id, "status": "scheduled", "held_by": peak_hold.marker(config),
        "held_until": until,
        "note": ("Not unblocked: the jev plugin GLM peak-hours hold keeps this card in the scheduled "
                 "status until held_until. scripts/jev-peak-hold releases it then, or at once with "
                 "scripts/jev-peak-hold off."),
    })


def handle_request_review(args: Mapping[str, Any], next_call: Callable[..., Any], *,
                          config: Mapping[str, Any], command: Optional[str] = None) -> Any:
    """``tool_execution`` middleware body for ``kanban_request_review``.

    In a GLM worker session, clear the card's model override first so that the
    reviewer run does not start with the GLM model and the ``zai`` provider.
    Only a task ID of the Hermes form and a board in ``routing.boards`` are
    used and logged; other argument values are never written to a log.
    """
    try:
        routing = config.get("routing") or {}
        profile = jev_log.profile_name()
        if (routing.get("enabled", False) and routing.get("clear_override_at_review", True)
                and profile in peak_hold.all_glm_workers(config)):
            raw_task = args.get("task_id") or os.environ.get("HERMES_KANBAN_TASK", "").strip() or None
            raw_board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD", "").strip() or None
            task_id = _arg_task_id(raw_task)
            board = _configured_board(raw_board, config)
            record: Dict[str, Any] = {"event": "clear_override", "board": board, "task_id": task_id,
                                      "original_assignee": profile, "applied": False}
            if task_id is None:
                record["not_applied_reason"] = "task_id_not_recognized"
            elif raw_board is not None and board is None:
                record["not_applied_reason"] = "board_not_configured"
            else:
                ok, error_class = peak_hold.run_kanban(config, board, ["set-model", task_id, "none"], command)
                record.update(applied=ok, error_class=error_class)
            jev_log.write("decisions", record)
    except Exception:
        pass
    return next_call()
