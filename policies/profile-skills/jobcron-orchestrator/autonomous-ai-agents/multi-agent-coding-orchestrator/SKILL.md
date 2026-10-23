---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating multi-agent coding with Hermes."
version: 0.6.9-jobcron.5
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

- Jobcron board `jobcron`: `jobcron-orchestrator` (`claude-opus-5-5`); implementation workers `jobcron-worker` (`claude-opus-5-5`) and `jobcron-worker-2` (`claude-opus-5-5`); independent `jobcron-reviewer` (`claude-fable-5-1`). Repository root: `/Users/chanbla11mit/projects/jobcron`; preview port: `17777`.
- Cha PT board `cha-pt`: `chapt-orchestrator` (`claude-opus-5-5`); implementation workers `chapt-worker` (`claude-opus-5-5`) and `chapt-worker-2` (`claude-opus-5-5`); independent `chapt-reviewer` (`claude-fable-5-1`). Repository root: `/Users/chanbla11mit/projects/cha-pt`; preview port: `18080`.

Each project profile has an independent Hermes home, memory, sessions, and fixed terminal root. Named boards provide separate databases, logs, attachments, and workspaces. A project orchestrator may assign only its matching workers and reviewer. A task or callback with a mismatched board, profile, repository, or workspace is invalid and must be blocked before file access or mutation.

Project orchestrators are interactive control-plane sessions, not dispatcher-spawned task workers. Hermes intentionally hides `kanban_list` and `kanban_unblock` whenever `HERMES_KANBAN_TASK` is set, so assigning a card to an orchestrator removes the board-routing tools it needs. Launch each controller through the tracked board-pinning wrapper (`scripts/run-jobcron-orchestrator` or `scripts/run-chapt-orchestrator`). Keep only project workers and reviewers in `kanban.dispatch_profiles`.

Each project has two implementation workers. Assign implementation only to them, never to a foreign-project or legacy worker. Spread independent ready cards across the two workers; keep cards that touch the same files serialized or dependency-linked. Review revision stays on the same assignee.

### Autonomous project repair budget

Project-fleet repair is independent of the legacy escalation ladder. Enable it only when the exact `jobcron` or `cha-pt` card body records exactly one full line `authorization_mode: autonomous` and one full line `repair_policy: bounded-convergence-v1`. Before the first dispatch, append a card comment containing one single-line `repair_history: <JSON array>` snapshot; append a complete successor snapshot comment for every state transition. Kanban comments are the append-only card-wide counter and evidence ledger. Continue on the same card—bounded-convergence-v1 repair authority never transfers to a replacement card. Reassign the same card when authorized, or human-block.

Each approach object has exactly `approach_id`, `strategy`, `strategy_sha256`, `material_difference_review_run_id`, and `attempts`. The strategy hash is calculated from the whitespace-normalized written strategy; approaches after the first require a distinct independent material-difference review run. Each attempt has exactly `candidate_commit`, `implementation_run_id`, `review_run_id`, `infrastructure_retries`, and `outcome`. Start an in-flight attempt with null candidate/review and `outcome: pending`. A successor snapshot may update only that final pending attempt, append one next attempt, or append one next approach; all prior snapshot content remains immutable.

Exact `repair_history` formats. `scripts/verify-state` rejects a snapshot that does not follow them:

- `approach_id` uses only lowercase letters, digits and hyphens, starts with a letter or digit, and has at most 64 characters, for example `a1` or `a2`. An ID with uppercase letters, such as `A1`, is rejected.
- `strategy_sha256` is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of the `strategy` text after every run of whitespace is replaced with one space and leading and trailing whitespace is removed. Copy the strategy text byte-for-byte into the snapshot, and compute the hash from that same text with this exact command: `python3 -I -c 'import hashlib,sys; print(hashlib.sha256(" ".join(sys.argv[1].split()).encode()).hexdigest())' "<strategy text>"`.
- The snapshot appended before the first dispatch has `implementation_run_id: null`, because no run exists before dispatch. After the dispatcher starts the run, append a successor snapshot that sets `implementation_run_id` to that run ID and changes nothing else. Follow the same two steps when an appended attempt or approach is recorded before its dispatch. Only the final attempt of the final approach may have a null run ID, and only while that attempt has `outcome: "pending"`, `infrastructure_retries: 0`, `candidate_commit: null` and `review_run_id: null`. A pending attempt with a null run ID never changes directly to another outcome.

Complete example of a valid snapshot line before the first dispatch:

