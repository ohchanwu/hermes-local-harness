#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "hermes-terminal-outcome-notification"
import sys
sys.path.insert(0, str(PLUGIN))
from core import Config, Store
from worker import Worker, send_macos


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
    failing = Worker(store, telegram=lambda body: (_ for _ in ()).throw(RuntimeError("offline")), macos=lambda t, b: sent.append(b), retry_backoff=(0,))
    assert failing.drain_once() == 1
    assert deliveries(store)[("completed", "macos")] == "success"
    restarted = Worker(store, telegram=lambda body: sent.append(body), macos=lambda t, b: sent.append(b), retry_backoff=(0,))
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


def test_explicit_pending_arm_binds_only_at_context_bearing_pre_llm_boundary():
    tmp, store = fresh()
    store.arm_next_direct("Opaque campaign")
    assert store.claim_pending_direct("opaque-cli-id", "cli")
    assert store.proposal("opaque-cli-id", "completed", "done")
    assert store.session_end("opaque-cli-id", completed=True)
    assert not store.claim_pending_direct("other-id", "cli")
    tmp.cleanup()


def test_human_block_triage_and_unavailable_board_state_are_not_lost():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "approval required")
    sent = []
    unavailable = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
                         state_reader=lambda _: None)
    assert unavailable.drain_once() == 0 and not sent
    with store._connect() as db:
        db.execute("UPDATE deliveries SET lease_until=NULL,available_at=0")
    human = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
                   state_reader=lambda _: {"status": "triage", "block_kind": "transient", "block_recurrences": 3,
                                           "current_run_id": 7, "reason": "retry allowance exhausted"})
    assert human.drain_once() == 2 and len(sent) == 2
    tmp.cleanup()


def test_bounded_retry_marks_only_failed_destination_and_uses_backoff():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_completed("t1", "done")
    worker = Worker(store, telegram=lambda _: (_ for _ in ()).throw(RuntimeError("offline")), macos=lambda *_: None,
                    max_attempts=2, retry_backoff=(0, 0))
    assert worker.drain_once() == 1
    assert worker.drain_once() == 0
    rows = {r["destination"]: r for r in store.status()}
    assert rows["telegram"]["delivery_status"] == "failed" and rows["macos"]["delivery_status"] == "success"
    tmp.cleanup()


def test_macos_adapter_uses_compilable_double_quoted_applescript():
    calls = []
    import worker
    original = worker.subprocess.run
    worker.subprocess.run = lambda argv, **kwargs: calls.append((argv, kwargs))
    try:
        send_macos('Title "quoted"', 'Body with \\ and "quotes"')
    finally:
        worker.subprocess.run = original
    script = calls[0][0][2]
    assert script.startswith('display notification "') and ' with title "' in script and "'" not in script


def test_reset_new_only_preserves_unrelated_and_stop_lane_resolves_predecessor():
    tmp, store = fresh()
    store.arm_direct("old", "Old", lane="lane-a")
    store.arm_direct("other", "Other", lane="lane-b")
    store.stopped("lane-a", "stopped", by_lane=True)
    store.reset("new", lane="lane-a")
    assert not store.proposal("old", "completed", "x")
    assert store.proposal("other", "completed", "x")
    tmp.cleanup()


def test_plugin_raw_command_contract_binds_opaque_context_at_pre_llm_call():
    import importlib.util
    import os
    tmp = tempfile.TemporaryDirectory()
    old = os.environ.get("HERMES_TERMINAL_OUTBOX")
    os.environ["HERMES_TERMINAL_OUTBOX"] = str(Path(tmp.name) / "shared.sqlite3")
    try:
        spec = importlib.util.spec_from_file_location("notification_plugin", PLUGIN / "__init__.py",
                                                      submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["notification_plugin"] = module
        spec.loader.exec_module(module)
        assert "next direct turn" in module.arm_command("CLI title")
        module._pre_llm_call(session_id="opaque-cli-1", platform="cli")
        assert module._store().proposal("opaque-cli-1", "completed", "done")
    finally:
        sys.modules.pop("notification_plugin", None)
        if old is None:
            os.environ.pop("HERMES_TERMINAL_OUTBOX", None)
        else:
            os.environ["HERMES_TERMINAL_OUTBOX"] = old
        tmp.cleanup()


def test_outbox_and_parent_are_private():
    import stat
    tmp, store = fresh()
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700
    tmp.cleanup()


def test_two_producers_share_one_configured_outbox():
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "shared.sqlite3"
    producer, worker_store = Store(path), Store(path)
    producer.watch_task("root", "Root")
    producer.kanban_completed("root", "done")
    sent = []
    assert Worker(worker_store, telegram=sent.append, macos=lambda *_: sent.append("macos")).drain_once() == 2
    assert len(sent) == 2
    tmp.cleanup()


for name, value in sorted(globals().copy().items()):
    if name.startswith("test_"):
        value()
print("ok")
