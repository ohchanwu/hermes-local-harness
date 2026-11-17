# GLM doubling deployment, part B (steps D6 to D10): record

Date: 2026-11-16 (all times KST, UTC+09:00).
Card: `t_653b7074` on board `harness`. Runs 600 and 601 of profile `harness-worker` (see "Runs 600 and 601" below).
Repository baseline and integrated commit of the procedure: `a34f62497cc135ed02f79341940bf7d6e75dc35b` (local `main`; holds cards R1 to R4 and the merge of the part A record of card `t_fb32c24a`). `plugins/jev/config.json` at this commit has SHA-256 `e38270e61aef43a76e68a1b41b27ba7e39930a1798490908198cae589a47ac00`.
Specification: `procedures/jev-plugin.md` at the baseline, section "Renaming the GLM worker profiles and creating the second worker of each route", steps D6, D7, D8 steps 1 to 3, D9 and D10, with `<card id>` = `t_fb32c24a` for every backup path, and with the order and changes of the card body.
Backup directory: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a` (mode 0700, the directory of part A). The output files of this card are in its subdirectory `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/part-b` (mode 0700); every output file named below is there unless a full path is given. The scripts that ran the loops are in `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/` (`d6.sh`, `d6_check.py`, `d7_2.sh`, `d8.sh`, `d8_check.sh`, `d9.sh`).

No `auth.json` was opened. No `.env` file was opened or printed. No `hermes kanban` command against a board other than `harness` was run by the worker, and the worker did not run the program of "Reading the cards of the old names". No gateway restart. No model call. `security.protected_instruction_files` was read only.

## Division of work

By the owner's decision of 2026-11-16 (card body), `harness-orchestrator` runs D8 step 4 and the card check of D10 (the program of "Reading the cards of the old names" with `<step>` `d8` and `d10`, and the moves and comments of D2a steps 1 and 2) after the review request of this card, and records them in comments on card `t_653b7074` that start with `Controller D8` and `Controller D10`. The worker ran D7 step 1, D6, D7 step 2, D8 steps 1 to 3 and their checks except the card program, D9 and the verifier run of D10.

## Start check (19:22)

`HERMES_KANBAN_TASK` is not set in the terminal environment of the worker. `git rev-parse --show-toplevel` is `/Users/chanbla11mit/hermes-local-harness/.worktrees/t_653b7074`; the branch is `wt/t_653b7074`; `HEAD`, `refs/harness/baselines/t_653b7074` and `git -C /Users/chanbla11mit/hermes-local-harness rev-parse main` all print `a34f62497cc135ed02f79341940bf7d6e75dc35b`; the checked-out branch of the main checkout is `main`; `git status --porcelain` of the worktree and of `/Users/chanbla11mit/hermes-local-harness` print nothing.

Read-only checks before D6 (19:25):
- `roster.yaml` of the main checkout is equal to `json.dumps(json.loads(<file>), indent=2) + "\n"`, so the roster write of `scripts/switch-profile-model --to glm` (line 221) gives an equal file when the model and provider are unchanged.
- The live `kanban.dispatch_profiles` (20 entries) is equal to the `kanban.dispatch_profiles` of `snapshots/sanitized-current-state.yaml` (50 entries) without its 30 GLM worker names, and those 30 names are the last 30 entries of the snapshot, in the order of the D6 commands.
- Each of the 35 profiles of D6 has a `roster.yaml` entry with model `glm-5.3`, provider `zai`, a `fallback_providers` entry with provider `claude-subscription` (`claude-haiku-5-5` on the ten `easy` workers, `claude-sonnet-5-5` on the others) and 16 `auxiliary_fallback_chain` entries.
- SHA-256 of `/Users/chanbla11mit/.hermes/config.yaml`: `e069dfeea57b81918198a3f99079c27a48a92c36c8929143b3085fa4f338618c`, the value after part A D1 step 4. Copy: `config.yaml.pre-d6`.

## Runs 600 and 601

Run 600 started the D6 loop at 19:32:57 as `bash /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/d6.sh apply` (pid 35606). At 20:18 the dispatcher recorded run 600 as `crashed` ("pid 3279 not alive") and started run 601, while pid 3279 and the D6 loop were still running. `harness-orchestrator` reported this at 20:13 as a false crash report and told run 601 not to run any D6 command and not to write `/Users/chanbla11mit/.hermes/config.yaml` until `pgrep -f 't_653b7074/d6.sh apply'` printed nothing. Run 601 waited; the loop wrote `done 20:18:01 count 50`, and `harness-orchestrator` stopped pid 3279 at 20:19:57. Run 601 did not run any D6 command again; it ran the D6 checks and the steps after D6.

## D7 step 1: the ten reviewer SOULs (19:32, before D6)

Commands: the loop of D7 step 1 for `jobcron-reviewer chapt-reviewer harness-reviewer jss-reviewer anki-reviewer jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm`, with `<card id>` = `t_fb32c24a`. Output: `d7-1.txt` (SHA-256 of each live file before and after, and of its tracked source).

Backups: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SOUL.md` for the ten profiles.

