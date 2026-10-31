# Kanban dispatcher records a live worker as crashed and starts a second worker

Reported: 2026-10-23, by the Jobcron orchestrator (board `jobcron`, card `t_19fd7dee`).

## Observed
- Run 299 (`jobcron-worker`, pid 29939) was recorded as `crashed` with
  `protocol_violation` ("worker exited cleanly (rc=0) without kanban_complete,
  kanban_block or kanban_request_review"). The process was still alive,
  reparented to pid 1. Its working directory was the card worktree, and it had a
  live Claude child (pid 36866, started 12:16:21 KST, about 12 minutes after the
  run started).
- The dispatcher then started run 300 (pid 31574) on the same card and worktree.
  Both workers were active at once. The run-299 worker kept writing files in the
  worktree after run 300 started.
- Run 300 detected the collision and blocked. The repeated-block rule then routed
  the card to `triage`. The only CLI path out of triage is `specify`, which
  rewrites the title and body with a model. `unblock`, `promote` and `block` all
  refuse a triage card, so the orchestrator had to archive the card and create a
  replacement.

## Impact
Two workers writing to one worktree, on a card authorised to read the owner's
private database. No database read happened, because the first worker had not
reached that step.

## Likely area
The wrapper's exit detection (rc=0 reported while the `hermes_cli.main` process
was still running), possibly the same root cause as the earlier Jobcron I9
false-death report. The dispatcher should confirm the recorded pid has exited
before it marks a run crashed and reclaims the card.

## Requested
1. Do not reclaim a card while the previous run's process tree is alive.
2. Provide a non-model command to move a triage card back to `ready`.

## Recurrence (same day, card `t_76b6785e`)
- Run 301, pid 42824, started 12:26:52 KST. At 12:53:00 it was recorded as `crashed` with "pid 42824 not alive", while the process was alive. It started a new Claude child (pid 64596) at 12:53:09.
- Run 302 (pid 63195) was spawned at 12:53:00 on the same worktree.
- Both incidents happened about 26 minutes after the run started, and heartbeats were arriving until the crash record (the last one at 12:51:43). The spawned event records `started_at` as `"|179272758315"`, so the liveness check may compare process start times in a mismatched format.
- The orchestrator blocked the card and stopped both process trees.

## Second recurrence (same day, card `t_ee5b93ea`): about 60 seconds, not 26 minutes
- Run 308, pid 33188, process start 14:04:17 KST (run `started_at` 1792731857). A heartbeat was recorded at 1792731858. At 1792731917 (14:05:17 KST, about 60 s after start) the run was recorded as `crashed` with "pid 33188 not alive", while pid 33188 was alive, had its working directory in the card worktree, and had a live Claude child (pid 33237) that was writing files.
- Run 309 (pid 34416) was spawned at 1792731917. Its `spawned` event again records `started_at` as `"|179273191928"` (a leading `|` and a truncated value). Run 309 found pid 33188 alive in the worktree and blocked itself; it did not stop the other worker.
- Claimer in both the `crashed` and `claimed` events: `Chanwus-MacBook-Pro-2.local:30895`.
- Consequence: keeping cards under about 23 minutes does not avoid the fault. The false crash can happen at any point in a run.
- The orchestrator left pid 33188 running as the only owner and kept the card blocked so no third worker is dispatched.

## Third recurrence (same day, cards `t_8e492e23` and `t_77fd441e`): two live processes in one dispatcher pass
- Both records were made at the same time, 1792736611 (15:23:31 KST), by claimer `Chanwus-MacBook-Pro-2.local:30895`.
- Card `t_8e492e23`, run 320 (jobcron-worker-2, pid 82085, started 1792736190): recorded as `crashed` with "pid 82085 not alive" about 7 minutes into the run. At 15:23:45 and 15:25:07 KST, `ps` showed pid 82085 alive with its working directory in the card workspace, and it had written a file there. Run 323 (pid 85146, `spawned` `started_at` `"|179273661490"`) found it on the single-worker check and blocked itself.
- Card `t_77fd441e`, review run 322 (jobcron-reviewer, pid 84614, started 1792736551): recorded as a `protocol_violation` ("worker exited cleanly (rc=0) without kanban_complete …") at the same time. At 15:23:45 KST, `ps` still showed pid 84614 alive with its working directory in the card workspace. A second reviewer, run 324 (pid 85147, `started_at` `"|179273661491"`), was dispatched, so two reviewer processes ran on the same card for a short time.
- Consequence: the fault also affects review runs, and the "exited cleanly" message can be recorded for a process that is still running.

