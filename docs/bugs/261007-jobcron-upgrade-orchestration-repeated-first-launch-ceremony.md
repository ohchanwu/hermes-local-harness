# Jobcron: routine upgrade expanded into first-launch-style orchestration

Date: 2026-10-07. Scope: Jobcron combined application upgrade and controller release orchestration. This is an execution/process failure, not an established Hermes runtime defect.

## Failure and impact

An already-deployed application upgrade became a prolonged sequence of operational packet revisions, reviews, deadline/cap amendments and credential questions. The owner expected the CI/CD investment to make subsequent deployments straightforward. The controller did not deliver that experience and discovered incomplete credential custody after substantial release preparation. The owner stopped the campaign; this report does not authorize resumption.

The failure is **disproportionate sequencing and operator burden**, not that every review was redundant or that all previous tests were actually rerun. Several reviews reused accepted evidence correctly. Actual CI defects and changed safety-helper semantics required targeted correction and exact-source binding. Those legitimate sub-gates nevertheless accumulated into a release process that was not kept proportionate to an application upgrade.

## Observed evidence

- The application changes include UI copy/progress JavaScript, AI prompt/scoring/cache/retry behavior, and the additive PostgreSQL migration `0020_ai_score_outcomes.sql` (with its SQLite counterpart). This is not exclusively a copy-only release.
- Application testing, an owned database forward/recovery rehearsal and independent review were already accepted. Review140 approved the corrected source pair; Review143 and Review145 separately approved operational data bindings, not successful live deployment.
- Hosted CI encountered a Compose-renderer compatibility failure. Subsequent local fixes addressed the verifier and test fixtures. This was release/tooling work, not a new infrastructure design requirement.
- The inspected `publish-production-image.yml` checks out a selected commit and publishes a private arm64 image. It contains no production-host replacement step. Image delivery exists; the final production-update procedure still relies on controller-run operations.
- The original controller acquisition reserved five credential groups conservatively, then retained only predetermined matching environment keys. Only GitHub/registry credentials were retained. That reservation did not prove AWS/master/owner credential availability, permissions or lifetime.
- The owner subsequently confirmed that the existing RDS master and application owner-login credentials are in the controller's `.env`. Missing retained keys were not evidence that the credentials did not exist. Actual field bindings remained unresolved; no fresh value acquisition occurred after that clarification.
- A proposed additional acquisition/authentication amendment was cancelled/unanswered, followed by the explicit owner stop. The narrow data card `t_ff410099` remains completed; the deployment remains incomplete. No production mutation occurred in this continuation.

## Root cause and responsibility

The controller failed to distinguish three surfaces consistently:

1. **Reusable platform evidence:** unchanged infrastructure, networking/TLS, deployment topology and accepted transport/security mechanisms.
2. **New-release evidence:** changed application behavior, exact-source CI/artifact identity, migration compatibility and recovery.
3. **Current execution prerequisites:** selected credential custody, usable scope/lifetime, actual targets and the next operation's budget/window.

First-launch-style packet preparation and serial amendments dominated a routine upgrade. Credential capability mapping was completed too late, and fixed guessed environment names were treated as sufficient discovery. The controller then presented additional preparation burdens instead of an already-ready bounded update path. These are controller execution failures. The owner's safety limits did not cause the sequencing mistake and must not be weakened retrospectively.

The pipeline's scope also fell short of the expected easy-upgrade experience: automated artifact publication is not end-to-end production deployment. That gap should have been stated upfront, not discovered through repeated operational handoffs.

### Protected-acquisition ceiling finding

The campaign-wide protected-read ceiling was a controller-created authorization device, not an AWS, GitHub, Hermes or security-standard requirement. Its intended purpose was defensible: limit repeated exposure of credentials and secret-backed runtime values, make failed or ambiguous provider reads consume retry authority, and encourage reuse of securely retained custody bytes.

The implementation became disproportionate. One aggregate counter combined materially different events: credential-provider acquisition, Secrets Manager bundle retrieval, owner-login or package-token custody, exact runtime-source reads, and forward/recovery verification bundles. The approved `ceiling20/prior7` later became a proposed ceiling22 with reservation14 because eight possible runtime acquisitions exceeded the six remaining units. Those numbers were bookkeeping consequences, not independently meaningful risk thresholds. The aggregate could therefore block a safe necessary deployment read because unrelated historical acquisitions had consumed units, while adding operator amendments and reconciliation work without directly reducing the risky behaviors.

Removing the aggregate counter does not mean permitting unlimited secret access. The material risks remain repeated provider calls, unnecessary secret exposure in additional processes or temporary files, ambiguous retries, throttling/audit noise and weak forensic attribution. Control those risks at the actual acquisition boundary rather than through one campaign-wide number.

### Meta-finding: caution can become a security liability

Agents tend to add operational machinery in the name of caution: extra ledgers, envelopes, counters, reviews, intermediate artifacts, reconciliation steps and exception paths. Past a proportional safety floor, this can reduce rather than improve security. Every additional state transition and policy layer creates more code or prose to interpret, more opportunities for contradictory authority, stale artifacts, unsafe recovery, secret duplication and human error. A system that operators cannot readily understand, audit or execute is harder to secure and recover.

