# Concurrent project fleets

Status: implemented locally on 2026-10-04.

## Goal

Run autonomous Jobcron and Cha PT campaigns concurrently without sharing their orchestrator, implementation worker pool, reviewer, board database, Hermes profile state, repository root, worktree tree, preview port, logs, attachments, or evidence namespace.

## Topology

- Jobcron
  - board: `jobcron`
  - repository: `/Users/chanbla11mit/projects/jobcron`
  - orchestrator: `jobcron-orchestrator` — `openai-codex/gpt-6.1-sol`
  - worker pool: `jobcron-worker` — `openai-codex/gpt-6.1-sol`; `jobcron-worker-glm-1` and `jobcron-worker-glm-2` — `zai/glm-5.3`
  - reviewer: `jobcron-reviewer` — `openai-codex/gpt-6-astra`
  - preview port: `17777`, loopback, `--no-open`
- Cha PT
  - board: `cha-pt`
  - repository: `/Users/chanbla11mit/projects/cha-pt`
  - orchestrator: `chapt-orchestrator` — `openai-codex/gpt-6.1-sol`
  - worker pool: `chapt-worker` — `openai-codex/gpt-6.1-sol`; `chapt-worker-glm-1` and `chapt-worker-glm-2` — `zai/glm-5.3`
  - reviewer: `chapt-reviewer` — `openai-codex/gpt-6-astra`
  - preview port: `18080`, loopback; routine smoke tests do not start the shared production-shaped Compose stack

The default multiplexed gateway remains the only dispatcher owner. The ten project profiles set `kanban.dispatch_in_gateway: false`. The default profile's `kanban.dispatch_profiles` includes each project's three workers and reviewer, but deliberately excludes both orchestrators. `kanban.max_in_progress_per_profile: 1` permits three independent implementation runs per project while preventing duplicate runs on one profile.

Hermes intentionally hides board-routing tools such as `kanban_list` and `kanban_unblock` from every dispatcher-spawned task worker. Therefore each orchestrator runs as a normal interactive control-plane session with an explicit `HERMES_KANBAN_BOARD` pin; it must not be assigned a Kanban card.

## Isolation guarantees

Named Kanban boards are the hard task boundary: each has its own SQLite database, workspaces, logs, and attachments, and dispatcher-spawned workers receive board-pinned environment variables. Each project profile has its own Hermes home, configuration, memory, sessions, logs, and state database. Each board's `default_workdir` points to one canonical repository, so coding tasks receive project-local worktrees.

Hermes profiles are not filesystem sandboxes. Repository/profile pairing is therefore also enforced by fixed `terminal.cwd`, role-specific `SOUL.md`, the canonical orchestration skill, explicit reviewer names, and `scripts/verify-state`. A card with a mismatched board, profile, repository, or workspace must block before file access or mutation.

## Operations

Launch interactive controllers in separate terminals or tmux panes through the tracked wrappers:

```sh
./scripts/run-jobcron-orchestrator
./scripts/run-chapt-orchestrator
```

The wrappers pin `HERMES_KANBAN_BOARD` before Hermes starts, so concurrent sessions cannot race on the global `kanban/current` pointer.

Human or script operations must always name the board:

```sh
hermes kanban --board jobcron list
hermes kanban --board cha-pt list
```

Every coding card must use a board-local worktree, identify its baseline and repository, assign only a worker from the matching project pool, and request only the matching reviewer. Sol is the routine bounded lane; GLM Full is preferred for large-context, repo-wide, long-horizon, multimodal, visual, or broadly specified work. Review revisions return to the same assignee unless a capability-bound continuation card explicitly preserves lineage and evidence.

## Upgrade and rollback

Hermes core is unmodified. The topology uses supported profiles, profile configuration, named boards, board default workdirs, the multiplex gateway, Kanban dispatch, skills, and Git worktrees.

Recovery point: `/Users/chanbla11mit/.hermes/backups/pre-update-2026-10-04-144022.zip`.

Rollback is additive: pause dispatch, remove the ten project profiles from the default dispatch allowlist, switch operators back to the legacy `default` board/profile, and archive (not delete) the named boards. Preserve project profiles and boards until their history is no longer needed. Restoring the full pre-update archive is the last-resort machine-wide rollback, not the normal topology rollback.

## Verification receipt

Verified on 2026-10-04 against Hermes `v0.21.5+6751.g9cf7960`, source commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6`. The tested rollback archive is `/Users/chanbla11mit/.hermes/backups/pre-update-2026-10-04-144022.zip`.

- Fresh model probes returned `gpt-6.1-sol` for both orchestrators and workers, and `gpt-6-astra` for both reviewers. Session receipts: `20261004_150701_63ea4b`, `20261004_150721_06f2b1`, `20261004_150727_d6d7fe`, `20261004_150735_592c54`, `20261004_150741_2cbc6a`, and `20261004_150748_9a9bce`.
- The four added project-pool profiles returned `zai/glm-5.3` on fresh probes: Jobcron `20261004_165429_6313f6`, `20261004_165438_4ff234`; Cha PT `20261004_165446_32ba09`, `20261004_165454_eb8ab8`.
- The gateway independently claimed all four added profiles on their matching boards, created project-local worktrees, and completed read-only registration cards: Jobcron `t_7268f2a6`, `t_b4b74b8d`; Cha PT `t_acb22637`, `t_0c296753`. Each run reported its assigned profile, `zai/glm-5.3`, matching board/repository, clean worktree, and no file or external writes.
- Both board-pinning wrappers exposed `kanban_list`, saw their own board task, and did not see the foreign-board task. Session receipts: `20261004_153001_30121a` and `20261004_153013_3ddeab`.
- The restarted stock gateway automatically claimed both named boards concurrently, created repository-local worktrees, routed worker handoffs to the matching reviewers, and completed both cards without manual dispatch: Jobcron `t_4360df63` (`jobcron-worker` run 4 → `jobcron-reviewer` run 5) and Cha PT `t_7c6cb6be` (`chapt-worker` run 4 → `chapt-reviewer` run 5).
- Worker and reviewer evidence independently confirmed board database, profile, workspace, Git top-level/common directory, branch, unchanged HEAD, and clean status. Neither project repository was edited or committed by the smoke tests.
- `tests/test_verify_state.py`, generated fixture checks, `scripts/verify-state`, `git diff --check`, and Gitleaks passed. The live verifier enforces that the multiplex gateway has no inherited `HERMES_KANBAN_DB` pin while the legacy terminal-notification LaunchAgent retains its own explicit default-board database path.
