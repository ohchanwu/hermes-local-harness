# jev plugin: install, settings, peak-hours hold, logs and rollback

The `jev` plugin (`/Users/chanbla11mit/hermes-local-harness/plugins/jev`, version 0.1.0) calls Jev, the decision model from TypeSafe, for two decisions, and writes logs that show whether it reduces Claude subscription token use:

- Card model routing: when an orchestrator creates a card with `kanban_create`, the plugin asks Jev whether the work is `easy`, `medium` or `hard`, and moves `easy` and `medium` cards to the board's GLM worker profiles.
- Tool result filter: when `terminal`, `execute_code`, `search_files` or `browser_exec` returns a large result, the plugin keeps only the parts Jev marks as needed and saves the full result to a file.
- GLM peak-hours hold: no GLM card starts on Monday to Friday from 15:00 to 19:00 Asia/Seoul time.
- Logs of the routing decisions, the tool result filter and every auxiliary model call.

The plugin uses only the Hermes plugin interface (`register_middleware`, `register_hook`) and the Python standard library. It never changes the installed Hermes checkout `/Users/chanbla11mit/.hermes/hermes-agent`.

## Install on a profile

The live installation, the gateway restart and the LaunchAgent belong to the deployment card and need the owner's authorization. Install the plugin the same way as `hermes-terminal-outcome-notification` (see `procedures/hermes-terminal-outcome-notifications.md`), from the reviewed commit:

    hermes -p <profile> plugins install https://github.com/ohchanwu/hermes-local-harness.git#plugins/jev --ref <reviewed commit> --enable
    hermes -p <profile> plugins list --plain --no-bundled
    hermes plugins validate /Users/chanbla11mit/hermes-local-harness/plugins/jev

Plugins load only when they are listed in the profile's `plugins.enabled` (Hermes source `hermes_cli/plugins.py` line 1481), which `--enable` does.

Profiles:

- Every Claude subscription profile (orchestrators, workers, reviewers, `advisor`, the `chapt-*` roles). Routing and the `kanban_unblock` part of the peak-hours hold have an effect only in profiles that call `kanban_create` and `kanban_unblock` (the orchestrators); the auxiliary log and the tool result filter apply in every profile.
- The six GLM worker profiles that the routes use (`jobcron-worker-glm-1`, `jobcron-worker-glm-2`, `chapt-worker-glm-1`, `chapt-worker-glm-2`, `harness-worker-glm-1`, `harness-worker-glm-2`). The plugin must run in these profiles so that the card's model override is cleared at the review handoff (see "Model override at the review handoff").

Gateway-served sessions load the plugin after the owner runs `hermes gateway restart` from a separate shell. Workers started by the dispatcher load it when they start (`hermes -p <profile> --cli ... chat -q`).

## TypeSafe API key

The plugin reads the key from the environment variable `TYPESAFE_API_KEY` at each call. The owner adds one line that sets the variable `TYPESAFE_API_KEY` to `/Users/chanbla11mit/.hermes/.env`; nobody else writes, prints or copies the value. The value is never written to a log, a card, the repository or a chat message.

Without the key the plugin still loads: every routing decision is logged with `error_class` `MissingKey` and the card is created unchanged; the tool result filter leaves results unchanged.

## Configuration file

`plugins/jev/config.json` in the installed plugin directory is read on every call, so a changed value applies without a restart. Each of `routing`, `peak_hold`, `tool_results` and `auxiliary_log` turns off with `"enabled": false`.

