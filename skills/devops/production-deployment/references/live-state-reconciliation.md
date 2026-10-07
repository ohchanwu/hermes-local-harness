# Live-state reconciliation

Use the applicable steps before a materially dependent resource start, Terraform plan, image publication, or infrastructure mutation. On resumption, retain accepted observations and refresh only unknown or relevantly invalidated surfaces; restored authentication alone does not require repeating completed gates.

## 1. Pin identity and source

1. Establish the exact cloud profile, account, and region with the provider identity API when that proof is missing or relevant identity selection changed. Reuse a still-applicable signed identity proof on resumption; acquiring usable credentials under the same selected identity is separate from repeating the identity gate.
2. Verify the repository branch is clean, local and remote release SHAs match, and release CI is genuinely green through every required downstream gate.
3. Keep account IDs, resource IDs, ARNs, endpoints, addresses, bucket names, database names, secret names, and recovered input values out of shared output.

## 2. Stage private controller inputs

1. Locate recovery artifacts by expected filename and provenance without printing their contents.
2. Inspect file mode and top-level schema only. A source copy with permissive mode is evidence to fix in staging, not permission to execute it in place.
3. Create a fresh mode-`0700` scratch directory, copy only required inputs, and set every private file to mode `0600`.
4. Compare competing packets to state by field equality or hashes and report only match booleans and differing field names. Never print values.
5. Preserve every source artifact unchanged until the rollback window closes.

## 3. Pull state without refreshing infrastructure

Use a scratch Terraform data directory so initialization does not alter the repository checkout:

```sh
umask 077
export AWS_PROFILE='<approved-profile>'
export AWS_REGION='<approved-region>'
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_DATA_DIR="$scratch/tfdata"
terraform init -reconfigure -input=false -backend-config="$scratch/backend.hcl"
terraform state pull >"$scratch/production.tfstate"
chmod 600 "$scratch/production.tfstate"
```

Do not run `terraform plan`, `refresh`, `apply`, `import`, or a state command that writes or locks remote state during this phase.

## 4. Reconcile state against live inventory

Parse selectors internally from the pulled state and query read-only describe/list/get APIs for each managed resource. Record value-blind facts:

- existence, lifecycle status, and state/live agreement;
- compute architecture, instance type, encrypted root volume, instance profile, public-address and EIP-association booleans, and management-agent status;
- VPC, subnet, route-table, Internet-gateway, and inherited/explicit route relationships;
- security-group rule counts, ports, and source categories rather than source identifiers; include managed prefix-list sources, compare them internally with accepted source bindings, and do not impose an inline-CIDR-only predicate on a prefix-list-based deployment;
- database status, encryption, public accessibility, deletion protection, backup retention, restore-window availability, subnet/SG attachment counts, and TLS parameter state;
- manual snapshot count/status/latest age;
- recovery and state bucket public block, versioning, encryption, TLS-deny policy, lifecycle, and object/version presence without downloading objects or exposing keys;
- secret metadata existence and rotation status without reading secret values.

Handle each resource independently. A not-found response confirms drift for that resource; it must not abort the remaining inventory. Inventory extra plausible hosts and databases in the same network or naming family by count and status. If more than one pair is plausible, treat selection as unresolved until state, packet provenance, backups, and operator confirmation agree.

## 5. Reconcile edge state

Resolve the public hostname and compare it internally with the current state EIP, live EIP, and host public address. Report only match booleans. Confirm authoritative DNS provider ownership separately. A record pointing to none of the reconciled live targets is stale even if the hostname still resolves.

An all-interface origin listener is not proof of exposure. Determine exposure from the full path: listener, host address/EIP association, security-group ingress, proxy-source restriction, and DNS.

## 6. Start only the selected resources

Ask for a bounded approval that names the state-selected host and database and explicitly excludes EIP association, security-group changes, DNS, image publication, migration, and Terraform plan/apply. Re-read both targets immediately before mutation and stop if either no longer has the expected status.

After requesting each start, wait for and read back effective state:

- compute running state, automatic public-address assignment, unchanged ingress, DNS mismatch/match, and management-agent Online state;
- database available state, private accessibility, encryption, deletion protection, and restored point-in-time recovery metadata.

