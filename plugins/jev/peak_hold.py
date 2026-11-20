"""GLM peak-hours hold (Part E) and the owner's on/off switch.

Z.ai charges double on Monday to Friday, 15:00 to 19:00 Asia/Seoul. Inside
that window no card assigned to a GLM worker profile listed in ``config.json``
may be claimed by the dispatcher. A held card is moved to the Kanban
``scheduled`` status with a reason that starts with the marker
``jev-peak-hold``; it is released with ``hermes kanban unblock``. Hermes sends
no gateway notification for the ``scheduled`` event, and the ``unblocked``
event has no notification text and does not wake the orchestrator.

The hold is active only when ``peak_hold.enabled`` in ``config.json`` is true,
the shared switch file allows it (absent file means on), and the time is
inside the window.

The GLM review pass (decision document
``docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md``): a card that
a GLM reviewer blocked with a reason that starts with
``jev-glm-review-pass`` is passed to the board's Opus reviewer with
``hermes kanban assign`` and then ``hermes kanban unblock``. This part of
every ``run`` of ``scripts/jev-peak-hold`` is independent of
``peak_hold.enabled``, of the on/off switch and of the window, and it runs no
command when the process itself was started by a worker (``worker_session``).

The release of cards held in review (decision item 6, section 5 way 2): a GLM
review run that started inside the hold window blocks its own card through
the plugin with the hold reason (``glm_review.hold_action``). ``run`` releases
such a card with ``hermes kanban unblock``, which returns it to ``review`` on
the same GLM reviewer, when the hold is not active or the time in its reason
has passed (``plan_review_release``, ``apply_review_release``). This part also
runs no command in a process that a worker started.

Changes to cards go through ``hermes kanban --board <board> ...`` commands only.
Reads go through the documented commands ``hermes kanban --board <board> show
<id> --json`` and ``hermes kanban --board <board> list --status <status>
[--assignee <profile>] --json`` (``show_card``, ``list_cards``; decision record
``docs/decisions/261120-plugin-behaviour-across-hermes-updates.md``, row J14).
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

try:  # loaded as the plugin package
    from . import jev_log
except ImportError:  # loaded directly by scripts/jev-peak-hold and the tests
    import jev_log  # type: ignore[no-redef]

DEFAULT_STATE_DIR = "/Users/chanbla11mit/.hermes/jev"
STATE_DIR_ENV = "HERMES_JEV_STATE_DIR"
SWITCH_FILE_NAME = "peak-hold.json"
DEFAULT_MARKER = "jev-peak-hold"
GLM_REVIEW_PASS_PREFIX = "jev-glm-review-pass"
# Any of these environment variables marks a process as a dispatcher-started
# worker or as a process that one started.
WORKER_SESSION_ENV_NAMES = ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID",
                            "HERMES_DELEGATED_CHILD_CONTEXT")
DEFAULT_KANBAN_HOME = "/Users/chanbla11mit/.hermes"
READ_ERROR_STATE_FILE_NAME = "read-error-state.json"
READ_ERROR_LOG_INTERVAL_SECONDS = 3600


# --- absent Hermes names ------------------------------------------------------

_LOGGER = logging.getLogger("jev")
# The Hermes names that this process has already reported with a WARNING record.
WARNED_HERMES_NAMES: set = set()


def warn_missing_hermes_name(name: str, feature: str) -> None:
    """Write one Python ``logging`` record at level WARNING per process for
    each absent Hermes name (decision record
    ``docs/decisions/261120-plugin-behaviour-across-hermes-updates.md``,
    change 2). ``name`` and ``feature`` are fixed texts of the plugin; the
    record holds no card text, tool output, token or credential. Never raises.
    """
    try:
        if name in WARNED_HERMES_NAMES:
            return
        WARNED_HERMES_NAMES.add(name)
        _LOGGER.warning("jev: the Hermes name %s is absent; jev turns off %s", name, feature)
    except Exception:
        pass


SOURCE_STATUS_NAME = "payload field source_status of the Kanban event blocked"
SOURCE_STATUS_FEATURE = "the GLM review pass and the release of GLM review runs held in review"


# --- window ---------------------------------------------------------------

def _hhmm(value: Any, default: str) -> dtime:
    try:
        hours, minutes = str(value or default).split(":")
        return dtime(int(hours), int(minutes))
    except Exception:
        hours, minutes = default.split(":")
        return dtime(int(hours), int(minutes))


def local_time(now: datetime, cfg: Mapping[str, Any]) -> datetime:
    """``now`` converted to the configured time zone (naive values are taken as that zone)."""
    zone = ZoneInfo(str(cfg.get("timezone") or "Asia/Seoul"))
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def in_window(now: datetime, cfg: Mapping[str, Any]) -> bool:
    """True from ``start`` (inclusive) to ``end`` (exclusive) on the configured weekdays."""
    local = local_time(now, cfg)
    weekdays = cfg.get("weekdays")
    if not isinstance(weekdays, list):
        weekdays = [0, 1, 2, 3, 4]
    if local.weekday() not in weekdays:
        return False
    start = _hhmm(cfg.get("start"), "15:00")
    end = _hhmm(cfg.get("end"), "19:00")
    return start <= local.time().replace(tzinfo=None) < end


def held_until(now: datetime, cfg: Mapping[str, Any]) -> str:
    """The release time for a hold placed at ``now``: ``end`` on the same local day."""
    local = local_time(now, cfg)
    end = _hhmm(cfg.get("end"), "19:00")
    return local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0).isoformat()


# --- owner switch -----------------------------------------------------------

def switch_path() -> Path:
    base = os.environ.get(STATE_DIR_ENV, "").strip() or DEFAULT_STATE_DIR
    return Path(base) / SWITCH_FILE_NAME


def read_switch() -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Return ``(enabled, content, error_class)``.

    An absent file means on. A file that cannot be read or parsed, or whose
    ``enabled`` value is not true or false, is treated as on and returns the
    error class so the caller can log it.
    """
    path = switch_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True, {}, None
    except Exception as exc:
        return True, {}, type(exc).__name__
    try:
        content = json.loads(text)
    except Exception as exc:
        return True, {}, type(exc).__name__
    if not isinstance(content, dict) or not isinstance(content.get("enabled"), bool):
        return True, {}, "InvalidSwitchFile"
    return content["enabled"], content, None


