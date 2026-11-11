# Scheduled board check for each orchestrator

Procedure owner: harness board. Source card: `t_ef4aae41` (change 2 of the three changes the owner approved on 2026-10-30).

Files:

- Script: `scripts/orchestrator-board-check` (Python 3 standard library only).
- Settings, one per orchestrator: `deployment/orchestrator-board-check/<orchestrator profile>.json` for harness-orchestrator, jobcron-orchestrator, chapt-orchestrator, jss-orchestrator and anki-orchestrator. The values `board`, `orchestrator_profile`, `reviewer_profile` and `repositories` come from roster.yaml `project_fleets`.
- Cron prompt: `deployment/orchestrator-board-check/cron-prompt.md`.
- Tests: `tests/test_orchestrator_board_check.py` (run as `python3 tests/test_orchestrator_board_check.py`).

## Why

Two approved cards waited for hours because the orchestrator was not woken: Jobcron card J8 (no notification arrived; 7 hours) and harness card `t_15903481` (the orchestrator session restarted; 2 hours). The existing harness-orchestrator cron job "harness filed-card check" (script `harness_filed_card_check.py`) finds only cards that another profile filed on board harness. That job stays as it is; this check does not change or replace it.

## What the check does

The Hermes cron scheduler runs the script every 15 minutes before the agent. The script reads the board database in SQLite read-only mode and runs only the read-only Git commands `cat-file -e`, `merge-base --is-ancestor`, `log --fixed-strings --grep`, `rev-parse <candidate>^{tree}`, `merge-base <candidate> <branch reference>` and `log --first-parent --format=%T <merge base>..<branch reference>` in the listed repositories. It never fetches and never writes a Git reference. The only file it writes is the state file named in the settings.

An open card is a card whose status is neither `done` nor `archived`. Each finding is one line `<KIND> <card id> <status> <assignee or -> <title>`. The three checks are:

1. `NO-WAKE-SUBSCRIPTION`: an open card without a `kanban_notify_subs` row that has delivery mode `notify+wake`, a non-empty notifier profile and a non-empty user ID (the same rule as `scripts/check-notify-subscriptions`).
2. `APPROVED-NOT-INTEGRATED`: a `done` card whose latest run by the board's reviewer profile has outcome `completed`, ended within `approved_lookback_seconds` (7 days), and names a 40-character hexadecimal candidate commit in its run metadata under `candidate_commit`, `candidate` or `commit` (the first key present is used). The candidate counts as integrated when, in any listed repository, one of these checks matches, tried in this order: (a) the candidate is an ancestor of that repository's branch reference; (b) a commit on that repository's branch reference contains `cherry picked from commit <candidate>`; (c) tree comparison, used only when the candidate commit exists in that repository and (a) and (b) did not match: the script reads the candidate's tree (`rev-parse <candidate>^{tree}`) and the merge base of the candidate and the branch reference (`merge-base <candidate> <branch reference>`), and the candidate counts as integrated when one first-parent commit in `<merge base>..<branch reference>` has exactly the candidate's tree. Check (c) covers a squash merge or a rebase merge only when one first-parent commit on the branch reference has exactly the candidate's tree. When the branch reference received other changes in the same commit (for example a squash merge commit that also contains changes made on the branch reference after the candidate was approved), that commit's tree differs and the finding stays. When the candidate and the branch reference have no common ancestor, check (c) does not match in that repository. The line ends with ` commit <candidate>`, and with ` (commit not found)` when no listed repository has the commit. A value that is not 40 hexadecimal characters is skipped.
3. `STALE-BLOCKED` and `STALE-REVIEW`: a `blocked` or `review` card whose newest activity (card creation, newest event, newest comment) is older than `stale_after_seconds` (2 hours).

Repeat control: a finding is reported again only after `report_again_seconds` (12 hours). When a finding is due, the script prints the header `Board <board> check for <orchestrator profile>:` and every current finding, and the scheduler starts the agent with the cron prompt. When no finding is due, the script prints only `{"wakeAgent": false}` and the agent does not start. A settings, database, state file or Git error prints one line starting with `Board check error:`; the agent then starts and reports the error.

## Branch reference for each repository

The branch reference of a repository is the Git reference that receives finished work in that repository. By default it is the settings value `main_branch` (`main`) for every listed repository. The optional settings key `repository_branches` is a JSON object that maps a repository path to its own branch reference; a repository that is not in the object uses `main_branch`, and a settings file without the key behaves as before. Each key must be a path that appears exactly in `repositories`, and each value must be a non-empty string that does not start with `-`. Otherwise the script prints one `Board check error:` line.

chapt-orchestrator.json sets `"repository_branches": {"/Users/chanbla11mit/projects/cha-pt-frontend": "origin/main"}`, because that checkout has no local branch `main` and its `refs/remotes/origin/HEAD` points to `origin/main`.

