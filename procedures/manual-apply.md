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

## 2b. Command approval mode (all roster profiles)

The desired state is `approvals.mode: off` on every installed roster profile. This removes Hermes terminal-command approval prompts; it does not relax project routing, repository/worktree scope, credential handling, deployment authorization, cloud-mutation, or production-write policies.

    for profile in default advisor reviewer-sol \
                   worker-flash-1 worker-flash-2 worker-flash-3 \
                   worker-luna-1 worker-luna-2 worker-terra-1 worker-glm-full \
                   worker-sol worker-astra worker-terra-2 \
                   jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer \
                   chapt-orchestrator chapt-worker chapt-worker-2 chapt-reviewer \
                   harness-orchestrator harness-worker harness-worker-2 harness-reviewer; do
      hermes -p "$profile" config set approvals.mode off
    done

Hermes reads this setting at the command approval gate. Subsequent commands in an already-running session use the new mode, but an approval request that is already pending must still be approved, denied, or retried.

Verify each profile explicitly:

    hermes -p <profile> config get approvals.mode   # expect: off

## 3. Ponytail 5.3.3: enabled at level `full` on the 56 target profiles, installed and disabled on the ten retired implementation profiles

Desired state (owner decision of 2026-11-18, card `t_9c1b6b2f`): Ponytail 5.3.3 at commit `7801d061243d7b753bad0e0b3c057cd250b11755` is installed and enabled on 56 target profiles, and each of them has the line `PONYTAIL_DEFAULT_MODE=full` in its `.env` file. The 56 target profiles are, for each board prefix `harness`, `chapt`, `jobcron`, `jss` and `anki`, the eleven profiles whose names are the prefix followed by `-orchestrator`, `-reviewer`, `-reviewer-glm`, `-worker`, `-worker-2`, `-worker-glm-easy-1`, `-worker-glm-easy-2`, `-worker-glm-medium-1`, `-worker-glm-medium-2`, `-worker-glm-hard-1` or `-worker-glm-hard-2`, and `advisor`; `roster.yaml` lists `ponytail` in their `required_plugins`. The ten retired implementation profiles (`worker-flash-1`, `worker-flash-2`, `worker-flash-3`, `worker-luna-1`, `worker-luna-2`, `worker-terra-1`, `worker-terra-2`, `worker-glm-full`, `worker-sol`, `worker-astra`) have the same commit installed and disabled (`installed_disabled_plugins`). `default` and every other profile have no Ponytail.

The Hermes plugin of Ponytail chooses its level from the environment variable `PONYTAIL_DEFAULT_MODE` first, then from `defaultMode` in `/Users/chanbla11mit/.config/ponytail/config.json`, and otherwise uses `full` (`__init__.py` lines 35 to 54 at the pinned commit). Hermes loads the profile's `.env` file into the environment, so the `.env` line sets level `full` on each target profile. The shared file `/Users/chanbla11mit/.config/ponytail/config.json` keeps `"defaultMode": "off"` for the owner's Claude Code and Codex sessions (section 4b) and does not change.

Install method: on Hermes `v0.21.5+6751.g9cf7960`, `hermes plugins install https://github.com/DietrichGebert/ponytail.git --ref 7801d061243d7b753bad0e0b3c057cd250b11755` stops with `plugin.json declares an unsupported or missing Agent Plugins schema`, so the plugin is installed by hand (owner decision of 2026-11-19): `git clone`, `git checkout --detach` of the commit, and `hermes plugins adopt`, which writes the origin URL and the revision to the profile's `plugins/.install-metadata.json` with `pinned` false. This method does not run the Hermes community-source scan, the scan of 2026-11-18 found no finding in the files that the Hermes plugin loads (`__init__.py`, `plugin.yaml`, `skills/`), and the normal `hermes plugins install --ref` method replaces this method after Hermes fixes NousResearch/hermes-agent#125937. For ponytail, `./scripts/verify-state` therefore requires the install metadata entry with `revision` `7801d061243d7b753bad0e0b3c057cd250b11755` and `source` `https://github.com/DietrichGebert/ponytail.git` (not `pinned` true), and a `plugins list --plain --no-bundled` line with source `git` and version `5.3.3` (not the `pinned@` text).

