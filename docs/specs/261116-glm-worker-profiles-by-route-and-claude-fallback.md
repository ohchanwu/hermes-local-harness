# Six GLM worker profiles per board by route, and the Claude subscription fallback of the GLM profiles

Card: `t_6957cef4` (board `harness`). Date: 2026-11-16 (Asia/Seoul, UTC+09:00).
Repository baseline: `e7d7583f02e669a4bf79896c1e169ebb31d6b77f`.
Installed Hermes read for this specification: `/Users/chanbla11mit/.hermes/hermes-agent` at commit `9cf7960f27` (`git -C /Users/chanbla11mit/.hermes/hermes-agent rev-parse --short HEAD`).

This file is a specification only. Its card changed no live file, no profile, no board and no other repository file. Every live fact below was read with read-only commands. No `.env`, `auth.json` or token file value was read: `.env` files were checked only with `grep -c '^NAME='`.

Line numbers of Hermes files refer to commit `9cf7960f27`. Line numbers of repository files refer to the baseline commit.

Revision after review round 1 (change request of `harness-reviewer` on card `t_6957cef4`): the order of the live deployment changed in section 2, in R4, in steps D1, D2, D6, D7, D8 and D10, in the new step D2a, and in open question Q5. The old names stay in the dispatch list until their runs finish. The wait covers the cards in review that have an old implementer. After the rename, step D2a moves the cards that are still assigned to an old name.

## 1. Owner decisions that this specification implements

The owner sent these decisions to `harness-orchestrator` in Telegram direct messages on 2026-11-16 (text of card `t_6957cef4`):

1. When the Z.ai subscription quota runs out, the GLM reviewers and the full GLM workers fall back to Claude Sonnet, and the GLM Flash workers fall back to Claude Haiku.
2. One GLM worker profile runs one route, because Hermes has one `fallback_providers` list per profile.
3. Each board gets six GLM worker profiles, named `<board prefix>-worker-glm-easy-1`, `-easy-2`, `-medium-1`, `-medium-2`, `-hard-1` and `-hard-2`. `hermes profile rename` renames the three existing profiles: `glm-1` becomes `glm-easy-1`, `glm-2` becomes `glm-medium-1` and `glm-3` becomes `glm-hard-1`. Copies create the other three. This applies to all five boards: `harness`, `cha-pt`, `jobcron`, `jss-genr` and `anki`. The owner runs the Z.ai login commands.
4. The owner approves adding the two path settings of the `claude-subscription` provider to the `.env` files of the GLM profiles.
5. The owner approves deploying the updated harness-orchestrator skill.

Fallback target for each profile. The `anthropic` provider is never used, because it is a paid Console key.

| Profiles | `fallback_providers` |
|---|---|
| `<prefix>-worker-glm-easy-1`, `<prefix>-worker-glm-easy-2` | `[{provider: claude-subscription, model: claude-haiku-5-5}]` |
| `<prefix>-worker-glm-medium-1`, `-medium-2`, `-hard-1`, `-hard-2` | `[{provider: claude-subscription, model: claude-sonnet-5-5}]` |
| the five `<prefix>-reviewer-glm` | `[{provider: claude-subscription, model: claude-sonnet-5-5}]` |

Board names and profile prefixes: board `harness`, prefix `harness`; board `cha-pt`, prefix `chapt`; board `jobcron`, prefix `jobcron`; board `jss-genr`, prefix `jss`; board `anki`, prefix `anki` (`plugins/jev/config.json` lines 25 to 101, `scripts/verify-state` lines 1109 to 1113).

### Names after the change (30 GLM worker profiles)

| Old name (renamed) | New name | Copy made from the renamed profile |
|---|---|---|
| `<prefix>-worker-glm-1` | `<prefix>-worker-glm-easy-1` | `<prefix>-worker-glm-easy-2` |
| `<prefix>-worker-glm-2` | `<prefix>-worker-glm-medium-1` | `<prefix>-worker-glm-medium-2` |
| `<prefix>-worker-glm-3` | `<prefix>-worker-glm-hard-1` | `<prefix>-worker-glm-hard-2` |

The five GLM reviewers keep their names: `jobcron-reviewer-glm`, `chapt-reviewer-glm`, `harness-reviewer-glm`, `jss-reviewer-glm` and `anki-reviewer-glm`.

### Work in progress that this specification builds on

- Card `t_17149680` adds `claude-sonnet-5-5` (context length 1000000) to `MODELS` of `plugins/model-providers/claude-subscription/compat.py`. When this specification was written, the card was in review by `harness-reviewer`: commit `98be7b2b7b42f8a2d289754c77e3f2e555c5fd23`, and the GLM review had no findings. At the baseline, `MODELS` has `claude-opus-5-5`, `claude-fable-5-1`, `claude-fable-5-2` and `claude-haiku-5-5` (`compat.py` lines 25 to 28).
- Card `t_cf518fd0` adds the lists `easy_route_workers` (the first entry of `glm_workers`) and `medium_route_workers` (the second entry) to each board of `plugins/jev/config.json`, and points route `easy` at the first list and route `medium` at the second. When this specification was written, the card was running on `harness-worker-glm-1` (run 537, model override `glm-5.3`). Card R1 below extends both lists to two workers each, and puts two workers into `glm_max_workers`.

### Decisions this specification makes for the cards below

- `easy_route_workers` = [`<prefix>-worker-glm-easy-1`, `<prefix>-worker-glm-easy-2`]; `medium_route_workers` = [`<prefix>-worker-glm-medium-1`, `<prefix>-worker-glm-medium-2`]; `glm_max_workers` = [`<prefix>-worker-glm-hard-1`, `<prefix>-worker-glm-hard-2`]. `glm_workers` names the four easy and medium workers in that order. No route reads `glm_workers` after card `t_cf518fd0`. `peak_hold.glm_workers_by_board` reads it first, and then every list that a route names (`plugins/jev/peak_hold.py` lines 170 to 209).
- Order of the 30 GLM worker names in `kanban.dispatch_profiles`. They follow the 20 names that stay: the 15 Claude profiles and the five GLM reviewers, in their present order. Boards go in the order `jobcron`, `chapt`, `harness`, `jss`, `anki`. Within each board the order is `easy-1`, `easy-2`, `medium-1`, `medium-2`, `hard-1`, `hard-2`. Card R1 writes this order into `snapshots/sanitized-current-state.yaml`, and live step D6 adds the names in this order. `scripts/verify-state` compares the whole list, including the order (`procedures/jev-plugin.md` line 173).
- The routing state file needs no change. `/Users/chanbla11mit/.hermes/jev/logs/routing-state.json` holds only board names, list names, route names and counters (`plugins/jev/routing.py` lines 114 to 125). It contains no profile name: `grep -c -E 'worker-glm-[0-9]'` returned 0. On 2026-11-16 its `counters` were `{"jobcron": 0, "harness": 1, "jss-genr": 0, "jss-genr:glm_max_workers": 0, "harness:glm_max_workers": 0}`. The alternation index of a list is taken modulo the length of the list (`routing.py` lines 143 to 167), so a list that grows from one to two workers needs no reset.

## 2. `hermes profile rename` in installed Hermes

The command `hermes profile rename <old> <new>` calls `_profile_rename` (`hermes_cli/profile_cmd.py` lines 437 to 446, table entry line 616), which calls `rename_profile` (`hermes_cli/profiles.py` lines 2446 to 2546).

### What it does

- It refuses an unknown old profile and an existing target (lines 2462 to 2465). It also refuses the name `default` as a target (line 2458).
- It removes the gateway service of the old name and stops that profile's own gateway, if one runs (lines 2471 to 2476). The GLM profiles have no service of their own. `launchctl list` shows only `ai.hermes.gateway`, `com.nous.hermes-jev-peak-hold` and `com.nous.hermes-terminal-outcome-notification` (read on 2026-11-16).
- A live default multiplexer counts as a live gateway (`_live_default_multiplexer`, lines 1545 to 1552): the gateway has recorded `served_profiles`. In that case `rename_profile` marks the old directory as deleted and tells the multiplexer to stop serving the old name before the move (lines 2484 to 2487). Read on 2026-11-16: `/Users/chanbla11mit/.hermes/gateway_state.json` has `served_profiles` with 53 names, among them all 15 GLM workers and all five GLM reviewers (and the retired `worker-glm-full`). The gateway is pid 82868, and that process also holds the dispatcher lock of the running cards. So during the deployment the rename takes the multiplexer path.
- It moves the whole directory with one `rename` (line 2499). Everything inside the profile directory therefore moves with it: `auth.json` (the credential pool with the Z.ai login), `.env`, `config.yaml`, `SOUL.md`, `skills/`, `plugins/` (with `jev` and, on the anki profiles, `model-providers/claude-subscription`), `memories/`, `sessions/`, `state.db`, `cron/`, `logs/` and `shell-hooks-allowlist.json` where one exists. The allowlist path is `get_hermes_home() / "shell-hooks-allowlist.json"` (`agent/shell_hooks.py` lines 39 and 517 to 519), so the file follows the directory. No GLM worker has that file; `harness-reviewer-glm` has one, and it is not renamed.
- It records the old name in `previous_names` of the profile's `profile.yaml` (lines 2431 to 2443 and 2517). It updates Honcho host blocks (line 2520). It removes the old wrapper script and creates one for the new name, unless the alias collides (lines 2523 to 2529). It moves `active_profile` if that pointed to the old name (line 2532).
- It migrates the session and routing identity, `_migrate_profile_identity` (line 2538; `hermes_cli/profile_identity.py` lines 185 to 235). With a live multiplexer, the gateway's control verb `migrate-profile-identity` does the migration (lines 195 to 215). When that fails, the command prints `⚠ Profile was renamed, but the live gateway could not migrate session identity ... Restart the gateway, then run: hermes profile migrate-identity <old> <new>` and returns without migrating. Without a live multiplexer, the command itself rewrites `/Users/chanbla11mit/.hermes/state.db` and the new profile's `state.db` (lines 218 to 235). The rewrite (`hermes_state_gateway.py` `rekey_profile_state`, lines 624 onward) changes `sessions.profile_name`, `sessions.session_key` (`agent:<old>:` to `agent:<new>:`), `sessions.origin_json` `profile`, `gateway_heartbeats.profile`, the `delivery_obligations` columns and the Telegram topic tables.
- Last, it tells the multiplexer to serve the new name, and registers a gateway service when one was registered (lines 2540 to 2543).

