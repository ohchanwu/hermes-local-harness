---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating multi-agent coding with Hermes."
version: 0.6.4-jobcron.1
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

Project-isolated fleets:

- Jobcron board `jobcron`: `jobcron-orchestrator` (`gpt-6.1-sol`); implementation pool `jobcron-worker` (`gpt-6.1-sol`), `jobcron-worker-glm-1` and `jobcron-worker-glm-2` (both `glm-5.3`); independent `jobcron-reviewer` (`gpt-6-astra`). Repository root: `/Users/chanbla11mit/projects/jobcron`; preview port: `17777`.
- Cha PT board `cha-pt`: `chapt-orchestrator` (`gpt-6.1-sol`); implementation pool `chapt-worker` (`gpt-6.1-sol`), `chapt-worker-glm-1` and `chapt-worker-glm-2` (both `glm-5.3`); independent `chapt-reviewer` (`gpt-6-astra`). Repository root: `/Users/chanbla11mit/projects/cha-pt`; preview port: `18080`.

Each project profile has an independent Hermes home, memory, sessions, and fixed terminal root. Named boards provide separate databases, logs, attachments, and workspaces. A project orchestrator may assign only its matching worker pool and reviewer. A task or callback with a mismatched board, profile, repository, or workspace is invalid and must be blocked before file access or mutation.

Project orchestrators are interactive control-plane sessions, not dispatcher-spawned task workers. Hermes intentionally hides `kanban_list` and `kanban_unblock` whenever `HERMES_KANBAN_TASK` is set, so assigning a card to an orchestrator removes the board-routing tools it needs. Launch each controller through the tracked board-pinning wrapper (`scripts/run-jobcron-orchestrator` or `scripts/run-chapt-orchestrator`). Keep only project workers and reviewers in `kanban.dispatch_profiles`.

Each project has one Sol worker and two GLM Full workers. Use Sol for routine bounded implementation; prefer GLM Full for large-context, repo-wide, long-horizon, multimodal, visual, or broadly specified work, and use either idle GLM worker for independent parallel slices. Capacity alone may select another matching project worker, but never a foreign-project or legacy worker. Review revision stays on the same assignee unless the reviewer identifies a concrete capability boundary; then the orchestrator may create a continuation card for another worker in the same project pool with explicit lineage and preserved evidence.

### Autonomous project repair budget

Project-fleet repair is independent of the legacy escalation ladder. Enable it only when the exact `jobcron` or `cha-pt` card body records exactly one full line `authorization_mode: autonomous` and one full line `repair_policy: bounded-convergence-v1`. Before the first dispatch, append a card comment containing one single-line `repair_history: <JSON array>` snapshot; append a complete successor snapshot comment for every state transition. Kanban comments are the append-only card-wide counter and evidence ledger. Continue on the same card—bounded-convergence-v1 repair authority never transfers to a replacement card. Reassign the same card when authorized, or human-block.

Each approach object has exactly `approach_id`, `strategy`, `strategy_sha256`, `material_difference_review_run_id`, and `attempts`. The strategy hash is calculated from the whitespace-normalized written strategy; approaches after the first require a distinct independent material-difference review run. Each attempt has exactly `candidate_commit`, `implementation_run_id`, `review_run_id`, `infrastructure_retries`, and `outcome`. Start an in-flight attempt with null candidate/review and `outcome: pending`. A successor snapshot may update only that final pending attempt, append one next attempt, or append one next approach; all prior snapshot content remains immutable.

- `max_approaches: 3`: an approach is a materially distinct written implementation strategy. Hash the normalized strategy as `strategy_sha256`; changing a worker, model, card, branch, or worktree, prompt, commit, label, or approach ID is not a new approach. The verifier rejects reused IDs or exact strategy hashes; the independent reviewer must reject a superficial semantic rewrite.
- `max_attempts_per_approach: 3`: the initial implementation and at most two reviewer-directed corrections. Every completed semantic attempt records a unique 40-hex candidate commit and non-empty independent review run ID.
- `max_infrastructure_retries_per_attempt: 1`: retry the materially unchanged pending operation once after a provider, process, transport, timeout, unavailable-model, or environment failure. If that retry also fails, the attempt is spent and becomes `infrastructure_failed`; advance within the remaining attempt/approach budget or human-block. An implementation defect is not infrastructure failure.
- A rejected third attempt cannot be approved. Retire the approach and either begin one recorded materially different approach on the same card or human-block. A third attempt that independently passes may be `approve`.
- Exhausting three approaches always human-blocks under `bounded-convergence-v1`. Further work requires a newly authorized policy version or explicit amended limits on the exact card; retain the complete prior history rather than resetting v1.
- An approach stop is not a campaign stop. The orchestrator may autonomously reassess and continue within the remaining budget, but user stop, product decisions, credentials/MFA, prohibited or external writes, unsafe state, capability boundaries, and policy/legal/security decisions still human-block immediately.

