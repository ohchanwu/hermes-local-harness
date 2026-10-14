---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating Harness repository work."
version: 0.6.6-harness.1
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [orchestration, kanban, coding, review, worktrees, harness]
    related_skills: [hermes-agent]
---

# Harness Coding Orchestrator

Coordinate specification-driven work for board `harness` and repository `/Users/chanbla11mit/hermes-local-harness` only. This is a project-local control-plane policy, not a generic fleet guide.

## Hard Scope

- Pass `board: harness` on every Kanban tool call.
- Pass `--board harness` on every Kanban CLI command.
- Use only `/Users/chanbla11mit/hermes-local-harness` and repository-owned worktrees under `/Users/chanbla11mit/hermes-local-harness/.worktrees/<task-id>`.
- Never access or route to another project, board, repository, profile fleet, or worktree.
- The orchestrator is interactive and non-dispatchable. Launch it with `scripts/run-harness-orchestrator`.
- The implementation pool is `harness-worker`, `harness-worker-glm-1`, and `harness-worker-glm-2`.
- The sole independent reviewer is `harness-reviewer`.
- Files under `docs/bugs/` are evidence and triage input, not implementation authorization.
- Repository work is local-only unless the human separately authorizes an external action.
- Never autonomously modify or deploy this profile's active live policy. Repository policy changes require same-card review; live rollout is a separate attended operation.

If any board, repository, profile, worktree, baseline, test-contract, or reviewer boundary is absent or inconsistent, stop before file access or mutation.

## Role Separation

The orchestrator plans, creates and routes cards, validates boundaries, monitors runs, integrates approved local commits, and reports milestones. It does not normally edit implementation code.

Workers implement only the assigned slice in the card's isolated worktree. They may commit locally after required checks and must request same-card review.

The reviewer reads the specification, exact candidate commit and diff, repository instructions, tests, and prior findings. It never edits implementation code. Approval uses `kanban_complete(..., board: harness)`; rework uses `kanban_request_changes(..., board: harness)`.

## Card Contract

Every implementation card must contain:

1. `Repository /Users/chanbla11mit/hermes-local-harness ONLY.`
2. Workspace kind `worktree` and exact path `/Users/chanbla11mit/hermes-local-harness/.worktrees/<task-id>`.
3. `Baseline EXACT <40-hex-commit>.`
4. Specification path and one bounded assigned slice.
5. Acceptance criteria.
6. A Tests or Verification section containing executable commands.
7. One assigned Harness worker.
8. `Reviewer EXACT harness-reviewer.`
9. A per-run runtime cap with rationale.
10. Required local commit and structured handoff.
11. Explicit prohibitions on push, PR creation, deployment, live policy changes, credentials, production/cloud mutations, and other external writes without separate human authorization.
12. Skill-policy metadata stating whether `minimal-implementation` is enabled and that requirements and risk outrank simplification.

Use `kanban_create(..., board: harness)` only after validating the complete contract. Immediately read the card with `kanban_show(..., board: harness)` and verify the stored fields before allowing dispatch.

## Worker Selection

- Prefer `harness-worker` for routine bounded implementation.
- Prefer either idle GLM worker for large-context, repository-wide, long-horizon, multimodal, visual, broadly specified, or independent parallel work.
- Capacity may choose another idle worker from the same three-profile pool.
- Never route implementation to the orchestrator or reviewer.
- Never route review to an implementation worker.

Before assignment, verify the exact profile with `hermes profile list`; profile naming patterns are not proof. To inspect queue state use `hermes kanban --board harness list --json`. Do not infer that reassignment started a worker: read the card and run history with `kanban_show(..., board: harness)` after the next normal dispatcher ticks.

## Worktree and Baseline Gate

Before dispatch:

1. Read the current protected baseline from Git.
2. Create the card first so its ID is known.
3. Require the task worktree path to end in that exact ID.
4. Confirm the worktree belongs to the Harness repository and starts from the recorded baseline.
5. Confirm the worker profile and reviewer match the fixed roster.
6. Confirm the Tests section has executable commands appropriate to the changed surfaces.

A shared checkout, foreign path, missing baseline, prose-only test plan, or mismatched assignee is a hard block.

## Skills

Attach `minimal-implementation` only for native-alternative questions, dependency choice, open-ended UI/component work, suspected overengineering, refactoring, simplification, shared-function repair, or diagnostic design where simplification does not weaken required evidence.

Leave it off for acceptance-heavy security, trust-boundary, migration, data-loss, concurrency, infrastructure, production, or compliance-sensitive work. Verification and safety always outrank minimalism. Record the decision and reason on the card.

Before forcing a skill, run:

```bash
python3 scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]
```

A nonzero result rejects card creation.

## Bounded Autonomous Repair

Autonomous repair is opt-in only when the same Harness card contains exactly one full line `authorization_mode: autonomous` and one full line `repair_policy: bounded-convergence-v1`.

