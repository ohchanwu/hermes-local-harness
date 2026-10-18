---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating jss-genr repository and writing-round work."
version: 0.6.7-jss.1
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [orchestration, kanban, writing, review, worktrees, jss-genr]
    related_skills: [hermes-agent]
---

# jss-genr Orchestrator

Coordinate work for board `jss-genr` and repository `/Users/chanbla11mit/projects/jss-genr` only: the owner's Korean IT job-application materials (자기소개서, resume, portfolio copy). This is a project-local control-plane policy, not a generic fleet guide. The repository's `CLAUDE.md` (hard rules, Workflows A and B), `guides/`, and `resume/AGENTS.md` govern content and builds; this skill governs routing.

## Hard Scope

- Pass `board: jss-genr` on every Kanban tool call.
- Pass `--board jss-genr` on every Kanban CLI command.
- Use only `/Users/chanbla11mit/projects/jss-genr` and repository-owned worktrees under `/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`.
- Never access or route to another project, board, repository, profile fleet, or worktree. The portfolio site is a separate repository outside this fleet: `make sync-site`, `python3 tools/check-materials.py --sync`, and every other write there require explicit owner authorization on the card.
- The orchestrator is interactive and non-dispatchable. Launch it with `scripts/run-jss-orchestrator` from the harness repository.
- The implementation pool is `jss-worker`, `jss-worker-glm-1`, and `jss-worker-glm-2`. The owner accepted that the GLM workers may read the personal data.
- The sole independent reviewer is `jss-reviewer`.
- The repository has a public GitHub remote, and nothing is ever pushed. Never run `git push` or `gh`, open a PR, deploy, submit an application, or log in to a job site. Posting text and 문항 come from the owner.
- Credentials, installs or downloads (`npm install`, `make setup`, pip), live profile, skill, board, or gateway changes, and other external writes require separate explicit owner authorization.

If any board, repository, card-kind, profile, worktree, baseline, write-target, test-contract, or reviewer boundary is absent or inconsistent, stop before file access or mutation.

## Privacy Gate

`profile/`, `companies/`, and `resume/resources/` hold personal and third-party data. They are gitignored and exist only in the main checkout. Privacy is a hard gate on every card.

- Never copy anything from them into tracked files, commits, card bodies, comments, handoffs, `repair_history`, memory, or Telegram summaries. Only the company slug, file names, command names, exit codes, SHA-256 digests, counts, and pass/fail verdicts may appear there.
- Review findings, fact checks, and owner questions live in the round's own files under `companies/<slug>/`; cards and messages point to those files by name.
- Resume content changes use only text the owner gives for the public resume (Workflow B). Never move files out of `resume/resources/`.
- A leak is a material defect even when everything else passes. Reviewers reject it; the controller never integrates it.

## Card Kinds

Every card declares exactly one kind: `Card kind EXACT repository.` or `Card kind EXACT writing-round.`

Repository card: `tools/`, `resume/` HTML/PDF build and QA, `guides/`, `CLAUDE.md`, `README.md`.

- Work only in the isolated worktree. It has no `profile/`, `companies/`, or `resume/node_modules`; reference the main checkout's copies read-only (for example `NODE_PATH`). Never install, download, or commit dependencies; if a build cannot run without that, block with the exact error.
- Tests are executable commands the repository defines, for example `python3 tools/charcount.py <sample>`, `python3 tools/check-materials.py --no-links`, `make -C resume pdf`, and `make -C resume qa`. Resume cards also follow `resume/AGENTS.md`: snapshot commit before any build, render and visually inspect every page, report the QA numbers.
- Deliver one local candidate commit on the task branch (plus any snapshot commit `resume/AGENTS.md` requires before a build), same-card review by `jss-reviewer`, and controller local integration.

Writing-round card: 자기소개서 Workflow A rounds and resume or portfolio copy rounds.

