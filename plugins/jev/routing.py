"""Card model routing (Part A) for ``kanban_create``, and the related Kanban steps.

``handle_create`` runs inside the ``tool_execution`` middleware for
``kanban_create``:

1. It asks Jev one Choice question whose criteria are the board's enabled
   routes; the state is the card title and the body cut at
   ``state_max_chars`` characters.
2. It applies a route only when the orchestrator left ``model`` empty and
   the ``assignee`` is one of the board's ``implementation_workers``.
   Card ``t_92e29d10`` (owner's instruction of 2026-11-14): when the GLM sum,
   the sum of the probabilities of the board's GLM routes (an enabled route
   with ``assignee_from`` or ``model``), is at least ``threshold``, the applied
   route is the GLM route with the highest probability (on a tie the one listed
   last in the board's ``routes``), whichever route Jev chose. Otherwise the
   applied route is the route that Jev chose only when its probability is at
   least ``threshold`` and it is not a GLM route. ``easy``, ``medium`` and
   ``hard`` are GLM routes: ``easy`` and ``medium`` move the card to the next
   GLM worker of the list ``glm_workers`` (alternating), ``hard`` to the one
   worker of ``glm_max_workers``; each sets ``model`` and ``provider`` and
   rewrites the profile name on a body line that starts with
   ``Assigned worker EXACT ``. ``very_hard`` changes nothing. The ``route``
   record keeps the route that Jev chose in ``route`` and names the applied
   route in ``applied_route``; ``glm_probability_sum`` holds the GLM sum.
   Control group: when ``routing.control_group_every`` is n > 0, every n-th
   card of a board and applied route that would get ``easy``, ``medium`` or
   ``hard`` (the three GLM routes) stays unchanged
   (``not_applied_reason`` ``control_group``), and the GLM worker alternation
   does not advance for it.
3. Inside the peak-hours window it creates a card assigned to a GLM worker
   as ``blocked`` and then moves it to ``scheduled`` with the
   ``jev-peak-hold`` marker (see ``peak_hold``), but only where both Kanban
   commands can work and only for a card this call creates (see
   ``_creation_hold_blocker``).
4. It writes one ``decisions`` record for every call.
5. When the body has a line that starts with ``Reasoning effort`` and cannot be
   used (``reasoning_effort.create_notice``), it adds the key ``jev_note`` with
   a notice to the JSON result; the card is created unchanged.

Any exception before ``next_call`` leaves the arguments unchanged.

``handle_unblock`` runs for ``kanban_unblock`` and, inside the window, moves a
blocked card of a GLM worker to ``scheduled`` with the marker instead of
making it ``ready``.

``handle_request_review`` runs for ``kanban_request_review`` in a GLM worker
session and clears the card's model override before the review handoff,
because the dispatcher passes a card's override to the reviewer run too.

``handle_request_changes`` runs for ``kanban_request_changes`` (reviewer
sessions): after the call, a card of a GLM worker with at least the card's
change request limit change requests goes to a Claude worker, and the
``Assigned worker EXACT`` body line is changed to name that worker. The limit
of a card comes from its route (a route can carry its own
``max_glm_change_requests``), else from the worker list of the assignee, else
from the general value ``routing.max_glm_change_requests``.
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
    from . import jev_log, peak_hold, reasoning_effort
    from .jev_client import JevError
except ImportError:  # loaded directly by the tests
    import jev_log  # type: ignore[no-redef]
    import peak_hold  # type: ignore[no-redef]
    import reasoning_effort  # type: ignore[no-redef]
    from jev_client import JevError  # type: ignore[no-redef]

QUESTION_ID = "route"
ASSIGNED_WORKER_LINE = re.compile(r"^(Assigned worker EXACT )([A-Za-z0-9][A-Za-z0-9_-]*)", re.MULTILINE)
# A task ID: a letter or digit, then up to 63 letters, digits, "_" or "-". The
# first character is not "-", so a task ID passed to ``hermes kanban`` cannot be
# read as a command option (decision record
# docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, row J23).
_HERMES_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
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


def _counter(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _clean_section(value: Any) -> Dict[str, Any]:
    """A state section with only string keys and counters (or one nested level of them)."""
    out: Dict[str, Any] = {}
    if not isinstance(value, dict):
        return out
    for key, item in value.items():
        if isinstance(item, dict):
            nested = {str(k): v for k, v in item.items() if isinstance(v, int) and not isinstance(v, bool)}
            if nested:
                out[str(key)] = nested
        elif isinstance(item, int) and not isinstance(item, bool):
            out[str(key)] = item
    return out


def _update_state(directory: Optional[Path], change: Callable[[Dict[str, Any]], Any]) -> Any:
    """Read ``<log dir>/routing-state.json`` under the lock, apply ``change`` to it,
    write it back atomically (mode 0600) and return what ``change`` returned.

    The file holds only board names, route names, section names and counters:
    ``counters`` (GLM worker alternation per board and per worker list; the
    list ``glm_workers`` uses the key of the board name alone, every other
    list the key ``<board>:<list name>``), ``control_group_counters``
    (per board and route) and ``escalation_counters`` (Claude worker
    alternation per board). Sections that ``change`` does not touch are kept.
    """
    path = (directory or jev_log.log_dir()) / STATE_FILE_NAME
    with _locked(path):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        state = {str(k): _clean_section(v) for k, v in (loaded.items() if isinstance(loaded, dict) else ())}
        value = change(state)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps({k: _clean_section(v) for k, v in state.items()}).encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, path)
    return value


def _next_in_rotation(section: str, board: str, workers: List[str], directory: Optional[Path],
                      list_name: str = "glm_workers") -> str:
    # The counter key of the list `glm_workers` is the board name alone, so the
    # existing live state files stay valid; every other list name is kept in
    # its own key, `<board>:<list name>`, so two lists of different lengths on
    # one board do not reset each other's alternation.
    key = board if list_name == "glm_workers" else f"{board}:{list_name}"

    def change(state: Dict[str, Any]) -> str:
        counters = state.setdefault(section, {})
        index = _counter(counters.get(key))
        counters[key] = (index + 1) % len(workers)
        return workers[index % len(workers)]
    return _update_state(directory, change)


def next_glm_worker(board: str, workers: List[str], directory: Optional[Path] = None,
                    list_name: str = "glm_workers") -> str:
    """Return the next GLM worker for ``board`` from the worker list named
    ``list_name`` and advance that list's counter (section ``counters``).

    The counter key is the board name for ``glm_workers`` and
    ``<board>:<list name>`` for every other list name.
    """
    return _next_in_rotation("counters", board, workers, directory, list_name)


def next_escalation_worker(board: str, workers: List[str], directory: Optional[Path] = None) -> str:
    """Return the next Claude worker for an escalated card of ``board`` (section ``escalation_counters``)."""
    return _next_in_rotation("escalation_counters", board, workers, directory)


def control_group_turn(board: str, route: str, every: int, directory: Optional[Path] = None) -> bool:
    """Advance the counter of ``board`` and ``route`` and return True on every ``every``-th card.

    The counter is kept modulo ``every`` in section ``control_group_counters``,
    so the ratio is exact however few cards there are.
    """
    def change(state: Dict[str, Any]) -> bool:
        routes = state.setdefault("control_group_counters", {}).setdefault(board, {})
        count = (_counter(routes.get(route)) + 1) % every
        routes[route] = count
        return count == 0
    return _update_state(directory, change)


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


def rewrite_assigned_worker(body: Any, new_assignee: str, only_from: Optional[str] = None) -> Any:
    """Replace the profile name on every body line that starts with
    ``Assigned worker EXACT ``; with ``only_from``, only on lines that name that
    profile. Text inside a line is never changed."""
    if not isinstance(body, str):
        return body

    def replace(match: "re.Match[str]") -> str:
        if only_from is not None and match.group(2) != only_from:
            return match.group(0)
        return match.group(1) + new_assignee
    return ASSIGNED_WORKER_LINE.sub(replace, body)


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
    if not parsed.get("error") and parsed.get("ok") is not False:
        for key in ("task_id", "status"):
            if key not in parsed:
                peak_hold.warn_missing_hermes_name(
                    f"result field {key} of the Hermes tool kanban_create",
                    "the task ID in the route record and the peak-hours hold at card creation")
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
    """A task ID taken from tool arguments, only when it matches ``_HERMES_TASK_ID``."""
    return value if isinstance(value, str) and _HERMES_TASK_ID.fullmatch(value) else None


def setting_count(section: Mapping[str, Any], key: str) -> int:
    """A positive whole-number setting; 0 (the part is off) for 0, a negative number,
    a missing value or a value of another type."""
    value = section.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _glm_sum(routes: Sequence[Mapping[str, Any]], probabilities: Mapping[str, float]) -> Optional[float]:
    """The sum of the probabilities of the GLM routes of the board, rounded to
    6 decimal places; None when the board has no GLM route.

    A GLM route is an enabled route that has ``assignee_from`` or ``model``. A
    GLM route without a number in Jev's answer counts as 0 (card t_92e29d10).
    """
    glm_routes = [str(r["name"]) for r in routes if r.get("assignee_from") or r.get("model")]
    if not glm_routes:
        return None
    return round(sum(probabilities.get(name, 0.0) for name in glm_routes), 6)


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
        "applied_route": None, "glm_probability_sum": None,
        "not_applied_reason": None, "jev_latency_ms": None, "jev_input_tokens": None, "error_class": None,
    }
    if not routing.get("enabled", False):
        record["not_applied_reason"] = "routing_disabled"
        return None, record
    if board_cfg is None:
        record["not_applied_reason"] = "board_not_configured"
        return None, record
    workers = [str(w) for w in board_cfg.get("implementation_workers") or []]
    glm = peak_hold.glm_workers_by_board(config).get(board, [])
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
    record.update(route=route, probabilities=probabilities, confidence=confidence,
                 glm_probability_sum=_glm_sum(routes, probabilities))

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
    # Card t_92e29d10: the applied route is decided by the GLM routes together.
    # When the GLM sum (the sum of the probabilities of the board's GLM routes,
    # rounded to 6 decimal places) is at least ``threshold``, the applied route
    # is the GLM route with the highest probability, whichever route Jev chose;
    # on a tie it is the tied GLM route that is listed last in the board's
    # ``routes``. Otherwise the card is unchanged when the probability of the
    # route that Jev chose is at least ``threshold`` and that route is not a
    # GLM route (``very_hard``); in every other case ``below_threshold``.
    glm_routes = [r for r in routes if r.get("assignee_from") or r.get("model")]
    glm_sum = record["glm_probability_sum"] if glm_routes else None
    chosen_by_jev = next(r for r in routes if str(r["name"]) == route)
    applied_route: Optional[str] = None
    if glm_routes and glm_sum is not None and glm_sum >= threshold:
        best = max(probabilities.get(str(r["name"]), 0.0) for r in glm_routes)
        applied_route = str(next(r for r in reversed(glm_routes)
                                if probabilities.get(str(r["name"]), 0.0) == best)["name"])
    elif (probabilities.get(route) is not None and probabilities[route] >= threshold
          and not chosen_by_jev.get("assignee_from") and not chosen_by_jev.get("model")):
        applied_route = route
    if applied_route is None:
        record["not_applied_reason"] = "below_threshold"
        return None, record

    chosen = next(r for r in routes if str(r["name"]) == applied_route)
    if not chosen.get("assignee_from") and not chosen.get("model"):
        record["applied"] = True  # very_hard: the orchestrator's Claude worker keeps the card unchanged
        record["applied_route"] = applied_route
        return None, record
    pool: List[str] = []
    if chosen.get("assignee_from"):
        pool = [str(w) for w in board_cfg.get(str(chosen["assignee_from"])) or []]
        if not pool:
            record["not_applied_reason"] = "no_glm_workers"
            return None, record
    # Control group: every n-th card that would get this route keeps the
    # orchestrator's Claude worker; the GLM worker alternation does not advance.
    # Card t_92e29d10: the counter of the applied route; the record names the
    # route that would have been applied in ``applied_route`` (it differs from
    # Jev's choice ``route`` whenever the GLM sum carried the card).
    every = setting_count(routing, "control_group_every")
    if every and control_group_turn(board, applied_route, every, state_dir):
        record["not_applied_reason"] = "control_group"
        record["applied_route"] = applied_route
        return None, record
    new_args = dict(args)
    if pool:
        new_assignee = next_glm_worker(board, pool, state_dir, str(chosen["assignee_from"]))
        new_args["assignee"] = new_assignee
        new_args["body"] = rewrite_assigned_worker(args.get("body"), new_assignee)
        record["new_assignee"] = new_assignee
    if chosen.get("model"):
        new_args["model"] = str(chosen["model"])
        if chosen.get("provider"):
            new_args["provider"] = str(chosen["provider"])
    record["applied"] = True
    record["applied_route"] = applied_route
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
    # A body line "Reasoning effort ..." that the worker's llm_request middleware
    # cannot use (reasoning_effort.create_notice): a notice in the result, the card unchanged.
    try:
        notice = reasoning_effort.create_notice(args.get("body"), config)
        parsed = json.loads(result) if notice is not None and isinstance(result, str) else result
        if notice is not None and isinstance(parsed, dict):
            with_note = dict(parsed)
            with_note["jev_note"] = notice
            result = json.dumps(with_note) if isinstance(result, str) else with_note
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
                state = peak_hold.card_hold_state(config, board, task_id, peak_hold.marker(config), command)
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


def _review_choice_record(board: Optional[str], task_id: Optional[str], profile: str,
                          reviewer: Optional[str], opus_count: Optional[int], glm_count: Optional[int],
                          switch: bool, applied: bool,
                          not_applied_reason: Optional[str]) -> Dict[str, Any]:
    """The ``decisions`` record ``event`` ``review_choice`` of items 2, 4 and 6:
    identifiers, the two counts, the switch position and the applied flag only."""
    return {"event": "review_choice", "board": board, "task_id": task_id,
            "original_assignee": profile, "reviewer": reviewer,
            "opus_change_requests": opus_count, "glm_change_requests": glm_count,
            "switch": switch, "applied": applied, "not_applied_reason": not_applied_reason}


def _board_review_names(board_cfg: Mapping[str, Any]) -> Tuple[Optional[str], List[str]]:
    """``(opus_reviewer, glm_reviewers)`` of one board; the reviewers that are
    not non-empty strings are missing. Only the returned names are used."""
    opus = board_cfg.get("opus_reviewer")
    glm = [str(name) for name in board_cfg.get("glm_reviewers") or [] if isinstance(name, str) and name]
    return (opus if isinstance(opus, str) and opus else None), glm


def _change_request_payloads(card: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The payloads of the card's ``changes_requested`` events, oldest first
    (``show --json`` order); a payload that is not an object is an empty dict,
    and a missing card has no events."""
    events = (card or {}).get("events") or []
    payloads = [peak_hold.event_payload(event.get("payload")) for event in events
                if isinstance(event, Mapping) and event.get("kind") == "changes_requested"]
    if any("reviewer" not in payload for payload in payloads):
        peak_hold.warn_missing_hermes_name("payload field reviewer of the Kanban event changes_requested",
                                           "the count of change requests by reviewer")
    return payloads


