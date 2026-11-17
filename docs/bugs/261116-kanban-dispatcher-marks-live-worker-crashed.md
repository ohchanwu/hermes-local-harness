# Kanban dispatcher books a live worker run as crashed ("pid N not alive") and starts a retry beside it

Reported: 2026-11-16, by harness-orchestrator (board `harness`, card `t_d134c710`, the card that ordered this
report). Further evidence arrived in three card comments by harness-orchestrator and was collected read only on
this card.

All times are KST (UTC+09:00). Source references are to the installed Hermes Agent
(`/Users/chanbla11mit/.hermes/hermes-agent/`, commit `9cf7960f274e`) and to psutil 7.2.2, read without changing it; to
the board database `/Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db` (opened read only); to
`/Users/chanbla11mit/.hermes/logs/gateway.log` and `/Users/chanbla11mit/.hermes/logs/gateway-exit-diag.log`; to
`pmset -g log`; and to this repository at the card baseline `1d8c1a9`. The gateway processes ran psutil from their own
environment
`/Users/chanbla11mit/.hermes/installs/e3458f3e9d1307c2/environments/b9a6b99d734d4cdcbd37892b5aca034b/venv/lib/python3.14/site-packages/`
(running gateway pid 82868 has files of that environment open); that psutil copy is byte for byte identical to the copy
under `/Users/chanbla11mit/.hermes/hermes-agent/venv/lib/python3.13/site-packages/psutil/`, where the cited psutil lines
were read, so the line references hold for both copies. Every statement of the diagnosis is marked OBSERVED (read in the
source, the database or the logs) or INFERRED.

## Observed (evidence)
- Nine worker runs on board `harness` were closed with outcome `crashed` and an error text beginning
  `pid <N> not alive` while the worker process was still alive. Last heartbeat is the last `heartbeat` event of
  the run; the state afterwards is the controller's observation recorded on the card.
  - Card `t_b668f19c`, run 489, profile harness-worker-glm-2, started 2026-11-15 19:58:55, closed 20:34:19, pid
    20795, fingerprint `|179474033779`, last heartbeat 20:34:04; alive, running the test loop, had committed
    f1eb2ec. Retry run 492 claimed in the same second.
  - Card `t_92a5f02e`, run 491, profile harness-worker, started 2026-11-15 20:04:58, closed 20:34:19 (the same
    second as run 489), pid 23839, fingerprint `|179474070016`, last heartbeat 20:33:19; alive, running the read
    only live `scripts/verify-state`, had committed a3a4fc6.
  - Card `t_35874d04`, run 503, profile harness-worker-glm-1, started 2026-11-16 00:16:27, closed 00:30:32, pid
    87724, fingerprint `|179475578808`, last heartbeat 00:29:35; alive with child zsh pid 91514 running
    `env -u HERMES_KANBAN_DB python3 scripts/verify-state`. This was the card's last retry, so the card went to
    blocked with `gave_up` (`failures` 2, `effective_limit` 2, `trigger_outcome` `crashed`).
  - Card `t_35874d04`, run 504, profile harness-worker, started 00:32:32, closed 01:01:47, pid 94650,
    fingerprint `|179475675505`, last heartbeat 01:01:45; alive with a `claude --print` child, had committed
    091362c. Retry run 506 claimed in the same second.
  - Card `t_d134c710`, run 505, profile harness-worker-glm-3, started 00:33:33, closed 01:01:47 (the same second
    as run 504), pid 95553, fingerprint `|179475681573`, last heartbeat 01:00:48; alive, no commit, no file
    change.
  - Card `t_d134c710`, run 507, profile harness-worker-glm-3, started 01:01:47, closed 01:52:28, pid 27375,
    fingerprint `|179475850865`, last heartbeat 01:52:09; alive. The `gave_up` event of this card was recorded in
    the same second (`failures` 2, `effective_limit` 2); the orchestrator unblocked the card at 01:53:56 and run
    515 started at 01:54:28.
  - Cards `t_e505dccb`, `t_eea37bed`, `t_93fa80bc`, runs 509, 510, 511, started 01:36:02 to 01:36:03, all closed
    01:52:28, pids 69488, 69500, 69514, fingerprints `|179476056410`, `|179476056432`, `|179476056457`, last
    heartbeats 01:52:08 to 01:52:12; all alive with parent pid 1. Run 509 had committed 028e4cd. Retry runs 512
    to 514 were claimed in the same second.