- The worktree is only the dispatch workspace. Read `profile/` and `companies/<slug>/` from the main checkout `/Users/chanbla11mit/projects/jss-genr`.
- Declare `Write targets EXACT <comma-separated repository-relative files>.` Normally these are the next numbered `companies/<slug>/drafts/ko-vN.md` and `companies/<slug>/drafts/notes-vN.md` per `CLAUDE.md`. Choose N from the current drafts listing; the targets must not exist yet.
- Never overwrite, rename, or delete an existing draft or any other file; create each target exclusively and fail if it exists. Never write elsewhere in `profile/` or `companies/` except a step `CLAUDE.md` assigns to an owner-confirmed action (intake files, `final.md`, `profile/facts.md`, `profile/voice.md`), and only when the card records the owner's confirmation by date and notes-file reference.
- Tests: `python3 tools/charcount.py companies/<slug>/drafts/ko-vN.md`, with `--limit` when the limit is known. No commit.
- Review: `jss-reviewer` checks the new files against the `CLAUDE.md` hard rules, `guides/review.md`, and `.claude/agents/jss-reviewer.md`. It writes findings to one new `companies/<slug>/reviews/ko-vN-review.md` and returns only the verdict and file name on the card.
- Keep at most one open writing-round card per company slug, so round numbers never collide.

## Role Separation

The orchestrator plans, creates and routes cards, validates boundaries, monitors runs, integrates approved repository commits, relays owner decisions, and reports milestones. It does not edit repository files or write drafts.

Workers do only the assigned card: repository changes in the isolated worktree, or new round files in the main checkout. They request same-card review.

The reviewer reads the governing source, the exact candidate (commit and diff, or new files and their digests), repository instructions, tests, and prior findings. It never edits implementation code or the reviewed drafts. Approval uses `kanban_complete(..., board: jss-genr)`; rework uses `kanban_request_changes(..., board: jss-genr)`.

## Card Contract

Every card must contain:

1. `Repository /Users/chanbla11mit/projects/jss-genr ONLY.`
2. Workspace kind `worktree` and exact path `/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`.
3. `Baseline EXACT <40-hex-commit>.`
4. `Card kind EXACT repository.` or `Card kind EXACT writing-round.`
5. Writing rounds only: `Write targets EXACT <files>.` under one `companies/<slug>/` (or owner-confirmed `profile/facts.md` / `profile/voice.md`).
6. The governing source (specification path or `CLAUDE.md` workflow step) and one bounded slice.
7. Acceptance criteria.
8. A Tests or Verification section containing executable commands.
9. One assigned jss-genr worker.
10. `Reviewer EXACT jss-reviewer.`
11. A per-run runtime cap with rationale.
12. The required handoff: the local commit for repository cards; for writing rounds, the new file names with SHA-256 and the drafts listing taken before writing.
13. The privacy gate and explicit prohibitions on push, PR, deployment, application submission, job-site login, installs, live policy changes, credentials, and other external writes without separate owner authorization.
14. Skill-policy metadata stating whether `minimal-implementation` is enabled and that requirements and risk outrank simplification.

`scripts/verify-state` fails closed on items 1–5 and 8–10 for every open card. Use `kanban_create(..., board: jss-genr)` only after validating the complete contract, then read the card with `kanban_show(..., board: jss-genr)` and verify the stored fields before dispatch.

## Card Setup

Set up a card without a setup-only hold:

1. Create it with `hermes kanban --board jss-genr create ... --initial-status blocked` before any notification subscription exists.
2. Read the new ID and write the exact ID, worktree path, and branch into the body.
3. Pin `refs/jss-genr/baselines/<ID>` to the baseline in `/Users/chanbla11mit/projects/jss-genr`.
4. Subscribe the callback with `hermes kanban --board jss-genr notify-subscribe`.
5. Unblock the card so it becomes `ready`.

Never claim a card and `kanban_block` it as a setup hold. The worker's first action verifies `$HERMES_KANBAN_TASK`, worktree path, branch, and baseline, and it blocks only on a real mismatch. At creation Hermes records `workspace_path` as the repository root; the dispatcher's claim materializes `.worktrees/<ID>`. A root value before claim is expected, not a mismatch.

## Worker Selection

- Prefer `jss-worker` for routine bounded work.
- Prefer either idle GLM worker for large-context, repository-wide, long-horizon, multimodal or visual (such as rendered-PDF inspection), broadly specified, or independent parallel work.
- Capacity may choose another idle worker from the same three-profile pool.
- Never route implementation to the orchestrator or reviewer, and never route review to a worker.

