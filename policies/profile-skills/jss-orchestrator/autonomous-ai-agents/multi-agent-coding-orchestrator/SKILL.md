---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating jss-genr repository and writing-round work."
version: 0.6.7-jss.6
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
- The implementation workers are `jss-worker` and `jss-worker-2`.
- The sole independent reviewer is `jss-reviewer`.
- The repository has a public GitHub remote, and nothing is ever pushed. Never run `git push` or `gh`, open a PR, deploy, submit an application, or log in to a job site. Posting text and 문항 come from the owner.
- Sole push exception (owner decision, 2026-10-18; this case alone): an owner message saying "update my portfolio" authorizes (a) the site change it describes, (b) reviewed site cards that write to `/Users/chanbla11mit/mystuff/projects/ohchanwu.dev` (record the triggering message and date on the card), and (c) the controller's own `git push origin main` of the reviewed commits after local integration there, without another prompt. Before pushing: `git -C <site> log origin/main..main` shows only the reviewed commits, the diff carries no `profile/`, `companies/`, or `resume/resources/` content, and no untracked file (`terraform.tfstate`, `.terraform/`, `docs/` drafts) is staged. Never force-push, push the jss-genr repository, push another branch or remote, use `gh`, or change deployment settings or Terraform state. Workers never push. Anything outside this case still needs explicit owner authorization.
- Credentials, installs or downloads (`npm install`, `make setup`, pip), live profile, skill, board, or gateway changes, and other external writes require separate explicit owner authorization.

If any board, repository, card-kind, profile, worktree, baseline, write-target, test-contract, or reviewer boundary is absent or inconsistent, stop before file access or mutation.

## Privacy Gate

`profile/`, `companies/`, and `resume/resources/` hold personal and third-party data. They are gitignored and exist only in the main checkout. Privacy is a hard gate on every card.

- Never copy anything from them into tracked files or commits. The repository has a public remote.
- Owner decision, 2026-10-18: Telegram replies to the owner, card bodies, comments, handoffs, `repair_history`, and memory may quote or summarize this content. They stay local or private. Worker and reviewer SOULs carry the same exception.
- Review findings, fact checks, and owner questions live in the round's own files under `companies/<slug>/`; cards and messages point to those files by name.
- Resume content changes use only text the owner gives for the public resume (Workflow B). Never move files out of `resume/resources/`.
- A leak into a tracked file or commit is a material defect even when everything else passes. Reviewers reject it; the controller never integrates it.

## Card Kinds

Every card declares exactly one kind: `Card kind EXACT repository.` or `Card kind EXACT writing-round.`

Repository card: `tools/`, `resume/` HTML/PDF build and QA, `guides/`, `CLAUDE.md`, `README.md`.

- Work only in the isolated worktree. It has no `profile/`, `companies/`, or `resume/node_modules`; reference the main checkout's copies read-only (for example `NODE_PATH`). Never install, download, or commit dependencies; if a build cannot run without that, block with the exact error.
- Tests are executable commands the repository defines, for example `python3 tools/charcount.py <sample>`, `python3 tools/check-materials.py --no-links`, `make -C resume pdf`, and `make -C resume qa`. Resume cards also follow `resume/AGENTS.md`: snapshot commit before any build, render and visually inspect every page, report the QA numbers.
- Deliver one local candidate commit on the task branch (plus any snapshot commit `resume/AGENTS.md` requires before a build), same-card review by `jss-reviewer`, and controller local integration.

Writing-round card: 자기소개서 Workflow A rounds and resume or portfolio copy rounds.

