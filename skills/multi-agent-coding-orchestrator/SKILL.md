---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating multi-agent coding with Hermes."
version: 0.3.1
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [orchestration, kanban, coding, review, worktrees]
    related_skills: [hermes-agent]
---

# Multi-Agent Coding Orchestrator

Coordinate specification-driven coding through Hermes profiles, Kanban, Git worktrees, and independent review. Prefer built-in Hermes mechanisms and the smallest upgrade-safe design that meets the current need.

## When to Use

- Planning or executing code changes through the model escalation fleet.
- Resuming an autonomous Jobcron or Cha Physical Therapy workstream.
- Routing, reviewing, escalating, integrating, pausing, or reporting Kanban work.

Do not use this procedure for a simple question that needs no repository change or multi-agent coordination.

## Fixed Roster

Control-plane profiles:

- `default`: `gpt-5.6-sol` orchestrator and user-facing profile.
- `reviewer-sol`: `gpt-5.6-sol` independent reviewer.
- `advisor`: `gpt-5.6-sol` read/analyze advisor; not a Kanban implementation lane.

Implementation profiles, in escalation order:

1. `worker-flash-1`, `worker-flash-2`, `worker-flash-3`: Z.AI `glm-5.3-flash`.
2. `worker-luna-1`, `worker-luna-2`: OpenAI Codex `gpt-5.6-luna`.
3. `worker-terra-1`: OpenAI Codex `gpt-5.6-terra`.
4. `worker-glm-full`: Z.AI `glm-5.3`.
5. `worker-sol`: OpenAI Codex `gpt-5.6-sol`.
6. `worker-astra`: OpenAI Codex `gpt-6-astra`.

Keep `worker-terra-2` installed but dormant as a rollback/spare lane. It is outside the active nine-lane roster unless the human changes the policy.

Ponytail never runs as a plugin on Hermes profiles. Implementation profiles keep the pinned package installed but `disabled`; the minimalism behavior lives in the per-card `minimal-implementation` skill instead (see Skills). The orchestrator, reviewer, and advisor neither load it nor the simplification skill.

## Skills

`minimal-implementation` is the task-triggered minimalism skill. The orchestrator attaches it per card (via `skills: ["minimal-implementation"]` on the card) using this policy:

- Attach for: native/platform-alternative questions, dependency or library choice, open-ended UI/component work, suspected overengineering, refactoring or simplification, and shared-function or root-cause repair.
- Leave off for: acceptance-heavy, security or trust-boundary, migration or data-loss, concurrency or distributed-systems, infrastructure or production, and compliance-sensitive tasks.
- Override: even for an attach-category task, the orchestrator may leave the skill off whenever verification or safety requirements outrank simplification. That is the direction of the override — verification and safety outrank minimalism, never the reverse.
- `simplification-review` is a separate, optional post-implementation review skill; it recommends reductions only and never edits or weakens tests. It is never a substitute for required verification.

Record the decision in card metadata: `skill_policy_version`, `minimal_implementation: enabled|disabled`, the reason, and that verification precedence applies (`verification_precedence: requirements-and-risk-outrank-simplification`). Reviewer and advisor lanes never load the implementation skill.

## Routing Rubric

Flash is the default entry rung. The Sol orchestrator may start directly at:

- Terra for substantial ambiguity, diagnosis, architecture, concurrency or security reasoning, risky migrations, unfamiliar subsystems, or complex multi-file work.
- GLM-full for large-context, repo-wide, long-horizon, multimodal or visual work, or broad but sufficiently specified execution.

Luna, Sol, and Astra are escalation rungs, not normal direct-entry rungs. A task that enters at Terra or GLM-full continues forward from that rung and never moves backward.

Before dispatch, record in the task body or an initial structured comment:

- `ladder_version: glm-review-v1`
- `entry_rung`
- `current_rung`
- protected baseline commit/checkpoint
- rung attempt count and same-rung revision count
- routing rationale

## Reviewer-Directed Failure Contract

The independent reviewer defines semantic task failure. Provider errors and process failures are infrastructure outcomes, not reviewer judgments.

The reviewer must issue exactly one verdict:

- `APPROVE`: acceptance criteria and required checks pass.
- `REVISE_SAME_RUNG`: localized correction at the current rung.
- `ESCALATE_CONTINUE`: advance one rung and preserve/continue the current artifact.
- `ESCALATE_RESTART`: preserve the rejected artifact for evidence, then restart from the recorded baseline at the next rung.
- `HUMAN_BLOCK`: stop automated execution and request human intervention.

Use `kanban_request_changes` only for `REVISE_SAME_RUNG`. For either escalation verdict, use `kanban_block` with a structured verdict so the task cannot race back to the previous implementer. The orchestrator reads the durable verdict, updates task history, safely reassigns the card, and explicitly promotes it to `ready`. Do not use `kanban_unblock` for this transition: a card blocked from review returns to the review lane when unblocked. Use `kanban_complete` only for `APPROVE`.

### Same-rung revision allowance

Allow one same-rung revision by default. The reviewer may grant one additional and final revision only when:

1. The prior substantive feedback substantially converged and remaining work is localized, mechanical, and unambiguous; or
2. The failed retry was caused primarily by incorrect, contradictory, incomplete, or materially ambiguous reviewer guidance.

Every revision consumes the allowance, including reviewer-caused retries. No rung may receive more than two `REVISE_SAME_RUNG` verdicts. Reviewer-caused failure must record what guidance was wrong, how it caused the retry failure, corrected actionable guidance, and whether independent worker error also occurred. Preserve attribution in task history and metrics; attribution never resets the allowance.

After the second revision, issue `APPROVE`, `ESCALATE_CONTINUE`, `ESCALATE_RESTART`, or `HUMAN_BLOCK`. Repeated worker failure, failure to resolve a substantive defect, newly discovered substantive inadequacy, or mixed responsibility containing material worker error ordinarily escalates instead of receiving the conditional second revision.

At Astra, any outcome that would advance beyond Astra, including exhausted revisions or repeated infrastructure failure, becomes `HUMAN_BLOCK` and notifies the human.

### Infrastructure failure

Retry one infrastructure failure at the same rung. Before retrying a timed-out run, increase its per-run runtime cap; never blindly requeue it under the cap that already proved insufficient. A second consecutive provider, quota, crash, timeout, unavailable-model, or context-exhaustion failure advances one rung with attribution `infrastructure`, not `worker_capability`. At Astra, block for human intervention. Never use provider fallback to silently traverse the semantic ladder inside one worker run.

## Escalation Mechanics

For `ESCALATE_CONTINUE`:

1. Preserve the current branch, commits, worktree, comments, test evidence, and reviewer findings.
2. Advance `current_rung` exactly once.
3. Activate the destination profile through the five-lane pool procedure if necessary.
4. Reassign the same card to the destination profile and use `hermes kanban promote <task>` (or the equivalent orchestrator action) to move the blocked review-origin card to `ready`.

For `ESCALATE_RESTART`:

1. Preserve the rejected attempt's branch and commit/checkpoint.
2. Create a fresh branch/worktree from the recorded baseline.
3. Point the same card at the clean worktree while retaining all prior comments and events.
4. Advance `current_rung`, assign the destination profile, and explicitly promote the card to `ready`.

Never delete rejected work merely because the next model starts clean. The same card remains the audit trail across all rungs.

## Five-Lane Implementation Pool

Installed profiles are capacity, not running work. Enforce a maximum of five simultaneous implementation runs with native per-profile capacity and a five-profile active allowlist:

- Leave `kanban.max_in_progress` unset because Hermes counts reviewer runs in that global number.
- Set `kanban.max_in_progress_per_profile` to `1`.
- Keep `reviewer-sol` in `kanban.dispatch_profiles` at all times.
- Keep no more than five implementation profiles in `kanban.dispatch_profiles` at once.
- Initially activate the three Flash lanes and two Luna lanes.
- Use `scripts/set-active-lanes.py` to change the active implementation profiles. It refuses to remove a running implementation profile, preventing a swap from temporarily creating a sixth implementation run.

A dormant profile may own a queued card, but it cannot run until the orchestrator safely activates it. When all five implementation slots are occupied, an escalation continuation waits rather than exceeding the cap. When capacity opens, activate the escalation profile before starting new low-rung work. Reviews remain independently dispatchable because `reviewer-sol` is outside the five-profile implementation pool and no shared global cap is set.

Priority order:

1. Review work.
2. Escalation continuation or restart.
3. Existing higher-rung work.
4. New low-rung work.