Check (19:32:02), `shasum -a 256` of each live file against `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md`:

    jobcron-reviewer      5d4ef7ff259d4d74b57cd4deed8b2e17c3db6af4f527786c06ac0bdca1c2a15f EQUAL
    chapt-reviewer        09905bd9a9a90f0164a39a2ff99bf79de86d421feb502216f463e1a5defb4403 EQUAL
    harness-reviewer      4f5a8b708fab370a5f8600c83fe9852a50cb8bda4994a837ae8f11613b59a45e EQUAL
    jss-reviewer          17cf2e539bab0ab341f47df356acad35e318b5da2ada7e15776c4b408748900c EQUAL
    anki-reviewer         594eb1eb4561a7403311a7f92461ec563a63c409ecf41d2e0724e9d5ff37ced1 EQUAL
    jobcron-reviewer-glm  867f6fa7ef2ecf43cf518cfd61127041982d65bc0c4404ff4b7ad46b140c6837 EQUAL
    chapt-reviewer-glm    250a402b79a256d2e421e84f41078ad29bf3f7b37dc81e1fd083d3f0f3db6ea1 EQUAL
    harness-reviewer-glm  a20fb8ed0373ce8ff75b9b9260b80c0d93f613f3053055b99dc164618651aad8 EQUAL
    jss-reviewer-glm      9588b2e49522ce77d718bb68dc1d18766f58c06007758feef8d334ed9ebaa0f7 EQUAL
    anki-reviewer-glm     ff18f163c2aff8e4259a98caf38d0051d44cf06236267c0445fde86bdd5a889d EQUAL
    equal 10 of 10

Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md` for each of the ten profiles.

## D6: `fallback_providers`, helper fallback chains and `kanban.dispatch_profiles` (19:32 to 20:18)

Dry run (19:32): `d6.sh dry` ran the 35 commands of D6 with `--dry-run` added, in the order of the procedure. Output `d6-dry-run.txt`: 35 sections, each `exit 0`.

Apply (19:32:57 to 20:18:01): `d6.sh apply` ran the 30 worker commands (`--to glm --dispatch add --apply-fallbacks`) and then the 5 reviewer commands (`--apply-fallbacks`), one at a time, in the order of the procedure. After each command the script recorded the exit code, the length and last entry of `kanban.dispatch_profiles` (read with the expression of the D6 check) and the line count of `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain`, and it would have stopped on a non-zero exit, on a length that did not grow by one (workers) or that changed (reviewers), on a last entry other than the profile, or on a repository change. Output `d6-apply.txt`: `start 19:32:57 count 20`; 35 lines with `exit 0` and `git_changes 0`; the worker lines go from `count 20->21 last jobcron-worker-glm-easy-1` to `count 49->50 last anki-worker-glm-hard-2`; the reviewer lines all have `count 50->50`; no `STOP` line; `done 20:18:01 count 50`. Every `roster:` line has `model glm-5.3 -> glm-5.3, provider zai -> zai`, and the main checkout stayed clean after every command.

Backups: `scripts/switch-profile-model` (line 208) wrote `/Users/chanbla11mit/.hermes/profiles/<profile>/config.yaml.pre-switch-20261116-<time>` before each of the 35 writes (35 `backup` lines in `d6-apply.txt`). The global `/Users/chanbla11mit/.hermes/config.yaml` before D6 is in `config.yaml.pre-d6` (SHA-256 `e069dfeea57b81918198a3f99079c27a48a92c36c8929143b3085fa4f338618c`); after D6 its SHA-256 is `41b684530a19389a9b1fccafef8ecb49134ed979727701b6c4ab150fa7c6a92f`.

Check of the 35 declarations (20:20 to 20:24, run 601): `python3 /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/d6_check.py`, which runs `hermes -p <profile> config get --json` for `fallback_providers`, `auxiliary.title_generation.fallback_chain`, `auxiliary.compression.fallback_chain` and `auxiliary`, and compares them with the card R2 entry of the profile in `/Users/chanbla11mit/hermes-local-harness/roster.yaml`. Output `d6-checks.txt` (one line per profile):

    profiles 35; different 0; with an anthropic entry 0
    35 profiles: OK, 16 helper fallback chains each, each equal to the roster declaration
    fallback_providers [{"provider": "claude-subscription", "model": "claude-haiku-5-5"}]   10 profiles: the ten *-worker-glm-easy-1 and *-worker-glm-easy-2
    fallback_providers [{"provider": "claude-subscription", "model": "claude-sonnet-5-5"}]  25 profiles: the other 20 GLM workers and the 5 GLM reviewers
    auxiliary.title_generation.fallback_chain [{"provider": "claude-subscription", "model": "claude-haiku-5-5"}]  35 profiles
    auxiliary.compression.fallback_chain [{"provider": "claude-subscription", "model": "claude-haiku-5-5"}]   10 profiles (the easy workers)
    auxiliary.compression.fallback_chain [{"provider": "claude-subscription", "model": "claude-sonnet-5-5"}]  25 profiles

No `fallback_providers` entry and no helper fallback chain entry of the 35 profiles has provider `anthropic`.

Check of the dispatch list and `security.protected_instruction_files` (20:20:23). Output `d6-dispatch-and-protected.txt`:

    True 50 50
    grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml: 0
    git -C /Users/chanbla11mit/hermes-local-harness status --porcelain: 0 lines; main a34f62497cc135ed02f79341940bf7d6e75dc35b
    harness-worker-glm-easy-1 false
    harness-worker-glm-easy-2 false
    harness-worker-glm-medium-1 false
    harness-worker-glm-medium-2 false
    harness-worker-glm-hard-1 false
    harness-worker-glm-hard-2 false

Rollback: as in D6 of the procedure: for each of the 30 GLM workers `python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch remove --clear-fallbacks`; for each GLM reviewer `python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <reviewer> --clear-fallbacks`. The list before D6 can also be restored with `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/part-b/config.yaml.pre-d6 /Users/chanbla11mit/.hermes/config.yaml`.

## D7 step 2: five orchestrator SOULs and four orchestrator skills (20:26)

Commands: the two loops of D7 step 2 with `<card id>` = `t_fb32c24a`, run by `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/d7_2.sh` (every copy exit 0). Output: `d7-2.txt` (SHA-256 of each live file before and after, of its tracked source and of its backup).

Backups: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SOUL.md` for `jobcron-orchestrator`, `chapt-orchestrator`, `harness-orchestrator`, `jss-orchestrator` and `anki-orchestrator`; `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SKILL.md` for `anki-orchestrator`, `chapt-orchestrator`, `jobcron-orchestrator` and `jss-orchestrator`. None of these backup directories existed before this step.

