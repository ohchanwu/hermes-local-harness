#!/usr/bin/env python3
"""Observe how Hermes Kanban moves a card from a first reviewer to a second reviewer.

Card t_bdfbfb88. Run from the worktree root:

    /Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I spikes/glm-reviewer-pass/run.py [BASE_DIR] [--keep]

The script creates a new directory under BASE_DIR (default: the scratch
directory of the profile harness-worker-2 for this card), points HERMES_HOME,
HOME and HERMES_KANBAN_HOME at it, and only then imports Hermes. Before the
first write it checks that the Kanban database path that Hermes resolved is
inside that directory; otherwise it prints the path and exits with status 2.

Every sequence calls the real Hermes functions (hermes_cli.kanban_db), the
real Kanban tool handlers (tools.kanban_tools) or the real `hermes kanban`
command handlers (hermes_cli.kanban.kanban_command, the function that
`hermes kanban <action>` calls). It prints one line per observation:

    OBSERVED <number> <what was done>: <status>, <assignee>, <implementer>, <other fact>

<implementer> is the `implementer` value of the latest `review_requested`
event of the card.

Safety rules:
- All HERMES_* variables of the calling environment are removed before any
  Hermes module is imported, so the live board database cannot be resolved.
- An audit hook stops the process (exit status 3) when it opens, lists or
  changes a path under /Users/chanbla11mit/.hermes other than the Hermes
  source tree and the new directory. Python bytecode files are not written.
- Hermes receives no process ID other than the ID of a child process that this
  script started (a stand-in for a reviewer run). The script itself sends no
  signal to any process.
- No gateway, no dispatcher loop, no model call; socket creation raises.
- The new directory is removed at the end unless --keep is given.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True

HERMES_ROOT = "/Users/chanbla11mit/.hermes"
HERMES_SRC = "/Users/chanbla11mit/.hermes/hermes-agent"
DEFAULT_BASE = "/Users/chanbla11mit/.hermes/profiles/harness-worker-2/cache/scratch/t_bdfbfb88"

WORKER = "harness-worker-glm-1"          # GLM worker that implements the card
GLM_REVIEWER = "harness-reviewer-glm"    # first reviewer (GLM)
OPUS_REVIEWER = "harness-reviewer"       # second reviewer (Claude Opus)
PASS_MARKER = "jev-glm-review-pass"
HOLD_MARKER = "jev-peak-hold until 19:00"

_GUARDED_EVENTS = {
    "open", "sqlite3.connect", "sqlite3.connect/handle", "os.listdir", "os.scandir", "os.mkdir",
    "os.remove", "os.rename", "os.rmdir", "os.chmod", "shutil.rmtree", "shutil.copyfile",
}


def _install_guards(root: str) -> None:
    """Audit hook and socket guard; installed in the main process and in every child mode."""
    allowed = (HERMES_SRC + os.sep, root + os.sep)

    def hook(event, args):
        if event not in _GUARDED_EVENTS or not args:
            return
        target = args[0]
        if isinstance(target, int) or target is None:
            return
        try:
            path = os.path.abspath(os.fsdecode(target))
        except Exception:
            return
        if path == HERMES_ROOT or path.startswith(HERMES_ROOT + os.sep):
            if path in (HERMES_SRC, root) or path.startswith(allowed):
                return
            os.write(2, f"STOPPED: {event} on {path} is outside the allowed paths\n".encode())
            os._exit(3)

    sys.addaudithook(hook)

    import socket as socket_module

    real_socket = socket_module.socket

    class NoNetworkSocket(real_socket):
        def __init__(self, *args, **kwargs):
            raise AssertionError("the observation script does not use the network")

    socket_module.socket = NoNetworkSocket


def _isolate_environment(root: str) -> None:
    """Remove every HERMES_* variable and point Hermes at ``root``."""
    for name in list(os.environ):
        if name.startswith("HERMES_"):
            del os.environ[name]
    home = os.path.join(root, "home")
    os.environ["HERMES_HOME"] = home
    os.environ["HOME"] = home
    os.environ["HERMES_KANBAN_HOME"] = home
    os.environ["TMPDIR"] = os.path.join(root, "tmp")
    os.environ["HERMES_DISABLE_LAZY_INSTALLS"] = "true"
    os.environ["PATH"] = "/usr/bin:/bin"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _import_hermes():
    if HERMES_SRC not in sys.path:
        sys.path.insert(0, HERMES_SRC)
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    return kb, kbc


def _hermes_kanban(argv):
    """Run `hermes kanban <argv>` through the handler that the `hermes` command calls.
    Returns (exit status, output text)."""
    import argparse
    import contextlib
    import io

    from hermes_cli.kanban import kanban_command
    from hermes_cli.kanban_parser import build_parser

    wrap = argparse.ArgumentParser(prog="hermes", add_help=False)
    parser = build_parser(wrap.add_subparsers(dest="_top"))
    args = parser.parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            status = kanban_command(args)
        except SystemExit as exc:
            status = exc.code
    return (0 if status is None else int(status)), (out.getvalue() + err.getvalue()).strip()


# --- child modes ---------------------------------------------------------------------------

def child_stand_in_run(root: str, task_id: str, run_id: str, ignore_term: str) -> int:
    """Stands for the reviewer run process. Waits for the file `go`, then starts the
    `hermes kanban reassign <id> <Opus reviewer> --reclaim` command as its own child and
    waits for it, as a plugin step inside the run would."""
    import signal
    import subprocess
    import time

    if ignore_term == "1":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.environ["HERMES_KANBAN_TASK"] = task_id
    os.environ["HERMES_KANBAN_RUN_ID"] = run_id
    go = os.path.join(root, f"go-{task_id}")
    deadline = time.time() + 30
    while not os.path.exists(go) and time.time() < deadline:
        time.sleep(0.02)
    with open(os.path.join(root, f"command-{task_id}.out"), "w") as out:
        subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--reassign-command", root,
                        task_id, OPUS_REVIEWER], stdout=out, stderr=subprocess.STDOUT, check=False)
    with open(os.path.join(root, f"stand-in-{task_id}.survived"), "w") as handle:
        handle.write("the stand-in run was not terminated\n")
    return 0


def child_reassign_command(root: str, task_id: str, profile: str) -> int:
    import json
    import time

    _import_hermes()
    started = time.time()
    status, text = _hermes_kanban(["reassign", task_id, profile, "--reclaim"])
    finished = time.time()
    tmp = os.path.join(root, f"command-{task_id}.json.tmp")
    with open(tmp, "w") as handle:
        json.dump({"exit_status": status, "output": text, "started": started, "finished": finished}, handle)
    os.replace(tmp, os.path.join(root, f"command-{task_id}.json"))
    return 0


# --- observation helpers -----------------------------------------------------------------

class Observer:
    def __init__(self, kb, conn):
        self.kb = kb
        self.conn = conn
        self.number = 0

    def implementer(self, task_id):
        row = self.conn.execute(
            "SELECT payload FROM task_events WHERE task_id = ? AND kind = 'review_requested' "
            "ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        if row is None:
            return "none"
        import json
        return str((json.loads(row["payload"] or "{}") or {}).get("implementer"))

    def state(self, task_id):
        row = self.conn.execute("SELECT status, assignee FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return str(row["status"]), str(row["assignee"]), self.implementer(task_id)

    def last_event(self, task_id, kind):
        import json
        row = self.conn.execute(
            "SELECT payload FROM task_events WHERE task_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
            (task_id, kind)).fetchone()
        return (json.loads(row["payload"] or "{}") or {}) if row is not None else None

    def events_after(self, task_id, after_id):
        rows = self.conn.execute("SELECT id, kind FROM task_events WHERE task_id = ? AND id > ? ORDER BY id",
                                 (task_id, after_id)).fetchall()
        return [r["kind"] for r in rows]

    def max_event_id(self, task_id):
        row = self.conn.execute("SELECT MAX(id) AS m FROM task_events WHERE task_id = ?", (task_id,)).fetchone()
        return int(row["m"] or 0)

    def run_profile(self, run_id):
        row = self.conn.execute("SELECT profile, outcome FROM task_runs WHERE id = ?", (run_id,)).fetchone()
        return (row["profile"], row["outcome"]) if row else (None, None)

    def emit(self, what, task_id, other):
        self.number += 1
        status, assignee, implementer = self.state(task_id)
        print(f"OBSERVED {self.number} {what}: status={status}, assignee={assignee}, "
              f"implementer={implementer}, {other}", flush=True)


def _new_card_in_glm_review(kb, conn, title):
    """Create a card, claim it as the GLM worker, request review by the GLM reviewer,
    claim it as the GLM reviewer. Returns (task id, GLM reviewer run id)."""
    task_id = kb.create_task(conn, title=title, body="Observation card.", assignee=WORKER,
                             created_by="observation-script")
    worker = kb.claim_task(conn, task_id)
    ok = kb.request_review(conn, task_id, summary="implemented", reviewer=GLM_REVIEWER,
                           expected_run_id=worker.current_run_id)
    assert ok, "worker request_review failed"
    review = kb.claim_review_task(conn, task_id)
    assert review is not None, "claim_review_task failed"
    return task_id, review.current_run_id


class WorkerEnv:
    """Sets HERMES_KANBAN_TASK and HERMES_KANBAN_RUN_ID as the dispatcher sets them for a run."""

    def __init__(self, task_id, run_id, *, task_only=False):
        self.values = {"HERMES_KANBAN_TASK": task_id}
        if not task_only:
            self.values["HERMES_KANBAN_RUN_ID"] = str(run_id)

    def __enter__(self):
        os.environ.update(self.values)

    def __exit__(self, *exc):
        for name in self.values:
            os.environ.pop(name, None)


def _make_profiles(home):
    """Profile directories so that the tool's reviewer check (profile_exists) passes."""
    for name in (WORKER, GLM_REVIEWER, OPUS_REVIEWER):
        path = os.path.join(home, "profiles", name)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "config.yaml"), "w") as handle:
            handle.write("model:\n  default: observation-only\n")