Legacy/default-board control profiles remain installed for rollback and existing history:

- `default`: legacy `gpt-5.6-sol` orchestrator and user-facing profile.
- `reviewer-sol`: legacy `gpt-5.6-sol` independent reviewer.
- `advisor`: read/analyze advisor; not a Kanban implementation lane.

Legacy/default-board implementation profiles, in escalation order:

1. `worker-flash-1`, `worker-flash-2`, `worker-flash-3`: Z.AI `glm-5.3-flash`.
2. `worker-luna-1`, `worker-luna-2`: OpenAI Codex `gpt-5.6-luna`.
3. `worker-terra-1`: OpenAI Codex `gpt-5.6-terra`.
4. `worker-glm-full`: Z.AI `glm-5.3`.
5. `worker-sol`: OpenAI Codex `gpt-5.6-sol`.
6. `worker-astra`: OpenAI Codex `gpt-6-astra`.

Keep `worker-terra-2` installed but dormant as a rollback/spare lane. It is outside the active legacy roster unless the human changes the policy.

The escalation ladder and terminal-retry rules below apply only to cards that explicitly use the legacy/default-board roster. Project-isolated Jobcron and Cha PT cards use their five-profile fleets and never fall through to a legacy profile.

Ponytail never runs as a plugin on Hermes profiles. Implementation profiles keep the pinned package installed but `disabled`; the minimalism behavior lives in the per-card `minimal-implementation` skill instead (see Skills). The orchestrator, reviewer, and advisor neither load it nor the simplification skill.

## Skills

`minimal-implementation` is the task-triggered minimalism skill. The orchestrator attaches it per card (via `skills: ["minimal-implementation"]` on the card) using this policy:

- Attach for: native/platform-alternative questions, dependency or library choice, open-ended UI/component work, suspected overengineering, refactoring or simplification, and shared-function or root-cause repair.
- Attach for diagnostic design, including infrastructure diagnostics; separate any production/mutation implementation slice. Verification and safety requirements still take precedence.
- Leave off for ordinary implementation of acceptance-heavy, security or trust-boundary, migration or data-loss, concurrency or distributed-systems, infrastructure or production, and compliance-sensitive tasks.
- Override: even for an attach-category task, the orchestrator may leave the skill off whenever verification or safety requirements outrank simplification. That is the direction of the override — verification and safety outrank minimalism, never the reverse.
- `simplification-review` is a separate, optional post-implementation review skill; it recommends reductions only and never edits or weakens tests. It is never a substitute for required verification.

Record the decision in card metadata: `skill_policy_version`, `minimal_implementation: enabled|disabled`, the reason, and that verification precedence applies (`verification_precedence: requirements-and-risk-outrank-simplification`). Reviewer and advisor lanes never load the implementation skill.

## Routing Rubric

Flash is the default entry rung. The Sol orchestrator may start directly at:

- Terra for substantial ambiguity, diagnosis, architecture, concurrency or security reasoning, risky migrations, unfamiliar subsystems, or complex multi-file work.
- GLM-full for large-context, repo-wide, long-horizon, multimodal or visual work, or broad but sufficiently specified execution.

Luna, Sol, and Astra are escalation rungs, not normal direct-entry rungs. A task that enters at Terra or GLM-full continues forward from that rung and never moves backward.

Before dispatch, record in the task body or an initial structured comment:

- `ladder_version: glm-review-v1` for bounded compatibility, or `glm-review-v2` only for an explicitly authorized terminal-retry campaign.
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
- `RETRY_TERMINAL`: only at Astra, for a fenced, remediable semantic rejection in an explicitly opted-in v2 campaign.

