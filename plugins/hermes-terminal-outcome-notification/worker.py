"""Outbox delivery worker. It never invokes an LLM."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Callable

from core import Store

# Board-unavailability retries are counted separately from send attempts so a
# flaky kanban read can never exhaust delivery of a still-valid block alert.
MAX_RECHECK_ATTEMPTS = 6
RECHECK_BACKOFF_SECONDS = (5, 30, 60, 120, 300, 900)


class Worker:
    def __init__(self, store: Store, *, telegram: Callable[[str], None], macos: Callable[[str, str], None],
                 state_reader: Callable[[str], dict | None] | None = None, max_attempts: int = 4,
                 retry_backoff: tuple[int, ...] = (5, 30, 120, 300),
                 max_recheck_attempts: int = MAX_RECHECK_ATTEMPTS,
                 recheck_backoff: tuple[int, ...] = RECHECK_BACKOFF_SECONDS) -> None:
        self.store, self.telegram, self.macos = store, telegram, macos
        self.state_reader, self.max_attempts, self.retry_backoff = state_reader, max_attempts, retry_backoff
        self.max_recheck_attempts, self.recheck_backoff = max_recheck_attempts, recheck_backoff

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
                db.execute("""UPDATE deliveries SET lease_until=?,attempts=attempts+1
                              WHERE event_id=? AND destination=?""", (now + 60, row["event_id"], destination))
            db.execute("COMMIT")
            return row

    def _retain(self, event_id: str, destination: str) -> None:
        """Board unavailable: reschedule a classification retry; escalate to visible failure after
        bounded recheck attempts so the row is never silently stuck pending-forever."""
        with self.store._connect() as db:
            row = db.execute("SELECT recheck_attempts FROM deliveries WHERE event_id=? AND destination=?",
                             (event_id, destination)).fetchone()
            if row is None:
                return
            attempts = int(row["recheck_attempts"]) + 1
            if attempts >= self.max_recheck_attempts:
                db.execute("""UPDATE deliveries SET status='failed',lease_until=NULL,
                              last_error='board state unavailable after bounded retries' WHERE event_id=? AND destination=?""",
                           (event_id, destination))
            else:
                delay = self.recheck_backoff[min(attempts - 1, len(self.recheck_backoff) - 1)]
                db.execute("""UPDATE deliveries SET lease_until=NULL,recheck_attempts=?,available_at=?
                              WHERE event_id=? AND destination=?""",
                           (attempts, int(time.time()) + delay, event_id, destination))

    def _finish(self, event_id: str, destination: str, error: Exception | None) -> None:
        with self.store._connect() as db:
            if error is None:
                db.execute("""UPDATE deliveries SET status='success',lease_until=NULL,delivered_at=?,last_error=NULL
                              WHERE event_id=? AND destination=?""", (int(time.time()), event_id, destination))
                return
            row = db.execute("SELECT attempts FROM deliveries WHERE event_id=? AND destination=?", (event_id, destination)).fetchone()
            attempts = int(row["attempts"]) if row else self.max_attempts
            if attempts >= self.max_attempts:
                db.execute("""UPDATE deliveries SET status='failed',lease_until=NULL,last_error=?
                              WHERE event_id=? AND destination=?""", (str(error)[:200], event_id, destination))
            else:
                delay = self.retry_backoff[min(attempts - 1, len(self.retry_backoff) - 1)]
                db.execute("""UPDATE deliveries SET lease_until=NULL,available_at=?,last_error=?
                              WHERE event_id=? AND destination=?""", (int(time.time()) + delay, str(error)[:200], event_id, destination))

    def _send_one(self, destination: str) -> int:
        row = self._claim(destination)
        if not row:
            return 0
        if row["terminal_status"] == "blocked" and self.state_reader:
            verdict = self.store.recheck_block(row["event_id"], self.state_reader)
            if verdict == "retain":
                # ponytail: claim incremented send attempts; refund it so classification retries
                # never consume delivery budget.
                with self.store._connect() as db:
                    db.execute("""UPDATE deliveries SET attempts=attempts-1,lease_until=NULL
                                  WHERE event_id=? AND destination=?""", (row["event_id"], destination))
                self._retain(row["event_id"], destination)
                return 0
            if verdict == "cancel":
                return self._send_one(destination)  # cancelled head-of-line: try the next row
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
            return 1
        return 0

    def drain_once(self) -> int:
        self.store.recover()  # stranded-arm scan each cycle
        return sum(self._send_one(destination) for destination in ("telegram", "macos"))


def send_telegram(message: str) -> None:
    subprocess.run(["hermes", "send", "--to", "telegram", "--quiet", message], check=True, timeout=30)


def _apple_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def send_macos(title: str, body: str) -> None:
    subprocess.run(["osascript", "-e", f"display notification {_apple_string(body)} with title {_apple_string(title)}"], check=True, timeout=15)


def kanban_state(task_id: str) -> dict | None:
    """Board state for the finality recheck, read with `hermes kanban show <id> --json` on the
    board that HERMES_KANBAN_DB names. Returns None when the board is unreadable (retry). A task
    that Hermes reports as absent is {"status": "missing"}: no human-block evidence exists, so
    delivery must not send. The block kind and recurrence count come from the newest `blocked`
    or `block_loop_detected` event (kanban.md, "Event reference"); the current run is the run
    without `ended_at`."""
    db_path = os.environ.get("HERMES_KANBAN_DB")
    # Hermes creates an empty board at a path that does not exist, which would report every
    # task as missing and cancel its alert; an absent board file is unreadable (retry) instead.
    if not db_path or not Path(db_path).is_file():
        return None
    try:
        result = subprocess.run(["hermes", "kanban", "show", task_id, "--json"],
                                capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        # Hermes v0.23.3 prints exactly this for an absent task; any other failure is retried.
        return {"status": "missing"} if result.stderr.strip() == f"no such task: {task_id}" else None
    try:
        shown = json.loads(result.stdout)
        task, events, runs = shown["task"], shown["events"], shown["runs"]
        block = next((event["payload"] or {} for event in reversed(events)
                      if event["kind"] in ("blocked", "block_loop_detected")), {})
        return {"status": task["status"], "block_kind": block.get("kind"),
                "block_recurrences": block.get("recurrences"),
                "current_run_id": next((run["id"] for run in reversed(runs) if run["ended_at"] is None), None),
                "max_run_id": max((run["id"] for run in runs), default=None),
                "reason": task.get("last_failure_error")}
    except (ValueError, KeyError, TypeError, AttributeError):
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