# --- sequences ----------------------------------------------------------------------------

def sequence_question_1_and_2(obs):
    """Candidate a: the GLM reviewer calls kanban_request_review with the Opus reviewer."""
    import json

    kb, conn = obs.kb, obs.conn
    from tools import kanban_tools as kt

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "candidate a")
    obs.emit("worker run requested review by the GLM reviewer, GLM reviewer claimed it from review",
             task_id, f"run {glm_run} profile={obs.run_profile(glm_run)[0]}, "
                      f"claimed source_status={obs.last_event(task_id, 'claimed').get('source_status')}")
    with WorkerEnv(task_id, glm_run):
        result = json.loads(kt._handle_request_review({"summary": "no findings", "reviewer": OPUS_REVIEWER}))
    obs.emit("GLM reviewer run called the kanban_request_review tool with reviewer=Opus reviewer",
             task_id, f"tool ok={result.get('ok')} error={result.get('error')}, "
                      f"run {glm_run} outcome={obs.run_profile(glm_run)[1]}")
    opus = kb.claim_review_task(conn, task_id)
    with WorkerEnv(task_id, opus.current_run_id):
        result = json.loads(kt._handle_request_changes({"reason": "finding of the Opus reviewer"}))
    obs.emit("Opus reviewer claimed it from review and called kanban_request_changes",
             task_id, f"tool implementer={result.get('implementer')}, "
                      f"changes_requested reviewer={obs.last_event(task_id, 'changes_requested').get('reviewer')}")
    claimed = kb.claim_task(conn, task_id)
    obs.emit("next ready-lane claim without a plugin step (what the dispatcher would start)",
             task_id, f"run {claimed.current_run_id} profile={obs.run_profile(claimed.current_run_id)[0]}, "
                      f"claimed source_status={obs.last_event(task_id, 'claimed').get('source_status')}")

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "candidate a with the plugin step")
    with WorkerEnv(task_id, glm_run):
        kt._handle_request_review({"summary": "no findings", "reviewer": OPUS_REVIEWER})
    opus = kb.claim_review_task(conn, task_id)
    with WorkerEnv(task_id, opus.current_run_id):
        kt._handle_request_changes({"reason": "finding of the Opus reviewer"})
    status, text = _hermes_kanban(["assign", task_id, WORKER])
    obs.emit("candidate a plugin step after the change request: hermes kanban assign <id> <worker>",
             task_id, f"command exit status={status}")

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "GLM reviewer has findings")
    with WorkerEnv(task_id, glm_run):
        result = json.loads(kt._handle_request_changes({"reason": "finding of the GLM reviewer"}))
    obs.emit("GLM reviewer run called kanban_request_changes (it has findings)", task_id,
             f"tool implementer={result.get('implementer')}, "
             f"changes_requested reviewer={obs.last_event(task_id, 'changes_requested').get('reviewer')}")


