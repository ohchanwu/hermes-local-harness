# Cha PT adoption

Adapter: `/Users/chanbla11mit/projects/cha-pt/docs/specs/260919-hermes-orchestration-transition.md`.

Status: operational, local adoption validated. It delegates fleet policy to the canonical skill and leaves profile selection/authority to Kanban cards. Use the clean canonical checkout under `/Users/chanbla11mit/projects/cha-pt`; use an assigned worktree for implementation. Task-scoped `minimal-implementation` (Ponytail plugin disabled on implementation profiles), loopback-only headless preview, public-safe records, sanitized/local data, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. Retained GT repositories are legacy recovery state, not canonical project checkouts; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