Excess ceremony also delays deployment. That can prolong exposure to known defects, leave old and new procedures coexisting, increase configuration drift, and encourage emergency bypasses when the official path becomes impractical. Security controls should therefore minimize total system complexity while directly addressing a named threat. Prefer simple, observable and independently reviewable boundaries over indirect proxy counters or duplicated workflow state. “More cautious steps” is not itself evidence of lower risk.

### Artificial time-limit finding

The controller also converted a user-selected completion horizon into an elaborate authorization and scheduling system. The `21:00 KST` horizon was combined with worst-case serial duration estimates, a 7,200-second host/TLS-tunnel allowance, candidate-specific CI allowances, recovery reserves, 1,800-second stability observations and reporting time. That arithmetic produced backward-derived latest-start cutoffs, ultimately `17:46 KST`. At `17:48:40 KST`, the controller declared the entire deployment a technical no-go because its conservative reserve exceeded the remaining horizon by 161 seconds—even though these were modeled maxima rather than observed execution times.

The owner then directed: “Get rid of all the time limits. No more time limits from now on.” The resulting amendment removed the campaign expiry, latest-start cutoffs, full-path timing admission test and aggregate authorization, CI, session and campaign elapsed-time allowances. Yet applying that simplification generated a new 220-field temporal delta, six fresh artifacts and another independent review. This is direct evidence of the failure mode: artificial timing machinery created work and delay after it had ceased to control a concrete risk.

Do not impose artificial campaign deadlines, latest-start calculations or elapsed-time authorization expiry. Approved scope should remain valid until its effects complete, the owner revokes it, relevant state changes invalidate it, or a real external constraint requires renewal. Do not require the entire worst-case serial path to fit inside a guessed wall-clock envelope before starting an otherwise safe operation.

“No artificial time limits” does **not** remove technically meaningful timing controls. Keep provider-issued credential expiry, externally imposed maintenance windows, network and subprocess timeouts, hung-operation watchdogs, retry backoff, lock/session cleanup, and minimum stability-observation periods. These controls address a specific failure mode or prove acceptance. Treat their durations as local technical bounds or minimum verification requirements—not as campaign authority, completion promises, or reasons to discard still-valid evidence. A host session or database tunnel may remain singular and attended without receiving an arbitrary aggregate lifetime.

## Required correction

- Classify the change as an application-only, migration-bearing or infrastructure-changing release before choosing its gates. Do not apply a first-launch procedure indiscriminately.
- Carry accepted unchanged evidence forward by surface. Authentication expiry does not invalidate prior verification; revalidate only after relevant drift or immediately before a materially dependent authorized action.
- Let automated CI verify the new code. Reuse completed local/rehearsal/review results when source and risk bindings remain valid. Correct genuine CI failures once with focused checks; do not restart unrelated verification.
- For this migration-bearing release, retain exact-image identity, pre-change recovery protection, compatible recovery, and focused post-update acceptance. These are genuine safeguards, not optional ceremony.
- Before requesting a deployment window or publishing prerequisite refs, map the entire dependent credential sequence: actual selected key/source names, controller custody, permissions, authentication-provider calls, lifetime and required human inputs. A reservation or file location is not readiness proof. Keep values out of reports, workers and logs.
- Retire the campaign-wide protected-read ceiling, reserved-slot arithmetic and owner amendments whose only purpose is increasing that aggregate. Do not count non-secret runtime or artifact verification as credential acquisition.
- Acquire each credential or secret bundle at most once per execution session when practical, reuse valid securely retained material, and reacquire normally when it expires under the same identity and scope. Permit at most one retry after a proven pre-provider/no-submission failure; an ambiguous provider response is consumed and requires reconciliation before another attempt.
- Keep per-operation target, actor, permission, lifetime, retry and custody bounds. Never place sensitive values in argv, logs, chat, worker contexts or ordinary persistent files. Record value-blind acquisition events for audit without turning their campaign-wide count into an authorization gate.
- Do not add campaign deadlines, latest-start cutoffs, full-path timing admission tests or aggregate session/CI elapsed-time caps merely to make an operation feel bounded. Authorization does not expire solely because a controller's guessed schedule elapsed; it ends through completion, revocation, invalidating state change or a real external constraint.
- Preserve narrowly justified technical timing: credential expiry, provider or maintenance windows, operation timeouts, hung-process watchdogs, retry backoff, cleanup and minimum stability observation. State whether each duration is a maximum safety bound, an external fact or a minimum acceptance requirement; never silently promote it into campaign authority.
- Keep the normal upgrade path concise: approved commit → green CI → immutable image → backup/migration when applicable → application-only replacement → focused acceptance/stability → retain recovery. Do not invent extra infrastructure work.
- Treat completing end-to-end deployment automation as a separate future implementation scope, not implicit authority to alter the pipeline during a stopped release.

## Verification of a correction

A future upgrade should reuse uninvalidated platform evidence, identify all credential dependencies before publication, avoid repeated operator permission requests for already-covered effects, and exercise the new artifact plus any migration/recovery requirements through the approved bounded procedure. Judge success by real deployment output and acceptance—not a reviewed packet or a worker-start notice.

Status: bug recorded; remediation not implemented. Deployment stays stopped. No credentials, private resource selectors or raw operational logs are included here.
