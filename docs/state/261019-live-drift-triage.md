# Live verify-state drift triage (2026-10-19 run, triaged 2026-10-20)

Card t_76a2134d (board harness), baseline 248e3be. This change is repository-only: no live file was read beyond the card's allowlist, and none was written.

## What changed in the verifier

- Shared skills, profile-local overrides and profile SOULs no longer carry hand-written sha256 pins. The snapshot and roster declare structure only: a shared skill's `source` directory under `skills/` plus its file list; `tracked-source` for an override under `policies/profile-skills/<profile>/`; `source`/`live` paths for a SOUL. The expected hash is computed from the tracked file when the check runs. A pin is still allowed where no tracked source exists (worker-astra's learned overrides, the external cha-pt-frontend `AGENTS.md`). A pin placed next to a tracked source is reported as malformed.
- A tracked file that no declaration lists also FAILs, so new policy content can never pass unseen.
- Retired roster profiles (the eight GLM workers, plus the GPT-era `worker-*` and `reviewer-sol` retired by t_4a2ded12) are excluded from shared-skill deployment checks. Non-retired profiles are checked as before. A profile that is not on the roster but has a deployed copy FAILs (`unexpected deployed skill copy`).
- Every profile is checked in its own skill home. The default profile uses `~/.hermes/skills`; every other profile uses `~/.hermes/profiles/<profile>/skills`. Before this change, the `multi-agent-coding-orchestrator` declaration pointed every orchestrator at the default profile's copy. That stale declaration caused the four orchestrator SKILL.md FAILs and the `profile-local skill override declaration drift` FAIL.

## Before and after counts

| Run | FAIL lines |
|---|---|
| Owner's live run, 2026-10-19 (at 061318a) | 58 |
| Baseline 248e3be, from this worker | 32 |
| After this card, from this worker | 19 |

t_4a2ded12 had already removed the 8 GLM "unexpected profile" FAILs, the 22 model/provider FAILs, the dispatch FAIL and the unclaimed-card FAIL before this card started.

Six of the FAIL lines in both of this worker's runs are artifacts of the worker environment, not live drift. The owner's run did not have them:

- `multi-board gateway is still pinned to one database via HERMES_KANBAN_DB`: the Kanban dispatcher sets this variable in the worker's own environment. It disappears with `env -u HERMES_KANBAN_DB` (31 → 18 FAILs).
- `unable to read open Cha PT card list` and `unable to read open project card list <board>` (×4): Hermes refuses `kanban list` from a delegated child context ("delegate_task child contexts cannot mutate Kanban tasks or boards"). The worker did not bypass that guard. Run from an owner shell, these checks read the boards.

With those six excluded: 26 skill/SOUL FAILs before, 13 after.

## Resolved by this card

| Former FAIL | Class | Resolution |
|---|---|---|
| deployed skill hash mismatch: multi-agent-coding-orchestrator chapt-orchestrator, harness-orchestrator, jobcron-orchestrator SKILL.md | (a) stale declaration | The check looked at the default profile's copy. Each profile's own copy equals its tracked override in `policies/profile-skills/<profile>/` (harness-orchestrator was restored there 2026-10-19). |
| profile-local skill override declaration drift | (a) stale declaration | The override hashes are now derived from the tracked sources. Live chapt, harness and jobcron overrides match exactly. The jss override is listed below. |
| deployed skill hash mismatch: multi-agent-coding-orchestrator jss-orchestrator/SKILL.md | (a) path, then listed below | It is now checked against its own home and reported once, as the jss override drift below. |
| production-deployment SKILL.md on worker-astra, worker-flash-1/2/3, worker-glm-full, worker-luna-1/2, worker-sol, worker-terra-1/2 (10) | (b) retired profile | Excluded from deployment checks. These are installed rollback profiles only. |

## Remaining live FAILs after this card (13)

The section names below come from a heading-level comparison. No file contents are reproduced here, and no file contains secrets.