def _card_change_request_reviewers(card: Optional[Mapping[str, Any]], opus_reviewer: str,
                                   glm_reviewers: List[str]) -> Tuple[int, int, Optional[str]]:
    """``(A, G, latest reviewer)`` of one card (a ``peak_hold.show_card``
    result): A is the number of its ``changes_requested`` events whose payload
    reviewer is ``opus_reviewer``, G the number whose payload reviewer is in
    ``glm_reviewers``, and the latest reviewer is the payload reviewer of the
    last event that has one. The events are read oldest first; no other text
    of a payload is used."""
    opus = glm = 0
    latest: Optional[str] = None
    for payload in _change_request_payloads(card):
        reviewer = payload.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer:
            continue
        latest = reviewer
        if reviewer == opus_reviewer:
            opus += 1
        elif reviewer in glm_reviewers:
            glm += 1
    return opus, glm, latest


def _review_payload(args: Mapping[str, Any], config: Mapping[str, Any], profile: str,
                    command: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """``(arguments for the tool, record)`` of the reviewer choice; the
    arguments are None when they are unchanged. Reads the card with
    ``peak_hold.show_card`` (``hermes kanban show --json``) and starts no
    command that changes the card."""
    routing_section = config.get("routing")
    routing: Mapping[str, Any] = routing_section if isinstance(routing_section, dict) else {}
    glm_section = routing.get("glm_review")
    glm_review: Mapping[str, Any] = glm_section if isinstance(glm_section, dict) else {}
    switch_on = bool(glm_review.get("enabled"))
    raw_task = args.get("task_id") or os.environ.get("HERMES_KANBAN_TASK", "").strip() or None
    raw_board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD", "").strip() or None
    task_id = _arg_task_id(raw_task)
    board = _configured_board(raw_board, config)

    def record(reviewer: Optional[str], applied: bool, reason: Optional[str],
               opus_count: Optional[int] = None, glm_count: Optional[int] = None) -> Dict[str, Any]:
        return _review_choice_record(board, task_id, profile, reviewer, opus_count, glm_count,
                                     switch_on, applied, reason)

    if task_id is None:
        return None, record(None, False, "task_id_not_recognized")
    if raw_board is not None and board is None:
        return None, record(None, False, "board_not_configured")
    if board is None:
        return None, record(None, False, "board_not_configured")
    board_cfg = (routing.get("boards") or {}).get(board) or {}
    opus_reviewer, glm_reviewers = _board_review_names(board_cfg)
    if opus_reviewer is None or not glm_reviewers:
        return None, record(None, False, "reviewer_not_configured")

    card = peak_hold.show_card(config, board, task_id, command)
    opus_events, glm_events, latest = _card_change_request_reviewers(card, opus_reviewer, glm_reviewers)

    arg_reviewer = args.get("reviewer")
    arg_names_glm = isinstance(arg_reviewer, str) and arg_reviewer in glm_reviewers
    arg_missing_or_empty = not isinstance(arg_reviewer, str) or not arg_reviewer
    chosen: Optional[str] = None
    if switch_on:
        maximum = setting_count(glm_review, "max_glm_review_change_requests")
        if opus_events == 0 and glm_events < maximum:
            chosen = glm_reviewers[0]
        else:
            chosen = opus_reviewer
    elif arg_names_glm or (arg_missing_or_empty and latest in glm_reviewers):
        chosen = opus_reviewer
    if chosen is None:
        return None, record(None, False, None, opus_events, glm_events)
    payload = dict(args)
    payload["reviewer"] = chosen
    return payload, record(chosen, True, None, opus_events, glm_events)


def handle_request_review(args: Mapping[str, Any], next_call: Callable[..., Any], *,
                          config: Mapping[str, Any], command: Optional[str] = None) -> Any:
    """``tool_execution`` middleware body for ``kanban_request_review``.

    In a GLM worker session, clear the card's model override first so that the
    reviewer run does not start with the GLM model and the ``zai`` provider.
    Only a task ID that matches ``_HERMES_TASK_ID`` and a board in ``routing.boards`` are
    used and logged; other argument values are never written to a log.

    Then, in a GLM worker session with ``routing.enabled`` true, the reviewer
    for the call is decided:

    - Switch on (``routing.glm_review.enabled`` true): the card is read with
      ``hermes kanban show --json`` and its ``changes_requested`` events are counted by
      the ``reviewer`` of each payload. A is the number of events whose
      reviewer is the board's ``opus_reviewer``; G the number of events whose
      reviewer is in the board's ``glm_reviewers``. When A is 0 and G is less
      than ``max_glm_review_change_requests`` (read with ``setting_count``; 0
      or a missing value means the GLM reviewer is never chosen), the reviewer
      is the first name of ``glm_reviewers``; otherwise it is the board's
      ``opus_reviewer``. The chosen reviewer is always passed explicitly with a
      copy of the arguments that has ``reviewer`` set to it; the original
      arguments are not changed, also when the arguments already name a
      reviewer.
    - Switch off or missing: when the ``reviewer`` argument names one of the
      board's ``glm_reviewers``, or when it is missing or empty and the
      ``reviewer`` of the card's latest ``changes_requested`` event is one of
      them, the board's ``opus_reviewer`` is passed explicitly instead. In
      every other case the arguments are unchanged. Reason (Rollback of Part 6
      of the specification): after the switch is turned off, Hermes would
      otherwise send a later review request back to a GLM reviewer, because
      with no ``reviewer`` argument Hermes uses the reviewer of the card's
      latest ``changes_requested`` event.
    - Missing data (no ``opus_reviewer`` or no ``glm_reviewers`` on the board,
      a task ID that does not match ``_HERMES_TASK_ID``, a board that is not in
      ``routing.boards``, or a read error of the card): the arguments are
      unchanged, as at the baseline.
    - In every other session (Claude workers, reviewers, orchestrators) the
      arguments are unchanged, also when the switch is on.
    - One ``decisions`` record ``event`` ``review_choice`` is written for each
      call that reaches one of the two rules: ``board``, ``task_id``,
      ``original_assignee`` (the profile), ``reviewer`` (the name passed, or
      null when unchanged), ``opus_change_requests`` (A), ``glm_change_requests``
      (G), ``switch`` (true or false), ``applied`` (true when the reviewer
      argument was set), and ``not_applied_reason`` when it was not
      (``task_id_not_recognized``, ``board_not_configured``,
      ``reviewer_not_configured``, ``read_error``). No other argument value and
      no card text is written. A failure to write the record is ignored.
    - ``next_call`` is called exactly once on every path. An exception in the
      new code never stops the call: the arguments are built inside ``try``,
      and after it ``next_call`` runs once, with the unchanged arguments when
      the new code raised.
    """
    profile = ""
    glm_worker_session = False
    try:
        routing_section = config.get("routing")
        routing = routing_section if isinstance(routing_section, dict) else {}
        profile = jev_log.profile_name()
        glm_worker_session = (bool(routing.get("enabled", False))
                              and profile in peak_hold.all_glm_workers(config))
        if glm_worker_session and routing.get("clear_override_at_review", True):
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

    payload: Optional[Dict[str, Any]] = None
    try:
        if glm_worker_session:
            payload, record = _review_payload(args, config, profile, command)
            jev_log.write("decisions", record)
    except Exception:
        payload = None
        try:
            routing_section = config.get("routing")
            routing = routing_section if isinstance(routing_section, dict) else {}
            glm_section = routing.get("glm_review")
            glm_review = glm_section if isinstance(glm_section, dict) else {}
            raw_task = args.get("task_id") or os.environ.get("HERMES_KANBAN_TASK", "").strip() or None
            raw_board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD", "").strip() or None
            jev_log.write("decisions", _review_choice_record(
                _configured_board(raw_board, config), _arg_task_id(raw_task), profile, None, None, None,
                bool(glm_review.get("enabled")), False, "read_error"))
        except Exception:
            pass
    return next_call(payload) if payload is not None else next_call()


# Card statuses in which a GLM implementer may hold the card right after
# ``kanban_request_changes``: ``ready`` or ``todo`` (Hermes ``request_changes``),
# ``running`` when a dispatcher tick claimed it for the GLM worker before the
# reassignment, ``scheduled`` when the peak-hours hold held it first.
_ESCALATION_STATUSES = ("ready", "todo", "running", "scheduled")
_RECLAIM_NAME = "option --reclaim of the command hermes kanban reassign"


def change_request_limit(route: Mapping[str, Any], routing: Mapping[str, Any]) -> int:
    """The change request limit of one route (card t_52be75ab): the route's own
    ``max_glm_change_requests`` when ``setting_count`` of it is positive, else
    the general value ``routing.max_glm_change_requests``."""
    own = setting_count(route, "max_glm_change_requests")
    return own if own else setting_count(routing, "max_glm_change_requests")


def change_request_state(card: Optional[Mapping[str, Any]]) -> Optional[Tuple[str, Optional[str], int]]:
    """``(status, assignee, number of changes_requested events)`` of one card
    (a ``peak_hold.show_card`` result), or None when the card does not exist."""
    if card is None:
        return None
    task = card["task"]
    return str(task.get("status")), task.get("assignee"), len(_change_request_payloads(card))


def _counted_change_requests(card: Optional[Mapping[str, Any]], glm_reviewers: Sequence[str]) -> int:
    """The number of the card's ``changes_requested`` events that count
    towards the change request limit: every event except one whose payload
    can be read and names one of ``glm_reviewers`` as the ``reviewer``.

    An event whose payload cannot be read, and an event whose payload has no
    ``reviewer``, is counted. With an empty ``glm_reviewers`` every event is
    counted, which is the number of the card's ``changes_requested`` events.
    """
    counted = 0
    for payload in _change_request_payloads(card):
        reviewer = payload.get("reviewer")
        if isinstance(reviewer, str) and reviewer in glm_reviewers:
            continue
        counted += 1
    return counted


def routed_claude_worker(board: str, task_id: str, workers: Sequence[str],
                         directory: Optional[Path] = None) -> Optional[str]:
    """The ``original_assignee`` of the latest ``route`` record of ``task_id`` on
    ``board`` in ``<log dir>/decisions.jsonl`` when it is one of ``workers``, else None."""
    path = (directory or jev_log.log_dir()) / "decisions.jsonl"
    found: Optional[str] = None
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if task_id not in line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if (isinstance(record, dict) and record.get("event") == "route" and record.get("task_id") == task_id
                        and record.get("board") == board and record.get("original_assignee") in workers):
                    found = record["original_assignee"]
    except OSError:
        return None
    return found


def routed_applied_route(board: str, task_id: str, board_cfg: Mapping[str, Any],
                         directory: Optional[Path] = None) -> Optional[str]:
    """The applied route name of the latest ``route`` record of ``task_id`` on
    ``board`` in ``<log dir>/decisions.jsonl`` when the board's ``routes`` has
    an entry with that name (enabled or not), else None (card t_52be75ab).

    The record is read as ``routed_claude_worker`` reads it. The applied route
    name of the record is ``applied_route`` when that is a non-empty string,
    otherwise ``route`` when that is a non-empty string (records written before
    card ``t_92e29d10`` have no ``applied_route``). A file that cannot be read
    gives None. Only the returned name is written onwards; no other text from
    the log file is written.
    """
    path = (directory or jev_log.log_dir()) / "decisions.jsonl"
    found: Optional[str] = None
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if task_id not in line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if (isinstance(record, dict) and record.get("event") == "route" and record.get("task_id") == task_id
                        and record.get("board") == board and record.get("applied") is True):
                    name = record.get("applied_route")
                    if not isinstance(name, str) or not name:
                        name = record.get("route")
                    found = name if isinstance(name, str) and name else None
    except OSError:
        return None
    if found is None:
        return None
    for route in board_cfg.get("routes") or []:
        if isinstance(route, dict) and route.get("name") == found:
            return found
    return None


# The body travels as one command-line argument of ``hermes kanban edit`` (it has
# no ``--body-file`` option). Linux limits one argument to 131072 bytes
# (MAX_ARG_STRLEN) and macOS all arguments and the environment together to
# 1048576 bytes (ARG_MAX); a longer body is not sent.
MAX_BODY_ARGUMENT_BYTES = 100_000


def rewrite_body_after_escalation(config: Mapping[str, Any], board: str, task_id: str, glm_worker: str,
                                  claude_worker: str, command: Optional[str] = None) -> Dict[str, Any]:
    """Step 3 of ``handle_request_changes``: name the Claude worker on the body
    line ``Assigned worker EXACT <GLM worker>`` (written by ``decide`` at creation).

    Reads the stored body again and runs ``hermes kanban --board <board> edit
    <task id> --body=<body>`` only when a line that starts with ``Assigned
    worker EXACT `` names ``glm_worker``. The ``--body=`` form keeps a body that
    starts with ``-`` one argument value. Returns the fields for the ``escalate``
    record: ``assigned_worker_line`` is ``rewritten``, ``no_line`` (no command
    runs) or ``failed``, and ``assigned_worker_line_error_class`` the error class.
    Never raises; a failure leaves the card as the reassignment left it. No
    body text is returned or logged.
    """
    try:
        card = peak_hold.show_card(config, board, task_id, command)
        body = card["task"].get("body") if card is not None else None
        new_body = rewrite_assigned_worker(body, claude_worker, only_from=glm_worker)
        if not isinstance(body, str) or new_body == body:
            return {"assigned_worker_line": "no_line", "assigned_worker_line_error_class": None}
        if len(new_body.encode("utf-8")) > MAX_BODY_ARGUMENT_BYTES:
            ok, error_class = False, "BodyTooLong"
        else:
            ok, error_class = peak_hold.run_kanban(config, board, ["edit", task_id, "--body=" + new_body], command)
    except Exception as exc:
        ok, error_class = False, type(exc).__name__
    return {"assigned_worker_line": "rewritten" if ok else "failed",
            "assigned_worker_line_error_class": error_class}


def _card_limit(board_cfg: Mapping[str, Any], assignee: str, routing: Mapping[str, Any],
                board: str, task_id: str, state_dir: Optional[Path]) -> Tuple[int, Optional[str]]:
    """``(limit, applied route name)`` of one card (card t_52be75ab), the route
    name None unless the card's ``route`` record gave the limit.

    First rule, the card's ``route`` record: when the last record in
    ``<log dir>/decisions.jsonl`` with ``event`` ``route``, this ``task_id``,
    this ``board`` and ``applied`` exactly true names an applied route that the
    board's ``routes`` has (enabled or not; ``routed_applied_route``), the limit
    is the limit of that route (``change_request_limit``).

    Second rule, the worker list: every route of the board, enabled or not,
    whose ``assignee_from`` names a list of the board that contains the
    assignee. When the limits of these routes are all the same number, that
    number is the limit; when there is no such route or the limits differ, the
    general value ``routing.max_glm_change_requests`` is the limit.
    """
    general = setting_count(routing, "max_glm_change_requests")
    name = routed_applied_route(board, task_id, board_cfg, state_dir)
    if name is not None:
        for route in board_cfg.get("routes") or []:
            if isinstance(route, dict) and route.get("name") == name:
                return change_request_limit(route, routing), name
    limits: List[int] = []
    for route in board_cfg.get("routes") or []:
        if not isinstance(route, dict):
            continue
        list_name = route.get("assignee_from")
        if not isinstance(list_name, str) or not list_name:
            continue
        if assignee in [str(w) for w in board_cfg.get(list_name) or []]:
            limits.append(change_request_limit(route, routing))
    if limits and len(set(limits)) == 1:
        return limits[0], None
    return general, None


def handle_request_changes(args: Mapping[str, Any], next_call: Callable[..., Any], *,
                           config: Mapping[str, Any], command: Optional[str] = None,
                           state_dir: Optional[Path] = None) -> Any:
    """``tool_execution`` middleware body for ``kanban_request_changes``.

    The call runs first and its result is returned unchanged. Afterwards, when
    the card's assignee (the implementer that Hermes ``request_changes`` gave the
    card back to) is one of the board's GLM workers (the list ``glm_workers``
    and every other worker list that a route of the board names in
    ``assignee_from``; see ``peak_hold.glm_workers_by_board``) and the card has
    at least the card's change request limit ``changes_requested`` events, the
    card goes to a Claude worker of the board:
    1. ``hermes kanban --board <board> set-model <task id> none``;
    2. only when that worked, ``hermes kanban --board <board> reassign <task id>
       <Claude worker> --reclaim``. ``--reclaim`` ends a GLM run that a
       dispatcher tick started between the change request and this command;
       for a card that is not running it changes nothing.
    3. only when the reassignment worked and the stored body has a line that
       starts with ``Assigned worker EXACT <GLM worker>``,
       ``hermes kanban --board <board> edit <task id> --body=<body>`` with the
       Claude worker named on that line (``rewrite_assigned_worker``), so that the
       Claude worker does not find another profile named as the assigned worker.
       See ``rewrite_body_after_escalation``.
    The Claude worker is the ``original_assignee`` of the card's ``route``
    record, else the next of the board's ``implementation_workers`` (alternating).
    Hermes runs these commands inside the reviewer process: none checks
    ``HERMES_KANBAN_TASK`` (``hermes_cli/kanban.py`` ``_cmd_set_model``,
    ``_cmd_reassign`` and ``_cmd_edit``). One ``escalate`` record is written per
    escalation; it names the route that gave the limit in ``applied_route``,
    the limit used in ``max_glm_change_requests`` and the number of counted
    change requests in ``change_requests``. Every failure leaves the card
    as the earlier commands left it.

    Not every change request of the card counts towards the limit. A
    ``changes_requested`` event whose payload names one of the board's GLM
    reviewers (the list ``glm_reviewers``, every name of the list) as the
    ``reviewer`` does not count. Every other change request counts: an event
    whose payload cannot be read, and an event whose payload has no
    ``reviewer``, is counted. A board without ``glm_reviewers`` therefore
    counts every change request. Only the counted change requests are
    compared with the limit, and only the counted number is written as the
    ``escalate`` record's ``change_requests``.

    The limit of a card is decided only here and by two rules in order (card
    t_52be75ab; ``_card_limit``). First the card's ``route`` record: the limit
    of the route that the record names as the applied route, when the board's
    ``routes`` has that route (a route can carry its own
    ``max_glm_change_requests``; ``change_request_limit``). Otherwise the worker
    list of the assignee: when every route of the board whose ``assignee_from``
    names a list that contains the assignee has the same limit, that limit;
    otherwise the general value ``routing.max_glm_change_requests``. A card
    created before this change that has a ``route`` record for ``easy`` or
    ``medium`` keeps the general value through the first rule. The log file is
    not read for a card whose assignee is not a GLM worker of the board. When
    the general value is 0 the reassignment stays off for every route.
    """
    result = next_call()
    record: Optional[Dict[str, Any]] = None
    try:
        routing = config.get("routing") or {}
        general = setting_count(routing, "max_glm_change_requests")
        if not routing.get("enabled", False) or not general or _tool_error(result):
            return result
        task_id = _arg_task_id(args.get("task_id") or os.environ.get("HERMES_KANBAN_TASK", "").strip() or None)
        board = _configured_board(resolve_board(args, config), config)
        if task_id is None or board is None:
            return result
        board_cfg = (routing.get("boards") or {}).get(board) or {}
        glm = peak_hold.glm_workers_by_board(config).get(board, [])
        claude = [str(w) for w in board_cfg.get("implementation_workers") or []]
        glm_reviewers = _board_review_names(board_cfg)[1]
        card = peak_hold.show_card(config, board, task_id, command)
        state = change_request_state(card)
        count = _counted_change_requests(card, glm_reviewers) if state is not None else 0
        if state is None:
            return result
        status, assignee, _ = state
        if assignee not in glm or status not in _ESCALATION_STATUSES:
            return result
        limit, applied_route = _card_limit(board_cfg, assignee, routing, board, task_id, state_dir)
        if count < limit:
            return result
        record = {"event": "escalate", "board": board, "task_id": task_id, "original_assignee": assignee,
                  "new_assignee": assignee, "change_requests": count, "applied": False,
                  "applied_route": applied_route, "max_glm_change_requests": limit}
        if not claude:
            record["not_applied_reason"] = "no_claude_workers"
        else:
            new_assignee = (routed_claude_worker(board, task_id, claude)
                            or next_escalation_worker(board, claude, state_dir))
            record["new_assignee"] = new_assignee
            ok, error_class = peak_hold.run_kanban(config, board, ["set-model", task_id, "none"], command)
            if ok:
                ok, error_class = peak_hold.run_kanban(
                    config, board, ["reassign", task_id, new_assignee, "--reclaim"], command)
                if (not ok and _RECLAIM_NAME not in peak_hold.WARNED_HERMES_NAMES
                        and peak_hold.kanban_option_absent(config, board, "reassign", "--reclaim", command)):
                    peak_hold.warn_missing_hermes_name(
                        _RECLAIM_NAME, "the move of a GLM card to a Claude worker after change requests")
            record.update(applied=ok, error_class=error_class)
            if not ok:
                record["new_assignee"] = assignee
            else:
                record.update(rewrite_body_after_escalation(config, board, task_id, assignee, new_assignee, command))
        jev_log.write("decisions", record)
    except Exception as exc:
        failed: Dict[str, Any] = dict(record or {"event": "escalate"})
        failed.update(applied=False, not_applied_reason="plugin_error", error_class=type(exc).__name__)
        jev_log.write("decisions", failed)
    return result


def _tool_error(result: Any) -> bool:
    """True when a Kanban tool result is a Hermes error object (``{"error": ...}``)
    or reports ``ok`` false; any other result, also one that is not JSON, is False."""
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        return False
    return isinstance(parsed, dict) and ("error" in parsed or parsed.get("ok") is False)