Use `kanban_request_changes` only for `REVISE_SAME_RUNG` and an eligible `RETRY_TERMINAL` continue transition. For either escalation verdict, use `kanban_block` with a structured verdict so the task cannot race back to the previous implementer. The orchestrator reads the durable verdict, updates task history, safely reassigns the card, and explicitly promotes it to `ready`. Do not use `kanban_unblock` for this transition: a card blocked from review returns to the review lane when unblocked. Use `kanban_complete` only for `APPROVE`.

### Same-rung revision allowance

Allow one same-rung revision by default. The reviewer may grant one additional and final revision only when:

1. The prior substantive feedback substantially converged and remaining work is localized, mechanical, and unambiguous; or
2. The failed retry was caused primarily by incorrect, contradictory, incomplete, or materially ambiguous reviewer guidance.

Every revision consumes the allowance, including reviewer-caused retries. No rung may receive more than two `REVISE_SAME_RUNG` verdicts. Reviewer-caused failure must record what guidance was wrong, how it caused the retry failure, corrected actionable guidance, and whether independent worker error also occurred. Preserve attribution in task history and metrics; attribution never resets the allowance.

After the second revision, issue `APPROVE`, `ESCALATE_CONTINUE`, `ESCALATE_RESTART`, or `HUMAN_BLOCK`. Repeated worker failure, failure to resolve a substantive defect, newly discovered substantive inadequacy, or mixed responsibility containing material worker error ordinarily escalates instead of receiving the conditional second revision.

At Astra, any outcome that would advance beyond Astra, including exhausted revisions or repeated infrastructure failure, becomes `HUMAN_BLOCK` and notifies the human unless the exact v2 terminal-retry contract below is satisfied. Provider, quota, crash, timeout, unavailable-model, and context-exhaustion are infrastructure outcomes and always remain on the bounded human-block path at Astra.

### Infrastructure failure

Retry one infrastructure failure at the same rung. Before retrying a timed-out run, increase its per-run runtime cap; never blindly requeue it under the cap that already proved insufficient. A second consecutive provider, quota, crash, timeout, unavailable-model, or context-exhaustion failure advances one rung with attribution `infrastructure`, not `worker_capability`. At Astra, block for human intervention. Never use provider fallback to silently traverse the semantic ladder inside one worker run.

## Escalation Mechanics

### Astra terminal retry (glm-review-v2 opt-in only)

`RETRY_TERMINAL` is never inferred. It is valid only when the same root card durably records all of:

```yaml
ladder_version: glm-review-v2
authorization_mode: autonomous
terminal_retry_policy: astra-until-approve-v1
verdict: RETRY_TERMINAL
rung: astra
strategy: continue | restart
```

The structured verdict must fence the root task, campaign generation, repository, protected baseline, worktree/branch, rejected candidate SHA, reviewer run ID, attribution, concrete findings, and strategy. Reject a stale or duplicate callback, a mismatched candidate/worktree/generation/root, or an identical SHA without explicit reviewer-guidance invalidation; no duplicate Astra run may be created. Event history is authoritative for cycle count, and every individual Astra run remains bounded.

For `continue`, preserve branch, commit, test evidence, and findings; return through `kanban_request_changes`, retain Astra ownership, and require a new commit plus fresh independent `reviewer-sol` review. For `restart`, durably block the fenced verdict first, preserve rejected evidence, create a fresh worktree from the protected baseline, retain the same root/generation lineage and Astra rung, then reassign `worker-astra` and promote to `ready`. In either case read the card and run history within two normal dispatcher ticks and require a new claimed run receipt. This paragraph is legacy/default-board policy only.

Never use terminal retry for user stop/pause/revocation, missing product decisions, credentials/MFA/prohibited writes, unsafe repository state, capability boundaries, or policy/legal/security decisions. Those conditions are `HUMAN_BLOCK`. Default, malformed, side-by-side, and v1 metadata stay bounded and human-block after Astra exhaustion.

