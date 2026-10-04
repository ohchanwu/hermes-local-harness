# Manual apply / reconstruction procedure

Reconstruct the non-secret harness from this repository using supported Hermes CLI commands only. No apply script exists by design. The project-fleet command forms were reverified against Hermes `v0.21.5+6751.g9cf7960` on 2026-10-04.

Global settings are scoped: always pass `-p default` explicitly so results do not depend on the caller's active profile (reviewer/worker profiles report `null` for unset-scoped queries).

## 0. Recovery point (before any change)

    hermes -p default config path          # note config location
    git -C ~/.hermes/hermes-agent rev-parse HEAD   # record source commit (expect 9cf7960f274ea2bdfe672d64d26389e9954dfeb6)
    # create a private snapshot outside Git per decisions/260920-harness-baseline.md; never snapshot into this repo
    # exact per-profile/path restore commands for the timestamped trees under
    # ~/.hermes/private live in procedures/rollback-restore.md

## 1. Profiles

Create the 12 non-default roster profiles with their exact descriptions (order irrelevant; `default` already exists and intentionally has no description):

    hermes profile create advisor --description "General advisor for terminology clarification, architecture decisions, local and web research, and read-only consultation of the default orchestrator's session transcripts."
    hermes profile create reviewer-sol --description "Independent GPT 5.6 Sol reviewer; defines semantic failure and selects revision, escalation, restart, approval, or human block."
    hermes profile create worker-flash-1 --description "GLM 5.3 Flash implementation lane 1; default economical coding worker."
    hermes profile create worker-flash-2 --description "GLM 5.3 Flash implementation lane 2; default economical coding worker."
    hermes profile create worker-flash-3 --description "GLM 5.3 Flash implementation lane 3; default economical coding worker."
    hermes profile create worker-luna-1 --description "GPT 5.6 Luna implementation escalation lane 1 for work rejected at the Flash rung."
    hermes profile create worker-luna-2 --description "GPT 5.6 Luna implementation escalation lane 2 for work rejected at the Flash rung."
    hermes profile create worker-terra-1 --description "GPT 5.6 Terra implementation lane for ambiguity, diagnosis, architecture, security, migrations, and complex multi-file work."
    hermes profile create worker-terra-2 --description "Dormant spare GPT 5.6 Terra implementation lane retained for rollback and capacity changes."
    hermes profile create worker-glm-full --description "GLM 5.3 full implementation lane for large-context, repo-wide, long-horizon, or visual work."
    hermes profile create worker-sol --description "GPT 5.6 Sol implementation escalation lane for work rejected below Sol."
    hermes profile create worker-astra --description "GPT 6 Astra final implementation escalation lane before human intervention."

To repair an existing profile's description instead:

    hermes -p default profile describe <profile> --text "<exact text above>"

Complete separate authorization per profile when a credential is required (`hermes` will prompt on first use; never copy OAuth stores between profiles).

## 2. Model and provider per profile (all 13)

    hermes -p default config set model.default gpt-5.6-sol
    hermes -p default config set model.provider openai-codex
    hermes -p advisor config set model.default gpt-5.6-sol
    hermes -p advisor config set model.provider openai-codex
    hermes -p reviewer-sol config set model.default gpt-5.6-sol
    hermes -p reviewer-sol config set model.provider openai-codex
    hermes -p worker-flash-1 config set model.default glm-5.3-flash
    hermes -p worker-flash-1 config set model.provider zai
    hermes -p worker-flash-2 config set model.default glm-5.3-flash
    hermes -p worker-flash-2 config set model.provider zai
    hermes -p worker-flash-3 config set model.default glm-5.3-flash
    hermes -p worker-flash-3 config set model.provider zai
    hermes -p worker-luna-1 config set model.default gpt-5.6-luna
    hermes -p worker-luna-1 config set model.provider openai-codex
    hermes -p worker-luna-2 config set model.default gpt-5.6-luna
    hermes -p worker-luna-2 config set model.provider openai-codex
    hermes -p worker-terra-1 config set model.default gpt-5.6-terra
    hermes -p worker-terra-1 config set model.provider openai-codex
    hermes -p worker-terra-2 config set model.default gpt-5.6-terra
    hermes -p worker-terra-2 config set model.provider openai-codex
    hermes -p worker-glm-full config set model.default glm-5.3
    hermes -p worker-glm-full config set model.provider zai
    hermes -p worker-sol config set model.default gpt-5.6-sol
    hermes -p worker-sol config set model.provider openai-codex
    hermes -p worker-astra config set model.default gpt-6-astra
    hermes -p worker-astra config set model.provider openai-codex

## 3. Ponytail on the ten implementation profiles (worker-flash-1/2/3, worker-luna-1/2, worker-terra-1/2, worker-glm-full, worker-sol, worker-astra; NOT default/reviewer-sol/advisor)