```text
repair_history: [{"approach_id":"a1","strategy":"Add a bounded retry limit to the export job and cover the limit with one unit test","strategy_sha256":"95a031c63f8d9676ebce8a6628f6c9681318ef99b653ca6619e1ff9a941aa934","material_difference_review_run_id":null,"attempts":[{"candidate_commit":null,"implementation_run_id":null,"review_run_id":null,"infrastructure_retries":0,"outcome":"pending"}]}]
```

- `max_approaches: 3`: an approach is a materially distinct written implementation strategy. Hash the normalized strategy as `strategy_sha256`; changing a worker, model, card, branch, or worktree, prompt, commit, label, or approach ID is not a new approach. The verifier rejects reused IDs or exact strategy hashes; the independent reviewer must reject a superficial semantic rewrite.
- `max_attempts_per_approach: 3`: the initial implementation and at most two reviewer-directed corrections. Every completed semantic attempt records a unique 40-hex candidate commit and non-empty independent review run ID.
- `max_infrastructure_retries_per_attempt: 1`: retry the materially unchanged pending operation once after a provider, process, transport, timeout, unavailable-model, or environment failure. If that retry also fails, the attempt is spent and becomes `infrastructure_failed`; advance within the remaining attempt/approach budget or human-block. An implementation defect is not infrastructure failure.
- A rejected third attempt cannot be approved. Retire the approach and either begin one recorded materially different approach on the same card or human-block. A third attempt that independently passes may be `approve`.
- Do not manufacture an architecture pivot to unlock budget for a localized defect in an exhausted approach. If the proportionate repair uses the same strategy, preserve the retirement and request a narrowly explicit same-card owner amendment for the additional attempt; record its exact limit before dispatch. A remaining approach slot does not make a renamed helper or broader rewrite materially different. Unchanged-source revalidation after an infrastructure-failed attempt needs no ceremonial code commit; retain original authorship and count the new verification attempt honestly.
- Exhausting three approaches always human-blocks under `bounded-convergence-v1`. Further work requires a newly authorized policy version or explicit amended limits on the exact card; retain the complete prior history rather than resetting v1.
- An approach stop is not a campaign stop. The orchestrator may autonomously reassess and continue within the remaining budget, but user stop, product decisions, credentials/MFA, prohibited or external writes, unsafe state, capability boundaries, and policy/legal/security decisions still human-block immediately.

Legacy/default-board lanes are retired and inert: the GLM Flash and GLM-full workers were archived on 2026-10-18 and the GPT Luna, Terra, Sol and Astra workers and `reviewer-sol` were retired the same day. Never assign, escalate, or route review to them. Archived copies are in `~/.hermes/profile-exports/`; restore one only per `procedures/switching-hermes-models.md`.

- `advisor`: read/analyze advisor; not a Kanban implementation lane.

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

Preflight the runtime-effective forced set for every intended lane, not only the creation assignee. Before creating a card, first check that intended reviewer skills actually exist; an unnecessary worker-only forced skill can otherwise become an uneditable inherited review blocker. Prefer no card-level forced skill when the worker can load its available procedural skill normally and the reviewer lacks it; never bypass a required review skill or install into another profile without authorization. Same-card review inherits `task.skills`, and the native dispatcher additionally force-loads `sdlc-review`; include both in the exact reviewer's resolver check before enabling that handoff. Run that check with invocation-local `HERMES_KANBAN_TASK=<actual-card>` and `HERMES_KANBAN_BOARD=<exact-board>` when validating a Kanban lane: environment-scoped skills can be hidden by offer-time discovery outside the worker context even though they are installed and explicitly loadable. Verify existing files and the correct context before diagnosing a missing installation; never overwrite an existing skill to repair a discovery false negative. Do not set worker environment flags globally in the controller. A passing `requesting-code-review` check cannot substitute for missing inherited or auto-added skills. If review capability is unavailable, continue useful authorized artifact preparation while gating review dispatch separately; preserve the existing card and evidence, do not edit the database or another profile's skills/configuration without authorization, and do not reinterpret the control-plane prerequisite as an application failure or a repair-budget reset. Task-scoped policy excerpts are reference data, not proof that a forced skill is installed.

After activating a lane and assigning or promoting a card intended to run immediately:

1. Read the card back and verify its exact assignee, eligible status, dependency state, and that the destination profile is active in `kanban.dispatch_profiles`.
2. Within two normal gateway dispatcher ticks, read the card and run history again. Require a new claimed/run record, or a terminal transition tied to that new run if the worker finished quickly.
3. If no new run appears, treat routing as failed: inspect profile existence, active lanes, parents, scheduling, concurrency, and card events. Report the exact blocker; never say the worker started merely because reassignment or promotion succeeded.

