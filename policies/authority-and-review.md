# Authority and review

The shared tracked skill is canonical; the `~/.hermes` copy is deployed state. Apply only through supported Hermes commands or a manual copy after explicit authorization. Each implementation change requires independent `reviewer-sol` review. No push, PR, deploy, credential change, or automatic deletion is authorized here.

Only an explicit user authorization recorded on the exact card or root campaign may set `terminal_retry_policy: astra-until-approve-v1`; it also requires `ladder_version: glm-review-v2` and `authorization_mode: autonomous`. It is not inherited from a repository, tenant, assignee, model, or another card, and in-flight cards are never silently migrated. The authorization permits only fenced Astra semantic retry: it does not permit external writes or weaken retained human gates for user stop, product decisions, credentials/MFA/prohibited actions, unsafe state, capability limits, or policy/legal/security decisions.
