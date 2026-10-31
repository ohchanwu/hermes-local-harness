# Kanban respawn guard held a ready card as `blocker_auth` because the stored error text of an earlier crashed run contained the word "Authorization"

Reported: 2026-10-29, by the Anki orchestrator (`anki-orchestrator`, filing session `20261023_184637_9df5ff55`; board `anki`, card `t_d9e2b517`, assignee `anki-worker`). Recorded from harness card `t_cb8d65f6`.

All times are KST (UTC+09:00). Source references are to the installed Hermes Agent (`/Users/chanbla11mit/.hermes/hermes-agent/`, commit `9cf7960f274e`), read without running, importing or changing it, and to this repository at commit `0c9a454`.

## Observed
- Run 99 was recorded `crashed` at 2026-10-29 20:14:46 with `last_failure_error` set to "pid 48768 not alive Worker's last output: ..." followed by the last captured output of the worker (470 characters).
- Run 100 then ended with outcome `blocked` at 20:16:10 (`block_loop_detected`; the card moved to triage).
- At about 20:21 the orchestrator moved the card from triage to ready with `specify_triage_task`. That path does not clear `last_failure_error`.
- From 20:21:48 to 21:17:03 the dispatcher appended 56 `respawn_guarded` events with the payload `{"reason": "blocker_auth"}` and never started a worker. The task row had status `ready` and `consecutive_failures` 1.
- The orchestrator found, by reading the source only, that `check_respawn_guard` skips the blocker regular expression only when the latest ended run has outcome `crashed`. The latest run (100) had outcome `blocked`, so `_RESPAWN_BLOCKER_RE` was applied to the stored crash text of run 99. It matched the word `Authorization`. That word came from a Python command of the worker that printed note text from the user's Anki deck (a search pattern for a note about HTTP headers). It was not an authentication failure.
- No gateway notification was sent for the 56 guarded dispatcher passes, so the hold was visible only in the event log.
- Expected: the `blocker_auth` guard applies only to error text that describes the failure of the latest run (quota, rate limit or authentication), not to captured worker output of an earlier crashed run; and a triage-to-ready transition that is a deliberate requeue clears or ignores stale failure text, as `unblock_task` does.

## Impact
- A ready card with a valid assignee received no worker for about 56 minutes, until the orchestrator blocked and unblocked it.
- The guard does not count a failure and does not block the card (see Diagnosis (a)), so the card does not reach the failure limit and does not move to `blocked`. Without an explicit block and unblock, the card can stay in `ready` without a worker.
- The guard can be triggered by any word in the captured worker output that the regular expression lists, for example a word printed from user data, when a later run of the same card ends with an outcome other than `crashed` and the stored error text is not replaced.
- No gateway notification reports the hold (see Diagnosis (d)). The owner sees the hold only in the event log.

## Diagnosis
Each statement is marked "Established from source" or "Not established".

