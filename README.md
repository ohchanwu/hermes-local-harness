# Hermes local harness control

Private desired state for the local Hermes harness. This repository is not live state: `~/.hermes` is applied configuration, Kanban is execution history, and project repositories retain project-specific rules.

## Switching a profile's model (Claude, GPT, GLM)

Every active profile currently runs on the [Claude subscription provider](plugins/model-providers/claude-subscription/README.md#rollout-status-2026-10-17-kst). Opus 5.5 serves workers, orchestrators and the default home; Fable 5.1 serves reviewers and the Advisor. To move any profile, use `scripts/switch-profile-model`. It sets the main model and all sixteen helper jobs in one step, after backing up the profile's `config.yaml`:

```sh
scripts/switch-profile-model --profile harness-worker --to glm --dry-run            # preview only
scripts/switch-profile-model --profile harness-worker --to glm                       # GLM 5.3 (z.ai)
scripts/switch-profile-model --profile harness-worker --to gpt --model gpt-6.1-sol   # back to GPT
scripts/switch-profile-model --profile harness-reviewer --to claude-fable            # Fable main, Opus helpers
scripts/switch-profile-model --profile default --to claude-opus                      # the main ~/.hermes home
scripts/switch-profile-model --profile worker-sol --to gpt --dispatch add            # put a GPT worker back on Kanban
```

The retired GPT profiles stay in `~/.hermes/profiles/`, with archives in `~/.hermes/profile-exports/`. Each switch writes a `config.yaml.pre-switch-<timestamp>` backup. [`procedures/switching-hermes-models.md`](procedures/switching-hermes-models.md) covers the prerequisites: a valid OpenAI login for GPT, and the plugin plus its `.env` settings for Claude. It also covers restoring a whole profile.

`scripts/verify-state` is read-only. It uses only an explicit allowlist of Hermes CLI/config fields, the public shared skill files, and Hermes-source Git metadata. The JSON-formatted `.yaml` files intentionally need no YAML dependency. Canonical skill trees in `skills/` are copied into each profile's isolated skill home by the manual-apply procedure; profiles never share one on-disk skill file or live inheritance tree.

With `--fixture <path>`, the verifier compares that explicit sanitized observation to repository-owned desired state and tracked policies/skills; it does not read live external policy files or run CLI/network discovery. Without `--fixture`, verification observes live state, including external repository policy files and their required markers. A passing fixture is not proof of live deployment.

No apply script exists. See `procedures/manual-apply.md`. Durable specifications and plans are indexed in `docs/README.md`. Never commit credentials, runtime databases, transcripts, logs, or snapshots containing private state.

Launch concurrent project control planes from this repository with:

```sh
./scripts/run-jobcron-orchestrator
./scripts/run-chapt-orchestrator
./scripts/run-harness-orchestrator
```

These wrappers pin separate named boards before Hermes starts. Do not assign Kanban cards to orchestrator profiles; stock Hermes intentionally limits dispatcher-spawned task sessions to task-lifecycle tools. The Harness fleet's attended live rollout is complete and operational. Future live profile, policy, board, gateway, credential, or other external-state changes still require separate explicit human authorization.