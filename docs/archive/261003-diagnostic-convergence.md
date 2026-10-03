# Diagnostic-convergence implementation plan

Status: implementation complete; independent review and separately authorized rollout pending.

## Scope and decisions

Prevent diagnostic designs from becoming reusable infrastructure without decision value. Maintain the durable contract in [diagnostic convergence](../../policies/diagnostic-convergence.md) and [authority and review](../../policies/authority-and-review.md); deploy concise operational rules through existing isolated skill copies. No new plugin, dispatcher behavior, or upstream Hermes change is required.

## Completed implementation

1. Define diagnostic metadata, smallest-probe ladder, proportional tool trust, one-time acceptance, explicit call envelopes, and a two-generation convergence governor.
2. Update the orchestrator to 0.5.0 and production-deployment to 0.2.0. Enable diagnostic-design minimalism while preserving risk-based verification and ordinary production/mutation rules.
3. Preserve campaign-level terminal retry and all human gates; require an exhausted diagnostic strategy to pivot, not accumulate micro-fixes.
4. Add static policy/link contracts, update canonical skill hashes, and regenerate synthetic desired-state fixtures with the existing generator.

## Acceptance and verification

Run each `tests/test_*.py` script, then `scripts/verify-state --fixture tests/fixtures/clean.yaml`, `git diff --check`, and publication-safety review. Static tests detect removal of key policy clauses; they do not implement runtime enforcement or prove live deployment. Existing notification/retry regression tests remain authoritative for runtime behavior.

## Handoff

Request independent `reviewer-sol` review on the implementation card before integration. The orchestrator alone handles separately authorized rollout via [manual apply](../../procedures/manual-apply.md) section 4, then live verification and any authorized push. Desired-state hash changes do not claim that deployed skill copies already match. This completed plan is archived rather than retained under active plans; the policy remains maintained.
