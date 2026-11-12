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

Changes to cards go through ``hermes kanban --board <board> ...`` commands only.
Reads use a read-only SQLite connection to the board database.
"""
from __future__ import annotations

import json
import os
import shlex
import sqlite3
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
DEFAULT_KANBAN_HOME = "/Users/chanbla11mit/.hermes"


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
    boards = ((config.get("routing") or {}).get("boards") or {})
    out: Dict[str, List[str]] = {}
    for board, entry in boards.items():
        workers = [str(w) for w in (entry or {}).get("glm_workers") or [] if w]
        if workers:
            out[str(board)] = workers
    return out


def all_glm_workers(config: Mapping[str, Any]) -> set:
    return {w for workers in glm_workers_by_board(config).values() for w in workers}


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

def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def holdable_cards(conn: sqlite3.Connection, workers: Iterable[str]) -> List[Tuple[str, str]]:
    """``(task_id, assignee)`` for ``ready`` and ``todo`` cards assigned to ``workers``."""
    workers = list(workers)
    if not workers:
        return []
    marks = ",".join("?" for _ in workers)
    rows = conn.execute(
        f"SELECT id, assignee FROM tasks WHERE status IN ('ready', 'todo') AND assignee IN ({marks}) "
        "ORDER BY id", workers).fetchall()
    return [(str(r["id"]), str(r["assignee"])) for r in rows]


def held_cards(conn: sqlite3.Connection, mark: str) -> List[Tuple[str, Optional[str], str]]:
    """``(task_id, assignee, reason)`` for ``scheduled`` cards whose latest ``scheduled``
    event reason carries the marker. Other scheduled or blocked cards are never returned."""
    out = []
    for row in conn.execute("SELECT id, assignee FROM tasks WHERE status = 'scheduled' ORDER BY id").fetchall():
        event = conn.execute(
            "SELECT payload FROM task_events WHERE task_id = ? AND kind = 'scheduled' "
            "ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
        if event is None:
            continue
        try:
            reason = (json.loads(event["payload"] or "{}") or {}).get("reason")
        except Exception:
            continue
        if carries_marker(reason, mark):
            out.append((str(row["id"]), row["assignee"], reason))
    return out


# --- board changes ------------------------------------------------------------

def run_kanban(config: Mapping[str, Any], board: Optional[str], args: List[str],
               command: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Run ``<hermes> kanban [--board <board>] <args>``; ``(ok, error_class)``.

    The command's output is not returned or logged because it can repeat card text.
    """
    kanban_cfg = config.get("kanban") or {}
    base = shlex.split(command or str(kanban_cfg.get("hermes_command") or "hermes"))
    argv = base + ["kanban"] + (["--board", board] if board else []) + list(args)
    try:
        timeout = float(kanban_cfg.get("command_timeout_seconds") or 30)
    except (TypeError, ValueError):
        timeout = 30.0
    try:
        completed = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except FileNotFoundError:
        return False, "CommandNotFound"
    except subprocess.TimeoutExpired:
        return False, "CommandTimeout"
    except Exception as exc:
        return False, type(exc).__name__
    if completed.returncode != 0:
        return False, "CommandFailed"
    return True, None


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

def plan(config: Mapping[str, Any], now: datetime, boards: Mapping[str, Path],
         *, force_release: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Planned holds and releases for ``boards`` (board name to database path).

    When the hold is active, ready and todo cards of the board's GLM workers
    are held, and marker-held cards that are no longer assigned to a GLM worker
    are released. When it is not active (outside the window, switch off or
    ``peak_hold.enabled`` false), every marker-held card is released.
    """
    active, switch_error = hold_active(config, now)
    if force_release:
        active = False
    cfg = config.get("peak_hold") or {}
    mark = marker(config)
    workers_by_board = glm_workers_by_board(config)
    until = held_until(now, cfg)
    actions: List[Dict[str, Any]] = []
    for board, path in boards.items():
        workers = workers_by_board.get(board, [])
        conn = connect_readonly(path)
        try:
            held = held_cards(conn, mark)
            if active:
                for task_id, assignee in holdable_cards(conn, workers):
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
        finally:
            conn.close()
    return actions, switch_error


def apply(config: Mapping[str, Any], actions: List[Dict[str, Any]],
          command: Optional[str] = None) -> List[Dict[str, Any]]:
    """Perform ``actions`` with ``hermes kanban`` commands; one decisions record each."""
    results = []
    for item in actions:
        if item["action"] == "hold":
            ok, error_class = hold_card(config, item["board"], item["task_id"], item["held_until"], command)
            log_hold(item["board"], item["task_id"], item["assignee"], item["held_until"], ok, error_class)
        else:
            ok, error_class = release_card(config, item["board"], item["task_id"], command)
            log_release(item["board"], item["task_id"], item["assignee"], item["held_until"], ok, error_class)
        results.append({**item, "applied": ok, "error_class": error_class})
    return results


def count_held(config: Mapping[str, Any], boards: Mapping[str, Path]) -> int:
    mark = marker(config)
    total = 0
    for _board, path in boards.items():
        conn = connect_readonly(path)
        try:
            total += len(held_cards(conn, mark))
        finally:
            conn.close()
    return total