### 3a. Remove Ponytail 4.8.4 first

Ponytail 4.8.4 (commit `16f29800fd2681bdf24f3eb4ccffe38be3baec6b`) was installed and disabled with `plugins install --ref` on the ten board Claude workers and on the ten retired implementation profiles. `git clone` stops when `plugins/ponytail` exists, and `plugins adopt` stops when the install metadata has a `ponytail` entry. `plugins remove` deletes both:

    hermes -p anki-worker plugins remove ponytail
    hermes -p anki-worker-2 plugins remove ponytail
    hermes -p chapt-worker plugins remove ponytail
    hermes -p chapt-worker-2 plugins remove ponytail
    hermes -p harness-worker plugins remove ponytail
    hermes -p harness-worker-2 plugins remove ponytail
    hermes -p jobcron-worker plugins remove ponytail
    hermes -p jobcron-worker-2 plugins remove ponytail
    hermes -p jss-worker plugins remove ponytail
    hermes -p jss-worker-2 plugins remove ponytail
    hermes -p worker-flash-1 plugins remove ponytail
    hermes -p worker-flash-2 plugins remove ponytail
    hermes -p worker-flash-3 plugins remove ponytail
    hermes -p worker-luna-1 plugins remove ponytail
    hermes -p worker-luna-2 plugins remove ponytail
    hermes -p worker-terra-1 plugins remove ponytail
    hermes -p worker-terra-2 plugins remove ponytail
    hermes -p worker-glm-full plugins remove ponytail
    hermes -p worker-sol plugins remove ponytail
    hermes -p worker-astra plugins remove ponytail

On any other target profile whose `plugins list --plain --no-bundled` output has a `ponytail` line, run `hermes -p`, that profile name written literally, and `plugins remove ponytail` before section 3b.

### 3b. The 56 target profiles: install, enable, `.env` line, verification

For each profile, in this order: clone, check out the commit, confirm the commit, adopt, enable, add the `.env` line only if it is absent, and verify. The `.env` command prints no line of the file and appends a line feed before the new line so that a last line without a line feed stays separate; an empty line in `.env` has no effect.

