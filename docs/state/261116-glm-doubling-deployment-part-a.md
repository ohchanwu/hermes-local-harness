# GLM doubling deployment, part A (steps D0 to D4): record

Date: 2026-11-16 (all times KST, UTC+09:00).
Card: `t_fb32c24a` on board `harness`. Runs 596, 597 and 598 of profile `harness-worker`.
Repository baseline and integrated commit of the procedure: `81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c` (local `main`; holds cards R1 `t_18a2dc93`, R2 `t_50fd66f2`, R3 `t_cd322ae1` and R4 `t_aabef2e4`).
Specification: `procedures/jev-plugin.md` at the baseline, section "Renaming the GLM worker profiles and creating the second worker of each route", steps D0 to D4, with the changes of the card body (division of work between `harness-orchestrator` and the worker, and item 4, the fallback sentence of the three Jobcron SOULs).
Backup directory: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a` (mode 0700). Every output file named below is in this directory unless a full path is given.

No `auth.json` was opened. No `.env` file was opened or printed: the `.env` commands printed only counts, modes and `cmp` results. No name was added to `kanban.dispatch_profiles`. No gateway restart. No `hermes kanban` command against a board other than `harness` was run by the worker.

## Division of work

By the owner's decision (Telegram, 2026-11-16, after run 596), `harness-orchestrator` runs the program of "Reading the cards of the old names" (D1 steps 2, 3, 5 and 6, and the check `d2a-check`), the counts of D1 step 7, and D2a steps 1 and 2. The worker ran D0, D1 steps 1 and 4, D2, item 4 of the card, D3 and D4. The comments of `harness-orchestrator` that start with `Controller D1` and `Controller D2a` on card `t_fb32c24a` are the record of the controller's steps.

D2a and the test `d2a-check` are run by `harness-orchestrator` after the commit of this record, and are recorded in the `Controller D2a` comment on card `t_fb32c24a` and in `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/` (files `old-name-cards-d2a.json` and `old-name-cards-d2a-check.json`). The worker did not run the test `d2a-check`. This order is safe because neither an old name nor a new name is in `kanban.dispatch_profiles` until D6, so no moved card can start before then.

## Start checks

Each of runs 596, 597 and 598 checked: `git rev-parse --show-toplevel` is `/Users/chanbla11mit/hermes-local-harness/.worktrees/t_fb32c24a`; the branch is `wt/t_fb32c24a`; `HEAD`, `refs/harness/baselines/t_fb32c24a` and `git -C /Users/chanbla11mit/hermes-local-harness rev-parse main` all print `81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c`; `git status --porcelain` of the worktree and of `/Users/chanbla11mit/hermes-local-harness` print nothing. `HERMES_KANBAN_TASK` is not set in the terminal environment of the worker. Run 598 started at 18:45 KST and also read `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml`: 0.

## D0. Smoke test of `claude-sonnet-5-5` (run 596)

Command:

    python3 /Users/chanbla11mit/hermes-local-harness/plugins/model-providers/claude-subscription/smoke.py --cli /Users/chanbla11mit/.hermes/runtimes/claude-code/2.1.302/claude --model claude-sonnet-5-5

Output at 14:43:57: `SMOKE PASS cli=2.1.302 model=claude-sonnet-5-5`, exit 0. The same command ran once more as the first test of the card (section "Tests").

Rollback: none, because nothing changes.

## D1. Back up, let the existing runs finish, stop new runs on the old names

Step 1 (worker, run 596): `mkdir -p -m 700 /Users/chanbla11mit/.hermes/backups/t_fb32c24a` and `cp -p /Users/chanbla11mit/.hermes/config.yaml /Users/chanbla11mit/.hermes/backups/t_fb32c24a/config.yaml`. SHA-256 of the backup and of the live file: `a17c0da2caeec0d9ead90fb0f282b7b9999242cc9b8797c88e4f14dff575418a`.

Steps 2 and 3 (`harness-orchestrator`): files `old-name-cards-d1-2.json` (14:54) and `old-name-cards-d1-3.json` (15:27). Time limit of step 3: 30 minutes, from about 14:55 to 15:27, recorded in the comment `Controller D1 step 2`. Every reading: (a) running on an old name: `[t_bf9ac726]` (board `anki`, `anki-worker-glm-3`, run 327); (b) in review with an old implementer: `[]`; assigned to an old name: `[t_643f251b, t_bf9ac726]`.

Step 4 (worker, run 597, 15:28 to 15:42): the 15 commands `python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <old name> --to glm --dispatch remove`, in the order of the procedure.
- Before the change: SHA-256 of the live `config.yaml` equal to the step 1 backup, so the backup was not taken again. Each of the 15 old-name profiles already had the provider, model, base URL and helper settings that `--to glm` writes (0 profiles with a difference).
- Dry runs: each command first with `--dry-run`: 15 times exit 0, each printing `roster: <old name> is not declared in /Users/chanbla11mit/hermes-local-harness/roster.yaml; no roster change (dry run: nothing written)`. Output: `d1-4-dry-run.txt`.
- Applied one at a time; after each command: exit 0, the name no longer in the list, the count lower by 1, `git status --porcelain` of the repository empty. Count 14 down to 0. Output: `d1-4-apply.txt`.
- Correction recorded in run 597: the first loop stopped at the tool time limit during `jss-worker-glm-1` (15:35:56), after some `hermes config set` calls with identical values and before its dispatch write; no process remained, the profile settings were unchanged, and the command was repeated. `jss-worker-glm-1` (now `jss-worker-glm-easy-1`) therefore has two `config.yaml.pre-switch-20261116-15*` backups; the 15 profiles have 16 such files in total.
- `diff` of the step 1 backup against the live `config.yaml`: 15 removed lines, all `    - <prefix>-worker-glm-[123]`, no added line (`d1-4-config-diff.txt`). New SHA-256 `e069dfeea57b81918198a3f99079c27a48a92c36c8929143b3085fa4f338618c`.

Steps 5 and 6 (`harness-orchestrator`): readings from 15:42 to 18:42 (`old-name-cards-d1-5.json`). (a) and (b) held at 18:42, after anki card `t_bf9ac726` run 327 ended at 18:41 (reclaimed by the dispatcher: stale lock, last heartbeat at about 16:55; worker process 28672 gone). Step 6 at 18:43 (`old-name-cards-d1-6.json`): (a) `[]`; (b) `[]`; assigned to an old name: `[t_643f251b, t_bf9ac726]`.

Step 7 (`harness-orchestrator`): `kanban_notify_subs` rows with `notifier_profile LIKE '%-worker-glm-%'`: jobcron 0, cha-pt 0, harness 0, jss-genr 0, anki 0.

Check of D1: (a) and (b) are `[]` at step 5; `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml` gives 0 (15:41:39 and again at 18:45 and 18:53); `old-name-cards-d1-6.json` exists.

Rollback of D1: `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/config.yaml /Users/chanbla11mit/.hermes/config.yaml`, only while the old profiles exist (after the D2 rollback).

## D2. Rename the 15 profiles (run 598, 18:46:24 to 18:47:11)

Before the renames: the 15 old-name profile directories existed, no new-name directory existed, and `ps -axo pid,command` showed no process started for an old-name profile (pattern `(-p|--profile|profiles/)<old name>`).

Commands, one at a time, in the order of the procedure: `hermes profile rename <prefix>-worker-glm-1 <prefix>-worker-glm-easy-1`, `... -2 ... -medium-1`, `... -3 ... -hard-1` for the prefixes `jobcron`, `chapt`, `harness`, `jss`, `anki`. The loop stopped at the first exit code other than 0, the first output without `Renamed <old name> → <new name>`, or the first output with `could not migrate session identity`; it did not stop. Output: `d2-rename.txt`.

Checks:
- 15 times exit 0 and `✓ Renamed <old name> → <new name>`; each output also printed `✓ Alias updated: <new name>`, and ten of them `✓ Checkpoint identity updated: <n> project(s)`. The warning `⚠ Profile was renamed, but the live gateway could not migrate session identity` was printed 0 times.
- `hermes profile list`: 0 old names, the 15 new names.
- `served_profiles` of `/Users/chanbla11mit/.hermes/gateway_state.json`, names with `-worker-glm-`: the 15 new names and none of the old names.
- For each new name (`d2-checks.txt`): `auth.json` present (`[ -e ]` only; not opened); `grep -c '<old name>' /Users/chanbla11mit/.hermes/profiles/<new name>/profile.yaml` gives 1; the old directory no longer exists.
- The wrapper scripts in `/Users/chanbla11mit/.local/bin` have the new names.

SOULs:
- Backup of each of the 15 renamed SOULs: `mkdir -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<new name> && cp -p /Users/chanbla11mit/.hermes/profiles/<new name>/SOUL.md /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<new name>/SOUL.md`.
- The 12 profiles of `chapt`, `harness`, `jss` and `anki`: `cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<new name>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<new name>/SOUL.md`. Check: SHA-256 of each copy equals its source (12 of 12; `d2-soul-checks.txt`).
- The three Jobcron profiles: the three `sed` commands of the procedure, from the backup (`s/jobcron-worker-glm-<n>/jobcron-worker-glm-<new>/g` and `s/implementation worker <n>/implementation worker <new>/g`). Check: `diff` of each backup against the live file shows line 1 (`implementation worker <n>` to `implementation worker <new>`) and line 7 (the attachment and diff paths); applying the reverse replacements to the live file gives a file equal to the backup (`cmp`, 3 of 3); `grep -c -E 'jobcron-worker-glm-[123]([^0-9]|$)'` gives 0 for each.

Rollback of D2: for each renamed profile `hermes profile rename <new name> <old name>`, then `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<new name>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<old name>/SOUL.md`. Then the D2a rollback, and the D1 rollback if the old names are to run again. The copies of D4 must be deleted first (D4 rollback).

## Item 4 of the card. Fallback sentence in the three Jobcron SOULs (run 598, 18:48)

In `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/SOUL.md`, `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/SOUL.md` and `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/SOUL.md`, after D2 wrote them, a Python program inserted one space and the sentence directly after the first `.` of line 1 (after `You are Jobcron GLM Full implementation worker <new>.`). The program first checked that the file did not contain `claude-subscription`. Sentence for `easy-1`:

    When the Z.ai quota is used up, Hermes can switch the run to provider `claude-subscription` with model `claude-haiku-5-5`; the card is then completed in the same way, and the `jev` rules are unchanged.

For `medium-1` and `hard-1` the same sentence with `claude-sonnet-5-5`. This is the wording of line 1 of `policies/profile-souls/harness-worker-glm-easy-1/SOUL.md` and `policies/profile-souls/harness-worker-glm-medium-1/SOUL.md` at the baseline.

Checks (`item4-checks.txt`, `final-checks.txt`):
- `diff` of each backup against the live file: line 1 (name replacement and the inserted sentence) and line 7 (name replacement) only.
- The live file with the sentence removed once and the two replacements reversed is equal to the backup (3 of 3).
- `grep -c 'claude-subscription'` gives 1 for each file; the sentence occurs exactly once.
- SHA-256 after item 4: `jobcron-worker-glm-easy-1` `4edacdb314ec2cbac2be6bc2e154c2e3c45b2eb3671ec96bdad2ee59a949d25f`, `jobcron-worker-glm-medium-1` `5e5eb760aea08efac18eea46243b9d701b156ff4d9921b056b639c22e2f60b70`, `jobcron-worker-glm-hard-1` `783f334f88c45fd1443350e7d4e818914e33f76e177498f2906c3d1571a88aad`.

Rollback: the D2 SOUL rollback (`cp -p` of the backup) also removes the sentence. To keep the rename and remove only the sentence, write the file again with the D2 `sed` command from the backup.

## D2a. Move the cards of the old names (run by `harness-orchestrator` after this commit)

Not run by the worker. The cards that D2a handles are those of `old-name-cards-d1-6.json` and of the new reading `old-name-cards-d2a.json`. The file of D1 step 6 lists 2 cards:

| Board | Card | Status at 18:43 | Assignee | Implementer of the latest `review_requested` | New name |
|---|---|---|---|---|---|
| `harness` | `t_643f251b` | `blocked` | `harness-worker-glm-3` | none | `harness-worker-glm-hard-1` |
| `anki` | `t_bf9ac726` | `ready` | `anki-worker-glm-3` | `anki-worker-glm-3` | `anki-worker-glm-hard-1` |

The cards moved and commented on each board are recorded by `harness-orchestrator` in the `Controller D2a` comment on card `t_fb32c24a`.

## D3. `.env` lines and the `claude-subscription` plugin (run 598, 18:48 to 18:49)

Step 1, source check: each of `grep -c '^HERMES_CLAUDE_SUBSCRIPTION_CLI='`, `grep -c '^HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE='` and `grep -c '^HERMES_CLAUDE_SUBSCRIPTION_EFFORT='` of `/Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env` gives 1 (`d3-before.txt`). Before step 3 the 16 targets read `<profile> 0 0 0 0 600`.

Step 2: `cp -p` of the `.env` of the 16 targets (the 12 renamed profiles of `jobcron`, `chapt`, `harness`, `jss` and the reviewers `jobcron-reviewer-glm`, `chapt-reviewer-glm`, `harness-reviewer-glm`, `jss-reviewer-glm`) to `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/.env`. Check: `cmp` equal and mode 600 for 16 of 16 (`d3-step2-backups.txt`).

Step 3: the append loop of the procedure, unchanged. Check: each target had 4 lines before and 7 after, and `diff` of the backup against the live file has 0 removed or changed lines (`d3-step3-linecounts.txt`). For each target and each of the three settings, the line in the target is equal to the line in the source (`cmp` of the two `grep` outputs; 16 of 16; values not printed).

Step 4: `git -C /Users/chanbla11mit/hermes-local-harness archive 81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c plugins/model-providers/claude-subscription | tar -x -C /Users/chanbla11mit/.hermes/backups/t_fb32c24a/source`, then the copy loop of the procedure over the 20 profiles (the 15 renamed profiles and the five GLM reviewers). Before the loop, only `anki-worker-glm-easy-1`, `anki-worker-glm-medium-1`, `anki-worker-glm-hard-1` and `anki-reviewer-glm` had a copy (`d3-step4-before.txt`); these four were moved to `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/claude-subscription`.

Checks (`d3-checks.txt`):
- The `.env` check loop of the procedure prints `<profile> 1 1 1 0 600` for each of the 20 profiles.
- `diff -r -x __pycache__` of the export against each of the 20 copies prints nothing.
- SHA-256 of each of the 20 copied `compat.py` equals that of `git -C /Users/chanbla11mit/hermes-local-harness show 81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c:plugins/model-providers/claude-subscription/compat.py`: `5e0e1dca07e0298908a3e68828465984d23734ef671ed706920834ae2f62e21b`.

Rollback of D3: `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/.env /Users/chanbla11mit/.hermes/profiles/<profile>/.env` for each of the 16 targets. For each of the 20 profiles `rm -rf /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription`, and on the four anki profiles `mv /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/claude-subscription /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription`. If the profile was renamed back (D2 rollback), use the old name in the profile path.

## D4. Create the 15 new profiles by copy (run 598, 18:49:29 to 18:52)

Commands, one at a time: `hermes profile create <prefix>-worker-glm-<route>-2 --clone-from <prefix>-worker-glm-<route>-1` for the prefixes `jobcron`, `chapt`, `harness`, `jss`, `anki` and the routes `easy`, `medium`, `hard` (standard input `/dev/null`). Output: `d4-create.txt`. Each printed `Profile '<new profile>' created at /Users/chanbla11mit/.hermes/profiles/<new profile>`, `Cloned config, .env, SOUL.md, and skills from <source>.`, `Cloned installed plugins too: jev, model-providers.` and `Wrapper created: /Users/chanbla11mit/.local/bin/<new profile>`, and exited with 0. The message `This profile has no API keys yet` is expected: the Z.ai login is step D5 (owner).

Step 1: `rm -f /Users/chanbla11mit/.hermes/profiles/<new profile>/memories/MEMORY.md /Users/chanbla11mit/.hermes/profiles/<new profile>/memories/USER.md` for the 15 copies. Before: `MEMORY.md` in the copies of `jobcron-worker-glm-easy-1`, `jobcron-worker-glm-medium-1`, `chapt-worker-glm-easy-1`, `chapt-worker-glm-medium-1`, `harness-worker-glm-easy-1` and `harness-worker-glm-medium-1`; no `USER.md`. After: `memories/` is empty in all 15 (`d4-step1.txt`).

Step 2: the 12 `cp` commands from `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<new profile>/SOUL.md`, and the three `sed` commands of the procedure for the Jobcron copies, from the live SOULs of `jobcron-worker-glm-easy-1`, `jobcron-worker-glm-medium-1` and `jobcron-worker-glm-hard-1` after item 4.

Step 3 and checks (`d4-checks.txt`):
- `hermes -p <new profile> plugins list --plain --no-bundled` and the same for the source profile print the same lines (15 of 15): `enabled  git pinned@85f06a1d 0.1.0  jev` and `not enabled  user  0.1.0  claude-subscription`. The second line is the same on the source profiles. A correction is appended in `d4-checks.txt`: the first pass of the `jev` status check used the pattern `^jev`, which does not match because the `--plain` line starts with the status; the corrected check (`^enabled[[:space:]].*[[:space:]]jev$`) gives 1 for each of the 15 copies.
- `ls -a` of `plugins` of each copy equals that of its source (15 of 15). `jev` of the source was copied; the `jev` of the integrated commit was not installed (D8 does that).
- `plugins/model-providers/claude-subscription` of each copy lists the plugin files, and `diff -r -x __pycache__` against the export prints nothing (15 of 15).
- `test -e /Users/chanbla11mit/.hermes/profiles/<new profile>/auth.json || echo absent` prints `absent` for each of the 15 copies.
- The `.env` check of D3 prints `<new profile> 1 1 1 0 600` for each copy.
- SHA-256 of each of the 12 copied SOULs with a tracked source equals that of the source.
- Each Jobcron copy: `diff` against the SOUL of its source profile shows line 1 and line 7 only; the reverse replacements give a file equal to the source (`cmp`, 3 of 3); `grep -c 'claude-subscription'` gives 1; the name of the source profile occurs 0 times. SHA-256: `jobcron-worker-glm-easy-2` `9bf9db928cc711eb081911b3994aa7faa5de85ce28c309dedc496fc6825873bc`, `jobcron-worker-glm-medium-2` `87a2de34c21e89e86d5b4ebf0a5eb5b24f5d7057037b1351e2a1d09d77d8034c`, `jobcron-worker-glm-hard-2` `5f514e4dbb3fa1d810c840543a1d0df27d960a361bff8c9b46a2effe68b283a5`.

Rollback of D4: `hermes profile delete <new profile>` for each copy; the command asks `Type '<new profile>' to confirm:`; type the name. None of the copies is in `kanban.dispatch_profiles`, so no D6 rollback is needed first.

## State after part A

- `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml`: 0. `grep -cE -- '-worker-glm-(easy|medium|hard)-[12]' /Users/chanbla11mit/.hermes/config.yaml`: 0, so no new name is in `kanban.dispatch_profiles`. SHA-256 of `config.yaml` is still `e069dfeea57b81918198a3f99079c27a48a92c36c8929143b3085fa4f338618c` (after D1 step 4).
- `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain` prints nothing; local `main` is `81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c`.
- The 15 renamed profiles keep their Z.ai login; the 15 copies have none until D5.
- The subdirectories of the backup directory were created by `mkdir -p` with mode 0755; the backup directory itself has mode 0700, and each `.env` backup has mode 0600.

Not done here (deployment part B, a separate card): D5 (owner Z.ai logins of the 15 copies) and D6 to D10.

## Tests

Live tests (output file `tests.txt`, 18:53):
- `python3 /Users/chanbla11mit/hermes-local-harness/plugins/model-providers/claude-subscription/smoke.py --cli /Users/chanbla11mit/.hermes/runtimes/claude-code/2.1.302/claude --model claude-sonnet-5-5`: `SMOKE PASS cli=2.1.302 model=claude-sonnet-5-5`, exit 0.
- The program of "Reading the cards of the old names" with `<step>` `d2a-check`: run by `harness-orchestrator` after the commit (see "Division of work"); not run by the worker.
- `hermes profile list`: the 15 renamed names and the 15 copies; 0 old names.
- The `.env` check loop of D3 over the 20 profiles and the 15 copies: 35 lines `<profile> 1 1 1 0 600`.
- `for p in <the 15 copies>; do test -e /Users/chanbla11mit/.hermes/profiles/$p/auth.json || echo "$p absent"; done`: 15 lines `<copy> absent`.

Repository tests, from the worktree (outputs are in the review request of card `t_fb32c24a`, run against the commit of this record):
- `python3 scripts/verify-state --fixture tests/fixtures/clean.yaml`: exit 0, `OK: desired state matches observed state`.
- `git diff --name-only 81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c HEAD`: only `docs/state/261116-glm-doubling-deployment-part-a.md`.
- The credential pattern count of the card's Tests section (`git diff` from the baseline to `HEAD`, added lines only, `grep -cE` with the three patterns of the TypeSafe key, the Anthropic key prefix and the Z.ai key): 0. The patterns are not written in this file, because a copy of them would match itself.
- `git diff --check 81b1faf782f2af6c7a68166430dd5c1aeb7e6b3c HEAD`: nothing.
- `git status --porcelain`: empty.
