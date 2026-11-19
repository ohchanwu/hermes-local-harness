# Ponytail 5.3.3 live rollout: record

Date: 2026-11-19 (all times KST, UTC+09:00).
Card: `t_18a461e9` on board `harness`. Runs 639 and 640 of profile `harness-worker`.
Baseline: `3631fb544360a77875d45410c3fb18c8fa3c98eb` (protected ref `refs/harness/baselines/t_18a461e9`; local `main`).
Specification: `procedures/manual-apply.md` at the baseline, sections 0, 3, 3a, 3b, 3c, 4 and 4a, and the card body.
Scratch directory with the full evidence: `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/` (below: the scratch directory). This record names the files of that directory by their file names.

No `.env` value was read or printed: the only commands on `.env` files were `grep -qxF 'PONYTAIL_DEFAULT_MODE=full' <file>` (prints nothing) and the append-if-absent command of section 3b. No `auth.json` or token file was opened or copied. No gateway restart. No change to `/Users/chanbla11mit/.config/ponytail/config.json`, to the `default` profile, to `security.protected_instruction_files`, to cron jobs, or to any card other than `t_18a461e9`. Network access: anonymous `git clone` of https://github.com/DietrichGebert/ponytail.git only.

## Runs 639 and 640

Run 639 (started 17:52) ran steps 1 to 7 and started step 8 at 18:28:01. Its last heartbeat was at 18:31; the dispatcher reclaimed the run at 19:44 (`stale_lock`). The `verify-state` process of step 8 (PID 90266, parent shell PID 90233) was not stopped by the reclaim and kept running; its output goes to `verify-after.txt` and its start time and exit code go to `verify-after.meta`.

Run 640 (started 19:44) repeated no step that changes live state. It read the evidence files of run 639, checked the live state that steps 1 to 7 produced (section "Checks of run 640" below), waited for the step 8 process, and wrote this record.

Start check of run 640 (19:44): `HERMES_KANBAN_TASK` is not set in the terminal environment of the worker; `git rev-parse --show-toplevel` prints `/Users/chanbla11mit/hermes-local-harness/.worktrees/t_18a461e9`; the branch is `wt/t_18a461e9`; `HEAD` is `3631fb544360a77875d45410c3fb18c8fa3c98eb`; `git status --porcelain` prints nothing.

## Step 1: recovery point and starting state (section 0)

Starting state survey (18:01, `survey-before.txt`, one line per profile of the 56 target profiles in `targets.txt` and the ten retired profiles in `retired.txt`): 46 profiles had no `plugins/ponytail` directory; 20 profiles had `plugins/ponytail` at commit `16f29800fd2681bdf24f3eb4ccffe38be3baec6b` (Ponytail 4.8.4): `harness-worker`, `harness-worker-2`, `chapt-worker`, `chapt-worker-2`, `jobcron-worker`, `jobcron-worker-2`, `jss-worker`, `jss-worker-2`, `anki-worker`, `anki-worker-2` and the ten retired profiles. The line `PONYTAIL_DEFAULT_MODE=full` was absent from the `.env` file of all 66 profiles. All ten retired profiles exist. `plugins-before.txt` holds the install metadata entry and the `plugins list` line of ponytail of each profile before the change.

Live `verify-state` before the change (18:01:02 to 18:13:32):

    python3 /Users/chanbla11mit/hermes-local-harness/.worktrees/t_18a461e9/scripts/verify-state > verify-before.txt 2>&1

Exit code 1 (`verify-before.meta`). `grep -c FAIL verify-before.txt`: 213. `grep -c WARN verify-before.txt`: 0. 178 of the FAIL lines contain `ponytail` (plugin drift, `ponytail mode drift`); further FAIL lines that this card addresses are 21 `profile SOUL drift <profile>` lines (`verify-state` printed this line for 21 of the 47 profiles of step 5) and five `profile-local skill override drift` lines, one for each orchestrator SKILL.md of step 7.

Backups (18:01): 53 files under `/Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/backup/`:

- `backup/souls/<profile>/SOUL.md` for the 47 profiles of `policies/profile-souls/`;
- `backup/advisor/SOUL.md`;
- `backup/skills/<board>-orchestrator/SKILL.md` for anki, chapt, harness, jobcron and jss.

`backup-sha256.txt` has the SHA-256 of each of the 53 files. Run 640 check: `shasum -a 256 -c backup-sha256.txt` in `backup/` reports `OK` for all 53 files. No `.env`, `auth.json` or token file is in `backup/` (`find` for these names prints nothing).