Do not force a manual dispatcher pass while the gateway dispatcher is active; observe its normal ticks.

For a completed candidate escalated to `triage` by block-loop detection, preserve the card and artifact: native CLI `promote`, `unblock`, and `request-review` do not accept triage. Use the documented native dashboard PATCH status interface to recover an inactive card to `ready`, then immediately request ordinary same-card review with exact candidate provenance and no forced claim override. Inspect current installed handler semantics first, retain prior events, and verify the result. Do not run auxiliary specification/decomposition merely to exit triage, recreate the graph, or issue raw database edits. If a worker claims during recovery, reconcile its actual identity before any override.

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

### Documentation-only closeout

A request to write or reorganize specifications and plans includes routine independent documentation/design-readiness review and corrections within that authorized documentation scope. Route the board-designated reviewer automatically after freezing the candidate; do not ask the owner to reauthorize ordinary review, finding resolution, or approved local integration. Preserve a same-card audit trail and require real dispatch/run evidence before reporting review active. Protected-file approval prompts remain separate security gates: obtain consent, never treat a timeout as consent or bypass a refusal. Neither documentation review nor approval grants application implementation, credential, publication, deployment, or live-experiment authority.

### Autonomous

Begin only when both conditions are true:

1. The specification and acceptance criteria are approved.
2. The user explicitly says `run autonomously` or an unambiguous equivalent for that specification.

For work expected to last hours or days, send the approved specification through the board-designated independent reviewer (`jobcron-reviewer`, `chapt-reviewer`, or legacy `reviewer-sol`) before dispatching implementation.

Authorization covers local branches, worktrees, commits, tests, and recoverable local destructive operations. It never covers pushes, PR creation, deployments, production mutations, messages beyond the configured progress protocol, purchases, credential changes, or other external writes.

## Proportional operational constraints

The Jobcron owner removed owner/controller-imposed time limits and requested no new artificial time limits. Do not invent campaign deadlines, latest-start cutoffs, authorization expiry, full-path timing admission tests, or aggregate session/CI elapsed-time caps unless the owner later explicitly reinstates one or a real external constraint requires it. Existing exact-scope authorization remains valid until revocation, completion of its approved effects, or relevant invalidating state change; this grants no new external effects. Preserve provider-issued credential expiry, maintenance windows, per-operation timeouts, hung-process watchdogs, retry backoff, cleanup, worker runtime caps, and minimum stability-observation periods as technical controls, not campaign authority. A watchdog timeout stops and reconciles that operation; it does not automatically end the authorized campaign.

Do not create campaign-wide protected-read or credential-acquisition ceilings, reserved-slot arithmetic, or approval amendments whose only purpose is increasing an aggregate count. Acquire a credential or secret bundle once per execution session when practical, securely reuse it, and reacquire normally after provider expiry under the same identity and scope. Permit at most one retry after a proven pre-provider/no-submission failure; an ambiguous provider response stops for reconciliation. Keep audit events that record no secret or identifying values and narrowly justified per-operation request/poll caps, but do not use their campaign-wide total as an authorization gate.

Judge controls by total system risk. Extra ledgers, envelopes, counters, reviews, artifacts, and exception paths are not inherently safer; require each control to address a named threat with decision value greater than its complexity, delay, and failure surface. Prefer the simplest observable boundary that preserves authorization, data safety, recovery, and independent review.

## Routine upgrade selection

Apply `production-deployment`'s Release change selection before selecting production gates or dispatching release work: existing-platform application-only, migration-bearing, infrastructure-changing, or first launch. Resolve unknown material surfaces with the smallest authorized check; mixed changes take every applicable branch, never a convenient app-only label.

For app-only updates, reuse accepted unchanged platform/topology/security/recovery evidence; require exact-source/new-image CI and focused app acceptance, applicable recovery and exact authorized replacement/readback. Migration adds compatibility, pre-change protection and schema-compatible recovery; after useful writes, never ordinary rollback to a stale writable database. Infrastructure changes invalidate only affected evidence/plans; first-launch discovery/plan safeguards apply when their preconditions exist, not for every production image.

For first launch or changed infrastructure requiring a plan, retain independent review of the exact saved plan before apply in concise next-action guidance, separately from owner authorization for that apply. Name both remaining dependencies even during local readiness; this is not an extra gate for unchanged-platform app-only updates with no infrastructure plan to apply.