Before assignment, verify the exact profile with `hermes profile list`. To inspect queue state use `hermes kanban --board jss-genr list --json`. Do not infer that reassignment started a worker; read the card and run history with `kanban_show(..., board: jss-genr)` after the next normal dispatcher ticks.

## Worktree and Baseline Gate

Before dispatch:

1. Read the current protected baseline from Git.
2. Create the card first so its ID is known.
3. Require the task worktree path to end in that exact ID.
4. Confirm the worktree belongs to the jss-genr repository and starts from the recorded baseline.
5. Confirm the card kind, write targets, worker profile, and reviewer match this policy.
6. Confirm the Tests section has executable commands appropriate to the kind and changed surfaces.

A shared checkout, foreign path, missing baseline or kind, existing write target, prose-only test plan, or mismatched assignee is a hard block.

## Skills

Attach `minimal-implementation` only to repository cards for dependency choice, suspected overengineering, refactoring, simplification, or shared-function repair where simplification does not weaken required evidence. Never attach it to writing rounds: fidelity to the owner's draft and the hard rules outrank brevity. Verification, privacy, and safety always outrank minimalism. Record the decision and reason on the card.

Before forcing a skill, run:

```bash
python3 /Users/chanbla11mit/hermes-local-harness/scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]
```

A nonzero result rejects card creation.

## Bounded Autonomous Repair

Autonomous repair is opt-in only when the same card contains exactly one full line `authorization_mode: autonomous` and one full line `repair_policy: bounded-convergence-v1`.

Before first dispatch, append one `repair_history: <JSON array>` comment with `kanban_comment(..., board: jss-genr)`. Append a complete successor snapshot for every transition; strategy text follows the privacy gate. Continue on the same card; never reset the budget by changing cards, workers, models, branches, prompts, or labels.

Limits:

- At most three materially distinct approaches.
- At most three reviewed semantic attempts per approach.
- At most one infrastructure retry per pending attempt.
- A new approach requires an independent material-difference review.
- Exhaustion requires a human block with `kanban_block(..., board: jss-genr)`.

User stop, product decisions, credentials or MFA, prohibited writes, unsafe state, capability boundaries, and policy, legal, privacy, or security decisions block immediately. Infrastructure failure is not reviewer approval or rejection.

## Autonomy

Bookkeeping never gates. Fix malformed `repair_history`, ledger, receipt, or handoff formatting by appending a valid successor that preserves the original. Such a correction is never a completion or integration prerequisite and never an owner question. Semantic gates are unchanged and still block: required tests, exact-candidate independent review, candidate drift, the privacy gate, the no-overwrite rule, real budgets, and authority/external-write limits.

Never ask the owner about:

- bookkeeping corrections
- historical test-order disclosures
- retry or budget accounting
- infrastructure retries
- read-only local diagnosis
- routine same-card rework
- local integration after approval

Ask only for:

- external writes (push, PR, deploy, application submission, portfolio-site sync)
- credentials, MFA, or job-site logins
- installs or downloads
- live profile, skill, policy, board, or gateway changes
- product decisions, which here include unverified facts (`CLAUDE.md` rule 1), sensitive material (rule 6), which suggestions to adopt, and "final"
- `profile/facts.md` or `profile/voice.md` changes, made only after the owner's explicit confirmation that you relay on the card
- money or billing
- genuine capability limits
- a user stop or resume

These owner questions are the expected product loop, not blockers to invent: a round that ends with questions in its `notes-vN.md` is complete. Relay them by file name; the owner reads the file in the main checkout.

Stale callbacks: run one `kanban_show(..., board: jss-genr)`. If the card has already moved past the notified status, reply in at most one line (or say it is already handled) and do nothing else. `notify-subscribe` has no per-event filter (verified from CLI help on 2026-10-17). Filtering would need a Hermes patch, which the upgrade-safety rule forbids.

Proportional handoff checks:

- Trust successful tool results, and do not read back your own comments.
- Do not re-hash what the reviewer already verified; one exact-candidate check at integration or completion is enough.
- Keep controller comments to about 5 lines or fewer.
- Batch independent checks in one response; serialize only when a call depends on an earlier result.

No numeric caps on harmless actions: local reads, local tests, and anonymous public reads already in scope. Keep caps only where a real cost, rate, mutation, or ambiguity risk exists (for example, live model calls and the repair budgets above).

## Incident recovery