def sequence_question_3(obs, root, ignore_term):
    """Candidate b: `hermes kanban reassign <id> <Opus reviewer> --reclaim` started inside the run."""
    import json
    import subprocess
    import time

    kb, conn = obs.kb, obs.conn
    from hermes_cli import kanban_db_dispatch as kbd

    label = "stand-in run ignores SIGTERM" if ignore_term else "stand-in run keeps the default SIGTERM action"
    task_id, glm_run = _new_card_in_glm_review(kb, conn, f"candidate b, {label}")
    child = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "--stand-in-run", root, task_id,
                              str(glm_run), "1" if ignore_term else "0"])
    kbd._set_worker_pid(conn, task_id, child.pid)
    fingerprint = conn.execute("SELECT worker_started_at FROM tasks WHERE id = ?", (task_id,)).fetchone()[0]
    obs.emit(f"GLM reviewer run with a child process recorded as worker ({label})", task_id,
             f"fingerprint recorded={fingerprint not in (None, kbd.UNVERIFIED_WORKER_FINGERPRINT)}")
    before = obs.max_event_id(task_id)
    with open(os.path.join(root, f"go-{task_id}"), "w") as handle:
        handle.write("go\n")
    result_path = os.path.join(root, f"command-{task_id}.json")
    child_end = None
    deadline = time.time() + 40
    while time.time() < deadline:
        if child_end is None and child.poll() is not None:
            child_end = time.time()
        if os.path.exists(result_path) and child_end is not None:
            break
        time.sleep(0.02)
    if child.poll() is None:
        child.wait(timeout=30)
        child_end = child_end or time.time()
    with open(result_path) as handle:
        command = json.load(handle)
    reclaimed = obs.last_event(task_id, "reclaimed") or {}
    survived = os.path.exists(os.path.join(root, f"stand-in-{task_id}.survived"))
    obs.emit(f"command started inside the run ({label})", task_id,
             f"command exit status={command['exit_status']}, stand-in run exit code={child.returncode}, "
             f"stand-in run reached its end={survived}, "
             f"stand-in run ended {child_end - command['started']:.1f}s after the command started and "
             f"{command['finished'] - child_end:.1f}s before the command finished, "
             f"reclaimed payload terminated={reclaimed.get('terminated')} sigkill={reclaimed.get('sigkill')} "
             f"retry_status={reclaimed.get('retry_status')}, events in order={obs.events_after(task_id, before)}, "
             f"run {glm_run} outcome={obs.run_profile(glm_run)[1]}")
    opus = kb.claim_review_task(conn, task_id)
    ok, detail = kb.request_changes(conn, task_id, reason="finding of the Opus reviewer",
                                    expected_run_id=opus.current_run_id)
    obs.emit(f"Opus reviewer claimed it from review and requested changes ({label})", task_id,
             f"request_changes ok={ok} returned implementer={detail}")


