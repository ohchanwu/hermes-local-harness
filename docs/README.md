# Documentation

This index is the entry point for durable harness documentation tracked in Git. Load this index instead of recursively reading the docs tree.

## Layout

- `plans/` contains active implementation plans.
- `specs/` contains active or awaiting-approval requirements and designs.
- `decisions/` contains durable decisions; maintained cross-cutting harness policy lives in root `policies/`.
- `archive/` contains completed plans and retired designs.

## Current entries

- [Diagnostic convergence policy](../policies/diagnostic-convergence.md) — maintained design and review contract; [authority boundaries](../policies/authority-and-review.md).
- [Completed diagnostic-convergence implementation plan](archive/261003-diagnostic-convergence.md)

- [Autonomous Astra terminal-retry harness plan](plans/260929-autonomous-astra-terminal-retry.md)
- [Hermes terminal outcome notification specification](specs/260921-hermes-terminal-outcome-notification.md)
- [Completed local Hermes harness tracking plan](archive/260920-hermes-local-harness-tracking-plan.md)

## Scoped Ponytail separation (approved design summary)

Diagnostic design, including infrastructure diagnostics, now attaches `minimal-implementation` subject to verification/safety precedence. The leave-off categories below continue to govern ordinary production/mutation implementation, not diagnostic design. See the diagnostic-convergence policy above.

Implementation profiles keep the pinned Ponytail plugin (4.8.4 @ 16f29800) installed but `disabled`; minimalism runs as the task-triggered `minimal-implementation` skill attached per card by the orchestrator. Routing: attach for native/platform-alternative, dependency/library-choice, open-ended UI, suspected-overengineering, refactoring/simplification, and shared-function/root-cause work; leave off for acceptance-heavy, security/trust-boundary, migration/data-loss, concurrency/distributed, infrastructure/production, and compliance-sensitive tasks; the orchestrator may also leave it off any otherwise-attach task whenever verification or safety requirements outrank simplification — that is the override direction (verification outranks minimalism, never the reverse). Card metadata records `skill_policy_version`, the enabled/disabled decision with reason, and `verification_precedence`. `simplification-review` is a separate advisory-only review skill that recommends reductions without editing or weakening tests. Interactive Claude/Codex sessions keep upstream Ponytail installed/enabled with shared `defaultMode: off` (manual activation); see `procedures/manual-apply.md` sections 3/4/4b.