Separate reusable platform evidence, new-release evidence and current execution prerequisites. Identify the whole dependent credential/capability sequence, recording names and order only, never values, before an execution window or prerequisite refs, including later host-management access; guessed names/reservations are not readiness and acquisition is not paperwork. Preserve credential/MFA, exact actor/target/scope, fresh dependent observation, external read/write, stop, ambiguity reconciliation and independent implementation-review gates. Apply the existing evidence-expiry and technical timing rules below, not new counters or campaign deadlines.

Derive the concise next useful authorized action from current verified state. Missing prose for a verified reversible step calls for guarded one-time guidance, not a new campaign/proof packet. Image publication alone does not supply host replacement: report the missing step without claiming deployment or silently building automation.

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

## Incident recovery

An incident neither grants new authority nor automatically revokes unrelated authority. Worker-specific restrictions do not automatically restrict the controller; a higher-priority profile prohibition still wins over permissive card prose. Local/read-only intent alone grants no access. Keep all existing external-read/write, credential/MFA, product, security/legal/policy, capability and unsafe-state gates.

1. Contain the offending owned actor/path and verify cessation before reporting containment or resuming a contaminated path. If containment is unavailable, record the real blocker.
2. Preserve the failed invocation, activation names without values, partial artifact, evidence, pending semantic attempt and spent infrastructure retry on the same card. Changing worker/model/branch must not reset repair history or escape its bounds.
3. Classify diagnosis, remediation, and independent implementation separately by actual actor, target, effects, access, authority, and dependencies. Use a brief existing card note, not a new recovery form or permission engine.
4. Perform the smallest useful non-secret read-only observation already authorized, without renewing permission merely because an incident happened. Preserve failed/inconclusive observations; do not repeat a probe that cannot change the next action.
5. After containment, continue already-authorized isolated work demonstrably independent of unresolved state. Withhold unauthorized remediation and pause dependent work. Before a campaign-wide block, name the concrete dependency affecting every remaining authorized action: X relies on unresolved Y for Z. No safe authorized action means a genuine blocker, not invented clearance.

Shared cleanup and historical impact remain unknown unless directly established: owned-fixture cleanup or current absence/zero connections proves neither. User stop remains global: stop all owned workers, reviewers, preview servers and watchers, verify cessation, and never restart from delayed callbacks without user resume.

For broad-test child commands, explicitly remove the project's inspected optional integration activation inputs in each child environment; a shell unset or URL override is insufficient. Separately run required targeted disposable-fixture tests only with inspected ownership/routing and their specifically permitted inputs. Derive names from the actual test surface, not a universal blacklist. Synthetic child tests prove only that command pattern, not live project enforcement.

## Card Setup

Set up a card without a setup-only hold:

1. Create it with the kanban_create tool: `kanban_create(..., board: jobcron, initial_status: blocked)`. The card is created blocked, so it cannot be dispatched before setup is complete, and its notification subscription exists from creation. Create cards only with the kanban_create tool, never with `hermes kanban --board jobcron create`. The tool auto-subscribes this session to the card with delivery_mode notify+wake, the owner's user ID, and this profile as notifier_profile, so completion, review-request, and block events wake this orchestrator and ping the owner. The CLI create command does not subscribe, and a manual notify-subscribe without flags defaults to notify with no user ID, which wakes nobody. This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators.
2. Read the new ID and write the exact ID, worktree path, and branch into the body.
3. Pin the approved baseline commit for that exact card before dispatch.
Protected instruction files (AGENTS.md, CLAUDE.md, SOUL.md, .cursorrules, project .hermes/): every write needs a human approval each time, and dispatched workers cannot get one, because the dispatcher starts them as `hermes chat -q` with stdin set to /dev/null; the prompt times out after 300 s. Do not offer the owner "approve the prompt when the worker reaches it". Before dispatching a card that edits such a file, either have the owner make that edit, or make that one edit from the orchestrator's Telegram session (the approval prompt is delivered to the owner there) with the owner's agreement, then dispatch the worker for the rest.

4. Confirm the kanban_create result reports subscribed: true. Only if it does not, repair the subscription with: hermes kanban --board jobcron notify-subscribe <id> --platform telegram --chat-id <owner chat> --user-id <owner user> --chat-type dm --notifier-profile jobcron-orchestrator --delivery-mode notify+wake. Re-running notify-subscribe updates an existing row, so this command also upgrades a wrongly subscribed card.
5. Unblock the card so it becomes `ready`.

