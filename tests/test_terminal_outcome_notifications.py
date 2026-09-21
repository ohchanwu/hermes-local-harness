#!/usr/bin/env python3
"""Terminal outcome notification tests: host contracts, recovery, retry accounting,
generation-safe block recheck, adapters, privacy. No real sends."""
import importlib.util
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "hermes-terminal-outcome-notification"
sys.path.insert(0, str(PLUGIN))
from core import Config, Store  # noqa: E402
from worker import Worker, send_macos, kanban_state  # noqa: E402


def fresh():
    directory = tempfile.TemporaryDirectory()
    return directory, Store(Path(directory.name) / "outbox.sqlite3", Config(block_debounce_seconds=0))


def deliveries(store):
    return {(r["terminal_status"], r["destination"]): r["delivery_status"] for r in store.status()}


def rows_by(store, terminal):
    return {r["destination"]: r for r in store.status() if r["terminal_status"] == terminal}


# ---------- finding 1: deterministic arming via host tool dispatch ----------

def test_arm_tool_binds_host_supplied_session_only():
    tmp, store = fresh()
    campaign = store.arm_direct("opaque-gw-1", "Campaign", "telegram")
    assert campaign.startswith("direct:")
    assert store.proposal("opaque-gw-1", "completed", "done")
    assert store.session_end("opaque-gw-1", completed=True)
    # a different session never claims it
    assert not store.proposal("opaque-other", "completed", "x")
    tmp.cleanup()


def test_arm_tool_fails_closed_without_session_identity():
    spec = importlib.util.spec_from_file_location("notification_plugin", PLUGIN / "__init__.py",
                                                  submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["notification_plugin"] = module
    tmp = tempfile.TemporaryDirectory()
    old = os.environ.get("HERMES_TERMINAL_OUTBOX")
    os.environ["HERMES_TERMINAL_OUTBOX"] = str(Path(tmp.name) / "shared.sqlite3")
    try:
        spec.loader.exec_module(module)
        # host dispatch always supplies session_id; simulate a degraded host that does not
        result = json.loads(module.arm_campaign({}, ))
        assert result["success"] is False and "session identity unavailable" in result["error"]
        assert module.arm_command("anything").startswith("Slash arming is not supported")
        # with host identity: binds exactly that session
        ok = json.loads(module.arm_campaign({"title": "T"}, session_id="opaque-cli-9", platform="cli"))
        assert ok["success"] is True
        assert module._store().proposal("opaque-cli-9", "completed", "done")
    finally:
        sys.modules.pop("notification_plugin", None)
        if old is None:
            os.environ.pop("HERMES_TERMINAL_OUTBOX", None)
        else:
            os.environ["HERMES_TERMINAL_OUTBOX"] = old
        tmp.cleanup()


def test_competing_sessions_cannot_cross_claim():
    # arming is per-session upsert; two concurrent sessions each keep their own campaign
    tmp, store = fresh()
    store.arm_direct("gw-a", "A", "telegram")
    store.arm_direct("gw-b", "B", "telegram")
    assert store.proposal("gw-a", "completed", "a done")
    assert store.proposal("gw-b", "blocked", "b blocked")
    a = store.session_end("gw-a", completed=True)
    b = store.session_end("gw-b", completed=True)
    assert a and b and a != b
    statuses = {r["terminal_status"] for r in store.status()}
    assert statuses == {"completed", "blocked"}
    tmp.cleanup()


# ---------- finding 2: recovery / stranded arms ----------

def test_recovery_classifies_stranded_arms_fail_closed():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    with store._connect() as db:
        db.execute("UPDATE campaigns SET last_activity_at=1")  # ancient
    assert store.recover(now=10**9, max_age_seconds=60) == 1
    evs = {(r["terminal_status"], r["destination"]) for r in store.status()}
    assert ("unknown", "telegram") in evs and ("unknown", "macos") in evs
    # never completed; one-shot disarmed
    assert all(r["terminal_status"] != "completed" for r in store.status())
    assert store.recover(now=10**9 + 1) == 0  # idempotent
    tmp.cleanup()


def test_recovery_prefers_stop_evidence_and_skips_recent_and_kanban():
    tmp, store = fresh()
    store.arm_direct("s1", "One")
    store.stopped("s1", "/stop requested")
    store.arm_direct("s2", "Two")  # recent: no activity backfill -> recover must skip
    store.watch_task("t1", "Root")
    with store._connect() as db:
        db.execute("UPDATE campaigns SET last_activity_at=1 WHERE session_id='s1'")
    assert store.recover(now=10**9, max_age_seconds=60) == 1
    statuses = {r["terminal_status"] for r in store.status()}
    assert statuses == {"interrupted"}
    assert not [c for c in store.campaigns() if c["session_id"] == "s2" and c["disarmed_at"]]
    tmp.cleanup()


def test_worker_cycle_runs_recovery_scan():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    with store._connect() as db:
        db.execute("UPDATE campaigns SET last_activity_at=1")
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(t))
    w.drain_once()
    assert len(sent) == 2 and all("unknown" in b for b in sent)
    tmp.cleanup()