## Fourth recurrence (2026-10-29, board `anki`, cards `t_d9e2b517` and `t_b232a1ed`)
- Reported by the `anki-orchestrator` profile. Both records were made by claimer `Chanwus-MacBook-Pro-2.local:29456`; dispatcher pid 29456 was the parent pid of both worker processes.
- Card `t_d9e2b517`, run 99 (`anki-worker`, pid 48768, started 20:11:49 KST): heartbeats arrived from 20:12 to 20:13:57 KST. At 20:14:46 KST, about 3 minutes into the run, the run was recorded as `crashed` with "pid 48768 not alive", and the notifier sent "Task t_d9e2b517 crashed (worker exited); dispatcher will retry." At 20:19:38 KST, `ps` showed pid 48768 alive (state `Ss`, started 20:11:50) with a `claude` child (pid 51105) that had started at 20:15:05 KST, after the crash record.
- At the same time, 20:14:46 KST, the dispatcher claimed run 100 and spawned pid 50734 in the same card worktree. Its `spawned` event records `started_at` as `"|179327249095"`. Both processes ran the same generator in the same worktree and scratch directory (at 11:15:24 and 11:15:36 UTC), and one process removed and rewrote an untracked file of the other. Run 100 detected the other process and blocked itself at 20:16:10 KST; repeated blocks moved the card to `triage` (`block_loop_detected`).
- At 20:19:40 KST the run-99 process committed 7b8a5658272108774b5aabb2f2db40d98c366a5b on the card branch, after its run had been recorded as crashed.
- At about 20:20 KST the orchestrator stopped pid 48768 and pid 51105 with SIGTERM by explicit pid. Pid 48768 became a zombie (`Z <defunct>`) of parent pid 29456, which suggests that the parent had not reaped it. The orchestrator kept the commit at a ref as evidence and moved the card from `triage` to `todo`/`ready` with `specify_triage_task`.
- Card `t_b232a1ed`, run 101 (`anki-worker-2`, pid 58153, started 20:24:49 KST): heartbeats arrived until 20:46:23 KST. At 20:46:57 KST, about 22 minutes into the run, the run was recorded as `crashed` with "pid 58153 not alive". In the same second the dispatcher claimed run 102 and spawned pid 95733 in the same card worktree. Its `spawned` event records `started_at` as `"|179327441761"`.
- At about 20:47:40 KST, `ps` showed pid 58153 alive (state `Ss`, started 20:24:49, elapsed 22:32) with live children: `claude` (pid 58189), a pyright language server (pid 63549), and a unit test shell (pid 96429) that started at about 20:47:20 KST, after the crash record.
- At about 20:48 KST the orchestrator stopped pids 58153, 58189, 63549, 96429 and 96471 with SIGTERM by explicit pid. Pid 58153 was first a zombie (`Z`) and was then reaped. Run 101 made no commit; its untracked files were kept as evidence.
- Both runs had run times far below the card runtime cap of 7200 s, and the false crash records came about 3 minutes and about 22 minutes after the run started, so the run age does not explain the fault.
- Hypothesis of the filer, not verified: the liveness check may treat a zombie or a process in another state as "not alive", or may compare a recorded start time in the malformed `started_at` form and conclude that the pid was reused.
- Same fault on 2026-10-31, board `harness`, card `t_87bc9e2f` (the card that adds this section), reported by the `harness-orchestrator` profile: at 14:19:52 KST run 205 (pid 46429) was recorded as `crashed` with "pid 46429 not alive", while pid 46429 was alive (environment variable `HERMES_KANBAN_TASK=t_87bc9e2f`, working directory the card worktree). Run 208 (pid 6966) then started in the same worktree. The `spawned` event for run 205 records `started_at` as `"|179342339013"`.
- The `harness-orchestrator` profile sent SIGTERM to pid 46429 and its child processes; all of them had exited by 14:21 KST. Run 208 continued. The uncommitted change that run 205 left in this file (13 added lines) was its partial work, and run 208 kept it.
- Not checked upstream for this recurrence: network access was not authorized on this card.

## Upstream status
Checked on 2026-10-26 against NousResearch/hermes-agent. No new upstream issue was filed, because the defect is already reported:
- Issue #141758: the dispatcher records a live worker as `crashed: pid not alive` on macOS and dispatches a duplicate run (open).
- Issue #138431: Kanban records `protocol_violation` and starts a new run while the original worker session continues on macOS (open).
- Issue #142301: `reclaim_task` releases the claim of a live worker, so a second worker starts beside it (open).
- Pull request #144350 (open, not merged on 2026-10-26) states a root cause that matches the `started_at` values above: on macOS the worker fingerprint `<epoch>|<round(create_time*100)>` is compared by exact string equality, and psutil shifts `create_time()` when the system clock is stepped. Pull request #140402 (open) holds a claim while the previous run's worker is alive.
- Requested item 2 (a command without a model call that returns a triage card to `ready`) is reported as issue #110339 and issue #122271 (both open).