Desired state: the pinned Ponytail package is installed but `disabled` on every implementation profile. Hermes never runs the Ponytail plugin; minimalism comes from the per-card `minimal-implementation` skill instead (see section 4).

Install pinned from Git without enabling:

    hermes -p worker-flash-1 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-flash-2 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-flash-3 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-luna-1 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-luna-2 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-terra-1 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-terra-2 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-glm-full plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-sol plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable
    hermes -p worker-astra plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --no-enable

(--ref pins exactly; catalog does not list ponytail. `--no-enable` installs disabled, skipping the enable prompt.)

If a profile already has Ponytail enabled, disable it instead of reinstalling:

    hermes -p <profile> plugins disable ponytail

Verify disabled-but-pinned on each:

    hermes -p <profile> plugins list --plain --no-bundled
    # expect: disabled     git pinned@16f29800 4.8.4    ponytail
    # drift: absent line (not installed) or `enabled` prefix (plugin active) — both are failures
    # the resolver honors PONYTAIL_DEFAULT_MODE and ~/.config/ponytail/config.json; with the plugin disabled they are irrelevant — leave both unset unless a mode override is an approved change

## 4. Deploy the shared skills (manual copy; never symlink)

Hermes skills load per profile: worker profiles read only `~/.hermes/profiles/<profile>/skills`, and the default profile reads `~/.hermes/skills`. A skill installed only under `~/.hermes/skills` is invisible to implementation lanes, so the two scoped skills are copied into every implementation profile home — including dormant `worker-terra-2` — and never into reviewer/advisor homes. The orchestrator skill stays in the default (control-plane) home.

    mkdir -p ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts
    cp skills/multi-agent-coding-orchestrator/SKILL.md ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md
    cp skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts/

    for profile in worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2 \
                   worker-terra-1 worker-terra-2 worker-glm-full worker-sol worker-astra; do
      mkdir -p ~/.hermes/profiles/$profile/skills/software-development/minimal-implementation \
               ~/.hermes/profiles/$profile/skills/software-development/simplification-review \
               ~/.hermes/profiles/$profile/skills/devops
      cp skills/minimal-implementation/SKILL.md ~/.hermes/profiles/$profile/skills/software-development/minimal-implementation/SKILL.md
      cp skills/simplification-review/SKILL.md ~/.hermes/profiles/$profile/skills/software-development/simplification-review/SKILL.md
      rm -rf ~/.hermes/profiles/$profile/skills/devops/production-deployment \
             ~/.hermes/profiles/$profile/skills/devops/production-deployment-planning
      cp -R skills/devops/production-deployment ~/.hermes/profiles/$profile/skills/devops/
      cp -R skills/devops/production-deployment-planning ~/.hermes/profiles/$profile/skills/devops/
    done

The tracked trees under `skills/` are canonical source; the copies under each profile home are intentional deployment artifacts. Profiles do not share on-disk skill files, inherit live changes, or use symlinks. Every deployed copy, including every supporting file in both deployment skills, must match the tracked hashes in `snapshots/sanitized-current-state.yaml`; its `deploy_profiles` lists exactly which profile homes host each skill, and `./scripts/verify-state` hashes each copy and fails on a missing or divergent one. Copy the reviewed tracked source only; do not patch a live skill. Preserve worker-astra's three declared, hash-pinned built-in skill overrides; they are profile-local exceptions, not copies to normalize. After copying, run `./scripts/verify-state` so source and deployed copies are identical. Reviewer and advisor profiles never receive `minimal-implementation`; the orchestrator attaches it per card per the routing policy in `skills/multi-agent-coding-orchestrator/SKILL.md`.

Before creating any card that force-loads skills, reject incompatible requests before the card exists:

    python3 scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]

This command uses the installed resolver under the exact profile home and fails if any requested name is unavailable or disabled; a mixed present/missing set is a failure.

## 4b. Interactive Claude/Codex sessions (manual live-state step)

Desired policy for interactive Claude Code and Codex CLI sessions on this machine: upstream Ponytail remains installed and enabled, but the shared default mode is `off`, so sessions are manually activatable (`/ponytail`) rather than ambient. This is live `~/.claude` / `~/.codex` state — apply it manually; never commit it to this repository.

    # resolver order: PONYTAIL_DEFAULT_MODE env var, then ~/.config/ponytail/config.json defaultMode, then plugin default
    unset PONYTAIL_DEFAULT_MODE                          # in the shell that launches claude/codex
    mkdir -p ~/.config/ponytail
    printf '{"defaultMode": "off"}\n' > ~/.config/ponytail/config.json

Verify (manual):

    cat ~/.config/ponytail/config.json                  # expect {"defaultMode": "off"}
    env | grep PONYTAIL_DEFAULT_MODE                    # expect no output
    # start one claude/codex session: no Ponytail system prompt appears; `/ponytail full` activates it for that session