### (a) Which text the regular expression is applied to, and when the guard skips it
- Established from source: `_RESPAWN_BLOCKER_RE` is a case-insensitive regular expression with word boundaries that includes `authoriz(?:e|es|ed|ing|ation)`, so it matches the word "Authorization" anywhere in the text (`hermes_cli/kanban_db_dispatch.py:63-71`).
- Established from source: the dispatcher calls `check_respawn_guard` for each ready or review row before it claims the row (`hermes_cli/kanban_db_dispatch.py:2073`).
- Established from source: `check_respawn_guard` reads the text from the task row, `tasks.last_failure_error` (`hermes_cli/kanban_db_dispatch.py:1546-1549`), not from the latest run. It selects the latest ended run separately, ordered by `ended_at` (`hermes_cli/kanban_db_dispatch.py:1561-1566`).
- Established from source: the guard returns before the regular expression check when the latest ended run has outcome `rate_limited` (`hermes_cli/kanban_db_dispatch.py:1572-1583`). When the latest ended run has outcome `spawn_failed` with infrastructure metadata inside the cooldown, it returns `infrastructure_cooldown` (`hermes_cli/kanban_db_dispatch.py:1567-1571`).
- Established from source: otherwise the guard applies the regular expression to `last_failure_error` whenever the latest ended run has an outcome other than `crashed`, and returns `blocker_auth` on a match (`hermes_cli/kanban_db_dispatch.py:1589-1592`). The comment at `hermes_cli/kanban_db_dispatch.py:1585-1588` states that the exception for `crashed` exists because the stored error of a crash includes the captured worker output. The exception tests only the outcome of the latest run; it does not test which run wrote `last_failure_error`.
- Established from source: `block_task` ends the open run with outcome `blocked` (`hermes_cli/kanban_db.py:3369-3371`). With the run 100 end time later than the run 99 end time, the latest ended run is run 100 with outcome `blocked`, so the exception for `crashed` does not apply, and the regular expression is applied to the text that run 99 stored.
- Established from source: when the guard returns a reason, the dispatcher records the reason in the dispatch result, appends one `respawn_guarded` event with the payload `{"reason": ...}`, and skips the row (`hermes_cli/kanban_db_dispatch.py:2073-2086`). This path records no failure, changes no task field, and does not block the task. The docstrings at `hermes_cli/kanban_db_dispatch.py:140-143` ("also auto-blocked") and `hermes_cli/kanban_db_dispatch.py:1536-1537` ("the breaker still trips eventually") describe a block that this path does not perform. Because no worker starts, no run ends, and `consecutive_failures` stays at its value, which matches the observed value 1.

### (b) Whether that text can contain captured worker output from an earlier run
- Established from source: for a dead worker whose exit is not a rate limit, `_classify_dead_worker` appends ` Worker's last output: ` and the `repr` of the captured output to the error text (`hermes_cli/kanban_db_dispatch.py:1047-1062`). The captured output is the last 400 characters of the worker log tail after the dispatcher removes the CLI exit summary, box-drawing characters and some preamble lines (`hermes_cli/kanban_db_dispatch.py:992-1022`). The error text "pid <pid> not alive" is used when the exit status is unknown (`hermes_cli/kanban_db_dispatch.py:1119-1129`).
- Established from source: the crash path passes this error text to `_record_task_failure` (`hermes_cli/kanban_db_dispatch.py:1276-1290`), which stores the first 500 characters in `tasks.last_failure_error` (`hermes_cli/kanban_db_dispatch.py:1378`, `1410-1415`, `1429-1436`). A protocol violation stores the same text directly (`hermes_cli/kanban_db_dispatch.py:1198-1207`).
- Established from source: `block_task` does not change `last_failure_error`; its update sets status, claim fields, worker PID and the block kind fields only (`hermes_cli/kanban_db.py:3346-3368`, `3382-3408`). The text that a crashed run stored therefore stays in the task row after a later run ends with outcome `blocked`.
- Established from source (text search of `hermes_cli/`, `gateway/`, `tools/`, `agent/` and `plugins/` in the installed source for `last_failure_error`): the column is set to NULL only by `assign_task` when the assignee changes (`hermes_cli/kanban_db.py:1625-1644`), by `unblock_task` (`hermes_cli/kanban_db.py:3750-3754`), by `_clear_failure_counter` (`hermes_cli/kanban_db_dispatch.py:1510-1522`), which `reclaim_task` and `complete_task` call (`hermes_cli/kanban_db.py:2670`, `2901`), and by the export and import scrub (`hermes_cli/kanban_transfer.py:70-87`). It is overwritten by `_record_task_failure`, by the dead-worker sweep for a rate limit or a protocol violation (`hermes_cli/kanban_db_dispatch.py:1198-1207`), and by `record_acceptance` (`hermes_cli/kanban_pr_acceptance_store.py:38-47`).
- Not established: the exact text that run 99 stored. The board `anki` and its task logs were not read on this card.