An automatically assigned public address does not by itself make the origin reachable, but report it and re-evaluate the complete exposure path. Database metadata becoming available does not prove application data integrity or replace the required pre-change recovery point.

## 7. Run sanitized remote diagnostics

Remote command execution is a separate external action; obtain approval even when every command is read-only. Emit only booleans, counts, service states, listener counts, and asset-presence checks. Do not print environment variables, secret files, command lines containing credentials, container inspection payloads, or journals that may contain sensitive values.

Expected inactive states must not abort the evidence collection. Avoid global `set -e`, or guard probes such as `systemctl is-active` with `|| true`. Quote `awk` programs so field references such as `$4` reach awk literally rather than being expanded by the remote shell. Read back the command invocation status and retry only a diagnostic-construction failure, not a substantive failed check.

## 8. Build the fresh plan packet

When the remote backend uses lockfiles, obtain explicit plan-generation approval because Terraform briefly writes and removes the lock object. Use the staged owner-only inputs and scratch `TF_DATA_DIR`; keep the plan binary, human log, and JSON mode `0600`.

```sh
umask 077
terraform plan -input=false -lock-timeout=5m \
  -var-file="$scratch/production.auto.tfvars.json" \
  -out="$scratch/fresh.tfplan" \
  >"$scratch/fresh-plan.txt" 2>&1
terraform show -json "$scratch/fresh.tfplan" >"$scratch/fresh-plan.json"
chmod 600 "$scratch/fresh.tfplan" "$scratch/fresh-plan.txt" \
  "$scratch/fresh-plan.json"
```

Add an explicit `-replace=ADDRESS` only when the reviewed runtime contract requires replacement; the flag is part of the plan's semantics, not a harmless formatting choice. Summarize only logical addresses, actions, reasons, diagnostic count, and output keys. Compute the binary plan digest, then require independent fail-closed review of all before/after values and live prerequisites.

If the plan creates a missing EIP, verify there is no association resource or edge/DNS action. If it replaces a host or volume, reconcile that deletion with the active rollback-preservation rule; preserve the target first or document why the exact inactive target is not a required rollback asset. Do not request apply approval while that question is unresolved. Regenerating the plan invalidates its digest, review, and any apply approval.

Validate the complete observed action combination, not each action in isolation. When a legitimate recovery combines drift classes that the checked-in validator does not support (for example, one missing unattached EIP create plus one explicit host replacement), stop and add an explicit validator mode with an exact argument contract. Require the full allowlisted address set, exact actions and reasons, no imports or moves, known-null association controls, no extra diagnostics or outputs, and mutation tests derived from a valid fixture. Preserve ordinary create and replacement modes unchanged; never make a broad mode more permissive just to pass one live plan.

Generate a fresh value-blind reconciliation checkpoint for recovery modes. Historical phase checkpoints remain evidence of that phase, not reusable claims about current state. The current checkpoint should bind the pending mutation to an exact schema, observation provenance, the clean release commit, selected-target confidence, the approved host disposition, retained rollback assets, EIP/exposure facts, database protection and restore metadata, recovery/backend safety, and runtime-secret metadata without reading or asserting secret content. Do not impose an arbitrary evidence-expiry window; reconcile relevant observed changes and satisfy the actual operation's current-state prerequisites. Record the observed secret-version count as a number when useful, but do not require an obsolete value such as zero after an unmanaged version legitimately exists. Mutation-test invalidated, missing, renamed, false, and unexpected fields. The plan must continue to exclude secret-version resources regardless of checkpoint count.

## 9. Stop and report before mutation

Produce a concise value-blind packet containing:

- exact release SHA and CI result;
- selected host/database confidence or ambiguity;
- drift list;
- encryption, backups, ingress, EIP, DNS, state-backend, and recovery-bucket findings;
- post-start readiness and sanitized diagnostic results when authorized;
- exact plan digest and value-blind action summary when authorized;
- missing evidence and explicit stop conditions;
- the next proposed mutation boundary.

Do not start stopped resources or generate a fresh plan until the intended pair and rollback assets are unambiguous. A fresh plan comes only after reconciliation and requires independent review; regenerating it invalidates any prior apply approval.
