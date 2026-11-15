# Decision: how a card passes from the GLM reviewer to the Opus reviewer

Date: 2026-11-14 (revised 2026-11-15 after review round 1 of the card)

Card `t_bdfbfb88` on board `harness`. Specification: that card and the request file `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/cache/scratch/camp/handoff-copy.md` (35,677 bytes, SHA-256 `2bc8c3dda0d03e42169a8cfe7f39d9e40bfc35d2d96943856cdc42f17b988ac5`), sections "Constraints", "Facts verified" (part "Review mechanics in Hermes"), "Not verified" (part "Part 6") and "Part 6". A parallel card copies the request file to `docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md`.

Hermes source read: `/Users/chanbla11mit/.hermes/hermes-agent` at commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6` (`git -C /Users/chanbla11mit/.hermes/hermes-agent rev-parse HEAD`). A file reference without a leading directory of this repository (`plugins/`, `scripts/`, `spikes/`, `procedures/`) is relative to that Hermes directory. Nothing under that directory was changed.

Observations: `spikes/glm-reviewer-pass/run.py` runs the sequences against a temporary Kanban database with the real Hermes functions, the real Kanban tool handlers and the real `hermes kanban` command handlers. "OBSERVED n" refers to line n of its output in `spikes/glm-reviewer-pass/README.md`. A statement marked "reading only" rests on source reading and was not observed.

Names in this document: "GLM worker" is a board GLM worker profile; "GLM reviewer" is the proposed reviewer profile on model `glm-5.3`, provider `zai` (request file, Part 6 step 1; no such profile exists yet); "Opus reviewer" is the board's present reviewer profile (for example `harness-reviewer`). The script uses the names `harness-worker-glm-1`, `harness-reviewer-glm` and `harness-reviewer`. "implementer" means the `implementer` value of the card's latest `review_requested` event, which Hermes `request_changes` uses to choose the profile that gets the card back. "Hold script" means `scripts/jev-peak-hold` of this repository, which a LaunchAgent (label `com.nous.hermes-jev-peak-hold`) starts every 10 seconds with `--apply` (`procedures/jev-plugin.md` line 344). "Descendant of a worker" means a process that a dispatcher-started worker process started, directly or through other processes.

## Decision

The GLM reviewer ends its review run with one Kanban tool call. The hold script, a process that no Hermes worker starts, then passes the card to the Opus reviewer. No step changes the `implementer` record of the worker's review request, and no step runs `assign` or `unblock` inside the GLM reviewer's worker process or a descendant of it.

1. When it has no findings, the GLM reviewer calls `kanban_block` with a `reason` that starts with `jev-glm-review-pass`. It never calls `kanban_request_review` or `kanban_complete`.
2. In a GLM reviewer session, for that reason only, the `jev` plugin's `tool_execution` middleware calls the tool with `kind` set to `needs_input` (`capability` when the card's present `block_kind` is `needs_input`). The middleware starts no `hermes kanban` command. Hermes ends the run; the card is `blocked`, and the `blocked` event records the reason, `source_status: review` and the run ID of the GLM review run.
3. On every run, the hold script selects each card that is `blocked`, whose newest `blocked` event has that reason and `source_status: review`, whose run belongs to a GLM reviewer of the board, and whose assignee is that GLM reviewer or the board's Opus reviewer.
4. For each selected card, after it reads the card again, the hold script runs `hermes kanban --board <board> assign <task id> <Opus reviewer>` if the card is not yet assigned to the Opus reviewer. If the card is now assigned to the Opus reviewer, it runs `hermes kanban --board <board> unblock <task id>`. Neither command's environment contains `HERMES_KANBAN_TASK`, `HERMES_KANBAN_RUN_ID` or `HERMES_DELEGATED_CHILD_CONTEXT`. Hermes returns the card to `review`, and the dispatcher's next review-lane claim starts the Opus reviewer's review run.

## Requirements

From the request file, Part 6 step 4, and the card:

- R1. After the GLM reviewer has no findings, the card's next run is a review run of the Opus reviewer.
- R2. A change request of either reviewer returns the card to the worker that implemented it, never to a reviewer profile.
- R3. No change under `/Users/chanbla11mit/.hermes/hermes-agent`.
- Constraint of Part 6 step 5: a failure of the plugin must never let a card be marked done without a review run of the Opus reviewer.

Result: the decided way meets R1, R2 and R3 (sections 4 and 7). It keeps the Hermes access rule for descendants of a worker (section 4). It costs a delay of up to about 10 seconds plus the run time of two commands at each pass. The constraint of Part 6 step 5 holds for every failure of a plugin step or a hold script step, including an exception, a failed command and a hold script that does not run. It does not hold when the `jev` plugin is not loaded at all in a GLM reviewer session: Hermes then accepts `kanban_complete` from a GLM review run (OBSERVED 31). No way found in this card closes that case with the plugin alone. Section 7 and "What the plugin cards must implement" name a guard in Hermes configuration that card C3 must establish. The controller presents this case and the other points of "Open points for the owner" to the owner together with this decision.

## 1. Does Hermes accept `kanban_request_review` from a run that was claimed from status `review`?

**Answer**

Yes. A review run is claimed by `claim_review_task`, which sets the card to `running` and writes `source_status: review` on the `claimed` event. Neither `_worker_guard` nor `_goal_gate` reads the card status or the source of the claim:

- `_worker_guard` checks, in this order: the caller is not a `delegate_task` child; a task ID can be resolved; when `HERMES_KANBAN_TASK` is set, the task ID equals it; and for the five run-lifecycle tools (`kanban_complete`, `kanban_block`, `kanban_schedule`, `kanban_request_review`, `kanban_request_changes`) the run ID from `HERMES_KANBAN_RUN_ID` can be resolved.
- `_goal_gate` returns at once unless the card has `goal_mode` set and a judge model is reachable. Then it asks the judge whether the card's goal is met, which does not depend on the review state.
- `kanban_request_review` checks only that a named reviewer is an installed profile, then calls `request_review` with the run ID.
- `request_review` updates the card only when its status is `running` or `ready` and, when given, the run ID matches the current run. A run claimed from `review` has status `running`, so the call is accepted.

Hermes records as `implementer` the profile of the card's current run (`task_runs.profile`), which for a review run is the reviewer profile; here the GLM reviewer. The named reviewer becomes the assignee.

**Evidence**

- `tools/kanban_tools.py` lines 111 to 114 (`_RUN_LIFECYCLE_TOOLS`), 266 to 298 (`_worker_guard`), 486 to 516 (`_goal_gate`), 873 to 916 (`_handle_request_review`).
- `hermes_cli/kanban_db.py` lines 2376 to 2403 (`claim_review_task`, `source_status` at 2398 to 2400), 3498 to 3506 (implementer from the current run), 3513 to 3525 (status condition), 3539 to 3547 (`review_requested` payload).
- OBSERVED 1 (the GLM review run is `running`, claimed with `source_status=review`) and OBSERVED 2 (the tool returns `ok=True`; status `review`, assignee the Opus reviewer, implementer `harness-reviewer-glm`).

**Not established**

- A card with `goal_mode` set and a reachable judge was not observed. By reading, the judge can refuse the call for a reason that does not depend on the review state.

## 2. Candidate a: the GLM reviewer calls `kanban_request_review` with the Opus reviewer

**Answer**

After a change request of the Opus reviewer the card goes to the GLM reviewer profile with status `ready`, because the latest `review_requested` event (written by the GLM reviewer's own request) names the GLM reviewer as implementer. Without a further step, the dispatcher's next ready-lane claim starts the GLM reviewer as an implementation run (a run whose `claimed` event has no `source_status: review`).

To meet R2 the plugin would have to do this in the Opus reviewer's session, after `kanban_request_changes` returned a result without an error:

1. Read the card's `review_requested` events in order and take the `implementer` of the latest one whose implementer is not a reviewer profile of the board (the GLM worker).
2. Run `hermes kanban --board <board> assign <task id> <that worker>`. Hermes `assign_task` refuses a card that is `running` under a claim; if a dispatcher tick has already claimed the card for the GLM reviewer, only `reassign --reclaim` works, and that terminates the GLM reviewer's implementation run.

The step works when it runs (OBSERVED 5: assignee the GLM worker). The `implementer` record stays the GLM reviewer until the worker's next review request (OBSERVED 5), so every reader of that record has to skip it. When the step fails or does not run, the card is `ready` (or `running`) on the GLM reviewer profile, and the next run is an implementation run of the GLM reviewer (OBSERVED 4): R2 is not met in that case. The request file's mitigation (the GLM reviewer's `SOUL.md` tells it to block a card it did not claim from `review`) depends only on the model following its policy text. The present escalation in `handle_request_changes` does not help, because it acts only when the assignee is in `glm_workers` (`plugins/jev/routing.py` line 733).

**Evidence**

- `hermes_cli/kanban_db.py` lines 3597 to 3607 (`request_changes` takes the implementer from the latest `review_requested` event), 3613 to 3624 (assignee set to that implementer), 1625 to 1654 (`assign_task`; refusal while running and claimed at 1634 to 1638), 2341 to 2373 (`claim_task`, no `source_status`).
- OBSERVED 2, 3 (assignee `harness-reviewer-glm`, status `ready`), 4 (the next ready-lane claim is a run of `harness-reviewer-glm` with `source_status=None`), 5.

**Not established**

- How a GLM reviewer model behaves when it is started as an implementation run.

## 3. Candidate b: `hermes kanban reassign <id> <Opus reviewer> --reclaim` started inside the GLM review run

**Answer**

Observed with stand-in processes, not with a real Hermes agent: the command finishes with exit status 0. The order is fixed by `reclaim_task`:

1. It reads the card's status, claim and recorded worker process.
2. It terminates the recorded worker: SIGTERM, then it checks every 0.5 seconds for about 5 seconds, then SIGKILL if the process is still alive.
3. Only then it opens its write transaction: status `review` (from `_retry_status_for_run`, because the run was claimed from `review`), claim fields cleared, the run ended with outcome `reclaimed`, event `reclaimed`. After the transaction it resets the card's failure counter.
4. `reassign_task` then calls `assign_task`, which sets the assignee to the Opus reviewer and writes the event `assigned`.

In the run recorded in the README, with the default SIGTERM action the stand-in run ended 0.4 seconds after the command started and 0.1 seconds before the command finished (OBSERVED 8). When the stand-in ignored SIGTERM it was ended by SIGKILL 6.4 seconds after the command started and 0.1 seconds before the command finished (OBSERVED 11). These times differ slightly between runs. Afterwards: status `review`, assignee the Opus reviewer, implementer the GLM worker; the events are `reclaimed` then `assigned`; the GLM review run has outcome `reclaimed`. A later change request of the Opus reviewer returns the card to the worker (OBSERVED 9 and 12). The stand-in never reached the end of its own code (OBSERVED 8 and 11): the tool call that starts the command never returns to the GLM reviewer.

A real dispatcher-started worker installs a SIGTERM handler that writes the session store, terminates the foreground processes of the terminal tool and calls `os._exit(0)`. By reading, a subprocess started by the plugin with `subprocess.run` is not registered as such a foreground process, so the command would continue after the worker ends.

**Evidence**

- `hermes_cli/kanban_db.py` lines 2638 to 2671 (`reclaim_task`: termination at 2652 to 2653 before the transaction at 2654 to 2668; failure counter reset at 2669 to 2670), 2674 to 2689 (`reassign_task`), 2406 to 2418 (`_retry_status_for_run`).
- `hermes_cli/kanban_db_dispatch.py` lines 424 to 430 (polling), 443 to 501 (`_terminate_reclaimed_worker`), 1468 to 1482 (`_set_worker_pid`, which the script uses to record the stand-in).
- `hermes_cli/kanban.py` lines 607 to 616 (`_cmd_reassign`).
- `hermes_cli/cli_single_query.py` lines 415 to 465 and `tools/environments/base.py` lines 95 to 125 (reading only).
- OBSERVED 7 to 12.

**Not established**

- The behaviour with a real Hermes agent as the GLM review run.
- The interval between the end of the process and the write (0.1 seconds in the recorded run; with SIGKILL the process ends about 5 seconds later than with SIGTERM). By reading, a dispatcher tick in that interval can find the recorded process dead (`detect_crashed_workers`, `hermes_cli/kanban_db_dispatch.py` line 1296; retry status at 1387) and return the card to `review` with the GLM reviewer as assignee and a `crashed` event. `reclaim_task` then finds the card not `running` and returns False, and `reassign_task` still calls `assign_task`, which succeeds on a card in `review`. The end state would be the same, with a `crashed` event and a counted failure in addition. Not observed.

## 4. Other ways that use only Hermes configuration and the plugin's extension points

**Answer**

The plugin can act at three points: the `tool_execution` middleware of `plugins/jev/__init__.py`, which can call the tool with changed arguments (`next_call(new_args)`), return its own result without calling the tool, or act after the tool returned; `hermes kanban` commands that it starts; and the hold script, which launchd starts outside every Hermes process. The `tool_request` middleware of `hermes_cli/middleware.py` can only change arguments, which gives no call that the `tool_execution` middleware cannot make.

The Hermes access rule for descendants of a worker. The Hermes documentation of worker lanes says: "Later children remain fenced even when a script removes the inherited task ID: CLI and tool mutations are rejected, rather than treating that script as an orchestrator." and "Workers may only perform lifecycle handoffs and attach files to their assigned task; `unblock` remains orchestrator-only." It tells integration authors to start processes with `agent.delegation_context.delegated_child_subprocess_env`. The implementation:

- `delegated_child_subprocess_env`, called with an environment that contains `HERMES_KANBAN_TASK`, returns that environment without the `HERMES_KANBAN_*` identity variables and with `HERMES_DELEGATED_CHILD_CONTEXT` set to the Kanban home of the board (OBSERVED 35). The terminal tool's child processes are started with it.
- A `hermes kanban` command whose action is in the denied list (it contains `assign`, `unblock`, `block`, `complete` and `reassign`) is refused when that variable names the board's Kanban home (OBSERVED 35 for `assign`, 36 for `unblock`). The Kanban database functions refuse in the same case with `PermissionError` (OBSERVED 37).
- The dispatcher removes `HERMES_DELEGATED_CHILD_CONTEXT` from the environment of the worker it starts, so the worker process itself has no such variable.
- `hermes kanban unblock` and the tool `kanban_unblock` also refuse when `HERMES_KANBAN_TASK` is set (OBSERVED 16).

A way therefore keeps the rule only when every `assign` and `unblock` is run by a process that is not a dispatcher-started worker and not a descendant of one. The ways considered:

| Way | R1 | R2 | R3 | Result |
| --- | --- | --- | --- | --- |
| W1. Candidate a (section 2) | met | met only while the plugin step after each Opus change request succeeds | met | rejected |
| W2. Candidate b (section 3) | met when the command completes | met | met | rejected; it also runs `reassign` from a descendant of the worker |
| W3. `kanban_block` with a reason that starts with `jev-glm-review-pass`; the plugin in the GLM reviewer session then runs `assign` and `unblock` with `HERMES_KANBAN_TASK` and `HERMES_KANBAN_RUN_ID` removed (the way of the first version of this document) | met | met by the Hermes record alone | met | rejected: it goes around the access rule above |
| W4. The GLM reviewer calls `kanban_request_changes`, then the plugin runs `hermes kanban request-review <id> --reviewer <Opus reviewer>` | not met when a dispatcher tick claims the `ready` card for the worker between the two calls | met | met | rejected |
| W5. `kanban_schedule` by the GLM review run, then `assign`, then `unblock` | not met: `unblock` returns a `scheduled` card to `ready`, not to `review` | (met) | met | rejected |
| W6. `hermes kanban reopen-review` | not met: it moves a `review` card to `ready` on the implementer | (met) | met | rejected |
| W7. A plugin write to the `tasks` or `task_events` table with SQL | (met) | (met) | met, but it is not a Hermes function and bypasses the checks of `kanban_db` | rejected |
| W8. Hermes workflow steps (`workflow_template_id`, `current_step_key`) | not available: unused in this Hermes version | | | rejected |
| W9. Hermes configuration that removes `kanban_complete` or `kanban_request_review` from a profile | no pass mechanism; the `kanban` toolset contains every `kanban_*` tool, so it cannot be split | | | not a way to pass a card |
| W10. `kanban_block` as in W3; the orchestrator, woken by the `blocked` event, runs `assign` and `unblock` | met when the orchestrator acts | met | met | rejected as the regular way; it is the manual recovery |
| W11. `kanban_block` as in W3; the plugin calls the Hermes functions `assign_task` and `unblock_task` in the GLM reviewer's own process (in the middleware, or in the `kanban_task_blocked` lifecycle hook, which runs in the process that blocked the card) | met | met | met | rejected: a worker process that changes its card other than by a lifecycle handoff goes around the same rule |
| W12. `kanban_block` as in W3; the hold script runs `assign` and `unblock` (the decision) | met | met by the Hermes record alone | met | decided |

W12 in detail (OBSERVED 13, 14, 34, 38, 39, 19, 20): `kanban_block` from the GLM review run is accepted (the run is `running`); `block_task` records the reason, `source_status: review` and the run ID on the `blocked` event, and ends the run with outcome `blocked` (OBSERVED 13, 34). The dispatcher's promotion pass `recompute_ready` does not move the card, because the newest of its `blocked` and `unblocked` events is `blocked` (OBSERVED 14). The selection rule of Decision step 3 selects the card (OBSERVED 34). It does not select a card that a GLM worker blocked with the same reason on its own implementation run: that event has `source_status: ready` and a run of the GLM worker (OBSERVED 40). In an environment without `HERMES_KANBAN_TASK`, `HERMES_KANBAN_RUN_ID` and `HERMES_DELEGATED_CHILD_CONTEXT`, `hermes kanban assign` and then `hermes kanban unblock` are accepted, and `unblock_task` returns the card to `review` because the newest lifecycle event carries `source_status: review` (OBSERVED 38). `delegated_child_subprocess_env` leaves such an environment unchanged (OBSERVED 38). The next review-lane claim is a run of the Opus reviewer (OBSERVED 39). Its change request returns the card to the worker (OBSERVED 19); after a new review request it can mark the card done (OBSERVED 20).

Comparison of W3 and W12, the two ways that meet R1 to R3:

- Hermes access rule. W3 works today only because the GLM reviewer's worker process has no `HERMES_DELEGATED_CHILD_CONTEXT` (the dispatcher removes it) and because the plugin would start the commands with a plain `subprocess.run` and the inherited environment, as `plugins/jev/peak_hold.py` line 319 does, instead of the helper that the Hermes documentation names. If a plugin card follows that documentation, or a Hermes update sets the variable for processes that a worker starts, `assign` and `unblock` are refused at every pass (OBSERVED 35, 36). The card then stays `blocked` on the GLM reviewer (or on the Opus reviewer when only `unblock` is refused, OBSERVED 23) until a person or the orchestrator runs the two commands. W12 runs both commands from a process that launchd starts, which has no worker identity and no such variable. The same LaunchAgent already runs `hermes kanban unblock` today, to release cards held for the peak hours.
- R1. Both meet R1: a `blocked` card is not dispatched and not promoted (OBSERVED 14, 23), so no run starts before the Opus reviewer's review run.
- Delay. W3 passes the card within the run time of two commands after the block. In W12 the card waits for the next run of the hold script (`StartInterval` 10, `procedures/jev-plugin.md` line 344; reading only), plus the run time of the two commands (each with the time limit `kanban.command_timeout_seconds`, default 30 seconds, `plugins/jev/peak_hold.py` lines 315 to 320).
- Process end. In W3 the commands run in the GLM reviewer's process after its run ended. `reap_terminal_workers` sends SIGTERM to a worker process whose run ended at least `TERMINAL_WORKER_REAP_GRACE_SECONDS` (120) seconds earlier, so W3 would need a time limit well under 120 seconds for both commands together (for example 30 seconds). If the process ends after `assign` and before `unblock`, the card stays `blocked` on the Opus reviewer (state of OBSERVED 23); if it ends before `assign`, the card stays `blocked` on the GLM reviewer (state of OBSERVED 21). In W12 nothing that the pass needs runs in the GLM reviewer's process after the block, so the end of that process has no effect on the pass.
- Dependence. W12 depends on the LaunchAgent being installed and running. When it is not, every passed card stays `blocked` on the GLM reviewer (state of OBSERVED 21 and 34), which is visible and never `done`. Its installation needs the owner's authorization (`procedures/jev-plugin.md` line 344).

The decision is W12. Its cost is the delay of up to about 10 seconds plus the command time at each pass.

The kind passed in Decision step 2 matters. Hermes keeps `block_kind` and `block_recurrences` after an unblock and counts a block whose kind equals the card's present `block_kind` as a repeat; at 2 repeats (`BLOCK_RECURRENCE_LIMIT`) the card goes to `triage` (OBSERVED 24). A kind that differs from the present `block_kind` starts the count at 1 (OBSERVED 25). Hence the rule in the Decision.

**Evidence**

- `hermes_cli/middleware.py` lines 102 to 132 (`tool_request`), 143 to 214 (`tool_execution`); `plugins/jev/__init__.py` lines 57 to 72.
- Access rule: `website/docs/user-guide/features/kanban-worker-lanes.md` lines 49 to 72 (section "Descendant process scope"; quotations from lines 54 to 55 and 64 to 65; the helper at lines 68 to 70). `agent/delegation_context.py` lines 20 (`DELEGATED_CHILD_ENV_MARKER`), 122 to 138 (`scrub_kanban_env`), 141 to 162 (`kanban_path_is_fenced`), 173 to 184 (`delegated_child_subprocess_env`). `hermes_cli/kanban.py` lines 150 to 153 (refusal of a command from a delegated child), 207 to 214 (denied actions), 222 to 231 (`_is_delegated_child_cli_mutation`), 1019 to 1021 (`_cmd_unblock` refuses when `HERMES_KANBAN_TASK` is set). `hermes_cli/kanban_db.py` lines 138 to 150 (`_assert_not_delegated_child_mutation`). `hermes_cli/kanban_db_dispatch.py` lines 2933 to 2935 (the dispatcher removes the variable for the worker it starts). `tools/environments/local.py` lines 276 to 285 (terminal tool child processes get the helper's environment; reading only). `tools/kanban_tools.py` lines 301 to 308 (`_require_orchestrator_tool`), 1260 to 1264 and 1294 (`kanban_unblock` is an orchestrator tool). OBSERVED 16, 35, 36, 37.
- W3: as in the first version; OBSERVED 13 to 17, 21, 23. Process end: `hermes_cli/kanban_db_dispatch.py` lines 51 (`TERMINAL_WORKER_REAP_GRACE_SECONDS = 120`) and 504 to 531 (`reap_terminal_workers`); reading only.
- W12: `hermes_cli/kanban_db.py` lines 3288 to 3379 (`block_task`, `source_status` at 3336, status condition at 3361, event with the run ID at 3372), 3399 to 3408 (`_route_block`, payload with `reason`, `kind`, `recurrences`, `source_status`; repeat count at 3402 to 3407), 114 (`BLOCK_RECURRENCE_LIMIT = 2`), 2148 to 2173 (`_has_sticky_block`), 2206 to 2265 (`recompute_ready`, skip at 2229), 2188 to 2203 (`_resume_status_from_events`), 3724 to 3765 (`unblock_task`, resume at 3729 to 3744), 1625 to 1654 (`assign_task`; it refuses only a card that is `running` under a claim); `hermes_cli/kanban.py` lines 572 to 577 (`_cmd_assign`); `tools/kanban_tools.py` lines 811 to 849 (`_handle_block`); `plugins/jev/peak_hold.py` lines 305 to 329 (`run_kanban`); `procedures/jev-plugin.md` line 344 (LaunchAgent). OBSERVED 13, 14, 19, 20, 24, 25, 34, 38, 39, 40.
- W4: `hermes_cli/kanban_db.py` lines 3610 to 3624 (`request_changes` lands `ready`), 3498 to 3506 (with no current run, `request_review` takes the assignee as implementer). Reading only.
- W5: `hermes_cli/kanban_db.py` lines 3729 to 3733 (only `blocked` resumes to `review`); OBSERVED 30.
- W6: `hermes_cli/kanban_db.py` lines 3768 to 3799 (`reopen_review_task`).
- W8: `hermes_cli/kanban_db.py` lines 990 to 994 and 1077 to 1078 ("v1 the column is nullable and unused").
- W9: `toolsets.py` lines 163 to 172 (the `kanban` toolset is every `kanban_*` core tool); `model_tools.py` lines 320 to 324 (the `kanban` toolset is added to every dispatcher-started worker) and 339 to 340 (`disabled_toolsets` removes whole toolsets).
- W10: `gateway/kanban_watchers_notifier.py` line 50 (`_WAKE_KINDS` contains `blocked`). Reading only.
- W11: `hermes_cli/kanban_db.py` line 3378 (the `kanban_task_blocked` hook runs after the block in the same process); `hermes_cli/kanban_db.py` lines 138 to 150 (no refusal in a process without the variable). Reading only.

**Not established**

- W4, W10 and W11 were not observed; their rejection rests on reading.
- The observations run the commands in the script's own process with a replaced environment (OBSERVED 35 to 38); no real launchd process, worker process or terminal tool process was started.
- Whether the LaunchAgent is installed and running at present. This card does not read live state.
- Whether another Hermes configuration surface exists that this reading did not find.

## 5. Peak-hours hold window for a card in status `review` whose assignee is a GLM reviewer

**Answer**

Hermes cannot move a card in status `review` to `blocked` or `scheduled` directly: `block_task` accepts only `running` and `ready`, and `schedule_task` accepts only `todo`, `ready`, `running` and `blocked` (OBSERVED 26). `reopen-review` moves the card to `ready` on the implementer, so the assignee changes.

The one Hermes path that holds the card visibly and returns it to `review` with the same assignee: a run claimed from `review`, then `block_task`, then, after the window, `unblock_task`. The `blocked` event carries `source_status: review`, so `unblock_task` sets `review` (the code at `hermes_cli/kanban_db.py` lines 3740 to 3744 that the card names); neither function changes the assignee. While the card is `blocked`, `recompute_ready` does not promote it. Observed: OBSERVED 28 (status `blocked`, `source_status=review`) and OBSERVED 29 (no promotion during the window; after `hermes kanban unblock`, status `review`, assignee `harness-reviewer-glm`). The same with `schedule_task` instead of `block_task` ends in `ready` (OBSERVED 30).

There are two ways to obtain the run claimed from `review`:

1. The hold script (`scripts/jev-peak-hold`, outside any worker session) calls the Hermes function `claim_review_task` and then runs `hermes kanban --board <board> block <id> "jev-peak-hold until <end>" --kind <kind>`. No `hermes kanban` command claims a `review` card (`claim` claims a `ready` card only), so the script has to import `hermes_cli.kanban_db`; `plugins/jev/peak_hold.py` line 15 says today that changes go through `hermes kanban` commands only. Costs: a run record with profile the GLM reviewer and outcome `blocked` that no process ran (OBSERVED 28); a `blocked` event, which the gateway notifier sends as a message and as a wake of the subscribed session, unlike today's `scheduled` hold, which sends neither (`plugins/jev/peak_hold.py` lines 7 to 9); and the kind rule of section 4. `claim_review_task` and the dispatcher's review-lane claim are both compare-and-set updates on status `review` with no claim; if the dispatcher claims first, a GLM review run starts inside the window.
2. The GLM review run that the dispatcher started blocks its own card through the plugin at its first tool call. This needs no new import, but it costs at least one GLM model call inside the window. Hermes has the plugin hooks `on_session_start` and `pre_llm_call`; whether one of them can end the run before the first model call is not established.

What the present code does with a GLM worker run that is already running when the window starts: nothing. `holdable_cards` selects only cards in status `ready` or `todo` (OBSERVED 27: a card with a running GLM worker run is not selected, and neither is a card in `review`); `handle_create` and `handle_unblock` act only when a card is created and when `kanban_unblock` is called; no plugin path reclaims or signals a running run. The run continues to its end, and a review request it makes is not held. A GLM review run that is already running when the window starts, handled the same way, continues to its end.

**Evidence**

- `hermes_cli/kanban_db.py` lines 3361 (`block_task` status condition), 4047 (`schedule_task` status condition), 3768 to 3799 (`reopen_review_task`), 2376 to 2403 (`claim_review_task`), 2294 to 2314 (`_claim_and_open_run`, compare-and-set), 3724 to 3765 (`unblock_task`), 2229 (`recompute_ready` skips a `blocked` card whose newest block event is `blocked`).
- `hermes_cli/kanban.py` lines 734 to 746 (`_cmd_claim` uses `claim_task`, `ready` only).
- `gateway/kanban_watchers_notifier.py` lines 47 (`TERMINAL_KINDS`, events sent as messages) and 50 (`_WAKE_KINDS`, events that wake the subscribed session; `blocked` is in both, `scheduled` in neither). Reading only.
- `hermes_cli/plugins.py` lines 109 to 132 (`VALID_HOOKS`). Reading only.
- `plugins/jev/peak_hold.py` lines 237 to 246 (`holdable_cards`); `plugins/jev/routing.py` lines 27 to 38.
- OBSERVED 26 to 30.

**Not established**

- Whether the owner accepts one message and one wake for every held review card.
- Whether an import of `hermes_cli.kanban_db` by the hold script is acceptable under the Constraints of the request file. This is a question for card C3, not for this decision.
- Whether a plugin hook can end a GLM review run before its first model call.

## 6. Does anything in Hermes prevent a profile on provider `zai` from running a review run?

**Answer**

Reading only: no source line was found that makes the review lane depend on the provider or the model. A review-lane dispatch differs from a ready-lane dispatch in two points only: the claim (`claim_review_task` instead of `claim_task`) and the skill `sdlc-review`, which is added to the run's skills. Both lanes use the same spawn function and command: `hermes -p <assignee> --cli --accept-hooks`, one `--skills <name>` per skill, `-m <model>` and `--provider <provider>` only when the card has a model override, `--reasoning <level>` only when the card has a reasoning effort, `--toolsets <the assignee profile's effective CLI toolsets>`, then `chat -q "work kanban task <id>"`.

