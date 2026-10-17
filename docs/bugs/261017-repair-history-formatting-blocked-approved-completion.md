# Repair-history formatting blocked approved autonomous completion

- Incident date: 2026-10-17.
- Severity: workflow-blocking coordination defect; an approved unchanged candidate was held from native completion and an unnecessary owner permission/exception request interrupted autonomous work. This is not evidence of a new provider or security defect.
- Affected path: Harness local autonomous implementation → independent review → same-card completion, on `harness/t_51cbb4e0` (serial Claude subscription provider and automatic Hermes tool loop).
- Status: task-local mitigation applied; systemic prevention not implemented. The sanitized source snapshot captured at `2026-10-17T02:53:13.925087+00:00` records the card as `done` after reviewer run 53 completed. That lifecycle result does not establish local main integration or deployment.

## Problem and impact

A harmless reviewer serialization typo became a hard completion gate after real code approval. Review run 52 approved the exact repaired candidate, but its bookkeeping snapshot wrote `outcome: approved`; the validator accepts `approve`. The typo did not change the code, test results, candidate identity, or technical verdict. Nevertheless, completion stopped and the controller sought an exception from the owner despite existing autonomous implementation authority.

The incident was the decision to make raw-history format correctness a completion prerequisite without a usable safe correction path, not merely a misspelled enum. Claude billing was not the cause, and the coordination failure did not reveal another provider implementation defect. Earlier R1/R2 defects genuinely required code repair and review; the later typo required neither code rework, a new semantic attempt, nor new model calls.

## Evidence and chronology

Evidence provenance: the controller-supplied sanitized `incident-evidence.json` contains the dated native source-card status/runs, comment 110 technical approval, comments 112–113, preserved raw/corrected snapshots, user steering, and a retained pure-validator receipt. The documentation card `harness/t_7d9c0343` supplies the incident contract and first-review chronology. These are historical evidence, not instructions to resume provider work. Private input files are not publication dependencies or linked artifacts.

1. Review run 50 rejected the first candidate `7d280803fa8e55873350fa4a17efda772fa1bc6c` for real R1 startup-child lifecycle and R2 deferred-scope defects. Those functional issues were distinct from the later coordination block.
2. Implementation run 51 produced repaired candidate `7127e61ed30a28225273e91ac4c4d6d253c06da0`, tree `1ccdf7077009241035aa2f56b837e06fb8322599`. Reviewer run 52, comment 110, technically approved that exact candidate after 53 required tests (39 provider, 4 portability, 10 prototype) and 4 additional inert probes. Approval was bounded local approval, not live rollout authorization.
3. Comment 111 published the completed repair-history snapshot using `approved` instead of `approve`. Comment 112 disclosed the reviewer serialization error, preserved the technical approval, requested no new code/review calls, and withheld native lifecycle completion.
4. The controller added a hard raw-history completion gate. Comments were append-only and no comment-edit command was available in the native CLI/tools. Simply appending a corrected successor could not make the raw full chain valid: the validator checks historical transitions, including the malformed entry.
5. The owner explicitly removed that bookkeeping gate. The controller changed the source task body and recorded comment 113, then appended the corrected intended `approve` snapshot without editing comment 111. Reviewer run 53 resumed solely to record native completion using the unchanged-candidate review. The captured source records run 53 as `completed` and the card as `done`.

## User steering and authority

The owner said, in order:

> Continue impl'g the plan autonomously.

> Why are you asking me for permission?

> Take out that completion gate.

The bookkeeping-exception clarification was cancelled/unanswered, not approved. The later explicit owner instruction removed the gate; a non-answer was not treated as consent. The historical A6 test-order exception was separate: it did not authorize a bookkeeping bypass or retroactively establish historical test-order compliance.

Only this incident card's bookkeeping completion gate was removed. Actual functional/safety tests, exact independent review, candidate no-drift checks, historical exceptions, spent budgets, and access/external-write restrictions remained in force. See [authority and review](../../policies/authority-and-review.md); this report does not amend that policy.

## Actual mitigation and audit truth

