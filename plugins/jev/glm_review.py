"""The refusal of ``kanban_complete`` and ``kanban_request_review`` in a GLM
reviewer session, and the pass of a review without findings to the Opus
reviewer of the board.

A GLM reviewer returns its findings with ``kanban_request_changes``; the
approval of a card is made by the Opus reviewer of the board. This module
decides whether the profile of this session is a GLM reviewer and builds the
error result that refuses the two tools. The refusal never raises and never
calls ``next_call``: a middleware that raises before it calls ``next_call``
lets Hermes run the tool.

``handle_pass_block`` is the ``tool_execution`` middleware body for
``kanban_block`` (decision document 261114-glm-reviewer-pass-to-opus-reviewer,
Decision step 2): a GLM reviewer session that blocks its card with a reason
that starts with the identifier ``jev-glm-review-pass`` blocks it with the
``kind`` that keeps the card out of ``triage``, and the hold script
(``scripts/jev-peak-hold``) later passes the card to the Opus reviewer of the
board.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, Mapping, Optional

try:  # loaded as the plugin package
    from . import jev_log, peak_hold, routing
except ImportError:  # loaded directly by the tests
    import jev_log  # type: ignore[no-redef]
    import peak_hold  # type: ignore[no-redef]
    import routing  # type: ignore[no-redef]

# A GLM reviewer profile name ends in ``-reviewer-glm``; the first character
# and the middle are lower case letters, digits and hyphens.
_GLM_REVIEWER_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*-reviewer-glm$")
# Hermes task IDs are "t_" plus hexadecimal digits (hermes_cli/kanban_db.py _new_task_id).
_HERMES_TASK_ID = re.compile(r"t_[0-9a-f]{4,32}")

# The fixed identifier of the decision document
# 261114-glm-reviewer-pass-to-opus-reviewer: the reason prefix of the block
# call that passes a review without findings to the Opus reviewer.
PASS_REASON = "jev-glm-review-pass"

# The result when building the normal refusal result itself raises.
REFUSAL_ERROR = ('{"error": "A GLM reviewer session cannot call this tool. A review with findings ends with '
                 'kanban_request_changes. The approval of a card is made by the Opus reviewer of the board."}')


def is_glm_reviewer(profile: Any, config: Any) -> bool:
    """True when ``profile`` names a GLM reviewer.

    The fixed pattern decides first: a name that matches it is a GLM reviewer
    whatever the configuration holds. A name that does not match the pattern is
    a GLM reviewer only when it is an entry of the ``glm_reviewers`` list of a
    board of ``config["routing"]["boards"]``. Any error while the
    configuration is read, a configuration that is empty or is not a mapping,
    and a board without a ``glm_reviewers`` list all leave the answer of the
    pattern alone.
    """
    if isinstance(profile, str) and _GLM_REVIEWER_NAME.match(profile):
        return True
    try:
        boards = (config.get("routing") or {}).get("boards") or {}
        if not isinstance(boards, dict):
            return False
        for entry in boards.values():
            names = (entry or {}).get("glm_reviewers") or []
            if isinstance(names, (list, tuple)) and profile in names:
                return True
        return False
    except Exception:
        return False


def refusal(tool_name: str) -> str:
    """The error result for one refused tool call, in the format of the Hermes tools."""
    return json.dumps({
        "error": (f"A GLM reviewer session cannot call {tool_name}. A review with findings ends with "
                  "kanban_request_changes. The approval of a card is made by the Opus reviewer of the board."),
    })


def handle_refused_tool(tool_name: str, args: Any) -> str:
    """Refuse one tool call of a GLM reviewer session.

    Writes one ``decisions`` record with the event ``glm_reviewer_refusal``,
    the tool name, the profile of this session and the task ID of the call (a
    task ID of the Hermes form, else null; from ``args`` when it is a dict,
    else from ``HERMES_KANBAN_TASK``). No other argument value is written. A
    failure to write the record is ignored. Never raises, never calls
    ``next_call``.
    """
    try:
        if isinstance(args, dict):
            raw_task_id = args.get("task_id")
        else:
            raw_task_id = os.environ.get("HERMES_KANBAN_TASK", "").strip() or None
        task_id: Optional[str] = raw_task_id if (isinstance(raw_task_id, str)
                                                 and _HERMES_TASK_ID.fullmatch(raw_task_id)) else None
        jev_log.write("decisions", {"event": "glm_reviewer_refusal", "tool": tool_name,
                                    "profile": jev_log.profile_name(), "task_id": task_id})
    except Exception:
        pass
    try:
        return refusal(tool_name)
    except Exception:
        return REFUSAL_ERROR


def _configured_board(board: Any, config: Any) -> Optional[str]:
    """``board`` when it is a board in ``routing.boards``, otherwise None.

    The same rule as ``routing._configured_board``: the resolved board name
    must be a board of the plugin configuration.
    """
    try:
        boards = (config.get("routing") or {}).get("boards") or {}
        return board if isinstance(board, str) and isinstance(boards, dict) and board in boards else None
    except Exception:
        return None


def _pass_note(config: Any, board: Optional[str]) -> str:
    """The ``jev_note`` text; it names the Opus reviewer when one is configured."""
    opus: Optional[str] = None
    try:
        entry = ((config.get("routing") or {}).get("boards") or {}).get(board)
        name = (entry or {}).get("opus_reviewer")
        opus = name if isinstance(name, str) and name else None
    except Exception:
        opus = None
    if opus is None:
        return ("The hold script passes this card to the Opus reviewer of the board. "
                "The GLM reviewer ends its run now and calls no other tool.")
    return (f"The hold script passes this card to the Opus reviewer of the board, {opus}. "
            "The GLM reviewer ends its run now and calls no other tool.")


def handle_pass_block(args: Any, next_call: Callable[..., Any], *, config: Any) -> Any:
    """The ``tool_execution`` middleware body for ``kanban_block`` in a GLM
    reviewer session (decision document 261114-glm-reviewer-pass-to-opus-
    reviewer, Decision step 2).

    The dispatch in the plugin package calls this function only in a GLM
    reviewer session, only for ``kanban_block``, only for dict ``args`` whose
    ``reason`` is a string that starts with the identifier
    ``jev-glm-review-pass``. It states the required behaviour in four items:

    1. It finds the task ID (``args["task_id"]`` when it is a Hermes task
       ID, else ``HERMES_KANBAN_TASK``) and the board
       (``routing.resolve_board(args, config)``), reads the card's
       ``block_kind`` from ``tasks`` with
       ``peak_hold.connect_readonly(peak_hold.kanban_db_path(config, board))``
       and closes the connection. It calls ``next_call`` with a copy of
       ``args`` whose ``kind`` is ``needs_input``, or ``capability`` when the
       card's ``block_kind`` is ``needs_input`` (the kind that keeps the card
       out of ``triage``); the original ``args`` object, the ``reason`` text
       and every other argument are unchanged. When the task ID or the board
       is not recognized, the card is not found, or the read raises, it calls
       ``next_call()`` with the arguments unchanged. After the tool returned,
       when its result is a JSON object without the key ``error``, it returns
       the same object with one added key ``jev_note`` whose value says that
       the hold script passes the card to the Opus reviewer of the board (it
       names the reviewer from ``opus_reviewer`` when one is configured) and
       that the GLM reviewer ends its run now and calls no other tool; in
       every other case (an error result, a result that is not a JSON
       object, an exception while the note is built) it returns the tool's
       result unchanged. It writes one ``decisions`` record with the event
       ``glm_review_pass_block``: ``board``, ``task_id``, ``profile``,
       ``kind`` (the kind passed, or null when unchanged), ``applied`` (true
       when the kind was set), ``not_applied_reason`` when it was not
       (``task_id_not_recognized``, ``board_not_configured``,
       ``card_not_found``, ``read_error``), ``error_class`` (the exception
       class name on a read error, else null) and ``tool_error`` (true when
       the tool's result had the key ``error``). No reason text, no other
       argument value and no card text is written. A failure to write the
       record is ignored.
    2. Every other ``kanban_block`` call never reaches this function; the
       dispatch passes it to ``next_call()`` unchanged, as at the baseline,
       also a GLM worker session that blocks with the same reason.
    3. ``next_call`` is called exactly once on every path. An exception in
       this function before the tool call means one ``next_call()`` with the
       unchanged arguments: ``next_call`` is not called inside the ``try``
       that catches this function's exceptions.
    4. This function starts no ``hermes kanban`` command, opens no write
       connection and calls no Hermes function other than through
       ``next_call``.
    """
    payload: Optional[Dict[str, Any]] = None
    record: Dict[str, Any] = {}
    try:
        record = {"event": "glm_review_pass_block", "board": None, "task_id": None,
                  "profile": jev_log.profile_name(), "kind": None, "applied": False,
                  "error_class": None, "tool_error": False}
        raw_task = args.get("task_id")
        task_id: Optional[str] = raw_task if (isinstance(raw_task, str)
                                              and _HERMES_TASK_ID.fullmatch(raw_task)) else None
        if task_id is None:
            env_task = os.environ.get("HERMES_KANBAN_TASK", "").strip()
            if _HERMES_TASK_ID.fullmatch(env_task):
                task_id = env_task
        record["task_id"] = task_id
        if task_id is None:
            record["not_applied_reason"] = "task_id_not_recognized"
        else:
            board = _configured_board(routing.resolve_board(args, config), config)
            record["board"] = board
            if board is None:
                record["not_applied_reason"] = "board_not_configured"
            else:
                conn = peak_hold.connect_readonly(peak_hold.kanban_db_path(config, board))
                try:
                    row = conn.execute("SELECT block_kind FROM tasks WHERE id = ?", (task_id,)).fetchone()
                finally:
                    conn.close()
                if row is None:
                    record["not_applied_reason"] = "card_not_found"
                else:
                    kind = "capability" if row["block_kind"] == "needs_input" else "needs_input"
                    payload = dict(args)
                    payload["kind"] = kind
                    record["kind"] = kind
                    record["applied"] = True
    except Exception as exc:
        payload = None
        record.setdefault("event", "glm_review_pass_block")
        record["applied"] = False
        record["kind"] = None
        record["not_applied_reason"] = "read_error"
        record["error_class"] = type(exc).__name__
    result = next_call(payload) if payload is not None else next_call()
    parsed: Any = None
    is_json_object = False
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
        is_json_object = isinstance(parsed, dict)
    except Exception:
        parsed = None
        is_json_object = False
    record["tool_error"] = bool(is_json_object and "error" in parsed)
    try:
        jev_log.write("decisions", record)
    except Exception:
        pass
    if is_json_object and "error" not in parsed:
        try:
            note = _pass_note(config, record.get("board"))
            with_note = dict(parsed)
            with_note["jev_note"] = note
            return json.dumps(with_note) if isinstance(result, str) else with_note
        except Exception:
            pass
    return result
