# Jobcron adoption

Adapter: `/Users/chanbla11mit/projects/jobcron/docs/specs/260919-hermes-orchestration-transition.md`.

Status: operational, local adoption validated. It delegates fleet policy to the canonical skill and keeps profile selection/authority on Kanban cards. Use the clean canonical checkout under `/Users/chanbla11mit/projects/jobcron`; use an assigned worktree for implementation. Local-only boundaries, `--no-open`, headless local UI smoke checks, no browser-driven scraping/fingerprint bypass, public-safe records, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. Retained GT repositories are legacy recovery state, not canonical project checkouts; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
