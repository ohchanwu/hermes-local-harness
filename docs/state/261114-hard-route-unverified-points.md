# Points not yet verified for GLM workers on `hard` cards: report

Date: 2026-11-14 (all times KST, UTC+09:00).
Card: `t_00cbdf0e` on board `harness`. Repository baseline: `c9e91312f2583d960b21fe2ef8787d1da6fb048d`.
Hermes commit read: `9cf7960f274ea2bdfe672d64d26389e9954dfeb6` (output of `git -C /Users/chanbla11mit/.hermes/hermes-agent rev-parse HEAD`).
Specification: the request file `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/cache/scratch/camp/handoff-copy.md` (35,677 bytes, SHA-256 `2bc8c3dda0d03e42169a8cfe7f39d9e40bfc35d2d96943856cdc42f17b988ac5`), sections "Facts verified", "Not verified", "Part 2", "Part 3" and "Part 4". A parallel card copies it to `docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md`.

This card read files and changed nothing live. Each statement under **Evidence** says how it was obtained:
- "source reading": the code was read; it was not run.
- "observed record": a row of the `harness` Kanban database (opened with `sqlite3 -readonly`), a record of `/Users/chanbla11mit/.hermes/jev/logs/decisions.jsonl` with `board` `harness`, or a line of `agent.log` or `errors.log` of `harness-worker-glm-1`, `harness-worker-glm-2` or `harness-worker-glm-3`. These logs were read only through `grep` with a pattern, with every line cut to 300 characters and passed through the required `sed` redaction.
- "tested": a request that this card sent and whose answer it recorded (question 4 only).
- "public page": https://docs.z.ai/guides/llm/glm-5.3, fetched on 2026-11-14.

Not read on this card: the `config.yaml` files of any profile, the Kanban worker log files under the board directory, the gateway log, and the databases and logs of the other four boards.

## Summary

1. Reasoning effort key: Hermes reads `agent.reasoning_effort` (after a per-model `agent.reasoning_overrides` entry), never `model.reasoning_effort`. The order is per-card `tasks.reasoning_effort` (sent as `--reasoning`), then `agent.reasoning_overrides`, then `agent.reasoning_effort`, then no field at all. Today the runs of the three harness GLM workers send no `reasoning_effort` field, by source reading, so Z.ai applies its default, which the public page gives as `max`. A profile value `max` under `agent` would be sent as `max`.
2. Part 3: the facts of option A are confirmed, and the inference about reviewer and Claude worker runs is confirmed by source reading. Option B needs three corrections: the key is `agent.reasoning_effort`; the GLM worker rotation counter must be kept per worker list; and the explicit `high` for `easy` and `medium` is a change from today's server default. Recommendation: B, with these corrections.
3. Z.ai usage limit: one stop for the harness GLM workers, on 2026-11-13 at 20:09 (card `t_c8c6860f`, run 371). Hermes recorded outcome `rate_limited` and exit code 75, set the card to `ready`, counted no failure, and started run 372 by itself at 20:15:29, after the 300-second cooldown. By source reading a `review` run takes the same path and returns to `review`. In both cases the card stays visible on the board, but nobody is notified until the plan's limit resets. The defect in `docs/bugs/261028-kanban-rate-limited-exit-settled-as-stale-reclaim.md` did not occur in this stop, but it applies to both lanes.
4. Four criteria: no code limits the number of routes or assumes three; the only count check is a minimum of two. Tested with 12 requests: every answer had four probabilities that sum to 1.0. The session cookie card was `medium` twice. The Stripe card was `hard` once and `easy` once, and never `very_hard`. The undecided authentication card and the card that runs commands against live Hermes were `very_hard` twice.
5. Readers of `glm_workers`: two direct reads in `plugins/jev/routing.py` (lines 323 and 723) and one helper pair in `plugins/jev/peak_hold.py` (lines 148 and 158), on which six other call sites depend. `scripts/jev-route-notice` and `routing.decide` read the list named by `assignee_from`, so they need no change. `scripts/verify-state` and two tests decide by fixed profile names, which option B keeps.
6. Limit per route: only `routed_claude_worker` reads the `route` record (the latest matching record in `decisions.jsonl`). Of the 31 `harness` route records, 9 have `applied_route` and 22 do not. Every record since 2026-11-14 19:43:57 has the field. A record without it should fall back to `route` when `applied` is true; this gives the general value 5 for every such card.
7. Capacity: the database records no token counts. The GLM worker `agent.log` files give 24.2M tokens on 2026-11-13 and 48.1M on 2026-11-14 up to 23:33; about 97% of the input tokens are cache reads. There was one stop, on 2026-11-13. The plan's limit is not available.
8. `max` compared with `high`: the public page gives a vendor benchmark figure of about 75K output tokens per task at `max` and about 50K at `high`. No measurement exists for these boards. Today's runs probably already run at `max`.

## 1. Which key gives a dispatcher-started GLM run its reasoning effort

**Answer**

