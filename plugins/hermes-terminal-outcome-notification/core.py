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
    # Summaries cross notification boundaries; redact common key/value secrets defensively.
    text = re.sub(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:limit]


class Store:
    """SQLite state; callbacks only make bounded local transactions."""

    def __init__(self, path: str | Path, config: Config = Config()) -> None:
        self.path, self.config = Path(path), config
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns (
                  campaign_id TEXT PRIMARY KEY, session_id TEXT UNIQUE, task_id TEXT UNIQUE,
                  generation INTEGER NOT NULL DEFAULT 1, title TEXT NOT NULL, lane TEXT,
                  armed_at INTEGER NOT NULL, proposal_status TEXT, proposal_summary TEXT,
                  candidate_response TEXT, stopped_reason TEXT, disarmed_at INTEGER
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
        os.chmod(self.path, 0o600)

    def arm_direct(self, session_id: str, title: str, lane: str | None = None) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        campaign_id = f"direct:{session_id}"
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT INTO campaigns(campaign_id,session_id,title,lane,armed_at)
                          VALUES(?,?,?,?,?)
                          ON CONFLICT(session_id) DO UPDATE SET title=excluded.title,lane=excluded.lane,
                          armed_at=excluded.armed_at,proposal_status=NULL,proposal_summary=NULL,
                          candidate_response=NULL,stopped_reason=NULL,disarmed_at=NULL""",
                       (campaign_id, session_id, _summary(title, self.config.summary_max_chars), lane, _now()))
            db.execute("COMMIT")
        return campaign_id

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
            cur = db.execute("""UPDATE campaigns SET proposal_status=?, proposal_summary=?
                                WHERE session_id=? AND disarmed_at IS NULL""",
                             (status, _summary(summary, self.config.summary_max_chars), session_id))
            return cur.rowcount == 1

    def candidate(self, session_id: str, response: str) -> None:
        with self._connect() as db:
            db.execute("""UPDATE campaigns SET candidate_response=? WHERE session_id=? AND disarmed_at IS NULL""",
                       (_summary(response, self.config.summary_max_chars), session_id))

    def _event(self, db: sqlite3.Connection, campaign: sqlite3.Row, status: str, summary: str, delay: int = 0) -> str:
        existing = db.execute("SELECT event_id FROM events WHERE campaign_id=? AND generation=? AND terminal_status=?",
                              (campaign["campaign_id"], campaign["generation"], status)).fetchone()
        if existing:
            return existing["event_id"]
        event_id = uuid.uuid4().hex
        now = _now()
        db.execute("""INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,NULL,NULL)""",
                   (event_id, campaign["campaign_id"], campaign["generation"], status, campaign["title"],
                    _summary(summary, self.config.summary_max_chars), campaign["task_id"], campaign["session_id"],
                    now, now + delay))
        db.executemany("INSERT INTO deliveries(event_id,destination) VALUES(?,?)",
                       ((event_id, "telegram"), (event_id, "macos")))
        return event_id

    def session_end(self, session_id: str, *, completed: bool, failed: bool = False,
                    interrupted: bool = False, turn_exit_reason: str = "") -> str | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            campaign = db.execute("SELECT * FROM campaigns WHERE session_id=? AND disarmed_at IS NULL", (session_id,)).fetchone()
            if not campaign:
                db.execute("COMMIT")
                return None
            if campaign["proposal_status"] and completed and not interrupted:
                status, summary = campaign["proposal_status"], campaign["proposal_summary"]
            elif interrupted:
                status, summary = "interrupted", campaign["stopped_reason"] or turn_exit_reason or "Turn interrupted"
            elif failed:
                status, summary = "failed", turn_exit_reason or "Turn failed"
            else:
                # post_llm_call is deliberately not proof of a committed final response.
                status, summary = "unknown", "No durable terminal outcome was recorded"
            event_id = self._event(db, campaign, status, summary)
            db.execute("UPDATE campaigns SET disarmed_at=? WHERE campaign_id=?", (_now(), campaign["campaign_id"]))
            db.execute("COMMIT")
            return event_id

    def stopped(self, session_id: str, reason: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE campaigns SET stopped_reason=? WHERE session_id=? AND disarmed_at IS NULL",
                       (_summary(reason, self.config.summary_max_chars), session_id))

    def reset(self, new_session_id: str, old_session_id: str | None = None, lane: str | None = None) -> None:
        """Only cancel an identified predecessor; a new-only reset never guesses."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if old_session_id:
                db.execute("UPDATE campaigns SET disarmed_at=? WHERE session_id=? AND disarmed_at IS NULL",
                           (_now(), old_session_id))
            # New session is an explicit unarmed boundary.  Lane is stored only as evidence for callers.
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

    def cancel_nonhuman_blocks(self, state_reader: Callable[[str], dict[str, Any] | None]) -> int:
        """Worker recheck: only a current, human-action block remains eligible."""
        cancelled = 0
        with self._connect() as db:
            rows = db.execute("""SELECT e.event_id,e.task_id FROM events e WHERE e.terminal_status='blocked'
                               AND e.cancelled_at IS NULL AND EXISTS(SELECT 1 FROM deliveries d WHERE d.event_id=e.event_id AND d.status='pending')""").fetchall()
            for row in rows:
                state = state_reader(row["task_id"]) if row["task_id"] else None
                if not state or state.get("status") != "blocked" or state.get("block_kind") not in HUMAN_BLOCKS:
                    db.execute("UPDATE events SET cancelled_at=?, cancellation_reason=? WHERE event_id=?",
                               (_now(), "block no longer requires human action", row["event_id"]))
                    cancelled += 1
        return cancelled

    def resume_task(self, task_id: str) -> None:
        with self._connect() as db:
            db.execute("""UPDATE campaigns SET generation=generation+1, disarmed_at=NULL WHERE task_id=?""", (task_id,))

    def status(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT e.*, d.destination, d.status AS delivery_status, d.attempts FROM events e JOIN deliveries d USING(event_id) ORDER BY e.created_at,d.destination")]