| # | FAIL line | Class | Difference | Recommended action |
|---|---|---|---|---|
| 1 | `deployed skill hash mismatch: multi-agent-coding-orchestrator default/SKILL.md` | (c) real drift: stale deployment | Live `~/.hermes/skills/.../SKILL.md` is 40,754 bytes, version 0.6.5. That is byte-identical to the repository at 7eabda5 (2026-10-07). The current source is 46,129 bytes, version 0.6.10. The repository adds "Routine upgrade selection" and "Incident recovery" and changes preamble, When to Use, Fixed Roster, Cha PT routing, project repair budget, Autonomous, Worker Contract and Verification. | Redeploy the repository version (procedures/manual-apply.md). |
| 2 | `unexpected deployed skill file: multi-agent-coding-orchestrator jobcron-orchestrator/references/kanban-triage-phase-routing.md` | (c) real drift: live-only file | 7,344 bytes, 17 lines, one section "Native triage and review-origin routing", dated 2026-10-15. No tracked source exists in any revision. The live jobcron-orchestrator SKILL.md does not reference it. The old default-home path hid this FAIL. | Owner choice: adopt it into `policies/profile-skills/jobcron-orchestrator/` through a reviewed card, or remove it on redeploy. |
| 3–6 | `deployed skill hash mismatch: production-deployment harness-orchestrator, harness-reviewer, harness-worker, harness-worker-2 SKILL.md` | (c) real drift: stale deployment | Live is 19,796 bytes, version 0.2.3, byte-identical to the repository at 774ec80 (2026-10-07). The current source is 25,752 bytes, version 0.2.5. The repository adds "Release change selection", retitles step 2 and changes steps 3–5 and Verification. | Redeploy the repository version. |
| 7–9 | `deployed skill hash mismatch: production-deployment jobcron-reviewer, jobcron-worker, jobcron-worker-2 SKILL.md` | (c) real drift: stale deployment | Same bytes as rows 3–6 (0.2.3 at 774ec80). | Redeploy the repository version. |
| 10 | `deployed skill hash mismatch: production-deployment jobcron-orchestrator/SKILL.md` | (c) real drift: live-local edits | 27,507 bytes, labelled version 0.2.3, matching no tracked revision. Compared with 0.2.3 (774ec80), steps 1, 5 and 6 and Pitfalls differ (about 7.7 KB added). Compared with current 0.2.5, it also lacks the 0.2.5 changes. | Owner choice: adopt the local edits into `skills/devops/production-deployment` through a reviewed card, then redeploy; or redeploy and drop them. |
| 11 | `deployed skill hash mismatch: production-deployment jobcron-orchestrator/references/release-ci-portability.md` | (c) real drift: live-local additions | 11,478 bytes against 9,171 tracked. Live adds "Database timestamp precision" and "Evidence custody versus test-child permissions". Every shared section is identical. | Owner choice: adopt the two sections through a reviewed card, or redeploy. |
| 12 | `profile-local skill override drift: jss-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | owner chose live (2026-10-19); adopted into repo by t_c2568e54 | 20,564 bytes live against 19,592 tracked, same version label 0.6.7-jss.5. "Hard Scope" and "Autonomy" differ. | None in this card. t_c2568e54 adopts the live bytes. |
| 13 | `profile SOUL drift jss-orchestrator` | owner chose live (2026-10-19); adopted into repo by t_c2568e54 | 2,931 bytes live against 2,471 tracked; the opening paragraph differs. | None in this card. t_c2568e54 adopts the live bytes. |

No other SOUL drifts: the other 12 tracked SOULs equal their live copies.

## Notes

- Rows 1 and 3–9 match an older repository revision, but no current tracked source. Class (a) applies only when live equals a current tracked source. These rows are therefore stale deployments of reviewed content: redeploy, do not adopt.
- `procedures/manual-apply.md` installs the orchestrator skill into the default home only. The per-profile orchestrator copies come from the profile-local override procedure. That procedure is unchanged by this card.