GOOD: an exact v2, autonomous, card-scoped `astra-until-approve-v1` verdict finds a remediable semantic defect at Astra and returns the same fenced card for a new bounded Astra run. BAD: a side-by-side or v1 card, a provider timeout, or prose merely mentioning “retry” automatically requeues Astra.

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

### Routing validation and dispatch receipt

Before creating or reassigning a card, resolve the destination from the Fixed Roster and verify the exact profile id against live `hermes profile list` output. Also verify the active board maps to that profile's project; profile existence alone does not authorize cross-project assignment. Never invent an id from a naming pattern. Do not use `hermes kanban assignees` as proof that a profile exists: it also includes names retained on cards, including stale or invalid assignees. If the exact profile is absent or belongs to another project, stop and correct the route before mutating the card.

Before creating a card with `skills`, run the reviewed harness preflight for the exact assignee and every requested skill:

    python3 scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]

It imports Hermes's installed resolver under that profile's `HERMES_HOME`; it does not parse `hermes skills list` table output and does not start model inference. A nonzero result, including a mixed present/missing request, rejects the card creation. Do not rely on Hermes's current partial-load behavior, which skips unknown names when another requested skill resolves.

Preflight the runtime-effective forced set for every intended lane, not only the creation assignee. Same-card review inherits `task.skills`, and the native dispatcher additionally force-loads `sdlc-review`; include both in the exact reviewer's resolver check before enabling that handoff. Run that check with invocation-local `HERMES_KANBAN_TASK=<actual-card>` and `HERMES_KANBAN_BOARD=<exact-board>` when validating a Kanban lane: environment-scoped skills can be hidden by offer-time discovery outside the worker context even though they are installed and explicitly loadable. Verify existing files and the correct context before diagnosing a missing installation; never overwrite an existing skill to repair a discovery false negative. Do not set worker environment flags globally in the controller. A passing `requesting-code-review` check cannot substitute for missing inherited or auto-added skills. If review capability is unavailable, continue useful authorized artifact preparation while gating review dispatch separately; preserve the existing card and evidence, do not edit the database or another profile's skills/configuration without authorization, and do not reinterpret the control-plane prerequisite as an application failure or a repair-budget reset. Task-scoped policy excerpts are reference data, not proof that a forced skill is installed.

After activating a lane and assigning or promoting a card intended to run immediately:

1. Read the card back and verify its exact assignee, eligible status, dependency state, and that the destination profile is active in `kanban.dispatch_profiles`.
2. Within two normal gateway dispatcher ticks, read the card and run history again. Require a new claimed/run record, or a terminal transition tied to that new run if the worker finished quickly.
3. If no new run appears, treat routing as failed: inspect profile existence, active lanes, parents, scheduling, concurrency, and card events. Report the exact blocker; never say the worker started merely because reassignment or promotion succeeded.

Do not force a manual dispatcher pass while the gateway dispatcher is active; observe its normal ticks.

## Legacy Five-Lane Implementation Pool

Installed profiles are capacity, not running work. Enforce a maximum of five simultaneous implementation runs with native per-profile capacity and a five-profile active allowlist:

- Leave `kanban.max_in_progress` unset because Hermes counts reviewer runs in that global number.
- Set `kanban.max_in_progress_per_profile` to `1`.
- Keep `reviewer-sol` in `kanban.dispatch_profiles` while legacy/default-board work remains enabled.
- Keep no more than five implementation profiles in `kanban.dispatch_profiles` at once.
- Keep both projects' workers and reviewers dispatchable independently of the legacy five-lane budget; each is already capped at one run by `kanban.max_in_progress_per_profile: 1`. Project orchestrators run as board-pinned interactive sessions outside the dispatcher.
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

For work expected to last hours or days, send the approved specification through the board-designated independent reviewer (`jobcron-reviewer`, `chapt-reviewer`, or legacy `reviewer-sol`) before dispatching implementation.

Authorization covers local branches, worktrees, commits, tests, and recoverable local destructive operations. It never covers pushes, PR creation, deployments, production mutations, messages beyond the configured progress protocol, purchases, credential changes, or other external writes.

## Proportional operational constraints