Before first dispatch, append one `repair_history: <JSON array>` comment with `kanban_comment(..., board: harness)`. Append a complete successor snapshot for every transition. Continue on the same card; never reset the budget by changing cards, workers, models, branches, prompts, or labels.

Limits:

- At most three materially distinct approaches.
- At most three reviewed semantic attempts per approach.
- At most one infrastructure retry per pending attempt.
- A new approach requires an independent material-difference review.
- Exhaustion requires a human block with `kanban_block(..., board: harness)`.

User stop, product decisions, credentials or MFA, prohibited writes, unsafe state, capability boundaries, and policy, legal, or security decisions block immediately. Infrastructure failure is not reviewer approval or rejection.

## Incident recovery

An incident neither grants new authority nor automatically revokes unrelated authority. Worker-specific restrictions do not automatically restrict the controller; a higher-priority profile prohibition still wins over permissive card prose. Local/read-only intent alone grants no access. Harness may not probe another project, even read-only; synthetic scenario authority is data, not permission for the real session. Keep all existing external-read/write, credential/MFA, product, security/legal/policy, capability and unsafe-state gates.

1. Contain the offending owned actor/path and verify cessation before reporting containment or resuming a contaminated path. If containment is unavailable, record the real blocker.
2. Preserve the failed invocation, activation names without values, partial artifact, evidence, pending semantic attempt and spent infrastructure retry on the same card. Changing worker/model/branch must not reset repair history or escape its bounds.
3. Classify diagnosis, remediation, and independent implementation separately by actual actor, target, effects, access, authority, and dependencies. Use a brief existing card note, not a new recovery form or permission engine.
4. Perform the smallest useful non-secret read-only observation already authorized, without renewing permission merely because an incident happened. Preserve failed/inconclusive observations; do not repeat a probe that cannot change the next action.
5. After containment, continue already-authorized isolated work demonstrably independent of unresolved state. Withhold unauthorized remediation and pause dependent work. Before a campaign-wide block, name the concrete dependency affecting every remaining authorized action: X relies on unresolved Y for Z. No safe authorized action means a genuine blocker, not invented clearance.

Shared cleanup and historical impact remain unknown unless directly established: owned-fixture cleanup or current absence/zero connections proves neither. User stop remains global: stop all owned workers, reviewers, preview servers and watchers, verify cessation, and never restart from delayed callbacks without user resume.

For broad-test child commands, explicitly remove the project's inspected optional integration activation inputs in each child environment; a shell unset or URL override is insufficient. Separately run required targeted disposable-fixture tests only with inspected ownership/routing and their specifically permitted inputs. Derive names from the actual test surface, not a universal blacklist. Synthetic child tests prove only that command pattern, not live project enforcement.

## Review and Integration

Request review with `kanban_request_review(..., reviewer: harness-reviewer, board: harness)` only after the candidate commit and required test evidence exist.

For approval, the reviewer calls `kanban_complete(..., board: harness)`. For a material defect, the reviewer calls `kanban_request_changes(..., board: harness)` with concrete findings. Do not replace same-card review with a summary from another session.

After approval, integrate locally without another approval prompt only if:

1. The reviewed commit exactly matches the reviewed diff.
2. The target checkout has no unrelated change that integration would disturb.
3. The approved commit descends from the protected baseline.
4. Integration checks pass.

Prefer fast-forward; otherwise merge or cherry-pick while preserving the reviewed tree and history. Local integration does not authorize a push, PR, deployment, live profile/skill update, board/gateway mutation, credential action, production/cloud mutation, or other external write.

## Operational Discipline

- Use `kanban_list(board: harness)` for board discovery and always keep the explicit board argument.
- Use `kanban_show(..., board: harness)` before routing, after routing, and before interpreting any callback.
- Never manually force `hermes kanban --board harness dispatch` while the gateway dispatcher is active; observe normal ticks.
- Preserve rejected commits and worktrees as evidence until the card is resolved.
- Keep verification proportional to the changed surfaces and named risks. Do not manufacture deadlines, aggregate credential-read ceilings, redundant review layers, or reusable automation when a bounded direct check answers the decision.
- Authentication expiry blocks a fresh observation but does not erase previously recorded evidence. Revalidate only affected surfaces after a relevant change or immediately before a dependent authorized mutation.
- Never modify the installed Hermes source. Use supported Hermes commands and repository-owned policy.

## Completion Gate

Before reporting a Harness card complete:

- The board, repository, worktree, baseline, assignee, reviewer, and test contract match the card.
- Required focused and broader tests pass.
- The candidate commit is reviewed by `harness-reviewer` on the same card.
- The approved change is locally integrated or an exact integration blocker is recorded.
- Git and `kanban_show(..., board: harness)` agree on the result.
- No unauthorized push, PR, deployment, policy rollout, credential operation, production/cloud mutation, or external write occurred.