`harness-orchestrator`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-orchestrator plugins adopt ponytail
    hermes -p harness-orchestrator plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/.env
    hermes -p harness-orchestrator plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-reviewer`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-reviewer/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-reviewer/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-reviewer/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-reviewer plugins adopt ponytail
    hermes -p harness-reviewer plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-reviewer/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-reviewer/.env
    hermes -p harness-reviewer plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-reviewer-glm`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-reviewer-glm plugins adopt ponytail
    hermes -p harness-reviewer-glm plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-reviewer-glm/.env
    hermes -p harness-reviewer-glm plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker plugins adopt ponytail
    hermes -p harness-worker plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker/.env
    hermes -p harness-worker plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-2 plugins adopt ponytail
    hermes -p harness-worker-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-2/.env
    hermes -p harness-worker-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-easy-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-easy-1 plugins adopt ponytail
    hermes -p harness-worker-glm-easy-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/.env
    hermes -p harness-worker-glm-easy-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-easy-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-easy-2 plugins adopt ponytail
    hermes -p harness-worker-glm-easy-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/.env
    hermes -p harness-worker-glm-easy-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-medium-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-medium-1 plugins adopt ponytail
    hermes -p harness-worker-glm-medium-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/.env
    hermes -p harness-worker-glm-medium-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-medium-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-medium-2 plugins adopt ponytail
    hermes -p harness-worker-glm-medium-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/.env
    hermes -p harness-worker-glm-medium-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-hard-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-hard-1 plugins adopt ponytail
    hermes -p harness-worker-glm-hard-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/.env
    hermes -p harness-worker-glm-hard-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`harness-worker-glm-hard-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p harness-worker-glm-hard-2 plugins adopt ponytail
    hermes -p harness-worker-glm-hard-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/.env
    hermes -p harness-worker-glm-hard-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-orchestrator`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-orchestrator plugins adopt ponytail
    hermes -p chapt-orchestrator plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/.env
    hermes -p chapt-orchestrator plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-reviewer`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-reviewer/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-reviewer/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-reviewer/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-reviewer plugins adopt ponytail
    hermes -p chapt-reviewer plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-reviewer/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-reviewer/.env
    hermes -p chapt-reviewer plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-reviewer-glm`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-reviewer-glm/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-reviewer-glm/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-reviewer-glm/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-reviewer-glm plugins adopt ponytail
    hermes -p chapt-reviewer-glm plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-reviewer-glm/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-reviewer-glm/.env
    hermes -p chapt-reviewer-glm plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker plugins adopt ponytail
    hermes -p chapt-worker plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker/.env
    hermes -p chapt-worker plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-2 plugins adopt ponytail
    hermes -p chapt-worker-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-2/.env
    hermes -p chapt-worker-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-easy-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-easy-1 plugins adopt ponytail
    hermes -p chapt-worker-glm-easy-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/.env
    hermes -p chapt-worker-glm-easy-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-easy-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-easy-2 plugins adopt ponytail
    hermes -p chapt-worker-glm-easy-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/.env
    hermes -p chapt-worker-glm-easy-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-medium-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-medium-1 plugins adopt ponytail
    hermes -p chapt-worker-glm-medium-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/.env
    hermes -p chapt-worker-glm-medium-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-medium-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-medium-2 plugins adopt ponytail
    hermes -p chapt-worker-glm-medium-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/.env
    hermes -p chapt-worker-glm-medium-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-hard-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-hard-1 plugins adopt ponytail
    hermes -p chapt-worker-glm-hard-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/.env
    hermes -p chapt-worker-glm-hard-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`chapt-worker-glm-hard-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p chapt-worker-glm-hard-2 plugins adopt ponytail
    hermes -p chapt-worker-glm-hard-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/.env
    hermes -p chapt-worker-glm-hard-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-orchestrator`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-orchestrator plugins adopt ponytail
    hermes -p jobcron-orchestrator plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/.env
    hermes -p jobcron-orchestrator plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-reviewer`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-reviewer plugins adopt ponytail
    hermes -p jobcron-reviewer plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer/.env
    hermes -p jobcron-reviewer plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-reviewer-glm`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer-glm/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer-glm/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer-glm/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-reviewer-glm plugins adopt ponytail
    hermes -p jobcron-reviewer-glm plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer-glm/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-reviewer-glm/.env
    hermes -p jobcron-reviewer-glm plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker plugins adopt ponytail
    hermes -p jobcron-worker plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker/.env
    hermes -p jobcron-worker plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-2 plugins adopt ponytail
    hermes -p jobcron-worker-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-2/.env
    hermes -p jobcron-worker-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-easy-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-easy-1 plugins adopt ponytail
    hermes -p jobcron-worker-glm-easy-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/.env
    hermes -p jobcron-worker-glm-easy-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-easy-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-easy-2 plugins adopt ponytail
    hermes -p jobcron-worker-glm-easy-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/.env
    hermes -p jobcron-worker-glm-easy-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-medium-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-medium-1 plugins adopt ponytail
    hermes -p jobcron-worker-glm-medium-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/.env
    hermes -p jobcron-worker-glm-medium-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-medium-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-medium-2 plugins adopt ponytail
    hermes -p jobcron-worker-glm-medium-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/.env
    hermes -p jobcron-worker-glm-medium-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-hard-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-hard-1 plugins adopt ponytail
    hermes -p jobcron-worker-glm-hard-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/.env
    hermes -p jobcron-worker-glm-hard-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jobcron-worker-glm-hard-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jobcron-worker-glm-hard-2 plugins adopt ponytail
    hermes -p jobcron-worker-glm-hard-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/.env
    hermes -p jobcron-worker-glm-hard-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-orchestrator`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-orchestrator/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-orchestrator/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-orchestrator/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-orchestrator plugins adopt ponytail
    hermes -p jss-orchestrator plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-orchestrator/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-orchestrator/.env
    hermes -p jss-orchestrator plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-reviewer`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-reviewer/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-reviewer/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-reviewer/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-reviewer plugins adopt ponytail
    hermes -p jss-reviewer plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-reviewer/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-reviewer/.env
    hermes -p jss-reviewer plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-reviewer-glm`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-reviewer-glm/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-reviewer-glm/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-reviewer-glm/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-reviewer-glm plugins adopt ponytail
    hermes -p jss-reviewer-glm plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-reviewer-glm/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-reviewer-glm/.env
    hermes -p jss-reviewer-glm plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker plugins adopt ponytail
    hermes -p jss-worker plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker/.env
    hermes -p jss-worker plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-2 plugins adopt ponytail
    hermes -p jss-worker-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-2/.env
    hermes -p jss-worker-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-easy-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-easy-1 plugins adopt ponytail
    hermes -p jss-worker-glm-easy-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/.env
    hermes -p jss-worker-glm-easy-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-easy-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-easy-2 plugins adopt ponytail
    hermes -p jss-worker-glm-easy-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/.env
    hermes -p jss-worker-glm-easy-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-medium-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-medium-1 plugins adopt ponytail
    hermes -p jss-worker-glm-medium-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/.env
    hermes -p jss-worker-glm-medium-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-medium-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-medium-2 plugins adopt ponytail
    hermes -p jss-worker-glm-medium-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/.env
    hermes -p jss-worker-glm-medium-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-hard-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-hard-1 plugins adopt ponytail
    hermes -p jss-worker-glm-hard-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/.env
    hermes -p jss-worker-glm-hard-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`jss-worker-glm-hard-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p jss-worker-glm-hard-2 plugins adopt ponytail
    hermes -p jss-worker-glm-hard-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/.env
    hermes -p jss-worker-glm-hard-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-orchestrator`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-orchestrator/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-orchestrator/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-orchestrator/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-orchestrator plugins adopt ponytail
    hermes -p anki-orchestrator plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-orchestrator/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-orchestrator/.env
    hermes -p anki-orchestrator plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-reviewer`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-reviewer/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-reviewer/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-reviewer/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-reviewer plugins adopt ponytail
    hermes -p anki-reviewer plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-reviewer/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-reviewer/.env
    hermes -p anki-reviewer plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-reviewer-glm`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-reviewer-glm/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-reviewer-glm/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-reviewer-glm/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-reviewer-glm plugins adopt ponytail
    hermes -p anki-reviewer-glm plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-reviewer-glm/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-reviewer-glm/.env
    hermes -p anki-reviewer-glm plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker plugins adopt ponytail
    hermes -p anki-worker plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker/.env
    hermes -p anki-worker plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-2 plugins adopt ponytail
    hermes -p anki-worker-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-2/.env
    hermes -p anki-worker-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-easy-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-easy-1 plugins adopt ponytail
    hermes -p anki-worker-glm-easy-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env
    hermes -p anki-worker-glm-easy-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-easy-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-easy-2 plugins adopt ponytail
    hermes -p anki-worker-glm-easy-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/.env
    hermes -p anki-worker-glm-easy-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-medium-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-medium-1 plugins adopt ponytail
    hermes -p anki-worker-glm-medium-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/.env
    hermes -p anki-worker-glm-medium-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-medium-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-medium-2 plugins adopt ponytail
    hermes -p anki-worker-glm-medium-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/.env
    hermes -p anki-worker-glm-medium-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-hard-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-hard-1 plugins adopt ponytail
    hermes -p anki-worker-glm-hard-1 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/.env
    hermes -p anki-worker-glm-hard-1 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`anki-worker-glm-hard-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p anki-worker-glm-hard-2 plugins adopt ponytail
    hermes -p anki-worker-glm-hard-2 plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/.env
    hermes -p anki-worker-glm-hard-2 plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