Never claim a card and `kanban_block` it as a setup hold. The worker's first action verifies `$HERMES_KANBAN_TASK`, worktree path, branch, and baseline, and it blocks only on a real mismatch.

At creation Hermes records `workspace_path` as the repository root; the dispatcher's claim materializes the repository-owned worktree under `/Users/chanbla11mit/projects/jobcron`. A root value before claim is expected, not a mismatch; rely on the worker's start check.

## Task Construction

### Diagnostic convergence

For `work_kind: diagnostic`, require `decision_to_unlock`, one falsifiable `hypothesis`, `minimum_probe`, `risk_tier`, `outcome_to_next_action` (positive, negative, INDETERMINATE), and `complexity_budget` (scope, files/dependencies, at most two design generations, plus only risk-justified per-operation safety bounds). Put the harness policy `policies/diagnostic-convergence.md` and applicable authority rules in the card context; workers need not have the harness checkout.

Reject likely-INDETERMINATE probes that do not change the next action. Follow the probe ladder: trusted direct command → local synthetic repro → one-off bounded script → sealed reusable controller. Ascend only with reasons simpler rungs cannot answer the decision; a sealed reusable controller requires written justification of decision value, reuse, and concrete threat.

Allow at most two design generations per hypothesis across cards and model rungs. After the first material review correction, reassess the approach before editing. After a second material failure or exhausted budget, require a strategy pivot or abandon the probe, not further default refinement. Record the failed design, spent budget, preserved evidence, and changed evidence path/decision framing; renaming a hypothesis or changing cards/models does not reset its budget. No viable authorized pivot means HUMAN_BLOCK.

Unlimited terminal retries mean campaign-level problem solving, not unlimited refinement of one diagnostic design. An exhausted diagnostic design requires a recorded strategy pivot before another eligible `RETRY_TERMINAL`; all existing v2 authorization, fencing, bounded runs, independent review, and human/infrastructure exclusions remain intact. Review proportionality and decision utility before implementation minutiae; direct simplify/pivot/abandon rather than serial micro-fixes of an overbuilt or low-value approach.

Accept one-time diagnostics with representative positive, negative, and indeterminate/error checks, risk-required verification, stated coverage/limitations, and an observed outcome selecting the next action; synthetic tests are not live proof. Do not require generalized automation. Accepted platform/system tools need proportional identity/target/permission/output checks, not recursive toolchain attestation absent a concrete threat.

Preserve all external-read/write, credential, mutation, deployment, and cutover HUMAN GATEs. For an authorized external operation, state the exact actor, target, operation/effect, permissions, output custody, and retry behavior. A proven local pre-provider failure consumes no external-call units; a completed provider request, including an error or ambiguous response, is not a free retry. Disable uncontrolled SDK retries, pages, and polls when practical; use a per-operation cap only for a concrete cost, rate, mutation, or ambiguity risk. Missing authority or materially broader effects require owner approval, but campaign-wide acquisition totals and artificial expiry do not.

Each implementation card must include:

- The exact repository line below and the tenant.
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

Write the repository line on the card body in exactly the form `Repository <exact repository path> ONLY.` `scripts/verify-state` accepts no other repository wording; a repository line that uses `EXACT` instead of `ONLY` fails the card contract check. The exact repository lines are:

- Jobcron: `Repository /Users/chanbla11mit/projects/jobcron ONLY.`

Use parent-child links for real dependencies. Keep independent slices parallel. Do not decompose merely to keep every lane busy.

### Runtime budgeting

Estimate the whole worker attempt, not just editing time: repository discovery, implementation, focused tests, cross-platform or container matrices, broad regression gates, commits, and the review handoff all consume the same per-run budget.

- Keep the one-hour default only when the complete attempt is reasonably expected to finish within it.
- If the orchestrator suspects the attempt may exceed one hour, set `max_runtime_seconds` explicitly when creating the card. Use at least two to three hours for substantial implementation, security, infrastructure, migration, large-context, or broad-verification work, and use a longer evidence-based cap when the test matrix or prior measurements justify it.
- If any prior attempt timed out, increase the cap before the next attempt. Choose a value comfortably above the observed elapsed time and remaining work; do not merely add a few minutes.
- Prefer a larger bounded cap over splitting work solely to evade the timer. Split into dependent cards only when the stages have real independent acceptance criteria or handoffs.
- Preserve committed progress and timeout evidence. If the installed Hermes version cannot update an existing card's cap through a supported interface, do not edit the Kanban database directly; create an explicitly linked continuation card with the higher cap and durable handoff, then retire or block the superseded card without losing its audit trail.

