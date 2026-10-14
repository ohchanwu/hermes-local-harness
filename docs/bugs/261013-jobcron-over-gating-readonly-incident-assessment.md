# Jobcron: over-gating read-only incident assessment stalls autonomous work

Date: 2026-10-13. Scope: Jobcron board, existing card `t_913bece9`, implementation run176 and controller response.

Severity: high operational/liveness failure. Primary defect: orchestration over-gating, not an established Hermes runtime defect.

## Summary

After a worker crossed a documented local test boundary, the controller incorrectly treated a safe, narrowly scoped read-only assessment as requiring fresh human authorization. It also made that incident disposition a prerequisite for all remaining isolated implementation, without establishing a dependency. The resulting approval request timed out and useful autonomous work stayed stopped. The owner had already authorized autonomous local implementation; preserving evidence and withholding unverified shared-state cleanup did not justify withholding permitted diagnosis or independent work.

The worker's test-command error triggered the incident, but the harmful failure addressed here is the controller's amplification of that error into unnecessary human work and campaign inactivity.

## Reproduction and observed behavior

1. An approved two-slice campaign is executing autonomously. Slice 1 is independently accepted and integrated; Slice 2 has preserved partial implementation on the same isolated card/worktree.
2. Worker run176 incorrectly runs the broad Go suite with `JOBCRON_TEST_POSTGRES_URL` retained. Some preview lifecycle tests check the disposable URL but launch a script that targets the shared Jobcron local Compose service. This is a real test-boundary violation and must remain in the record.
3. The worker preserves the rejected test output and partial source, cleans only its verified owned fixture, and stops. Native recurrence handling routes the existing card to triage.
4. The controller verifies the source-routing mismatch and preserves a durable recovery attachment, but labels read-only catalog/identity assessment itself an owner-authorization gate.
5. The controller requests permission to inspect only the Jobcron local container identity and generated preview-database names/connection counts, despite requiring no secret access, user-table reads, service changes, or database mutation.
6. The clarification returns `unanswered` / `timed_out`. The controller leaves the campaign stopped and reports that owner authorization is needed before proceeding, rather than taking the permitted read-only action and continuing independent authorized work.
7. When challenged, the controller acknowledges that read-only Jobcron-scoped assessment was over-gated. The owner requests this report and autonomous continuation.

## Expected behavior

- Classify each proposed next action by its actual target, effects, access requirements and existing authority—not merely because it follows an incident.
- Perform narrowly scoped, non-secret, read-only local Jobcron diagnosis autonomously when it is within existing authority and useful to the next decision.
- Keep worker restrictions on shared-target use distinct from a controller's permitted incident diagnosis; do not invent a controller-wide ban from a worker card's execution fence.
- Preserve the boundary violation, uncertainty, failed evidence, budget history and exact partial artifact. Do not claim that owned-fixture cleanup proves shared-target cleanup or that current metadata proves no historical damage.
- Continue already-authorized isolated implementation whose safety does not depend on shared cleanup. An incident requires a campaign-wide pause only when a concrete dependency or genuine prohibited action makes continuation unsafe.
- Ask for authorization only at a real boundary: protected credential access, prohibited external/production effects, or unapproved shared-resource mutation. Do not merge assessment and remediation into one universal human gate.
- Retain global user-stop behavior. This correction is about avoiding invented authorization gates, not weakening a user stop or introducing scoped user-stop semantics.

## Evidence

- Same-card native run176 comments419–420 preserve the wrong-environment broad command, failed preview checks, partial implementation and unknown shared-state impact.
- Controller comments421–422 establish the unnecessary assessment gate, unanswered approval request and withheld resumption.
- The owner challenged the gate; the controller admitted: “Not for a strictly read-only, Jobcron-scoped assessment—I over-gated that.”
- Native attachments15–16 preserve successive partial checkpoints. There was no Slice 2 candidate commit, independent acceptance or integration at the stop.
- After the owner directed autonomous continuation, the controller successfully performed a direct local read-only assessment: exact Jobcron Compose labels/identity followed by a PostgreSQL `BEGIN READ ONLY` catalog query, with statement/lock timeouts and no user-table or secret reads. The generated database named in the incident was present with zero connections at observation time. Other matching preview databases were also present but were not attributed to this run. No cleanup was performed.

Machine-local raw evidence remains in the native task record and owner-only controller/worker scratch. No credentials, connection strings, user data, private runtime selectors or raw logs are included here.

## Root cause and responsibility

The controller conflated three distinct questions:

1. Did the worker violate its allowed execution boundary? **Yes.**
2. Does a safe read-only assessment cross a new authorization boundary? **Not inherently; its actual effects and applicable authority must be checked.**
3. Is shared-resource remediation permitted? **Not inferred from diagnostic permission; establish ownership, need and mutation authority separately.**

It then treated unresolved remediation as a dependency of unrelated isolated implementation. This was the controller's responsibility, not a reason to blame the worker for the subsequent unnecessary pause. The incident also repeats the pattern already documented in [the earlier Jobcron over-blocking report](261007-jobcron-test-boundary-incident-overblocked-autonomous-implementation.md); the prior lesson was not applied at the decision point.

## Correction and regression criteria

- Replace blanket “incident assessment needs owner approval” reasoning with a per-action authority/effect check.
- Do the smallest direct read-only observation first; do not build a generalized checker or another task graph.
- Preserve incident evidence and any unresolved cleanup without making cleanup an automatic prerequisite for independent development.
- Resume the same card/artifact after fencing the former actor; retain the pending semantic attempt and spent infrastructure retry rather than resetting history.
- Enforce broad-test isolation at each exact subprocess invocation, clearing optional PostgreSQL/browser inputs and new fixture opt-ins; scoped disposable PostgreSQL tests remain mandatory and separate. This prevents recurrence but does not explain away the over-gating defect.
- Regression scenario: a worker violates a test boundary, no actor remains active, a read-only local metadata probe needs no new privileged/secret access, and the remaining feature work is isolated. The controller must preserve evidence, perform the permitted probe and resume useful authorized work without another human prompt.
- Negative regression: if the probe actually requires prohibited access or the next action mutates protected/shared state without applicable authority, preserve the real gate; do not reinterpret autonomous implementation as blanket permission.

## Status

Report written and indexed; read-only assessment executed and its limitations retained. Shared cleanup remains unperformed and is not an invented prerequisite for safe isolated implementation. Same-card autonomous continuation was verified as native `jobcron-worker` run177 in the original pinned worktree, with prior evidence and repair history preserved. Full Slice 2 validation and independent acceptance remain required and are not claimed complete.