Before the first candidate commit is checked, the script runs `git -C <repository> cat-file -e <branch reference>^{commit}` for every listed repository. If a reference does not name a commit, the error line names the repository and the reference. The ancestry check, the cherry-pick search and the tree comparison use the same branch reference of each repository.

A remote-tracking reference such as `origin/main` is only as current as the last fetch from that checkout, or the last push from that checkout that updated it. The check does not fetch, so work that reached the remote through another checkout appears on `origin/main` only after the next fetch in this checkout; until then the check can report that work as `APPROVED-NOT-INTEGRATED`.

## Provider of watched profiles (`provider_watch`)

Source card: `t_f6ea4228` (owner request of 2026-11-09, item 5: report for each Jobcron profile whether the current run is on the primary provider or on a fallback, from evidence that Hermes already records).

The optional settings key `provider_watch` is a list of objects with exactly the keys `profile` (profile name), `home` (absolute path of the profile's Hermes home) and `primary_provider` (the provider name that Hermes records for the primary model, for example `claude-subscription`). Profile names must be unique. A settings file without the key behaves as before. jobcron-orchestrator.json lists jobcron-orchestrator, jobcron-worker, jobcron-worker-2 and jobcron-reviewer, each with the primary provider `claude-subscription` and the home `/Users/chanbla11mit/.hermes/profiles/<profile>`. No other settings file has the key.

### Evidence that Hermes records

The statements below were read from the installed Hermes source at commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6` (`/Users/chanbla11mit/.hermes/hermes-agent`).

- When a fallback activates, Hermes sets the agent's model and provider to the fallback (`agent/chat_completion_helpers.py:2145`) and logs `Fallback activated: <old model> → <fallback model> (<fallback provider>)` at level INFO (`agent/chat_completion_helpers.py:1923`) for every reason except billing. For the billing reason it logs a WARNING with other text (`agent/chat_completion_helpers.py:1928-1932`). The log file is `<home>/logs/agent.log` with the rotated files `agent.log.1`, `agent.log.2` and so on; the line format is `<date> <time>,<milliseconds> <level>[ [<session id>]] <logger>: <message>` in local time (`hermes_logging.py:107`, `hermes_logging.py:372`).
- At the start of every turn Hermes restores the primary runtime (`agent/turn_context.py:1059`) and logs `Primary runtime restored for new turn` (`agent/agent_runtime_helpers.py:1514`). The fallback therefore lasts at most until the next turn (Hermes documentation `website/docs/user-guide/features/fallback-providers.md:149`, "Per-Turn, Not Per-Session").
- Every main-loop API call reports its usage with the provider and model active at that call (`agent/turn_usage.py:268`). The table `sessions` does not show a fallback: its columns `billing_provider` and `model` are filled only while they are empty (`hermes_state_usage.py:40`), and are replaced only on the first accounted call of a session (`hermes_state_usage.py:322-331`). The table `session_model_usage` does show it: every main-loop call adds to the row for its session, model, provider, base URL, billing mode and task, and sets that row's `last_seen` (`hermes_state_usage.py:52-71`, `hermes_state_usage.py:312`, `hermes_state_usage.py:337`). The main agent loop has task `''`; auxiliary work such as compression or title generation has its own task name.

### What the check reads and reports

For each listed profile the script reads two things, and the newer item decides:

1. `<home>/state.db`, opened in SQLite read-only mode: `SELECT billing_provider, model, last_seen FROM session_model_usage WHERE task = '' AND COALESCE(billing_provider, '') <> '' AND last_seen IS NOT NULL ORDER BY last_seen DESC LIMIT 1`. No other table and no other column is read; in particular no session id, message, title or content column.
2. `<home>/logs/agent.log`, then `agent.log.1`, `agent.log.2` and so on up to `agent.log.20`. From each file only lines whose record is `agent.chat_completion_helpers: Fallback activated: ... → <model> (<provider>)` at level INFO are used, and only the time, the provider and the model are kept. The model and the provider must consist of letters, digits and the characters `. _ : / @ + -`; other lines are ignored. Reading stops at the first file that holds such a record, because every rotated file is older than the file before it. A log file whose modification time is older than the newest database row is not read, because it cannot hold a newer record; the older rotated files are then not read either.

When the newest item names a provider other than `primary_provider` (compared without regard to letter case), the scheduled run prints the finding `ON-FALLBACK <profile>: <provider>/<model> at <time>` with the key `ON-FALLBACK:<profile>`, under the same repeat control as the other findings (again after `report_again_seconds`, 12 hours). `<time>` is the time of that newest item, as `YYYY-MM-DD HH:MM:SS +ZZZZ` in local time: for a database row its `last_seen`, for a log record the time of the record. It is not the start time of the fallback: the database row covers all calls of one session with that provider and model, so its first call can be older than the current fallback. When the newest item names the primary provider again, the finding disappears and its key is removed from the state file.

A missing `state.db`, a missing `session_model_usage` row for the main loop and missing log files count as no evidence, and no finding is printed. A `state.db` that cannot be read (for example a file that is not an SQLite database, or one without the table `session_model_usage`) and a log file that cannot be read produce one `Board check error:` line, as for the board database.

`--status` prints one line per listed profile and wakes nobody: `<profile>: primary <provider>`, `<profile>: fallback <provider>/<model> at <time>`, `<profile>: no evidence`, or `<profile>: error <reason>` for an unreadable `state.db` or log file. It does not read the board database, does not read or write the state file and writes no file. The scheduled run does not use `--status`. Example, run by hand on the machine where the settings file is deployed: `python3 <profile home>/scripts/orchestrator_board_check.py --status`.

### Limits

- Because the primary provider is restored at the start of the next turn, a fallback can begin and end between two scheduled runs (every 15 minutes). The check then reports nothing for it, since only the newest item is compared.
- A profile whose newest main-loop call used a fallback and that has made no call since is reported as on the fallback until its next call, every 12 hours.
- When one profile runs several sessions at the same time, only the newest call of all its sessions is compared.
- A fallback for the billing reason is logged only as a WARNING with other text, which the check does not read. The check sees such a fallback once the first call on the fallback provider is recorded in `session_model_usage`.
- A change of the profile's model or provider by the owner (for example with `/model`) also appears as a provider other than `primary_provider`, and is reported as `ON-FALLBACK`.
- The log time has no time zone; the script reads it in the local time zone of the machine that runs the check, which is the machine that wrote the log. Hermes uses another line format only for the `--verbose` console output (`hermes_logging.py:417`), not for `agent.log`.
- `ON-FALLBACK` lines have no card id. Card `t_731d4476` added the instruction for them to the cron prompt `deployment/orchestrator-board-check/cron-prompt.md`: report each line in the final report as "<profile> is running on fallback provider <provider> / <model> since <time>", and do not run kanban_show or any other card action for it. In that sentence `<time>` is the time from the line, that is, the time of the newest item as described above, not the start time of the fallback. The instruction takes effect when the cron prompt is deployed; jobcron-orchestrator's live settings file must not get `provider_watch` before that deployment.

## Output content

The output contains card ids, statuses, assignees, titles and candidate commits, and, for `provider_watch`, profile names, provider names, model names and times. It never contains card bodies, comment text, run summaries or other run metadata, and nothing from `state.db` or the log files other than the provider, the model and the time.

## Rollout for one profile

Live rollout is a separate card. Use these steps for one orchestrator profile at a time. `<profile home>` is `/Users/chanbla11mit/.hermes/profiles/<profile>`.

1. For every repository in the profile's settings file, take its branch reference (its value in `repository_branches`, otherwise `main_branch`), confirm that this reference is where finished work goes in that repository, and verify that it names a commit with `git -C <repo> rev-parse --verify --quiet <ref>^{commit}`. Correct the settings file on a harness card if a reference is wrong or the command fails.
2. Copy the script and the settings file:

   ```
   cp scripts/orchestrator-board-check <profile home>/scripts/orchestrator_board_check.py
   cp deployment/orchestrator-board-check/<profile>.json <profile home>/scripts/orchestrator_board_check.json
   ```

   The Hermes cron scheduler runs only scripts inside `HERMES_HOME/scripts/` and passes no arguments, so the script reads `orchestrator_board_check.json` from its own directory.
3. Create the cron job. Check each flag against `hermes cron create --help` before running the command:

   ```
   hermes -p <profile> cron create "every 15m" "$(cat deployment/orchestrator-board-check/cron-prompt.md)" \
     --name "<board> board check" \
     --script orchestrator_board_check.py \
     --workdir <first repository in the settings file> \
     --skill multi-agent-coding-orchestrator
   ```

   This procedure does not set `--deliver`; the rollout card chooses the delivery target.
4. Confirm the job with `hermes -p <profile> cron list`.

harness-orchestrator's own job is installed by the owner, because it changes the live setup of the controlling orchestrator itself. The existing harness-orchestrator job "harness filed-card check" stays.

## Rollback for one profile

1. Find the job id with `hermes -p <profile> cron list` and remove the job with `hermes -p <profile> cron remove <job id>`.
2. Delete `<profile home>/scripts/orchestrator_board_check.py` and `<profile home>/scripts/orchestrator_board_check.json`.
3. Delete the state file `<profile home>/cron/orchestrator_board_check_state.json`.
