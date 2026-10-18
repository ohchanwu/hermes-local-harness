# jss-genr adoption

Adapter: `/Users/chanbla11mit/projects/jss-genr/CLAUDE.md` (the repository's own agent rules, adopted unchanged; this fleet never writes it outside an owner-scoped repository card). The verifier's adapter marker is the repository's public-push privacy boundary.

Status: defined in repository source; live setup pending. Board `jss-genr` is rooted solely at `/Users/chanbla11mit/projects/jss-genr` and routes only through `jss-orchestrator`, the worker pool (`jss-worker`, `jss-worker-glm-1`, `jss-worker-glm-2`), and `jss-reviewer`. The orchestrator and primary worker use `claude-subscription/claude-opus-5-5`; both GLM workers use `zai/glm-5.3` (the owner accepted that GLM workers may read the personal data); the reviewer uses `claude-subscription/claude-fable-5-1`. There is no preview-port contract. Launch the controller with `scripts/run-jss-orchestrator`.

Two card kinds, declared on every card: repository cards (`tools/`, `resume/` HTML/PDF build and QA, `guides/`, `CLAUDE.md`, `README.md`) work in an isolated worktree with executable tests, one local candidate commit, same-card `jss-reviewer` review, and controller local integration; writing-round cards (자기소개서 Workflow A rounds, resume or portfolio copy rounds) use the worktree only as the dispatch workspace and create only their declared new numbered files under `companies/<slug>/drafts/` in the main checkout, with no commit. Existing drafts are never overwritten or deleted.

Privacy is a hard gate: nothing from `profile/`, `companies/`, or `resume/resources/` is copied into tracked files, commits, card bodies, comments, handoffs, or Telegram summaries beyond the company slug and file names. The repository has a public GitHub remote; the fleet never pushes, opens PRs, deploys, submits applications, or logs in to job sites. Writes to the separate portfolio site repository (`make sync-site`, `tools/check-materials.py --sync`), installs, credentials, and live profile, skill, board, or gateway changes require separate explicit owner authorization.

GT dependency: none.