`advisor`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/advisor/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/advisor/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/advisor/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p advisor plugins adopt ponytail
    hermes -p advisor plugins enable ponytail
    grep -qxF 'PONYTAIL_DEFAULT_MODE=full' /Users/chanbla11mit/.hermes/profiles/advisor/.env || printf '\nPONYTAIL_DEFAULT_MODE=full\n' >> /Users/chanbla11mit/.hermes/profiles/advisor/.env
    hermes -p advisor plugins list --plain --no-bundled | grep -x 'enabled      git      5.3.3    ponytail'
    # expect: enabled      git      5.3.3    ponytail

### 3c. The ten retired implementation profiles: install and keep disabled

These profiles get no `.env` line, because the plugin stays disabled.

`worker-flash-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-flash-1 plugins adopt ponytail
    hermes -p worker-flash-1 plugins disable ponytail
    hermes -p worker-flash-1 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-flash-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-flash-2 plugins adopt ponytail
    hermes -p worker-flash-2 plugins disable ponytail
    hermes -p worker-flash-2 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-flash-3`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-flash-3 plugins adopt ponytail
    hermes -p worker-flash-3 plugins disable ponytail
    hermes -p worker-flash-3 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-luna-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-luna-1 plugins adopt ponytail
    hermes -p worker-luna-1 plugins disable ponytail
    hermes -p worker-luna-1 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-luna-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-luna-2 plugins adopt ponytail
    hermes -p worker-luna-2 plugins disable ponytail
    hermes -p worker-luna-2 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-terra-1`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-terra-1 plugins adopt ponytail
    hermes -p worker-terra-1 plugins disable ponytail
    hermes -p worker-terra-1 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-terra-2`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-terra-2/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-terra-2/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-terra-2/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-terra-2 plugins adopt ponytail
    hermes -p worker-terra-2 plugins disable ponytail
    hermes -p worker-terra-2 plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-glm-full`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-glm-full plugins adopt ponytail
    hermes -p worker-glm-full plugins disable ponytail
    hermes -p worker-glm-full plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-sol`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-sol plugins adopt ponytail
    hermes -p worker-sol plugins disable ponytail
    hermes -p worker-sol plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