## Step 2: section 3a, remove Ponytail 4.8.4

Commands: `step2.sh` (18:14:22 to 18:14:52, output `step2.txt`). For each of the 66 profiles: when `plugins/ponytail` is absent or at a commit other than `16f29800fd2681bdf24f3eb4ccffe38be3baec6b`, the profile is skipped; otherwise:

    hermes -p <profile> plugins remove ponytail

Skipped: the 46 profiles without the directory. Removed on the 20 profiles with commit `16f29800fd2681bdf24f3eb4ccffe38be3baec6b` (list in step 1). Each of the 20 commands exited 0 and printed `✗ Plugin ponytail removed from /Users/chanbla11mit/.hermes/profiles/<profile>/plugins`; after each, the directory was absent and the install metadata had no `ponytail` entry.

Rollback: none needed. Ponytail 4.8.4 was installed and disabled; reinstalling it would contradict the desired state of section 3.

## Step 3: section 3b, the 56 target profiles

Commands: `step3.sh enable <profile>...` for the 56 profiles of `targets.txt` (first `harness-orchestrator` alone, 18:15:26 to 18:15:36, output `step3-part1.txt`; then the other 55, 18:15:45 to 18:25:09, output `step3-part2.txt`). For each profile, in this order, with the result of a step checked before the step and the step skipped when its result exists:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/ponytail rev-parse HEAD
    hermes -p <profile> plugins adopt ponytail
    hermes -p <profile> plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/<profile>/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/<profile>/.env
    hermes -p <profile> plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'

Result for all 56 profiles: clone exit 0, checkout exit 0, `rev-parse HEAD` printed `7801d061243d7b753bad0e0b3c057cd250b11755`, adopt exit 0 (`✓ Adopted ponytail (source: https://github.com/DietrichGebert/ponytail.git, revision: 7801d061243d). It is now a tracked git install.`), enable exit 0, `.env` line appended (exit 0) and then found by `grep -qxF`, and the verification line is `enabled      git      5.3.3    ponytail`, equal to the expected output of the procedure. No step was skipped, no mismatch, no profile was stopped.

Each enable command printed `✓ Plugin ponytail enabled. Takes effect on next session. Gateway reloaded plugins — active in the running gateway now: gateway_commands, gateway_transforms, hooks.`

Rollback for one profile: `hermes -p <profile> plugins disable ponytail`, and delete the one line `PONYTAIL_DEFAULT_MODE=full` from `/Users/chanbla11mit/.hermes/profiles/<profile>/.env` (the append also added one empty line before it, which has no effect). The 56 profiles: harness-orchestrator harness-reviewer harness-reviewer-glm harness-worker harness-worker-2 harness-worker-glm-easy-1 harness-worker-glm-easy-2 harness-worker-glm-medium-1 harness-worker-glm-medium-2 harness-worker-glm-hard-1 harness-worker-glm-hard-2 chapt-orchestrator chapt-reviewer chapt-reviewer-glm chapt-worker chapt-worker-2 chapt-worker-glm-easy-1 chapt-worker-glm-easy-2 chapt-worker-glm-medium-1 chapt-worker-glm-medium-2 chapt-worker-glm-hard-1 chapt-worker-glm-hard-2 jobcron-orchestrator jobcron-reviewer jobcron-reviewer-glm jobcron-worker jobcron-worker-2 jobcron-worker-glm-easy-1 jobcron-worker-glm-easy-2 jobcron-worker-glm-medium-1 jobcron-worker-glm-medium-2 jobcron-worker-glm-hard-1 jobcron-worker-glm-hard-2 jss-orchestrator jss-reviewer jss-reviewer-glm jss-worker jss-worker-2 jss-worker-glm-easy-1 jss-worker-glm-easy-2 jss-worker-glm-medium-1 jss-worker-glm-medium-2 jss-worker-glm-hard-1 jss-worker-glm-hard-2 anki-orchestrator anki-reviewer anki-reviewer-glm anki-worker anki-worker-2 anki-worker-glm-easy-1 anki-worker-glm-easy-2 anki-worker-glm-medium-1 anki-worker-glm-medium-2 anki-worker-glm-hard-1 anki-worker-glm-hard-2 advisor.

## Step 4: section 3c, the ten retired profiles

Commands: `step3.sh disable worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2 worker-terra-1 worker-terra-2 worker-glm-full worker-sol worker-astra` (18:25:25 to 18:27:11, output `step4.txt`): the clone, checkout, `rev-parse HEAD` and adopt commands of step 3, then `hermes -p <profile> plugins disable ponytail`, no `.env` command, and the verification `hermes -p <profile> plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'`.