### What it does not update

- Kanban: `rename_profile` makes no Kanban call. Of the files that contain "rename", the only Kanban files are about boards and logs (`hermes_cli/kanban_boards.py` line 137, `hermes_cli/kanban_db_dispatch.py` lines 2486 to 2487). So these keep the old name: `tasks.assignee` of every card, `task_runs.profile` (run history, `kanban_db_connect.py` line 1033), the payloads of `task_events`, and `kanban_notify_subs.notifier_profile` (notification subscriptions, `kanban_db_connect.py` lines 1045 to 1049 and 844). A card that is still assigned to an old name becomes a card the dispatcher cannot start: `profile_exists(assignee)` is false, so the dispatcher records `skipped_nonspawnable` (`kanban_db_dispatch.py` lines 2049 to 2064).
- `kanban.dispatch_profiles` in `/Users/chanbla11mit/.hermes/config.yaml`. The dispatcher claims a card only for a name that is in that list and whose profile exists (`kanban_db_dispatch.py` lines 1686 to 1690 and 1696 to 1740). On 2026-11-16 the list has 35 names, including the 15 GLM workers and the five GLM reviewers, and `max_in_progress_per_profile` is 1.
- Cron jobs: their prompts and targets are not rewritten. The 15 GLM worker profiles have no `cron/jobs.json` (read on 2026-11-16). One other file names GLM workers: `/Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/cron/jobs.json`, job `94d7b3d1dc19` "Jobcron emergency autonomous deployment controller", with `enabled` false. Its `prompt` names `jobcron-worker-glm-1` and `jobcron-worker-glm-2`. See open question Q4.
- The text inside moved files. For example, a `SOUL.md` that names the profile's own name keeps the old name. Live steps D2 and D3 replace the SOUL files.
- The `jev` plugin configuration in every profile, `roster.yaml`, `snapshots/sanitized-current-state.yaml`, and the `jev` logs.

### Whether it refuses while a worker of the profile runs

It does not. `rename_profile` checks only the profile's gateway and the multiplexer (lines 2471 to 2487). It has no check for a running Kanban worker or any other process whose `HERMES_HOME` is the old directory. `hermes_cli/profiles.py` contains no "worker"/"running agent"/"in use" check in the rename path: the grep for these words gave only line 2139, which is about profile resolution. A worker that runs during the move keeps a working directory and open files under the old path. The deployment must therefore wait until no run is running on any of the 15 old names, and until no card in `review` has one of them as its implementer (step D1). Cards that are still assigned to an old name after the rename are moved to the new name (step D2a). A wait for zero assigned cards could not end (step D1 gives the reason).

### Whether the gateway must restart

Not when the multiplexer accepts the control verb: the rename itself stops serving the old name and starts serving the new one (lines 2484 to 2487 and 2541 to 2542). A restart is needed only when the command prints the warning quoted above. In that case the restart comes before `hermes profile migrate-identity <old> <new>`. Do not restart the gateway while any Kanban worker runs, because the dispatcher runs in that gateway process (dispatcher lock `Chanwus-MacBook-Pro-2.local:82868`) (see `docs/bugs/261116-kanban-dispatcher-marks-live-worker-crashed.md`).

## 3. Repository inventory of the profile names

`git grep -l "worker-glm-" e7d7583f02e669a4bf79896c1e169ebb31d6b77f -- .` lists 133 files. Each one is named in section 8 together with the card that changes it, or with the reason it stays unchanged. There are three kinds of line:

- lines that name a GLM worker of a board (`<prefix>-worker-glm-<number>`);
- lines that name only the retired generic profile `worker-glm-full`. That profile stays retired, and its name does not change (`scripts/verify-state` lines 361 to 365);
- template lines, for example `` f"{prefix}-worker-glm-{number}" `` in tests, or `<prefix>-worker-glm-3` in prose.

Places that the card text names but that contain no literal GLM worker name:

- `scripts/jev-peak-hold`, `scripts/jev-report`, `scripts/jev-route-notice` and the code of `plugins/jev/*.py` read the worker names from `plugins/jev/config.json` (for example `scripts/jev-peak-hold` line 93, `peak_hold.glm_workers_by_board`). `grep -n "worker-glm"` on these scripts matched no profile name.
- `scripts/switch-profile-model` names no GLM worker. It is the tool of live steps D6 and D7 (`--to glm`, `--dispatch add|remove`, `--apply-fallbacks`; lines 5 to 24, 101 to 125 and 142 to 188).

Places that name GLM workers in the baseline and must change for the rename and the new profiles:

- `roster.yaml`, 50 name strings: `glm_worker_reasoning_effort_settings.profiles` (5, lines 106 to 112, the `-3` profiles at `agent.reasoning_effort` `max`); `approval_policy.profiles` (15, lines 162 to 184); `profiles[].name` (15 entries, lines 2852 to 3786, each with `model` `glm-5.3`, `provider` `zai`, `lifecycle` `project-active`, `concurrency_limit` 1, `required_plugins` [`jev`]); `project_dispatch_allowlist` (15, lines 4032 to 4046).
- `snapshots/sanitized-current-state.yaml`, 96 name strings: `profiles` (15), `approvals.profiles` (15), `kanban.dispatch_profiles` (15), and `skill.shared_skills[].deploy_profiles` (51): `minimal-implementation` 15, `simplification-review` 15, `production-deployment-planning` 9, `production-deployment` 6, `human-deployment-guide-writing` 6.
- `scripts/verify-state`: `PROJECT_GLM_WORKER_POOLS` (lines 1103 to 1114), which `glm_worker_profiles` (line 501) and `check_glm_worker_profiles` (line 506) read; the comment at line 2321.
- `plugins/jev/config.json`: `glm_workers`, `glm_max_workers` and `glm_reviewers` of the five boards (lines 27 to 29, 45 to 47, 63 to 65, 81 to 83 and 99 to 101).
- `policies/profile-souls/`: the SOUL sources of 12 GLM workers (`anki`, `chapt`, `harness` and `jss`, `-glm-1` to `-glm-3`). The jobcron GLM workers have no tracked SOUL; `procedures/jev-plugin.md` line 99 gives the `sed` method. Also the five GLM reviewer SOULs, the five Opus reviewer SOULs and the five orchestrator SOULs.
- `policies/profile-skills/<board>-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` of the five orchestrators.
- `procedures/jev-plugin.md` (30 lines), `procedures/switching-hermes-models.md` line 15, and `docs/README.md` line 17 (the declared profiles of `human-deployment-guide-writing`).
- `tests/gen_fixtures.py` (lines 217, 218 and 267) and the 40 fixtures under `tests/fixtures/` that it generates from `tests/fixtures/clean.yaml` (`tests/gen_fixtures.py` lines 6 to 9). There are 46 files in `tests/fixtures/`; 40 of them name a GLM worker.
- 38 other Python files under `tests/` (section 8). Three of them, `tests/hard_route_policy_edits.py`, `tests/jss_download_install_edits.py` and `tests/orchestrator_glm_review_edits.py`, reverse the edits of earlier cards so that tests can compare a policy source with an earlier reviewed version (for example `tests/hard_route_policy_edits.py` lines 2 to 6). Their text records the earlier edits and stays as written.

Files that stay as written because they are history: `docs/bugs/`, `docs/decisions/`, `docs/plans/`, `docs/specs/`, `docs/state/` and `spikes/glm-reviewer-pass/`. These record what happened under the names of the time. The same holds for `docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md`.

## 4. Live state to change (read on 2026-11-16, read only)

### The 20 GLM profiles

From `/Users/chanbla11mit/.hermes/profiles/<profile>/config.yaml`, key values only:

- 15 GLM workers. `model.default` is `glm-5.3`, `model.provider` is `zai`, `plugins.enabled` is [`jev`], and every helper task under `auxiliary` has target `zai`/`glm-5.3`. `agent.reasoning_effort` is `high` on `-glm-1` and `-glm-2` and `max` on `-glm-3`. `fallback_providers` is absent on the `-glm-1` and `-glm-2` profiles of `harness`, `chapt`, `jobcron` and `jss`, and `[]` on the other seven. No `auxiliary.<task>.fallback_chain` has an entry.
- Five GLM reviewers. Same model and provider, `agent.reasoning_effort` `max`, `fallback_providers` `[]`, and a `pre_tool_call` hook (for `harness-reviewer-glm`, `config.yaml` lines 142 to 146: matcher `kanban_complete|kanban_request_review`, command `/Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/agent-hooks/jev-glm-reviewer-hook`, `fail_closed` true). Each reviewer's `config.yaml` has one line with its own name (the hook command path). The reviewers are not renamed.
- All 20 have `auth.json`, `.env` and `state.db`. Only the four anki profiles (`anki-worker-glm-1` to `-3` and `anki-reviewer-glm`) have `plugins/model-providers/claude-subscription` and the three `claude-subscription` settings in `.env`. The other 16 have only `plugins/jev`. No worker `config.yaml` contains its own name.

### `.env` settings that the `claude-subscription` provider reads

- `HERMES_CLAUDE_SUBSCRIPTION_CLI`: required. It is the absolute path of the provider's dedicated Claude CLI install (`compat.py` line 49; `client.py` lines 147 and 320 to 322, which reject a missing or relative path). The process list on 2026-11-16 shows the dedicated CLI at `/Users/chanbla11mit/.hermes/runtimes/claude-code/2.1.302/claude`; `procedures/haiku-helper-routing.md` line 177 names CLI 2.1.302.
- `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE`: the path of an owner-only (0600) token file. Background Hermes processes cannot read a locked Keychain, so this is the path the Kanban workers use (`compat.py` line 45; `client.py` lines 331 to 340).
- `HERMES_CLAUDE_SUBSCRIPTION_EFFORT`: optional. One of `low`, `medium`, `high`, `xhigh`, `max`; the default is `medium` (`compat.py` lines 37 to 39; `client.py` line 270). This is not a path; see open question Q2.

Setting names checked with `grep -c '^NAME='` (no value read):

| Setting | `anki-worker-glm-2/.env` | `harness-worker/.env` |
|---|---|---|
| `HERMES_CLAUDE_SUBSCRIPTION_CLI` | 1 | 1 |
| `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` | 1 | 1 |
| `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` | 1 | 1 |
| `ANTHROPIC_API_KEY` | 0 | 1 |
| `ZAI_API_KEY` | 0 | 0 |

The Z.ai login is in `auth.json`, not in `.env`. The provider needs no Anthropic key. It must not get one: `harness-worker` has `ANTHROPIC_API_KEY` and `fallback_providers` `[{provider: anthropic, model: claude-opus-5-5}]`, and that is exactly the paid path the owner excludes for the GLM profiles.

### Plugin copies

`claude-subscription` is a user model provider plugin. Hermes loads it from `$HERMES_HOME/plugins/model-providers/<name>/` (`providers/__init__.py` lines 6, 298 to 302 and 362). A profile without that directory cannot resolve the provider, so its fallback entry would be skipped as "provider not configured" (`agent/chat_completion_helpers.py` lines 2112 to 2115). On 2026-11-16, 25 profiles have the copy. The `compat.py` of `harness-worker`, of `anki-worker-glm-1` and of the repository have the same SHA-256, `f6478cb12d573d7d0834ba367a1afc85649adf26b3f30bd0e5425039e895afe5` (the baseline `MODELS`, without Sonnet). `scripts/verify-state` checks no hash of these copies: `grep -n model-providers` gives only the allowlist reader at lines 732 to 739. 41 profiles have `plugins/jev`.

### `kanban.dispatch_profiles` (`/Users/chanbla11mit/.hermes/config.yaml`)

The list has 35 names, in this order: `jobcron-worker`, `jobcron-reviewer`, `chapt-worker`, `chapt-reviewer`, `harness-worker`, `harness-reviewer`, `jss-worker`, `jss-reviewer`, `harness-worker-2`, `chapt-worker-2`, `jobcron-worker-2`, `jss-worker-2`, `anki-worker`, `anki-worker-2`, `anki-reviewer`, then the ten `-glm-1` and `-glm-2` profiles (jobcron, chapt, harness, jss, anki), then the five `-glm-3` profiles (harness, chapt, jobcron, jss, anki), then the five GLM reviewers (jobcron, chapt, harness, jss, anki). The other kanban settings: `review_dispatch` true, `orchestrator_profile` `default`, `max_in_progress_per_profile` 1, `auto_decompose` false.

### `jev` logs and how the rules read old names

The log directory is `/Users/chanbla11mit/.hermes/jev/logs` (`plugins/jev/jev_log.py` line 18). Lines that contain `-worker-glm-`: `decisions.jsonl` 127 of 184, `tool_results.jsonl` 3273 of 10918, `auxiliary.jsonl` 35 of 628, `peak-hold.out.log` 0 of 31403. A `route` record has the keys `applied`, `board`, `confidence`, `error_class`, `event`, `held_until`, `jev_input_tokens`, `jev_latency_ms`, `new_assignee`, `not_applied_reason`, `orchestrator_model`, `original_assignee`, `probabilities`, `profile`, `route` and `task_id`. History stays as written, and no log line is rewritten. This is how the readers treat old names:

- The change request limit, `_card_limit` (`plugins/jev/routing.py` lines 948 to 982). The first rule reads the applied route name from the card's last `route` record (`routed_applied_route`, lines 867 to 904), which contains no profile name. The second rule compares the card's current assignee with the current lists. Old names in the log do not change either rule.
- The Claude worker after the change request limit, `routed_claude_worker` (lines 844 to 864). It reads `original_assignee` only when that is one of the board's Claude workers. Those names do not change.
- Change requests that do not count, `_counted_change_requests` (lines 820 to 841), compares reviewer names. The GLM reviewers keep their names.
- The peak hold and the review handoff act on open cards and on the profile name of the running process (`jev_log.profile_name`, `HERMES_PROFILE`, `plugins/jev/jev_log.py` lines 44 to 52). After step D2a no open card is assigned to an old name, and no new run starts on an old name, because the old profiles no longer exist.
- `scripts/jev-report` counts a card as moved to a GLM worker when `new_assignee` is a non-empty string different from `original_assignee` (lines 414 to 418). Old names still count. Defect found: the report gives a run its sessions by comparing `task_runs.profile` with `sessions.profile_name` (line 356). After a rename, `task_runs.profile` keeps the old name, while `rekey_profile_state` changes `sessions.profile_name` to the new name. The report would therefore no longer find the sessions and tokens of the runs from before the rename. Card R3 fixes this.

### LaunchAgent `com.nous.hermes-jev-peak-hold`

`/Users/chanbla11mit/Library/LaunchAgents/com.nous.hermes-jev-peak-hold.plist` runs `/usr/bin/python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply` every 10 seconds, with `PATH` `/Users/chanbla11mit/.hermes/hermes-agent/.hermes/bin:/usr/bin:/bin:/usr/sbin:/sbin`. Its output goes to `/Users/chanbla11mit/.hermes/jev/logs/peak-hold.out.log` and its errors to `/Users/chanbla11mit/.hermes/jev/logs/peak-hold.err.log`. The plist names no profile. The script reads `plugins/jev/config.json` of the main checkout `/Users/chanbla11mit/hermes-local-harness`, not an installed copy (`scripts/jev-peak-hold` lines 69 to 70 and 304). The plist itself needs no change. But the peak hold follows the main checkout as soon as the new `config.json` is integrated into local `main`. So that integration belongs to live step D8, after the rename and together with the `jev` install, and not earlier.

## 5. Fallback of a dispatcher-started worker, and the Z.ai quota error

### The fallback chain of a worker with a card model override

- The dispatcher starts a worker with `hermes -p <profile> --cli --accept-hooks [-m <model> [--provider <provider>]] ... chat -q "work kanban task <id>"` (`hermes_cli/kanban_db_dispatch.py` lines 2743 to 2777; `-m` and `--provider` at lines 2761 to 2766).
  Update for Hermes v0.23.3 (2026-11-20, card t_9cd82eff, commit `caafe5389ae585ef77387a962aee05b1bcf17029`): the dispatcher now starts `[sys.executable, "-m", "hermes_cli.kanban_worker_client"]` (`_worker_argv`, `hermes_cli/kanban_db_dispatch.py` lines 2639 to 2642). That process sends `kanban.run` to the profile owner, which builds the session policy with the card's model, provider and reasoning effort (`gateway/session_kanban.py` `build_kanban_policy`, lines 51 to 57) and sets `accept_hooks=True` in the Kanban context (line 65); the managed worker registers the profile's shell hooks with it (`gateway/session_policy.py` `register_worker_hooks`, lines 843 to 857). The bullets below about the fallback chain were established on the earlier commit and were not checked again on v0.23.3.
