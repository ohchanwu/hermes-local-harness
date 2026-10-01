# Jobcron adoption

Adapter: `/Users/chanbla11mit/projects/jobcron/docs/archive/2026-09-24-hermes-orchestration-transition/260919-hermes-orchestration-transition.md` (archived lifecycle location after the repository's docs taxonomy migration; the recorded transition is complete and was validated — current constraints below remain the operational adoption record).

Status: operational, local adoption validated. It delegates fleet policy to the canonical skill and keeps profile selection/authority on Kanban cards. Use the clean canonical checkout under `/Users/chanbla11mit/projects/jobcron`; use an assigned worktree for implementation. Local-only boundaries, `--no-open`, headless local UI smoke checks, no browser-driven scraping/fingerprint bypass, public-safe records, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. Retained GT repositories are legacy recovery state, not canonical project checkouts; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
