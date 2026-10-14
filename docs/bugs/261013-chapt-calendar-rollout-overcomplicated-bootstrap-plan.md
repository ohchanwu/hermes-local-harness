# Cha PT: calendar rollout plan accumulated disproportionate ceremony

Date: 2026-10-13. Scope: attended Cha PT ARM64/database/calendar migration guidance after successful P1/P2/P4 installation and empty-custody binding.

Severity: near-miss operational/liveness defect. No production data was lost and no unsafe mutation occurred. The owner challenged the plan before a redundant implementation/review campaign was started.

## Summary

The proposed continuation turned a small, reversible editor-enablement step into a prospective new implementation campaign with another independently reviewed operator procedure, extensive repeated state proofs and a long exporter-certification sequence. Most of the earlier migration was already complete and verified: immutable ARM64/MySQL images were selected, the historical database was restored, calendar migrations and real provider mapping were installed, empty custody was bound, the upload credential was expired, and a body-free request proved intake remained closed.

At that point the material next operation was narrow: stop the sole metadata writer, update the schedule marker and coherent calendar/warning revision under the existing lock order in one guarded transaction, read the result back, and reopen the same SQL/raw pair. The original proposal failed to prune scaffolding that had been justified for earlier high-risk stages.

## Why did the original proposed plan get so complicated?

### 1. It treated a proof-oriented runbook as the minimum execution path

The maintained Cha PT rollout document intentionally records design history, synthetic acceptance, negative cases, recovery behavior and unexecuted live gates. Phrases such as “separately reviewed,” “attended procedure,” “explicit revision/reevaluation disposition” and “preserve evidence” describe a defensible safety envelope, but they do not make every historical test artifact or review cycle a prerequisite for each live step.

The guidance copied the runbook's entire assurance structure into the operator path instead of extracting the few invariants that still mattered in the current empty, bound state.

### 2. Earlier real hazards caused caution to spread beyond their scope

This migration had encountered genuine risks: an initially wrong MySQL downgrade target, non-idempotent DDL, secret transfer, cross-architecture replacement, immutable-image identity and SQL/raw custody pairing. Those justified source inspection, attended execution and ambiguity handling at their respective boundaries.

After those risks were resolved, the plan continued applying migration-grade ceremony to a marker transition with no imports and a preserved rollback host. Caution became monotonic: each discovered hazard added controls, but completed stages did not remove controls that no longer changed the decision.

### 3. It confused missing copy-paste commands with missing implementation

The runbook states the marker-transition invariants but does not contain a ready-made live SQL block. The proposal interpreted that documentation gap as a possible need for a new worker card, implementation campaign and independent review. That was the wrong default.

The relevant schema and source already define the state, lock order, revision coherence and warning-generation invariant. A concise one-time operator transaction can be derived directly, guarded by current-state predicates and verified by readback. Missing operational prose did not by itself establish missing product functionality.

### 4. It optimized each check locally instead of minimizing total system risk

Every proposed check sounded reasonable in isolation: reverify bindings, review the transaction, certify exporter behavior, preserve another evidence packet, reconfirm prior migrations and require another acceptance handoff. Together they increased the number of states, documents, decisions and opportunities for contradiction.

The result would have imposed more operator work, delayed deployment, and increased the chance of configuration drift or an emergency shortcut. Additional ceremony is not automatically safer; it must control a named failure mechanism that remains live at that step.

### 5. The guidance did not separate irreversible boundaries from reversible local steps

The plan applied nearly the same process weight to:

- non-idempotent schema migration and first real clinical intake, where recovery and ambiguity controls are essential; and
- enabling an editor marker in an empty bound calendar, where the web owner can be stopped and the state changed atomically before any producer credential is live.

Risk, uncertainty, blast radius and reversibility should determine verification depth. A production label alone is not enough to require the maximum ceremony.

### 6. Context accumulation discouraged simplification

The long-running migration context preserved every prior warning and correction. Subsequent guidance favored adding another guard over reconsidering the whole remaining path. This is a common agent failure mode: history becomes an append-only checklist rather than evidence from which obsolete requirements should be retired.

The owner supplied the missing corrective question—whether the remaining plan was proportionate—and the answer was no.

## Disproportionate proposed work

The following items were not justified as prerequisites for this empty-state marker transition:

- a new implementation campaign solely to produce the one-time SQL procedure;
- another full independent-review cycle for already exercised lock/revision semantics;
- repeated validation of completed image, restore, migration, mapping, volume and expired-token work;
- a new evidence packet for each intermediate state;
- exhaustive exporter certification before any bounded compatibility exercise;
- treating every harmless state discrepancy as a rollback event rather than reconciling it directly.

This does not make those techniques universally wrong. They become appropriate when relevant inputs changed, evidence is missing, the state is nonempty, custody is incoherent, a transaction outcome is ambiguous, or the next action crosses a credential, clinical-data, publication or traffic boundary.

## Proportionate path

The remaining rollout can be governed by direct controls:

1. Stop and verify termination of the sole web/calendar metadata owner.
2. In one guarded transaction, lock the singleton then `cha` and `joy`, verify the expected bound/empty state and mapping revision, advance the calendar revision, stamp existing warning generations coherently and enable the schedule marker.
3. Commit once; on an ambiguous result, keep writers stopped and reconcile by readback rather than retrying.
4. Reopen the same SQL/raw pair behind the already-expired upload credential and verify custody identity, enabled editor, coherent revisions and zero imports.
5. Enter and read back approved Cha/Joy schedules.
6. Replace the bootstrap credential with a distinct future-expiring producer credential only in an attended intake window.
7. Perform one bounded compatibility exercise, one attended real capture and focused private parity review.
8. Run ordinary origin, form, TLS and rollback smoke checks before traffic cutover.

These controls retain the consequential safety boundaries: custody coherence, single-writer operation, transactional revision integrity, secret custody, ambiguous-outcome reconciliation, clinical parity and attended public cutover.

## Correction criteria

Future operational guidance should:

- start from the latest verified state and explicitly delete completed gates from the remaining path;
- identify the concrete failure mechanism controlled by every proposed review, artifact or repeated check;
- distinguish missing operator documentation from missing implementation;
- reuse evidence bound to unchanged source, configuration and external state;
- prefer one guarded transaction plus decisive readback over a new campaign for a one-time reversible transition;
- escalate verification for non-idempotent migration, nonempty custody, ambiguous provider/transaction outcomes, real clinical intake, credential release and traffic cutover—not merely because the target is production;
- periodically recompute the minimal safe path instead of appending controls indefinitely.

## Status

Near miss documented after owner intervention. The overcomplicated continuation was not executed and no new implementation campaign was authorized. The corrected direction is a concise attended marker transition followed by schedule entry, bounded exporter/intake acceptance and ordinary cutover checks. No credentials, patient data, private resource selectors or raw production logs are included here.