## Autonomy

Bookkeeping never gates. Fix malformed `repair_history`, ledger, receipt, or handoff formatting by appending a valid successor that preserves the original. Such a correction is never a completion or integration prerequisite and never an owner question. Semantic gates are unchanged and still block: required tests, exact-candidate independent review, candidate drift, real budgets, and authority/external-write limits.

Never ask the owner about:

- bookkeeping corrections
- historical test-order disclosures
- retry or budget accounting
- infrastructure retries
- read-only local diagnosis
- routine same-card rework
- local integration after approval

Ask only for:

- external writes (push, PR, deploy)
- credentials or MFA
- live profile, skill, policy, board, or gateway changes
- product decisions
- money or billing
- genuine capability limits
- a user stop or resume

These lists never override a Jobcron board-specific control: the local-only repository boundary and scraping rules, repair budgets, incident recovery, user stop, and every credential/MFA, production/deployment, external-write, and protected-file approval gate. A protected-file approval prompt stays a security gate: obtain consent, never treat a timeout as consent or bypass a refusal.

Stale callbacks: run one `kanban_show(..., board: jobcron)`. If the card has already moved past the notified status, reply in at most one line (or say it is already handled) and do nothing else. `notify-subscribe` has no per-event filter (verified from CLI help on 2026-10-17). Filtering would need a Hermes patch, which the upgrade-safety rule forbids.

Proportional handoff checks:

- Trust successful tool results, and do not read back your own comments.
- Do not re-hash what the reviewer already verified; one exact-candidate/diff check at integration is enough.
- Keep controller comments to about 5 lines or fewer.
- Batch independent checks in one response; serialize only when a call depends on an earlier result.

No numeric caps on harmless actions: local reads, local tests, and anonymous public reads already in scope. Keep caps only where a real cost, rate, mutation, or ambiguity risk exists (for example, live model calls and the repair budgets above).

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