- Source reading: a run that the dispatcher starts reads its reasoning effort from `agent.reasoning_effort`, after a matching entry in `agent.reasoning_overrides`, unless the run command contains `--reasoning`. Hermes does not read `model.reasoning_effort` anywhere on this path. The comment at `hermes_cli/kanban_db.py` line 1010 names the key that the code reads.
- Order of precedence, by source reading:
  1. `tasks.reasoning_effort` of the card, when it is set. The dispatcher adds `--reasoning <value>` to the run command, and that wins for the run.
  2. `agent.reasoning_overrides.<model>` for the model of the run (the model is `glm-5.3` or `glm-5.3-flash`, set by the card's model override).
  3. `agent.reasoning_effort`.
  4. Nothing: Hermes sends neither a `reasoning_effort` field nor a `thinking` field, and the Z.ai server default applies. The public page gives that default as `max`.
- What the three harness GLM workers send today:
  - Observed record: all 160 cards of board `harness` have `tasks.reasoning_effort` NULL, so no run command has `--reasoning`.
  - The request file states that the GLM worker profiles set `reasoning_effort: high` under `model:`. If they set nothing under `agent:`, then by source reading their requests carry no `reasoning_effort` field. Z.ai then uses its default, which the public page gives as `max`, not `high`.
  - No log of these profiles records the value sent (no log file or field exists for it).
- A profile value `max` under `agent.reasoning_effort` (or under `agent.reasoning_overrides` for the run's model) would be sent as `max`: the top-level request field `reasoning_effort: "max"` with `thinking: {"type": "enabled"}`. A value `max` under `model.reasoning_effort` would not be read, so nothing would be sent.

**Evidence**

- Source reading, the value from the dispatcher to the run:
  - `hermes_cli/kanban_db_dispatch.py` lines 2769 to 2770: `--reasoning` is added only when `task.reasoning_effort` is set. The same function `_worker_argv` (lines 2743 to 2777) builds the command for both lanes; `_default_spawn` calls it at line 2940.
  - `hermes_cli/_parser.py` line 251: the `chat` subcommand accepts `--reasoning`.
  - `hermes_cli/cli_init_mixin.py` lines 260 to 273: first `resolve_reasoning_config(CLI_CONFIG, self.model)`, then `--reasoning` replaces it when it parses.
- Source reading, the profile keys:
  - `hermes_constants.py` lines 1109 to 1132, `resolve_reasoning_config`: it reads `agent.reasoning_overrides` (through `resolve_per_model_reasoning_effort`, lines 1061 to 1093) and then `agent.reasoning_effort`. It reads `model` only to find the model name (lines 1117 to 1121).
  - `hermes_cli/cli_config_load.py` lines 200 to 204: the default `agent.reasoning_effort` is the empty string. Lines 228 to 235: the `model:` section is merged into the `model` dictionary, and no key of it is moved to `agent`.
  - A search of the Hermes source (outside `tests/`) for `reasoning_effort` together with `model` found no reader of `model.reasoning_effort`.
- Source reading, from the run to the request:
  - `agent/chat_completion_helpers.py` lines 1492 to 1511: the provider profile for `agent.provider` (`zai`) builds the request.
  - `agent/transports/chat_completions.py` lines 153 to 162 and 559 to 574: the effort is clamped to `OPENAI_COMPAT_WIRE_EFFORTS`, which contains `max` (`agent/reasoning_effort.py` line 28). Then `ZaiProfile.build_api_kwargs_extras` runs.
  - `plugins/model-providers/zai/__init__.py`:
    - lines 31 to 42: with `glm-5.3` in the model name, `GLM53_EFFORTS` (`agent/reasoning_effort.py` line 78: `low`, `medium`, `high`, `max`) applies, so `max` stays `max`;
    - lines 57 to 63: `thinking` is added only when a reasoning configuration exists, and the top-level `reasoning_effort` only when an effort exists;
    - with no configuration, neither field is added.
  - `hermes_constants.py` lines 994 and 997 to 1021: `max` is a valid level; an empty value gives no configuration.
- Observed record: `sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db "SELECT coalesce(reasoning_effort,'NULL'), count(*) FROM tasks GROUP BY 1;"` returned `NULL|160`.
- Observed record: `grep -c -iE 'reasoning'` and `grep -c -iE 'effort|thinking'` on `agent.log` and `errors.log` of the three GLM worker profiles returned 0 for each file.
- Public page: the table "reasoning_effort | low, high, max | Default max".

**Not established**

- The live `config.yaml` of the three GLM worker profiles was not read (it is outside the inputs of this card). Whether they set `agent.reasoning_effort` or `agent.reasoning_overrides` is therefore not established; the statement about `model:` comes from the request file. Reading those two keys in the three files would settle it.
- No request sent to Z.ai was captured, so the value sent is established only by source reading. A request captured in an isolated Hermes home (`procedures/isolated-hermes-test-home.md`) for a profile with no `agent.reasoning_effort` and for one with `agent.reasoning_effort: max` would show the field.
- Whether Z.ai applies its documented default `max` to requests on the endpoint `https://api.z.ai/api/coding/paas/v4` (the base URL in the GLM worker logs) is not established beyond the public page.

## 2. Per-card value or profile value (Part 3, options A and B)

**Answer**

Facts of option A:
- Confirmed: no `kanban_create` argument and no `hermes kanban` subcommand sets `tasks.reasoning_effort`.
- Addition: `create_task` in `hermes_cli/kanban_db.py` accepts `reasoning_effort`, but the tool handler does not pass it.
- Confirmed: the setter `set_reasoning_effort` exists, and only the dashboard plugin calls it.
- Confirmed, now by source reading and not only by inference: the dispatcher builds the command of every run of the card, review runs included, with the same function. The reviewer runs would therefore get `--reasoning max`. `assign_task` does not clear the value, so the Claude worker after reassignment would also get `--reasoning max`.

Facts of option B:
- Correction: the profile key that Hermes reads is `agent.reasoning_effort`, not `model.reasoning_effort` (section 1).
- Correction: the request file assumes that `easy` and `medium` cards run at `high` today. By source reading they send no effort and get the server default, which the public page gives as `max`. Keeping `easy` and `medium` at `high` therefore needs `agent.reasoning_effort: high` on `glm-1` and `glm-2`. That is a change from today's behaviour.
- Confirmed: no per-card state is needed, and no Hermes internals are imported.
- Confirmed: `easy` and `medium` cards would alternate over two GLM workers.
- Not established: that only one `hard` card per board runs on GLM at a time. `roster.yaml` declares `concurrency_limit: 1` for `harness-worker-glm-3`, but `scripts/verify-state` does not check that field. The dispatcher limit per profile is the live Kanban setting read at `hermes_cli/kanban_db_dispatch.py` line 2367, which was not read.
- Confirmed: every reader of `glm_workers` must also read the new list (section 5).
- Addition: the GLM worker rotation counter is kept per board, not per list (`routing.py` lines 135 to 146). A one-worker list for `hard` would reset that counter to 0 on every `hard` card, so the `easy` and `medium` rotation would restart at the first worker each time.

What the `jev` plugin would have to do:
- Option A:
  1. After `kanban_create` returns a card whose applied route is `hard` and that went to a GLM worker, set `tasks.reasoning_effort` to `max`. This needs `hermes_cli.kanban_db.set_reasoning_effort` imported from Hermes and a connection to the board database, or a call to the dashboard API, because no command exists.
  2. In `handle_request_review` (GLM worker session), clear the value together with the model override.
  3. In `handle_request_changes`, when the card goes back to the GLM worker, set `max` again. Hermes `request_changes` makes the card `ready` before the middleware runs, so a dispatcher pass can start the next GLM run before the value is set.
  4. Before the reassignment to the Claude worker, clear the value.
  5. Fail open at each step: if a clear fails, a reviewer or Claude worker run is started with `--reasoning max`.
- Option B:
  1. Add `glm_max_workers` to each board in `config.json` and give `hard` `assignee_from: glm_max_workers`, `model: glm-5.3` and `provider: zai`.
  2. Make every reader of section 5 treat both lists as GLM workers. The smallest change is in `peak_hold.glm_workers_by_board` and `peak_hold.all_glm_workers`, plus the two direct reads in `routing.py`.
  3. Keep the rotation counter per board and per list.
  4. The deployment card sets `agent.reasoning_effort: max` on the five `<board>-worker-glm-3` profiles and, if the owner wants `high` for `easy` and `medium`, `agent.reasoning_effort: high` on the other ten GLM worker profiles.

Recommendation: option B, with the three corrections above. Reasons:
- With option B the effort belongs to the profile, so it applies to every run of that profile and to no reviewer or Claude worker run. No change is needed when the model override is cleared at review.
- Option A needs Hermes internals imported into the plugin, four writes to keep in step for each card, and it has the timing gap after a change request.
- An explicit `max` on the profile is better than relying on the server default, so that a change of that default does not change the effort.

**Evidence**

- Source reading, the per-card value and how it can be set:
  - `tools/kanban_tools_schemas.py`: the `kanban_create` schema has `model` and `provider` and no reasoning property; `grep -n -i reasoning tools/kanban_tools.py` finds nothing.
  - `tools/kanban_tools.py` lines 1095 to 1133 (`_handle_create`) call `kb.create_task` without `reasoning_effort`.
  - `hermes_cli/kanban_db.py` lines 1335 and 1362: `create_task` takes and normalizes `reasoning_effort`.
  - `grep -c -i reasoning hermes_cli/kanban.py hermes_cli/kanban_parser.py` returned 0 for both files.
  - `hermes_cli/kanban_db.py` lines 1690 to 1699: `set_reasoning_effort` writes the column and the event `reasoning_effort_set`.
  - `plugins/kanban/dashboard/plugin_api.py` line 616 is the only caller outside tests.
- Source reading, how the value reaches each run:
  - `hermes_cli/kanban_db_dispatch.py` line 2427 (review lane) and line 2940 (`_default_spawn` calls `_worker_argv`): one command builder for every run.
  - `hermes_cli/kanban_db.py` lines 1625 to 1654: `assign_task` resets `consecutive_failures` and `last_failure_error` only.
  - `plugins/jev/routing.py` lines 594 and 743: the plugin's only effort-related command today is `set-model <id> none`, which clears the model and provider, not the reasoning effort (`hermes_cli/kanban_db.py` lines 1657 to 1669).
- Source reading, the corrections to option B:
  - The profile key: section 1.
  - The rotation counter: `plugins/jev/routing.py` lines 135 to 146 (`_next_in_rotation`, `counters[board] = (index + 1) % len(workers)`) and line 407 (`next_glm_worker(board, pool, state_dir)`).
- Observed record: `roster.yaml` line 2990, `"concurrency_limit": 1` in the entry of `harness-worker-glm-3`. `grep -n concurrency_limit scripts/verify-state` returned nothing.
- Public page: default `max`; "For complex tasks such as coding, we recommend using max".

**Not established**

- How `claude-subscription` runs (the reviewers and the Claude workers) treat `--reasoning max`. This matters only for option A; it was not read or tested.
- How often a dispatcher pass would start a GLM run between `request_changes` and the plugin's write under option A. A test in an isolated Hermes home would show it.
- The live dispatcher limit per profile (see Answer).

## 3. Usage limit of the Z.ai plan

**Answer**

Observed, harness GLM workers: one stop on the plan's usage limit, on 2026-11-13 at 20:09:32.
- Profile `harness-worker-glm-1`, session `20261113_190059_19fc93`, error class `RateLimitError`, HTTP status 429, Z.ai error code `1308`.
- Card `t_c8c6860f`, run 371, started at 19:00:57.
- Hermes recorded run outcome `rate_limited`, exit code 75, retry status `ready`, at 20:10:26. The card's status became `ready`.
- The dispatcher recorded five `respawn_guarded` events with reason `rate_limit_cooldown` (20:10:26 to 20:14:28). It then started run 372 by itself at 20:15:29, 303 seconds after the stop, with no human action in between. Run 372 ended with `review_requested` at 20:32:08, and the card was done at 21:01:41.
- The stop was not counted as a failure: the settlement path does not call the failure counter, and the card has no `gave_up` event.

Stops per day, harness GLM workers:
- 2026-11-13: 1.
- Every other day in these logs (2026-10-14 to 2026-11-14 23:33): 0.
- The hours 09 and 10 of 2026-11-13 named by the request file have no usage-limit record in the logs of the three harness GLM workers. They are not on this board.

Source reading, a run of the lane `review`:
- Any Kanban run whose turn fails on a provider rate limit exits with code 75.
- The dispatcher books it as `rate_limited` without counting a failure. It returns the card to `review`, not `ready`, because the run was claimed from `review`.
- It then waits 300 seconds before each new review run, and repeats this without limit until a run succeeds.
- Observed record on this board (a Claude reviewer, not a GLM run): card `t_b27aa945` had 40 `harness-reviewer` runs with outcome `rate_limited` and retry status `review` (2026-11-03 23:04 to 2026-11-04 03:00), 200 `respawn_guarded` events with reason `rate_limit_cooldown`, no `gave_up` event, and then a completed review run at 03:11:47.
- No GLM review run exists today. By source reading, a GLM reviewer under Part 6 would take the same path.

Visibility in both cases:
- The card stays in status `ready` (worker) or `review` (review lane) and shows the run outcome `rate_limited` and a set `last_failure_error`. It stays without work or review until the plan's limit resets.
- Nobody is notified: the events `rate_limited`, `respawn_guarded` and `reclaimed` are not among the event kinds that the gateway notifier sends.
- A card is therefore not hidden, but its waiting is reported to nobody.

Relation to `docs/bugs/261028-kanban-rate-limited-exit-settled-as-stale-reclaim.md`:
- The observed stop was settled through `detect_crashed_workers`, 54 seconds after the error. That is the path that does not count a failure and applies the cooldown. The defect path did not occur.
- The installed Hermes commit is the one the bug note analysed, so the defect is still present: when no dispatcher pass sees the dead worker before its claim expires, `release_stale_claims` books the run as `reclaimed` and counts a failure.
- That applies equally to a GLM worker run and to a review run. Two such reclaims in a row reach the default failure limit of 2 and block the card with `gave_up`. That state is notified.

**Evidence**

- Observed record, logs:
  - `grep -n -iE 'usage limit|1308|1310|1113|rate.?limit|quota|429' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-1/logs/errors.log | cut -c1-300 | sed -E ...` gives lines 113, 166, 167 and 168, all at 2026-11-13 20:09:32, all in session `20261113_190059_19fc93`, with `RateLimitError`, status 429 and code `1308`.
  - `grep -c -E "Usage limit reached|'code': '1308'"` returned 4 for `agent.log` and 4 for `errors.log` of `harness-worker-glm-1`, and 0 for both files of `harness-worker-glm-2` and `harness-worker-glm-3`.
  - The four lines of each file belong to the one stop.
  - The first and last timestamps of the three `agent.log` files: 2026-10-14 13:44:25 to 2026-11-14 22:29:37 (`glm-1`), 2026-10-14 13:44:28 to 2026-11-14 23:33:47 (`glm-2`), 2026-11-14 09:18:30 to 2026-11-14 23:31:18 (`glm-3`).
- Observed record, `task_runs`:
  - `SELECT ... FROM task_runs WHERE outcome='rate_limited' ...` lists run 371 (`t_c8c6860f`, `harness-worker-glm-1`, 19:00:57 to 20:10:26). It is the only `rate_limited` run of a GLM worker.
  - The other `rate_limited` runs of the board belong to `harness-worker-2` (run 111), `harness-worker` (run 396) and `harness-reviewer` (runs 232 to 271 and 360).
- Observed record, `task_events` of `t_c8c6860f`:
  - event 6509 `rate_limited`, payload fields `exit_code` 75 and `retry_status` `ready`;
  - events 6510 to 6514 `respawn_guarded` with `rate_limit_cooldown`;
  - event 6515 `claimed`, run 372, 20:15:29;
  - event 6539 `review_requested`;
  - event 6597 `completed`.
- Observed record, `t_b27aa945`:
  - run outcomes: `rate_limited` 40, `completed` 1, `review_requested` 1;
  - all 40 `claimed` events of runs 232 to 271 carry `source_status` `review`;
  - `respawn_guarded` events: 200, all with `rate_limit_cooldown`;
  - no `gave_up` event for the card (the board's 11 `gave_up` events are listed by `SELECT ... WHERE kind='gave_up'`).
- Source reading, Hermes:
  - `hermes_cli/cli_single_query.py` lines 147 to 190: exit code 75 for a Kanban run that failed on a provider rate limit. The test is whether `HERMES_KANBAN_TASK` is set, not which lane the run is in.
  - `hermes_cli/kanban_db.py` line 309: `KANBAN_RATE_LIMIT_EXIT_CODE = 75`.
  - `hermes_cli/kanban_db_dispatch.py`:
    - lines 1097 to 1106: outcome `rate_limited`, no failure;
    - lines 1146 to 1213: the status becomes the retry status, and lines 1198 to 1209 set `last_failure_error` without touching `consecutive_failures`;
    - line 80: `DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 300`;
    - lines 1525 to 1583: the cooldown applies in both lanes and then retries without limit;
    - line 2305: review lane guard.
  - `hermes_cli/kanban_db.py` lines 2406 to 2418: `_retry_status_for_run` gives `review` when the run was claimed from `review`.
  - `gateway/kanban_watchers_notifier.py` lines 47 and 50: `TERMINAL_KINDS` and `_WAKE_KINDS` contain neither `rate_limited` nor `respawn_guarded` nor `reclaimed`.
- The bug note: `docs/bugs/261028-kanban-rate-limited-exit-settled-as-stale-reclaim.md`, Diagnosis (a) and (b), for the installed Hermes commit `9cf7960f274e`.

**Not established**

- Where the stops in hours 09 and 10 of 2026-11-13 were recorded. The logs of the GLM workers of the other boards are outside this card.
- Whether the GLM runs of other boards, which can also start when the hold window ends at 19:00, used the same Z.ai plan and contributed to the stop at 20:09. Run 371 started 57 seconds after that window ended.
- The value of `consecutive_failures` at 20:10:26. Hermes stores only the current value, which is 0 after completion.
- Why run 372 was claimed by a different dispatcher process (claim lock `Chanwus-MacBook-Pro-2.local:2447`) than run 371 (`...:78153`). The gateway log was not read.
- The reset time in the Z.ai error response. Its time zone is not stated; the next run, 5 minutes later, did not meet the limit.

## 4. Four criteria

**Answer**

(a) Source reading:
- No code in `plugins/jev/routing.py` or `plugins/jev/jev_client.py` limits the number of routes or assumes three.
- `route_question` (lines 195 to 200) makes one criterion for each enabled route. `_parse_answer` (lines 217 to 231) accepts any route name of the board. `_glm_sum` (lines 286 to 296) and the decision code (lines 369 to 382) loop over the routes.
- The only count check is the minimum of two routes (line 329, `single_route`).
- `jev_client.ask` (lines 57 to 114) sends the questions unchanged and limits only the response size (4 MiB, line 24).
- Outside these two files, tests and policy text name three routes, for example `tests/test_jev_policy_sources.py` line 555.

(b) Tested:
- 12 requests in total: each of the six synthetic cards below was sent twice with the four criteria.
- Every answer named a route and had four probabilities whose sum is 1.0.
- Response times were 174 to 328 ms, and input sizes were 606 to 742 tokens.
- The applied route of each answer comes from `routing.decide` of this worktree on the proposed `config.json` of Part 2 step 1, with `routing.control_group_every` set to 0 so that the control group does not hide the route.
- The owner's two examples were never `very_hard`:
  - the session cookie card (C3) was `medium` both times;
  - the Stripe card (C4) was `hard` the first time (0.38 against `easy` 0.37) and `easy` the second time (0.40 against `hard` 0.34), so identical requests gave different applied routes.
- C5 (authentication with the approach undecided) and C6 (the worker runs commands against the live Hermes installation) were `very_hard` both times, at 1.0 and 0.98. The card stayed with the Claude worker, as `hard` does today.
- C2 (a fully specified change across several files) was `easy`, not `medium`, both times, so it would run on `glm-5.3-flash`.

| Card | Try | easy | medium | hard | very_hard | Sum | Time (ms) | Jev's choice | Applied route (proposed config) |
|---|---|---|---|---|---|---|---|---|---|
| C1 names its files and check command | 1 | 1.00 | 0.00 | 0.00 | 0.00 | 1.00 | 207 | easy | easy |
| C1 | 2 | 1.00 | 0.00 | 0.00 | 0.00 | 1.00 | 185 | easy | easy |
| C2 fully specified, several files | 1 | 0.71 | 0.29 | 0.00 | 0.00 | 1.00 | 328 | easy | easy |
| C2 | 2 | 0.69 | 0.31 | 0.00 | 0.00 | 1.00 | 175 | easy | easy |
| C3 session cookie, behaviour stated | 1 | 0.20 | 0.48 | 0.31 | 0.01 | 1.00 | 183 | medium | medium |
| C3 | 2 | 0.16 | 0.49 | 0.34 | 0.01 | 1.00 | 203 | medium | medium |
| C4 one Stripe request, behaviour stated | 1 | 0.37 | 0.24 | 0.38 | 0.01 | 1.00 | 174 | hard | hard |
| C4 | 2 | 0.40 | 0.26 | 0.34 | 0.00 | 1.00 | 197 | easy | easy |
| C5 authentication, approach undecided | 1 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 181 | very_hard | very_hard |
| C5 | 2 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 283 | very_hard | very_hard |
| C6 worker runs commands on live Hermes | 1 | 0.01 | 0.00 | 0.01 | 0.98 | 1.00 | 283 | very_hard | very_hard |
| C6 | 2 | 0.01 | 0.00 | 0.01 | 0.98 | 1.00 | 177 | very_hard | very_hard |

**Evidence**

- Source reading: the line numbers given in (a).
- Tested, setup:
  - Script `cache/scratch/t_00cbdf0e/q4_run.py` of the `harness-worker` profile directory, run with `HERMES_JEV_LOG_DIR=/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_00cbdf0e/jevlogs /Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I q4_run.py`.
  - It imports `jev_client` and `routing` from `/Users/chanbla11mit/hermes-local-harness/.worktrees/t_00cbdf0e/plugins/jev/` and calls `routing.decide` with `assignee` `harness-worker`, board `harness`, no `model`, and `state_dir` in the same temporary directory.
  - The script stops after 12 requests and printed `{"requests_sent": 12}`. No record was written to the shared Jev logs; the temporary log directory stayed empty, because `decide` does not write logs.
  - The `TYPESAFE_API_KEY` variable was checked only with `[ -n "${TYPESAFE_API_KEY:-}" ] && echo set || echo not-set`, which printed `set`.
- Tested, criteria sent (route order as proposed):
  - `easy` and `medium`: the texts of `plugins/jev/config.json` lines 53 and 55.
  - `hard`: "Everything that is not easy, medium or very hard: a design decision, a fault with an unknown cause, or logic for authentication, secrets, payment, a database migration or deployment when the card states the required behaviour. The topic alone does not make a card very hard."
  - `very_hard`: "Work on authentication, secrets, payment, a database migration or production systems, and in addition either the card leaves the required behaviour or the approach undecided, or the problem is very complex: many parts that depend on each other and must be worked out together. Also any card whose worker itself runs commands against production or against the live Hermes installation."
  - The question instruction was "Which route fits the work this Kanban card asks for?".
  - In the proposed configuration, `hard` had `assignee_from` `glm_workers`, `model` `glm-5.3` and `provider` `zai`; `very_hard` had neither `assignee_from` nor `model`.
- Tested, the six synthetic card texts (title, then body), as sent:
  - C1. Title: "Fix the spelling of one word in the usage text of scripts/example-report". Body: "Repository /tmp/example ONLY. / In scripts/example-report, line 12, change the word "recieved" to "received" in the usage text. Change no other line and no other file. / Check: python3 tests/test_example_report.py exits 0."
  - C2. Title: "Add the setting report.max_rows to the report script, its documentation and its tests". Body: "Repository /tmp/example ONLY. / Add the integer setting report.max_rows with the default value 50 to config/defaults.json. In scripts/example-report, read the setting and print at most that many rows; when the value is 0 or negative, print all rows. Add one row for the setting to the table of settings in docs/report.md. In tests/test_example_report.py add three tests: the default 50, the value 10, and the value 0. No other behaviour changes. / Check: python3 tests/test_example_report.py exits 0."
  - C3. Title: "Implement a session cookie for the existing login". Body: "Repository /tmp/example-web ONLY. / The login form at POST /login already checks the password with the existing function check_password in app/auth.py. After a successful login, set a session cookie named sid: a random value of 32 bytes from the Python secrets module, with the attributes HttpOnly, Secure, SameSite=Lax, Path=/ and Max-Age=86400. Store the value with the user ID and the expiry time in the existing table sessions (columns sid, user_id, expires_at). On each request, app/middleware.py looks up the cookie and sets request.user, or leaves request.user as None when the cookie is missing, unknown or expired. POST /logout deletes the row and clears the cookie. Add tests in tests/test_session_cookie.py for a login, a request with the cookie, an expired cookie and a logout. / Check: python3 -m pytest tests/test_session_cookie.py exits 0."
  - C4. Title: "Send one request to the Stripe API endpoint that creates a refund". Body: "Repository /tmp/example-shop ONLY. / Add the function create_refund(payment_intent_id, amount_cents) to app/payments.py. It sends one POST request to https://api.stripe.com/v1/refunds with the form fields payment_intent and amount, authenticated with the secret key read from the environment variable STRIPE_SECRET_KEY, which the deployment already sets; do not write the key to any file. On HTTP status 200 the function returns the refund ID from the JSON response; on any other status it raises RefundError with the status code. No retries. Add tests in tests/test_payments.py with a mocked HTTP client for the success case, a 402 response and a missing environment variable. / Check: python3 -m pytest tests/test_payments.py exits 0."
  - C5. Title: "Decide and implement how administrators authenticate to the admin area". Body: "Repository /tmp/example-web ONLY. / The admin area has no authentication today. Choose how administrators authenticate (for example a password with a second factor, single sign-on through the company identity provider, or client certificates), decide how sessions and account recovery work, and implement the chosen approach. The required behaviour is not decided yet; propose it on the card before you implement it."
  - C6. Title: "Install the updated plugin on every live Hermes profile". Body: "Repository /tmp/example-harness ONLY. / The plugin copy in plugins/example/ is reviewed and committed. On the live Hermes installation, run hermes -p <profile> plugins install for each of the 36 profiles listed in roster.yaml, then run hermes -p <profile> plugins list for each profile and check that the plugin is enabled. Restart the gateway afterwards. Record the commands and their exit status on the card."
  - In these bodies, " / " stands for a line break.

**Not established**

- How Jev classifies real cards with the proposed texts. Only six synthetic cards were sent, each twice. The variation of C4 between two identical requests shows that a card near the boundary between `easy` and `hard` can get either route.
- How the same six cards are classified with the three current criteria. They were not sent with them, to stay within 14 requests.
- Whether the probabilities change with the length of a real card body (up to `state_max_chars` 60000).

## 5. Readers of `glm_workers` and other ways of deciding that a profile is a GLM worker

**Answer** (source reading)

Code that reads the list `glm_workers` of `plugins/jev/config.json`:

| File and line | What the answer is used for | What option B (`glm_max_workers`) needs |
|---|---|---|
| `plugins/jev/routing.py` 323 to 326 (`decide`) | records `original_assignee` when the assignee is a Claude worker or a GLM worker | include the new list (affects the log record only) |
| `plugins/jev/routing.py` 390 to 391 (`decide`) | the worker pool of the applied route, read through the route's `assignee_from` | nothing; it reads `glm_max_workers` when `hard` names it. The rotation counter (lines 135 to 146, 407) must be kept per list (section 2) |
| `plugins/jev/routing.py` 723 and 733 (`handle_request_changes`) | moves a card to a Claude worker only when its assignee is in `glm_workers` | include the new list, or a `hard` card on `glm-3` is never moved to a Claude worker |
| `plugins/jev/peak_hold.py` 148 to 155 (`glm_workers_by_board`) and 158 to 159 (`all_glm_workers`) | the helper pair used by the six call sites below | read both lists here; this covers all six call sites |
| `plugins/jev/routing.py` 462 (`handle_create`, through `glm_workers_by_board`) | creates a card for a GLM worker as held inside the peak-hours window | covered by the helper |
| `plugins/jev/routing.py` 531 (`handle_unblock`, through `glm_workers_by_board`) | holds instead of unblocking inside the window | covered by the helper |
| `plugins/jev/routing.py` 582 (`handle_request_review`, through `all_glm_workers`) | clears the model override before the review | covered by the helper. Without it the reviewer run would start on `glm-5.3` and `zai` |
| `plugins/jev/peak_hold.py` 399 (`plan`) and 435 (`still_holdable`) | selects and rechecks the cards to hold | covered by the helper |
| `scripts/jev-peak-hold` 63 | default list of boards to check | covered by the helper |
| `scripts/jev-route-notice` 107 to 125 (`route_is_on`) | a route counts as on when the list named by its `assignee_from` is not empty | nothing; it reads the list named by `assignee_from` |

Code that decides by other means:

| File and line | How | Use | Option B |
|---|---|---|---|
| `scripts/jev-report` 104 and 362 to 387 | route names `easy` and `medium` in `route` records (`SAVINGS_ROUTES`) | Claude tokens saved | Part 5 adds `hard`; not a reader of the list |
| `scripts/jev-report` 215 to 221 (`model_family`) | model name contains `glm` | tokens by model family | nothing |
| `scripts/verify-state` 1057 to 1063 (`PROJECT_GLM_WORKER_POOLS`), 493 to 495 (`glm_worker_profiles`) | fixed profile names, three per board | model `glm-5.3` on `zai` (448 to 449), lifecycle and dispatch flags (498 to 512), `jev` plugin required (523), dispatch lists (813 to 816), allowed card assignees (1064 to 1067) | nothing; the `glm-3` profiles stay GLM workers. A check of `agent.reasoning_effort` would be new work |
| `scripts/verify-state` 198 to 206 (`glm_workers_of_board`) | roster fields `modes` `["project-isolated", <board>]` and provider `zai` | shared skill deploy lists (209 to 229) | nothing |
| `tests/test_glm_retirement_policy.py` 52 and `tests/test_second_worker_policy.py` 52 | name pattern `<prefix>-worker-glm-<digit>` with the prefix `jobcron`, `chapt`, `harness`, `jss` or `anki` | policy text checks | nothing |
| `tests/test_jev_routing.py` 320 to 328 and 517 to 530, `tests/test_third_glm_worker_policy.py` 274 to 287 | assert that `glm_workers` is exactly the three profiles of each board | configuration tests | these assertions change under option B |
| `tests/test_jev_policy_sources.py` 547 to 555, `tests/test_jev_routing_policy_text.py` 354 to 355 and 404 to 405 | assert policy text that names the three GLM workers and three routes | policy text tests | change together with the policy text (Part 5) |
| `skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py` 19 | names the retired profile `worker-glm-full` | lanes of the default board | not a board GLM worker; nothing |
| `scripts/switch-profile-model` 55 | target `glm` sets `glm-5.3` on `zai` | model switching | does not decide GLM worker status; nothing |

Policy text, not code: `procedures/jev-plugin.md` lines 233, 252, 253 and 287, the five orchestrator `SKILL.md` files and the GLM worker and reviewer `SOUL.md` files name `glm_workers` or the three GLM workers. They change with Part 5.

**Evidence**

- `grep -n -E 'glm_workers|glm-[0-9]|worker-glm|glm_|GLM_|-glm' plugins/jev/__init__.py plugins/jev/jev_log.py plugins/jev/peak_hold.py plugins/jev/tool_filter.py scripts/jev-peak-hold scripts/jev-report scripts/jev-route-notice scripts/switch-profile-model scripts/verify-state skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py` (55 lines).
- `grep -n 'glm_workers' tests/*.py`.
- `grep -rn 'glm_workers' procedures policies skills snapshots roster.yaml`.
- `grep -n 'glm_workers_by_board\|all_glm_workers\|board_cfg.get("glm_workers")\|assignee_from' plugins/jev/routing.py`.
- `roster.yaml` and `snapshots/sanitized-current-state.yaml` name the GLM profiles in profile lists only; no code reads a GLM list from them except through `scripts/verify-state` as listed.

**Not established**

- Readers outside the directories named by the card, for example the live plugin copies installed in the profiles. They were not read; they are copies of `plugins/jev/` once deployed.

## 6. Limit per route (Part 4)

**Answer**

How the code finds a card's `route` record today (source reading):
- `handle_request_changes` does not read the `route` record to decide; it uses the assignee and the count of `changes_requested` events from the board database.
- Only after deciding to move the card does it call `routed_claude_worker`. That function opens `decisions.jsonl` in the plugin log directory (`HERMES_JEV_LOG_DIR`, else `/Users/chanbla11mit/.hermes/jev/logs`) and skips lines that do not contain the task ID. It parses the others and keeps the last record with `event` `route`, the same `task_id` and `board`, and an `original_assignee` that is one of the board's Claude workers.

Observed records, board `harness`:
- 31 `route` records, one for each card.
- 9 have the field `applied_route`, of which 8 are non-null. 22 do not have the field.
- The records without the field run from 2026-11-13 11:13:14 to 2026-11-14 18:12:31.
- Every record since 2026-11-14 19:43:57 has the field. The field was added in the repository by commit `62e44b8` (card `t_92e29d10`, 2026-11-14 17:11:46). `jev_log.write` writes every field of its list, so a record from a plugin copy that has the field always carries the key.

What the code needs to use the limit of the card's applied route:
- A lookup of the card's latest `route` record that returns `applied_route`. It can share the file scan of `routed_claude_worker`, but must not depend on the `original_assignee` condition.
- A per-route setting `max_glm_change_requests` read from the route of that name in the board's `routes`.
- The general `routing.max_glm_change_requests` when no record or no per-route value is found.
- The `applied_route` and the limit used, added to the `escalate` record.

For a card without the field:
- Use `route` when `applied` is true. Before `t_92e29d10` the applied route was the route Jev chose. `scripts/jev-report` `report_route` uses the same fallback.
- Of the 22 harness records without the field, the 9 that moved a card to a GLM worker are `easy` (2) and `medium` (7). The fallback therefore gives the general value 5 for all of them.
- No `hard` card was sent to a GLM worker before the field existed, so no `hard` card lacks it.
- With option B, an assignee in `glm_max_workers` gives the same answer without reading the log; this is a second source for the limit.

**Evidence**

- Source reading: `plugins/jev/routing.py` lines 683 to 757 (`handle_request_changes`; the count at line 614; the call at line 740) and lines 619 to 639 (`routed_claude_worker`); `plugins/jev/jev_log.py` lines 18 to 41 (log directory) and lines 22 to 27 and 76 to 87 (every field written); `scripts/jev-report` lines 348 to 359 (`report_route`).
- Observed record: a Python script run with `/Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I` on `/Users/chanbla11mit/.hermes/jev/logs/decisions.jsonl`. It kept only records whose `board` is `harness` and printed counts and timestamps only. Results:
  - 46 harness records: 31 `route`, 13 `clear_override`, 1 `hold`, 1 `release`, 0 `escalate`;
  - `route` records with the field 9, without 22;
  - first record with the field 2026-11-14T19:43:57+09:00;
  - last record without the field 2026-11-14T18:12:31+09:00;
  - by day: 2026-11-13, 10 without; 2026-11-14, 12 without and 9 with;
  - records with the field: `medium` applied 4, `easy` applied 3, `hard` applied (card unchanged) 1, `below_threshold` 1;
  - records without the field: `hard` applied (unchanged) 8, `medium` applied to a GLM worker 7, `easy` applied to a GLM worker 2, `below_threshold` 5 (3 `medium`, 2 `hard`);
  - no card has more than one `route` record.
- `git log -S'applied_route' -- plugins/jev/routing.py` gives `62e44b8 2026-11-14 17:11:46 +0900`.

**Not established**

- When the plugin copy with `applied_route` was installed in the harness profiles. The first record with the field limits it to between 18:12:31 and 19:43:57 on 2026-11-14. The deployment record was not read.
- The same counts for the other four boards (outside this card).

## 7. Capacity of the Z.ai plan

**Answer**

- The `harness` Kanban database records no token counts. The `task_runs` table has no token column, and none of the 19 GLM worker runs (of 24) that have `metadata` has a token field in it.
- The `agent.log` files of the three harness GLM workers record one line for each model call, with input, output and cache read token counts. Observed sums for these three profiles:
  - 2026-11-13: 248 calls, 24,195,685 tokens in total (input 23,693,476, of which cache read 23,158,272; output 502,209).
  - 2026-11-14 up to 23:33: 621 calls, 48,102,782 tokens (input 47,546,127, of which cache read 46,467,712; output 556,655).
  - Earlier days with calls: 2026-10-14, 25,506 tokens; 2026-10-17, 11,180,998; 2026-10-18, 7,988,011; 2026-11-12, 39,479.
- Stops on the usage limit: 1 on 2026-11-13, at 24.2M tokens that day for these three profiles (section 3).
- Not available:
  - the plan's limit and the way Z.ai counts it (whether cache reads count, and the length of the window; the error response with code `1308` refers to a five-hour window);
  - whether the GLM workers of all five boards share one plan account;
  - the token use of the other twelve GLM workers;
  - therefore whether the plan can carry `hard` cards at `max` plus GLM review runs.

**Evidence**

- Observed record:
  - `PRAGMA table_info(task_runs)` (columns: id, task_id, profile, step_key, status, claim_lock, claim_expires, worker_pid, worker_started_at, max_runtime_seconds, last_heartbeat_at, started_at, ended_at, outcome, summary, metadata, error).
  - The key count of `metadata` over the 19 GLM worker runs that have it lists no token key.
  - `SELECT count(*) FROM task_runs WHERE profile LIKE 'harness-worker-glm-%'` returned 24.
- Observed record: `grep -E 'agent\.conversation_loop: API call #[0-9]+: model=glm' <agent.log> | cut -c1-300 | sed -E ...` for each of the three profiles, summed by date, profile and model with `awk` over the fields `in=`, `out=`, `total=` and `cache=`:
  - 2026-11-13: `glm-1`, `glm-5.3`: 226 calls, 23,238,701 total; `glm-1`, `glm-5.3-flash`: 22 calls, 956,984 total.
  - 2026-11-14: `glm-1`, `glm-5.3`: 300 calls, 27,331,985; `glm-2`, `glm-5.3`: 88 calls, 8,526,266; `glm-2`, `glm-5.3-flash`: 98 calls, 5,503,977; `glm-3`, `glm-5.3`: 112 calls, 5,933,672; `glm-3`, `glm-5.3-flash`: 23 calls, 806,882.
- The request file gives 56M on 2026-11-13 and 46M on 2026-11-14 up to 21:28 for GLM tokens per day. Those figures were not recomputed here and cover a set of profiles that the request file does not name.

**Not established**

- The plan's limit and how it is counted. The owner's Z.ai account page or Z.ai support would establish it.
- Whether the 24.2M on 2026-11-13 is close to the limit: the stop depends on the use of every profile on the same plan, and the other boards were not read.

## 8. Tokens at `max` compared with `high`

**Answer**

- The public page says that `glm-5.3` supports `low`, `high` and `max`, that the default is `max`, and that `max` is recommended for coding.
- The page reports one vendor benchmark (Z.ai Code Bench): at `max`, about 75K output tokens per task with a score of 34.5%; at `high`, about 50K output tokens per task with 31.4%. That is about 1.5 times the output tokens at `max` on that benchmark.
- A comment in the Hermes source records one probe prompt: 98 reasoning tokens at `high` and 125 at `max`.
- No measurement exists for the cards of these boards, and none was made on this card.
- By section 1, today's GLM runs probably already run at the server default `max`. If so, setting `max` explicitly would not change their token use, and setting `high` on the `easy` and `medium` workers would lower it.

**Evidence**

- Public page, https://docs.z.ai/guides/llm/glm-5.3:
  - the section "Feature Changes", table row `reasoning_effort` with values `low`, `high`, `max` and default `max`;
  - the sentence "For complex tasks such as coding, we recommend using max";
  - the paragraph on Z.ai Code Bench with "At Max effort, GLM-5.3 reaches 34.5% at roughly 75K output tokens per task" and "At High effort, GLM-5.3 reaches 31.4% at around 50K output tokens".
  - Fetched with `curl` on 2026-11-14 (HTTP 200, 367,187 bytes, SHA-256 `208cd9a2fa1282ed263943de6702fd1239880fa5661f77493ae968857aa15284`).
- Source reading: `agent/reasoning_effort.py` lines 75 to 77 (the probe figures `low=4, medium=11, high=98, max=125`, citing Hermes issue #91789).

**Not established**

- Token use per card at `max` compared with `high` on these boards. Two measurements would establish it:
  - the same synthetic cards run by one GLM profile with `agent.reasoning_effort: high` and then with `max`, in an isolated Hermes home, comparing the `out=` counts of the `agent.log` call lines;
  - after deployment of Part 3, the GLM tokens of `hard` cards compared with those of `medium` cards in `scripts/jev-report`.
- Whether the effort that runs use today is `max` (section 1, Not established).
