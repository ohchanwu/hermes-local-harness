# Hermes local harness control

Private desired state for the local Hermes harness. This repository is not live state: `~/.hermes` is applied configuration, Kanban is execution history, and project repositories retain project-specific rules.

## Switching a profile's model (Claude, GPT, GLM)

Every active profile currently runs on the [Claude subscription provider](plugins/model-providers/claude-subscription/README.md#rollout-status-2026-10-17-kst). Since 2026-11-13 (card `t_0faca45d`), Fable 5.2 serves the orchestrators, the default home and the Advisor, and Opus 5.5 serves the workers and the reviewers; the reasoning effort of each role is in [`procedures/switching-hermes-models.md`](procedures/switching-hermes-models.md#role-models-and-reasoning-effort). Under both Claude targets, the six light helper tasks run on Haiku 5.5 and the other ten helper tasks run on Opus 5.5 ([`procedures/haiku-helper-routing.md`](procedures/haiku-helper-routing.md)). To move any profile, use `scripts/switch-profile-model`. It sets the main model and all sixteen helper jobs in one step, after backing up the profile's `config.yaml`:

```sh
scripts/switch-profile-model --profile harness-worker --to glm --dry-run            # preview only
scripts/switch-profile-model --profile harness-worker --to glm                       # GLM 5.3 (z.ai)
scripts/switch-profile-model --profile harness-worker --to gpt --model gpt-6.1-sol   # back to GPT
scripts/switch-profile-model --profile harness-reviewer --to claude-opus             # Opus main, Haiku and Opus helpers
scripts/switch-profile-model --profile default --to claude-fable                     # Fable main; the main /Users/chanbla11mit/.hermes home
scripts/switch-profile-model --profile worker-sol --to gpt --dispatch add            # put a GPT worker back on Kanban
```

The retired GPT profiles stay in `~/.hermes/profiles/`, with archives in `~/.hermes/profile-exports/`. Each switch writes a `config.yaml.pre-switch-<timestamp>` backup. [`procedures/switching-hermes-models.md`](procedures/switching-hermes-models.md) covers the prerequisites: a valid OpenAI login for GPT, and the plugin plus its `.env` settings for Claude. It also covers restoring a whole profile.

`scripts/verify-state` is read-only. It uses only an explicit allowlist of Hermes CLI/config fields, the public shared skill files, and Hermes-source Git metadata. The JSON-formatted `.yaml` files intentionally need no YAML dependency. Canonical skill trees in `skills/` are copied into each profile's isolated skill home by the manual-apply procedure; profiles never share one on-disk skill file or live inheritance tree.

Skill and SOUL expectations are derived, not pinned. `snapshots/sanitized-current-state.yaml` and `roster.yaml` declare which files each profile must carry and where (shared skills by `source` under `skills/` and a file list, profile-local overrides under `policies/profile-skills/<profile>/` as `tracked-source`, SOULs by `source`/`live` path); the verifier hashes the tracked source at check time. The reviewed repository is the truth, so changing a tracked skill or SOUL needs no pin edit and cannot leave a stale pin behind. The live-vs-repository comparison stays strict: an unchanged live copy then FAILs until it is redeployed, or until a reviewed card adopts the live content into the repository. A hash pin remains only where no tracked source exists (worker-astra's learned overrides, external repository policies). Retired roster profiles are excluded from shared-skill deployment checks. The default profile's skill home is `~/.hermes/skills`; every other profile's is its own `~/.hermes/profiles/<profile>/skills`. Current live drift is triaged in [`docs/state/261019-live-drift-triage.md`](docs/state/261019-live-drift-triage.md).

With `--fixture <path>`, the verifier compares that explicit sanitized observation to repository-owned desired state and tracked policies/skills; it does not read live external policy files or run CLI/network discovery. Without `--fixture`, verification observes live state, including external repository policy files and their required markers. A passing fixture is not proof of live deployment.

No apply script exists. See `procedures/manual-apply.md`. Durable specifications and plans are indexed in `docs/README.md`. Never commit credentials, runtime databases, transcripts, logs, or snapshots containing private state.

Launch concurrent project control planes from this repository with:

```sh
./scripts/run-jobcron-orchestrator
./scripts/run-chapt-orchestrator
./scripts/run-harness-orchestrator
```

These wrappers pin separate named boards before Hermes starts. Do not assign Kanban cards to orchestrator profiles; stock Hermes intentionally limits dispatcher-spawned task sessions to task-lifecycle tools. The Harness fleet's attended live rollout is complete and operational. Future live profile, policy, board, gateway, credential, or other external-state changes still require separate explicit human authorization.