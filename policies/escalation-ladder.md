# Escalation ladder vglm-review-v2

Flash → Luna → Terra → GLM-full → Sol → Astra → human.

Direct entry: Flash, Terra, or GLM-full. One same-rung revision is normal; a second is final and only for localized convergence or materially faulty reviewer guidance. Reviewer attribution never resets the limit. After two revisions, approve, escalate once, or human-block.

`glm-review-v1` remains compatible: all Astra exhaustion and repeated infrastructure failure human-block. `glm-review-v2` preserves that bounded default unless the exact card/root metadata is `ladder_version: glm-review-v2`, `authorization_mode: autonomous`, and `terminal_retry_policy: astra-until-approve-v1`. Only then may independent `reviewer-sol` issue fenced `RETRY_TERMINAL` for a concrete remediable semantic defect at Astra. Astra remains the final implementation rung: `continue` returns the same fenced card to `worker-astra`; `restart` preserves rejected evidence and starts from the recorded protected baseline. A new Astra run and independent review are required; stale, duplicate, or unchanged-candidate verdicts are rejected.

User stop, product decisions, credentials/MFA/prohibited writes, unsafe state, capability boundaries, and policy/legal/security decisions always human-block. Provider, quota, crash, timeout, unavailable-model, and context-exhaustion remain infrastructure outcomes and never enter the terminal semantic retry loop.