- The CLI reads the fallback chain from the profile's configuration, whatever model it was started with: `self._fallback_model = get_fallback_chain(CLI_CONFIG)` (`hermes_cli/cli_init_mixin.py` line 295). The chain is read again at each turn (`hermes_cli/cli_chat_turn_mixin.py` lines 34 to 47). `get_fallback_chain` returns `fallback_providers` first and then the legacy `fallback_model` (`hermes_cli/fallback_config.py` lines 103 to 120). The rule that a pinned route gets no inherited chain, `scoped_fallback_chain` (lines 123 to 144), applies only to delegated children and cron jobs (`tools/delegate_tool_config.py` line 481, `cron/scheduler.py` lines 115 to 120). The main CLI agent does not use it. So a card override `-m glm-5.3-flash --provider zai` still has the profile's `fallback_providers`.
- A fallback switch replaces the client, the model and the provider in place, and the retry loop continues on the new backend (`agent/chat_completion_helpers.py` `try_activate_fallback`, lines 2074 to 2134). Fallback lasts for one turn: `restore_primary_runtime` returns to the primary model at the start of the next turn (`agent/agent_runtime_helpers.py` lines 1426 to 1434). A dispatcher worker runs one `chat -q` turn, so after a switch the rest of that run stays on the Claude model. The next run of the same card (after a change request, or after a requeue) starts on `zai` again.
- `fallback.min_switch_reset_seconds` defaults to 0, which means off (`hermes_cli/config_defaults.py` line 40; `agent/fallback_cooldown.py` lines 25, 33 and 36). The switch is therefore not delayed when the provider names a reset time.

### Classification of the Z.ai quota error

The record of the observed error is `/Users/chanbla11mit/.hermes/profiles/harness-worker-glm-1/logs/errors.log`, lines 113, 166 and 168, on 2026-11-13 at 20:09:32. The error was HTTP 429 with body `{'error': {'code': '1308', 'message': 'Usage limit reached for 5 hour. Your limit will reset at 2026-11-13 19:11:25'}}`, followed by `agent.conversation_loop: Non-retryable client error`. `docs/state/261114-hard-route-unverified-points.md` lines 20 and 133 to 170 record the outcome without a fallback: `rate_limited`, exit code 75, a requeue after the 300-second cooldown, and no notification.

`_status_429` (`agent/error_classifier.py` lines 1049 to 1078) classifies this body as follows:

1. The code `1308` is not in `_BILLING_ERROR_CODES` (line 1053). The message matches no `_OVERLOADED_PATTERNS` (lines 156 to 165 and 1057). The response is not an OpenRouter upstream error (line 1060).
2. The quota check: the message contains `usage limit`, one of `_USAGE_LIMIT_PATTERNS` (line 169), so `quota_wall` is true (lines 1068 to 1070). It contains none of `_RATE_LIMIT_PATTERNS` (lines 145 to 152; the message has "will reset at", not "try again in"), so `explicit_rate_limit` is false (line 1071).
3. `_has_usage_limit_transient_signal` (lines 1233 to 1242) is false: the message contains none of `_USAGE_LIMIT_TRANSIENT_SIGNALS` (lines 170 to 173; "reset at" is not "resets at"), and the body has none of `_RESET_FIELDS` (line 1229). The function also checks the headers `_RESET_HEADERS` (line 1230). Whether the response headers had `retry-after` or `x-ratelimit-reset` was not established, because the log does not record headers. With such a header, step 4 gives `rate_limit` instead of `billing`.
4. The result is `_V_BILLING`: reason `billing`, `retryable` false, `should_rotate_credential` true, `should_fallback` true (lines 1072 to 1073 and 459 to 463). This matches the logged "Non-retryable client error" (`agent/turn_recovery.py` line 1075).

### When the fallback starts

`billing` and `rate_limit` are both in `_RATE_LIMIT_REASONS` (`agent/turn_recovery.py` lines 1666 to 1680). For these reasons the switch to fallback happens at once, at the first error of the call, with no retry (`agent/turn_recovery.py` lines 1884 to 1921). There is one exception: no early switch while the credential pool can rotate to another entry (`_pool_may_recover_from_rate_limit`, `run_agent.py` lines 217 to 224: the pool has more than one entry and an available one). Whether a GLM profile's `auth.json` pool has more than one Z.ai entry was not established, because `auth.json` was not read. When the early switch does not happen, the non-retryable path tries the fallback as well (`agent/turn_api_error.py` lines 306 to 346). The billing verdict reaches the fallback in both cases. Today the GLM profiles have no fallback chain (section 4), so the run ends with `rate_limited`.

A Z.ai overload 429 (a message in `_OVERLOADED_PATTERNS`) is a different case: Hermes backs off on the same key (`agent/error_classifier.py` lines 1055 to 1058), and it switches to fallback only after two retries (`agent/turn_recovery.py` lines 1899 to 1908).

### A fallback run still counts as the GLM worker profile

The dispatcher sets `HERMES_PROFILE` to the profile it starts (docstring of `hermes_cli/profiles.py` line 2139; the variable is read at line 2147). `jev_log.profile_name` reads that variable (`plugins/jev/jev_log.py` lines 44 to 52). Every `jev` rule selects by profile name and by the lists in `config.json`, never by model:

- the peak hold: `glm_workers_by_board` and `all_glm_workers` (`plugins/jev/peak_hold.py` lines 170 to 213);
- clearing the model override at the review handoff (`plugins/jev/routing.py` `handle_request_review`, about lines 740 to 770, `profile in peak_hold.all_glm_workers(config)`);
- the change request limits (`_card_limit`, lines 948 to 982), and the choice of the GLM review (`_review_payload`, line 637).

So a card whose run fell back to Claude is held in peak hours like any GLM card. It is cleared at review, counted against the route's change request limit, and first reviewed by the board's GLM reviewer.

### What a GLM worker profile running a Claude model changes or breaks

1. Reasoning effort. `agent.reasoning_effort` (`high` or `max`) does not reach the provider. `claude-subscription` reads its effort only from `HERMES_CLAUDE_SUBSCRIPTION_EFFORT`, with the default `medium` (`client.py` line 270). See open question Q2.
2. Helper tasks. The helper tasks of the GLM profiles name `zai` explicitly. The main fallback chain applies only to helper tasks with `provider: auto` (`agent/auxiliary_client.py` lines 4502 to 4513). With the Z.ai quota used up, compression and the other helper calls fail, unless each `auxiliary.<task>.fallback_chain` has an entry. Card R2 declares these entries; see open question Q1.
3. Claude subscription quota. All 30 GLM workers and five GLM reviewers can fall back at the same time, when one Z.ai plan runs out for all of them. Up to 35 Claude sessions (`max_in_progress_per_profile` 1 per profile) would then run next to the Claude workers on the same Claude subscription. A Claude subscription limit on concurrent sessions or tokens is not recorded in this repository or in Hermes, so it was not established.
4. SOUL text. Each GLM worker SOUL begins "The profile model is `glm-5.3` on provider `zai`" (for example `policies/profile-souls/anki-worker-glm-1/SOUL.md` line 1). After a switch the text is not true for the rest of the run. Card R2 adds one sentence that says so.
5. The savings report. `scripts/jev-report` sorts tokens by model family (`model_family`, lines 266 to 272, and lines 314 to 326). Claude tokens of a fallback run on a GLM worker profile count as Claude tokens of a card moved to a GLM worker, so the reported saving goes down. That is correct accounting; card R2 records it in `procedures/jev-plugin.md`.
6. `verify-state` currently forbids fallback declarations on the GLM reviewers. The message is "GLM reviewer declares fallback_providers: ... must declare none, as the GLM workers" (`scripts/verify-state` lines 554 to 556 in `check_glm_reviewer_profiles`, docstring line 529). The same lines also forbid `auxiliary_fallback_chain` and `auxiliary_models` on the GLM reviewers. For the GLM workers, `check_glm_worker_profiles` (lines 506 to 519) checks no fallback field. Card R2 replaces the reviewer rule and adds the worker rule.
7. Nothing else was found that breaks. The provider binds its session to profile, workspace and task, and refuses a change of these (`client.py` lines 190 to 192). A fallback client is a new client (`chat_completion_helpers.py` lines 2096 to 2111). After a switch the preflight runs again against the context length of the fallback model (`agent/turn_api_error.py` lines 342 to 346); `compat.py` declares 1000000.

## 6. The Z.ai side of doubling the concurrent GLM runs

- Hermes limits concurrency by profile, not by provider: `max_in_progress_per_profile` (`hermes_cli/kanban_db_dispatch.py` lines 2360 to 2372; value 1 on 2026-11-16). With six GLM workers and one GLM reviewer per board, up to 35 Z.ai runs can be in progress across the five boards, against 20 today. No Hermes or repository setting needs a change for this.
- `roster.yaml` declares `concurrency_limit: 1` for every GLM worker, but `scripts/verify-state` does not check that field (`docs/state/261114-hard-route-unverified-points.md` lines 86 and 124).
- Not established: whether the 15 new profiles log in to the same Z.ai account as the existing ones (the owner adds the logins; `auth.json` is not read). Also not established: the Z.ai plan's limit on concurrent requests, and how Z.ai counts its five-hour limit (`docs/state/261114-hard-route-unverified-points.md` lines 375 to 377). Hermes recognises "too many concurrent requests" as a rate limit (`agent/error_classifier.py` line 150) and handles a Z.ai 429 overload by backing off (lines 1055 to 1058). Neither needs configuration.
- Expected effect: the shared five-hour limit is reached sooner when more runs work in parallel. After this change, every GLM profile falls back to the Claude subscription at that point (section 5, item 3). No request was sent to Z.ai for this specification.

## 7. Cards, in order

