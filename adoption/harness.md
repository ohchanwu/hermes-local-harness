# Hermes local harness adoption

Adapter: `/Users/chanbla11mit/hermes-local-harness/docs/specs/261004-concurrent-project-fleets.md`.

Status: operational; attended live rollout verified. Board `harness` is rooted solely at `/Users/chanbla11mit/hermes-local-harness` and routes only through `harness-orchestrator`, the worker pool (`harness-worker`, `harness-worker-glm-1`, `harness-worker-glm-2`), and `harness-reviewer`. The orchestrator and primary worker use `openai-codex/gpt-6.1-sol`; both GLM workers use `zai/glm-5.3`; the reviewer uses `openai-codex/gpt-6-astra`. Fresh inference probes succeeded for all five profiles.

Harness work is local-only by default. Local commits are permitted only in isolated task worktrees. Pushes, PRs, live profile or skill deployment, board or gateway changes, credentials, production/cloud mutations, and other external writes require separate explicit human authorization. `docs/bugs/` entries are evidence and triage input, not automatic implementation authorization. The harness orchestrator may not autonomously modify or deploy its own active live policy; repository policy changes require same-card `harness-reviewer` review, and live rollout is separately attended.
