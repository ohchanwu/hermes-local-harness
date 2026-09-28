# Temporary Cloud Bootstrap IAM

Use this recipe when an operator needs short-lived write authority to create or connect hosting, deployment, or other cloud resources after local preparation has passed review.

## Gate sequence

1. Authenticate a dedicated non-root identity with only inventory/read permissions. Prefer temporary browser or SSO credentials; never repurpose an unrelated administrative profile.
2. Inventory the target account, region, existing resources, and naming/tag constraints without mutation.
3. Write the attended operation sequence first. Give each write operation its own expected API actions, resource identity, verification readback, rollback, and stop condition.
4. Build the temporary policy from that operation map. Exclude actions that have no named step; convenience permissions such as broad update, delete, webhook, or unrelated service access do not belong in bootstrap authority.
5. Independently review the policy and operation map as one artifact. A structurally valid policy is insufficient if its actions cannot perform the documented steps or exceed them.
6. Ask separately for authorization to attach the reviewed policy. After attachment, read back the exact principal, policy form, document/version, and effective boundary before provisioning.
7. Ask separately for authorization to create or connect resources. Verify each external mutation by reading back the exact target before advancing.
8. Remove bootstrap authority immediately after the provisioning phase, then verify its absence. Keep later deployment, domain/routing, and production-cutover permissions behind separate gates.

## Statement partitioning

Derive resource scope action by action from the provider's current service-authorization reference; do not infer it from API path similarity.

- Put a create action under `Resource: "*"` only when the service cannot authorize the not-yet-existing resource by ARN. Constrain it with supported request-tag, region, account, name, or other creation-time condition keys.
- Keep resource-tagging actions out of that wildcard statement when they support the created resource ARN. Sharing one statement silently widens the tag action to wildcard scope.
- Scope child-resource actions to the documented child ARN type. Application, branch/environment, job/deployment, domain, and webhook actions may have different resource support even when they are used in one workflow.
- Split statements whenever action sets require different resources or conditions. Fewer statements are not safer when they erase authorization boundaries.
- Avoid wildcard action families. Enumerate only the calls required by the attended sequence and the reads required for post-write verification.

For create-then-tag services, distinguish tags accepted on the create request from a later tagging call. Require creation tags with request-tag conditions when supported; grant the later tag action only on the specific resource ARN pattern if the workflow truly needs it.

## Cleanup semantics

State the policy form explicitly:

- **Inline policy:** delete it from the principal or group; there is no separate managed-policy object to detach and delete.
- **Customer-managed policy:** detach it from every principal, delete non-default versions when required, then delete the policy object.
- **Session or permission-set grant:** revoke or expire it through that mechanism and verify no active assignment remains.

Do not write generic cleanup prose that mixes these models. The operator must be able to follow one exact removal path and prove the temporary write authority is gone.

## Evidence to retain

Record only non-secret evidence: reviewed policy digest or commit, principal label, region, policy form, attachment/removal timestamps, resource identifiers needed for audit, and sanitized readbacks. Never store credentials, session tokens, account-login URLs, MFA values, or secret-bearing command output in the repository, task history, or chat.