Each repository card works in its own worktree of `/Users/chanbla11mit/hermes-local-harness`. Its baseline is the local `main` that holds the cards before it, with `t_17149680` and `t_cf518fd0` integrated. Each repository card runs the full test loop of this card as its last check:

    for f in tests/test_*.py; do LANG=en_US.UTF-8 python3 "$f" >/dev/null 2>&1 || echo "FAIL $f"; env -u LANG python3 "$f" >/dev/null 2>&1 || echo "FAIL-noLANG $f"; done
    python3 tests/test_verify_state.py; python3 scripts/verify-state --fixture tests/fixtures/clean.yaml

The live cards need the owner's authorization for each live write. They run in the order given. No live step starts before R1 to R4 are approved and integrated into local `main` (D8 does the integration of the `jev` configuration).

### R1. Repository: names of the 30 GLM worker profiles

Precedent: card `t_f4ce916d`, which added the `-3` profiles to `roster.yaml`, `scripts/verify-state`, `snapshots/sanitized-current-state.yaml`, `plugins/jev/config.json` and the policy sources in one card (`procedures/jev-plugin.md` line 91).

- Files:
  - `roster.yaml`: rename the 15 entries and add 15 new entries, which copy the entry of their source profile. In `glm_worker_reasoning_effort_settings.profiles`, the ten `-hard-1` and `-hard-2` profiles. In `approval_policy.profiles` and `project_dispatch_allowlist`, the 30 names.
  - `snapshots/sanitized-current-state.yaml`: `profiles`, `approvals.profiles`, `kanban.dispatch_profiles` (the 20 names that stay, then the 30 in the order of section 1), and the five `deploy_profiles` lists. A copy gets the skills of its source profile (`procedures/jev-plugin.md` line 119).
  - `scripts/verify-state`: `PROJECT_GLM_WORKER_POOLS` with six names per board, and the comment at line 2321.
  - `plugins/jev/config.json`: the four lists of section 1 on each board.
  - `policies/profile-souls/`: rename the 12 GLM worker SOUL directories with `git mv` and add 12 new ones. Each new SOUL is its source SOUL with the profile name and the worker number replaced. The first sentence gives the route's model: `glm-5.3-flash` on the easy profiles, `glm-5.3` on the medium and hard profiles. Also the five GLM reviewer SOULs, the five Opus reviewer SOULs and the five orchestrator SOULs, each naming the eight implementation profiles of its board.
  - The five orchestrator skill sources, with the `version` line raised.
  - `procedures/jev-plugin.md` and `procedures/switching-hermes-models.md` line 15: current names, plus one sentence each about this card. `docs/README.md` line 17.
  - `tests/gen_fixtures.py`, `tests/fixtures/clean.yaml`, and the other fixtures regenerated by `python3 tests/gen_fixtures.py`.
  - Every test of section 8 group R1 that states an old name as a member of the shipped roster, snapshot, verifier, configuration or policy text, changed in this card. A test that uses an old name only as input of a configuration it builds itself may stay unchanged.
- Check: the full test loop, and also these two commands. The first must print nothing. The second must print `2 2 4 2` after each board name (the lengths of `easy_route_workers`, `medium_route_workers`, `glm_workers` and `glm_max_workers`; the key path `routing.boards` is that of `plugins/jev/config.json` at the baseline):

      git grep -n -E -- '-worker-glm-[123]([^0-9]|$)' -- roster.yaml snapshots scripts plugins policies procedures/jev-plugin.md procedures/switching-hermes-models.md docs/README.md tests/gen_fixtures.py tests/fixtures
      python3 -c 'import json; c=json.load(open("plugins/jev/config.json")); [print(b, *(len(v.get(k, [])) for k in ("easy_route_workers", "medium_route_workers", "glm_workers", "glm_max_workers"))) for b, v in c["routing"]["boards"].items()]'

  The first command leaves out `tests/test_*.py`, because a test may keep an old name as input of a configuration it builds itself (see the last item of the file list).

### R2. Repository: fallback declarations of the 35 GLM profiles

Depends on R1 and on `t_17149680` (the Sonnet entry in `MODELS`).

- Files:
  - `roster.yaml`: `fallback_providers` of section 1 on the 30 GLM workers and the five GLM reviewers. Also `auxiliary_fallback_chain` for the 16 `HELPER_TASKS` (`scripts/verify-state` lines 597 to 599), as decided in open question Q1. Default if the owner gives no other answer: the `LIGHT_HELPER_TASKS` (lines 605 to 606) get `claude-haiku-5-5`, and the other helper tasks get the profile's own fallback model.
  - `scripts/verify-state`: replace the rule of lines 554 to 556 (and the docstring, line 529). The new rule: a GLM worker or GLM reviewer declares exactly the `fallback_providers` entry of section 1; every entry has provider `claude-subscription` and a model in `MODELS`; no entry names `anthropic`. `auxiliary_models` stays forbidden. Change the fixture fallback settings so that `tests/fixtures/clean.yaml` matches, and add one fixture with a GLM profile whose fallback is `anthropic`.
  - The 30 GLM worker SOUL sources and the five GLM reviewer SOULs: one sentence. When the Z.ai quota is used up, Hermes can switch the run to `claude-subscription` `claude-haiku-5-5` (easy) or `claude-sonnet-5-5` (medium, hard, reviewers); the card is then completed in the same way, and the `jev` rules are unchanged.
  - `procedures/jev-plugin.md`: one paragraph with section 5 of this file.
  - `tests/test_verify_state.py` and a new `tests/test_glm_claude_fallback.py`. The new test checks that the roster has the owner's fallback for each of the 35 profiles, that the verifier rejects `anthropic` and a missing entry, and that it accepts the clean fixture.
- Check: `python3 tests/test_glm_claude_fallback.py`, `python3 scripts/verify-state --fixture tests/fixtures/clean.yaml` (exit 0), `python3 scripts/verify-state --fixture tests/fixtures/<new fixture>.yaml` (exit 1 with the expected line), and the full test loop.

### R3. Repository: `scripts/jev-report` matches the sessions of runs from before a rename

- Files: `scripts/jev-report` and `tests/test_jev_report.py`. At line 356, a session also matches a run when the run's profile is in `previous_names` of `/Users/chanbla11mit/.hermes/profiles/<session profile>/profile.yaml`. That is the list `rename_profile` writes (`hermes_cli/profiles.py` lines 2431 to 2443; `read_profile_meta`, lines 934 to 951). The report reads only that key. A missing or unreadable file means no previous names.
- Check: `python3 tests/test_jev_report.py`, with a new test of a run under an old name and a session under the new name, and the full test loop.

### R4. Repository: procedure of the live deployment

- Files: `procedures/jev-plugin.md`, a new section "Renaming the GLM worker profiles and creating the second worker of each route". It holds steps D0 to D10 below with their exact commands and rollbacks, in the form of the section "Creating the third GLM worker profile of each board" (lines 89 to 179).
- The procedure text keeps the order of D1 and D2a, with its source lines:
  - The old names stay in `kanban.dispatch_profiles` while the existing runs finish. They are removed only when no run is running on them, and the wait is then repeated, because a run can start before the removal.
  - The wait also covers every card in `review` whose latest `review_requested` event names an old implementer. A change request gives such a card back to that name (`hermes_cli/kanban_db.py` lines 3602 to 3617 and 3768 to 3797).
  - The rename does not wait for zero cards assigned to an old name. After the rename, step D2a moves those cards to the new name and adds a comment. The same check is repeated in D8 and D10, and after the deployment, until the list of D1 step 2 holds no card that is not `done` or archived.
- Check: `git diff --name-only` names only that file; `grep -c 'review_requested' procedures/jev-plugin.md` and `grep -c 'kanban --board <board> assign' procedures/jev-plugin.md` each give at least 1; and the full test loop.

### D0. Live: smoke test of `claude-sonnet-5-5`

Use the method of `procedures/haiku-helper-routing.md` step 4a (lines 172 to 188). This runs before any other live change and changes no live state, because it uses a throwaway `HERMES_HOME`. Run it once, from the main checkout that holds `t_17149680`:

    python3 /Users/chanbla11mit/hermes-local-harness/plugins/model-providers/claude-subscription/smoke.py --cli /Users/chanbla11mit/.hermes/runtimes/claude-code/2.1.302/claude --model claude-sonnet-5-5

- Check: the output is `SMOKE PASS cli=2.1.302 model=claude-sonnet-5-5`. On `SMOKE FAIL: <reason>`, stop and record the reason.
- Rollback: none, because nothing changes.

### D1. Live: back up, let the existing runs finish, then stop new runs on the old names

Facts that set the order of this step:

- The dispatcher starts a card only when its assignee is in `kanban.dispatch_profiles` and the profile exists (`_gated`, `hermes_cli/kanban_db_dispatch.py` lines 1685 to 1690). For any other assignee it records `skipped_nonspawnable` and starts nothing (lines 2049 to 2064). After the old names leave the list, a `ready` card on an old name is never started. This includes a `scheduled` card that the peak hold releases to `ready`, and a card that a change request returns. A wait for zero cards assigned to an old name after that removal therefore cannot end, so this step does not wait for it. Step D2a moves those cards instead.
- The `implementer` of a `review_requested` event is the profile of the card's latest run (`hermes_cli/kanban_db.py` lines 3498 to 3506). A change request reads the `implementer` of the latest `review_requested` event (lines 3602 to 3607) and writes it as the assignee (line 3617). `reopen_review_task` does the same (lines 3768 to 3797). A card in `review` has its reviewer as its assignee, so a wait that reads only the assignee does not see these cards.
- `unblock_task` returns a card that was blocked from `review` to `review` (`hermes_cli/kanban_db.py` lines 3724 to 3744, line 3742). Such a card can return to an old name long after the rename.
- Until D7, the reviewers have their old SOULs, which name the old implementation profiles. They therefore accept a card whose implementer is an old name.