Check (20:26:15), `shasum -a 256` of each live file against its tracked source in `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md` or `/Users/chanbla11mit/hermes-local-harness/policies/profile-skills/<profile>/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`:

    jobcron-orchestrator SOUL   a7a63bd412f82db1be88e074a3fe793da033ff52b7dfb7118b650b1d2ff021ec EQUAL
    chapt-orchestrator SOUL     d988cc94dd1766f5683769286bfd0e8f31c20da00755e906aba4699ad711fcac EQUAL
    harness-orchestrator SOUL   9106df2660186313ea964728db5bafa3b0ab0739cbad6555eef83f1ab85d6bca EQUAL
    jss-orchestrator SOUL       d7d71aa14f18521f19f10f4a776eb322641b4c4b5f01b3a515ed39d6389b3a14 EQUAL
    anki-orchestrator SOUL      269b48d6a0ff939660faeab89978563495a1dc0a74cb8ffcbcf88ae03af24306 EQUAL
    anki-orchestrator SKILL     eeb9a372e49d1e1dd6c74ad1e5d845b3b8d04e7d6e6b81f26f3375a95c1287ac EQUAL
    chapt-orchestrator SKILL    86138bcfaf855e60164e8854a8fb81b49389c95f7f816a9c455c07f52afdd316 EQUAL
    jobcron-orchestrator SKILL  9b6643399ff54c92c0de8e679ed4d13fcc9218fad24ecc89bee8969f68b3e201 EQUAL
    jss-orchestrator SKILL      c94502941c2dc18c5bca31a55f997854a5b7c875eeb6dbe9c1ac46d37be7eba8 EQUAL
    equal 9 of 9

Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md` and `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/SKILL.md /Users/chanbla11mit/.hermes/profiles/<profile>/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` for each changed file.

## D8 steps 1 to 3: `jev` install of the integrated commit (20:27 to 20:38)

Step 1 (20:27): `d8.sh metadata` ran the loop of D8 step 1 with `<card id>` = `t_fb32c24a` for the 56 profiles, in the order of the procedure (no `FAIL` line; output `d8-metadata.txt` is empty). Backups: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/install-metadata.json` for the 56 profiles. In all 56 the `jev` entry is `revision` `85f06a1d7829460aa7bdb7aa935ed90de833ff42`, `pinned` `true`, `source` `file:///Users/chanbla11mit/hermes-local-harness#plugins/jev`; this is the rollback reference. Before step 2, `/Users/chanbla11mit/.hermes/jev/logs/peak-hold.out.log` had 37933 lines (`peak-hold.out.lines.before-d8-run601`) and `/Users/chanbla11mit/.hermes/jev/logs/peak-hold.err.log` had 0 lines.

