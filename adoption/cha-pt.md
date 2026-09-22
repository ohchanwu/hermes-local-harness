# Cha PT adoption

Adapter: `/Users/chanbla11mit/gt/cha_pt/mayor/rig/docs/specs/260919-hermes-orchestration-transition.md`.

Status: operational, local adoption validated. It delegates fleet policy to the canonical skill and leaves profile selection/authority to Kanban cards. Preserve the dirty primary checkout and existing worktrees; use only an assigned worktree. Task-scoped `minimal-implementation` (Ponytail plugin disabled on implementation profiles), loopback-only headless preview, public-safe records, sanitized/local data, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. The legacy path is only a repository location; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