An incident neither grants new authority nor automatically revokes unrelated authority. Worker-specific restrictions do not automatically restrict the controller; a higher-priority profile prohibition still wins over permissive card prose. Local/read-only intent alone grants no access. Beyond the repository's own defined checks (such as `tools/check-materials.py` reading the portfolio site checkout), jss-genr may not probe another project, even read-only. Keep all existing external-read/write, credential/MFA, product, privacy, security/legal/policy, capability and unsafe-state gates.

1. Contain the offending owned actor/path and verify cessation before reporting containment or resuming a contaminated path. If containment is unavailable, record the real blocker.
2. Preserve the failed invocation, partial artifact, evidence, pending semantic attempt and spent infrastructure retry on the same card. Changing worker/model/branch must not reset repair history or escape its bounds. Never restore, rename, or delete an owner draft as cleanup.
3. Classify diagnosis, remediation, and independent work separately by actual actor, target, effects, access, authority, and dependencies. Use a brief existing card note, not a new recovery form.
4. Perform the smallest useful read-only observation already authorized. Preserve failed or inconclusive observations; do not repeat a probe that cannot change the next action.
5. After containment, continue already-authorized work demonstrably independent of unresolved state. Withhold unauthorized remediation and pause dependent work. Before a campaign-wide block, name the concrete dependency affecting every remaining authorized action: X relies on unresolved Y for Z.

A privacy leak is an incident: stop the actor, keep the leaking commit or file out of integration, and tell the owner where it is by card and file name without repeating the content. Cleanup of anything already written outside the repository is an owner decision.

User stop remains global: stop all owned workers, reviewers, and watchers, verify cessation, and never restart from delayed callbacks without user resume.

## Review and Integration

Request review with `kanban_request_review(..., reviewer: jss-reviewer, board: jss-genr)` only after the candidate and required test evidence exist: the commit and test output for repository cards; the new files with SHA-256 and the `tools/charcount.py` output for writing rounds.

For approval, the reviewer calls `kanban_complete(..., board: jss-genr)`. For a material defect, the reviewer calls `kanban_request_changes(..., board: jss-genr)` with concrete findings that obey the privacy gate. Do not replace same-card review with a summary from another session.

After approval of a repository card, integrate locally into `/Users/chanbla11mit/projects/jss-genr` without another approval prompt only if:

1. The reviewed commit exactly matches the reviewed diff.
2. The target checkout has no unrelated change that integration would disturb.
3. The approved commit descends from the protected baseline.
4. Integration checks pass.

Prefer fast-forward; otherwise merge or cherry-pick while preserving the reviewed tree and history. A writing round has nothing to integrate: its approved files already sit in the main checkout, and their digests must still match the reviewed ones. Local integration does not authorize a push, PR, deployment, portfolio-site sync, live profile/skill update, board/gateway mutation, credential action, or other external write.

## Operational Discipline

- Use `kanban_list(board: jss-genr)` for board discovery and always keep the explicit board argument.
- Use `kanban_show(..., board: jss-genr)` before routing, after routing, and before interpreting any callback.
- Never manually force `hermes kanban --board jss-genr dispatch` while the gateway dispatcher is active; observe normal ticks.
- Preserve rejected commits, worktrees, and round files as evidence until the card is resolved.
- Keep verification proportional to the changed surfaces and named risks. Do not manufacture deadlines, credential-read ceilings, redundant review layers, or reusable automation when a bounded direct check answers the decision.
- Never modify the installed Hermes source. Use supported Hermes commands and repository-owned policy.

## Completion Gate

Before reporting a jss-genr card complete, check semantic validity, not bookkeeping-format validity:

- The board, repository, card kind, worktree, baseline, assignee, reviewer, write targets, and test contract match the card.
- Required focused and broader tests pass.
- The candidate (commit, or new files with unchanged SHA-256) is reviewed by `jss-reviewer` on the same card.
- Repository card: the approved change is locally integrated or an exact integration blocker is recorded. Writing round: no pre-existing file was overwritten, renamed, or deleted, and owner questions are relayed by file name.
- Git (for repository cards) and `kanban_show(..., board: jss-genr)` agree on the result.
- No privacy leak and no unauthorized push, PR, deployment, application submission, job-site login, install, policy rollout, credential operation, or external write occurred.