The Jobcron owner removed owner/controller-imposed time limits and requested no new artificial time limits. Do not invent campaign deadlines, latest-start cutoffs, authorization expiry, full-path timing admission tests, or aggregate session/CI elapsed-time caps unless the owner later explicitly reinstates one or a real external constraint requires it. Existing exact-scope authorization remains valid until revocation, completion of its approved effects, or relevant invalidating state change; this grants no new external effects. Preserve provider-issued credential expiry, maintenance windows, per-operation timeouts, hung-process watchdogs, retry backoff, cleanup, worker runtime caps, and minimum stability-observation periods as technical controls, not campaign authority. A watchdog timeout stops and reconciles that operation; it does not automatically end the authorized campaign.

Do not create campaign-wide protected-read or credential-acquisition ceilings, reserved-slot arithmetic, or approval amendments whose only purpose is increasing an aggregate count. Acquire a credential or secret bundle once per execution session when practical, securely reuse it, and reacquire normally after provider expiry under the same identity and scope. Permit at most one retry after a proven pre-provider/no-submission failure; an ambiguous provider response stops for reconciliation. Keep value-blind audit events and narrowly justified per-operation request/poll caps, but do not use their campaign-wide total as an authorization gate.

Judge controls by total system risk. Extra ledgers, envelopes, counters, reviews, artifacts, and exception paths are not inherently safer; require each control to address a named threat with decision value greater than its complexity, delay, and failure surface. Prefer the simplest observable boundary that preserves authorization, data safety, recovery, and independent review.

## Operator Effort and Evidence Lifecycle

Do not manufacture manual work. Recommend an operator action only when all of these are true:

1. It is necessary to pass the current authorized gate.
2. Existing evidence for the affected surface was invalidated by a relevant observed change, not merely elapsed time or authentication expiry.
3. The agent cannot perform the action under its authorization and capabilities.
4. The decision value exceeds the operator effort.

Authentication expiry blocks a fresh observation; it does not erase evidence already recorded. Revalidate only the affected surface, and only after a relevant invalidating event or immediately before the next materially dependent authorized mutation. Do not use a precautionary recheck to replace a completed, blocked, or still-valid check.

For production deployment, treat prior verified deployment evidence as valid until a relevant observed deployment/configuration change invalidates its affected surface. Do not ask an operator to log in or recheck solely because a token expired. A fresh production observation is required only at the next materially dependent authorized deployment mutation or after the relevant invalidating event; this policy does not authorize that mutation.

Maintain a lightweight campaign checkpoint in the task body or structured comment:

- `completed`: checks/actions with accepted evidence.
- `currently_actionable`: authorized work that can usefully proceed now.
- `blocked_by`: the exact unmet gate, if any.
- `next_gate`: the gate after `currently_actionable` completes.
- `evidence_invalidation_events`: relevant observed changes and their affected surfaces.

Derive “what next?” from `currently_actionable`. After filtering completed, blocked, and uninvalidated checks, an empty list is a valid completion: say directly that nothing useful remains. Do not create a campaign database, plugin, or precautionary task for this convention.

### Examples

- GOOD — Rules were verified and the token later expires: retain the verified rules evidence. If no materially dependent authorized mutation is next, `currently_actionable` is empty: nothing useful remains. BAD — ask the operator to recheck rules solely because the token expired.
- GOOD — A GitHub App installation changes but does not affect repository rules: record it only if relevant to a later gate; do not recheck rules. BAD — treat an unrelated App installation as ruleset evidence drift.
- GOOD — A ruleset edit is observed: add a ruleset invalidation event and revalidate only the affected ruleset before its next materially dependent authorized mutation. BAD — recheck every repository, deployment, and unrelated control surface.

## Cross-Session Startup

When the user refers to another session, "the spec," or prior work from another surface, recover the exact session record or literal source path first and verify that target exists. Telegram, CLI, TUI, and tmux conversations may share a profile without sharing conversational context; do not infer the intended artifact from a similar name.

1. Confirm repository root and current branch/status with `terminal`.
2. Read repository `AGENTS.md` and `docs/README.md`.
3. Read only the active specification, plan, decision, and status material relevant to the work.
4. Inspect the matching Kanban tenant and active task histories.
5. Reconcile repository state, Git branches/worktrees, active lane allowlist, and Kanban before changing status or dispatching work.

Completion criterion: the next action is grounded in current files, Git state, active lanes, and board state rather than transcript memory.