Do not remove a running profile from the active allowlist to make room; wait for an idle profile and then swap. Raise the implementation pool to seven and later nine only after sustained measurements of utilization, queueing, reviewer latency, provider limits, cost, and repository contention justify each increase and the human approves the policy change.

## Operating Principles

1. **KISS.** Use profiles, Kanban, worktrees, checkpoints, skills, and the gateway before custom plugins or daemons.
2. **Upgrade safety.** Never modify the installed Hermes source. Use documented configuration commands and user-local extension points.
3. **Orchestrate, do not implement.** The Sol orchestrator plans, decomposes, routes, unblocks, verifies, and integrates. It does not normally edit implementation code.
4. **Evidence over summaries.** Verify repository state, diffs, tests, task events, and review verdicts directly.
5. **One source for each concern.** Repository specs/status hold repository-specific intent and progress; Git holds code state; Kanban holds execution and handoffs; this skill holds shared fleet policy.
6. **No invisible ladder fallback.** Provider fallback may handle a transient retry within one profile, but it must not change the task's model rung without a durable reviewer or infrastructure escalation event.

## Authorization Modes

### Side-by-side

Discuss consequential decisions as they arise. Delegation is preferred for implementation, but no autonomous product run begins merely because a specification exists.

### Autonomous

Begin only when both conditions are true:

1. The specification and acceptance criteria are approved.
2. The user explicitly says `run autonomously` or an unambiguous equivalent for that specification.

For work expected to last hours or days, send the approved specification through an independent `reviewer-sol` preflight before dispatching implementation.

Authorization covers local branches, worktrees, commits, tests, and recoverable local destructive operations. It never covers pushes, PR creation, deployments, production mutations, messages beyond the configured progress protocol, purchases, credential changes, or other external writes.

## Cross-Session Startup

When the user refers to another session, "the spec," or prior work from another surface, recover the exact session record or literal source path first and verify that target exists. Telegram, CLI, TUI, and tmux conversations may share a profile without sharing conversational context; do not infer the intended artifact from a similar name.

1. Confirm repository root and current branch/status with `terminal`.
2. Read repository `AGENTS.md` and `docs/README.md`.
3. Read only the active specification, plan, decision, and status material relevant to the work.
4. Inspect the matching Kanban tenant and active task histories.
5. Reconcile repository state, Git branches/worktrees, active lane allowlist, and Kanban before changing status or dispatching work.

Completion criterion: the next action is grounded in current files, Git state, active lanes, and board state rather than transcript memory.

## Task Construction

Each implementation card must include:

- Repository and tenant.
- Specification path and exact assigned slice.
- Base branch or commit and recovery procedure.
- Required worktree/branch isolation.
- Acceptance criteria and test commands.
- An explicit per-run runtime cap and its rationale.
- Ladder metadata and routing rationale.
- Skill policy metadata (`minimal_implementation` enabled/disabled and reason; see Skills).
- Required local commit and structured handoff.
- `reviewer-sol` as same-card reviewer for code changes.
- Explicit prohibitions on push, PR creation, deployment, and production mutation.

Use parent-child links for real dependencies. Keep independent slices parallel. Do not decompose merely to keep every lane busy.

### Runtime budgeting

Estimate the whole worker attempt, not just editing time: repository discovery, implementation, focused tests, cross-platform or container matrices, broad regression gates, commits, and the review handoff all consume the same per-run budget.

- Keep the one-hour default only when the complete attempt is reasonably expected to finish within it.
- If the orchestrator suspects the attempt may exceed one hour, set `max_runtime_seconds` explicitly when creating the card. Use at least two to three hours for substantial implementation, security, infrastructure, migration, large-context, or broad-verification work, and use a longer evidence-based cap when the test matrix or prior measurements justify it.
- If any prior attempt timed out, increase the cap before the next attempt. Choose a value comfortably above the observed elapsed time and remaining work; do not merely add a few minutes.
- Prefer a larger bounded cap over splitting work solely to evade the timer. Split into dependent cards only when the stages have real independent acceptance criteria or handoffs.
- Preserve committed progress and timeout evidence. If the installed Hermes version cannot update an existing card's cap through a supported interface, do not edit the Kanban database directly; create an explicitly linked continuation card with the higher cap and durable handoff, then retire or block the superseded card without losing its audit trail.