def test_continuation_lineage_retains_watch_across_rotation():
    tmp, store = fresh()
    store.arm_direct("old-id", "Campaign")
    store.touch("new-id", parent_session_id="old-id")  # compression rotation
    assert store.proposal("new-id", "completed", "done")
    assert store.session_end("new-id", completed=True)
    assert ("completed", "telegram") in deliveries(store)
    tmp.cleanup()


# ---------- finding 3: board-unavailability retry accounting ----------

def test_board_unavailable_never_consumes_send_attempts_then_fails_visibly():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "approval required", run_id=5)
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=lambda _: None, max_recheck_attempts=3, recheck_backoff=(0, 0, 0))
    for _ in range(3):
        with store._connect() as db:  # make available_at elapsed
            db.execute("UPDATE deliveries SET available_at=0, lease_until=NULL")
        w.drain_once()
    row = rows_by(store, "blocked")["telegram"]
    assert sent == [] and row["delivery_status"] == "failed"
    assert row["attempts"] == 0  # classification retries never consumed delivery budget
    assert "board state unavailable" in row["last_error"]
    tmp.cleanup()


def test_board_recovers_after_outages_and_sends():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "approval required", run_id=5)
    sent, calls = [], {"n": 0}

    def reader(task_id):
        calls["n"] += 1
        if calls["n"] <= 2:  # both destinations see one outage each
            return None
        return {"status": "blocked", "block_kind": "needs_input",
                "current_run_id": 5, "max_run_id": 5, "block_recurrences": 0}

    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b), state_reader=reader)
    with store._connect() as db:
        db.execute("UPDATE deliveries SET available_at=0, lease_until=NULL")
    w.drain_once()  # outage: retain both
    assert sent == []
    with store._connect() as db:
        db.execute("UPDATE deliveries SET available_at=0, lease_until=NULL")
    w.drain_once()  # board back: send both
    assert len(sent) == 2
    assert rows_by(store, "blocked")["telegram"]["delivery_status"] == "success"
    tmp.cleanup()


def test_triage_and_exhaustion_classifications_deliver():
    for kind_state in ({"status": "triage", "block_kind": "transient", "block_recurrences": 3,
                        "current_run_id": 7, "max_run_id": 7, "reason": "retry allowance exhausted"},
                       {"status": "blocked", "block_kind": None, "block_recurrences": 0,
                        "current_run_id": 7, "max_run_id": 7, "reason": "explicit human approval gate"}):
        tmp, store = fresh()
        store.watch_task("t1", "Root")
        store.kanban_blocked("t1", "escalated", run_id=7)
        sent = []
        w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
                   state_reader=lambda _: kind_state)
        assert w.drain_once() == 2 and len(sent) == 2
        tmp.cleanup()


# ---------- finding 4: generation-safe block recheck ----------

def _board(task_id="t1", status="blocked", kind="needs_input", run=5, recurrences=0, reason="approval required"):
    return lambda _: {"status": status, "block_kind": kind, "current_run_id": run,
                      "max_run_id": run, "block_recurrences": recurrences, "reason": reason}