### (c) `specify_triage_task` compared with `unblock_task`
- Established from source: `specify_triage_task` updates only `status` (to `todo`) and, when given and changed, `title`, `body` and `assignee` (`hermes_cli/kanban_db.py:3899-3936`). It does not change `last_failure_error` or `consecutive_failures`. It then calls `recompute_ready`, which moves a task without open parents to `ready` (`hermes_cli/kanban_db.py:3950-3953`). An assignee change through `specify_triage_task` is written directly and does not go through `assign_task`, so it does not clear the column either (`hermes_cli/kanban_db.py:3928-3931`).
- Established from source: `unblock_task` sets `consecutive_failures = 0` and `last_failure_error = NULL` (`hermes_cli/kanban_db.py:3724-3765`, lines 3750-3754). Its comment states that a deliberate unblock is a fresh start for the retry budget (`hermes_cli/kanban_db.py:3745-3749`). This explains why the block and unblock sequence in Workaround released the card.

### (d) Whether a `respawn_guarded` event produces a gateway notification
- Established from source: the gateway notifier reads only the event kinds in `TERMINAL_KINDS` (`gateway/kanban_watchers_notifier.py:47`, `316`), and only those kinds have message formatters (`gateway/kanban_watchers_notifier.py:470-486`). `respawn_guarded` is not among them, so the event produces no notification to a subscribed chat. It is also not in `_WAKE_KINDS` (`gateway/kanban_watchers_notifier.py:50`), so it does not wake the origin session.
- Established from source: the gateway dispatcher loop writes the log warning "kanban dispatcher stuck" when the ready queue was not empty for 6 consecutive passes in which no worker started on any board, at most once every 300 seconds, and names the guard reasons of the last pass (`gateway/kanban_watchers.py:37`, `308-322`; `hermes_cli/kanban_db_dispatch.py:157-183`). This is a gateway log line, not a chat notification, and a worker started on any other board resets the count.
- Not established: whether that log warning was written between 20:21 and 21:17. The gateway log was not read on this card.
- Not established: whether any installed plugin observes `respawn_guarded` through the `on_kanban_dispatch_tick` hook (`hermes_cli/plugins.py:182-189`). The installed plugins were not read on this card.

## Workaround
The orchestrator ran `hermes kanban --board anki block --kind transient t_d9e2b517 ...` and then `hermes kanban --board anki unblock t_d9e2b517`. The unblock sets `last_failure_error = NULL` (see Diagnosis (c)). Run 105 was then claimed and started at 21:18:04. The workaround succeeded.

## Likely area
Hermes Agent Kanban dispatcher and database code: the condition `latest_outcome != "crashed"` and the use of `tasks.last_failure_error` in `check_respawn_guard` (`hermes_cli/kanban_db_dispatch.py:1585-1592`), the guard branch in the dispatch of one row (`hermes_cli/kanban_db_dispatch.py:2073-2086`), and `specify_triage_task` (`hermes_cli/kanban_db.py:3899-3953`).

## Requested
Changes requested from Hermes Agent:
1. Apply the `blocker_auth` check only to an error that describes the failure of the latest ended run. For example, store the failure classification (such as `auth` or `quota`) on the run when the run ends, and let `check_respawn_guard` read that classification from the latest ended run instead of applying the regular expression to free text that can include captured worker output.
2. As long as the regular expression is applied to free text, apply it only to the part of the error text written by Hermes, not to the part after ` Worker's last output: `.
3. Clear `last_failure_error` (and, as `unblock_task` does, reset `consecutive_failures`) when `specify_triage_task` moves a card out of triage, or record the run that wrote `last_failure_error` so that the guard can ignore text from a run that is not the latest ended run.
4. Make the `blocker_auth` hold visible to the owner: either make the guard path block the card with a reason, as the docstrings at `hermes_cli/kanban_db_dispatch.py:140-143` and `1536-1537` describe, or send a gateway notification to the subscribed chat once when a card is first held. Correct the docstrings if the behaviour stays as it is.

## Related
- [Kanban dispatcher records a live worker as crashed and starts a second worker](261023-kanban-live-worker-marked-crashed-duplicate-dispatch.md): according to the specification of this card by harness-orchestrator, the crash record of run 99 that supplied the stored error text came from that defect (harness card `t_87bc9e2f`). This record describes a separate defect in the respawn guard.

## Upstream status
Not checked: network access was not authorized on this card.
