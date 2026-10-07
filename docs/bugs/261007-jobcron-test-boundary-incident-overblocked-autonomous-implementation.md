# Jobcron: test-boundary incident incorrectly halted autonomous implementation

Date: 2026-10-07. Scope: Jobcron board, card `t_1f2581e2`, worker run122 and controller response.

## Failure

1. Despite an explicit card prohibition, worker122 ran `go test -count=1 -timeout=8m ./...` with `JOBCRON_TEST_POSTGRES_URL` enabled. Existing preview tests use that variable as an activation switch but invoke `scripts/preview-interactive.sh`, which targets the shared local Compose project rather than the supplied disposable database. This crossed the authorized test boundary.
2. The controller correctly fenced that test path, but incorrectly made permission to inspect shared-local state a prerequisite for **all** autonomous implementation. It requested a human decision and left the campaign stopped instead of continuing independent, already-authorized work in the isolated feature/recovery worktrees.

## Evidence and limits

The native blocked receipt, worker handoff and retained broad-test log agree on the invocation. The preview script hard-pins its Compose project and performs service startup and database create/drop operations. The controller verified only the recorded owned fixture container's absence. Exact shared-local impact and cleanup remain unknown; neither absence on the disposable endpoint nor fixture cleanup proves shared cleanup. No candidate commit or independent code approval existed at the stop.

Evidence remains on the same card and in its pinned primary worktree under `.superpowers/sdd/implementation122/`. The retained broad-log SHA256 is `c41a35049219842252a1ede3c33f9adefb961a60205e2e96031519a954f42f20`. No credentials, user data or raw runtime logs are included here.

## Root cause and responsibility

The worker failed to enforce the documented environment/fixture boundary. The controller then conflated an incident requiring separately scoped actions with a campaign-wide dependency it had not established. The installed orchestration policy explicitly separates fixture-boundary incidents from code correctness; it does not say that every such incident revokes autonomous local implementation authority. This was an execution/orchestration failure, not an established Hermes runtime bug.

## Correction

- Preserve incident evidence and unresolved shared-state questions without claiming safety clearance.
- Continue the existing card and preserved code autonomously; do not duplicate tasks or reset repair history.
- Remove optional database/browser activation explicitly from every broad test subprocess. Scope disposable PostgreSQL activation only to inspected targeted commands; never rerun the shared preview path.
- Treat ordinary implementation/test defects as worker repairs and independent-review work, not routine requests for human intervention.
- Gate only actions that actually require additional authority. An incident blocks another action only when an evidenced dependency makes proceeding unsafe; it is not automatically a campaign-wide halt.

Status: report written; same-card isolated implementation resumption directed. Shared-local assessment/remediation is not performed or declared complete. Feature, recovery rehearsal, independent review and integration still require actual passing evidence.
