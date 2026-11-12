"""Append-only JSON Lines logs for the jev plugin.

One JSON object per line in ``<log dir>/<stream>.jsonl``. Files are created
with mode 0600 and the directory with mode 0700. Records hold identifiers,
sizes, probabilities, timings and token counts only; callers never pass card
text or tool output. Writing never raises: a failed write returns False so a
logging problem cannot change a tool call.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_LOG_DIR = "/Users/chanbla11mit/.hermes/jev/logs"
LOG_DIR_ENV = "HERMES_JEV_LOG_DIR"

# Field order per stream; a missing field is written as JSON null.
STREAM_FIELDS = {
    "decisions": (
        "event", "board", "task_id", "original_assignee", "new_assignee", "orchestrator_model",
        "route", "probabilities", "confidence", "applied", "not_applied_reason", "jev_latency_ms",
        "jev_input_tokens", "error_class", "held_until",
    ),
    "tool_results": (
        "event", "session_id", "tool", "chars_before", "chars_after", "chunks_kept", "chunks_total",
        "jev_latency_ms", "jev_input_tokens", "action", "reason", "error_class", "saved_file",
    ),
    "auxiliary": ("aux_task", "provider", "model", "input_tokens", "output_tokens", "status"),
}

_STREAM_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


def log_dir() -> Path:
    """The log directory: ``HERMES_JEV_LOG_DIR`` when set, else the shared default."""
    return Path(os.environ.get(LOG_DIR_ENV, "").strip() or DEFAULT_LOG_DIR)


def profile_name() -> str:
    """The Hermes profile running this process.

    ``HERMES_PROFILE`` is set by the dispatcher for workers. Otherwise the
    profile is the last path part of ``HERMES_HOME`` when that directory sits
    in a ``profiles`` directory, else ``default``.
    """
    explicit = os.environ.get("HERMES_PROFILE", "").strip()
    if explicit:
        return explicit
    home = os.environ.get("HERMES_HOME", "").strip()
    if home:
        path = Path(home)
        if path.parent.name == "profiles" and path.name:
            return path.name
    return "default"


def now_iso() -> str:
    """Current local time, ISO 8601 with the UTC offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_private_dir(path: Path) -> None:
    """Create ``path`` (and parents) and set mode 0700 on ``path``."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def build_record(stream: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Return the record with ``ts`` and ``profile`` first and every known field present."""
    out: Dict[str, Any] = {
        "ts": record.get("ts") or now_iso(),
        "profile": record.get("profile") or profile_name(),
    }
    for field in STREAM_FIELDS.get(stream, ()):
        out[field] = record.get(field)
    for key, value in record.items():
        if key not in out:
            out[key] = value
    return out


def write(stream: str, record: Dict[str, Any], *, directory: Optional[Path] = None) -> bool:
    """Append one JSON object to ``<log dir>/<stream>.jsonl``; False on any failure."""
    try:
        if not _STREAM_NAME.match(stream):
            return False
        target_dir = directory if directory is not None else log_dir()
        ensure_private_dir(target_dir)
        line = json.dumps(build_record(stream, record), ensure_ascii=False, sort_keys=False) + "\n"
        path = target_dir / f"{stream}.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except Exception:
        return False