- So the bookings happened in four dispatcher passes, each pass closing its runs in one second: 20:34:19 (runs
  489, 491), 00:30:32 (run 503), 01:01:47 (runs 504, 505) and 01:52:28 (runs 507, 509, 510, 511).
- The pass of 20:34:20 also closed runs of other boards in the same second: gateway.log lines 8957 to 8959
  record, in that second, the dispatcher summaries `crashed=2` for board harness, `crashed=1` for board jobcron
  and `crashed=2` for board jss-genr, and gateway.log line 8962 records the notifier `crashed` event for card
  `t_ce91a955` (profile jss-orchestrator). This card's scope is board harness, so those bookings are not
  analyzed further here.
- One gateway process, pid 5063, served all boards from 2026-11-14 16:13:49 until it received SIGTERM at
  2026-11-16 01:49:24 and exited at 01:50:01 (gateway.log line 9115; gateway-exit-diag.log records
  `gateway.start` for pid 5063 at 2026-11-14T07:13:49Z and `asyncio.run.returned` at 2026-11-15T16:50:01Z). This
  process recorded the fingerprints of all nine runs and booked the passes of 20:34:19, 00:30:32 and 01:01:47.
  Its replacement, pid 82868, started at 01:50:27 and booked the pass of 01:52:28 (gateway.log line 9211,
  `crashed=4`, `auto_blocked=1`). The dispatcher summary lines of the passes are gateway.log lines 8957, 9095 and
  9211; the pass of 00:30:32 has no summary line because the summary is logged only for a board that spawned a
  run (`gateway/kanban_watchers_dispatcher.py:330-346`), and run 503 was the card's last retry, so the pass
  spawned nothing; the notifier line 9081 (00:30:37, events `gave_up`, `crashed`) confirms the pass.
- The `claimer` field of every crashed event is the claim lock of the run, `Chanwus-MacBook-Pro-2.local:5063`,
  also for the pass booked by gateway 82868; the field names the claim owner, not the process that booked the
  pass.
- `task_runs.worker_pid` is null for the nine closed runs; for reference, the columns are also null now for runs 513,
  514 and 515, which had carried their pids while they were running. This is expected: `_end_run` keeps the columns on
  the closed run row (`hermes_cli/kanban_db.py:2027-2040`), and `reap_terminal_workers`
  (`hermes_cli/kanban_db_dispatch.py:504-560`, called at line 2194 of every pass) clears them for rows that ended at
  least 120 seconds earlier (`TERMINAL_WORKER_REAP_GRACE_SECONDS`, line 51); for a live pid whose fingerprint no longer
  matches, `_worker_alive` returns false (line 540) and `_reap_terminal_worker_row` clears the columns without a
  `terminal_worker_reaped` event (lines 547 to 556) and without signalling the process, which matches the database: no
  such event exists for any of the nine runs. The sweep that made the bookings reads the `tasks` table, so the null
  columns did not affect any booking. The fingerprints survive in the `spawned` events, whose values are listed above;
  the part before the pipe is empty on this host.
- Host sleep is excluded for the whole window: `pmset -g log` records the last `Entering Sleep` at 2026-11-14
  07:57:01 and the last wake entry at 2026-11-14 08:38:35; there is no sleep or wake entry between 2026-11-15
  19:00 and 2026-11-16 02:00.