def write_switch(enabled: bool, changed_by: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Write the switch file atomically with mode 0600 and return its content."""
    path = switch_path()
    jev_log.ensure_private_dir(path.parent)
    stamp = (now or datetime.now()).astimezone().isoformat(timespec="seconds")
    content = {"enabled": bool(enabled), "changed_at": stamp, "changed_by": str(changed_by)}
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (json.dumps(content) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return content


def hold_active(config: Mapping[str, Any], now: datetime) -> Tuple[bool, Optional[str]]:
    """Return ``(active, switch_error_class)`` for ``now``."""
    cfg = config.get("peak_hold") or {}
    switch_on, _content, error_class = read_switch()
    if not cfg.get("enabled", False) or not switch_on:
        return False, error_class
    return in_window(now, cfg), error_class


def log_switch_error(error_class: Optional[str]) -> None:
    if error_class:
        jev_log.write("decisions", {"event": "switch_error", "applied": False, "error_class": error_class})


# --- configuration lookups --------------------------------------------------

def glm_workers_by_board(config: Mapping[str, Any]) -> Dict[str, List[str]]:
    """The GLM worker names of each board, in order and with no name twice.

    For each board of ``routing.boards`` the returned list holds the non-empty
    entries of the board's list ``glm_workers``, then, for each entry of the
    board's ``routes`` in the order of the list, the non-empty entries of the
    board's list that the route names in ``assignee_from``, when that value is
    a non-empty string other than ``glm_workers`` and other than
    ``implementation_workers``. A route counts whether its ``enabled`` is true
    or false: a card that is already assigned to such a worker must still be
    held, cleared at review and moved to a Claude worker after the route is
    turned off. ``implementation_workers`` is excluded so that a configuration
    error never makes a Claude worker count as a GLM worker. A board whose
    result is empty is left out. Nothing is raised when ``routes`` is absent
    or is not a list, when a route entry is not a mapping, or when the named
    list is absent.
    """
    boards = ((config.get("routing") or {}).get("boards") or {})
    out: Dict[str, List[str]] = {}
    for board, entry in boards.items():
        entry = entry or {}
        lists: List[Any] = [entry.get("glm_workers")]
        routes = entry.get("routes")
        if isinstance(routes, list):
            for route in routes:
                if not isinstance(route, Mapping):
                    continue
                list_name = route.get("assignee_from")
                if (not isinstance(list_name, str) or not list_name
                        or list_name in ("glm_workers", "implementation_workers")):
                    continue
                lists.append(entry.get(list_name))
        workers: List[str] = []
        for names in lists:
            for name in names or []:
                if name and str(name) not in workers:
                    workers.append(str(name))
        if workers:
            out[str(board)] = workers
    return out


def all_glm_workers(config: Mapping[str, Any]) -> set:
    return {w for workers in glm_workers_by_board(config).values() for w in workers}


def glm_reviewer_pairs(config: Mapping[str, Any]) -> Dict[str, Tuple[str, str]]:
    """``{board: (glm_reviewer, opus_reviewer)}`` for boards that name both.

    The first entry of the board's ``glm_reviewers`` list is the GLM reviewer;
    ``opus_reviewer`` is the board's Opus reviewer. A board without either name
    is left out (the decision names one GLM reviewer per board, so there is no
    second entry to choose). Nothing is raised when the values are absent or
    are not strings.
    """
    boards = ((config.get("routing") or {}).get("boards") or {})
    out: Dict[str, Tuple[str, str]] = {}
    for board, entry in boards.items():
        entry = entry or {}
        reviewers = entry.get("glm_reviewers")
        glm_reviewer = None
        if isinstance(reviewers, (list, tuple)):
            named = [str(name) for name in reviewers if isinstance(name, str) and name.strip()]
            if named:
                glm_reviewer = named[0]
        opus_reviewer = entry.get("opus_reviewer")
        if glm_reviewer and isinstance(opus_reviewer, str) and opus_reviewer.strip():
            out[str(board)] = (glm_reviewer, opus_reviewer.strip())
    return out


def marker(config: Mapping[str, Any]) -> str:
    return str((config.get("peak_hold") or {}).get("marker") or DEFAULT_MARKER)


def hold_reason(config: Mapping[str, Any], until: str) -> str:
    return f"{marker(config)} until {until}"


def carries_marker(reason: Any, mark: str) -> bool:
    return isinstance(reason, str) and (reason == mark or reason.startswith(mark + " "))


def until_from_reason(reason: str, mark: str) -> Optional[str]:
    prefix = mark + " until "
    if not reason.startswith(prefix):
        return None
    return reason[len(prefix):].strip() or None


def kanban_home(config: Mapping[str, Any]) -> Path:
    override = os.environ.get("HERMES_KANBAN_HOME", "").strip()
    if override:
        return Path(override)
    return Path(str((config.get("kanban") or {}).get("home") or DEFAULT_KANBAN_HOME))


def kanban_db_path(config: Mapping[str, Any], board: str) -> Path:
    """Board database path, following Hermes: ``default`` lives at ``<home>/kanban.db``."""
    home = kanban_home(config)
    if board == "default":
        return home / "kanban.db"
    return home / "kanban" / "boards" / board / "kanban.db"


# --- board reads ------------------------------------------------------------

class KanbanReadError(Exception):
    """A ``hermes kanban ... --json`` read failed. The callers record the class
    name of the subclass as the error class, in the form that ``run_kanban``
    uses for a change command. The message is the board name only, because
    the command output can repeat card text."""


class CommandNotFound(KanbanReadError):
    pass


class CommandTimeout(KanbanReadError):
    pass


class CommandFailed(KanbanReadError):
    pass


class UnexpectedOutput(KanbanReadError):
    pass


def _command_timeout(config: Mapping[str, Any]) -> float:
    try:
        return float((config.get("kanban") or {}).get("command_timeout_seconds") or 30)
    except (TypeError, ValueError):
        return 30.0


def _read_kanban(config: Mapping[str, Any], board: str, args: List[str],
                 command: Optional[str]) -> subprocess.CompletedProcess:
    """Run ``<hermes> kanban --board <board> <args> --json`` and return the finished process."""
    argv = hermes_argv(config, command) + ["kanban", "--board", board] + list(args) + ["--json"]
    try:
        # Hermes prints the JSON with ensure_ascii=False; UTF-8 is set here
        # because the locale encoding is ASCII when LANG is not set.
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=_command_timeout(config), check=False)
    except FileNotFoundError:
        raise CommandNotFound(board) from None
    except subprocess.TimeoutExpired:
        raise CommandTimeout(board) from None


def _parse_output(text: str, board: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        raise UnexpectedOutput(board) from None


def show_card(config: Mapping[str, Any], board: str, task_id: str,
              command: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """One card from ``hermes kanban --board <board> show <task_id> --json``, or
    None when Hermes reports that the task does not exist.

    The object has ``task`` (with ``status``, ``assignee`` and ``body``),
    ``events`` (each with ``kind``, ``payload`` and ``run_id``, oldest first)
    and ``runs`` (each with ``id``, ``profile`` and ``started_at``) (Hermes
    ``hermes_cli/kanban.py`` ``_cmd_show``; ``kanban.md``). Every other
    failure raises a ``KanbanReadError``. Hermes refuses no ``show`` call in a
    worker session, so the middleware uses only this read.
    """
    completed = _read_kanban(config, board, ["show", task_id], command)
    if completed.returncode != 0:
        # Hermes v0.23.3 prints "no such task: <id>" for an unknown task. When a
        # later Hermes prints another text, the call is a read error instead;
        # every caller then leaves the card unchanged, as for a missing card,
        # and only the recorded reason differs.
        if f"no such task: {task_id}" in (completed.stderr or ""):
            return None
        raise CommandFailed(board)
    card = _parse_output(completed.stdout, board)
    if (not isinstance(card, dict) or not isinstance(card.get("task"), dict)
            or not isinstance(card.get("events"), list) or not isinstance(card.get("runs"), list)):
        raise UnexpectedOutput(board)
    return card


def list_cards(config: Mapping[str, Any], board: str, status: str, assignee: Optional[str] = None,
               command: Optional[str] = None) -> List[Dict[str, Any]]:
    """The tasks of ``hermes kanban --board <board> list --status <status>
    [--assignee <assignee>] --json``, in task ID order (the order of the
    earlier SQLite reads; Hermes sorts by priority).

    Every failure raises a ``KanbanReadError``. Hermes refuses ``list`` in a
    process that a dispatched worker started, because ``list`` first runs
    ``recompute_ready``, which changes the board; only the passes of
    ``scripts/jev-peak-hold`` call this function.
    """
    args = ["list", "--status", status] + (["--assignee", assignee] if assignee else [])
    completed = _read_kanban(config, board, args, command)
    if completed.returncode != 0:
        raise CommandFailed(board)
    tasks = _parse_output(completed.stdout, board)
    if not isinstance(tasks, list) or not all(isinstance(t, dict) and isinstance(t.get("id"), str)
                                              for t in tasks):
        raise UnexpectedOutput(board)
    return sorted(tasks, key=lambda task: task["id"])


def event_payload(raw: Any) -> Dict[str, Any]:
    """The payload of one event as a dict, or an empty dict (never raises).

    ``show --json`` gives the parsed payload; a JSON text is parsed as well.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def newest_event(card: Mapping[str, Any], kind: str) -> Optional[Mapping[str, Any]]:
    """The newest event of ``kind`` in a ``show_card`` result, or None when there is none."""
    found = None
    for event in card.get("events") or []:
        if isinstance(event, Mapping) and event.get("kind") == kind:
            found = event
    return found


def block_kind(card: Mapping[str, Any]) -> Optional[str]:
    """The ``kind`` of the newest ``blocked`` event (``kanban.md``), used in
    place of the ``tasks.block_kind`` column, which ``show --json`` does not give."""
    event = newest_event(card, "blocked")
    kind = event_payload(event.get("payload")).get("kind") if event is not None else None
    return kind if isinstance(kind, str) else None


def _held_reason(card: Mapping[str, Any], mark: str) -> Optional[str]:
    """The reason of the newest ``scheduled`` event when the card is ``scheduled``
    and that reason carries the marker, else None."""
    if card["task"].get("status") != "scheduled":
        return None
    event = newest_event(card, "scheduled")
    payload = event_payload(event.get("payload")) if event is not None else {}
    if event is not None and "reason" not in payload:
        warn_missing_hermes_name("payload field reason of the Kanban event scheduled",
                                 "the recognition of cards that the peak-hours hold scheduled")
    reason = payload.get("reason")
    return reason if carries_marker(reason, mark) else None


def card_hold_state(config: Mapping[str, Any], board: str, task_id: str, mark: str,
                    command: Optional[str] = None) -> Optional[Tuple[str, Optional[str], bool]]:
    """``(status, assignee, carries_marker)`` of one card, or None when it does not exist.

    ``carries_marker`` is true only for a ``scheduled`` card whose latest
    ``scheduled`` event reason carries the marker.
    """
    card = show_card(config, board, task_id, command)
    if card is None:
        return None
    task = card["task"]
    return str(task.get("status")), task.get("assignee"), _held_reason(card, mark) is not None


def holdable_cards(config: Mapping[str, Any], board: str, workers: Iterable[str],
                   command: Optional[str] = None) -> List[Tuple[str, str]]:
    """``(task_id, assignee)`` for ``ready`` and ``todo`` cards assigned to ``workers``, in ID order."""
    workers = list(workers)
    if not workers:
        return []
    tasks = list_cards(config, board, "ready", command=command) + list_cards(config, board, "todo", command=command)
    return sorted((task["id"], str(task["assignee"])) for task in tasks if task.get("assignee") in workers)


def held_cards(config: Mapping[str, Any], board: str, mark: str,
               command: Optional[str] = None) -> List[Tuple[str, Optional[str], str]]:
    """``(task_id, assignee, reason)`` for ``scheduled`` cards whose latest ``scheduled``
    event reason carries the marker. Other scheduled or blocked cards are never returned."""
    out = []
    for task in list_cards(config, board, "scheduled", command=command):
        card = show_card(config, board, task["id"], command)
        if card is None:
            continue
        reason = _held_reason(card, mark)
        if reason is not None:
            out.append((task["id"], card["task"].get("assignee"), reason))
    return out


# --- the GLM review pass (decision item 5) -----------------------------------

def _run_profile(card: Mapping[str, Any], run_id: Any) -> Optional[str]:
    """The ``profile`` of the run ``run_id`` of the card, or None when absent."""
    if not isinstance(run_id, int):
        return None
    for run in card.get("runs") or []:
        if isinstance(run, Mapping) and run.get("id") == run_id:
            return run.get("profile")
    return None


def _card_matches_pass(card: Optional[Mapping[str, Any]], glm_reviewer: str,
                       opus_reviewer: str) -> bool:
    """True when the card (a ``show_card`` result) meets every selection condition of decision item 5.3.

    ``blocked`` status, the newest ``blocked`` event reason starts with the
    pass prefix and its payload records ``source_status: review`` (Hermes
    ``block_task`` writes it; the value comes from ``_retry_status_for_run``,
    which reads the ``source_status`` of the run's ``claimed`` event), the run
    of that event (its ``run_id`` matched with the card's ``runs``) is the GLM
    reviewer, and the assignee is the GLM reviewer or the Opus reviewer. A
    missing card and any unexpected shape (a payload that is not an object, a
    missing run) make the answer False.
    """
    if card is None:
        return False
    task = card["task"]
    if str(task.get("status")) != "blocked":
        return False
    if task.get("assignee") not in (glm_reviewer, opus_reviewer):
        return False
    event = newest_event(card, "blocked")
    if event is None:
        return False
    payload = event_payload(event.get("payload"))
    reason = payload.get("reason")
    if not (isinstance(reason, str) and reason.startswith(GLM_REVIEW_PASS_PREFIX)):
        return False
    if "source_status" not in payload:
        warn_missing_hermes_name(SOURCE_STATUS_NAME, SOURCE_STATUS_FEATURE)
    if payload.get("source_status") != "review":
        return False
    return _run_profile(card, event.get("run_id")) == glm_reviewer


def plan_glm_review_pass(config: Mapping[str, Any], boards: Mapping[str, Path]
                         ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Planned passes for ``boards`` (board name to database path; only the
    names are used, the cards are read with ``list_cards`` and ``show_card``).

    Returns ``(passes, read_errors)``. A pass is ``{"board", "task_id",
    "glm_reviewer", "opus_reviewer", "assign"}`` where ``assign`` is true when
    the card is not yet assigned to the Opus reviewer. A board that cannot be
    read adds ``{"board", "error_class"}`` to ``read_errors`` and does not
    stop the other boards. Passes are in task ID order. This is independent of
    ``peak_hold.enabled``, of the switch and of the window.
    """
    passes: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    pairs = glm_reviewer_pairs(config)
    for board in boards:
        pair = pairs.get(board)
        if pair is None:
            continue
        glm_reviewer, opus_reviewer = pair
        try:
            for task in list_cards(config, board, "blocked"):
                # _card_matches_pass needs one of the two assignees; this saves a show call per other card.
                if task.get("assignee") not in (glm_reviewer, opus_reviewer):
                    continue
                card = show_card(config, board, task["id"])
                if card is not None and _card_matches_pass(card, glm_reviewer, opus_reviewer):
                    passes.append({"board": board, "task_id": task["id"], "glm_reviewer": glm_reviewer,
                                   "opus_reviewer": opus_reviewer,
                                   "assign": card["task"].get("assignee") != opus_reviewer})
        except Exception as exc:
            errors.append({"board": board, "error_class": type(exc).__name__})
    return passes, errors


def still_passable(config: Mapping[str, Any], board: str, task_id: str,
                   command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """``(passable, read error class)``: passable when the card still meets
    every selection condition of the pass for ``board``.

    ``apply_glm_review_pass`` reads the card again just before the commands,
    as ``apply`` does with ``still_holdable`` for holds, so a card that a
    person or the orchestrator changed between the selection and the commands
    is skipped. A read error returns ``(False, <error class>)``, so the card
    stays unchanged until the next run.
    """
    pair = glm_reviewer_pairs(config).get(board)
    if pair is None:
        return False, None
    glm_reviewer, opus_reviewer = pair
    try:
        return _card_matches_pass(show_card(config, board, task_id, command), glm_reviewer, opus_reviewer), None
    except Exception as exc:
        return False, type(exc).__name__


def log_glm_review_pass(board: str, task_id: str, glm_reviewer: str, opus_reviewer: str,
                        assigned: Optional[bool], unblocked: bool, skipped: bool,
                        error_class: Optional[str]) -> None:
    """One ``decisions`` record per passed card; a failure to write is ignored.

    ``assigned`` is true or false when the assign command ran, and null when it
    was not needed. No card text and no reason text is written.
    """
    try:
        jev_log.write("decisions", {
            "event": "glm_review_pass", "board": board, "task_id": task_id,
            "glm_reviewer": glm_reviewer, "opus_reviewer": opus_reviewer,
            "assigned": assigned, "unblocked": unblocked, "skipped": skipped,
            "error_class": error_class,
        })
    except Exception:
        pass


def apply_glm_review_pass(config: Mapping[str, Any], passes: List[Mapping[str, Any]],
                          command: Optional[str] = None,
                          boards: Optional[Mapping[str, Path]] = None) -> List[Dict[str, Any]]:
    """Pass each planned card to the Opus reviewer; one decisions record each.

    With ``boards`` (board name to database path; only the names are used)
    each card is checked again with ``still_passable`` first, read with the
    same ``command``; a card that no longer meets the selection
    conditions, or that cannot be read again, is skipped (no command). For a
    card that is not yet assigned to the Opus reviewer, ``hermes kanban assign``
    runs first; only after it succeeded, or when it was not needed,
    ``hermes kanban unblock`` runs. A failed command stops the steps for that
    card; the next run of the script tries again (a card already assigned to
    the Opus reviewer gets only ``unblock``).
    """
    results: List[Dict[str, Any]] = []
    for item in passes:
        board = str(item["board"])
        task_id = str(item["task_id"])
        glm_reviewer = str(item["glm_reviewer"])
        opus_reviewer = str(item["opus_reviewer"])
        if boards is not None and board in boards:
            passable, read_error = still_passable(config, board, task_id, command)
            if not passable:
                log_glm_review_pass(board, task_id, glm_reviewer, opus_reviewer, None, False,
                                    True, read_error)
                results.append({**item, "assigned": None, "unblocked": False,
                                "skipped": True, "error_class": read_error})
                continue
        assigned: Optional[bool] = None
        unblocked = False
        error_class: Optional[str] = None
        if item.get("assign"):
            ok, error_class = run_kanban(config, board, ["assign", task_id, opus_reviewer], command)
            assigned = ok
            if not ok:
                log_glm_review_pass(board, task_id, glm_reviewer, opus_reviewer, assigned,
                                    unblocked, False, error_class)
                results.append({**item, "assigned": assigned, "unblocked": unblocked,
                                "skipped": False, "error_class": error_class})
                continue
        ok, unblock_error = run_kanban(config, board, ["unblock", task_id], command)
        unblocked = ok
        error_class = error_class if error_class else unblock_error
        log_glm_review_pass(board, task_id, glm_reviewer, opus_reviewer, assigned, unblocked,
                            False, error_class)
        results.append({**item, "assigned": assigned, "unblocked": unblocked,
                        "skipped": False, "error_class": error_class})
    return results


# --- the release of GLM review runs held in review (decision item 6) -----------

RELEASED_TO_REVIEW = "review"


def first_glm_reviewer_by_board(config: Mapping[str, Any]) -> Dict[str, str]:
    """``{board: first entry of the board's glm_reviewers}`` for boards that name one.

    Nothing is raised when the list is absent or is not a list.
    """
    boards = ((config.get("routing") or {}).get("boards") or {})
    out: Dict[str, str] = {}
    for board, entry in boards.items():
        reviewers = (entry or {}).get("glm_reviewers")
        if isinstance(reviewers, (list, tuple)):
            named = [str(name) for name in reviewers if isinstance(name, str) and name.strip()]
            if named:
                out[str(board)] = named[0]
    return out


def _review_hold_reason(card: Optional[Mapping[str, Any]], glm_reviewer: str,
                        mark: str) -> Optional[str]:
    """The reason of the newest ``blocked`` event when the card (a ``show_card``
    result) is held in review, else None.

    Held in review: status ``blocked``, assignee ``glm_reviewer``, and the
    newest ``blocked`` event has a ``reason`` that carries the marker
    (``carries_marker``) and ``source_status`` ``review``. This is the block
    that a GLM review run makes through the plugin (``glm_review.hold_action``);
    ``hermes kanban unblock`` returns such a card to ``review`` with the same
    assignee.
    """
    if card is None:
        return None
    task = card["task"]
    if str(task.get("status")) != "blocked" or task.get("assignee") != glm_reviewer:
        return None
    event = newest_event(card, "blocked")
    if event is None:
        return None
    payload = event_payload(event.get("payload"))
    reason = payload.get("reason")
    if not carries_marker(reason, mark):
        return None
    if "source_status" not in payload:
        warn_missing_hermes_name(SOURCE_STATUS_NAME, SOURCE_STATUS_FEATURE)
    if payload.get("source_status") != "review":
        return None
    return reason


def _until_passed(until: Optional[str], now: datetime, cfg: Mapping[str, Any]) -> bool:
    """True when ``until`` (ISO 8601) is not later than ``now``; False when it is absent or unreadable."""
    if not until:
        return False
    try:
        return local_time(now, cfg) >= local_time(datetime.fromisoformat(until), cfg)
    except Exception:
        return False


def plan_review_release(config: Mapping[str, Any], now: datetime, boards: Mapping[str, Path]
                        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Planned releases of cards held in review, for ``boards`` (board name to
    database path; only the names are used).

    Returns ``(releases, read_errors)``. A card held in review
    (``_review_hold_reason``, with the first entry of the board's
    ``glm_reviewers``) is released when the hold is not active (outside the
    window, switch off or ``peak_hold.enabled`` false) or when the time in its
    reason (``until_from_reason``) has passed. A release is ``{"action":
    "release", "board", "task_id", "assignee", "held_until", "released_to":
    "review"}``. A board that cannot be read adds ``{"board",
    "error_class"}`` to ``read_errors`` and does not stop the other boards.
    """
    active, _switch_error = hold_active(config, now)
    cfg = config.get("peak_hold") or {}
    mark = marker(config)
    reviewers = first_glm_reviewer_by_board(config)
    releases: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for board in boards:
        glm_reviewer = reviewers.get(board)
        if glm_reviewer is None:
            continue
        try:
            for task in list_cards(config, board, "blocked", glm_reviewer):
                task_id = task["id"]
                reason = _review_hold_reason(show_card(config, board, task_id), glm_reviewer, mark)
                if reason is None:
                    continue
                until = until_from_reason(reason, mark)
                if active and not _until_passed(until, now, cfg):
                    continue
                releases.append({"action": "release", "board": board, "task_id": task_id,
                                 "assignee": glm_reviewer, "held_until": until,
                                 "released_to": RELEASED_TO_REVIEW})
        except Exception as exc:
            errors.append({"board": board, "error_class": type(exc).__name__})
    return releases, errors


def still_held_in_review(config: Mapping[str, Any], board: str, task_id: str,
                         command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """``(held, read error class)``: held when the card still meets the selection of
    ``plan_review_release``. A read error returns ``(False, <error class>)``, so the
    card stays ``blocked`` until the next run."""
    glm_reviewer = first_glm_reviewer_by_board(config).get(board)
    if glm_reviewer is None:
        return False, None
    try:
        card = show_card(config, board, task_id, command)
        return _review_hold_reason(card, glm_reviewer, marker(config)) is not None, None
    except Exception as exc:
        return False, type(exc).__name__


def apply_review_release(config: Mapping[str, Any], releases: List[Mapping[str, Any]],
                         command: Optional[str] = None,
                         boards: Optional[Mapping[str, Path]] = None) -> List[Dict[str, Any]]:
    """Release each planned card with ``hermes kanban unblock``; one ``release`` record each.

    With ``boards`` (board name to database path; only the names are used)
    each card is read again with ``still_held_in_review`` first, with the
    same ``command``; a card that no longer meets the
    selection, or that cannot be read again, is skipped (``skipped`` true, no
    command, no record). The record is the ``release`` record of
    ``log_release`` with the added field ``released_to: review``. A failed
    command leaves the card ``blocked``; the next run tries again. No other
    ``hermes kanban`` command runs.
    """
    results: List[Dict[str, Any]] = []
    for item in releases:
        board = str(item["board"])
        task_id = str(item["task_id"])
        if boards is not None and board in boards:
            held, read_error = still_held_in_review(config, board, task_id, command)
            if not held:
                results.append({**item, "applied": False, "skipped": True, "error_class": read_error})
                continue
        ok, error_class = release_card(config, board, task_id, command)
        log_release(board, task_id, item.get("assignee"), item.get("held_until"), ok, error_class,
                    released_to=RELEASED_TO_REVIEW)
        results.append({**item, "applied": ok, "skipped": False, "error_class": error_class})
    return results


# --- board changes ------------------------------------------------------------

def hermes_argv(config: Mapping[str, Any], command: Optional[str] = None) -> List[str]:
    kanban_cfg = config.get("kanban") or {}
    return shlex.split(command or str(kanban_cfg.get("hermes_command") or "hermes"))


def command_resolves(config: Mapping[str, Any], command: Optional[str] = None) -> bool:
    """True when the ``hermes`` command names an executable file (a path or a ``PATH`` entry)."""
    try:
        base = hermes_argv(config, command)
    except ValueError:
        return False
    if not base:
        return False
    program = base[0]
    if os.sep in program:
        return os.path.isfile(program) and os.access(program, os.X_OK)
    return shutil.which(program) is not None


def worker_session() -> bool:
    """True inside a dispatcher-started worker session or in a process that
    one started.

    ``HERMES_KANBAN_TASK`` marks a dispatcher-started worker;
    ``HERMES_KANBAN_RUN_ID`` marks the same for the five run-lifecycle tools;
    ``HERMES_DELEGATED_CHILD_CONTEXT`` marks a process that a worker started
    (directly or through other processes). In all three ``hermes kanban
    schedule``, ``hermes kanban unblock`` and ``hermes kanban assign`` refuse
    the card or are refused for a delegated child (Hermes
    ``hermes_cli/kanban.py`` ``_DELEGATED_CHILD_DENIED_ACTIONS``,
    ``hermes_cli/kanban_db.py`` ``_assert_not_delegated_child_mutation`` and
    the ``unblock`` command).
    """
    return any(os.environ.get(name, "").strip() for name in WORKER_SESSION_ENV_NAMES)


def run_kanban(config: Mapping[str, Any], board: Optional[str], args: List[str],
               command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Run ``<hermes> kanban [--board <board>] <args>``; ``(ok, error_class)``.

    The command's output is not returned or logged because it can repeat card text.
    """
    base = hermes_argv(config, command)
    argv = base + ["kanban"] + (["--board", board] if board else []) + list(args)
    try:
        completed = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=_command_timeout(config), check=False)
    except FileNotFoundError:
        return False, "CommandNotFound"
    except subprocess.TimeoutExpired:
        return False, "CommandTimeout"
    except Exception as exc:
        return False, type(exc).__name__
    if completed.returncode != 0:
        return False, "CommandFailed"
    return True, None


def kanban_option_absent(config: Mapping[str, Any], board: str, verb: str, option: str,
                         command: Optional[str] = None) -> bool:
    """True when ``<hermes> kanban --board <board> <verb> --help`` exits 0 and
    its output does not name ``option``; False on every other outcome. The
    help text holds no card text."""
    try:
        argv = hermes_argv(config, command) + ["kanban", "--board", board, verb, "--help"]
        completed = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                                   errors="replace", timeout=_command_timeout(config), check=False)
    except Exception:
        return False
    return completed.returncode == 0 and option not in (completed.stdout or "")


def hold_card(config: Mapping[str, Any], board: str, task_id: str, until: str,
              command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    return run_kanban(config, board, ["schedule", task_id, hold_reason(config, until)], command)


def release_card(config: Mapping[str, Any], board: str, task_id: str,
                 command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    return run_kanban(config, board, ["unblock", task_id], command)


def log_hold(board: str, task_id: Optional[str], assignee: Optional[str], until: Optional[str],
             applied: bool, error_class: Optional[str], **extra: Any) -> None:
    jev_log.write("decisions", {
        "event": "hold", "board": board, "task_id": task_id, "original_assignee": assignee,
        "new_assignee": assignee, "applied": applied, "error_class": error_class, "held_until": until,
        **extra,
    })


def log_release(board: str, task_id: str, assignee: Optional[str], until: Optional[str],
                applied: bool, error_class: Optional[str], **extra: Any) -> None:
    jev_log.write("decisions", {
        "event": "release", "board": board, "task_id": task_id, "original_assignee": assignee,
        "new_assignee": assignee, "applied": applied, "error_class": error_class, "held_until": until,
        **extra,
    })


# --- one pass over the boards (used by scripts/jev-peak-hold) ---------------

def _plan_board(config: Mapping[str, Any], board: str, workers: List[str], mark: str, active: bool,
                until: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    held = held_cards(config, board, mark)
    if active:
        for task_id, assignee in holdable_cards(config, board, workers):
            actions.append({"action": "hold", "board": board, "task_id": task_id,
                            "assignee": assignee, "held_until": until})
        for task_id, assignee, reason in held:
            if assignee not in workers:
                actions.append({"action": "release", "board": board, "task_id": task_id,
                                "assignee": assignee, "held_until": until_from_reason(reason, mark)})
    else:
        for task_id, assignee, reason in held:
            actions.append({"action": "release", "board": board, "task_id": task_id,
                            "assignee": assignee, "held_until": until_from_reason(reason, mark)})
    return actions


def plan(config: Mapping[str, Any], now: datetime, boards: Mapping[str, Path],
         *, force_release: bool = False
         ) -> Tuple[List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
    """Planned holds and releases for ``boards`` (board name to database path;
    only the names are used).

    Returns ``(actions, switch_error_class, read_errors)``. When the hold is
    active, ready and todo cards of the board's GLM workers are held, and cards
    held with the marker that are no longer assigned to a GLM worker are
    released. When it is not active (outside the window, switch off or
    ``peak_hold.enabled`` false), every card held with the marker is released.
    A board that cannot be read adds ``{"board", "error_class"}`` to
    ``read_errors`` and does not stop the other boards.
    """
    active, switch_error = hold_active(config, now)
    if force_release:
        active = False
    cfg = config.get("peak_hold") or {}
    mark = marker(config)
    workers_by_board = glm_workers_by_board(config)
    until = held_until(now, cfg)
    actions: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for board in boards:
        try:
            actions.extend(_plan_board(config, board, workers_by_board.get(board, []), mark, active, until))
        except Exception as exc:
            errors.append({"board": board, "error_class": type(exc).__name__})
    return actions, switch_error, errors


def still_holdable(config: Mapping[str, Any], board: str, task_id: str,
                   command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """``(holdable, read error class)``: holdable when the card is still ``ready``
    or ``todo`` and assigned to a GLM worker of ``board``.

    ``apply`` reads the card again just before each hold, so a card that was
    reassigned to a Claude worker after ``plan`` read the board (for example by
    the reassignment after change requests of ``routing.handle_request_changes``) is not
    held. A read error returns ``(False, <error class>)``, so the card stays
    unchanged until the next run.
    """
    try:
        card = show_card(config, board, task_id, command)
    except Exception as exc:
        return False, type(exc).__name__
    task = card["task"] if card is not None else None
    return (task is not None and task.get("status") in ("ready", "todo")
            and task.get("assignee") in glm_workers_by_board(config).get(board, [])), None


def apply(config: Mapping[str, Any], actions: List[Dict[str, Any]],
          command: Optional[str] = None, boards: Optional[Mapping[str, Path]] = None) -> List[Dict[str, Any]]:
    """Perform ``actions`` with ``hermes kanban`` commands; one decisions record each.

    With ``boards`` (board name to database path; only the names are used)
    each planned hold is checked again with ``still_holdable`` first, read
    with the same ``command``; a card that no longer qualifies, or
    that cannot be read again, is skipped (``skipped`` true, no command, no
    record; ``error_class`` is the read error class or None).
    """
    results = []
    for item in actions:
        if item["action"] == "hold" and boards is not None and item["board"] in boards:
            holdable, read_error = still_holdable(config, item["board"], item["task_id"], command)
            if not holdable:
                results.append({**item, "applied": False, "skipped": True, "error_class": read_error})
                continue
        if item["action"] == "hold":
            ok, error_class = hold_card(config, item["board"], item["task_id"], item["held_until"], command)
            log_hold(item["board"], item["task_id"], item["assignee"], item["held_until"], ok, error_class)
        else:
            ok, error_class = release_card(config, item["board"], item["task_id"], command)
            log_release(item["board"], item["task_id"], item["assignee"], item["held_until"], ok, error_class)
        results.append({**item, "applied": ok, "error_class": error_class})
    return results


def read_error_state_path() -> Path:
    return jev_log.log_dir() / READ_ERROR_STATE_FILE_NAME


def _read_error_state() -> Dict[str, str]:
    """Board name to the ISO 8601 time of its last ``read_error`` record; empty when unreadable."""
    try:
        content = json.loads(read_error_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(content, dict):
        return {}
    return {str(board): stamp for board, stamp in content.items() if isinstance(stamp, str)}


def _write_read_error_state(state: Mapping[str, str]) -> None:
    """Write the state file atomically with mode 0600; failures are ignored."""
    path = read_error_state_path()
    try:
        jev_log.ensure_private_dir(path.parent)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, (json.dumps(dict(state), sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        pass


def log_read_errors(errors: Iterable[Mapping[str, Any]], now: datetime) -> int:
    """Write one ``decisions`` record ``event: read_error`` per board in ``errors``,
    at most once per board per hour; return the number of records written.

    A board database that stays unreadable would otherwise write one record per
    script run (8,640 per day with the 10-second schedule). The time of the
    last record per board is kept in ``<log dir>/read-error-state.json``, which
    holds only board names and timestamps. A record is written when the board
    has no earlier time, when an hour or more has passed, or when the earlier
    time is later than ``now`` (a clock that moved back). The caller still
    reports every error and exits non-zero.
    """
    errors = list(errors)
    if not errors:
        return 0
    if now.tzinfo is None:
        now = now.astimezone()
    state = _read_error_state()
    written = 0
    for item in errors:
        board = str(item.get("board"))
        try:
            last = datetime.fromisoformat(state[board])
            if last.tzinfo is None:
                last = last.astimezone()
            elapsed = (now - last).total_seconds()
        except Exception:
            elapsed = None
        if elapsed is not None and 0 <= elapsed < READ_ERROR_LOG_INTERVAL_SECONDS:
            continue
        jev_log.write("decisions", {"event": "read_error", "board": item.get("board"), "applied": False,
                                    "error_class": item.get("error_class")})
        state[board] = now.isoformat(timespec="seconds")
        written += 1
    if written:
        _write_read_error_state(state)
    return written


def count_held(config: Mapping[str, Any], boards: Mapping[str, Path]) -> Tuple[int, List[Dict[str, Any]]]:
    """``(number of cards held with the marker, read_errors)`` over ``boards``
    (board name to database path; only the names are used)."""
    mark = marker(config)
    total = 0
    errors: List[Dict[str, Any]] = []
    for board in boards:
        try:
            total += len(held_cards(config, board, mark))
        except Exception as exc:
            errors.append({"board": board, "error_class": type(exc).__name__})
    return total, errors
