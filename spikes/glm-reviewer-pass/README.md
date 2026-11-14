# Observation script: passing a card from the GLM reviewer to the Opus reviewer

Card `t_bdfbfb88` on board `harness`. The decision that uses these observations is `docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md`.

## What the script does

`run.py` creates a new temporary directory, points Hermes at a Kanban database inside it, and runs the sequences of questions 1 to 5 and 7 of the decision document with the real Hermes code. Observations 34 to 40 (added after review round 1) concern the Hermes access rule for processes that a worker starts, and the decided way, in which the hold script `scripts/jev-peak-hold` runs `assign` and `unblock`. The script uses:

- the Kanban functions of `hermes_cli/kanban_db.py` (`create_task`, `claim_task`, `claim_review_task`, `request_review`, `request_changes`, `block_task`, `schedule_task`, `unblock_task`, `recompute_ready`) and `_set_worker_pid` of `hermes_cli/kanban_db_dispatch.py`;
- the Kanban tool handlers of `tools/kanban_tools.py` (`kanban_request_review`, `kanban_request_changes`, `kanban_block`, `kanban_complete`), called with `HERMES_KANBAN_TASK` and `HERMES_KANBAN_RUN_ID` set as the dispatcher sets them for a run;
- the `hermes kanban` command handlers (`hermes_cli.kanban.kanban_command` with the parser of `hermes_cli/kanban_parser.py`, the function that `hermes kanban <action>` calls) for `assign`, `unblock` and `reassign --reclaim`;
- the `tool_execution` middleware chain of `hermes_cli/middleware.py`, with two test middlewares registered in memory;
- `holdable_cards` of `plugins/jev/peak_hold.py` from this repository;
- `delegated_child_subprocess_env` and `DELEGATED_CHILD_ENV_MARKER` of `agent/delegation_context.py`. It computes the environment that this helper gives a child process of a GLM reviewer session (observations 35 to 37). It also computes an environment with no `HERMES_KANBAN_TASK`, `HERMES_KANBAN_RUN_ID` or `HERMES_DELEGATED_CHILD_CONTEXT`, which is the environment of a process that launchd starts (observation 38). For each command it replaces the script's own process environment with that environment and restores it afterwards. No separate process is started for these observations.

Observations 34 and 40 apply the selection rule that the decision gives the hold script (function `pass_selected`, read-only): the card is `blocked`, the newest `blocked` event has a reason that starts with `jev-glm-review-pass` and `source_status` `review`, and the run of that event is a run of the GLM reviewer.

A reviewer run is a claim without a model. For candidate b the run process is a Python child process (a stand-in) that the script starts and records as the card's worker with `_set_worker_pid`; the stand-in starts the `hermes kanban reassign <id> <Opus reviewer> --reclaim` handler as its own child process and waits for it, as a plugin step inside the run would. One variant keeps the default SIGTERM action, the other ignores SIGTERM.

Each observation is one line: `OBSERVED <number> <what was done>: <status>, <assignee>, <implementer>, <other fact>`. `implementer` is the `implementer` value of the card's latest `review_requested` event.

The profile names in the temporary database are `harness-worker-glm-1` (GLM worker), `harness-reviewer-glm` (GLM reviewer) and `harness-reviewer` (Opus reviewer). The script creates empty profile directories for them inside the temporary directory, because the tool `kanban_request_review` checks that a named reviewer is an installed profile.

## Safety rules and how the script keeps them

1. `HERMES_HOME`: before any Hermes module is imported, the script removes every `HERMES_*` variable of the calling environment (a worker session has `HERMES_KANBAN_DB` set to the live board database) and sets `HERMES_HOME`, `HOME` and `HERMES_KANBAN_HOME` to `<new directory>/home`. It then asks Hermes for `kanban_db_path()` and `kanban_home()`; when either is outside the new directory it prints the path and exits with status 2 before the first write. This path was checked once on 2026-11-14 by a caller that replaced `_isolate_environment` so that `HERMES_KANBAN_DB` named a file outside the new directory: the script printed that path, exited with status 2, and the file was not created.
2. Files under `/Users/chanbla11mit/.hermes`: an audit hook (`sys.addaudithook`) stops the process with exit status 3 when it opens, lists or changes a path under `/Users/chanbla11mit/.hermes` other than the Hermes source tree `/Users/chanbla11mit/.hermes/hermes-agent` and the new directory. The hook is installed in the main process and in both child modes. `sys.dont_write_bytecode` is set before the first import, so no bytecode file is written into the Hermes source tree.
3. Process IDs: the only process ID that Hermes receives is the ID of the stand-in child process that the script started (`_set_worker_pid`). Hermes `reclaim_task` signals that process. The script itself sends no signal to any process.
4. No gateway, no dispatcher loop, no model call: the script calls none of them. Socket creation raises an error in every process of the script.
5. Run time and cleanup: the run takes about 9 seconds, of which about 6 seconds are the SIGKILL variant of candidate b. The new directory is removed at the end unless `--keep` is given.