`worker-astra`:

    git clone https://github.com/DietrichGebert/ponytail.git /Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/ponytail
    git -C /Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/ponytail checkout --detach 7801d061243d7b753bad0e0b3c057cd250b11755
    git -C /Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/ponytail rev-parse HEAD
    # expect: 7801d061243d7b753bad0e0b3c057cd250b11755
    hermes -p worker-astra plugins adopt ponytail
    hermes -p worker-astra plugins disable ponytail
    hermes -p worker-astra plugins list --plain --no-bundled | grep -x 'disabled     git      5.3.3    ponytail'
    # expect: disabled     git      5.3.3    ponytail

Hermes loads plugins when a process starts: each running gateway and each running worker of a changed profile must restart to load the plugin. Then run `./scripts/verify-state`.

## 4. Deploy the shared skills (manual copy; never symlink)

Hermes skills load per profile: worker profiles read only `~/.hermes/profiles/<profile>/skills`, and the default profile reads `~/.hermes/skills`. A skill installed only under `~/.hermes/skills` is invisible to implementation lanes, so the two scoped skills are copied into every implementation profile home — including dormant `worker-terra-2` — and never into reviewer/advisor homes. The canonical orchestration skill is deployed to the default home. The project orchestrators use separately tracked, hash-pinned variants under `policies/profile-skills/` so their learned project procedures are preserved instead of overwritten by a shared copy.

    mkdir -p ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts
    cp skills/multi-agent-coding-orchestrator/SKILL.md ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md
    cp skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts/

    for profile in jobcron-orchestrator chapt-orchestrator harness-orchestrator; do
      mkdir -p ~/.hermes/profiles/$profile/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts
      cp policies/profile-skills/$profile/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md ~/.hermes/profiles/$profile/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md
      cp skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py ~/.hermes/profiles/$profile/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts/
    done

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

The tracked trees under `skills/` are canonical source; the copies under each profile home are intentional deployment artifacts. Profiles do not share on-disk skill files, inherit live changes, or use symlinks. Every deployed copy, including every supporting file in both deployment skills, must match the tracked hashes in `snapshots/sanitized-current-state.yaml`; its `deploy_profiles` lists exactly which profile homes host each skill, and `./scripts/verify-state` hashes each copy and fails on a missing or divergent one. Copy the reviewed tracked source only; do not patch a live skill. Preserve worker-astra's three declared, hash-pinned built-in skill overrides; they are profile-local exceptions, not copies to normalize. After copying, run `./scripts/verify-state` so source and deployed copies are identical. The active policy for minimal implementation is the Ponytail plugin at level `full` (section 3); the orchestrators no longer attach `minimal-implementation` to a card.

