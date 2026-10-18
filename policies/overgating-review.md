# Overgating review checklist

Reviewer checklist for `harness-reviewer`, `chapt-reviewer`, and `jobcron-reviewer`. It governs review findings only and grants no new authority: it authorizes no action and removes no boundary set by a profile SOUL, skill, card, or [authority and review](authority-and-review.md).

## Scope

Apply when a reviewed diff adds or changes a specification, implementation plan, procedure/runbook, policy, or card template.

For every proposed gate, approval request, hold, review layer, cap/ceiling/counter, deadline/expiry, extra artifact, or repeated verification, require that the text names the concrete failure mechanism it controls and that the mechanism is still live at that step. A control with no named mechanism, or whose mechanism is already resolved, is overgating.

## Flag as overgating

1. Owner/human approval requested for already-authorized local, reversible, or read-only work, or for bookkeeping: ledger/receipt/format corrections, test-order disclosures, retry/budget accounting.
2. Bookkeeping or format validity used as a completion, integration, or dispatch prerequisite.
3. Aggregate numeric ceilings, reserved-slot arithmetic, or counters on harmless actions (local reads/tests, already-scoped anonymous reads).
4. Artificial campaign deadlines, latest-start cutoffs, elapsed-time authorization expiry, or worst-case timing admission tests.
5. Setup-only holds, claim-then-block steps, or extra state transitions whose only purpose is ceremony.
6. An incident or open question turned into a campaign-wide halt without a named dependency (X relies on unresolved Y for Z).
7. First-launch/migration-grade ceremony applied to a routine, reversible, or app-only change; re-verifying unchanged accepted evidence; a new campaign or review cycle for a one-time reversible step; missing operator prose treated as missing implementation.
8. Controls that only accumulate: completed stages whose gates are never retired from the remaining path.

## Do not flag genuine controls

- External writes (push, PR, deploy) and operator-protected path authorization.
- Credentials/MFA and provider credential expiry.
- Live profile, skill, policy, board, or gateway changes.
- Production/cloud mutation, non-idempotent migration, nonempty/clinical data.
- Ambiguous provider/transaction outcomes.
- Real cost/rate limits, including live model calls and repair budgets.
- Network/subprocess timeouts and watchdogs.
- Product decisions, money or billing, genuine capability limits.
- Required tests, exact-candidate independent review, candidate drift.
- User stop or resume.

Removing overgating must never weaken those controls.

## Verdict

- Material finding: overgating that would block, stall, or add owner prompts to otherwise authorized work. Use `kanban_request_changes` naming the gate, why its mechanism is absent or not live, and the proportionate replacement (often deletion).
- Non-blocking note: minor ceremony that blocks nothing. Record it in the approval (`kanban_complete`); do not request changes for it.

## Evidence and agreement

- [Jobcron routine upgrade expanded into first-launch ceremony](../docs/bugs/261007-jobcron-upgrade-orchestration-repeated-first-launch-ceremony.md) — items 3, 4, 7, 8.
- [Jobcron test-boundary incident halted autonomous implementation](../docs/bugs/261007-jobcron-test-boundary-incident-overblocked-autonomous-implementation.md) — item 6.
- [Jobcron over-gated read-only incident assessment](../docs/bugs/261013-jobcron-over-gating-readonly-incident-assessment.md) — items 1, 6.
- [Cha PT calendar rollout accumulated ceremony](../docs/bugs/261013-chapt-calendar-rollout-overcomplicated-bootstrap-plan.md) — items 7, 8.
- [Repair-history formatting blocked approved completion](../docs/bugs/261017-repair-history-formatting-blocked-approved-completion.md) — items 1, 2.
- Agrees with the Harness orchestrator card-setup rule, ask/don't-ask list, and numeric-cap rule (items 1, 2, 3, 5) in [multi-agent-coding-orchestrator](profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md).