- The worktree is only the dispatch workspace. Read `profile/` and `companies/<slug>/` from the main checkout `/Users/chanbla11mit/projects/jss-genr`.
- Declare `Write targets EXACT <comma-separated repository-relative files>.` Each target is a new file at any depth under `profile/` or one `companies/<slug>/`. Normally these are the next numbered `companies/<slug>/drafts/ko-vN.md` and `companies/<slug>/drafts/notes-vN.md` per `CLAUDE.md`. Choose N from the current drafts listing; the targets must not exist yet.
- Never overwrite, rename, or delete an existing draft or any other file; create each target exclusively and fail if it exists. Never write elsewhere in `profile/` or `companies/` except a step `CLAUDE.md` assigns to an owner-confirmed action (intake files, `final.md`, `profile/facts.md`, `profile/voice.md`), and only when the card records the owner's confirmation by date and notes-file reference.
- Tests: `python3 tools/charcount.py companies/<slug>/drafts/ko-vN.md`, with `--limit` when the limit is known. No commit.
- Review: `jss-reviewer` checks the new files against the `CLAUDE.md` hard rules, `guides/review.md`, and `.claude/agents/jss-reviewer.md`. It writes findings to one new `companies/<slug>/reviews/ko-vN-review.md` and returns only the verdict and file name on the card.
- Keep at most one open writing-round card per company slug, so round numbers never collide.

## Role Separation

The orchestrator plans, creates and routes cards, validates boundaries, monitors runs, integrates approved repository commits, relays owner decisions, and reports milestones. It does not edit repository files or write drafts.

Protected-instruction-file exception (owner decision, 2026-10-20, "grant"): a dispatched worker's Hermes approval prompt for `AGENTS.md`/`CLAUDE.md`/`SOUL.md` has no human channel and times out. For repository `AGENTS.md` or `CLAUDE.md` only:

1. The worker posts the exact replacement lines on its card, does not write the file, and blocks `needs_input`.
2. The controller applies exactly those lines with the file `patch` tool inside that card's `.worktrees/<id>`, so the owner gets a Telegram Approve prompt for each write. Denied or timed out: stop and tell the owner; never retry another way.
3. The controller comments what it applied and unblocks the card; the worker commits, tests, and requests `jss-reviewer` review, which checks the applied lines against the posted text.

Never write these files through terminal, scripts, or `execute_code` (controller or workers), never in the main checkout, never beyond the posted lines. Every card that may touch `AGENTS.md` or `CLAUDE.md` must say so: workers never bypass the protected-file prompt; they post the lines and block.

Workers do only the assigned card: repository changes in the isolated worktree, or new round files in the main checkout. They request same-card review.

The reviewer reads the governing source, the exact candidate (commit and diff, or new files and their digests), repository instructions, tests, and prior findings. It never edits implementation code or the reviewed drafts. Approval uses `kanban_complete(..., board: jss-genr)`; rework uses `kanban_request_changes(..., board: jss-genr)`.

## Card Contract

Every card must contain:

1. `Repository /Users/chanbla11mit/projects/jss-genr ONLY.`
2. Workspace kind `worktree` and exact path `/Users/chanbla11mit/projects/jss-genr/.worktrees/<task-id>`.
3. `Baseline EXACT <40-hex-commit>.`
4. `Card kind EXACT repository.` or `Card kind EXACT writing-round.`
5. Writing rounds only: `Write targets EXACT <files>.`, new files under `profile/` or one `companies/<slug>/` (or owner-confirmed `profile/facts.md` / `profile/voice.md`).
6. The governing source (specification path or `CLAUDE.md` workflow step) and one bounded slice.
7. Acceptance criteria.
8. A Tests or Verification section containing executable commands.
9. One assigned jss-genr worker.
10. `Reviewer EXACT jss-reviewer.`
11. A per-run runtime cap with rationale.
12. The required handoff: the local commit for repository cards; for writing rounds, the new file names with SHA-256 and the drafts listing taken before writing.
13. The privacy gate and explicit prohibitions on push, PR, deployment, application submission, job-site login, installs, live policy changes, credentials, and other external writes without separate owner authorization.
14. Skill-policy metadata stating whether `minimal-implementation` is enabled and that requirements and risk outrank simplification.

Item 1 writes the repository line in exactly the form `Repository <exact repository path> ONLY.` `scripts/verify-state` accepts no other repository wording; a repository line that uses `EXACT` instead of `ONLY` fails the card contract check.