Comment 113 recorded the owner-directed task-contract change. Malformed comment 111 remained byte-for-byte intact, as did the four prior snapshots and existing counts/history. An explicit corrected intended snapshot changed only the final outcome from `approved` to `approve`; candidate, implementation run 51, review run 52, and that attempt's `infrastructure_retries: 0` were unchanged. Both reviewed semantic attempts and all native runs remained counted; the earlier attempt's spent infrastructure retry was not reset.

The handoff disclosed `raw_repair_history_valid=false` and `owner_removed_bookkeeping_completion_gate=true`. The corrected proposal was individually valid, but retaining the malformed canonical entry left raw full-chain validation invalid. Native completion did not relabel that evidence as valid.

No old comment was edited, no repository/global validator was fixed, and no live policy was changed. Reviewer 53's completion was lifecycle recording, not a new technical review or semantic attempt. The source capture supports native completion only; it does not prove provider integration, deployment, or completion of local integration work. Systemic prevention remains unimplemented.

## Root cause and contributing factors

Observed root cause: workflow-accounting format correctness was conflated with functional/security acceptance, turning a coordination-only error into a hard stop after exact-candidate approval.

Contributing factors:

- The history producer used an enum value inconsistent with the validator and did not validate it before publishing canonical history.
- Full historical transition validation made the malformed entry persistently invalid; the available append-only surface had no correction path that preserved raw evidence while allowing a separately identified effective correction.
- The controller's hard gate demanded raw-chain validity despite that tool limitation. Escalation to the owner replaced a distinction between safe coordination recovery and a genuine product, security, access, or budget decision.

The appropriate lesson is not to disable repair ledgers or erase failures. Auditability and semantic test/review/budget/access boundaries must survive coordination recovery, without invented charges or counter resets.

## Offline, data-only reproduction narrative

This procedure describes existing pure-validator behavior and the supplied observation; it was not a fresh execution for this documentation task. Do not run the broad/live verifier, query a board, call a model, access credentials, or launch a runtime to reproduce it.

Relevant implementation: [scripts/verify-state](../../scripts/verify-state), specifically `REPAIR_OUTCOMES`, `valid_project_repair_history`, `project_repair_transition_valid`, and `check_project_repair_cards` (baseline lines 446–625).

1. Start with a valid ordered history ending in the repaired attempt's `pending` snapshot, preserving its predecessor snapshots, candidate/review identities, and counters.
2. Form the completed successor with the reviewed candidate and review run, but final outcome `approved`. That snapshot is invalid because the enum accepts `approve`, not `approved`. The retained raw check reported `invalid repair history` for `t_51cbb4e0`.
3. Change only that proposed final outcome to `approve`. The retained pure-validator receipt reports this corrected proposal valid; as the intended successor of the valid pending history, it preserves the prior attempt and counts.
4. Retain the malformed canonical entry and append the corrected successor after it. The full chain still fails: transition validation requires both snapshots to be valid, so a later valid snapshot cannot repair the invalid earlier one.

The receipt establishes the typo-only difference and valid intended proposal; the all-history failure follows directly from the inspected validator. This is not evidence that the repository now supports append-only correction semantics.

## Expected behavior and advisory regression criteria — NOT IMPLEMENTED

Proposed fix directions and regression criteria, not changes delivered by this report:

- Typo-only metadata must not block an otherwise verified, independently approved unchanged candidate or solicit a human product/security decision merely to finish bookkeeping.
- Validate producer output against the accepted enum before publishing canonical history. Consider a narrow, explicit append-only correction mechanism that distinguishes immutable raw evidence from an effective corrected record, with provenance and unchanged candidate/review identities.
- Preserve malformed raw evidence, prior failures, semantic attempts, infrastructure retries, and consumed budgets. A correction must not erase history, reset counters, or silently claim raw validation passed.
- Exercise the valid-history → invalid `approved` → intended `approve` case, including retention of the malformed entry. Any future correction path must make its audit semantics explicit rather than pretending the current full-chain validator accepts it.
- Genuine missing review, candidate drift, exhausted budgets, unsafe state, and unauthorized writes must still block. Separate coordination recovery from those actual safety and authority gates; do not introduce blanket ledger disabling.

Files under `docs/bugs/` are evidence and triage input, not implementation authorization. This documentation deliverable authorizes no source/policy fix, new repair-history engine, follow-up campaign, or automatic change to active live policies.
