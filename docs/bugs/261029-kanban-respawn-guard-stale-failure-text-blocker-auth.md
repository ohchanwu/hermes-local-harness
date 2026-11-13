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

## Second occurrence (2026-11-14, board `jss-genr`, card `t_1b49542f`): a card in status `review`, held by the stored text of an earlier rate-limited run
Reported: 2026-11-14, by `jss-orchestrator` (board `jss-genr`, card `t_1b49542f`, assignee `jss-reviewer`). Recorded from harness card `t_485c294f`. The filer reports the Hermes Agent version v0.21.5+6751.g9cf7960.

All times are KST (UTC+09:00). Source references in this section are to the installed Hermes Agent at commit `9cf7960f274e`, the same commit as the references above (`git rev-parse HEAD` of the installed source, read on card `t_485c294f`). Only `hermes_cli/kanban_db_dispatch.py` and `hermes_cli/kanban_db.py` were read, as text, without running, importing or changing them. Board `jss-genr`, its database and its task logs were not read on card `t_485c294f`; the observations below are those that the filer reported.

Observed (reported by the filer):
- Runs 3 and 4 of the card ended with outcome `rate_limited`. Run 3 is listed with the time 2026-11-13 21:58 and the error text "pid 81706 exited rate-limited (quota wall) — requeued without counting a failure". Run 4 is listed with the time 22:37, pid 36401 and the same text.
- Run 5 started at 23:08 and ended at 2026-11-14 00:33 with outcome `review_requested`; the worker exited with exit code 0. The worker's `kanban_request_review` moved the card to status `review` with assignee `jss-reviewer` at 00:33:46.
- No review run started. The dispatcher appended `respawn_guarded` events with the payload `{'reason': 'blocker_auth'}` at 00:34:28, 00:35:29, 00:39:32, 00:40:33, 00:41:34, 00:42:34 and 00:43:35.
- In the same period `jss-reviewer` started and finished review runs on two other cards (`t_9ded8f54`, `t_011b6e53`), so the reviewer profile was able to start.
- At 00:44 the task row had `last_failure_error` = "pid 36401 exited rate-limited (quota wall) — requeued without counting a failure" and `consecutive_failures` None.
- Expected: the review run starts on the next dispatcher pass on which the reviewer profile is free.

Diagnosis of the second occurrence. Each statement is marked "Established from source" or "Not established".

(a) Which alternatives of the regular expression match the stored text:
- Established from source: `_RESPAWN_BLOCKER_RE` encloses all alternatives in `\b(` and `)\b` and is compiled with `re.IGNORECASE` (`hermes_cli/kanban_db_dispatch.py:63-71`). A copy of this pattern, evaluated with the Python standard library module `re`, finds exactly one match in the stored text "pid 36401 exited rate-limited (quota wall) — requeued without counting a failure": the word `quota`. The alternative `rate[\s_\-]?limit` does not match "rate-limited", because the character after "limit" is the word character "e", so the closing word boundary does not hold. This corrects the filer's statement that the words "rate-limited" and "quota" match.

(b) Why the rate-limit branch of `check_respawn_guard` did not apply:
- Established from source: `check_respawn_guard` selects the latest ended run of the card, ordered by `ended_at` (`hermes_cli/kanban_db_dispatch.py:1561-1566`). It returns before the regular expression check, with `rate_limit_cooldown` or with no reason, only when that run has outcome `rate_limited` (`hermes_cli/kanban_db_dispatch.py:1572-1583`). The comment at `hermes_cli/kanban_db_dispatch.py:1555-1556` states "LATEST run only: a newer crash/completion supersedes the rate-limit run". The docstring at `hermes_cli/kanban_db_dispatch.py:1533-1536` states that this branch is checked before `blocker_auth` because "the requeue stamps a quota-flavored ``last_failure_error`` that would otherwise park the task forever".
- Established from source: `request_review` ends the open run with outcome `review_requested` through `_end_or_synthesize_run` (`hermes_cli/kanban_db.py:3534-3538`), and `_end_run` sets `ended_at` of that run to the current time (`hermes_cli/kanban_db.py:2042-2056`). After run 5 ended, the latest ended run therefore had outcome `review_requested`, the rate-limit branch did not apply, and, because that outcome is not `crashed`, the guard applied the regular expression to the stored text that names pid 36401 and returned `blocker_auth` (`hermes_cli/kanban_db_dispatch.py:1589-1592`).

(c) Whether the guard applies to a card in status `review`:
- Established from source: each dispatcher pass reads the unclaimed rows in status `review` when review dispatch is enabled (`hermes_cli/kanban_db_dispatch.py:2362`, `2269-2275`) and passes each row that has an assignee to `_dispatch_lane_task` with `lane="review"` (`hermes_cli/kanban_db_dispatch.py:2421-2428`), the same function that handles rows in status `ready` (`hermes_cli/kanban_db_dispatch.py:2400-2415`). `_dispatch_lane_task` calls `check_respawn_guard` before the claim (`hermes_cli/kanban_db_dispatch.py:2073`); when the guard returns a reason, it appends one `respawn_guarded` event with the payload `{"reason": ...}` and skips the row (`hermes_cli/kanban_db_dispatch.py:2074-2086`).
- Established from source: in `check_respawn_guard`, the return for `lane == "review"` comes after the `blocker_auth` check (`hermes_cli/kanban_db_dispatch.py:1596-1597`). For a card in status `review`, the guard skips only the later checks, not `blocker_auth`.