def test_generation_safe_recheck_cancels_old_generation_block():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "waiting human", run_id=5)
    sent = []
    # before drain: task re-claimed (generation bump) — old candidate must not send
    store.claimed("t1", run_id=6)
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=_board(run=6))
    assert w.drain_once() == 0 and sent == []
    assert all(r["cancelled_at"] for r in store.status() if r["terminal_status"] == "blocked")
    tmp.cleanup()


def test_run_evidence_blocks_stale_candidate_even_same_generation_read():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "waiting human", run_id=5)
    # generation NOT bumped (e.g. direct board surgery) but a newer run exists
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=_board(run=7))
    assert w.drain_once() == 0 and sent == []
    assert all(r["cancelled_at"] for r in store.status())
    tmp.cleanup()


def test_fresh_human_block_still_sends():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "approval required", run_id=5)
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=_board(run=5))
    assert w.drain_once() == 2 and len(sent) == 2
    tmp.cleanup()


def test_dependency_block_is_cancelled_not_sent():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "waiting on parent", run_id=5)
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=_board(kind="dependency", run=5, reason="dependency wait"))
    assert w.drain_once() == 0 and sent == []
    assert all(r["cancelled_at"] for r in store.status())
    tmp.cleanup()


def test_resume_then_new_human_block_before_old_candidate_drains():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_blocked("t1", "waiting human", run_id=5)
    store.claimed("t1")  # resume: generation 2
    store.kanban_blocked("t1", "still needs human", run_id=6)  # new human block in gen 2
    sent = []
    w = Worker(store, telegram=lambda b: sent.append(b), macos=lambda t, b: sent.append(b),
               state_reader=_board(run=6))
    assert w.drain_once() == 2
    assert sent and "still needs human" in sent[0]
    old = [r for r in store.status() if r["generation"] == 1]
    assert old and all(r["cancelled_at"] for r in old)
    tmp.cleanup()


# ---------- reset / interruption surfaces ----------

def test_reset_variants_do_not_guess_predecessor():
    tmp, store = fresh()
    store.arm_direct("old", "Old")
    store.arm_direct("other", "Other")
    store.reset("new")  # new-only: no predecessor proven
    assert store.proposal("old", "completed", "x")
    store.reset("new2", "old")  # explicit old id
    assert not store.proposal("old", "completed", "x")
    assert store.proposal("other", "completed", "x")
    tmp.cleanup()


def test_reset_new_only_preserves_unrelated_and_stop_lane_resolves_predecessor():
    tmp, store = fresh()
    store.arm_direct("old", "Old", lane="lane-a")
    store.arm_direct("other", "Other", lane="lane-b")
    store.stopped("lane-a", "stopped", by_lane=True)
    store.reset("new", lane="lane-a")
    assert not store.proposal("old", "completed", "x")
    assert store.proposal("other", "completed", "x")
    tmp.cleanup()


# ---------- core semantics ----------

def test_direct_and_duplicate_callbacks():
    tmp, store = fresh()
    store.arm_direct("s1", "Campaign")
    store.proposal("s1", "completed", "done")
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
    failing = Worker(store, telegram=lambda body: (_ for _ in ()).throw(RuntimeError("offline")),
                     macos=lambda t, b: sent.append(b), retry_backoff=(0,))
    assert failing.drain_once() == 1
    assert deliveries(store)[("completed", "macos")] == "success"
    restarted = Worker(store, telegram=lambda body: sent.append(body), macos=lambda t, b: sent.append(b), retry_backoff=(0,))
    assert restarted.drain_once() == 1
    assert len(sent) == 2 and deliveries(store)[("completed", "telegram")] == "success"
    tmp.cleanup()


def test_secret_redaction_and_documented_crash_window():
    tmp, store = fresh()
    store.watch_task("t1", "Root")
    store.kanban_completed("t1", "token=private-value")
    row = store.status()[0]
    assert "private-value" not in row["short_summary"] and "[REDACTED]" in row["short_summary"]
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