Step 2 (20:28:04 to 20:35:08): `d8.sh install` ran, for each of the 56 profiles in the order of the procedure, `hermes -p <profile> plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref a34f62497cc135ed02f79341940bf7d6e75dc35b --enable --force` with standard input from `/dev/null`, wrote the output to `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/jev-install.log`, and would have stopped after an output that names `caution` or `dangerous` or after a non-zero exit. Output `d8-install-summary.txt`: 56 lines `<time> <profile> exit 0 reloaded 1`, no `stop` line. No install log names `caution` or `dangerous` (`grep -ciE 'caution|dangerous'` over the 56 logs: 0). Each log has the two warnings about a custom source and a local URL scheme, the `Installed` panel with the profile's plugin location, `Replacement installed; plugin selection was not changed.` and `Gateway reloaded plugins — active in the running gateway now: gateway_transforms, hooks.`; the logs differ only in the profile name and in the line wrapping of the location. The reload of plugins is part of the install command; no gateway was restarted.

Step 3 and the checks (20:36:33 to 20:38:48): `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/d8_check.sh`. Output `d8-checks.txt` (one line per profile):

    step 3: HEAD a34f62497cc135ed02f79341940bf7d6e75dc35b main a34f62497cc135ed02f79341940bf7d6e75dc35b status lines 0
    tracked config.json e38270e61aef43a76e68a1b41b27ba7e39930a1798490908198cae589a47ac00   (git show a34f62497cc135ed02f79341940bf7d6e75dc35b:plugins/jev/config.json | shasum -a 256)
    56 x: enabled git pinned@a34f6249 0.1.0 jev | config.json e38270e61aef43a76e68a1b41b27ba7e39930a1798490908198cae589a47ac00 | revision a34f62497cc135ed02f79341940bf7d6e75dc35b
    profiles 56; jev enabled 56; config.json equal 56
    peak-hold.out.log lines 38051 (before D8 in run 601: 37933)
    peak-hold.err.log lines 0

The `jev` line is from `hermes -p <profile> plugins list --plain --no-bundled`; `revision` is from `/Users/chanbla11mit/.hermes/profiles/<profile>/plugins/.install-metadata.json`. Read at 20:40, the lines of `peak-hold.out.log` after line 37933 are 60 lines `nothing to hold or release` and 60 lines `no card to pass to the Opus reviewer` (two lines more than at the check, written after it); `tail -3` of the two logs shows these lines and no error.