All ten profiles exist; none was skipped. Result for all ten: clone, checkout and adopt exit 0, `rev-parse HEAD` printed `7801d061243d7b753bad0e0b3c057cd250b11755`, disable exit 0 (`⊘ Plugin ponytail disabled. Takes effect on next session.`), verification line `disabled     git      5.3.3    ponytail`. No mismatch.

Rollback: none needed while the plugin is disabled; `hermes -p <profile> plugins remove ponytail` removes the copy.

## Step 5: the 47 SOUL files

Check (18:04, outputs `soul-check.txt` and `soul-diff-before.txt`): for each directory under `policies/profile-souls/`, `diff policies/profile-souls/<profile>/SOUL.md` against the backup of `/Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md`. For all 47 profiles the diff has one change that adds two lines to the live file: the paragraph that starts "These wording rules take precedence over the instructions that the Ponytail plugin" and its blank line; no line is removed or changed. No profile was recorded as different in other lines.

Copy (18:27:23, output `step5.txt`): `cp policies/profile-souls/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md` for all 47 profiles; `cmp` after each copy reports equal.

Rollback for one profile: `cp /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/backup/souls/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md`.

## Step 6: advisor SOUL

`/Users/chanbla11mit/.hermes/profiles/advisor/SOUL.md` had 18 lines; `# Terminology and wording` is line 13 and is the last section, so the last paragraph of the section is the end of the file. The file had no line feed after its last line; the new paragraph keeps that form. Unified diff against the backup (18:27, `step6-advisor.diff`; run 640 created the diff again and `cmp` reports it equal to the file):

    --- /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/backup/advisor/SOUL.md	2026-10-20 13:48:24
    +++ /Users/chanbla11mit/.hermes/profiles/advisor/SOUL.md	2026-11-19 18:27:42
    @@ -16,4 +16,6 @@
     - A project-specific term is permitted only if it is defined in the relevant glossary and marked "(project term)" on first use in each document, card, commit message, or reply. For a project repository that is docs/GLOSSARY.md; for this advisor profile it is ~/.hermes/profiles/advisor/GLOSSARY.md. When unsure whether a term is standard, say so and use the plain phrase.
     - Do not use metaphors or analogies unless the user explicitly asks to be taught. Even then, introduce no new terms.
     - Prefer longer precise wording over shorter clever wording. Boring, literal, technically exact language is the goal.
    -- This applies to chat replies, Kanban cards, commit messages, documentation, code comments, test strings, and new identifiers.
    -\ No newline at end of file
    +- This applies to chat replies, Kanban cards, commit messages, documentation, code comments, test strings, and new identifiers.
    +
    +These wording rules take precedence over the instructions that the Ponytail plugin adds to each turn. Do not write the Ponytail code comment marker `shortcut:`; write a plain code comment that states the known limit and the condition for changing the code.
    +\ No newline at end of file

(The `~` in the context lines is the existing text of the advisor file.) The only change to the line that was last is the added line feed. The paragraph text is equal to line 18 of `policies/profile-souls/harness-worker/SOUL.md`. The file now has 20 lines.

Rollback: `cp /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/backup/advisor/SOUL.md /Users/chanbla11mit/.hermes/profiles/advisor/SOUL.md`.

## Step 7: the five orchestrator skills (sections 4 and 4a)

Check (18:04, `skill-check.txt`): for each board, the live `/Users/chanbla11mit/.hermes/profiles/<board>-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` was compared with `git show <commit>:policies/profile-skills/<board>-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` for each commit of `git log --format=%H -- <path>`. Each of the five live files is byte-equal to the file at commit `5bc2ecf8af666758ff5cf2d3192fc00423dabbb3` (2026-11-16, "Give the 30 GLM worker profiles the names of their routes in the repository (t_18a2dc93)"; an ancestor of `main`). Run 640 compared the five backups with that commit again: equal. Live versions before the copy, equal to the expected versions of the card: anki `0.6.10-anki.13`, chapt `0.6.7-chapt.17`, harness `0.6.7-harness.15`, jobcron `0.6.9-jobcron.18`, jss `0.6.7-jss.19`.

Copy (18:27:52 to 18:27:53, `step7.txt`): `cp policies/profile-skills/<board>-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/<board>-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`; only SKILL.md was copied. After each copy, `cmp` reports equal. New versions: anki `0.6.10-anki.14`, chapt `0.6.7-chapt.18`, harness `0.6.7-harness.17`, jobcron `0.6.9-jobcron.19`, jss `0.6.7-jss.20`. No file was left unchanged.

