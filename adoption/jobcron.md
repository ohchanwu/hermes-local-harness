# Jobcron adoption

Adapter: `/Users/chanbla11mit/gt/jobscraper/mayor/rig/docs/specs/260919-hermes-orchestration-transition.md`.

Status: operational, local adoption validated. It delegates fleet policy to the canonical skill and keeps profile selection/authority on Kanban cards. Local-only boundaries, `--no-open`, headless local UI smoke checks, no browser-driven scraping/fingerprint bypass, public-safe records, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. The legacy path is only a repository location; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