## Task Construction

### Diagnostic convergence

For `work_kind: diagnostic`, require `decision_to_unlock`, one falsifiable `hypothesis`, `minimum_probe`, `risk_tier`, `outcome_to_next_action` (positive, negative, INDETERMINATE), and `complexity_budget` (time, files/dependencies, external-call units, at most two design generations). Put the harness policy `policies/diagnostic-convergence.md` and applicable authority rules in the card context; workers need not have the harness checkout.

Reject likely-INDETERMINATE probes that do not change the next action. Follow the probe ladder: trusted direct command → local synthetic repro → one-off bounded script → sealed reusable controller. Ascend only with reasons simpler rungs cannot answer the decision; a sealed reusable controller requires written justification of decision value, reuse, and concrete threat.

Allow at most two design generations per hypothesis across cards and model rungs. After the first material review correction, reassess the approach before editing. After a second material failure or exhausted budget, require a strategy pivot or abandon the probe, not further default refinement. Record the failed design, spent budget, preserved evidence, and changed evidence path/decision framing; renaming a hypothesis or changing cards/models does not reset its budget. No viable authorized pivot means HUMAN_BLOCK.

Unlimited terminal retries mean campaign-level problem solving, not unlimited refinement of one diagnostic design. An exhausted diagnostic design requires a recorded strategy pivot before another eligible `RETRY_TERMINAL`; all existing v2 authorization, fencing, bounded runs, independent review, and human/infrastructure exclusions remain intact. Review proportionality and decision utility before implementation minutiae; direct simplify/pivot/abandon rather than serial micro-fixes of an overbuilt or low-value approach.

Accept one-time diagnostics with representative positive, negative, and indeterminate/error checks, risk-required verification, stated coverage/limitations, and an observed outcome selecting the next action; synthetic tests are not live proof. Do not require generalized automation. Accepted platform/system tools need proportional identity/target/permission/output checks, not recursive toolchain attestation absent a concrete threat.

Preserve all external-read/write, credential, mutation, deployment, and cutover HUMAN GATEs. For an authorized external operation, state the exact actor, target, operation/effect, permissions, output custody, and retry behavior. A proven local pre-provider failure consumes no external-call units; a completed provider request, including an error or ambiguous response, is not a free retry. Disable uncontrolled SDK retries, pages, and polls when practical; use a per-operation cap only for a concrete cost, rate, mutation, or ambiguity risk. Missing authority or materially broader effects require owner approval, but campaign-wide acquisition totals and artificial expiry do not.

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
- The exact board-designated reviewer as same-card reviewer for code changes.
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
6. Request review with the exact reviewer named by the project contract (`jobcron-reviewer`, `chapt-reviewer`, or legacy `reviewer-sol`) and concise evidence.
7. Block for a genuine decision, prohibited action, credential need, unsafe state, or infrastructure outcome that the orchestrator must classify.
8. Never push, open a PR, deploy, mutate production, or bypass review.

## Review Contract