Before creating any card that force-loads skills, reject incompatible requests before the card exists:

    python3 scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]

This command uses the installed resolver under the exact profile home and fails if any requested name is unavailable or disabled; a mixed present/missing set is a failure.

On 2026-11-15, card `t_fcdd77ed` copied `SKILL.md` of the orchestrator skill sources of commit `71bbf080f5d7ee25a7ddbac3532db5f9445df144` (versions `0.6.9-jobcron.15` and `0.6.7-chapt.14`) to `jobcron-orchestrator` and `chapt-orchestrator`, and did not change `harness-orchestrator`, `jss-orchestrator`, `anki-orchestrator` or the default profile.

On 2026-11-16, card `t_5f0d8d22` copied the reviewer `SOUL.md` sources of commit `60a79fca167beb5fe37add10b79ef19eb777f0f7` to `anki-reviewer`, `chapt-reviewer`, `harness-reviewer`, `jobcron-reviewer` and `jss-reviewer`, and copied `SKILL.md` of the orchestrator skill sources of the same commit (versions `0.6.10-anki.11`, `0.6.7-chapt.15`, `0.6.9-jobcron.16` and `0.6.7-jss.17`) to `anki-orchestrator`, `chapt-orchestrator`, `jobcron-orchestrator` and `jss-orchestrator`; it did not change `harness-orchestrator` or the default profile. On 2026-11-16, after the owner's approval, card `t_fb1a44e4` copied `SKILL.md` of the `harness-orchestrator` skill source of commit `8845e54ebad421c4381d46f14843cbbb74492854` (version `0.6.7-harness.13`) to the live `harness-orchestrator` profile.

## 4a. Pin a deployed skill copy that the Hermes curator manages

The Hermes curator is a background task that periodically reviews agent-created skills, prunes stale ones, consolidates overlaps, and archives obsolete skills. A skill that the curator manages and that has not been used for `curator.archive_after_days` days is archived: its files move from `/Users/chanbla11mit/.hermes/profiles/<profile>/skills/` into `/Users/chanbla11mit/.hermes/profiles/<profile>/skills/.archive/`, and `./scripts/verify-state` then reports the declared copy as missing (`deployed skill copy missing: <skill> <profile>`). Measured settings on `harness-orchestrator`, `chapt-orchestrator` and `jobcron-orchestrator` (2026-11-14, `hermes -p <profile> config get`): `curator.enabled` true, `curator.interval_hours` 168, `curator.stale_after_days` 14, `curator.archive_after_days` 30.

The curator manages a skill only when the record of that skill in `/Users/chanbla11mit/.hermes/profiles/<profile>/skills/.usage.json` has `created_by` `agent`; other copies are never archived. Check one skill on one profile, read-only:

    python3 -c "import json; r = json.load(open('/Users/chanbla11mit/.hermes/profiles/<profile>/skills/.usage.json'))['<skill>']; print(r['created_by']); print(r['pinned']); print(r['state'])"

This prints exactly three lines: the values of `created_by`, `pinned` and `state` of that one record, nothing else.

Step: after a declared skill has been deployed to a profile (section 4 above), run the read-only command for that skill and profile. If it prints `agent`, pin the copy so the curator never changes its state automatically:

    hermes -p <profile> curator pin <skill>
    # expect: curator: pinned '<skill>' (will bypass auto-transitions)

Read back with the same read-only command: `pinned` must now print `True`. The pin changes only the `pinned` field in `.usage.json`; it does not change the skill files (measured 2026-11-14: after the pins, all three files of each pinned copy were byte-equal to their tracked source under `skills/`).

If the curator has already archived a copy, bring it back with `hermes -p <profile> curator restore <skill>`.

A pin is a live change to a profile. It needs the owner's authorization like every other live change in this procedure.