## Worker Contract

1. Read the Kanban card, full comment history, and repository instructions.
2. Inspect relevant code before editing.
3. Implement only the assigned slice in the pinned worktree.
4. Run focused tests, then required broader gates.
5. Commit successful work locally.
6. Request review with `reviewer="reviewer-sol"` and concise evidence.
7. Block for a genuine decision, prohibited action, credential need, unsafe state, or infrastructure outcome that the orchestrator must classify.
8. Never push, open a PR, deploy, mutate production, or bypass review.

## Review Contract

Every code change requires independent Sol review before local integration. Inspect the specification, actual diff and commit, repository context, prior rung history, and test evidence. Do not edit implementation code.

Approve only when acceptance criteria pass and no material correctness, security, regression, or scope defect remains. Every non-approval must name the verdict, attribution, rung, revision count, findings, evidence, required next action, and whether continuation or a clean restart is safer.

## Integration

Reviewer approval authorizes and requires automatic local integration without asking. Integrate in the same turn that approval is observed; do not leave a successful branch isolated for the human to notice. Prefer a fast-forward when the reviewed branch descends from the target. Otherwise merge or cherry-pick while preserving the reviewed tree and history. Before integration:

1. Verify the reviewed commit matches the reviewed diff.
2. Verify the target checkout has no unrelated changes that integration would disturb. Preserve and restore concurrent work instead of overwriting it.
3. Integrate locally, preferring fast-forward, and run specification integration gates.
4. Verify the target branch contains the reviewed result, then update repository status and Kanban from observed results.

If integration is blocked, report the exact blocker immediately. Pushing, opening a PR, or deploying still requires explicit approval.

## Orchestrator Escape Hatch

The orchestrator may edit implementation code only after repeated delegation failures and only for a tiny surgical unblock. Record why delegation failed, keep the change minimal, run normal checks, commit locally, and require independent Sol review.

## Telegram Protocol

Send only milestone completions, genuine blockers, and approval requests. Do not stream routine heartbeats or verbose logs. A remote instruction may pause, resume, reprioritize, or clarify work, but repository and Kanban state remain authoritative.

## Pitfalls

- When the user says stop, terminate every owned background worker, reviewer, preview server, and watcher before replying, then verify they stopped. Do not resume because a delayed completion notification arrives.
- Run every Git command with an explicit repository `workdir` or `git -C`; printing a repository path inside a loop does not change the command's working repository.
- For Hermes plugin or service specifications, validate every required hook and payload against the installed source or current official documentation on each emitting surface. CLI, TUI, gateway, and automatic lifecycle paths can expose different identifiers and ordering.
- Standard `kanban_request_changes` immediately routes back to the original implementer; use a structured block for tier escalation to prevent a reassignment race. A normal unblock preserves review provenance and returns to review, so escalation must reassign and then explicitly promote the card to `ready`.
- Hermes's global `kanban.max_in_progress` counts review tasks. Do not use it for the implementation-only cap; enforce the active profile pool instead.
- Profile isolation does not isolate files. Every code-changing card needs its own worktree.
- A skill installed only under `default` cannot be force-loaded by a worker profile. Put the minimum role contract in each worker's `SOUL.md` and card.
- Never copy OpenAI Codex OAuth stores between profiles. Complete separate authorization when a profile needs an independent grant.
- Do not manually force `hermes kanban dispatch` while the gateway-embedded dispatcher is already active merely to accelerate a handoff. Let the next gateway tick claim it; overlapping immediate ticks can produce a short-lived duplicate/protocol-violation retry even though the board lock preserves correctness.
- Do not enable automatic decomposition until observed use shows manual decomposition is the bottleneck.

## Verification

Before declaring the harness or an autonomous workstream complete, verify:

- The Hermes source checkout is clean and updateable.
- Every active profile returns its configured model identity on a fresh inference probe.
- The active allowlist contains `reviewer-sol` and no more than the configured implementation-pool size.
- No running implementation profile was removed during a lane swap.
- Reviews can start while five implementation profiles are running.
- Every code change reaches independent review before integration.
- Every escalation has a durable verdict and advances exactly one rung.
- Rejected artifacts and clean-restart baselines remain recoverable.
- Git and Kanban contain no unexplained state.
- No push, PR, deployment, purchase, credential change, or other external write occurred without approval.