def test_macos_adapter_script_compiles():
    # non-notifying compile check: osacompile builds the .scpt without executing it
    import worker
    script = "display notification " + worker._apple_string("probe") + " with title " + worker._apple_string("probe")
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "probe.scpt"
        result = subprocess.run(["osacompile", "-o", str(out), "-e", script], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert out.exists()


def test_kanban_state_reader_resolves_runs():
    tmp = tempfile.TemporaryDirectory()
    board = Path(tmp.name) / "kanban.db"
    with sqlite3.connect(board) as db:
        db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT, block_kind TEXT, block_recurrences INTEGER, current_run_id INTEGER, last_failure_error TEXT)")
        db.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT)")
        db.execute("INSERT INTO tasks VALUES('t1','blocked','needs_input',0,5,NULL)")
        db.execute("INSERT INTO task_runs VALUES(5,'t1','blocked')")
    old = os.environ.get("HERMES_KANBAN_DB")
    os.environ["HERMES_KANBAN_DB"] = str(board)
    try:
        state = kanban_state("t1")
        assert state["status"] == "blocked" and state["block_kind"] == "needs_input"
        assert state["current_run_id"] == 5 and state["max_run_id"] == 5
        assert kanban_state("missing") is not None  # conservative, not unavailable
        board.unlink()  # now unreadable
        board2 = Path(tmp.name) / "kanban.db"
        os.environ["HERMES_KANBAN_DB"] = str(board2 / "sub" / "deep.db")  # connect fails
        assert kanban_state("t1") is None  # unavailable -> retain
    finally:
        if old is None:
            os.environ.pop("HERMES_KANBAN_DB", None)
        else:
            os.environ["HERMES_KANBAN_DB"] = old
        tmp.cleanup()


def test_outbox_and_parent_are_private():
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


def test_watch_tool_and_hooks_via_real_plugin_module():
    spec = importlib.util.spec_from_file_location("notification_plugin2", PLUGIN / "__init__.py",
                                                  submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["notification_plugin2"] = module
    tmp = tempfile.TemporaryDirectory()
    old = os.environ.get("HERMES_TERMINAL_OUTBOX")
    os.environ["HERMES_TERMINAL_OUTBOX"] = str(Path(tmp.name) / "shared.sqlite3")
    try:
        spec.loader.exec_module(module)
        assert json.loads(module.watch_terminal_task({"task_id": "t9", "title": "Root"}))["success"]
        # hook payloads exactly as the host fires them
        module._pre_llm_call(session_id="s-opaque", session_key="ns:telegram:dm:111", parent_session_id="")
        module._post_llm_call(session_id="s-opaque", assistant_response="candidate text")
        module._kanban_blocked(task_id="t9", reason="needs approval", run_id=3)
        module._kanban_claimed(task_id="t9", run_id=4)
        module._kanban_completed(task_id="t9", summary="done", run_id=4)
        module._on_session_end(session_id="s-opaque", completed=True, failed=False, interrupted=False, turn_exit_reason="x")
        st = module._store().status()
        assert any(r["terminal_status"] == "completed" for r in st)
        ev = [r for r in st if r["terminal_status"] == "blocked"][0]
        assert ev["cancelled_at"] is None  # cancelled only via generation check at delivery time
    finally:
        sys.modules.pop("notification_plugin2", None)
        if old is None:
            os.environ.pop("HERMES_TERMINAL_OUTBOX", None)
        else:
            os.environ["HERMES_TERMINAL_OUTBOX"] = old
        tmp.cleanup()


def test_public_safety_no_private_state_in_repo_tree():
    text = (PLUGIN / "README.md").read_text() + (ROOT / "deployment/hermes-terminal-outcome-notification.example.yaml").read_text()
    for needle in ("bot_token", "-100", "chat_id=", "thread_id="):
        assert needle not in text.lower(), needle
    # plugin sources contain no hardcoded chat/thread/token
    for src in PLUGIN.glob("*.py"):
        body = src.read_text()
        for needle in ("api_id", "api_hash", "bot_token", "chat_id"):
            assert needle not in body, f"{src}: {needle}"


for name, value in sorted(globals().copy().items()):
    if name.startswith("test_"):
        value()
print("ok")
