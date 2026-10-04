# Cha PT adoption

Adapter: `/Users/chanbla11mit/projects/cha-pt/docs/archive/260919-hermes-orchestration-transition.md` (archived lifecycle location after the repository's docs taxonomy migration; the adapter content is unchanged).

Status: operational, local adoption validated. Board `cha-pt` is rooted at `/Users/chanbla11mit/projects/cha-pt` and routes only through `chapt-orchestrator`, the worker pool (`chapt-worker`, `chapt-worker-glm-1`, `chapt-worker-glm-2`), and `chapt-reviewer`. The orchestrator and primary worker use `gpt-6.1-sol`; both added workers use `glm-5.3`; the reviewer uses `gpt-6-astra`. Use an assigned board-local worktree for implementation. Task-scoped `minimal-implementation` (Ponytail plugin disabled on implementation profiles), loopback-only Go preview port `18080`, no routine startup of the shared production-shaped Compose stack, public-safe records, sanitized/local data, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. Retained GT repositories are legacy recovery state, not canonical project checkouts; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