## 5. Global kanban settings (default-scoped)

    hermes -p default config set kanban.max_in_progress_per_profile 1
    hermes -p default config unset kanban.max_in_progress   # must stay unset: it counts reviewer runs

## 6. Dispatch allowlist (five implementation lanes + reviewer-sol)

Use the canonical helper, which refuses to remove a running implementation profile:

    python3 skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py \
      worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2
    # helper appends reviewer-sol automatically; --dry-run previews; --limit caps pool size

## 7. Repository adapters (already adopted; verify only)

The cha-pt and jobcron adapters live at their canonical archived lifecycle paths in
`snapshots/sanitized-current-state.yaml` (each repository migrated its docs to the
`docs/{plans,specs,decisions,archive}` taxonomy). Each adapter must contain its own
lifecycle-status line — `Status: operational; local repository adoption validated.`
for a still-active adapter, or the archived variant whose recorded transition is
complete and was validated — and `./scripts/verify-state` checks that marker plus the
tracked `adoption/*.md` records' operational adoption status. Do not modify those
repositories from here.

## 8. Verify and commit

    ./scripts/verify-state        # must exit 0
    git add -A && git commit -m "Apply <change>"   # commit desired-state change separately from applying

## 8b. Project-isolated concurrent fleets

Create or repair the ten project profiles and two named boards exactly as recorded in `docs/specs/261004-concurrent-project-fleets.md`. Use `--clone-from` only as a bootstrap; delete copied `MEMORY.md`/`USER.md`, replace `SOUL.md` with the project role contract, and do not clone messaging channels. Configure:

- `jobcron-orchestrator`, `jobcron-worker`: `openai-codex/gpt-6.1-sol`; `jobcron-worker-glm-1`, `jobcron-worker-glm-2`: `zai/glm-5.3`; `jobcron-reviewer`: `openai-codex/gpt-6-astra`; all rooted at `/Users/chanbla11mit/projects/jobcron`.
- `chapt-orchestrator`, `chapt-worker`: `openai-codex/gpt-6.1-sol`; `chapt-worker-glm-1`, `chapt-worker-glm-2`: `zai/glm-5.3`; `chapt-reviewer`: `openai-codex/gpt-6-astra`; all rooted at `/Users/chanbla11mit/projects/cha-pt`.
- Project orchestrator CLI toolsets: `clarify`, `kanban`, `memory`, `session_search`, `skills`, `todo` only.
- `kanban.dispatch_in_gateway: false` on every named project profile; the default multiplexed gateway remains the sole dispatcher.
- Boards `jobcron` and `cha-pt` with their canonical repositories as `default_workdir`.
- Default-profile `kanban.dispatch_profiles` includes each project's three-worker pool and reviewer plus explicitly retained legacy lanes. It excludes both orchestrators because dispatcher-spawned task sessions intentionally lack board-routing tools.
- Clear any legacy global launchd database pin with `launchctl unsetenv HERMES_KANBAN_DB`; a gateway inheriting that variable intentionally resolves every board slug to the one pinned database. The notifier LaunchAgent keeps its own explicit database path and is unaffected.

Disable `hermes-terminal-outcome-notification` on project profiles: its legacy shared-default-DB deployment is not the authority for named-board events. Named-board lifecycle and subscriptions remain inside stock Hermes Kanban.

Launch controllers only through `scripts/run-jobcron-orchestrator` and `scripts/run-chapt-orchestrator`; these set the per-process board pin before starting the profile.

After clearing the launchd pin, restart the default gateway once from a separate shell. Do not restart it from a gateway-owned agent process: the restart terminates that process before it can verify completion. Normal topology rollback may restore the legacy pin with `launchctl setenv HERMES_KANBAN_DB /Users/chanbla11mit/.hermes/kanban.db` only if named-board dispatch has first been paused or retired.

## 9. Authorized Astra terminal-retry upgrade (manual only)

After independent review, copy the exact tracked `skills/multi-agent-coding-orchestrator` tree to
the default profile and install the exact reviewed `hermes-terminal-outcome-notification` pin on
every producer profile using supported Hermes plugin commands. Render and reload the reviewed
notification worker only with separate deployment authorization. Run `./scripts/verify-state`
after deployment; before rollout, fixture mode is the valid proof and live pin/copy drift is
expected. Never enable `astra-until-approve-v1` globally: record all three v2 authorization fields
only on the explicitly authorized card/root campaign.

## Boundaries

- Do not use this procedure for credentials; authorization happens per profile through the supported interface.
- Do not remove unexpected state merely because verification reports it; removal is a separately reviewed manual action.
- Do not change the Hermes source checkout; it stays clean at the pinned commit.