def sequence_question_4(obs):
    """Way W3 of the decision document: kanban_block (reason jev-glm-review-pass) by the GLM reviewer run,
    then assign and unblock from the GLM reviewer session."""
    import json

    kb, conn = obs.kb, obs.conn
    from tools import kanban_tools as kt

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "way W3")
    with WorkerEnv(task_id, glm_run):
        result = json.loads(kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": "needs_input"}))
    blocked = obs.last_event(task_id, "blocked") or {}
    obs.emit("GLM reviewer run called the kanban_block tool with the reason jev-glm-review-pass (way W3, steps 1 and 2)", task_id,
             f"tool ok={result.get('ok')}, blocked source_status={blocked.get('source_status')} "
             f"kind={blocked.get('kind')} recurrences={blocked.get('recurrences')}, "
             f"run {glm_run} outcome={obs.run_profile(glm_run)[1]}")
    promoted = kb.recompute_ready(conn)
    obs.emit("dispatcher promotion pass (recompute_ready) while the card is blocked", task_id,
             f"promoted count={promoted}")
    with WorkerEnv(task_id, glm_run):
        status, _ = _hermes_kanban(["assign", task_id, OPUS_REVIEWER])
    obs.emit("way W3 step 3: hermes kanban assign <id> <Opus reviewer> inside the GLM reviewer session", task_id,
             f"command exit status={status}")
    with WorkerEnv(task_id, glm_run):
        status, text = _hermes_kanban(["unblock", task_id])
    obs.emit("hermes kanban unblock <id> inside the GLM reviewer session (HERMES_KANBAN_TASK set)", task_id,
             f"command exit status={status}, refused as orchestrator-only={'orchestrator-only' in text}")
    status, _ = _hermes_kanban(["unblock", task_id])
    unblocked = obs.last_event(task_id, "unblocked") or {}
    obs.emit("way W3 step 4: hermes kanban unblock <id> with HERMES_KANBAN_TASK and HERMES_KANBAN_RUN_ID removed",
             task_id, f"command exit status={status}, unblocked resume_status={unblocked.get('resume_status')}")
    opus = kb.claim_review_task(conn, task_id)
    obs.emit("next review-lane claim (what the dispatcher would start)", task_id,
             f"run {opus.current_run_id} profile={obs.run_profile(opus.current_run_id)[0]}")
    with WorkerEnv(task_id, opus.current_run_id):
        result = json.loads(kt._handle_request_changes({"reason": "finding of the Opus reviewer"}))
    obs.emit("Opus reviewer called kanban_request_changes", task_id,
             f"tool implementer={result.get('implementer')}")
    worker = kb.claim_task(conn, task_id)
    ok = kb.request_review(conn, task_id, summary="fixed", reviewer=OPUS_REVIEWER,
                           expected_run_id=worker.current_run_id)
    opus = kb.claim_review_task(conn, task_id)
    with WorkerEnv(task_id, opus.current_run_id):
        result = json.loads(kt._handle_complete({"summary": "approved"}))
    obs.emit("worker fixed and requested review by the Opus reviewer, Opus reviewer called kanban_complete",
             task_id, f"request_review ok={ok}, complete ok={result.get('ok')}")

    # Failure of the assign step: the card stays blocked on the GLM reviewer.
    task_id, glm_run = _new_card_in_glm_review(kb, conn, "way W3, assign fails")
    with WorkerEnv(task_id, glm_run):
        kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": "needs_input"})
    obs.emit("failure of the assign step: state after the block by the GLM reviewer only", task_id, "no further command")
    status, _ = _hermes_kanban(["unblock", task_id])
    obs.emit("a person or orchestrator unblocks that card without assigning it", task_id,
             f"command exit status={status}")

    # Failure of the unblock step: the card stays blocked on the Opus reviewer.
    task_id, glm_run = _new_card_in_glm_review(kb, conn, "way W3, unblock fails")
    with WorkerEnv(task_id, glm_run):
        kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": "needs_input"})
    _hermes_kanban(["assign", task_id, OPUS_REVIEWER])
    promoted = kb.recompute_ready(conn)
    obs.emit("failure of the unblock step: state after the block and the assign, then a dispatcher promotion pass", task_id,
             f"promoted count={promoted}")

    # Block kind equal to the card's earlier block kind: the loop limit sends the card to triage.
    for kind_label, pass_kind in (("same kind as the earlier block", "capability"),
                                  ("a kind different from the earlier block", "needs_input")):
        task_id = kb.create_task(conn, title=f"block kind, {kind_label}", body="Observation card.",
                                 assignee=WORKER, created_by="observation-script")
        worker = kb.claim_task(conn, task_id)
        kb.block_task(conn, task_id, reason="worker needs access", kind="capability",
                      expected_run_id=worker.current_run_id)
        kb.unblock_task(conn, task_id)
        worker = kb.claim_task(conn, task_id)
        kb.request_review(conn, task_id, summary="implemented", reviewer=GLM_REVIEWER,
                          expected_run_id=worker.current_run_id)
        review = kb.claim_review_task(conn, task_id)
        with WorkerEnv(task_id, review.current_run_id):
            kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": pass_kind})
        event = obs.last_event(task_id, "block_loop_detected") or obs.last_event(task_id, "blocked") or {}
        obs.emit(f"earlier worker block kind=capability, pass block with {kind_label} (kind={pass_kind})",
                 task_id, f"recurrences={event.get('recurrences')} limit={event.get('limit')}")


def sequence_question_5(obs):
    """Peak-hours hold of a card in status review whose assignee is the GLM reviewer."""
    import importlib.util

    kb, conn = obs.kb, obs.conn
    task_id = kb.create_task(conn, title="peak hold of a review card", body="Observation card.",
                             assignee=WORKER, created_by="observation-script")
    worker = kb.claim_task(conn, task_id)
    kb.request_review(conn, task_id, summary="implemented", reviewer=GLM_REVIEWER,
                      expected_run_id=worker.current_run_id)
    ok_block = kb.block_task(conn, task_id, reason=HOLD_MARKER, kind="capability")
    ok_schedule = kb.schedule_task(conn, task_id, reason=HOLD_MARKER)
    obs.emit("block_task and schedule_task called on the card in status review", task_id,
             f"block_task returned {ok_block}, schedule_task returned {ok_schedule}")

    plugin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "plugins", "jev")
    sys.path.insert(0, plugin_dir)
    spec = importlib.util.spec_from_file_location("peak_hold_observed", os.path.join(plugin_dir, "peak_hold.py"))
    assert spec is not None and spec.loader is not None, "plugins/jev/peak_hold.py not found"
    peak_hold = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(peak_hold)
    found = peak_hold.holdable_cards(conn, [WORKER, GLM_REVIEWER])
    running_id = kb.create_task(conn, title="GLM worker run already running", body="Observation card.",
                                assignee=WORKER, created_by="observation-script")
    kb.claim_task(conn, running_id)
    found_running = peak_hold.holdable_cards(conn, [WORKER, GLM_REVIEWER])
    obs.emit("present plugin selection peak_hold.holdable_cards for the GLM profiles", task_id,
             f"review card selected={any(t == task_id for t, _ in found)}, "
             f"card with a running GLM worker run selected={any(t == running_id for t, _ in found_running)}")

    review = kb.claim_review_task(conn, task_id)
    ok = kb.block_task(conn, task_id, reason=HOLD_MARKER, kind="capability")
    blocked = obs.last_event(task_id, "blocked") or {}
    obs.emit("claim_review_task without a process, then block_task with the hold marker", task_id,
             f"block_task returned {ok}, source_status={blocked.get('source_status')}, "
             f"run {review.current_run_id} profile={obs.run_profile(review.current_run_id)[0]} "
             f"outcome={obs.run_profile(review.current_run_id)[1]}")
    promoted = kb.recompute_ready(conn)
    status, _ = _hermes_kanban(["unblock", task_id])
    obs.emit("dispatcher promotion pass during the window, then hermes kanban unblock after the window", task_id,
             f"promoted count during the window={promoted}, unblock exit status={status}")

    task_id = kb.create_task(conn, title="peak hold with schedule", body="Observation card.",
                             assignee=WORKER, created_by="observation-script")
    worker = kb.claim_task(conn, task_id)
    kb.request_review(conn, task_id, summary="implemented", reviewer=GLM_REVIEWER,
                      expected_run_id=worker.current_run_id)
    kb.claim_review_task(conn, task_id)
    kb.schedule_task(conn, task_id, reason=HOLD_MARKER)
    status, _ = _hermes_kanban(["unblock", task_id])
    obs.emit("comparison: claim_review_task, schedule_task, then hermes kanban unblock", task_id,
             f"unblock exit status={status}")


