# Diagnostic convergence

Diagnostics unlock decisions; they are not reusable products by default. This policy constrains design, not required verification or authority. All existing external-read/write, credential, mutation, deployment, and cutover HUMAN GATEs remain unchanged. Read-only does not mean authorized; obtain any required owner approval before the probe.

## Card contract

Before diagnostic design or execution, record:

- `work_kind: diagnostic` (separate any production/mutation implementation slice).
- `decision_to_unlock`: the concrete next decision, not “collect more evidence”.
- `hypothesis`: one falsifiable claim and its disconfirming observation.
- `minimum_probe`: smallest observation capable of testing that claim.
- `risk_tier`: local-synthetic, external-read, or mutation; identify data exposure and applicable approval gates. Remote execution may be a provider write even when its payload only reads.
- `outcome_to_next_action`: positive, negative, and INDETERMINATE outcomes, each mapped to an action or stop condition.
- `complexity_budget`: maximum elapsed design effort, files/dependencies, external-call units, and generations (at most two), chosen before work begins.

Reject likely-INDETERMINATE probes that do not change the next action. Positive and negative evidence must each have stated decision utility; absence of evidence is not proof of absence without coverage. If all credible outcomes lead to the same action, take that already-authorized action or stop rather than building the probe.

## Probe ladder and trust

Use the lowest sufficient rung: trusted direct command → local synthetic repro → one-off bounded script → sealed reusable controller. Document why each simpler rung is insufficient before ascending. A sealed reusable controller requires written justification of decision value, expected reuse, and the concrete threat that requires sealing; incident diagnosis alone is not justification for generalized automation.

Accept approved platform/system tools within their stated trust boundary. Verify tool identity, arguments, target, permissions, output handling, and relevant version behavior proportionally to risk; do not recursively attest or reimplement the trusted OS/toolchain without a concrete threat. Secret isolation, bounded targets, owner-only custody where required, fail-closed safety checks, and independent review are never optional.

## Convergence governor

Allow at most two design generations per hypothesis across cards, worktrees, and model rungs. A generation is an initial probe design or its materially revised replacement, not a shell invocation. After the first material review correction, reassess the approach before editing: retain only if the decision utility and remaining budget still justify it; otherwise simplify, pivot, or abandon. A material correction changes safety, evidence validity, scope, or the decision model, rather than wording or formatting.

After a second material failure or exhausted complexity budget, require a strategy pivot or abandon the probe; do not keep refining the same design by default. Preserve rejected evidence and record the failed hypothesis/design, spent budget, and new strategy. Renaming a hypothesis, creating a new card, or changing models does not reset its budget. A pivot must change the evidence path or decision framing and explain why it can converge; no viable authorized pivot means HUMAN BLOCK, not another invented model rung.

Unlimited terminal retries mean campaign-level problem solving, not unlimited refinement of one diagnostic design. Existing card-scoped Astra retry authorization, fencing, bounded individual runs, independent review, and infrastructure/human exclusions still apply. Record an exhausted design's strategy pivot before requesting another eligible campaign retry.

## One-time acceptance

Accept a one-time diagnostic when the bounded probe has been reviewed and exercised against representative positive, negative, and indeterminate/error cases, required risk-based checks pass, evidence coverage/limitations and the actual outcome are recorded, and that outcome selects the declared next action. Live evidence still requires its own authorization; synthetic success is not live proof. Do not demand a reusable framework, generalized schema, lifecycle register, or future-proof controller unless the decision and threat model require it. Stop after the decision is unlocked; keep sanitized evidence and retire the probe without expanding scope. No diagnostic result grants mutation or cutover approval.

## Bounded authorization call envelopes

Before execution, owner-approved envelopes must name target/scope, allowed operations, maximum external-call units, expiry/stop conditions, retry/pagination/polling behavior, and output custody. State whether the unit is a provider request or a stricter owner-defined action; a local command is not automatically one request.

A proven local pre-provider failure consumes no external-call units. Each completed provider request consumes one unit, including provider error responses; SDK retries, pagination, and polling each count separately. Disable implicit retries or bound them within the envelope. An ambiguous submission/timeout is not a free retry: reserve its possible unit and stop for authorized reconciliation before resubmitting. Local retries still consume design/time budget and never bypass an explicit attempt cap. Missing or ambiguous envelope semantics require owner clarification, not inferred permission; extending any envelope requires fresh owner approval.