(d) Whether `request_review` changes `last_failure_error`:
- Established from source: `request_review` (`hermes_cli/kanban_db.py:3426-3552`) changes the task row only in `status`, `claim_lock`, `claim_expires`, `worker_pid` and, when a reviewer is named, `assignee` (`hermes_cli/kanban_db.py:3507-3525`). It does not change `last_failure_error` and does not call `_clear_failure_counter`. `_end_run`, which it reaches through `_end_or_synthesize_run`, changes only the run row and `tasks.current_run_id` (`hermes_cli/kanban_db.py:2042-2057`).
- Established from source: `request_review` writes the reviewer as the assignee in its own update (`hermes_cli/kanban_db.py:3507`, `3520`), not through `assign_task`. The change of assignee to the reviewer therefore does not set `last_failure_error` to NULL, unlike a change of assignee through `assign_task` (`hermes_cli/kanban_db.py:1639-1644`).
- Established from source (text search of the two files read): in `hermes_cli/kanban_db.py`, the column is set to NULL only by `assign_task` (line 1643), by `unblock_task` (line 3752) and through `_clear_failure_counter` (`hermes_cli/kanban_db_dispatch.py:1510-1522`), which `reclaim_task` and `complete_task` call (`hermes_cli/kanban_db.py:2670`, `2901`). This agrees with Diagnosis (b) in the section `## Diagnosis` above.

(e) Which code writes the rate-limit text to `tasks.last_failure_error`:
- Established from source: `_classify_dead_worker_exit` builds the text "pid {pid} exited rate-limited (quota wall) — requeued without counting a failure" when the exit status of a dead worker is classified as `rate_limited` (`hermes_cli/kanban_db_dispatch.py:1097-1106`). `_classify_dead_worker` does not append the captured worker output for a rate-limited exit (`hermes_cli/kanban_db_dispatch.py:1057-1061`).
- Established from source: `_reclaim_dead_workers`, which `detect_crashed_workers` calls (`hermes_cli/kanban_db_dispatch.py:1306`), ends the run with outcome `rate_limited` and this error text (`hermes_cli/kanban_db_dispatch.py:1181-1186`, `1041-1044`), and stores the first 500 characters of the text in `tasks.last_failure_error` without changing `consecutive_failures` (`hermes_cli/kanban_db_dispatch.py:1198-1207`). The comment at `hermes_cli/kanban_db_dispatch.py:1199-1203` states that the text is stored so that "a rate-limited requeue must show ``check_respawn_guard`` a quota blocker".
- Established from source: in the two files read, `hermes_cli/kanban_db_dispatch.py:1102` is the only occurrence of the text "exited rate-limited (quota wall)".
- Not established: whether other files of the installed source write the same text. They were not read on card `t_485c294f`.

Workaround tried by the filer:
- The filer ran `hermes kanban --board jss-genr assign t_1b49542f none` and then `hermes kanban --board jss-genr assign t_1b49542f jss-reviewer` at 00:47. Afterwards `last_failure_error` was None, the status was still `review` and the assignee was `jss-reviewer`.
- Established from source: `assign_task` sets `consecutive_failures = 0` and `last_failure_error = NULL` when the assignee changes, and does not change the status (`hermes_cli/kanban_db.py:1639-1646`; see also Diagnosis (b) in the section `## Diagnosis` above). It refuses only a card in status `running` that has a claim (`hermes_cli/kanban_db.py:1634-1638`).
- Not established: whether the review run then started. The filer had not observed it at filing time, and board `jss-genr` is not read on card `t_485c294f`.
- Established from source: the block and unblock workaround of the first occurrence does not change a card in status `review`. `block_task` changes the status only of a card in status `running` or `ready` (its update has the condition `status IN ('running', 'ready')` and returns False when no row matches, `hermes_cli/kanban_db.py:3353-3368`), or classifies a card that is already in status `blocked` (`hermes_cli/kanban_db.py:3321-3335`). `unblock_task` changes only a card in status `blocked` or `scheduled` (`hermes_cli/kanban_db.py:3750-3756`). The workaround of the first occurrence is therefore not suitable for a card in status `review`.
- Not established: whether the command `hermes kanban block` reaches `block_task` for every card. The command-line source was not read on card `t_485c294f`.

Difference from the first occurrence:
- The card was in status `review`, not `ready`.
- The stored text was written by Hermes for a rate-limited exit (Diagnosis (e) of this section) and contains no captured worker output; the matched word `quota` is in the text that Hermes writes. Item 2 of `## Requested` (apply the regular expression only to the part of the error text written by Hermes) would therefore not prevent this occurrence. Item 1 (read a failure classification from the latest ended run) would prevent it, because the latest ended run, run 5, ended with outcome `review_requested`.
- Additional change requested from Hermes Agent: clear `last_failure_error` in `request_review` when a run ends with a review request, as `complete_task` does through `_clear_failure_counter` (`hermes_cli/kanban_db.py:2901`). Diagnosis (d) of this section establishes that `request_review` does not change the column.

Impact:
- The filer reports that the card waited 13 minutes in status `review` without a review run.
- No notification reported the hold: a `respawn_guarded` event produces no gateway notification (Diagnosis (d) in the section `## Diagnosis` above).
- The filer states that the card would have waited until an operator message, and reports a deadline for reviewed work of 2026-11-15 23:00 while the owner was asleep.
- Not checked upstream for this occurrence: network access was not authorized on this card.

## Upstream status
Not checked: network access was not authorized on this card.