## How to run

From the worktree root:

```
/Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I spikes/glm-reviewer-pass/run.py
```

Optional arguments: a base directory as the first argument (default `/Users/chanbla11mit/.hermes/profiles/harness-worker-2/cache/scratch/t_bdfbfb88`; the script creates a new directory `glm-reviewer-pass-<random>` inside it), and `--keep` to keep that directory. Exit status 0 means that every sequence ran.

## Hermes version

Run against `/Users/chanbla11mit/.hermes/hermes-agent` at commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6`.

## Output of the recorded run (2026-11-15)

Complete output. Between runs only the path of the temporary directory and the times in observations 8 and 11 change. The line that starts with `Middleware 'tool_execution' callback raising_middleware raised` is a warning that Hermes writes for the test middleware of observation 32.

```
Kanban database: /Users/chanbla11mit/.hermes/profiles/harness-worker-2/cache/scratch/t_bdfbfb88/glm-reviewer-pass-aggbn33y/home/kanban.db
Hermes source: /Users/chanbla11mit/.hermes/hermes-agent
OBSERVED 1 worker run requested review by the GLM reviewer, GLM reviewer claimed it from review: status=running, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, run 2 profile=harness-reviewer-glm, claimed source_status=review
OBSERVED 2 GLM reviewer run called the kanban_request_review tool with reviewer=Opus reviewer: status=review, assignee=harness-reviewer, implementer=harness-reviewer-glm, tool ok=True error=None, run 2 outcome=review_requested
OBSERVED 3 Opus reviewer claimed it from review and called kanban_request_changes: status=ready, assignee=harness-reviewer-glm, implementer=harness-reviewer-glm, tool implementer=harness-reviewer-glm, changes_requested reviewer=harness-reviewer
OBSERVED 4 next ready-lane claim without a plugin step (what the dispatcher would start): status=running, assignee=harness-reviewer-glm, implementer=harness-reviewer-glm, run 4 profile=harness-reviewer-glm, claimed source_status=None
OBSERVED 5 candidate a plugin step after the change request: hermes kanban assign <id> <worker>: status=ready, assignee=harness-worker-glm-1, implementer=harness-reviewer-glm, command exit status=0
OBSERVED 6 GLM reviewer run called kanban_request_changes (it has findings): status=ready, assignee=harness-worker-glm-1, implementer=harness-worker-glm-1, tool implementer=harness-worker-glm-1, changes_requested reviewer=harness-reviewer-glm
OBSERVED 7 GLM reviewer run with a child process recorded as worker (stand-in run keeps the default SIGTERM action): status=running, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, fingerprint recorded=True
OBSERVED 8 command started inside the run (stand-in run keeps the default SIGTERM action): status=review, assignee=harness-reviewer, implementer=harness-worker-glm-1, command exit status=0, stand-in run exit code=-15, stand-in run reached its end=False, stand-in run ended 0.4s after the command started and 0.1s before the command finished, reclaimed payload terminated=True sigkill=False retry_status=review, events in order=['reclaimed', 'assigned'], run 11 outcome=reclaimed
OBSERVED 9 Opus reviewer claimed it from review and requested changes (stand-in run keeps the default SIGTERM action): status=ready, assignee=harness-worker-glm-1, implementer=harness-worker-glm-1, request_changes ok=True returned implementer=harness-worker-glm-1
OBSERVED 10 GLM reviewer run with a child process recorded as worker (stand-in run ignores SIGTERM): status=running, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, fingerprint recorded=True
OBSERVED 11 command started inside the run (stand-in run ignores SIGTERM): status=review, assignee=harness-reviewer, implementer=harness-worker-glm-1, command exit status=0, stand-in run exit code=-9, stand-in run reached its end=False, stand-in run ended 6.4s after the command started and 0.1s before the command finished, reclaimed payload terminated=True sigkill=True retry_status=review, events in order=['reclaimed', 'assigned'], run 14 outcome=reclaimed
OBSERVED 12 Opus reviewer claimed it from review and requested changes (stand-in run ignores SIGTERM): status=ready, assignee=harness-worker-glm-1, implementer=harness-worker-glm-1, request_changes ok=True returned implementer=harness-worker-glm-1
OBSERVED 13 GLM reviewer run called the kanban_block tool with the reason jev-glm-review-pass (way W3, steps 1 and 2): status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, tool ok=True, blocked source_status=review kind=needs_input recurrences=1, run 17 outcome=blocked
OBSERVED 14 dispatcher promotion pass (recompute_ready) while the card is blocked: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, promoted count=0
OBSERVED 15 way W3 step 3: hermes kanban assign <id> <Opus reviewer> inside the GLM reviewer session: status=blocked, assignee=harness-reviewer, implementer=harness-worker-glm-1, command exit status=0
OBSERVED 16 hermes kanban unblock <id> inside the GLM reviewer session (HERMES_KANBAN_TASK set): status=blocked, assignee=harness-reviewer, implementer=harness-worker-glm-1, command exit status=1, refused as orchestrator-only=True
OBSERVED 17 way W3 step 4: hermes kanban unblock <id> with HERMES_KANBAN_TASK and HERMES_KANBAN_RUN_ID removed: status=review, assignee=harness-reviewer, implementer=harness-worker-glm-1, command exit status=0, unblocked resume_status=review
OBSERVED 18 next review-lane claim (what the dispatcher would start): status=running, assignee=harness-reviewer, implementer=harness-worker-glm-1, run 18 profile=harness-reviewer
OBSERVED 19 Opus reviewer called kanban_request_changes: status=ready, assignee=harness-worker-glm-1, implementer=harness-worker-glm-1, tool implementer=harness-worker-glm-1
OBSERVED 20 worker fixed and requested review by the Opus reviewer, Opus reviewer called kanban_complete: status=done, assignee=harness-reviewer, implementer=harness-worker-glm-1, request_review ok=True, complete ok=True
OBSERVED 21 failure of the assign step: state after the block by the GLM reviewer only: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, no further command
OBSERVED 22 a person or orchestrator unblocks that card without assigning it: status=review, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, command exit status=0
OBSERVED 23 failure of the unblock step: state after the block and the assign, then a dispatcher promotion pass: status=blocked, assignee=harness-reviewer, implementer=harness-worker-glm-1, promoted count=0
OBSERVED 24 earlier worker block kind=capability, pass block with same kind as the earlier block (kind=capability): status=triage, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, recurrences=2 limit=2
OBSERVED 25 earlier worker block kind=capability, pass block with a kind different from the earlier block (kind=needs_input): status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, recurrences=1 limit=None
OBSERVED 26 block_task and schedule_task called on the card in status review: status=review, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, block_task returned False, schedule_task returned False
OBSERVED 27 present plugin selection peak_hold.holdable_cards for the GLM profiles: status=review, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, review card selected=False, card with a running GLM worker run selected=False
OBSERVED 28 claim_review_task without a process, then block_task with the hold marker: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, block_task returned True, source_status=review, run 33 profile=harness-reviewer-glm outcome=blocked
OBSERVED 29 dispatcher promotion pass during the window, then hermes kanban unblock after the window: status=review, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, promoted count during the window=0, unblock exit status=0
OBSERVED 30 comparison: claim_review_task, schedule_task, then hermes kanban unblock: status=ready, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, unblock exit status=0
OBSERVED 31 GLM reviewer run called kanban_complete with no plugin loaded: status=done, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, tool ok=True
Middleware 'tool_execution' callback raising_middleware raised: plugin failure before next_call (middleware provides: args, middleware_schema_version, next_call, original_args, telemetry_schema_version, tool_name; identical failures are logged at DEBUG from now on)
OBSERVED 32 kanban_complete through the Hermes tool_execution chain with a middleware that raises before next_call: status=done, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, tool executed=True, result error=False
OBSERVED 33 kanban_complete through the Hermes tool_execution chain with a middleware that returns an error without next_call: status=running, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, tool executed=False, result error=True
OBSERVED 34 GLM reviewer run called the kanban_block tool with the reason jev-glm-review-pass: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, tool ok=True, selection rule of the hold script selects the card=True (blocked source_status=review, profile of the blocking run=harness-reviewer-glm)
OBSERVED 35 hermes kanban assign <id> <Opus reviewer> in a child of the GLM reviewer session started with delegated_child_subprocess_env: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, environment from delegated_child_subprocess_env: marker set to the Kanban home=True, HERMES_KANBAN_TASK present=False, HERMES_KANBAN_RUN_ID present=False, command exit status=1, refused for a delegated child=True
OBSERVED 36 hermes kanban unblock <id> in the same environment: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, command exit status=1, refused for a delegated child=True
OBSERVED 37 Hermes function unblock_task called in the same environment: status=blocked, assignee=harness-reviewer-glm, implementer=harness-worker-glm-1, exception=PermissionError
OBSERVED 38 hermes kanban assign <id> <Opus reviewer>, then hermes kanban unblock <id>, in an environment with no HERMES_KANBAN_TASK, HERMES_KANBAN_RUN_ID or HERMES_DELEGATED_CHILD_CONTEXT (as a launchd process): status=review, assignee=harness-reviewer, implementer=harness-worker-glm-1, delegated_child_subprocess_env leaves that environment unchanged=True, assign exit status=0, unblock exit status=0, unblocked resume_status=review
OBSERVED 39 next review-lane claim (what the dispatcher would start): status=running, assignee=harness-reviewer, implementer=harness-worker-glm-1, run 44 profile=harness-reviewer
OBSERVED 40 GLM worker implementation run (claimed from ready) called kanban_block with the reason jev-glm-review-pass: status=blocked, assignee=harness-worker-glm-1, implementer=none, selection rule of the hold script selects the card=False (blocked source_status=ready, profile of the blocking run=harness-worker-glm-1)
All sequences ran: 40 observations.
```