Every code change requires independent board-designated review before local integration. Project boards use their board's designated reviewer (`jobcron-reviewer`, `chapt-reviewer`); the legacy reviewer `reviewer-sol` was retired on 2026-10-18. Inspect the specification, actual diff and commit, repository context, prior rung history, and test evidence. Do not edit implementation code.

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
- Profile isolation does not isolate files. Every code-changing card needs its own worktree. For an already-created worktree, prefer `workspace_kind: dir` with its exact path; native `worktree` allocation can replace a supplied path on claim. Verify the claimed path and branch against the body before edits, and reconcile any mismatch on the same card rather than accepting a different workspace receipt.
- A native `crashed`/exited-worker receipt does not by itself prove the former process is dead. Before accepting a retry into the same worktree, reconcile the recorded old and replacement PIDs against observed process identity/start time and cwd. If both owners remain active, fence further edits/effects and resolve ownership through supported controls; never kill an unverified/reused PID. Preserve any false-death/overlap discrepancy on the existing card, retain budget history and partial work, and continue only after one active owner is observed.
- Bind test evidence to the actual command cwd, including temporary parent-source archives, rather than a recorder's hardcoded primary worktree. Audit claimed RED-before-fix ordering against the original tool protocol and observed source-change/GREEN timestamps; a log title cannot establish chronology. Preserve each failed output under an immutable unique name instead of deleting/replacing it; if replacement already occurred, retain the recovered original protocol and explicitly mark the file-custody loss rather than recreating the deleted file.
- Do not declare crashed-worker evidence lost merely because the advertised profile scratch is empty. Resolve the actual task command's inherited `TMPDIR` and output paths, read only the task-specific originals, and preserve them unchanged in native attachments with explicit source/exit/environment limitations. A pipeline's `ok` text or a post-hoc baseline reproduction cannot manufacture an original exit receipt, source binding, or historical RED-before-implementation ordering; forbid stash/reset gymnastics solely to recreate that history. Put new output under the exact worker's own scratch and reuse attributable evidence without gratuitous matrix replay.
- Gate a host-run native database suite on the exact disposable fixture's effective host mapping, host TCP reachability and authenticated host-side SQL, not in-container `pg_isready` or SQL alone. Preserve setup failures distinctly from product/TDD RED, and stop at the connectivity boundary instead of generating a suite-wide connection-refused cascade. A requested loopback binding is not proof Docker actually published it; inspect effective mapping before tests. Keep provider/scraper denial explicit when changing fixture-network topology rather than assuming a bridge is egress-isolated.
- Inspect integration-test fixture routing before enabling optional database inputs. A URL override does not prove isolation: a test may check the disposable URL while its subprocess hard-codes an existing managed service. Scope owned fixture URLs to inspected targeted packages. For EVERY Jobcron broad-suite launch, clear optional inputs at that exact invocation with `env -u JOBCRON_TEST_POSTGRES_URL -u JOBCRON_RERATE_BROWSER_PROBE -u JOBCRON_RERATE_PROBE_OUT` and clear any new opt-ins too; do not rely on an earlier shell `unset` or exported environment surviving a fresh/background shell. Record whether each opt-in input is set (yes or no) in the effective launch environment, never its value, before launch. Preserve a fixture-boundary incident separately from code correctness and fence further unsafe effects. Classify assessment and cleanup separately: perform a useful, authorized, narrowly project-scoped non-secret read-only assessment without inventing a fresh approval gate; retain genuine protected-access/shared-mutation gates. A worker execution fence is not automatically a controller diagnosis ban, and unresolved cleanup does not block independent authorized work without an evidenced dependency. Owned cleanup is not proof or authorization of shared cleanup. Preserve global user-stop behavior.
- For custody-sensitive runner tests, set invocation-local `TMPDIR` to a newly created controller-owned mode-0700 directory with real, non-symlink ancestry; macOS terminal tools can inherit `/var/...` despite the advertised profile scratch path, and `/var` is a symlink. Disable bytecode writes with `PYTHONDONTWRITEBYTECODE=1` when testing canonical source. Preserve prerequisite refusal logs and correct only the test environment, never weaken custody checks or treat an unexecuted test body as a semantic rejection. Use tracked notifying background execution for measured suites that exceed the foreground tool window; an API timeout is not evidence that its actor stopped. Verify old process identity/absence before another invocation, and reuse complete unaffected package results rather than repeating the whole suite.
- Apply Incident recovery at fixture-boundary failures; keep incident effects separate from code correctness. Inspect subprocess scripts, which can hard-code an existing managed service. Reported cleanup neither authorizes the original access nor bypasses an independent HUMAN_BLOCK.
- When canonical `gofmt -l .` reports only ignored evidence inside nested worktrees, preserve those files and the literal command result; check all Git-indexed Go files separately instead of editing private historical fixtures or treating them as application defects. Never claim the literal command was empty. A canonical rebuild without `-trimpath` can differ in bytes from an exact-tree nested-worktree build because compile paths differ: record separate hashes and source/version bindings, exercise the canonical artifact, and reuse unchanged source-bound review evidence without claiming binary identity.
- Resolve handoff filenames from the native run's submitted artifact paths before comparing hashes. A prepared `.md` placeholder may coexist with an authored `.txt` or `.json` deliverable; preserve both and verify the exact submitted bytes before diagnosing wrong placement or requesting revision.
- Store recurring evidence basenames under run-scoped attachment names with `hermes kanban --board <project> attach <task> <original-path> --name <run-scoped-name>`; verify the stored bytes against the untouched original and refuse to overwrite a prior run's path. A successor report or manifest must not silently replace the earlier attachment's custody.
- When required native lifecycle coverage cannot be reached with compiled metadata, distinguish a real product decision from missing synthetic-input testability. Use bounded independent contract classification before adding a seam or waiving coverage; an UNKNOWN saved ID is not deprecated acknowledgement, and pure helper tests are not authenticated native save proof. If original fixture authority permits a narrow private instance-local supplier, explicitly bind its scope, identical nil/default behavior, fresh-copy/isolation controls and unchanged runtime/security boundaries before continuation. Keep classification separate from CODE acceptance and preserve the same pending attempt/counters; never mutate production catalogue facts or invent unreachable producer sequences merely to make tests pass.
- Resolve contradictory terminal/notification requirements against the original approved contract through bounded independent classification before demanding a new architecture or owner decision. A recovery callback that can fail only after observing a truthful immutable terminal cannot retroactively change that terminal without violating exactly-once semantics; distinguish it narrowly from still-owned pre-terminal work and other unfinished scopes. Preserve the disputed raw failure, require separately named corrected controls, and retain real operation-failure requirements plus subsequent independent code review. If no successor or semantic rejection occurred, resume the same pending uncommitted attempt after verified interpretation without inventing an attempt, infrastructure retry or green result. Actual product/security changes still require human approval.
- Respect attachment size caps before recursively nesting prior evidence archives. Reference an already-durable native attachment by exact task/id/name/hash/size after rechecking stored/source bytes and CRC, while including every unique current artifact and explicit provenance links. Preserve an oversized producer archive/nonpass distinctly; repackaging duplicate bytes is not a new code-validation result, semantic attempt or infrastructure retry.
- Resolve virtual archive prefixes through an explicit source-path map before asserting evidence loss or byte equality; archive paths such as checks/, final-source/ and recovered originals need not be direct siblings. Validate every member against its real original and bind committed source snapshots to Git blobs separately; a verifier mapping failure is not a semantic implementation failure or retry-budget reset.
- Verify stored evidence against the original worker file's SHA256 and validate ZIP/gzip CRC before declaring custody; successful attachment, matching size, or readable plain text does not prove byte identity. If an inline attachment differs or fails CRC, preserve that copy and attach the intact original through the native file-path CLI under a distinct filename, then verify the stored hash. Never reconstruct test logs, assume sibling attachments are intact, blame a transport without evidence, or turn a corrected evidence-copy problem into a semantic rejection or repair-budget reset.
- A skill installed only under `default` cannot be force-loaded by a worker profile. Put the minimum role contract in each worker's `SOUL.md` and card.
- Never copy OpenAI Codex OAuth stores between profiles. Complete separate authorization when a profile needs an independent grant.
- Do not manually force `hermes kanban dispatch` while the gateway-embedded dispatcher is already active merely to accelerate a handoff. Let the next gateway tick claim it; overlapping immediate ticks can produce a short-lived duplicate/protocol-violation retry even though the board lock preserves correctness.
- Inspect the actual persisted/CLI JSON schema rather than assuming tool-view fields are stored verbatim. CLI `show --json` can wrap the card under `task`; a reviewer-owned closed card can retain the reviewer as assignee. A completed native run can be stored as `status: done` plus `outcome: completed`, rather than `status: completed`. Match the actual board/profile/workspace and durable outcome before accepting a receipt. `hermes kanban --board <project> show <id> --json` may omit tool-added `unsatisfied_parents` and comment `id`; verify dependencies from listed parents' current states and comment writes by exact author/body. Native cron may render `continuity: true` from persisted `context_from`, without a stored `continuity` key; self-continuity can be stored literally as `["self"]`, not as the job ID. Verify the actual context source and exact owner-profile job/script/workdir; a local verifier's missing-field error is not a task, scheduler, or product failure.
- Treat `tmux capture-pane` text as rendered terminal data: trailing prompt spaces may be trimmed. Match a fixed masked-input label without its trailing space and confirm it is the last nonempty line, with no anchored exit or consumption marker. Trace the actual prompt call into its delegated helper before deriving labels; an entrypoint can delegate to a module's `prompt()` rather than contain any `getpass()` calls. If a post-launch presence assertion fails, inspect the exact pane and phase without recording any input values before any retry; preserve the original receipt and record the verifier correction separately instead of relaunching a healthy waiting process.
- Do not enable automatic decomposition until observed use shows manual decomposition is the bottleneck.