| Setting | Value | Meaning |
|---|---|---|
| `jev.endpoint` | `https://api.typesafe.ai/v1/systemone` | TypeSafe endpoint (tests point it at a local fake server) |
| `jev.model` | `jev-1.14.0` | Jev model ID |
| `jev.timeout_seconds` | `5` | Timeout of every Jev call |
| `jev.api_key_env` | `TYPESAFE_API_KEY` | Name of the environment variable that holds the key |
| `kanban.home` | `/Users/chanbla11mit/.hermes` | Kanban root; board databases are `<home>/kanban/boards/<board>/kanban.db` (`HERMES_KANBAN_HOME` overrides) |
| `kanban.hermes_command` | `hermes` | Command used for `hermes kanban --board <board> ...` changes |
| `kanban.command_timeout_seconds` | `30` | Timeout of each `hermes kanban` command |
| `routing.enabled` | `true` | Card model routing on or off |
| `routing.threshold` | `0.6` | Minimum probability of the chosen route |
| `routing.state_max_chars` | `60000` | The card body is cut at this length before it is sent to Jev |
| `routing.question_instructions` | text | The Choice question sent to Jev |
| `routing.clear_override_at_review` | `true` | Clear the card's model override when a GLM worker requests review |
| `routing.known_models` | model IDs | Model IDs that are written to the log as given in `orchestrator_model`; any other `model` argument is logged as `unrecognized`. The models of the configured routes are always included |
| `routing.boards.<board>` | object | `implementation_workers`, `glm_workers`, `routes` |
| `peak_hold.enabled` | `true` | Peak-hours hold on or off in the configuration (the owner's switch file is the other condition) |
| `peak_hold.timezone` | `Asia/Seoul` | Time zone of the window |
| `peak_hold.weekdays` | `[0, 1, 2, 3, 4]` | Monday to Friday |
| `peak_hold.start`, `peak_hold.end` | `15:00`, `19:00` | Start inclusive, end exclusive |
| `peak_hold.marker` | `jev-peak-hold` | Text at the start of the `scheduled` reason of every held card |
| `tool_results.enabled` | `true` | Tool result filter on or off |
| `tool_results.tools` | `terminal`, `execute_code`, `search_files`, `browser_exec` | Tools whose results are filtered |
| `tool_results.min_chars`, `max_chars` | `8000`, `100000` | Output text length range that is filtered |
| `tool_results.chunk_lines`, `chunk_chars` | `40`, `2000` | Chunk size |
| `tool_results.args_chars` | `2000` | Tool arguments are cut at this length in the Jev state |
| `tool_results.keep_threshold` | `0.3` | Minimum probability for keeping a chunk |
| `tool_results.max_kept_ratio` | `0.8` | If the kept text is this share of the original or more, the result is unchanged |
| `auxiliary_log.enabled` | `true` | Auxiliary call log on or off |

## Routes and their criteria

For each `kanban_create` call the plugin sends Jev one Choice question. The state is the card title and the body cut at 60,000 characters; the options are the board's enabled routes with these criteria:

- `easy` (model `glm-5.3-flash`, provider `zai`, assignee from the board's `glm_workers`): very easy to easy work: a small, well-specified change in one or two files, a documentation or wording edit, or a mechanical change with an exact test.
- `medium` (model `glm-5.3`, provider `zai`, assignee from the board's `glm_workers`): a well-specified change across several files, or a change that needs reading surrounding code but no design decision.
- `hard` (no change: the Claude worker the orchestrator named, with that profile's own model): everything else, including design decisions, debugging without a known cause, security, payment, migration or deployment work.

The route is applied only when all three conditions hold: the orchestrator left `model` empty, the `assignee` is one of the board's `implementation_workers`, and the chosen route's probability is at least `threshold`. Otherwise the card is created exactly as the orchestrator asked. On `easy` or `medium` the plugin sets `assignee` to the next GLM worker of the board (the two alternate; the counter is in `<log dir>/routing-state.json`, which holds only board names and counters), sets `model` and `provider`, and replaces the profile name on a body line that starts with `Assigned worker EXACT `. The reviewer is not changed. Any Jev error, timeout, HTTP error, missing key or unexpected answer leaves the card unchanged.

| Board | Implementation workers | GLM workers | Enabled routes |
|---|---|---|---|
| `jobcron` | `jobcron-worker`, `jobcron-worker-2` | `jobcron-worker-glm-1`, `jobcron-worker-glm-2` | `easy`, `medium`, `hard` |
| `cha-pt` | `chapt-worker`, `chapt-worker-2` | `chapt-worker-glm-1`, `chapt-worker-glm-2` | `easy`, `medium`, `hard` |
| `harness` | `harness-worker`, `harness-worker-2` | `harness-worker-glm-1`, `harness-worker-glm-2` | `easy`, `medium`, `hard` |
| `jss-genr` | `jss-worker`, `jss-worker-2` | none | `hard` only (`easy`, `medium` present with `enabled: false`) |
| `anki` | `anki-worker`, `anki-worker-2` | none | `hard` only (`easy`, `medium` present with `enabled: false`) |

`jss-genr` and `anki` have no GLM worker profile. Their cards stay on Claude, and no Jev call is made for them, until GLM worker profiles exist and the two routes are enabled.

### Model override at the review handoff

The dispatcher passes a card's `model` and `provider` override to every run of the card, including the reviewer's run (Hermes source `hermes_cli/kanban_db_dispatch.py` lines 2761 to 2766). Without a correction the Claude reviewer would start with a GLM model and the `zai` provider. Therefore, when a GLM worker profile calls `kanban_request_review`, the plugin first runs `hermes kanban --board <board> set-model <task id> none`, and then lets the review request run. Consequence: if the reviewer requests changes, the rework runs on the GLM worker profile's own model (`glm-5.3`), also for a card that started on the `easy` route with `glm-5.3-flash`.

## GLM peak-hours hold

Z.ai charges double on Monday to Friday from 15:00 to 19:00 Asia/Seoul time. In that window no card assigned to a GLM worker profile listed in `config.json` may be claimed by the dispatcher. A GLM run that started before 15:00 continues. Claude cards (the `hard` route) are never held.

How a card is held: it is moved to the Kanban `scheduled` status with the reason `jev-peak-hold until <date>T19:00:00+09:00`. Hermes sends no gateway notification for the `scheduled` event, and the `unblocked` event at release has no notification text and does not wake the orchestrator. A `blocked` status would wake the orchestrator for every hold, so it is not used except as the creation status below.

Holds and releases:

- `kanban_unblock` middleware (the usual path). Orchestrator Card Setup creates every card with `initial_status: blocked` and unblocks it with the `kanban_unblock` tool when setup is complete. Inside the window, when the card is `blocked` and assigned to a GLM worker of a configured board, the middleware runs `hermes kanban --board <board> schedule <id> "jev-peak-hold until ..."` instead of the unblock. Hermes accepts `schedule` for a `blocked` card, so the card goes from `blocked` directly to `scheduled` and is never `ready` inside the window. The tool result returned to the orchestrator has `status` `scheduled`, `held_until` and a note that says the card was not unblocked and how it is released. A card that is already held with the marker stays held. If the schedule command fails, the unblock runs unchanged and the script below holds the card. `kanban_unblock` is an orchestrator tool (Hermes refuses it when `HERMES_KANBAN_TASK` is set), so the `hermes kanban schedule` command works in that session. An unblock with the command line `hermes kanban unblock` instead of the tool is not seen by the middleware.
- `kanban_create` middleware. A card that ends up assigned to a GLM worker and that the caller did not create `blocked` or in triage is created with `initial_status: blocked` (the orchestrator's subscription is created after that event, so it is not delivered) and is then moved to `scheduled` with the marker. This is used only when all of the following are true, because only then can the plugin be sure the card is new and that both Kanban commands work: the call has no `idempotency_key` (Hermes returns the existing card for a known key), the session is not a dispatcher-started worker session (`HERMES_KANBAN_TASK` is not set; there `hermes kanban schedule` and `hermes kanban unblock` refuse every other card), the `hermes` command resolves to an executable, and the `kanban_create` result reports the card as `blocked`. In every other case the card is created exactly as requested and the script holds it on its next run. If the schedule command fails, the plugin runs `hermes kanban --board <board> unblock <id>` and the script holds the card on its next run. If that unblock also fails, the card stays `blocked` without the marker: the script does not release it, Hermes sends no notification for it, and the `hold` record has both error classes in `error_class` (for example `CommandFailed+CommandFailed`); find such cards with the `hold` records that have `applied` `false`.
- `scripts/jev-peak-hold --apply` (the other paths). It holds every `ready` or `todo` card of a GLM worker inside the window: cards already `ready` or `todo` at 15:00, cards created as requested in the cases above, cards returned to a GLM worker by a reviewer, cards retried after a crash, and cards unblocked with the command line.
- Release: the first `scripts/jev-peak-hold --apply` run at or after 19:00 runs `hermes kanban --board <board> unblock <id>` for every `scheduled` card whose latest `scheduled` reason starts with the marker. Hermes returns the card to `ready`, or to `todo` while a parent is open. Other `scheduled` or `blocked` cards are never released. A held card that is reassigned to a non-GLM profile is released on the next run.

`scripts/jev-peak-hold` (Python standard library; it runs under `/usr/bin/python3` and under `python3` from Homebrew):

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold              # prints planned holds and releases only
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply      # performs them
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --now 2026-11-11T16:00:00+09:00   # time for tests

`--kanban-db <path>` with one `--board <name>`, `--config <path>` and `--hermes <command>` exist for tests. Running it twice changes nothing the second time. It reads each board database with a SQLite connection that has `PRAGMA query_only` set, which works for a WAL-mode database that has no `-wal` and `-shm` files with the older SQLite in `/usr/bin/python3`. A board database that cannot be read is reported as `failed read <board> error_class=<class>` (with `--apply` also as a `decisions` record with `event` `read_error`), the other boards are still processed, and the script exits with status 1. A failed hold or release also gives exit status 1. The script reads the repository copy `/Users/chanbla11mit/hermes-local-harness/plugins/jev/config.json` unless `--config` names another file, while the middleware reads the copy installed in each profile; keep the `peak_hold` and `routing.boards` sections of the two copies the same.

Schedule: a LaunchAgent with label `com.nous.hermes-jev-peak-hold` runs `/usr/bin/python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply` every 10 seconds (`StartInterval` 10), with the directory of the `hermes` executable in its `PATH` (the default `PATH` of launchd does not contain `/opt/homebrew/bin`). The deployment card installs it with the owner's authorization. Outside the window each run only releases cards held with the marker, so one schedule serves both holding and releasing. A run that finds nothing to do only reads the board databases.

Remaining race between a dispatcher tick and the script:

- No race for a card unblocked with the `kanban_unblock` tool inside the window (orchestrator Card Setup step 5) and for a card held at creation: the card goes from `blocked` to `scheduled` and is never `ready`.
- A race for every card that becomes `ready` for a GLM worker inside the window by another path (listed under `scripts/jev-peak-hold --apply` above, and the fallbacks when a schedule command fails). The dispatcher claims `ready` cards once per `kanban.dispatch_interval_seconds` (default 60 seconds; Hermes source `gateway/kanban_watchers_dispatcher.py` line 50, read once when the gateway starts), and the script runs every 10 seconds. Such a card is claimed by the dispatcher before the next script run when a dispatcher tick comes first, which is about one card in six (10 of 60 seconds) on average. A GLM run started that way continues. The same applies at 15:00 to cards that were already `ready`.
- Release happens up to 10 seconds after 19:00.

Every hold and every release writes one `decisions` record (`event` `hold` or `release`, `held_until`).

## Turning the peak-hours hold off and on

The owner can turn the hold off in an emergency and back on, without reinstalling the plugin, editing `config.json` or restarting the gateway. The switch is the file `/Users/chanbla11mit/.hermes/jev/peak-hold.json` (mode 0600; content `enabled`, `changed_at`, `changed_by`). An absent file means on. A file that cannot be read is treated as on and logged with its `error_class`. The middleware and the script read it on every call; the hold is active only when both `peak_hold.enabled` in `config.json` and the switch are true.

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off      # turn off and release every held card at once
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold on       # turn on; cards are held again from the next run inside the window
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold status   # on or off, when and by whom, number of held cards

`off` and `on` are idempotent. Each change writes one `decisions` record with `event` `toggle` and the new value in `enabled`. `--by <name>` sets `changed_by` (default: `HERMES_PROFILE`, then the login name).

## Tool result filter

The `transform_tool_result` hook calls `plugins/jev/tool_filter.py` (written by a parallel card). It acts only on `terminal`, `execute_code`, `search_files` and `browser_exec`, and only when the output text is longer than 8,000 and at most 100,000 characters. It never changes `read_file` or `kanban_*` results. It saves the full output under `<HERMES_HOME>/cache/jev` with mode 0600 before changing anything, splits the output into chunks of 40 lines (at most 2,000 characters), asks Jev one yes-or-no question per chunk, keeps the first chunk, the last chunk and every chunk with probability 0.3 or more, and replaces each run of removed chunks with one line that gives the number of removed lines and the saved file path. If the kept text is 80% of the original or more, or the format is not recognised, or anything fails, the result is unchanged. A later `read_file` of a saved file writes a `saved_read` record.

## Logs and report

Logs are JSON Lines files in `/Users/chanbla11mit/.hermes/jev/logs` (one directory for every profile; `HERMES_JEV_LOG_DIR` overrides it in tests), files mode 0600, directory mode 0700. Every record has `ts` (ISO 8601 with offset) and `profile`; unknown values are `null`. Records contain identifiers, sizes, probabilities, timings and token counts only, never card text or tool output.

- `decisions.jsonl`: `event` (`route`, `hold`, `release`, `toggle`, `clear_override`, `switch_error`, `read_error`), `board`, `task_id`, `original_assignee`, `new_assignee`, `orchestrator_model`, `route`, `probabilities`, `confidence`, `applied`, `not_applied_reason` (`routing_disabled`, `board_not_configured`, `single_route`, `jev_error`, `model_set`, `assignee_not_listed`, `below_threshold`, `no_glm_workers`, `create_failed`, `plugin_error`, `task_id_not_recognized`), `jev_latency_ms`, `jev_input_tokens`, `error_class`, `held_until`. A `toggle` record also has `enabled` and `changed_by`. A board name or assignee that is not in the configuration is logged as `null`, a `model` argument that is not in `routing.known_models` or a route as `unrecognized`, and a task ID from tool arguments that does not have the Hermes form `t_<hexadecimal digits>` as `null`.
- `tool_results.jsonl`: `event` (`filter`, `saved_read`), `session_id`, `tool`, `chars_before`, `chars_after`, `chunks_kept`, `chunks_total`, `jev_latency_ms`, `jev_input_tokens`, `action` (`filtered`, `unchanged`, `skipped`), `reason`, `error_class`, `saved_file`.
- `auxiliary.jsonl`: `aux_task`, `provider`, `model`, `input_tokens` (input plus cache read and cache write tokens), `output_tokens`, `status` (`ok`, `error`, `streaming`).

`scripts/jev-report` (written by a parallel card) reads these logs and the Kanban run history and prints the results per route, per tool and per auxiliary task, and the total Jev input tokens and cost.

## Rollback

1. Turn off a single part at once: set its `enabled` to `false` in the installed `config.json`. For the peak-hours hold, `python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off` is enough.
2. Remove the plugin from a profile: `hermes -p <profile> plugins disable jev` on each profile, then the owner runs `hermes gateway restart` from a separate shell so gateway-served sessions drop it.
3. Before or after step 2, run `python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off` so no card stays held, and remove the `com.nous.hermes-jev-peak-hold` LaunchAgent.
4. Cards already created on a GLM route keep their assignee and model override; reassign them with `hermes kanban --board <board> assign <id> <profile>` and `hermes kanban --board <board> set-model <id> none` if needed.
5. Keep or archive `/Users/chanbla11mit/.hermes/jev/logs` for the report.
