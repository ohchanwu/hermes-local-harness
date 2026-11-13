# Jobcron adoption

Adapter: `/Users/chanbla11mit/projects/jobcron/docs/archive/2026-09-24-hermes-orchestration-transition/260919-hermes-orchestration-transition.md` (archived lifecycle location after the repository's docs taxonomy migration; the recorded transition is complete and was validated — current constraints below remain the operational adoption record).

Status: operational, local adoption validated. Board `jobcron` is rooted at `/Users/chanbla11mit/projects/jobcron` and routes only through `jobcron-orchestrator`, the workers `jobcron-worker` and `jobcron-worker-2`, and `jobcron-reviewer`. The orchestrator uses `claude-fable-5-2`; `jobcron-worker`, `jobcron-worker-2` and the reviewer use `claude-opus-5-5` (models since 2026-11-13, card `t_0faca45d`). Use an assigned board-local worktree for implementation. Local-only boundaries, `--no-open`, loopback preview port `17777`, headless local UI smoke checks, no browser-driven scraping/fingerprint bypass, public-safe records, and Go verification (`go test ./...`, `go vet ./...`, `gofmt -l .`) are repository-specific.

GT dependency: none operational. Retained GT repositories are legacy recovery state, not canonical project checkouts; this control repository neither invokes nor maintains GT services, agents, boards, databases, or workflows.