- Toolsets: from the assignee profile's configuration (`platform_toolsets.cli`). The `kanban` toolset is added to every dispatcher-started worker. The `kanban_*` tools are core tools, which are never deferred behind tool search. Hermes has no toolset named `review`; in this repository `"toolsets": "review"` in `roster.yaml` is a label, and `scripts/verify-state` lines 2423 to 2427 require each board reviewer's `platform_toolsets.cli` to equal the worker tool list.
- Instructions: the Kanban guidance that every worker's system prompt has, the skill `sdlc-review`, and the profile's own policy files. A run whose requested skills are all missing stops at start with an error, so a GLM reviewer profile must have `sdlc-review` installed.
- Model: the profile's own model unless the card has a model override. The plugin clears the override in a GLM worker session before the review request (`plugins/jev/routing.py` lines 569 to 599), so the GLM reviewer runs on its own profile model.

GLM worker sessions already call `kanban_request_review` (the plugin's `handle_request_review` exists for that call), which shows by reading that the Kanban tools reach `zai` sessions.

**Evidence**

- `hermes_cli/kanban_db_dispatch.py` lines 2025 to 2149 (`_dispatch_lane_task`; claim at 2098, `sdlc-review` at 2119 to 2122), 2687 to 2712 (`_resolve_worker_cli_toolsets`), 2743 to 2777 (`_worker_argv`).
- `model_tools.py` lines 320 to 324 and 530 to 531; `toolsets.py` lines 12 to 32 and 163 to 172; `agent/prompt_builder.py` line 267 (`KANBAN_GUIDANCE`); `cli.py` lines 1046 to 1052 (missing skills).
- Source reading only; no model call.

**Not established**

- How well `glm-5.3` follows the reviewer policy text and the `sdlc-review` skill. No data exists.

## 7. The decided way: R1, R2, R3 and the constraint of Part 6 step 5

The steps of the decided way, as numbered in the Decision: step 1 is the GLM reviewer's own call; step 2 is the `kanban_block` call through the middleware (P2); step 3 is the selection by the hold script (H3); step 4 is the hold script's `assign` (H4a) and `unblock` (H4b).

**Answer**

Successful sequence:

1. The worker's run requests review by the GLM reviewer. Hermes writes `review_requested` with implementer the GLM worker (OBSERVED 1).
2. The GLM review run calls `kanban_request_changes` when it has findings: the card goes to the GLM worker (OBSERVED 6). R2 holds for the GLM reviewer.
3. When it has no findings, P2: the card is `blocked` on the GLM reviewer, `source_status: review`, run outcome `blocked`; no run can start, because a `blocked` card is not dispatched and is not promoted (OBSERVED 13, 14, 34). The GLM reviewer's process runs no further step of the pass.
4. H3: the hold script selects the card (OBSERVED 34).
5. H4a and H4b, from the LaunchAgent process: status `review`, assignee the Opus reviewer, implementer still the GLM worker (OBSERVED 38). The next run is the Opus reviewer's review run (OBSERVED 39). R1 holds.
6. The Opus reviewer's change request returns the card to the GLM worker (OBSERVED 19). R2 holds for the Opus reviewer, without any plugin step, because no step changed the implementer record. The Opus reviewer's approval marks the card done (OBSERVED 20).

The access rule of section 4 holds: the GLM reviewer's process makes only its own lifecycle handoff (`kanban_block`); `assign` and `unblock` run in a process that launchd starts, which is neither a dispatcher-started worker nor a descendant of one. If a plugin card, contrary to this decision, ran H4a or H4b in the GLM reviewer session, both commands would be refused once the session's child processes carry `HERMES_DELEGATED_CHILD_CONTEXT` (OBSERVED 35, 36, 37), and the card would stay in one of the states below. It would not be `done`.

Each failure:

- The plugin is not loaded, is turned off, or cannot read `config.json` in the GLM reviewer session: Hermes runs the GLM reviewer's `kanban_block` unchanged. The card is `blocked` on the GLM reviewer, visible, and not dispatched (state of OBSERVED 21). When the model's reason starts with `jev-glm-review-pass`, the hold script still selects and passes the card, because the selection does not depend on the kind. If the model's kind equals the card's present `block_kind`, the card goes to `triage` instead (OBSERVED 24); the hold script does not select a `triage` card, and the card is visible and not dispatched.
- The middleware raises before it calls the tool: Hermes calls the tool anyway (`hermes_cli/middleware.py` lines 204 to 212; OBSERVED 32 shows this for `kanban_complete`). Same state as the previous case.
- P2 returns a tool error (for example a run ID that is no longer current): Hermes changed nothing; the plugin returns the error. The card stays as Hermes had it.
- The GLM reviewer's process ends after P2 (for example by `reap_terminal_workers` 120 seconds after the run ended, or by a crash): no effect on the pass, which does not need that process.
- The LaunchAgent is not installed or does not run, the hold script cannot read the board, or H3 has an error: the card stays `blocked` on the GLM reviewer (state of OBSERVED 34). A person or the orchestrator can pass it by hand with the same two commands (state of OBSERVED 38). An unblock without an assignment returns it to `review` on the GLM reviewer (OBSERVED 22), which gives a second GLM review run, not a done card.
- H4a fails (command not found, time limit, non-zero exit status): the card stays `blocked` on the GLM reviewer (OBSERVED 21). The next run of the hold script selects it again.
- H4b fails: the card stays `blocked` on the Opus reviewer and is not promoted (OBSERVED 23). The next run of the hold script selects it again (the selection allows the Opus reviewer as assignee) and runs only `unblock`.
- The hold script is started with `HERMES_KANBAN_TASK`, `HERMES_KANBAN_RUN_ID` or `HERMES_DELEGATED_CHILD_CONTEXT` in its environment (for example from a worker session): it runs no pass command. Hermes would refuse the commands in that case anyway (OBSERVED 16, 35, 36). The card stays `blocked`.
- The card changes between H3 and H4a. When a person or the orchestrator has already unblocked it, the hold script's second read finds it not `blocked` and skips it. When the dispatcher has also claimed it for a GLM review run, `assign_task` refuses a card that is `running` under a claim (`hermes_cli/kanban_db.py` lines 1634 to 1638) and the card continues with a second GLM review run (reading only).
- A GLM worker blocks its own implementation run with the reason `jev-glm-review-pass`: the hold script does not select the card (OBSERVED 40). The card stays `blocked` on the GLM worker.
- The decisions record of the middleware or of the hold script fails to write: no effect on the card.

R3: every step is an existing Kanban tool, an existing `hermes kanban` command, the existing plugin middleware or the existing hold script and its LaunchAgent. Nothing under `/Users/chanbla11mit/.hermes/hermes-agent` changes.

Constraint of Part 6 step 5: no step of the decided way calls `kanban_complete` or `hermes kanban complete`, and no failure state above is `done` (OBSERVED 13, 21, 22, 23, 24, 34, 35, 36, 37, 40). The remaining way to `done` is a `kanban_complete` call by the run that holds the card. For an Opus review run that is the intended approval. For a GLM review run Hermes accepts the call (OBSERVED 31), so it must be refused:

- by the plugin's middleware for `kanban_complete` in a GLM reviewer session, which returns an error without calling the tool. This works (OBSERVED 33). The refusal must not raise, because a middleware that raises before `next_call` lets Hermes run the tool (OBSERVED 32), and it must not depend on `config.json`, because `load_config` returns an empty configuration when the file cannot be read (`plugins/jev/__init__.py` lines 33 to 39);
- and, for the case that the plugin is not loaded (a plugin load failure is only logged, `hermes_cli/plugins_loader.py` line 513), by a second guard that does not depend on the plugin. By reading, Hermes configuration offers one: a `pre_tool_call` shell hook with a `matcher` for the tool name; exit status 2 blocks the call, and with `fail_closed` a failing hook also blocks it (`agent/shell_hooks.py` lines 5 and 133 to 135). This guard was not observed.

**Evidence**

OBSERVED 1, 6, 13 to 24, 31 to 40; the source lines named in each item and in section 4.

**Not established**

- The shell hook guard is now observed in a temporary Hermes home with the `jev` plugin absent: registration with `--accept-hooks` and the allowlist record (OBSERVED 41, 42, 43, 51), blocking of `kanban_complete` and `kanban_request_review` by exit status 2 through the Hermes tool call path with no other tool blocked (OBSERVED 44 to 48), `fail_closed` blocking with a missing script (OBSERVED 49, 50), and the case that an exception inside `_dispatch_pre_tool_call_hooks` lets the call proceed past the guard, so the guard does not protect in that case (OBSERVED 52, `model_tools.py` lines 781 to 789). Not observed: a run of a real dispatcher-started worker process, which needs a model call, and that the guard gives no protection in this case in such a run.
- No real Hermes agent, dispatcher, launchd process or gateway ran; the failure states were produced by calling the functions in the observed order, and the commands of OBSERVED 35 to 38 ran in the script's own process with a replaced environment.
- The race between H3 and H4a was not observed.

## Rejected ways

- **Candidate a (W1).** The GLM reviewer's own review request makes it the recorded implementer (OBSERVED 2). R2 then depends on a plugin step after every change request of the Opus reviewer; when that step fails, the next run is an implementation run of the GLM reviewer (OBSERVED 4).
- **Candidate b (W2).** It meets R1 to R3 when the command completes (OBSERVED 8, 9, 11, 12), but: it runs `reassign`, a command that the Hermes access rule denies to descendants of a worker (section 4); it ends the GLM review run by a signal, so the tool call never returns; it records the run as `reclaimed` with the error text of an operator reclaim and resets the card's failure counter at every pass (`hermes_cli/kanban_db.py` lines 2664 to 2670); and its result depends on timing: between the end of the process and the database write (0.1 seconds in the recorded run, after up to about 6 seconds of waiting for the process to end) a dispatcher tick can record a crash (reading only), and if the command itself ends in that interval the card stays `running` until the crash path returns it to the GLM reviewer, so the next run is a second GLM review run, not an Opus review run.
- **W3 (`assign` and `unblock` from the GLM reviewer session, the way of the first version of this document).** The Hermes documentation says that descendants of a worker remain fenced even when a script removes the inherited task ID, and that `unblock` remains orchestrator-only (`website/docs/user-guide/features/kanban-worker-lanes.md` lines 54 to 55 and 64 to 65). W3 is not refused today only because the worker process has no `HERMES_DELEGATED_CHILD_CONTEXT` and the plugin would not use `delegated_child_subprocess_env`. With that variable both commands are refused (OBSERVED 35, 36), and every passed card stays `blocked` until a person or the orchestrator acts. W3 also needs both commands to finish within the 120 seconds before `reap_terminal_workers` ends the worker process (section 4). Its only advantage over W12 is a shorter delay.
- **W4.** A dispatcher tick between the change request and the new review request starts the worker on a card that had no findings, and the change request is recorded with the GLM reviewer as reviewer, so it counts as a GLM return under Part 6 step 2 (reading only).
- **W5 and W6.** They do not return the card to `review` on the Opus reviewer (OBSERVED 30; `hermes_cli/kanban_db.py` lines 3768 to 3799).
- **W7.** It writes Hermes tables without the Hermes functions and their checks. The same applies to the reason given for W11.
- **W8 and W9.** Not available in this Hermes version, or not a way to pass a card (section 4).
- **W10 (the orchestrator passes the card).** It keeps the access rule, but each pass costs one orchestrator model turn, its delay is the time until the orchestrator acts, and it depends on the model following its skill text. It remains the manual recovery for a card that stays `blocked` with the pass reason.
- **W11 (Hermes functions called in the GLM reviewer's own process).** A worker process that changes its card other than by a lifecycle handoff goes around the same rule as W3. In addition, the plugin would import Hermes internals into the worker process.

## What the plugin cards must implement

Hermes calls, in this order. "State on failure" is the card's state when the step fails and no later step runs.

1. Card C3, middleware for `kanban_complete` in a GLM reviewer session: return an error result in the format of the Hermes tools (`{"error": ...}`) without calling `next_call`. Identify a GLM reviewer session without reading `config.json` (for example by a fixed profile name pattern, with `config.json` only adding names), and catch every exception inside the handler so that the error result is still returned. State on failure: if the handler raises before `next_call`, Hermes marks the card done (OBSERVED 32).
2. Card C3, middleware for `kanban_request_review` in a GLM reviewer session: the same refusal, so that the state of candidate a cannot arise. State on failure: status `review` on the Opus reviewer with the GLM reviewer as implementer (OBSERVED 2).
3. Card C3, a `pre_tool_call` shell hook with `fail_closed` in each GLM reviewer profile configuration for `kanban_complete` and `kanban_request_review`, after card C3 has observed that it registers and blocks in a dispatcher-started worker. State on failure: as in items 1 and 2 when the plugin is also absent.
4. Card C3 or C4, middleware for `kanban_block` in a GLM reviewer session whose `reason` starts with `jev-glm-review-pass` (any other `kanban_block` call passes through unchanged):
   1. Read the card with a read-only connection (`peak_hold.connect_readonly`): `block_kind`. State on failure: call `next_call(args)` unchanged; the card is `blocked` on the GLM reviewer, or `triage` when the model's kind equals the card's `block_kind`.
   2. `next_call(args)` with `kind` set to `needs_input`, or `capability` when `block_kind` is `needs_input`. State on failure (tool error): unchanged, the GLM review run continues and receives the error.
   3. One `decisions` record (identifiers, applied flag and error class only, no card text).
   4. Return the tool result of step 2 with a note that the hold script passes the card to the Opus reviewer, so that the GLM reviewer ends its run.
   The middleware starts no `hermes kanban` command and calls no Hermes function other than through `next_call`.
5. Card C3 or C4, a pass part in `scripts/jev-peak-hold`, run on every `--apply` run of the LaunchAgent, independent of `peak_hold.enabled` and of the on/off switch of the hold:
   1. If `HERMES_KANBAN_TASK`, `HERMES_KANBAN_RUN_ID` or `HERMES_DELEGATED_CHILD_CONTEXT` is set in the script's environment, print that the pass is refused for a process that a worker started, and run no pass command. State: the cards stay `blocked`.
   2. For each board, with `peak_hold.connect_readonly`, select every card that is `blocked`, whose newest `blocked` event has a `reason` that starts with `jev-glm-review-pass` and `source_status` `review`, whose `blocked` event's run (`task_events.run_id`, then `task_runs.profile`) belongs to a GLM reviewer of that board in `config.json`, and whose assignee is that GLM reviewer or the board's Opus reviewer. State on failure (read error): the cards stay `blocked`; the existing `read_error` record is written; the next run tries again.
   3. Read the card again just before the commands, as `still_holdable` does for holds; skip it when it no longer meets item 5.2.
   4. When the assignee is not yet the Opus reviewer: `run_kanban(config, board, ["assign", <task id>, <Opus reviewer>])`, that is `hermes kanban --board <board> assign <task id> <Opus reviewer>`. State on failure: `blocked` on the GLM reviewer (OBSERVED 21); the next run tries again.
   5. Only after item 5.4 succeeded or was not needed: `run_kanban(config, board, ["unblock", <task id>])`. State on failure: `blocked` on the Opus reviewer (OBSERVED 23); the next run runs only this command.
   6. One `decisions` record per card (identifiers, applied flags and error classes only, no card text).
   The commands are started with the environment of the LaunchAgent process, which contains none of the three variables of item 5.1. `delegated_child_subprocess_env` is not needed: it returns that environment unchanged (OBSERVED 38). The pass commands must never be started from a GLM reviewer session or another worker session, nor from a process that one of them started. Each command keeps the time limit `kanban.command_timeout_seconds` of `run_kanban`.
6. Card C3, the peak-hours hold of `review` cards on a GLM reviewer: one of the two ways of section 5, with the kind rule of item 4.2. The release is `hermes kanban --board <board> unblock <task id>` from the hold script. State on failure of the hold: the card stays `review` and the dispatcher may start the GLM review run inside the window. State on failure of the release: the card stays `blocked`, visible.
7. Card C4, `handle_request_changes`: count only `changes_requested` events whose `reviewer` is not a GLM reviewer (request file, Part 6 step 3). A pass writes no `changes_requested` event, so it is not counted as a GLM return.
8. Card C3, the reviewer choice of Part 6 step 2: always pass `reviewer` explicitly. When a review request names no reviewer after a change request, Hermes uses the reviewer of the latest `changes_requested` event (`_prior_reviewer`, `hermes_cli/kanban_db.py` lines 3555 to 3568), which after a GLM change request is the GLM reviewer.
9. Card C5, the report: identify a pass by a `blocked` event whose `reason` starts with `jev-glm-review-pass`; a GLM review run of a pass has outcome `blocked`.
10. Card C1, the verifier: each GLM reviewer profile has the `jev` plugin installed and enabled and the skill `sdlc-review` installed, and the LaunchAgent `com.nous.hermes-jev-peak-hold` is loaded.
11. Card C2, policy text: the GLM reviewer's `SOUL.md` states item 4's call for no findings and `kanban_request_changes` for findings, and forbids `kanban_complete` and `kanban_request_review`. The orchestrator skills state that a `blocked` event whose reason starts with `jev-glm-review-pass` needs no action while the hold script runs, and that a card still `blocked` with that reason at the orchestrator's next check is passed by hand with the two commands of item 5. The Opus reviewer `SOUL.md` files state that an earlier GLM review run with outcome `blocked` and that reason is not a mismatch.

## Open points for the owner

Approval of this card makes the proposal the decision. The controller presents these points to the owner with it:

1. The constraint of Part 6 step 5 is not met if the `jev` plugin is not loaded in a GLM reviewer session (OBSERVED 31). The second guard (a `pre_tool_call` shell hook with `fail_closed`) is now observed in a temporary Hermes home with the `jev` plugin absent (OBSERVED 41 to 50: registration with `--accept-hooks`, blocking by exit status 2 of `kanban_complete` and `kanban_request_review`, and `fail_closed` blocking with a missing script). It is established that the call proceeds past the guard when `_dispatch_pre_tool_call_hooks` raises, so the guard does not protect in that case (OBSERVED 52), which card C3 or a later card must close another way. Not established: a run of a real dispatcher-started worker process, which needs a model call, and that the guard gives no protection in this case in such a run.
2. Hermes documents that `unblock` is orchestrator-only and that descendants of a worker stay fenced even when a script removes the task ID (`website/docs/user-guide/features/kanban-worker-lanes.md` lines 54 to 55 and 64 to 65). The first version of this decision ran `assign` and `unblock` from the GLM reviewer session with the task ID removed, which works today only because the worker process has no `HERMES_DELEGATED_CHILD_CONTEXT`. This version moves both commands to the hold script's LaunchAgent run. The costs: a delay of up to about 10 seconds plus the command time at each pass; and the pass depends on the LaunchAgent, whose installation needs the owner's authorization. While it does not run, every passed card stays `blocked` on the GLM reviewer until a person or the orchestrator runs the two commands.
3. Each pass writes one `blocked` event (a message and a wake of the subscribed session) and one `unblocked` event (a message).
4. The peak-hours hold of `review` cards (section 5) needs either the Hermes function `claim_review_task` imported by the hold script (no `hermes kanban` command claims a `review` card) or one GLM model call inside the window.

## Not established

- No real Hermes agent, dispatcher, launchd process, gateway notifier or model ran. The observations call the Hermes functions, tool handlers and command handlers directly in a temporary Kanban database; the reviewer runs are claims without a model; in section 3 the run process is a Python stand-in; the commands of OBSERVED 35 to 38 ran in the script's own process with a replaced environment.
- The behaviour of a real GLM review run that receives SIGTERM while a plugin command runs (candidate b), and the race with `detect_crashed_workers`.
- The `pre_tool_call` shell hook guard of section 7.
- Whether the LaunchAgent `com.nous.hermes-jev-peak-hold` is installed and running at present, and its real interval between runs. This card does not read live state.
- Whether a later Hermes version restricts `assign` or `unblock` further for processes that are not workers (for example to named orchestrator profiles). Such a change would also stop the present release of held cards by the same LaunchAgent.
- A card with `goal_mode` set. By reading, `_handle_block` accepts only the kinds `dependency` and `needs_input` for such a card (`tools/kanban_tools.py` lines 831 to 836), so for a `goal_mode` card whose `block_kind` is already `needs_input` the kind rule of item 4.2 cannot avoid `triage` through the tool.
- How many messages and wakes the subscribed sessions receive per pass. By reading, the pass writes one `blocked` event (message and wake) and one `unblocked` event (message only); candidate a would write one `review_requested` event (message and wake); candidate b writes neither.
- How well a `glm-5.3` reviewer follows its policy text; how many findings it has. No data exists.

## Observations of the second guard (2026-11-16, card t_85d4fbda)

Card `t_85d4fbda` on board `harness`. The observation program is `tests/observe_glm_reviewer_hook.py` of this repository, run with `/Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I` from the worktree root. It creates a temporary directory, sets `HERMES_HOME` to `<temporary directory>/home` before it imports any Hermes module, removes every `HERMES_KANBAN_*`, `HERMES_PROFILE`, `HERMES_ACCEPT_HOOKS` and `HERMES_SESSION_*` variable from its environment, writes a `config.yaml` there with the hook of the script `scripts/jev-glm-reviewer-hook` (matcher `kanban_complete|kanban_request_review`, `timeout` 10, `fail_closed` true) and no plugins, and deletes the temporary directory at the end. "OBSERVED n" below refers to its printed lines: OBSERVED 41 is the printed line `a1`, 42 `a2`, 43 `a3`, 44 `b0`, 45 `b1`, 46 `b2`, 47 `b3`, 48 `b4`, 49 `c1`, 50 `c2`, 51 `d1` and 52 `e1`. The `jev` plugin is absent because user plugins load only from `get_hermes_home()/"plugins"` (`hermes_cli/plugins_discovery.py` line 209) and the temporary home has no such directory; the loaded list of OBSERVED 44 is the bundled set only. Hermes source: `/Users/chanbla11mit/.hermes/hermes-agent` at commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6`.

- OBSERVED 41 (registration): `register_from_config(cfg, accept_hooks=True)` returns one `pre_tool_call` spec with matcher `kanban_complete|kanban_request_review` and `fail_closed` true (`agent/shell_hooks.py` `ShellHookSpec` lines 127 to 136, register path lines 141 to 176). The temporary `shell-hooks-allowlist.json` holds one approval for the `(event, command)` pair (OBSERVED 42; `_prompt_and_record` lines 572 to 592 records it because `accept_hooks` is true, `_record_approval` lines 595 to 598, `save_allowlist` lines 535 to 543; the path is `allowlist_path()` lines 517 to 519).
- OBSERVED 43 (no registration without consent): with `accept_hooks=False`, stdin not a TTY and no `hooks_auto_accept`, `register_from_config` registers nothing and writes no approval (`_resolve_effective_accept` lines 622 to 627; `_prompt_and_record` line 578 `sys.stdin.isatty()` is false, so the answer is no without a prompt).
- OBSERVED 44 (plugin absence): the plugin manager of the temporary home loads only bundled plugins; no `jev` plugin is loaded in the process.
- OBSERVED 45 (blocking of `kanban_complete`): through `model_tools.handle_function_call` (`model_tools.py` lines 876 to 947, which calls `_pre_dispatch_guards` at line 944), the hook script runs, exits with status 2 (`BLOCK_EXIT_CODE`, `agent/shell_hooks.py` line 42; `_evaluate_result` lines 417 to 423 takes the message from stderr), and the tool result is `{"error": "<the script's message>"}`; the tool handler is not run. `_pre_dispatch_guards` lines 779 to 791 returns it as a `tool_error` with error type `plugin_block`.
- OBSERVED 46 (blocking of `kanban_request_review`): the same call with `kanban_request_review` is blocked the same way; the matcher accepts it (`matches_tool` lines 117 to 124, `re.fullmatch` of `kanban_complete|kanban_request_review`).
- OBSERVED 47 (`kanban_block` not blocked): `kanban_block` passes the hook (the callback returns `None` for a tool name the matcher refuses; `_make_callback` lines 368 to 377) and reaches its handler, which returns a tool error because no `HERMES_KANBAN_TASK` is set (`tools/kanban_tools.py` `_require_task_id` lines 209 to 228). No board is reached.
- OBSERVED 48 (`read_file` not blocked): `read_file` passes the hook and reads the temporary `config.yaml` (result keys `content`, `file_size`, `total_lines`).
- OBSERVED 49 (`fail_closed` with a missing script): with `fail_closed` true and a command path that does not exist, `kanban_complete` is blocked with `hook <path> failed closed: command not found` (`_spawn` lines 313 to 365 reports the spawn error; `_evaluate_result` lines 406 to 413 returns the block of `_fail_closed_block` lines 380 to 381).
- OBSERVED 50 (fail open without `fail_closed`): the same missing command with `fail_closed` false does not block; the hook returns `None` (`_evaluate_result` lines 406 to 413) and the `kanban_complete` handler answers with its own refusal (no `HERMES_KANBAN_TASK`), so no board is reached.
- OBSERVED 51 (dispatcher flag): `_worker_argv` of `hermes_cli/kanban_db_dispatch.py` (lines 2743 to 2777; the flag at line 2754) contains `--accept-hooks` for a stand-in task object, and `hermes_cli/main.py` `_prepare_agent_startup` (lines 3012 to 3028, registration at 3088 to 3093) passes it to `register_from_config(load_config(), accept_hooks=_accept_hooks)`.
- OBSERVED 52 (remaining failure case, observed with `mock.patch` of `_dispatch_pre_tool_call_hooks`): an exception inside `_dispatch_pre_tool_call_hooks` (`hermes_cli/plugins.py` lines 2150 to 2158) does not block. `_pre_dispatch_guards` (`model_tools.py` lines 781 to 789) catches every `Exception`, logs it at debug level only, and leaves the block message `None`, so the tool handler runs. In the observation the handler refuses because no `HERMES_KANBAN_TASK` is set; in a real GLM review run the environment of the dispatcher names the task, so the call would proceed to the board. This is a failure case of the second guard that this card reports and does not work around. (The hook callback path has its own rule that a failure blocks: a `pre_tool_call` callback that raises or times out inside the delivery manager is turned into a block directive, `hermes_cli/plugins_dispatch.py` lines 226 to 242 with `_HOOK_TIMEOUT_FAIL_CLOSED_HOOKS` at line 49; the observed exception is raised above that, at the `model_tools.py` call site.)

Not established by these observations: a run of a real dispatcher-started worker process with the hook configured, which needs a model call.