Steps:

1. Back up the dispatch list: `cp -p /Users/chanbla11mit/.hermes/config.yaml /Users/chanbla11mit/.hermes/config.yaml.pre-<card id>`.
2. Record the cards, read only. For `<board>` in `jobcron`, `cha-pt`, `harness`, `jss-genr` and `anki`:

       hermes kanban --board <board> list --json

   (`list` with `--json`: `hermes_cli/kanban_parser.py` lines 235 to 249). For each card that is not `done` or archived, read its events:

       hermes kanban --board <board> show <task id> --json

   (`hermes_cli/kanban.py` lines 473 to 497; the `events` field, with `kind` and `payload`, is line 497). Write one file `/Users/chanbla11mit/.hermes/profiles/<deployment profile>/cache/scratch/<card id>/old-name-cards.json`. For each card it holds the board, the task id, the status, the assignee and the `implementer` of the latest `review_requested` event. It lists every card whose assignee is an old name, and every card whose latest `review_requested` implementer is an old name.
3. Let the existing runs finish while the 15 old names stay in `kanban.dispatch_profiles`. Read the lists of step 2 again, and wait until both of these hold on every board:
   - (a) No card has status `running` with an old name as its assignee.
   - (b) No card in `review` has an old name as the `implementer` of its latest `review_requested` event.

   Cards in `ready`, `todo`, `scheduled` or `blocked` that are assigned to an old name may remain; step D2a moves them. While the old names are in the list, the dispatcher starts `ready` cards on them, so this wait has no fixed end. The deployment card may stop it after a time limit that it records, and go on to step 4. The wait of step 5 ends without a time limit.
4. Remove the 15 old names from `kanban.dispatch_profiles`, one at a time. After that the dispatcher starts no new run on them (`kanban_db_dispatch.py` lines 1690 and 2049 to 2064):

       python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <old name> --to glm --dispatch remove

   The script writes the dispatch entry only together with `--to`. `--to glm` writes the model, provider and helper tasks that the profile already has, and backs up the profile's `config.yaml` (`procedures/jev-plugin.md` line 144).
5. Read the lists again, and repeat the wait of step 3 until (a) and (b) hold. A run can start in the time between the last reading of step 3 and step 4, so the result of step 3 alone is not enough. This wait ends, for these reasons:
   - After step 4 no run starts on an old name, so no new `review_requested` event names an old implementer.
   - A running run ends, at the latest when it reaches its runtime limit.
   - A card in `review` leaves `review` when its reviewer approves it (`done`), requests changes (the card returns to `ready` on the old name and waits for D2a), or blocks it. A card that is blocked from `review` stays in the file of step 2, and step D2a handles it.
6. Write the file of step 2 again, from new readings. Cards that changed status, or that were created since step 2, are then in it.
7. Count the notification subscriptions that name an old name, read only. For each board: `sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/<board>/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"`. If a count is not 0, stop and ask the owner.

From step 4 until D8, the orchestrators should create no card on a GLM route (open question Q5). A card that is created anyway is moved by the repeated check of D2a.

- Check: (a) and (b) hold on every board in the reading of step 5. `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml` gives 0. The file of step 6 exists.
- Rollback: `cp -p /Users/chanbla11mit/.hermes/config.yaml.pre-<card id> /Users/chanbla11mit/.hermes/config.yaml`.

### D2. Live: rename the 15 profiles

For each board prefix in `jobcron`, `chapt`, `harness`, `jss`, `anki`:

    hermes profile rename <prefix>-worker-glm-1 <prefix>-worker-glm-easy-1
    hermes profile rename <prefix>-worker-glm-2 <prefix>-worker-glm-medium-1
    hermes profile rename <prefix>-worker-glm-3 <prefix>-worker-glm-hard-1

Then replace the SOUL of each renamed profile with its R1/R2 source. For jobcron, write the SOUL with the `sed` method of `procedures/jev-plugin.md` line 135, using the new name and number. Back up the old SOUL first (`cp -p .../SOUL.md .../SOUL.md.pre-<card id>`). Replacing these SOULs needs the owner's approval of open question Q3.

- Check: each command prints `✓ Renamed` and does not print `⚠ Profile was renamed, but the live gateway could not migrate session identity`. If it prints that warning, stop the rename sequence and follow the printed instruction after all Kanban workers have ended. `hermes profile list` shows the 15 new names and none of the old. `/Users/chanbla11mit/.hermes/gateway_state.json` `served_profiles` contains the new names. `ls /Users/chanbla11mit/.hermes/profiles/<new name>/auth.json` exists.
- Rollback: `hermes profile rename <new name> <old name>` for each, and restore `SOUL.md.pre-<card id>`.

### D2a. Live: move the cards of the old names to the new names

Start this step directly after D2. Use the file of D1 step 6, and read each listed card again with `hermes kanban --board <board> show <task id> --json`.

1. Move each card that is not `done` or archived, not `running` and not in `review`, and whose assignee is an old name:

       hermes kanban --board <board> assign <task id> <new name>

   (`hermes_cli/kanban_parser.py` line 251). `assign_task` refuses only a card that is `running` under a claim (`hermes_cli/kanban_db.py` lines 1634 to 1638). After D1 no such card remains on an old name. A new assignee starts with a failure count of 0 (lines 1639 to 1643). Do not move a card in `review`: its assignee is its reviewer.
2. Add one comment to each card of the file, both the moved cards and the cards that only have an old implementer:

       hermes kanban --board <board> comment <task id> "Profile <old name> was renamed to <new name> by hermes profile rename on <date> (deployment card <card id>). The name <old name> in the card body and in earlier events is the same profile."

   (`hermes_cli/kanban_parser.py` lines 280 to 284). Reason: card bodies name the assigned worker exactly, and the worker SOULs and, after D7, the reviewer SOULs treat a different profile name as a boundary mismatch. The comment records the rename in the card history.
3. A card with an old implementer that is still `blocked`, or that returns to `review` later (`unblock_task`, `hermes_cli/kanban_db.py` line 3742), returns to the old name when its reviewer requests changes (line 3617). The dispatcher then records `skipped_nonspawnable` for it, because the profile does not exist (`kanban_db_dispatch.py` lines 2049 to 2064). Repeat step 1 for these cards in D8 step 4 and in D10. After the deployment, repeat it after each change request on a card of the file, until no card of the file is anything other than `done` or archived.

The moved cards start only after D6 adds the new names to `kanban.dispatch_profiles`.

- Check: on every board, `hermes kanban --board <board> list --json` shows no card that is not `done` or archived and is assigned to an old name. `show <task id> --json` of each card of the file shows the comment.
- Rollback: after the D2 rollback, `hermes kanban --board <board> assign <task id> <old name>` for each moved card. Comments are not removed. Add one comment that records the rollback.

### D3. Live: `.env` path lines and the `claude-subscription` plugin, on the renamed profiles and the GLM reviewers

1. Back up each `.env` with `cp -p` before any write. On the 12 renamed profiles of `harness`, `chapt`, `jobcron` and `jss`, and on the GLM reviewers of those four boards, append the two lines `HERMES_CLAUDE_SUBSCRIPTION_CLI` and `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE`. Copy them, without printing, from `/Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env` (after D2), for example `grep -E '^HERMES_CLAUDE_SUBSCRIPTION_(CLI|TOKEN_FILE)=' <source .env> >> <target .env>`. Add `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` only if open question Q2 says so. The four anki profiles already have the lines.
2. Copy the plugin directory `plugins/model-providers/claude-subscription` of the integrated commit (with `claude-sonnet-5-5`) to `/Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription` of the 15 renamed profiles and the five GLM reviewers. Back up an existing copy first. This replaces the old copy on the four anki profiles.

- Check: `grep -c '^HERMES_CLAUDE_SUBSCRIPTION_CLI='` and `grep -c '^HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE='` give 1 for each of the 20 `.env` files. `grep -c '^ANTHROPIC_API'` gives 0. `shasum -a 256` of each copied `compat.py` equals the integrated repository file.
- Rollback: restore each `.env` and plugin backup; remove a plugin copy that did not exist before.

### D4. Live: create the 15 new profiles by copy

For each board prefix, after D3, so that each copy gets the `.env` lines and the plugin:

    hermes profile create <prefix>-worker-glm-easy-2 --clone-from <prefix>-worker-glm-easy-1
    hermes profile create <prefix>-worker-glm-medium-2 --clone-from <prefix>-worker-glm-medium-1
    hermes profile create <prefix>-worker-glm-hard-2 --clone-from <prefix>-worker-glm-hard-1

