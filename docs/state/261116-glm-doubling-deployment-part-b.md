# GLM doubling deployment, part B (steps D6 to D10): record

Date: 2026-11-16 (all times KST, UTC+09:00).
Card: `t_653b7074` on board `harness`. Runs 600 and 601 of profile `harness-worker` (see "Runs 600 and 601" below).
Repository baseline and integrated commit of the procedure: `a34f62497cc135ed02f79341940bf7d6e75dc35b` (local `main`; holds cards R1 to R4 and the merge of the part A record of card `t_fb32c24a`). `plugins/jev/config.json` at this commit has SHA-256 `e38270e61aef43a76e68a1b41b27ba7e39930a1798490908198cae589a47ac00`.
Specification: `procedures/jev-plugin.md` at the baseline, section "Renaming the GLM worker profiles and creating the second worker of each route", steps D6, D7, D8 steps 1 to 3, D9 and D10, with `<card id>` = `t_fb32c24a` for every backup path, and with the order and changes of the card body.
Backup directory: `/Users/chanbla11mit/.hermes/backups/t_fb32c24a` (mode 0700, the directory of part A). The output files of this card are in its subdirectory `/Users/chanbla11mit/.hermes/backups/t_fb32c24a/part-b` (mode 0700); every output file named below is there unless a full path is given. The scripts that ran the loops are in `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_653b7074/` (`d6.sh`, `d6_check.py`, `d7_2.sh`, `d8.sh`).

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