Statements above that come from reading the Hermes source or the `--help` text only, without running the command behind them: the description of what the curator does and the archive behavior after `curator.archive_after_days` days (from `hermes curator --help` and `/Users/chanbla11mit/.hermes/hermes-agent/agent/curator.py`), the `created_by` `agent` management rule (from `/Users/chanbla11mit/.hermes/hermes-agent/tools/skill_usage.py`), and the `curator restore` command (from `hermes curator --help` only; it was not run in this procedure).

Record of 2026-11-14: the curator archived `production-deployment` on `harness-orchestrator` (last use 2026-10-13; ledger entry `fc119ea5eee8` in `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/.curator_ledger.jsonl`; files moved to `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/.archive/production-deployment`), and `./scripts/verify-state` then printed `deployed skill copy missing: production-deployment harness-orchestrator`. The controller pinned the copies on `chapt-orchestrator` and `jobcron-orchestrator` with `hermes -p <profile> curator pin production-deployment`; each printed the expected line above, and in each `.usage.json` exactly one field changed (`pinned`, false to true). Backups of the two `.usage.json` files from before the pins: `/Users/chanbla11mit/.hermes/profiles/chapt-orchestrator/skill-backups/usage.json-pre-pin-20261114205748` and `/Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/skill-backups/usage.json-pre-pin-20261114205748`. Card `t_31846ed4` removes the Harness profiles from the `deploy_profiles` list of `production-deployment` in `snapshots/sanitized-current-state.yaml`, so the archived copy on `harness-orchestrator` is not restored.

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

Create or repair the nine project profiles and three named boards exactly as recorded in `docs/specs/261004-concurrent-project-fleets.md`. This section is an attended reconstruction procedure, not authority for an agent to apply it. Use `--clone-from` only as a bootstrap; delete copied `MEMORY.md`/`USER.md`, replace `SOUL.md` with the project role contract, and do not clone messaging channels. Configure:

- `jobcron-orchestrator`, `jobcron-worker`: `openai-codex/gpt-6.1-sol`; `jobcron-reviewer`: `openai-codex/gpt-6-astra`; all rooted at `/Users/chanbla11mit/projects/jobcron`.
- `chapt-orchestrator`, `chapt-worker`: `openai-codex/gpt-6.1-sol`; `chapt-reviewer`: `openai-codex/gpt-6-astra`; all rooted at `/Users/chanbla11mit/projects/cha-pt`.
- `harness-orchestrator`, `harness-worker`: `openai-codex/gpt-6.1-sol`; `harness-reviewer`: `openai-codex/gpt-6-astra`; all rooted solely at `/Users/chanbla11mit/hermes-local-harness`.
- Second workers `jobcron-worker-2`, `chapt-worker-2`, `harness-worker-2` (added 2026-10-18): `claude-subscription/claude-opus-5-5`, created with `hermes profile create --clone-from <fleet>-worker`, with the source worker's `terminal.cwd`, toolsets, skills and tracked `SOUL.md`.
- Project orchestrator CLI toolsets: `clarify`, `kanban`, `memory`, `session_search`, `skills`, `todo` only.
- `kanban.dispatch_in_gateway: false` on every named project profile; the default multiplexed gateway remains the sole dispatcher.
- Boards `jobcron`, `cha-pt`, and `harness` with their canonical repositories as `default_workdir`.
- Default-profile `kanban.dispatch_profiles` includes each project's workers and reviewer plus explicitly retained legacy lanes. It excludes all project orchestrators because dispatcher-spawned task sessions intentionally lack board-routing tools.
- Clear any legacy global launchd database pin with `launchctl unsetenv HERMES_KANBAN_DB`; a gateway inheriting that variable intentionally resolves every board slug to the one pinned database. The notifier LaunchAgent keeps its own explicit database path and is unaffected.

Disable `hermes-terminal-outcome-notification` on project profiles: its legacy shared-default-DB deployment is not the authority for named-board events. Named-board lifecycle and subscriptions remain inside stock Hermes Kanban.

Launch controllers only through `scripts/run-jobcron-orchestrator`, `scripts/run-chapt-orchestrator`, and `scripts/run-harness-orchestrator`; these set the per-process board pin before starting the profile.

