> Legacy: describes the retired GPT-era fleet (Flash/Luna/Terra/Sol/Astra, retired 2026-10-18). Retained for history; does not govern current Harness routing.

# Escalation ladder vglm-review-v2

Flash → Luna → Terra → GLM-full → Sol → Astra → human.

Direct entry: Flash, Terra, or GLM-full. One same-rung revision is normal; a second is final and only for localized convergence or materially faulty reviewer guidance. Reviewer attribution never resets the limit. After two revisions, approve, escalate once, or human-block.

`glm-review-v1` remains compatible: all Astra exhaustion and repeated infrastructure failure human-block. `glm-review-v2` preserves that bounded default unless the exact card/root metadata is `ladder_version: glm-review-v2`, `authorization_mode: autonomous`, and `terminal_retry_policy: astra-until-approve-v1`. Only then may independent `reviewer-sol` issue fenced `RETRY_TERMINAL` for a concrete remediable semantic defect at Astra. Astra remains the final implementation rung: `continue` returns the same fenced card to `worker-astra`; `restart` preserves rejected evidence and starts from the recorded protected baseline. A new Astra run and independent review are required; stale, duplicate, or unchanged-candidate verdicts are rejected.

User stop, product decisions, credentials/MFA/prohibited writes, unsafe state, capability boundaries, and policy/legal/security decisions always human-block. Provider, quota, crash, timeout, unavailable-model, and context-exhaustion remain infrastructure outcomes and never enter the terminal semantic retry loop.

The rung-relative revision rule above is only for legacy/default-board cards. Project-isolated `jobcron` and `cha-pt` cards may instead opt in on the exact card with exact full-line `authorization_mode: autonomous` and `repair_policy: bounded-convergence-v1` declarations plus append-only `repair_history` JSON snapshot comments. That policy is independent of ladder length: at most three materially distinct approaches, at most three implementation attempts per approach (initial attempt plus two reviewer-directed corrections), and at most one infrastructure retry of an unchanged operation per attempt. Every completed implementation attempt still requires a unique candidate commit and independent review run. A repeated infrastructure failure spends the attempt. A rejected third attempt retires the approach; it is never an approval path. Exhausting one approach permits an autonomous strategy reassessment on the same card, but exhausting all three approaches human-blocks under v1. Repair authority never transfers to a replacement card, and changing a worker, model, branch, worktree, prompt, label, or approach ID is not a new approach and never resets history.

Exact `repair_history` formats. `scripts/verify-state` rejects a snapshot that does not follow them:

- `approach_id` uses only lowercase letters, digits and hyphens, starts with a letter or digit, and has at most 64 characters, for example `a1` or `a2`. An ID with uppercase letters, such as `A1`, is rejected.
- `strategy_sha256` is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of the `strategy` text after every run of whitespace is replaced with one space and leading and trailing whitespace is removed. Copy the strategy text byte-for-byte into the snapshot, and compute the hash from that same text with this exact command: `python3 -I -c 'import hashlib,sys; print(hashlib.sha256(" ".join(sys.argv[1].split()).encode()).hexdigest())' "<strategy text>"`.
- The snapshot appended before the first dispatch has `implementation_run_id: null`, because no run exists before dispatch. After the dispatcher starts the run, append a successor snapshot that sets `implementation_run_id` to that run ID and changes nothing else. Follow the same two steps when an appended attempt or approach is recorded before its dispatch. Only the final attempt of the final approach may have a null run ID, and only while that attempt has `outcome: "pending"`, `infrastructure_retries: 0`, `candidate_commit: null` and `review_run_id: null`. A pending attempt with a null run ID never changes directly to another outcome.

Complete example of a valid snapshot line before the first dispatch:

```text
repair_history: [{"approach_id":"a1","strategy":"Add a bounded retry limit to the export job and cover the limit with one unit test","strategy_sha256":"95a031c63f8d9676ebce8a6628f6c9681318ef99b653ca6619e1ff9a941aa934","material_difference_review_run_id":null,"attempts":[{"candidate_commit":null,"implementation_run_id":null,"review_run_id":null,"infrastructure_retries":0,"outcome":"pending"}]}]
```
