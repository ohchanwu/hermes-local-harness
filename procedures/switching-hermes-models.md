# Switching Hermes profiles between Claude, GPT and GLM

State on 2026-10-17: every active profile runs on the Claude subscription provider. See the [provider README](../plugins/model-providers/claude-subscription/README.md#rollout-status-2026-10-17-kst) for the role-by-role table. OpenAI (GPT) was retired from 2026-10-18. GLM (z.ai) profiles are unchanged and still usable.

## Where the GPT profiles are kept

- **On disk, unchanged:** `reviewer-sol`, `worker-sol`, `worker-astra`, `worker-luna-1`, `worker-luna-2`, `worker-terra-1`, `worker-terra-2` stay in `~/.hermes/profiles/` with their config, `.env` and history. They are inert. They are in no `kanban.dispatch_profiles` list and have no chat connection.
- **Archived copies:** `~/.hermes/profile-exports/<name>-20261017-18*.tar.gz` (mode 600), made with `hermes profile export`. Exports deliberately exclude `.env` and `auth.json`. A profile restored with `hermes profile import <archive>` needs those re-created.
- **Config backups of the Claude profiles:** in each home, `config.yaml.pre-claude-261017` is the state before any Claude change. `config.yaml.pre-helpers-261017` is the state before helpers moved off GPT. The switch script below writes `config.yaml.pre-switch-<timestamp>` on every run.

## Switching one profile

`scripts/switch-profile-model` sets a profile's main model, base URL and all sixteen helper tasks in one step, after backing up its `config.yaml`. Preview with `--dry-run`.

```sh
scripts/switch-profile-model --profile harness-worker --to glm                       # GLM 5.3 everywhere
scripts/switch-profile-model --profile harness-worker --to gpt --model gpt-6.1-sol   # back to GPT
scripts/switch-profile-model --profile harness-reviewer --to claude-fable            # Fable main, Opus helpers
scripts/switch-profile-model --profile default --to claude-opus                      # the main ~/.hermes home
scripts/switch-profile-model --profile worker-sol --to gpt --dispatch add            # put a GPT worker back on Kanban
```

- **Targets:**
  - `claude-opus`: `claude-opus-5-5`.
  - `claude-fable`: `claude-fable-5-1`, with helpers on Opus.
  - `gpt`: `openai-codex`, default `gpt-5.6-sol`.
  - `glm`: `zai`, default `glm-5.3`.
- **Helpers follow the main model**, except under `claude-fable`. Pass `--model` to choose another model id.
- **Before switching to GPT:** the OpenAI login must be valid again (`hermes -p <profile> auth status openai-codex`). Use a model your plan offers.
- **Before switching to Claude:** the profile needs the plugin in `plugins/model-providers/claude-subscription/`, and `HERMES_CLAUDE_SUBSCRIPTION_CLI` and `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` in its `.env`.
- **When changes take effect:** new Kanban tasks and new gateway turns pick up the change. Running tasks finish on their current model.
- **Restoring a whole profile instead:** copy its `config.yaml.pre-claude-261017` back over `config.yaml`.