- A fresh interpreter read by this card (about 02:20): `psutil.boot_time()` = 1788934586.0, equal to the value
  the same interpreter recorded at import and to `sysctl kern.boottime` (sec = 1788934586, Wed Sep 9 15:16:26
  2026). The create times of the live runs 514 (pid 95537, 1794761548.357) and 515 (pid 492, 1794761669.036)
  produce exactly the recorded fingerprints `|179476154836` and `|179476166904`. Runs 513 to 515 were spawned by
  gateway 82868 and were not misclassified.
- The worker of run 505 examined the same mechanism before its own booking; its last recorded output (quoted on
  the card and in the error text of run 507) ends: "the gateway's boot_time() still reads the shifted value
  (adjustment still +1, fingerprint matches). My fresh venv interpreter read INIT_BOOT_TIME = boot_time() =
  ...586.0".
- Earlier reports of the same fault class:
  `docs/bugs/261023-kanban-live-worker-marked-crashed-duplicate-dispatch.md` (boards jobcron, anki and harness,
  cards t_19fd7dee, t_76b6785e, t_ee5b93ea, t_8e492e23, t_77fd441e, t_87bc9e2f, t_8b704011, t_5f91d067). That
  report reads the recorded `started_at` values such as `"|179272758315"` as malformed ("a leading `|` and a
  truncated value"); this report identifies them as the normal macOS form of the fingerprint, with an empty epoch
  part, and not as damage.
- Card `t_653b7074`, run 600, profile harness-worker, started 2026-11-16 19:22:23, closed 20:11:49, pid
  3279, fingerprint `|179482454823`, last heartbeat 20:11:45; alive afterwards, running the deployment
  script `d6.sh apply` (child pid 35606), which ended at 20:18:01 with `done ... count 50` and 35 exit
  lines, all 0; the controller stopped the worker process at 20:19:57 (card comments 557, 558 and 560).
  Every field value is OBSERVED in the board database (`task_runs` row of run 600; the `claimed`,
  `spawned`, `crashed` and heartbeat events; the error text begins `pid 3279 not alive`; the fingerprint
  column of the row is null now and the fingerprint survives in the `spawned` event, as described
  above); the state afterwards is the controller's observation recorded on the card, as for the nine
  runs above. INFERRED: the booking is of the same kind as the nine above, a live worker process booked
  as crashed, observed after this report was written. The `crashed` event carries the worker's last
  recorded output, which shows shell steps of about 390 to 420 seconds each (OBSERVED). The record file
  of run 600 was untracked and not committed (comment 558, OBSERVED). Retry run 601 claimed and spawned
  in the same second, pid 11050, started 2026-11-16 20:11:49 (OBSERVED in the board database).
  gateway.log line 10668 records the notifier `crashed` event for the card at 20:11:55 (OBSERVED); the
  filtered read authorized on this card found no other line of gateway.log or gateway-exit-diag.log
  naming the card, run 600, run 601, pid 3279 or pid 11050.

Host sleep is excluded for this run as well: `pmset -g log` records no sleep or wake entry between
2026-11-16 19:22:23 and 20:11:49, the window of run 600 (the last sleep and wake entries of 2026-11-16
are at 18:37:12 and 18:41:14, both before the run; OBSERVED); the gap between the last heartbeat
(20:11:45) and the close time (20:11:49) is 4 seconds, inside the 2 to 60 second range of the nine
runs above, larger only than the 2 seconds of run 504 and smaller than the other eight, so the gap is
not unusually large (INFERRED by subtraction of the two observed times).

## Impact
- In each pass a retry run was claimed in the same second and worked on the same card and the same worktree while
  the old process kept running, so two runs worked on the same files until the controller stopped the old process
  and its children with SIGTERM.
- Each booking counted one failure toward the failure limit of 2. Card `t_35874d04` went to blocked ("gave up
  (retries exhausted)") on its last retry; card `t_d134c710` went to blocked (event `gave_up`, `failures` 2,
  `effective_limit` 2, at 01:52:28) and needed the orchestrator to unblock it at 01:53:56, and two of its runs, 505 and
  507, were each stopped by the controller before their work was finished, so their reading of the source produced no
  commit.
- Four completed commits (f1eb2ec, a3a4fc6, 091362c, 028e4cd) reached review only because the retry runs checked
  the commits of the runs that the dispatcher had booked as crashed.
- The controller had to find and stop nine live process trees by hand, and to check each worktree for
  uncommitted changes afterwards.

## Diagnosis
- (F1) OBSERVED, `hermes_cli/kanban_db_dispatch.py:1146-1212`: the sweep `_reclaim_dead_workers` selects `tasks`
  rows with status `running` and `worker_pid` not null (lines 1151 to 1154), skips a row inside the launch grace
  of 30 seconds (lines 1160 to 1163; `hermes_cli/kanban_db.py:303-305`, `317-319`), skips a row when
  `_worker_alive` returns true (line 1165), and otherwise closes the run with outcome `crashed`, clears the claim
  and the worker columns (lines 1173 to 1190) and hands the booking to the crash accounting (lines 1211 to 1212,
  through `detect_crashed_workers` at line 1306). The
  error text `pid {pid} not alive` is built at `hermes_cli/kanban_db_dispatch.py:1124` when the exit kind is
  `unknown`: the reap registry has no entry for the pid (`_classify_worker_exit`, lines 226 to 247) and the worker
  log has no exit trailer (`_worker_log_exit_code`, lines 265 to 278). The sweep never reads the heartbeat time.
- (F2) OBSERVED, `hermes_cli/kanban_db_dispatch.py:381-414`: `_worker_alive` returns false when `_pid_recycled`
  returns true. Every fingerprint of the nine runs has the pipe form, so lines 405 and 406 apply:
  `_process_fingerprint(int(pid)) != started_at`, an exact string comparison with no tolerance.
- (F3) OBSERVED, `hermes_cli/kanban_db_dispatch.py:367-377`, `gateway/status.py:464-500`,
  `gateway/drain_control.py:41-56`: the fingerprint is `"<epoch>|<start>"`. On macOS the start part is
  `int(round(psutil.Process(pid).create_time() * 100))` (`gateway/status.py:492-494`), and the epoch part is the
  empty string because `current_instantiation_epoch` reads only `/proc` files, which do not exist on this host.
  The database fingerprints `|179...` confirm this form.
- (F4) OBSERVED, `psutil/_psosx.py:276-296` and `473-478`: on macOS `Process.create_time()` passes the raw value
  through `adjust_proc_create_time`, which computes `diff = INIT_BOOT_TIME - boot_time()` (line 289) and, when
  `abs(diff)` is at least one second, returns `ctime - diff` for a negative difference and `ctime + diff`
  otherwise (lines 293 to 296). When the difference is negative it is subtracted, not added; in both branches
  the shift is the absolute value of the difference, so the reported create time is always moved later by
  `abs(INIT_BOOT_TIME - boot_time())`. `INIT_BOOT_TIME` is fixed once, when psutil is imported into that
  process; the shift applies to every process read by that process after the change.
  `create_time(monotonic=True)` returns the value without the shift. So the same live process can yield different
  create time values to the same reader over time, and different reader processes can disagree about the same
  live process.
- (F5) OBSERVED, `gateway/status.py:442-453`, `hermes_cli/local_runtime/recovery.py:44-50`,
  `hermes_cli/process_identity.py:179-181`: the installed Hermes code itself treats one to two seconds of drift of
  these readings on macOS as normal: the comment at `gateway/status.py:442-445` names the "macOS
  ``kern.boottime`` adjustment, #117505", `START_TIME_DRIFT_TOLERANCE = 200` (two seconds at the ×100 scale) is
  defined for the comparator `start_time_fingerprints_match`, which the local runtime recovery uses, and
  `_same_incarnation` in `process_identity.py` allows two seconds for the same purpose in the spawn ledger. The
  dispatcher's pipe branch (F2) uses exact equality and none of these tolerances.
- (F6) INFERRED: in each of the four passes the reading gateway process produced create time values that did not
  equal the recorded fingerprints, because the values it computed at pass time were shifted by at least one
  second relative to the values it had computed at spawn time (F4) or, for the pass of 01:52:28, relative to the
  values that the previous gateway process had recorded. This explains the observed shape of the fault: several
  runs closed in the same second on one board; runs of three boards closed in the same second by one process
  (one reader, one changed input); and the pass of 01:52:28 closing exactly the four runs whose fingerprints the
  previous gateway had recorded (507, 509, 510, 511) while the runs whose fingerprints gateway 82868 recorded
  itself (512 to 515) were left alone.
- (F7) INFERRED, and the underlying system event is not established: what changed the boot time value inside a
  gateway process between its import of psutil and a later read. Host sleep is excluded (Observed above). psutil
  documents its adjustment for "system clock updates" (`_psosx.py:285`). The worker of run 505 measured a fresh
  interpreter reading the same boot time as the static sysctl value and estimated the difference inside the
  gateway at about one second (quoted above). Neither the gateway log nor `pmset -g log` records a clock
  adjustment, so the event itself cannot be attributed with the evidence available on this card.
- (F8) OBSERVED, two further conditions of the same path, both not applicable or not established here: a create
  time that cannot be read makes `_process_fingerprint` return None, and None does not equal the recorded string,
  so the run is booked as crashed (`hermes_cli/kanban_db_dispatch.py:367-377`; `gateway/status.py:495-496`); such a
  read failure would have to affect several processes in one pass to explain a pass that closed several runs, which
  fits the evidence less well than F6 but is not excluded for any single run. A false return from `_pid_alive`
  (`hermes_cli/kanban_db_dispatch.py:311-358`) is excluded because the controller observed the processes alive.
- (F9) OBSERVED: no other check protects a worker whose heartbeats are fresh: the crash sweep consults only the
  launch grace and `_worker_alive` (F1), and the claim extension path of expired claims is not involved because
  the claims had not expired.

## Likely area
Hermes Agent Kanban dispatcher: the worker identity comparison `_pid_recycled` at
`hermes_cli/kanban_db_dispatch.py:396-414` (exact equality, lines 405 and 406), the fingerprint construction
`_process_fingerprint` at `hermes_cli/kanban_db_dispatch.py:367-377` with `gateway/status.py:464-501`, and the
macOS create time source in psutil (`_psosx.py`, `adjust_proc_create_time`), which makes the fingerprint value
depend on the reading process and on the time of the read.

## The controller's present procedure for a recovery
1. On a `crashed` event whose error text begins `pid <N> not alive`, check `ps -p <N>` (and the process tree)
   before treating the run as dead. If the process is alive, the booking is presumed false.
2. Stop the old process and its children with SIGTERM by explicit pid; the dispatcher does not signal a worker on
   this path, so the old process otherwise keeps running beside the retry.
3. Confirm that the worktree of the card has no uncommitted change, and check whether the old run had made a
   commit that the retry must not lose or duplicate.
4. Leave a comment for the retry run on the card stating what was stopped and what was found.
5. If the card went to blocked because the false bookings exhausted the retry limit, unblock or reassign the card
   so that the work continues.
This procedure was applied to all nine runs (card comments of t_d134c710; comments 492, 493, 501 for the first
three cards).

## Proposals
### Harness side, without changing the Hermes source
- A read only check that detects the fault: query the board database read only for runs closed as `crashed` whose
  error text begins `pid <N> not alive`, and test each pid with `ps -p <N>`; report every pid that is still
  alive. This uses the documented database of the board and standard process tools only, and stays compatible
  with Hermes upgrades. Implementation and deployment are out of scope for this card and need a separate card.
- Keep the recovery procedure above as the documented response; the orchestrator already applies it. Writing it
  into the orchestrator skill is a separate card.
- No configuration of the dispatcher prevents the misclassification: the launch grace
  (`HERMES_KANBAN_CRASH_GRACE_SECONDS`, `hermes_cli/kanban_db.py:317-319`) protects only the first 30 seconds,
  and the sweep has no heartbeat condition (F1), so shorter or longer runs are equally exposed.

### Upstream report text (draft, not filed)
Title: Kanban dispatcher books a live worker as crashed ("pid N not alive") when psutil shifts create_time on
macOS.
Body, in short: `_pid_recycled` (`hermes_cli/kanban_db_dispatch.py:405-406`) compares the worker fingerprint
`<epoch>|<round(create_time*100)>` by exact string equality. On macOS `psutil.Process.create_time()` passes
through `adjust_proc_create_time`, which moves every reading later by the absolute value of the difference
between the reading process's import time boot value and a later `boot_time()` read, whenever that difference is
at least one second (`psutil/_psosx.py:276-296`). A gateway process whose boot time value changes after it
imported psutil therefore classifies every running worker as a recycled pid in one dispatcher pass, closes the
runs as `crashed` with `pid <N> not alive`, and starts retry runs beside the live workers. Nine runs on board
harness were closed in four such passes on one host, and in one of those passes further runs of two other boards
closed in the same second (evidence above); a gateway restart produces the same fault in the other direction,
because the replacement process reads unshifted values against fingerprints the previous process recorded
shifted. `gateway/status.py:442-453` already defines `START_TIME_DRIFT_TOLERANCE = 200` for exactly this drift
("macOS ``kern.boottime`` adjustment, #117505") and `local_runtime/recovery.py` already compares with that
tolerance; the dispatcher does not.
Requests:
1. Compare the start part of the fingerprint with the existing tolerance instead of exact string equality, for
   example by using `start_time_fingerprints_match` (`gateway/status.py:449-453`) when both values are numeric.
2. Or build the fingerprint from `psutil.Process.create_time(monotonic=True)` on macOS, which skips the
   adjustment (`_psosx.py:477-478`) and matches the semantics of the Linux `/proc` field, which counts from the
   boot and which the fingerprint design already assumes; recording it at spawn and at read would then be stable
   across clock updates and across processes.
3. Do not close a run as `crashed` on a fingerprint mismatch alone while its heartbeat is fresh; hold the claim
   instead, as the `unverified` fingerprint marker already does, and require a second observation.
4. Record the recorded fingerprint and the freshly read value in the `crashed` event payload, so that a mismatch
   can be attributed after the fact; the current payload carries only the pid, the claimer and the last worker
   output.

## Upstream status
Not checked on this card: no network access was authorized. The earlier report
`docs/bugs/261023-kanban-live-worker-marked-crashed-duplicate-dispatch.md` lists, in its upstream section, issue
#141758 (dispatcher records a live worker as `crashed: pid not alive` on macOS and dispatches a duplicate run)
and pull request #144350, whose stated root cause matches this diagnosis: on macOS the worker fingerprint is
compared by exact string equality and psutil shifts `create_time()` when the system clock is stepped. The new
evidence of this report adds the clustering of several runs in one pass on one board and across boards, the
gateway restart variant of the mismatch, the exclusion of host sleep, and the drift tolerance that already exists
in the repository code but is not used by the dispatcher.

## Note on tests
No test under `tests/` checks the set of files under `docs/bugs/`; every existing test reference names one fixed
report (`tests/test_overgating_review_policy.py`, `tests/test_telegram_unserved_update_patch.py`,
`tests/test_fallback_provider_settings.py`, `tests/test_harness_bug_report_skill.py`, and the two assertions in
`tests/test_verify_state.py` that only require the string `docs/bugs`). This card therefore changes no test.
