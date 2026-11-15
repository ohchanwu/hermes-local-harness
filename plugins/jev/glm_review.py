"""The refusal of ``kanban_complete`` and ``kanban_request_review`` in a GLM reviewer session.

A GLM reviewer returns its findings with ``kanban_request_changes``; the
approval of a card is made by the Opus reviewer of the board. This module
decides whether the profile of this session is a GLM reviewer and builds the
error result that refuses the two tools. It never raises and never calls
``next_call``: a middleware that raises before it calls ``next_call`` lets
Hermes run the tool.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

try:  # loaded as the plugin package
    from . import jev_log
except ImportError:  # loaded directly by the tests
    import jev_log  # type: ignore[no-redef]

# A GLM reviewer profile name ends in ``-reviewer-glm``; the first character
# and the middle are lower case letters, digits and hyphens.
_GLM_REVIEWER_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*-reviewer-glm$")
# Hermes task IDs are "t_" plus hexadecimal digits (hermes_cli/kanban_db.py _new_task_id).
_HERMES_TASK_ID = re.compile(r"t_[0-9a-f]{4,32}")

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