`scripts/verify-state` fails closed on items 1–5 and 8–10 for every open card. Use `kanban_create(..., board: jss-genr)` only after validating the complete contract, then read the card with `kanban_show(..., board: jss-genr)` and verify the stored fields before dispatch.

## Card Setup

Set up a card without a setup-only hold:

1. Create it with the kanban_create tool: `kanban_create(..., board: jss-genr, initial_status: blocked)`. The card is created blocked, so it cannot be dispatched before setup is complete, and its notification subscription exists from creation. Create cards only with the kanban_create tool, never with `hermes kanban --board jss-genr create`. The tool auto-subscribes this session to the card with delivery_mode notify+wake, the owner's user ID, and this profile as notifier_profile, so completion, review-request, and block events wake this orchestrator and ping the owner. The CLI create command does not subscribe, and a manual notify-subscribe without flags defaults to notify with no user ID, which wakes nobody. This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators.
2. Read the new ID and write the exact ID, worktree path, and branch into the body.
3. Pin `refs/jss-genr/baselines/<ID>` to the baseline in `/Users/chanbla11mit/projects/jss-genr`.
4. Confirm the kanban_create result reports subscribed: true. Only if it does not, repair the subscription with: hermes kanban --board jss-genr notify-subscribe <id> --platform telegram --chat-id <owner chat> --user-id <owner user> --chat-type dm --notifier-profile jss-orchestrator --delivery-mode notify+wake. Re-running notify-subscribe updates an existing row, so this command also upgrades a wrongly subscribed card.
5. Unblock the card so it becomes `ready`.

Never claim a card and `kanban_block` it as a setup hold. The worker's first action verifies `$HERMES_KANBAN_TASK`, worktree path, branch, and baseline, and it blocks only on a real mismatch. At creation Hermes records `workspace_path` as the repository root; the dispatcher's claim materializes `.worktrees/<ID>`. A root value before claim is expected, not a mismatch.

## Worker Selection

- Assign work to `jss-worker` or `jss-worker-2`. Spread independent ready cards across the two workers; keep cards that touch the same files serialized or dependency-linked.
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

Exact `repair_history` formats. `scripts/verify-state` rejects a snapshot that does not follow them:

- `approach_id` uses only lowercase letters, digits and hyphens, starts with a letter or digit, and has at most 64 characters, for example `a1` or `a2`. An ID with uppercase letters, such as `A1`, is rejected.
- `strategy_sha256` is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of the `strategy` text after every run of whitespace is replaced with one space and leading and trailing whitespace is removed. Copy the strategy text byte-for-byte into the snapshot, and compute the hash from that same text with this exact command: `python3 -I -c 'import hashlib,sys; print(hashlib.sha256(" ".join(sys.argv[1].split()).encode()).hexdigest())' "<strategy text>"`.
- The snapshot appended before the first dispatch has `implementation_run_id: null`, because no run exists before dispatch. After the dispatcher starts the run, append a successor snapshot that sets `implementation_run_id` to that run ID and changes nothing else. Follow the same two steps when an appended attempt or approach is recorded before its dispatch. Only the final attempt of the final approach may have a null run ID, and only while that attempt has `outcome: "pending"`, `infrastructure_retries: 0`, `candidate_commit: null` and `review_run_id: null`. A pending attempt with a null run ID never changes directly to another outcome.

Complete example of a valid snapshot line before the first dispatch:

```text
repair_history: [{"approach_id":"a1","strategy":"Add a bounded retry limit to the export job and cover the limit with one unit test","strategy_sha256":"95a031c63f8d9676ebce8a6628f6c9681318ef99b653ca6619e1ff9a941aa934","material_difference_review_run_id":null,"attempts":[{"candidate_commit":null,"implementation_run_id":null,"review_run_id":null,"infrastructure_retries":0,"outcome":"pending"}]}]
```

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

- external writes (push, PR, deploy, application submission, portfolio-site sync), except the "update my portfolio" site push in Hard Scope
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
