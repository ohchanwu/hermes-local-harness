"""Outbox delivery worker. It never invokes an LLM."""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Callable

from core import Store


class Worker:
    def __init__(self, store: Store, *, telegram: Callable[[str], None], macos: Callable[[str, str], None],
                 state_reader: Callable[[str], dict | None] | None = None, max_attempts: int = 4,
                 retry_backoff: tuple[int, ...] = (5, 30, 120, 300)) -> None:
        self.store, self.telegram, self.macos = store, telegram, macos
        self.state_reader, self.max_attempts, self.retry_backoff = state_reader, max_attempts, retry_backoff

    @staticmethod
    def text(event: sqlite3.Row) -> tuple[str, str]:
        icon = "✅" if event["terminal_status"] == "completed" else "⚠️"
        title = f"{icon} Hermes campaign {event['terminal_status']}"
        return title, "\n".join(part for part in (event["title"], event["short_summary"],
                         f"Task: {event['task_id']}" if event["task_id"] else None) if part)

    def _claim(self, destination: str) -> sqlite3.Row | None:
        now = int(time.time())
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT e.* FROM events e JOIN deliveries d USING(event_id)
                                WHERE d.destination=? AND d.status='pending' AND d.attempts < ?
                                  AND (d.lease_until IS NULL OR d.lease_until < ?) AND d.available_at <= ?
                                  AND e.cancelled_at IS NULL ORDER BY e.created_at LIMIT 1""",
                             (destination, self.max_attempts, now, now)).fetchone()
            if row:
                db.execute("UPDATE deliveries SET lease_until=?,attempts=attempts+1 WHERE event_id=? AND destination=?",
                           (now + 60, row["event_id"], destination))
            db.execute("COMMIT")
            return row

    def _finish(self, event_id: str, destination: str, error: Exception | None) -> None:
        with self.store._connect() as db:
            if error is None:
                db.execute("UPDATE deliveries SET status='success',lease_until=NULL,delivered_at=?,last_error=NULL WHERE event_id=? AND destination=?",
                           (int(time.time()), event_id, destination))
                return
            row = db.execute("SELECT attempts FROM deliveries WHERE event_id=? AND destination=?", (event_id, destination)).fetchone()
            attempts = int(row["attempts"]) if row else self.max_attempts
            if attempts >= self.max_attempts:
                db.execute("UPDATE deliveries SET status='failed',lease_until=NULL,last_error=? WHERE event_id=? AND destination=?",
                           (str(error)[:200], event_id, destination))
            else:
                delay = self.retry_backoff[min(attempts - 1, len(self.retry_backoff) - 1)]
                db.execute("UPDATE deliveries SET lease_until=NULL,available_at=?,last_error=? WHERE event_id=? AND destination=?",
                           (int(time.time()) + delay, str(error)[:200], event_id, destination))

    def drain_once(self) -> int:
        delivered = 0
        for destination in ("telegram", "macos"):
            row = self._claim(destination)
            if not row:
                continue
            if row["terminal_status"] == "blocked" and self.state_reader and not self.store.recheck_block(row["event_id"], self.state_reader):
                with self.store._connect() as db:
                    db.execute("UPDATE deliveries SET lease_until=NULL,available_at=? WHERE event_id=? AND destination=?",
                               (int(time.time()) + 5, row["event_id"], destination))
                continue
            try:
                title, body = self.text(row)
                if destination == "telegram":
                    self.telegram(f"{title}\n{body}")
                else:
                    self.macos(title, body)
            except Exception as exc:
                self._finish(row["event_id"], destination, exc)
            else:
                # A crash before this write leaves the claimed delivery pending: at-least-once by design.
                self._finish(row["event_id"], destination, None)
                delivered += 1
        return delivered


def send_telegram(message: str) -> None:
    subprocess.run(["hermes", "send", "--to", "telegram", "--quiet", message], check=True, timeout=30)


def _apple_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def send_macos(title: str, body: str) -> None:
    subprocess.run(["osascript", "-e", f"display notification {_apple_string(body)} with title {_apple_string(title)}"], check=True, timeout=15)


def kanban_state(task_id: str) -> dict | None:
    db_path = os.environ.get("HERMES_KANBAN_DB")
    if not db_path:
        return None
    try:
        with sqlite3.connect(db_path) as db:
            row = db.execute("SELECT status,block_kind,block_recurrences,current_run_id,last_failure_error FROM tasks WHERE id=?", (task_id,)).fetchone()
            return {"status": row[0], "block_kind": row[1], "block_recurrences": row[2], "current_run_id": row[3], "reason": row[4]} if row else None
    except sqlite3.Error:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain Hermes terminal-notification outbox once.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--kanban-db", default=os.environ.get("HERMES_KANBAN_DB", ""))
    args = parser.parse_args()
    if args.kanban_db:
        os.environ["HERMES_KANBAN_DB"] = args.kanban_db
    worker = Worker(Store(Path(args.db)), telegram=send_telegram, macos=send_macos, state_reader=kanban_state)
    while worker.drain_once():
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