def sequence_question_7(obs):
    """Facts for the constraint of Part 6 step 5."""
    import json

    kb, conn = obs.kb, obs.conn
    from tools import kanban_tools as kt
    from hermes_cli import middleware
    from hermes_cli.plugins import _delivery_manager

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "GLM reviewer completes without a plugin")
    with WorkerEnv(task_id, glm_run):
        result = json.loads(kt._handle_complete({"summary": "approved by the GLM reviewer"}))
    obs.emit("GLM reviewer run called kanban_complete with no plugin loaded", task_id,
             f"tool ok={result.get('ok')}")

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "middleware raises before next_call")
    calls = []

    def raising_middleware(**kwargs):
        raise RuntimeError("plugin failure before next_call")

    def refusing_middleware(**kwargs):
        if kwargs.get("tool_name") == "kanban_complete":
            return json.dumps({"error": "a GLM reviewer cannot mark a card done"})
        return kwargs["next_call"]()

    manager = _delivery_manager()
    chain = manager._middleware.setdefault("tool_execution", [])
    for callback, label in ((raising_middleware, "a middleware that raises before next_call"),
                            (refusing_middleware, "a middleware that returns an error without next_call")):
        chain.append(callback)
        try:
            with WorkerEnv(task_id, glm_run):
                returned = middleware.run_tool_execution_middleware(
                    "kanban_complete", {"summary": "approved by the GLM reviewer"},
                    lambda payload: calls.append(label) or kt._handle_complete(payload))
        finally:
            chain.remove(callback)
        obs.emit(f"kanban_complete through the Hermes tool_execution chain with {label}", task_id,
                 f"tool executed={label in calls}, result error={'error' in json.loads(returned)}")
        if label in calls:
            task_id, glm_run = _new_card_in_glm_review(kb, conn, "middleware returns an error")


