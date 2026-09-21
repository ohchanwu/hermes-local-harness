#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "hermes-terminal-outcome-notification"
import sys
sys.path.insert(0, str(PLUGIN))
from core import Config, Store
from worker import Worker


def fresh():
    directory = tempfile.TemporaryDirectory()
    return directory, Store(Path(directory.name) / "outbox.sqlite3", Config(block_debounce_seconds=0))


def deliveries(store):
    return {(r["terminal_status"], r["destination"]): r["delivery_status"] for r in store.status()}


def test_direct_and_duplicate_callbacks():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    assert store.proposal("s1", "completed", "done")
    first = store.session_end("s1", completed=True)
    assert first and store.session_end("s1", completed=True) is None
    sent = []
    worker = Worker(store, telegram=lambda body: sent.append(("t", body)), macos=lambda title, body: sent.append(("m", body)))
    assert worker.drain_once() == 2 and len(sent) == 2
    assert worker.drain_once() == 0 and len(sent) == 2
    tmp.cleanup()


def test_ambiguous_never_completes():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    assert store.session_end("s1", completed=True)
    assert ("unknown", "telegram") in deliveries(store)
    tmp.cleanup()


def test_intermediate_candidate_does_not_send():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    store.candidate("s1", "looks complete")
    assert not store.status()
    tmp.cleanup()


def test_destination_retry_independence_and_restart():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_completed("t1", "done")
    sent = []
    failing = Worker(store, telegram=lambda body: (_ for _ in ()).throw(RuntimeError("offline")), macos=lambda t, b: sent.append(b))
    assert failing.drain_once() == 1
    assert deliveries(store)[("completed", "macos")] == "success"
    restarted = Worker(store, telegram=lambda body: sent.append(body), macos=lambda t, b: sent.append(b))
    assert restarted.drain_once() == 1
    assert len(sent) == 2 and deliveries(store)[("completed", "telegram")] == "success"
    tmp.cleanup()


def test_block_recheck_and_resume_generation():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "waiting")
    sent = []
    worker = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
                    state_reader=lambda task: {"status": "todo", "block_kind": "dependency"})
    assert worker.drain_once() == 0 and not sent
    store.resume_task("t1")
    store.kanban_completed("t1", "fixed")
    worker = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b))
    assert worker.drain_once() == 2 and len(sent) == 2
    tmp.cleanup()


def test_reset_variants_do_not_guess_predecessor():
    tmp, store = fresh()
    store.arm_direct("old", "Old")
    store.arm_direct("other", "Other")
    store.reset("new")
    assert store.proposal("old", "completed", "x")
    store.reset("new2", "old")
    assert not store.proposal("old", "completed", "x")
    assert store.proposal("other", "completed", "x")
    tmp.cleanup()


def test_secret_redaction_and_documented_crash_window():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_completed("t1", "token=private-value")
    row = store.status()[0]
    assert "private-value" not in row["short_summary"] and "[REDACTED]" in row["short_summary"]
    # Simulate external acceptance followed by a process death before _finish().
    accepted = []
    worker = Worker(store, telegram=lambda body: accepted.append(body), macos=lambda t, b: None)
    claimed = worker._claim("telegram")
    assert claimed is not None
    worker.telegram("accepted before crash")
    restarted = Worker(store, telegram=lambda body: accepted.append(body), macos=lambda t, b: None)
    with store._connect() as db:
        db.execute("UPDATE deliveries SET lease_until=0 WHERE event_id=? AND destination='telegram'", (claimed["event_id"],))
    assert restarted.drain_once() >= 1 and len(accepted) == 2
    tmp.cleanup()


for name, value in sorted(globals().copy().items()):
    if name.startswith("test_"):
        value()
print("ok")
