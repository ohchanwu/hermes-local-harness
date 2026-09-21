"""Durable, zero-LLM terminal outcome state for Hermes notifications."""
from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

TERMINAL = {"completed", "blocked", "failed", "interrupted", "timed_out", "unknown"}
HUMAN_BLOCKS = {"needs_input", "capability"}


@dataclass(frozen=True)
class Config:
    summary_max_chars: int = 240
    block_debounce_seconds: int = 15
    max_attempts: int = 4


def _now() -> int:
    return int(time.time())


def _summary(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return re.sub(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)[:limit]


def shared_outbox_path() -> Path:
    """One explicit absolute path shared by every producer and the LaunchAgent."""
    configured = os.environ.get("HERMES_TERMINAL_OUTBOX", "")
    path = Path(configured)
    if not configured or not path.is_absolute():
        raise RuntimeError("HERMES_TERMINAL_OUTBOX must be an absolute shared outbox path")
    return path


class Store:
    def __init__(self, path: str | Path, config: Config = Config()) -> None:
        self.path, self.config = Path(path), config
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _add_column(self, db: sqlite3.Connection, table: str, name: str, definition: str) -> None:
        if name not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns (
                  campaign_id TEXT PRIMARY KEY, session_id TEXT UNIQUE, task_id TEXT UNIQUE,
                  generation INTEGER NOT NULL DEFAULT 1, title TEXT NOT NULL, lane TEXT,
                  armed_at INTEGER NOT NULL, proposal_status TEXT, proposal_summary TEXT,
                  candidate_response TEXT, stopped_reason TEXT, disarmed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS arm_requests (
                  request_id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at INTEGER NOT NULL, claimed_at INTEGER, producer TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS events (
                  event_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, generation INTEGER NOT NULL,
                  terminal_status TEXT NOT NULL, title TEXT NOT NULL, short_summary TEXT NOT NULL,
                  task_id TEXT, session_id TEXT, created_at INTEGER NOT NULL, available_at INTEGER NOT NULL,
                  cancelled_at INTEGER, cancellation_reason TEXT,
                  UNIQUE(campaign_id, generation, terminal_status)
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                  event_id TEXT NOT NULL, destination TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                  lease_until INTEGER, last_error TEXT, delivered_at INTEGER,
                  PRIMARY KEY(event_id, destination), FOREIGN KEY(event_id) REFERENCES events(event_id)
                );
            """)
            self._add_column(db, "deliveries", "available_at", "INTEGER NOT NULL DEFAULT 0")
            self._add_column(db, "arm_requests", "producer", "TEXT NOT NULL DEFAULT ''")
        os.chmod(self.path, 0o600)

    def arm_direct(self, session_id: str, title: str, lane: str | None = None) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        campaign_id = f"direct:{session_id}"
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT INTO campaigns(campaign_id,session_id,title,lane,armed_at) VALUES(?,?,?,?,?)
                          ON CONFLICT(session_id) DO UPDATE SET title=excluded.title,lane=excluded.lane,armed_at=excluded.armed_at,
                          proposal_status=NULL,proposal_summary=NULL,candidate_response=NULL,stopped_reason=NULL,disarmed_at=NULL""",
                       (campaign_id, session_id, _summary(title, self.config.summary_max_chars), lane, _now()))
            db.execute("COMMIT")
        return campaign_id

    def arm_next_direct(self, title: str, producer: str = "") -> str:
        """Slash handlers lack session context; pre_llm_call claims this once with the real ID."""
        request_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO arm_requests(request_id,title,created_at,claimed_at,producer) VALUES(?,?,?,NULL,?)",
                       (request_id, _summary(title, self.config.summary_max_chars), _now(), producer))
        return request_id

    def claim_pending_direct(self, session_id: str, lane: str | None = None, producer: str = "") -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM arm_requests WHERE claimed_at IS NULL AND producer=? ORDER BY created_at LIMIT 1", (producer,)).fetchone()
            if not row:
                db.execute("COMMIT")
                return False
            db.execute("UPDATE arm_requests SET claimed_at=? WHERE request_id=?", (_now(), row["request_id"]))
            db.execute("""INSERT INTO campaigns(campaign_id,session_id,title,lane,armed_at) VALUES(?,?,?,?,?)
                          ON CONFLICT(session_id) DO UPDATE SET title=excluded.title,lane=excluded.lane,armed_at=excluded.armed_at,
                          proposal_status=NULL,proposal_summary=NULL,candidate_response=NULL,stopped_reason=NULL,disarmed_at=NULL""",
                       (f"direct:{session_id}", session_id, row["title"], lane, _now()))
            db.execute("COMMIT")
        return True

    def watch_task(self, task_id: str, title: str) -> str:
        if not task_id:
            raise ValueError("task_id is required")
        campaign_id = f"kanban:{task_id}"
        with self._connect() as db:
            db.execute("""INSERT INTO campaigns(campaign_id,task_id,title,armed_at) VALUES(?,?,?,?)
                          ON CONFLICT(task_id) DO UPDATE SET title=excluded.title,disarmed_at=NULL""",
                       (campaign_id, task_id, _summary(title, self.config.summary_max_chars), _now()))
        return campaign_id

    def proposal(self, session_id: str, status: str, summary: str) -> bool:
        if status not in {"completed", "blocked"}:
            raise ValueError("status must be completed or blocked")
        with self._connect() as db:
            return db.execute("UPDATE campaigns SET proposal_status=?,proposal_summary=? WHERE session_id=? AND disarmed_at IS NULL",
                              (status, _summary(summary, self.config.summary_max_chars), session_id)).rowcount == 1

    def candidate(self, session_id: str, response: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE campaigns SET candidate_response=? WHERE session_id=? AND disarmed_at IS NULL",
                       (_summary(response, self.config.summary_max_chars), session_id))

    def _event(self, db: sqlite3.Connection, campaign: sqlite3.Row, status: str, summary: str, delay: int = 0) -> str:
        existing = db.execute("SELECT event_id FROM events WHERE campaign_id=? AND generation=? AND terminal_status=?",
                              (campaign["campaign_id"], campaign["generation"], status)).fetchone()
        if existing:
            return existing["event_id"]
        event_id, now = uuid.uuid4().hex, _now()
        db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,NULL,NULL)",
                   (event_id, campaign["campaign_id"], campaign["generation"], status, campaign["title"],
                    _summary(summary, self.config.summary_max_chars), campaign["task_id"], campaign["session_id"], now, now + delay))
        db.executemany("INSERT INTO deliveries(event_id,destination,available_at) VALUES(?,?,?)",
                       ((event_id, "telegram", now + delay), (event_id, "macos", now + delay)))
        return event_id

    def session_end(self, session_id: str, *, completed: bool, failed: bool = False, interrupted: bool = False,
                    turn_exit_reason: str = "") -> str | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            campaign = db.execute("SELECT * FROM campaigns WHERE session_id=? AND disarmed_at IS NULL", (session_id,)).fetchone()
            if not campaign:
                db.execute("COMMIT"); return None
            if campaign["proposal_status"] and completed and not interrupted:
                status, summary = campaign["proposal_status"], campaign["proposal_summary"]
            elif interrupted:
                status, summary = "interrupted", campaign["stopped_reason"] or turn_exit_reason or "Turn interrupted"
            elif failed:
                status, summary = "failed", turn_exit_reason or "Turn failed"
            else:
                status, summary = "unknown", "No durable terminal outcome was recorded"
            event_id = self._event(db, campaign, status, summary)
            db.execute("UPDATE campaigns SET disarmed_at=? WHERE campaign_id=?", (_now(), campaign["campaign_id"]))
            db.execute("COMMIT")
            return event_id

    def stopped(self, session_or_lane: str, reason: str, *, by_lane: bool = False) -> None:
        column = "lane" if by_lane else "session_id"
        with self._connect() as db:
            db.execute(f"UPDATE campaigns SET stopped_reason=? WHERE {column}=? AND disarmed_at IS NULL",
                       (_summary(reason, self.config.summary_max_chars), session_or_lane))

    def reset(self, new_session_id: str, old_session_id: str | None = None, lane: str | None = None) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            predecessor = old_session_id
            if not predecessor and lane:
                row = db.execute("SELECT session_id FROM campaigns WHERE lane=? AND stopped_reason IS NOT NULL AND disarmed_at IS NULL", (lane,)).fetchone()
                predecessor = row["session_id"] if row else None
            if predecessor:
                db.execute("UPDATE campaigns SET disarmed_at=? WHERE session_id=? AND disarmed_at IS NULL", (_now(), predecessor))
            db.execute("INSERT OR IGNORE INTO campaigns(campaign_id,session_id,title,lane,armed_at,disarmed_at) VALUES(?,?,?,?,?,?)",
                       (f"boundary:{new_session_id}", new_session_id, "", lane, _now(), _now()))
            db.execute("COMMIT")

    def kanban_completed(self, task_id: str, summary: str) -> str | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            campaign = db.execute("SELECT * FROM campaigns WHERE task_id=? AND disarmed_at IS NULL", (task_id,)).fetchone()
            if not campaign:
                db.execute("COMMIT"); return None
            event_id = self._event(db, campaign, "completed", summary)
            db.execute("UPDATE campaigns SET disarmed_at=? WHERE campaign_id=?", (_now(), campaign["campaign_id"]))
            db.execute("COMMIT")
            return event_id

    def kanban_blocked(self, task_id: str, reason: str) -> str | None:
        with self._connect() as db:
            campaign = db.execute("SELECT * FROM campaigns WHERE task_id=? AND disarmed_at IS NULL", (task_id,)).fetchone()
            return self._event(db, campaign, "blocked", reason, self.config.block_debounce_seconds) if campaign else None

    @staticmethod
    def human_block(state: dict[str, Any]) -> bool:
        kind, status = state.get("block_kind"), state.get("status")
        reason = str(state.get("reason") or "").lower()
        if kind in HUMAN_BLOCKS:
            return status == "blocked"
        if status == "triage" and (int(state.get("block_recurrences") or 0) > 0 or "exhaust" in reason):
            return True
        return status == "blocked" and ("human_block" in reason or "approval" in reason or "human" in reason or "review" in reason)

    def recheck_block(self, event_id: str, state_reader: Callable[[str], dict[str, Any] | None]) -> bool:
        with self._connect() as db:
            event = db.execute("SELECT task_id FROM events WHERE event_id=? AND cancelled_at IS NULL", (event_id,)).fetchone()
            if not event or not event["task_id"]:
                return True
            state = state_reader(event["task_id"])
            if state is None:  # board read failure is retryable, never a cancellation.
                return False
            if self.human_block(state):
                return True
            db.execute("UPDATE events SET cancelled_at=?, cancellation_reason=? WHERE event_id=?", (_now(), "block no longer requires human action", event_id))
            return False

    def cancel_nonhuman_blocks(self, state_reader: Callable[[str], dict[str, Any] | None]) -> int:
        cancelled = 0
        with self._connect() as db:
            rows = db.execute("SELECT event_id FROM events WHERE terminal_status='blocked' AND cancelled_at IS NULL").fetchall()
        for row in rows:
            before = self.status()
            self.recheck_block(row["event_id"], state_reader)
            if any(r["event_id"] == row["event_id"] and r["cancelled_at"] for r in self.status()) and before:
                cancelled += 1
        return cancelled

    def resume_task(self, task_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE campaigns SET generation=generation+1,disarmed_at=NULL WHERE task_id=?", (task_id,))

    def status(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT e.*,d.destination,d.status AS delivery_status,d.attempts,d.available_at AS delivery_available_at FROM events e JOIN deliveries d USING(event_id) ORDER BY e.created_at,d.destination")]