Then follow steps 2 to 4 of `procedures/jev-plugin.md` lines 124 to 143: delete the copied memory files, replace the copied SOUL with its R1/R2 source (`sed` for jobcron), and check the plugins. Without `--clone-all`, the copy contains `config.yaml`, `.env`, `SOUL.md`, `skills/`, `memories/` and `plugins/`, and no `auth.json` (`procedures/jev-plugin.md` lines 115 to 123).

- Check: `hermes -p <new profile> plugins list --plain --no-bundled` shows the same plugin lines as its source profile. `ls /Users/chanbla11mit/.hermes/profiles/<new profile>/plugins/model-providers/claude-subscription` exists. `auth.json` is absent.
- Rollback: `hermes profile delete <new profile>` for each. The exact confirmation prompt of the delete command was not read for this specification.

### D5. Owner: Z.ai login of the 15 new profiles

The owner runs these commands. Nobody else runs them or handles the key:

    hermes -p jobcron-worker-glm-easy-2 auth add zai
    hermes -p jobcron-worker-glm-medium-2 auth add zai
    hermes -p jobcron-worker-glm-hard-2 auth add zai
    hermes -p chapt-worker-glm-easy-2 auth add zai
    hermes -p chapt-worker-glm-medium-2 auth add zai
    hermes -p chapt-worker-glm-hard-2 auth add zai
    hermes -p harness-worker-glm-easy-2 auth add zai
    hermes -p harness-worker-glm-medium-2 auth add zai
    hermes -p harness-worker-glm-hard-2 auth add zai
    hermes -p jss-worker-glm-easy-2 auth add zai
    hermes -p jss-worker-glm-medium-2 auth add zai
    hermes -p jss-worker-glm-hard-2 auth add zai
    hermes -p anki-worker-glm-easy-2 auth add zai
    hermes -p anki-worker-glm-medium-2 auth add zai
    hermes -p anki-worker-glm-hard-2 auth add zai

The 15 renamed profiles keep their login, because `auth.json` moved with the directory (section 2).

- Check: `ls /Users/chanbla11mit/.hermes/profiles/<new profile>/auth.json` exists for all 15 (no value read). The owner's one model call per new profile, as in `procedures/jev-plugin.md` line 91: `hermes -p <profile> chat -q "Reply with exactly READY. Do not call any tools." --oneshot -Q`, which returns `READY`.
- Rollback: deleting the profile (D4 rollback) removes its login.

### D6. Live: `fallback_providers`, helper fallback chains and `kanban.dispatch_profiles`

Before the first `--dispatch add` command, deploy the five Opus reviewer SOULs and the five GLM reviewer SOULs of D7. A card that D2a moved starts as soon as its new name is in the list, and its review then needs a reviewer SOUL that names the new name.

For the 30 GLM workers, in the order of section 1. This adds each name at the end of `kanban.dispatch_profiles` and writes the roster declarations of R2:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch add --apply-fallbacks

For the five GLM reviewers:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <reviewer> --apply-fallbacks

Preview each command with `--dry-run` first. The script backs up each profile's `config.yaml`.

- Check: `hermes -p <profile> config get fallback_providers` shows the entry of section 1. The dispatch list equals `kanban.dispatch_profiles` of `snapshots/sanitized-current-state.yaml` of R1, entry for entry.
- Rollback: `--clear-fallbacks` on each profile (`scripts/verify-state` treats `[]` and an absent value as equal, line 690), and the D1 backup of `/Users/chanbla11mit/.hermes/config.yaml`.

### D7. Live: GLM reviewer and Opus reviewer SOULs, orchestrator SOULs and skills

Before any card can start on a new name, the five Opus reviewer SOULs and the five GLM reviewer SOULs from R1/R2 must be live. So these ten SOULs are deployed before the `--dispatch add` commands of D6, and the other files of this step after D6. A reviewer with an old SOUL does not accept a card from an implementation profile that its SOUL does not name (`procedures/jev-plugin.md` line 178). The orchestrator SOULs and the five orchestrator skills follow. The owner approved the harness-orchestrator skill (decision 5). The other files need the owner's approval (open question Q3).

- Check: `shasum -a 256` of each live file equals its tracked source.
- Rollback: restore the backup of each file (`cp -p` before the copy).

### D8. Live: `jev` install of the reviewed commit, and integration into local `main`

1. Record `plugins/.install-metadata.json` of each `jev` profile (41 before D4, 56 after) as the rollback reference.
2. Install the integrated commit of R1 to R3 from the local source, in this order (the method of `procedures/jev-plugin.md` lines 154 to 162): first the 30 GLM workers and the ten reviewers, then all other `jev` profiles, with the five orchestrators last.

       hermes -p <profile> plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref <reviewed commit> --enable --force

3. Integrate R1 to R4 into local `main` of `/Users/chanbla11mit/hermes-local-harness` with the owner's authorization, so that the `com.nous.hermes-jev-peak-hold` LaunchAgent reads the new `config.json` (section 4).
4. Repeat D2a steps 1 and 2 on the cards of the five boards, read again as in D1 step 2. This moves a card that was created during the window and routed to an old name, and a card that a change request returned to an old name.

- Check: every install output names no `caution` or `dangerous` verdict. `plugins list` prints `jev` `enabled`. The installed `config.json` has the same SHA-256 on every `jev` profile. `tail -3 /Users/chanbla11mit/.hermes/jev/logs/peak-hold.out.log` and `peak-hold.err.log` show no new error.
- Rollback: install the recorded previous commit with the same command and `--ref <previous commit>`. Revert the `main` integration only with the owner's authorization.

### D9. Live: harness-orchestrator skill copy

Copy `policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` of the integrated commit to the live harness-orchestrator profile, in the same way as card `t_fb1a44e4` (`procedures/manual-apply.md`). The owner approved this (decision 5).

- Check: `shasum -a 256` of the live file equals the tracked source.
- Rollback: restore the backup made before the copy.

### D10. Live: verifier

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state

- Check: none of the failure kinds listed in `procedures/jev-plugin.md` lines 165 to 178 is printed for any of the 30 names or the five GLM reviewers, and no `fallback drift` line is printed for them. The output has no new line compared with the last recorded live run. Also repeat D2a step 1 on the cards of the file of D1 step 6. It finds no card that is not `done` or archived and is assigned to an old name. While a card of that file is not `done` or archived, the deployment card records it in its handoff, so that the check of D2a step 3 continues after the deployment.
- Rollback: none; the verifier writes nothing.

## 8. Inventory: the 133 files and their cards

Columns: lines that name a GLM worker of a board; lines that name only `worker-glm-full`; other lines (templates). The counts are from `grep -c` at the baseline.