Cha PT uses one board with three repository-specific worktree roots. Keep the board default and all three profile `terminal.cwd` values at `/Users/chanbla11mit/projects/cha-pt`. Create the frontend and scraper projects only in the `chapt-orchestrator` profile; do not run `project bind-board` afterward because that command would replace the board default workdir:

    hermes -p chapt-orchestrator project create "Cha PT Frontend" \
      /Users/chanbla11mit/projects/cha-pt-frontend \
      --slug cha-pt-frontend \
      --primary /Users/chanbla11mit/projects/cha-pt-frontend \
      --board cha-pt
    hermes -p chapt-orchestrator project show cha-pt-frontend
    hermes -p chapt-orchestrator project create "Cha WebPT Website Sync" \
      /Users/chanbla11mit/projects/cha-webpt-website-sync \
      --slug cha-webpt-website-sync \
      --primary /Users/chanbla11mit/projects/cha-webpt-website-sync \
      --board cha-pt
    hermes -p chapt-orchestrator project show cha-webpt-website-sync

The scraper checkout `/Users/chanbla11mit/projects/cha-webpt-website-sync` must have origin EXACT `git@github.com:raysong-sudo/cha-webpt-website-sync.git`. Install the tracked worker/reviewer push refusal as its `pre-push` hook (a copy, never a symlink), and confirm no `core.hooksPath` override would bypass it:

    test -z "$(git -C /Users/chanbla11mit/projects/cha-webpt-website-sync config --get core.hooksPath)"
    install -m 0755 policies/repository-hooks/cha-webpt-website-sync/pre-push /Users/chanbla11mit/projects/cha-webpt-website-sync/.git/hooks/pre-push
    cmp policies/repository-hooks/cha-webpt-website-sync/pre-push /Users/chanbla11mit/projects/cha-webpt-website-sync/.git/hooks/pre-push

The hook refuses every push while `HERMES_KANBAN_TASK` or `HERMES_KANBAN_WORKSPACE` is set (any dispatched worker or reviewer) or from a Hermes profile other than `chapt-orchestrator`, and any update other than a fast-forward of `refs/heads/main`. Only `chapt-orchestrator` pushes, through `scripts/chapt-push-scraper-main --card <id> --sha <sha> --approval '<owner message verbatim>'`, after a per-push owner approval naming the repository, `main` and that exact reviewed SHA. The helper refuses unless `HERMES_HOME` ends in `profiles/chapt-orchestrator`, `HERMES_PROFILE` (when set) is `chapt-orchestrator`, and neither `HERMES_KANBAN_TASK` nor `HERMES_KANBAN_WORKSPACE` is set.

Deploy the exact tracked Cha PT role contracts; never patch the live copies directly:

    for profile in chapt-orchestrator chapt-worker chapt-worker-2 chapt-reviewer; do
      cp "policies/profile-souls/$profile/SOUL.md" "$HOME/.hermes/profiles/$profile/SOUL.md"
    done

Deploy the exact tracked harness role contracts only during a separately authorized attended rollout; never let `harness-orchestrator` modify its own active live policy:

    for profile in harness-orchestrator harness-worker harness-worker-2 harness-reviewer; do
      cp "policies/profile-souls/$profile/SOUL.md" "$HOME/.hermes/profiles/$profile/SOUL.md"
    done

The harness fleet is local-only by default. Isolated task worktrees may contain local commits, but pushes, PRs, live policy/profile deployment, board or gateway changes, credentials, production/cloud mutations, and external writes require separate explicit human authorization. `docs/bugs/` entries are evidence and triage input, not automatic implementation authorization. Repository policy changes require same-card `harness-reviewer` review before integration; live rollout remains separate and attended.

Every Cha PT card must name exactly one authorized repository, its repository-owned isolated worktree, the protected baseline commit, and the explicit test contract. Scraper cards set `project: cha-webpt-website-sync` and declare `Scraper project EXACT cha-webpt-website-sync.`; their workers and reviewer stay local-only. Frontend cards set `project: cha-pt-frontend` and obey `/Users/chanbla11mit/projects/cha-pt-frontend/AGENTS.md`; protected paths, credentials, pushes, PRs, previews, deployments, production/cloud changes, and other external writes retain their separate human approval gates. Split cross-repository work into linked cards. Do not rewrite or broaden existing cards, including P4 campaign cards.

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
