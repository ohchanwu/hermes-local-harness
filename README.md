# Hermes local harness control

Private desired state for the local Hermes harness. This repository is not live state: `~/.hermes` is applied configuration, Kanban is execution history, and project repositories retain project-specific rules.

`scripts/verify-state` is read-only. It uses only an explicit allowlist of Hermes CLI/config fields, the public shared skill files, and Hermes-source Git metadata. The JSON-formatted `.yaml` files intentionally need no YAML dependency. Canonical skill trees in `skills/` are copied into each profile's isolated skill home by the manual-apply procedure; profiles never share one on-disk skill file or live inheritance tree.

No apply script exists. See `procedures/manual-apply.md`. Durable specifications and plans are indexed in `docs/README.md`. Never commit credentials, runtime databases, transcripts, logs, or snapshots containing private state.