Commits that the copies deploy (`git log 5bc2ecf8..3631fb5 -- <path>`): `a9c8123` (card `t_0c1ccf16`, Ponytail Skills section) on all five; `5fa77a0` (card `t_40028345`) on `harness-orchestrator` only. Card `t_77cc3308` (merge `510c057`) changed only `procedures/jev-plugin.md` and no skill file, so the `harness-orchestrator` copy contains no change of that card.

Section 4a (curator pin): the read-only command of section 4a for skill `multi-agent-coding-orchestrator` on each of the five orchestrator profiles printed `learn`, `False`, `active` (`step7-usage-before-pin.txt`). `created_by` is `learn`, not `agent`, so the curator does not manage these copies and section 4a requires no pin. No `curator pin` command was run.

Rollback for one board: `cp /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/backup/skills/<board>-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/<board>-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`.

## Checks of run 640

Run 640 checked the live state again (19:46), without any change:

- `git -C /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/ponytail rev-parse HEAD` prints `7801d061243d7b753bad0e0b3c057cd250b11755` for all 56 target profiles and all ten retired profiles.
- `grep -qx 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/<profile>/.env` succeeds for all 56 target profiles.
- `cmp -s` of each of the 47 `policies/profile-souls/<profile>/SOUL.md` with the live file: all equal.
- `cmp -s` of each of the five repository orchestrator SKILL.md files with the live file: all equal.
- `grep -c 'take precedence over the instructions that the Ponytail plugin' /Users/chanbla11mit/.hermes/profiles/advisor/SOUL.md`: 1.

## Step 8: final state

Command (started by run 639 at 18:28:01 from the worktree root, after steps 1 to 7; ended 19:53:07; exit code 1 in `verify-after.meta`):

    python3 scripts/verify-state > /Users/chanbla11mit/.hermes/profiles/harness-worker/cache/scratch/t_18a461e9/verify-after.txt 2>&1

This is the first test command of the card. No live state changed between the start of this command and the end of run 640. The run took 85 minutes; the run of step 1 took 12.5 minutes. Run 640 did not start the command a second time, because a second run of the same length could exceed the runtime cap of the card and would overwrite `verify-after.txt` while it runs.

Results (19:53):

- `grep -i ponytail verify-after.txt | grep -E 'FAIL|WARN'` prints nothing.
- `grep -c FAIL`: `verify-before.txt` 213, `verify-after.txt` 9. `grep -c WARN verify-after.txt`: 0.
- FAIL lines that are in `verify-after.txt` and not in `verify-before.txt` (`comm -13` of the two sorted lists of FAIL lines): none.
- FAIL lines that are in `verify-before.txt` and not in `verify-after.txt`: 204; 122 `plugin drift` lines and 56 `ponytail mode drift` lines (steps 2 to 4), 21 `profile SOUL drift` lines (step 5), and five `profile-local skill override drift` lines, one for each orchestrator SKILL.md (step 7).

The nine FAIL lines of `verify-after.txt`, all present in `verify-before.txt` and outside the steps of this card:

    FAIL: terminal notification runtime pending gateway: running gateway has not inherited HERMES_TERMINAL_OUTBOX (hermes gateway restart required)
    FAIL: multi-board gateway is still pinned to one database via HERMES_KANBAN_DB: /Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db
    FAIL: unable to read open Cha PT card list
    FAIL: unable to read open project card list jobcron
    FAIL: unable to read open project card list cha-pt
    FAIL: unable to read open project card list harness
    FAIL: unable to read open project card list jss-genr
    FAIL: unable to read open project card list anki
    FAIL: deployed skill hash mismatch: multi-agent-coding-orchestrator default/SKILL.md

The first two need a gateway restart, which this card does not allow. The six card list lines come from the card reads of `verify-state` for other boards; this card does not read other boards. The last line is about the `default` profile, which this card does not change.

## Running gateway and workers

Each running gateway and worker loads Ponytail, the new SOUL text and the new skill text only after it restarts; a new worker session that the dispatcher starts after 18:28 reads the new files. `ps` at 19:47 shows one gateway process, `gateway run --external-supervisor` (PID 1217, started by PID 1049 and PID 800), with no `-p` argument and working directory `/Users/chanbla11mit/.hermes`: it is the gateway of profile `default`, and it also runs the dispatcher. No gateway of another profile runs. The enable commands of step 3 printed that the running gateway reloaded the plugin hooks; this record does not depend on that message.