Every code change requires independent board-designated review before local integration. Project boards use Astra reviewers; the legacy board uses `reviewer-sol`. Inspect the specification, actual diff and commit, repository context, prior rung history, and test evidence. Do not edit implementation code.

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
- Run every Git command with an explicit repository `workdir` or `git -C`; printing a repository path inside a loop does not change the command's working repository. Set explicit pinned `workdir` on every dispatcher-worker terminal call, including absolute-path helper/test invocations: shell cwd persistence can differ by backend. A receipt's cwd derived from its artifact root is declarative, not observed process-cwd evidence; use same-call native `pwd` or an actual `Path.cwd()` assertion when proving execution context.
- For Hermes plugin or service specifications, validate every required hook and payload against the installed source or current official documentation on each emitting surface. CLI, TUI, gateway, and automatic lifecycle paths can expose different identifiers and ordering.
- Standard `kanban_request_changes` immediately routes back to the original implementer; use a structured block for tier escalation to prevent a reassignment race. A normal unblock preserves review provenance and returns to review, so escalation must reassign and then explicitly promote the card to `ready`.
- Hermes's global `kanban.max_in_progress` counts review tasks. Do not use it for the implementation-only cap; enforce the active profile pool instead.
- Profile isolation does not isolate files. Every code-changing card needs its own worktree.
- Inspect integration-test fixture routing before enabling optional database environment variables for a broad suite. A URL override does not prove isolation: subprocess scripts can hard-code an existing managed service. Scope owned disposable-fixture URLs to inspected targeted package commands, run the ordinary broad suite without optional integration activation, and keep fixture-boundary incidents separate from code correctness; reported cleanup neither authorizes the original access nor bypasses an independent HUMAN_BLOCK.
- When canonical `gofmt -l .` reports only ignored evidence inside nested worktrees, preserve those files and the literal command result; check all Git-indexed Go files separately instead of editing private historical fixtures or treating them as application defects. Never claim the literal command was empty. A canonical rebuild without `-trimpath` can differ in bytes from an exact-tree nested-worktree build because compile paths differ: record separate hashes and source/version bindings, exercise the canonical artifact, and reuse unchanged source-bound review evidence without claiming binary identity.
- Resolve handoff filenames from the native run's submitted artifact paths before comparing hashes. A prepared `.md` placeholder may coexist with an authored `.txt` or `.json` deliverable; preserve both and verify the exact submitted bytes before diagnosing wrong placement or requesting revision.
- A skill installed only under `default` cannot be force-loaded by a worker profile. Put the minimum role contract in each worker's `SOUL.md` and card.
- Never copy OpenAI Codex OAuth stores between profiles. Complete separate authorization when a profile needs an independent grant.
- Do not manually force `hermes kanban dispatch` while the gateway-embedded dispatcher is already active merely to accelerate a handoff. Let the next gateway tick claim it; overlapping immediate ticks can produce a short-lived duplicate/protocol-violation retry even though the board lock preserves correctness.
- Inspect the actual persisted/CLI JSON schema rather than assuming tool-view fields are stored verbatim. CLI `show --json` can wrap the card under `task`; a reviewer-owned closed card can retain the reviewer as assignee. A completed native run can be stored as `status: done` plus `outcome: completed`, rather than `status: completed`. Match the actual board/profile/workspace and durable outcome before accepting a receipt. `hermes kanban --board <project> show <id> --json` may omit tool-added `unsatisfied_parents` and comment `id`; verify dependencies from listed parents' current states and comment writes by exact author/body. Native cron may render `continuity: true` from persisted `context_from`, without a stored `continuity` key; self-continuity can be stored literally as `["self"]`, not as the job ID. Verify the actual context source and exact owner-profile job/script/workdir; a local verifier's missing-field error is not a task, scheduler, or product failure.
- Treat `tmux capture-pane` text as rendered terminal data: trailing prompt spaces may be trimmed. Match a fixed masked-input label without its trailing space and confirm it is the last nonempty line, with no anchored exit or consumption marker. Trace the actual prompt call into its delegated helper before deriving labels; an entrypoint can delegate to a module's `prompt()` rather than contain any `getpass()` calls. If a post-launch presence assertion fails, inspect the exact pane and phase value-blindly before any retry; preserve the original receipt and record the verifier correction separately instead of relaunching a healthy waiting process.
- Do not enable automatic decomposition until observed use shows manual decomposition is the bottleneck.

## Verification

Before declaring the harness or an autonomous workstream complete, verify:

- The Hermes source checkout is clean and updateable.
- Every active profile returns its configured model identity on a fresh inference probe.
- The dispatch allowlist contains each project's three-worker pool and reviewer plus the intended legacy lanes, excludes project orchestrators, and has no project card assigned outside its project tuple.
- Board `jobcron` resolves only the Jobcron repository/workspaces and board `cha-pt` only the Cha PT repository/workspaces.
- Fresh project profile sessions have separate state homes and return `gpt-6.1-sol` for orchestrator/primary worker, `glm-5.3` for both GLM Full workers, and `gpt-6-astra` for reviewer.
- No running implementation profile was removed during a lane swap.
- Reviews can start while five implementation profiles are running.
- Every code change reaches independent review before integration.
- Every escalation has a durable verdict and advances exactly one rung.
- Rejected artifacts and clean-restart baselines remain recoverable.
- Git and Kanban contain no unexplained state.
- No push, PR, deployment, purchase, credential change, or other external write occurred without approval.