Step 4 and the card program of the D8 check are run by `harness-orchestrator` after the review request (comment `Controller D8`).

Rollback: on each profile, `hermes -p <profile> plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref 85f06a1d7829460aa7bdb7aa935ed90de833ff42 --enable --force` (the revision of `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/<profile>/install-metadata.json`).

## D9: harness-orchestrator skill copy (20:39)

Commands: the two commands of D9 with `<card id>` = `t_fb32c24a`, run by `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/d9.sh` (copy exit 0). Output `d9.txt`.

Backup: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/harness-orchestrator/SKILL.md` (SHA-256 `a2f69024a1492f4848b1c1f27eab9ff0e97bf9a7ecafec1d8b94e69ea4b0e2c3`, the live file before the copy; no backup file was there before).

Check, `shasum -a 256`:

    live   /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md                     818bd5f382885c823fcbc3a20c9fa5fdb7ce4fe882408c5fafd5e7a24d440244
    source /Users/chanbla11mit/hermes-local-harness/policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md  818bd5f382885c823fcbc3a20c9fa5fdb7ce4fe882408c5fafd5e7a24d440244
    EQUAL

Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/t_fb32c24a/harness-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`.

## D10: verifier (20:46:34 to 21:02:07)

Command: `python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state`, run from `/Users/chanbla11mit/hermes-local-harness` in the terminal environment of the worker, which keeps `HERMES_KANBAN_DB` (`/Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db`) as the card requires. Output: `verify-d10.txt` (8 lines), `verify-d10.stderr.txt` (empty), `verify-d10.exit.txt` (`verify exit 1 end 21:02:07`). A first start at 20:39 was stopped when the terminal call reached its 400-second limit and wrote no output; run 600's start at 19:24 (`verify-before-part-b.txt`) is also empty.

    FAIL: multi-board gateway is still pinned to one database via HERMES_KANBAN_DB: /Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db
    FAIL: unable to read open Cha PT card list
    FAIL: unable to read open project card list jobcron
    FAIL: unable to read open project card list cha-pt
    FAIL: unable to read open project card list harness
    FAIL: unable to read open project card list jss-genr
    FAIL: unable to read open project card list anki
    FAIL: deployed skill hash mismatch: multi-agent-coding-orchestrator default/SKILL.md

Comparison with the last recorded live run, the run of `harness-reviewer` for card `t_e61ee47c` at 07:19 (`/Users/chanbla11mit/.hermes/profiles/harness-reviewer/cache/scratch/t_e61ee47c/verify-review.txt`, copy `verify-last-recorded-live-t_e61ee47c-0719.txt`, `rc=1`): `comm` of the two sorted line sets prints no new line and no removed line; the 8 lines are the same.

Lines that name one of the 30 GLM workers or the five GLM reviewers: none. Lines `fallback drift`: none (`grep -cE 'worker-glm|reviewer-glm|fallback drift' verify-d10.txt` prints 0). There is no new failure for these 35 profiles.

The card check of D10 (D2a steps 1 and 2 with `<step>` `d10`) is run by `harness-orchestrator` after the review request (comment `Controller D10`).

Rollback: none; the verifier writes nothing.

## Tests

- D6 dispatch list program: `True 50 50` (20:20:23); `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml`: `0`.
- `hermes -p <profile> config get --json fallback_providers` for the 35 profiles of D6: the entry of card R2 on all 35 (`d6-checks.txt`: `profiles 35; different 0; with an anthropic entry 0`).
- `shasum -a 256` checks of D7 and D9: `equal 10 of 10` (D7 step 1), `equal 9 of 9` (D7 step 2), `EQUAL` (D9).
- `jev` checks of D8: `profiles 56; jev enabled 56; config.json equal 56`.
- `python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state`: exit 1, the same 8 lines as the last recorded live run, none for the 35 GLM profiles (D10 above).
- From the worktree, `python3 scripts/verify-state --fixture tests/fixtures/clean.yaml`: `OK: desired state matches observed state`, exit 0.
- The git checks of the card from the worktree: see the review request of card `t_653b7074`, run after the last commit of this file.