## Completion Gate

Before reporting a jobcron card complete, check semantic validity, not bookkeeping-format validity:

- The board, repository, worktree, baseline, assignee, reviewer, and test contract match the card.
- Required focused and broader tests pass.
- The candidate commit is reviewed by `jobcron-reviewer` on the same card.
- The approved change is locally integrated or an exact integration blocker is recorded.
- Git and `kanban_show(..., board: jobcron)` agree on the result.
- No unauthorized push, PR, deployment, policy rollout, credential operation, production/cloud mutation, or external write occurred.

## Verification

Before declaring the harness or an autonomous workstream complete, verify:

- The Hermes source checkout is clean and updateable.
- Every active profile returns its configured model identity on a fresh inference probe.
- The dispatch allowlist contains each project's workers and reviewer plus the intended legacy lanes, excludes project orchestrators, and has no project card assigned outside its project tuple.
- Board `jobcron` resolves only the Jobcron repository/workspaces and board `cha-pt` only the Cha PT repository/workspaces.
- Fresh project profile sessions have separate state homes and return `claude-opus-5-5` for orchestrator/worker and `claude-fable-5-1` for reviewer.
- No running implementation profile was removed during a lane swap.
- Reviews can start while five implementation profiles are running.
- Every code change reaches independent review before integration.
- Every escalation has a durable verdict and advances exactly one rung.
- Rejected artifacts and clean-restart baselines remain recoverable.
- Git and Kanban contain no unexplained state.
- No push, PR, deployment, purchase, credential change, or other external write occurred without approval.
