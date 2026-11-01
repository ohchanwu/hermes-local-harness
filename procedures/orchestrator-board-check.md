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

The Hermes cron scheduler runs the script every 15 minutes before the agent. The script reads the board database in SQLite read-only mode and runs only the read-only Git commands `cat-file -e`, `merge-base --is-ancestor` and `log --fixed-strings --grep` in the listed repositories. It never fetches. The only file it writes is the state file named in the settings.

An open card is a card whose status is neither `done` nor `archived`. Each finding is one line `<KIND> <card id> <status> <assignee or -> <title>`. The three checks are:

1. `NO-WAKE-SUBSCRIPTION`: an open card without a `kanban_notify_subs` row that has delivery mode `notify+wake`, a non-empty notifier profile and a non-empty user ID (the same rule as `scripts/check-notify-subscriptions`).
2. `APPROVED-NOT-INTEGRATED`: a `done` card whose latest run by the board's reviewer profile has outcome `completed`, ended within `approved_lookback_seconds` (7 days), and names a 40-character hexadecimal candidate commit in its run metadata under `candidate_commit`, `candidate` or `commit` (the first key present is used). The candidate counts as integrated when, in any listed repository, it is an ancestor of `main_branch`, or a commit on `main_branch` contains `cherry picked from commit <candidate>`. The line ends with ` commit <candidate>`, and with ` (commit not found)` when no listed repository has the commit. A value that is not 40 hexadecimal characters is skipped.
3. `STALE-BLOCKED` and `STALE-REVIEW`: a `blocked` or `review` card whose newest activity (card creation, newest event, newest comment) is older than `stale_after_seconds` (2 hours).

Repeat control: a finding is reported again only after `report_again_seconds` (12 hours). When a finding is due, the script prints the header `Board <board> check for <orchestrator profile>:` and every current finding, and the scheduler starts the agent with the cron prompt. When no finding is due, the script prints only `{"wakeAgent": false}` and the agent does not start. A settings, database, state file or Git error prints one line starting with `Board check error:`; the agent then starts and reports the error.

The output contains card ids, statuses, assignees, titles and candidate commits only. It never contains card bodies, comment text, run summaries or other run metadata.

## Rollout for one profile

Live rollout is a separate card. Use these steps for one orchestrator profile at a time. `<profile home>` is `/Users/chanbla11mit/.hermes/profiles/<profile>`.

1. Confirm that `main_branch` (`main`) is the integration branch of every repository in the profile's settings file. Correct the settings file on a harness card if it is not.
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
