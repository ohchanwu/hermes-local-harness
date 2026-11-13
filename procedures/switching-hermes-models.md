# Switching Hermes profiles between Claude, GPT and GLM

State on 2026-10-17: every active profile runs on the Claude subscription provider. See the [provider README](../plugins/model-providers/claude-subscription/README.md#rollout-status-2026-10-17-kst) for the role-by-role table. OpenAI (GPT) was retired from 2026-10-18. The GLM (z.ai) worker profiles were retired on 2026-10-18; on 2026-11-12 the GLM workers of the `jobcron`, `cha-pt`, `harness` and `jss-genr` boards returned to service for the jev plugin, and two new GLM workers were added for the `anki` board (see below). Every provider stays switchable with the script below.

## Where the GPT profiles are kept

- **On disk, unchanged:** `reviewer-sol`, `worker-sol`, `worker-astra`, `worker-luna-1`, `worker-luna-2`, `worker-terra-1`, `worker-terra-2` stay in `~/.hermes/profiles/` with their config, `.env` and history. They are inert. They are in no `kanban.dispatch_profiles` list and have no chat connection.
- **Archived copies:** `~/.hermes/profile-exports/<name>-20261017-18*.tar.gz` (mode 600), made with `hermes profile export`. Exports deliberately exclude `.env` and `auth.json`. A profile restored with `hermes profile import <archive>` needs those re-created.
- **Config backups of the Claude profiles:** in each home, `config.yaml.pre-claude-261017` is the state before any Claude change. `config.yaml.pre-helpers-261017` is the state before helpers moved off GPT. The switch script below writes `config.yaml.pre-switch-<timestamp>` on every run.

## Where the GLM worker profiles are kept

The owner retired the GLM workers on 2026-10-18. The same day the owner added a second Opus worker to every fleet, so each fleet now has two implementation workers (`harness-worker` and `harness-worker-2`, `chapt-worker` and `chapt-worker-2`, `jobcron-worker` and `jobcron-worker-2`, `jss-worker` and `jss-worker-2`) plus its reviewer.

- **Back in service since 2026-11-12 (cards `t_4f7740d0` and `t_71b4ef4a`):** `jobcron-worker-glm-1`, `jobcron-worker-glm-2`, `chapt-worker-glm-1`, `chapt-worker-glm-2`, `harness-worker-glm-1`, `harness-worker-glm-2` (card `t_4f7740d0`), and `jss-worker-glm-1`, `jss-worker-glm-2` with the two new profiles `anki-worker-glm-1`, `anki-worker-glm-2` (card `t_71b4ef4a`; the two anki profiles are created by a later deployment card, see `procedures/jev-plugin.md`). The jev plugin reassigns easy and medium implementation cards on every board (`jobcron`, `cha-pt`, `harness`, `jss-genr` and `anki`) to the two GLM workers of the same board. `roster.yaml` declares each of the ten with `"lifecycle": "project-active"`, model `glm-5.3`, provider `zai`, `dispatch_eligible` and `in_dispatch_pool` true, and the required plugin `jev`. `scripts/verify-state` checks the ten against model `glm-5.3` on provider `zai` instead of the Claude model policy below, expects all ten in `kanban.dispatch_profiles` (`PROJECT_GLM_WORKER_POOLS`), and accepts each one as the assignee of an implementation card on its own board. They are not fleet workers: the fleet `workers` lists, the shared skill deployment lists and the `profile_souls` entries of `roster.yaml` do not name them.
- **Still retired, on disk, unchanged:** the legacy `worker-flash-1`, `worker-flash-2`, `worker-flash-3` and `worker-glm-full` stay in `/Users/chanbla11mit/.hermes/profiles/`. They are inert. They are in no `kanban.dispatch_profiles` list. The owner decided on 2026-10-19 to keep the GLM profiles and mark them retired: `roster.yaml` declares each of the four with `"lifecycle": "retired"`, `dispatch_eligible` and `in_dispatch_pool` false, so `scripts/verify-state` checks their model and approval mode like any installed profile and fails if one becomes dispatchable or returns to a dispatch list or pool. They are the `RETIRED_PROFILES` floor of `scripts/verify-state`. The GPT-era profiles above carry the same retired lifecycle.
- **Archived copies:** `/Users/chanbla11mit/.hermes/profile-exports/<name>-20261018-*.tar.gz` (mode 600), made with `hermes profile export`. Exports exclude `.env` and `auth.json`.
- **Restoring one:** `hermes profile import <archive>`, then re-add the z.ai credential with `hermes -p <profile> auth add zai`, then `scripts/switch-profile-model --profile <profile> --to glm --dispatch add`. Also return it to an active lifecycle in `roster.yaml` and add it to the snapshot dispatch list, or `scripts/verify-state` reports the dispatch entry as drift. A profile of the `RETIRED_PROFILES` floor additionally needs that floor in `scripts/verify-state` changed by a reviewed card.

## Switching one profile

`scripts/switch-profile-model` sets a profile's main model, base URL and all sixteen helper tasks in one step, after backing up its `config.yaml`. It also updates that profile's `model` and `provider` in the `roster.yaml` of the checkout it runs from (`--roster` picks another file); commit that change, or `scripts/verify-state` reports model drift. Preview both the live and the roster changes with `--dry-run`, which writes nothing. `scripts/verify-state` also fails when a non-retired roster profile is outside the owner model policy (provider `claude-subscription`; `claude-fable-5-2` for the orchestrators, `default` and the advisor; `claude-opus-5-5` for the workers and the reviewers; `glm-5.3` on `zai` for the ten GLM workers in service; see "Role models and reasoning effort" below), so an out-of-policy switch stays red until the policy itself is changed.

```sh
scripts/switch-profile-model --profile harness-worker --to glm                       # GLM 5.3 everywhere
scripts/switch-profile-model --profile harness-worker --to gpt --model gpt-6.1-sol   # back to GPT
scripts/switch-profile-model --profile harness-reviewer --to claude-fable            # Fable main, Haiku and Opus helpers
scripts/switch-profile-model --profile default --to claude-opus                      # the main ~/.hermes home
scripts/switch-profile-model --profile worker-sol --to gpt --dispatch add            # put a GPT worker back on Kanban
```

- **Targets:**
  - `claude-opus`: `claude-opus-5-5`.
  - `claude-fable`: `claude-fable-5-2`.
  - `gpt`: `openai-codex`, default `gpt-5.6-sol`.
  - `glm`: `zai`, default `glm-5.3`.
- **Helpers under both Claude targets (`claude-opus` and `claude-fable`):** the six light helper tasks (`LIGHT_HELPER_TASKS` in `scripts/verify-state`: `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub`, `vision`) go to `claude-haiku-5-5`, and the other ten helper tasks go to `claude-opus-5-5`, all on `claude-subscription` (card `t_e7efc35f`; live record in [`haiku-helper-routing.md`](haiku-helper-routing.md)). Under `claude-fable` this means the helpers do not follow the Fable main model.
- **Helpers under `gpt` and `glm`** follow the main model. Pass `--model` to choose another main model id; under the Claude targets it changes only the main model.
- **Before switching to GPT:** the OpenAI login must be valid again (`hermes -p <profile> auth status openai-codex`). Use a model your plan offers.
- **Before switching to Claude:** the profile needs the plugin in `plugins/model-providers/claude-subscription/`, and `HERMES_CLAUDE_SUBSCRIPTION_CLI` and `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` in its `.env`.
- **When changes take effect:** new Kanban tasks and new gateway turns pick up the change. Running tasks finish on their current model.
- **Restoring a whole profile instead:** copy its `config.yaml.pre-claude-261017` back over `config.yaml`.

## Role models and reasoning effort

Owner decision of 2026-11-13, applied by card `t_0faca45d`: the five reviewers moved from `claude-fable-5-2` to `claude-opus-5-5`, and the six orchestrators (`default` and the five project orchestrators) moved from `claude-opus-5-5` to `claude-fable-5-2`. `roster.yaml` and the `MODEL_POLICY_BY_ROLE` constant of `scripts/verify-state` hold the main model of each role. Neither holds `agent.reasoning_effort`, so this table is the record of it; read it with `hermes -p <profile> config get agent.reasoning_effort` (`hermes config get agent.reasoning_effort` for `default`).

| Role | Profiles | Main model | `agent.reasoning_effort` | Main fallback (`fallback_providers`) |
| --- | --- | --- | --- | --- |
| Orchestrator | `default` (`/Users/chanbla11mit/.hermes/config.yaml`), `jobcron-orchestrator`, `chapt-orchestrator`, `harness-orchestrator`, `jss-orchestrator`, `anki-orchestrator` | `claude-fable-5-2` | `medium` | `anthropic` / `claude-fable-5-2` |
| Reviewer | `jobcron-reviewer`, `chapt-reviewer`, `harness-reviewer`, `jss-reviewer`, `anki-reviewer` | `claude-opus-5-5` | `high` | `anthropic` / `claude-opus-5-5` |
| Claude worker | `<board>-worker`, `<board>-worker-2` of the five boards | `claude-opus-5-5` | unchanged by `t_0faca45d` | `anthropic` / `claude-opus-5-5` |
| Advisor | `advisor` | `claude-fable-5-2` | unchanged by `t_0faca45d` | `anthropic` / `claude-fable-5-2` |

The helper tasks are the same under both Claude targets (see "Helpers under both Claude targets" above). `scripts/switch-profile-model` does not set `agent.reasoning_effort`; set it with `hermes -p <profile> config set agent.reasoning_effort <value>`. To change a role's main model: edit the profile's `fallback_providers` model in `roster.yaml` to the new main model, run `scripts/switch-profile-model --profile <name> --to <target>`, then `scripts/switch-profile-model --profile <name> --apply-fallbacks`, and change `MODEL_POLICY_BY_ROLE` in `scripts/verify-state` in the same reviewed change.

`default` is an exception for the helper tasks. On `default` the six light helper tasks run on `claude-opus-5-5`, not `claude-haiku-5-5` (`default` was outside card `t_e7efc35f`, see [`haiku-helper-routing.md`](haiku-helper-routing.md)), and `roster.yaml` declares no `auxiliary_models` for it. A `--to claude-opus` or `--to claude-fable` run on `default` writes `claude-haiku-5-5` to those six tasks. Card `t_0faca45d` set them back after its switch on 2026-11-13: `hermes -p default config set auxiliary.<task>.model claude-opus-5-5` for `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub` and `vision`. Run the script for `default` with `HERMES_HOME` unset (`env -u HERMES_HOME`): the script runs `hermes config set` without `-p` for `default`, and inside a dispatched session `HERMES_HOME` names that session's own profile.

## Fallback providers

The script also manages fallback providers. `--apply-fallbacks` writes the `fallback_providers` and `auxiliary_fallback_chain` values that the profile's `roster.yaml` entry declares, and `--clear-fallbacks` sets them to empty lists. Both work with or without `--to` and honor `--dry-run`. `scripts/verify-state` reports any difference as `fallback drift`. The owner-approved Anthropic API fallback for the four Jobcron profiles, including the credential steps and the revert after 2026-11-19, is in [`anthropic-api-fallback.md`](anthropic-api-fallback.md).
