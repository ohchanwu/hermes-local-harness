# Documentation

This index is the entry point for durable harness documentation tracked in Git. Load this index instead of recursively reading the docs tree.

## Layout

- `plans/` contains active implementation plans.
- `specs/` contains active or awaiting-approval requirements and designs.
- `decisions/` contains durable decisions; maintained cross-cutting harness policy lives in root `policies/`.
- `archive/` contains completed plans and retired designs.

## Current entries

- [Claude Max 20x inside Hermes and model portability](specs/261016-claude-max20x-model-portability.md) — execution specification; native billing verification first; implementation/live testing not yet authorized.
- [Claude Max 20x implementation plan](plans/261016-claude-max20x-implementation-plan.md) — native-first M0–M5 execution plan; execution unexecuted/unapproved.
- [Claude Max 20x native pre-inference gate](operations/261016-claude-max20x-native-preflight.md) — bounded execution update superseding the historical unexecuted labels above: documented NATIVE_FAILURE; M1 UNRUN, no account/billing proof or rollout.
- [Private-local Claude runtime feasibility](../spikes/claude-subscription-feasibility/README.md) — bounded offline M2 update: PARTIAL, source-path/inert mechanisms only; no Support-letter prerequisite for non-inference work, no official/account compatibility or rollout claim.
- [Incident recovery without invented authorization gates](specs/261014-incident-recovery-without-over-gating.md) — authorized local implementation; behavioral evidence and same-card review required, no live rollout.
- [Incident-recovery implementation plan](plans/261014-incident-recovery-implementation-plan.md) — adopted standalone plan with the foreign-read fixture verification correction.

- [Concurrent project fleets](specs/261004-concurrent-project-fleets.md) — implemented and verified Jobcron, Cha PT, and Harness isolation; the Harness attended live rollout is operational.
- [Diagnostic convergence policy](../policies/diagnostic-convergence.md) — maintained design and review contract; [authority boundaries](../policies/authority-and-review.md).
- [Completed diagnostic-convergence implementation plan](archive/261003-diagnostic-convergence.md)

- [Autonomous Astra terminal-retry harness plan](plans/260929-autonomous-astra-terminal-retry.md)
- [Hermes terminal outcome notification specification](specs/260921-hermes-terminal-outcome-notification.md)
- [Completed local Hermes harness tracking plan](archive/260920-hermes-local-harness-tracking-plan.md)

## Bugs

- [Jobcron upgrade orchestration: repeated first-launch ceremony](bugs/261007-jobcron-upgrade-orchestration-repeated-first-launch-ceremony.md)
- [Jobcron test-boundary incident incorrectly halted autonomous implementation](bugs/261007-jobcron-test-boundary-incident-overblocked-autonomous-implementation.md)
- [Jobcron over-gating read-only incident assessment stalls autonomous work](bugs/261013-jobcron-over-gating-readonly-incident-assessment.md) — recurrence focused on unnecessary authorization gates and campaign-wide dependency invention.
- [Cha PT calendar rollout accumulated disproportionate ceremony](bugs/261013-chapt-calendar-rollout-overcomplicated-bootstrap-plan.md) — near miss caused by carrying proof-oriented migration scaffolding into a narrow empty-state transition.

## Scoped Ponytail separation (approved design summary)

Diagnostic design, including infrastructure diagnostics, now attaches `minimal-implementation` subject to verification/safety precedence. The leave-off categories below continue to govern ordinary production/mutation implementation, not diagnostic design. See the diagnostic-convergence policy above.

Implementation profiles keep the pinned Ponytail plugin (4.8.4 @ 16f29800) installed but `disabled`; minimalism runs as the task-triggered `minimal-implementation` skill attached per card by the orchestrator. Routing: attach for native/platform-alternative, dependency/library-choice, open-ended UI, suspected-overengineering, refactoring/simplification, and shared-function/root-cause work; leave off for acceptance-heavy, security/trust-boundary, migration/data-loss, concurrency/distributed, infrastructure/production, and compliance-sensitive tasks; the orchestrator may also leave it off any otherwise-attach task whenever verification or safety requirements outrank simplification — that is the override direction (verification outranks minimalism, never the reverse). Card metadata records `skill_policy_version`, the enabled/disabled decision with reason, and `verification_precedence`. `simplification-review` is a separate advisory-only review skill that recommends reductions without editing or weakening tests. Interactive Claude/Codex sessions keep upstream Ponytail installed/enabled with shared `defaultMode: off` (manual activation); see `procedures/manual-apply.md` sections 3/4/4b.