| File | GLM worker of a board | only `worker-glm-full` | other | Card |
|---|---|---|---|---|
| `deployment/hermes-terminal-outcome-notification.example.yaml` | 0 | 1 | 0 | unchanged: names only the retired `worker-glm-full` |
| `docs/README.md` | 1 | 0 | 0 | R1 |
| `docs/bugs/261116-kanban-dispatcher-marks-live-worker-crashed.md` | 4 | 0 | 0 | unchanged: history, records the names of the time |
| `docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md` | 1 | 0 | 0 | unchanged: history, records the names of the time |
| `docs/plans/261016-claude-max20x-implementation-plan.md` | 1 | 0 | 1 | unchanged: history, records the names of the time |
| `docs/specs/261004-concurrent-project-fleets.md` | 3 | 0 | 0 | unchanged: history, records the names of the time |
| `docs/specs/261020-chapt-scraper-repository-scope-and-push.md` | 1 | 0 | 0 | unchanged: history, records the names of the time |
| `docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md` | 0 | 0 | 1 | unchanged: history, records the names of the time |
| `docs/state/261019-live-drift-triage.md` | 0 | 1 | 0 | unchanged: history, records the names of the time |
| `docs/state/261114-hard-route-unverified-points.md` | 7 | 1 | 3 | unchanged: history, records the names of the time |
| `plugins/jev/config.json` | 10 | 0 | 0 | R1 |
| `policies/profile-skills/anki-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | 5 | 0 | 0 | R1 |
| `policies/profile-skills/chapt-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | 4 | 0 | 0 | R1 |
| `policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | 5 | 0 | 0 | R1 |
| `policies/profile-skills/jobcron-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | 4 | 0 | 0 | R1 |
| `policies/profile-skills/jss-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | 5 | 0 | 0 | R1 |
| `policies/profile-souls/anki-orchestrator/SOUL.md` | 1 | 0 | 0 | R1 |
| `policies/profile-souls/anki-reviewer-glm/SOUL.md` | 4 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/anki-reviewer/SOUL.md` | 3 | 0 | 0 | R1 |
| `policies/profile-souls/anki-worker-glm-1/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/anki-worker-glm-2/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/anki-worker-glm-3/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/chapt-orchestrator/SOUL.md` | 1 | 0 | 0 | R1 |
| `policies/profile-souls/chapt-reviewer-glm/SOUL.md` | 4 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/chapt-reviewer/SOUL.md` | 3 | 0 | 0 | R1 |
| `policies/profile-souls/chapt-worker-glm-1/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/chapt-worker-glm-2/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/chapt-worker-glm-3/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/harness-orchestrator/SOUL.md` | 1 | 0 | 0 | R1 |
| `policies/profile-souls/harness-reviewer-glm/SOUL.md` | 4 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/harness-reviewer/SOUL.md` | 3 | 0 | 0 | R1 |
| `policies/profile-souls/harness-worker-glm-1/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/harness-worker-glm-2/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/harness-worker-glm-3/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/jobcron-orchestrator/SOUL.md` | 1 | 0 | 0 | R1 |
| `policies/profile-souls/jobcron-reviewer-glm/SOUL.md` | 4 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/jobcron-reviewer/SOUL.md` | 3 | 0 | 0 | R1 |
| `policies/profile-souls/jss-orchestrator/SOUL.md` | 1 | 0 | 0 | R1 |
| `policies/profile-souls/jss-reviewer-glm/SOUL.md` | 4 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/jss-reviewer/SOUL.md` | 3 | 0 | 0 | R1 |
| `policies/profile-souls/jss-worker-glm-1/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/jss-worker-glm-2/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `policies/profile-souls/jss-worker-glm-3/SOUL.md` | 1 | 0 | 0 | R1; R2 (fallback sentence) |
| `procedures/hermes-terminal-outcome-notifications.md` | 0 | 1 | 0 | unchanged: names only the retired `worker-glm-full` |
| `procedures/jev-plugin.md` | 30 | 0 | 0 | R1; R2 (fallback paragraph); R4 (deployment section) |
| `procedures/manual-apply.md` | 0 | 7 | 0 | unchanged: names only the retired `worker-glm-full` |
| `procedures/rollback-restore.md` | 0 | 11 | 0 | unchanged: names only the retired `worker-glm-full` |
| `procedures/switching-hermes-models.md` | 1 | 1 | 0 | R1 |
| `roster.yaml` | 50 | 2 | 0 | R1; R2 (`fallback_providers`, `auxiliary_fallback_chain`) |
| `scripts/verify-state` | 5 | 2 | 1 | R1 (`PROJECT_GLM_WORKER_POOLS`, line 2321 comment); R2 (fallback rule, lines 554 to 556) |
| `skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py` | 0 | 1 | 0 | unchanged: names only the retired `worker-glm-full` |
| `snapshots/sanitized-current-state.yaml` | 96 | 7 | 0 | R1 |
| `spikes/glm-reviewer-pass/README.md` | 38 | 0 | 0 | unchanged: history, records the names of the time |
| `spikes/glm-reviewer-pass/run.py` | 1 | 0 | 0 | unchanged: history, records the names of the time |
| `tests/fixtures/active-extra.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/adapter-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/adoption-record-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/adoption-status-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/approval-mode-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/astra-local-override.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/auxiliary-model-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/behavior-changing-model-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/chapt-profile-soul-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/clean.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/compression-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/deployed-skill-divergence.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/deployment-skill-supporting-file-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/dormant-extra.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/fallback-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/frontend-repository-policy-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/glm-reviewer-dispatch-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/glm-reviewer-jev-plugin-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/glm-reviewer-model-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/glm-reviewer-skill-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/glm-worker-dispatch-missing.yaml` | 144 | 8 | 0 | R1 |
| `tests/fixtures/incomplete-omits-profile.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/jev-plugin-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/launch-agent-not-loaded.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/missing-plugin.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/orchestrator-skill-settings-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/plugin-pin-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/ponytail-absent-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/ponytail-enabled-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/project-repair-card-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/project-repair-policy-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/project-repository-allowlist-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/retired-glm-dispatch-drift.yaml` | 146 | 10 | 0 | R1 |
| `tests/fixtures/skill-deployment-missing.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/terminal-deployment-pending.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/terminal-notification-rollback.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/terminal-retry-default-drift.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/terminal-retry-missing-human-gate.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/terminal-retry-missing-scope.yaml` | 146 | 8 | 0 | R1 |
| `tests/fixtures/unexpected-plugin.yaml` | 146 | 8 | 0 | R1 |
| `tests/gen_fixtures.py` | 3 | 4 | 0 | R1 |
| `tests/hard_route_policy_edits.py` | 5 | 0 | 3 | R1: stays; it reverses earlier edits. R1 adds a reversal of its own edits in the same form if a comparison test needs it |
| `tests/jss_download_install_edits.py` | 2 | 0 | 0 | R1: stays; it reverses earlier edits. R1 adds a reversal of its own edits in the same form if a comparison test needs it |
| `tests/orchestrator_glm_review_edits.py` | 0 | 0 | 1 | R1: stays; it reverses earlier edits. R1 adds a reversal of its own edits in the same form if a comparison test needs it |
| `tests/test_anki_fleet_policy.py` | 1 | 0 | 0 | R1 |
| `tests/test_chapt_policy_reconciliation.py` | 2 | 1 | 0 | R1 |
| `tests/test_chapt_scraper_scope.py` | 2 | 0 | 0 | R1 |
| `tests/test_glm_retirement_policy.py` | 35 | 10 | 8 | R1 |
| `tests/test_glm_reviewer_roster.py` | 1 | 0 | 1 | R1 |
| `tests/test_glm_reviewer_souls.py` | 0 | 0 | 1 | R1 (name template) |
| `tests/test_haiku_helper_routing.py` | 1 | 0 | 0 | R1 |
| `tests/test_human_deployment_guide_writing_skill.py` | 7 | 0 | 0 | R1 |
| `tests/test_jev_change_request_count.py` | 11 | 0 | 0 | R1 |
| `tests/test_jev_client.py` | 1 | 0 | 0 | R1 |
| `tests/test_jev_glm_review.py` | 1 | 0 | 0 | R1 |
| `tests/test_jev_glm_review_block.py` | 1 | 0 | 0 | R1 |
| `tests/test_jev_glm_review_choice.py` | 33 | 0 | 0 | R1 |
| `tests/test_jev_glm_review_hold.py` | 1 | 0 | 0 | R1 |
| `tests/test_jev_glm_review_pass.py` | 2 | 0 | 0 | R1 |
| `tests/test_jev_peak_hold.py` | 30 | 0 | 0 | R1 |
| `tests/test_jev_policy_sources.py` | 25 | 0 | 8 | R1 |
| `tests/test_jev_report.py` | 0 | 0 | 2 | R1; R3 |
| `tests/test_jev_report_glm_review.py` | 1 | 0 | 0 | R1 |
| `tests/test_jev_route_notice.py` | 0 | 0 | 4 | R1 (name template) |
| `tests/test_jev_routing.py` | 92 | 0 | 0 | R1 |
| `tests/test_jev_routing_policy_text.py` | 21 | 0 | 5 | R1 |
| `tests/test_jss_fleet_policy.py` | 7 | 0 | 0 | R1 |
| `tests/test_managed_compression_settings.py` | 8 | 0 | 1 | R1 |
| `tests/test_orchestrator_profile_settings.py` | 2 | 0 | 1 | R1 |
| `tests/test_orchestrator_skill_terminology.py` | 0 | 1 | 0 | unchanged: names only the retired `worker-glm-full` |
| `tests/test_second_worker_policy.py` | 3 | 3 | 4 | R1 |
| `tests/test_stale_test_rule_policy.py` | 8 | 0 | 0 | R1 |
| `tests/test_third_glm_worker_policy.py` | 6 | 0 | 25 | R1 |
| `tests/test_upgrade_proportionality.py` | 1 | 1 | 0 | R1 |
| `tests/test_verify_state.py` | 7 | 0 | 0 | R1; R2 |
| `tests/test_verify_state_derived_expectations.py` | 2 | 0 | 0 | R1 |
| `tests/test_verify_state_glm_worker_skills.py` | 4 | 0 | 1 | R1 |
| `tests/test_verify_state_reconcile_roster.py` | 7 | 11 | 1 | R1 |
| `tests/test_writing_rules_policy.py` | 2 | 0 | 0 | R1 |

## 9. Open questions for the owner

- Q1. Helper tasks when the Z.ai quota is used up. Should each `auxiliary.<task>.fallback_chain` of the GLM profiles get a `claude-subscription` entry (default of R2: the light tasks to `claude-haiku-5-5`, the other tasks to the profile's own fallback model)? Without one, compression and the other helper calls of a fallback run still go to Z.ai and fail (section 5, item 2).
- Q2. Should the `.env` of the GLM profiles also get `HERMES_CLAUDE_SUBSCRIPTION_EFFORT`? It is not a path, so decision 4 does not cover it. Without it, a fallback run uses effort `medium`. The anki GLM profiles already have the setting.
- Q3. Do you approve deploying the changed SOULs of the five Opus reviewers, five GLM reviewers, five orchestrators and 30 GLM workers, and the four other orchestrator skills (anki, chapt, jobcron, jss)? Decision 5 covers only the harness-orchestrator skill. The reviewer SOULs are required before routing starts (D7).
- Q4. The disabled cron job `94d7b3d1dc19` "Jobcron emergency autonomous deployment controller" of `jobcron-orchestrator` names `jobcron-worker-glm-1` and `jobcron-worker-glm-2` in its prompt. The rename does not change it. Should a Jobcron card update it? This harness work does not touch Jobcron.
- Q5. Card creation from D1 step 4 to D8. A new card created in that window can be routed to an old name by the installed `jev` configuration. The dispatcher cannot start it (D1). D2a and D8 step 4 reassign such cards afterwards. Alternatively, you can stop creating cards on the five boards during the window.