class ReplacedEnvironment:
    """Replaces os.environ with ``values`` for the duration of one in-process command,
    as if the command were a separate process started with that environment."""

    def __init__(self, values):
        self.values = dict(values)
        self.saved = {}

    def __enter__(self):
        self.saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.values)

    def __exit__(self, *exc):
        os.environ.clear()
        os.environ.update(self.saved)


def pass_selected(obs, task_id):
    """The selection rule that the decision gives the hold script: the card is blocked, the newest
    event of kind blocked has a reason that starts with the pass marker and source_status review,
    and the run that wrote it is a run of the GLM reviewer. Read-only."""
    row = obs.conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    event = obs.conn.execute(
        "SELECT run_id, payload FROM task_events WHERE task_id = ? AND kind = 'blocked' "
        "ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
    if row is None or row["status"] != "blocked" or event is None:
        return False, None, None
    import json
    payload = json.loads(event["payload"] or "{}") or {}
    profile = obs.run_profile(event["run_id"])[0] if event["run_id"] is not None else None
    selected = (str(payload.get("reason") or "").startswith(PASS_MARKER)
                and payload.get("source_status") == "review" and profile == GLM_REVIEWER)
    return selected, payload.get("source_status"), profile


def sequence_question_4_process_lineage(obs):
    """The Hermes rule for descendants of a worker, and the unblock by a process outside
    the worker's process lineage (the LaunchAgent run of scripts/jev-peak-hold)."""
    import json

    kb, conn = obs.kb, obs.conn
    from tools import kanban_tools as kt
    from agent.delegation_context import DELEGATED_CHILD_ENV_MARKER, delegated_child_subprocess_env

    task_id, glm_run = _new_card_in_glm_review(kb, conn, "pass, unblock outside the worker process lineage")
    with WorkerEnv(task_id, glm_run):
        result = json.loads(kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": "needs_input"}))
        worker_environment = dict(os.environ)
    selected, source_status, profile = pass_selected(obs, task_id)
    obs.emit("GLM reviewer run called the kanban_block tool with the reason jev-glm-review-pass", task_id,
             f"tool ok={result.get('ok')}, selection rule of the hold script selects the card={selected} "
             f"(blocked source_status={source_status}, profile of the blocking run={profile})")

    child_environment = delegated_child_subprocess_env(worker_environment)
    marker = child_environment.get(DELEGATED_CHILD_ENV_MARKER)
    facts = (f"environment from delegated_child_subprocess_env: marker set to the Kanban home="
             f"{marker == os.path.abspath(str(kb.kanban_home()))}, "
             f"HERMES_KANBAN_TASK present={'HERMES_KANBAN_TASK' in child_environment}, "
             f"HERMES_KANBAN_RUN_ID present={'HERMES_KANBAN_RUN_ID' in child_environment}")
    with ReplacedEnvironment(child_environment):
        status, text = _hermes_kanban(["assign", task_id, OPUS_REVIEWER])
    obs.emit("hermes kanban assign <id> <Opus reviewer> in a child of the GLM reviewer session started "
             "with delegated_child_subprocess_env", task_id,
             f"{facts}, command exit status={status}, refused for a delegated child={'delegate_task child' in text}")
    with ReplacedEnvironment(child_environment):
        status, text = _hermes_kanban(["unblock", task_id])
    obs.emit("hermes kanban unblock <id> in the same environment", task_id,
             f"command exit status={status}, refused for a delegated child={'delegate_task child' in text}")
    with ReplacedEnvironment(child_environment):
        try:
            kb.unblock_task(conn, task_id)
            raised = "none"
        except PermissionError:
            raised = "PermissionError"
    obs.emit("Hermes function unblock_task called in the same environment", task_id, f"exception={raised}")

    outside_environment = {name: value for name, value in worker_environment.items()
                           if name not in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", DELEGATED_CHILD_ENV_MARKER)}
    unchanged = delegated_child_subprocess_env(outside_environment) == outside_environment
    with ReplacedEnvironment(outside_environment):
        assign_status, _ = _hermes_kanban(["assign", task_id, OPUS_REVIEWER])
        unblock_status, _ = _hermes_kanban(["unblock", task_id])
    unblocked = obs.last_event(task_id, "unblocked") or {}
    obs.emit("hermes kanban assign <id> <Opus reviewer>, then hermes kanban unblock <id>, in an environment with no "
             "HERMES_KANBAN_TASK, HERMES_KANBAN_RUN_ID or HERMES_DELEGATED_CHILD_CONTEXT (as a launchd process)", task_id,
             f"delegated_child_subprocess_env leaves that environment unchanged={unchanged}, "
             f"assign exit status={assign_status}, unblock exit status={unblock_status}, "
             f"unblocked resume_status={unblocked.get('resume_status')}")
    opus = kb.claim_review_task(conn, task_id)
    obs.emit("next review-lane claim (what the dispatcher would start)", task_id,
             f"run {opus.current_run_id} profile={obs.run_profile(opus.current_run_id)[0]}")

    task_id = kb.create_task(conn, title="worker run blocks with the pass reason", body="Observation card.",
                             assignee=WORKER, created_by="observation-script")
    worker = kb.claim_task(conn, task_id)
    with WorkerEnv(task_id, worker.current_run_id):
        kt._handle_block({"reason": f"{PASS_MARKER}: no findings", "kind": "needs_input"})
    selected, source_status, profile = pass_selected(obs, task_id)
    obs.emit("GLM worker implementation run (claimed from ready) called kanban_block with the reason "
             "jev-glm-review-pass", task_id,
             f"selection rule of the hold script selects the card={selected} "
             f"(blocked source_status={source_status}, profile of the blocking run={profile})")


# --- main ---------------------------------------------------------------------------------

def main(argv):
    import shutil
    import tempfile

    keep = "--keep" in argv
    positional = [a for a in argv if not a.startswith("--")]
    base = os.path.abspath(positional[0]) if positional else DEFAULT_BASE
    os.makedirs(base, exist_ok=True)
    root = tempfile.mkdtemp(prefix="glm-reviewer-pass-", dir=base)
    os.makedirs(os.path.join(root, "home"))
    os.makedirs(os.path.join(root, "tmp"))
    _isolate_environment(root)
    _install_guards(root)
    try:
        kb, kbc = _import_hermes()
        db_path = os.path.abspath(str(kb.kanban_db_path()))
        kanban_home = os.path.abspath(str(kb.kanban_home()))
        if not (db_path.startswith(root + os.sep) and kanban_home.startswith(root + os.sep)):
            print(f"Hermes resolved the Kanban database to {db_path} (Kanban home {kanban_home}), "
                  f"which is outside {root}; nothing was written.")
            sys.exit(2)
        print(f"Kanban database: {db_path}")
        print(f"Hermes source: {HERMES_SRC}")
        _make_profiles(os.path.join(root, "home"))
        kbc.init_db()
        conn = kbc.connect()
        obs = Observer(kb, conn)
        sequence_question_1_and_2(obs)
        sequence_question_3(obs, root, ignore_term=False)
        sequence_question_3(obs, root, ignore_term=True)
        sequence_question_4(obs)
        sequence_question_5(obs)
        sequence_question_7(obs)
        sequence_question_4_process_lineage(obs)
        conn.close()
        print(f"All sequences ran: {obs.number} observations.")
    finally:
        if keep:
            print(f"Kept {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--stand-in-run", "--reassign-command"):
        mode, child_root = sys.argv[1], sys.argv[2]
        _install_guards(child_root)
        if mode == "--stand-in-run":
            sys.exit(child_stand_in_run(child_root, *sys.argv[3:6]))
        sys.exit(child_reassign_command(child_root, *sys.argv[3:5]))
    sys.exit(main(sys.argv[1:]))
