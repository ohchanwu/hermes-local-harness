# Documentation

This index is the entry point for durable harness documentation tracked in Git. Load this index instead of recursively reading the docs tree.

## Hermes behaviour the harness depends on (check after every Hermes upgrade)

After every Hermes upgrade, run `scripts/verify-state`; it reports FAIL when one of these Hermes behaviours no longer holds.

- Per-card reasoning effort of the `jev` plugin: the documented `llm_request` plugin middleware, the `provider` and `model` keyword arguments that `agent/turn_api_request.py` passes to it, the Kanban variables `HERMES_KANBAN_TASK` and `HERMES_KANBAN_BOARD`, which `bind_worker_context` in `gateway/session_kanban.py` sets in the worker process (Hermes v0.23.3), and the top-level `reasoning_effort` of the `zai` provider. Decision record: [decisions/261120-per-card-reasoning-effort.md](decisions/261120-per-card-reasoning-effort.md). Verify-state check: `check_hermes_reasoning_effort_sources` (FAIL on drift; WARN when the Hermes Kanban tools contain `reasoning_effort`, which means a supported per-card option may exist). When it breaks, model requests are sent unchanged and workers run at the reasoning effort of their profile.
- Manual Hermes and plugin updates (owner instruction, 2026-11-20): Hermes v0.23.3 applies plugin updates with no person involved when `plugins.auto_apply` is true (`auto_apply_enabled` in `hermes_cli/plugins_cadence.py`, line 117, called at line 277); the default is false (`hermes_cli/config_defaults.py`, line 1675). Verify-state check: `check_plugin_auto_apply` (one FAIL line for each profile whose `hermes config get --json plugins.auto_apply` value is true). After an upgrade, confirm that Hermes still reads this key and that the default is still false; if the key is renamed, the check passes while unattended plugin updates can be on.

## Layout

- `plans/` contains active implementation plans.
- `specs/` contains active or awaiting-approval requirements and designs.
- `decisions/` contains durable decisions; maintained cross-cutting harness policy lives in root `policies/`.
- `archive/` contains completed plans and retired designs.

## Current entries

- [Decision: reasoning effort of one Kanban card, set by the worker's `jev` plugin](decisions/261120-per-card-reasoning-effort.md) — body line `Reasoning effort EXACT <level>.`, applied by the `llm_request` middleware of `jev` for GLM and Claude workers; the Hermes behaviour it depends on and the verify-state check `check_hermes_reasoning_effort_sources`.
- [Claude worker compression threshold, route very_hard, GLM workers first for hard cards, GLM reviewer before the Opus reviewer](specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md) — owner-approved specification (2026-11-14); the work is done by separate cards on board harness, and each live deployment is a separate card.
- [Scheduled board check for each orchestrator](../procedures/orchestrator-board-check.md) — `scripts/orchestrator-board-check` with one settings file per orchestrator and the cron prompt in `deployment/orchestrator-board-check/`: findings NO-WAKE-SUBSCRIPTION, APPROVED-NOT-INTEGRATED, STALE-BLOCKED and STALE-REVIEW; live rollout is a separate card.
- [Human deployment guide review](../skills/devops/human-deployment-guide-review/SKILL.md) — shared skill `human-deployment-guide-review` (version 1.0.0): six review steps for a guide that a person runs against production, with the rules of `human-deployment-guide-writing` as the rule list; declared for jobcron-reviewer and chapt-reviewer; live deployment is a separate card.
- [Human deployment guide writing](../skills/devops/human-deployment-guide-writing/SKILL.md) — shared skill `human-deployment-guide-writing` (version 1.0.0): twelve rules for a guide that a person runs against production; declared for jobcron-orchestrator, jobcron-worker, jobcron-worker-2, jobcron-worker-glm-easy-1, jobcron-worker-glm-easy-2, jobcron-worker-glm-medium-1, jobcron-worker-glm-medium-2, jobcron-worker-glm-hard-1, jobcron-worker-glm-hard-2, jobcron-reviewer, chapt-orchestrator, chapt-worker, chapt-worker-2, chapt-worker-glm-easy-1, chapt-worker-glm-easy-2, chapt-worker-glm-medium-1, chapt-worker-glm-medium-2, chapt-worker-glm-hard-1, chapt-worker-glm-hard-2 and chapt-reviewer; live deployment is a separate card.
- [Cha PT scraper repository scope and owner-approved pushes to its `main`](specs/261020-chapt-scraper-repository-scope-and-push.md) — owner specification (2026-10-20), repository desired state only: three-repository Cha PT allowlist, `cha-webpt-website-sync` project, controller-only per-SHA push helper `scripts/chapt-push-scraper-main` and the clone's `pre-push` hook. Clone, project creation, hook installation and live deployment are a separate attended rollout.
- [Live verify-state drift triage (2026-10-19)](state/261019-live-drift-triage.md) — skill/SOUL expectations derived from tracked sources; every remaining live FAIL classified with its recommended action.
- [Points not yet verified for GLM workers on `hard` cards (2026-11-14)](state/261114-hard-route-unverified-points.md) — read-only report on the eight points that the request for the `hard` and `very_hard` routes left unverified.
- [Switching Hermes profiles between Claude, GPT and GLM](../procedures/switching-hermes-models.md) — where the retired GPT profiles and config backups are, and `scripts/switch-profile-model`.
- [Claude subscription helper support](specs/261017-claude-subscription-helper-support.md) — implemented and live; Hermes helper jobs (compression, titles, approval, vision, …) run on the provider. Title generation was rejected until the 2026-10-17 fix ([bug record](bugs/261017-claude-subscription-cli-retries-and-title-helper-rejected.md)).
- [Claude subscription transcript rebuild](specs/261017-claude-subscription-transcript-rebuild.md) — implemented; review approved; live smoke (with rebuild) and a harness-worker Kanban pilot passed on CLI 2.1.302 with the headless login token. Rolled out as the default model of the worker, reviewer and orchestrator profiles in all three projects; see the provider README.
- [Claude subscription provider hardening](specs/261017-claude-subscription-provider-hardening.md) — implemented; independent review approved; live smoke test passed (CLI 2.1.283); not installed in live Hermes.
- [Claude Max 20x inside Hermes and model portability](specs/261016-claude-max20x-model-portability.md) — execution specification; native billing verification first; implementation/live testing not yet authorized.
- [Claude Max 20x implementation plan](plans/261016-claude-max20x-implementation-plan.md) — native-first M0–M5 execution plan; execution unexecuted/unapproved.
- [Claude Max 20x native pre-inference gate](operations/261016-claude-max20x-native-preflight.md) — bounded execution update superseding the historical unexecuted labels above: documented NATIVE_FAILURE; M1 UNRUN, no account/billing proof or rollout.
- [Private-local Claude runtime feasibility](../spikes/claude-subscription-feasibility/README.md) — bounded offline M2 update: PARTIAL, source-path/inert mechanisms only; no Support-letter prerequisite for non-inference work, no official/account compatibility or rollout claim.
- [Incident recovery without invented authorization gates](specs/261014-incident-recovery-without-over-gating.md) — authorized local implementation; behavioral evidence and same-card review required, no live rollout.
- [Incident-recovery implementation plan](plans/261014-incident-recovery-implementation-plan.md) — adopted standalone plan with the foreign-read fixture verification correction.

- [Concurrent project fleets](specs/261004-concurrent-project-fleets.md) — implemented and verified Jobcron, Cha PT, and Harness isolation; the Harness attended live rollout is operational.
- [Diagnostic convergence policy](../policies/diagnostic-convergence.md) — maintained design and review contract; [authority boundaries](../policies/authority-and-review.md).
- [Overgating review checklist](../policies/overgating-review.md) — reviewer findings for gates, holds, caps and ceremony in specs, plans, procedures and policy; applied by the harness, Cha PT and Jobcron reviewer SOULs.
- [Completed diagnostic-convergence implementation plan](archive/261003-diagnostic-convergence.md)

- [Autonomous Astra terminal-retry harness plan](plans/260929-autonomous-astra-terminal-retry.md)
- [Hermes terminal outcome notification specification](specs/260921-hermes-terminal-outcome-notification.md)
- [Completed local Hermes harness tracking plan](archive/260920-hermes-local-harness-tracking-plan.md)
- [Decision: reviewers on Claude Opus 5.5, orchestrators on Claude Fable 5.2](decisions/261113-reviewers-on-opus-orchestrators-on-fable.md) — the measured token use of both roles from 2026-11-11 to 2026-11-13 and the owner's reasons.
- [Decision: how a card passes from the GLM reviewer to the Opus reviewer](decisions/261114-glm-reviewer-pass-to-opus-reviewer.md) — the Hermes calls that move a card from a GLM review run to an Opus review run.
- [Decision: behaviour of the harness plugins and provider across Hermes updates](decisions/261120-plugin-behaviour-across-hermes-updates.md) — every Hermes name used by `jev`, the terminal outcome notification plugin and the `claude-subscription` provider, whether Hermes documents it, and seven proposed changes.

## Bugs

- Harness defects found by project orchestrators arrive as cards on the harness board assigned to `harness-worker`, filed under the `harness-bug-report` skill ([skill source](../skills/harness-bug-report/SKILL.md)); harness workers write the `docs/bugs/` entries from those cards.
- [Claude subscription provider rejected CLI retries, title-helper requests and parallel tool calls](bugs/261017-claude-subscription-cli-retries-and-title-helper-rejected.md) — fixed and deployed: mid-reply CLI retries restart cleanly before any text reaches Hermes; `extra_body.reasoning` on helper calls is accepted and ignored; parallel tool calls are supported.
- [Repair-history formatting blocked approved autonomous completion](bugs/261017-repair-history-formatting-blocked-approved-completion.md) — task-local bookkeeping gate removed; systemic prevention not implemented.
- [Kanban dispatcher records a live worker as crashed and starts a second worker](bugs/261023-kanban-live-worker-marked-crashed-duplicate-dispatch.md) — defect in Hermes Agent, already reported upstream (issue #141758); no change in this repository.
- [Kanban dispatcher reclaims the expired claim of a rate-limited worker and counts it as a failure](bugs/261028-kanban-rate-limited-exit-settled-as-stale-reclaim.md) — defect in Hermes Agent, diagnosed from source; reported upstream (issue #145820); no change in this repository.
- [Cards made with `hermes kanban create` had no notification subscription](bugs/261030-kanban-cli-create-no-notify-subscription.md) — defect in Hermes Agent CLI create (no subscription, no warning); read-only check added as scripts/check-notify-subscriptions; upstream not checked.
- [Orchestrators lost their skill text in context compression and edited their own skills](bugs/261030-orchestrator-skill-loss-and-self-editing.md) — roster requires skills.auto_load, skills.write_approval and SKILL.md as a protected instruction file name on the five orchestrators, checked by verify-state; skill section `## Skill Changes` added; live rollout on a separate card; upstream not checked.
- [Kanban respawn guard held a ready card as `blocker_auth` because the stored error text of an earlier crashed run contained the word "Authorization"](bugs/261029-kanban-respawn-guard-stale-failure-text-blocker-auth.md) — defect in Hermes Agent, diagnosed from source (`check_respawn_guard` applies the regular expression to stale `last_failure_error` text; `specify_triage_task` does not clear it); workaround is block and unblock; no change in this repository; upstream not checked.
- [Jobcron upgrade orchestration: repeated first-launch ceremony](bugs/261007-jobcron-upgrade-orchestration-repeated-first-launch-ceremony.md)
- [Jobcron test-boundary incident incorrectly halted autonomous implementation](bugs/261007-jobcron-test-boundary-incident-overblocked-autonomous-implementation.md)
- [Jobcron over-gating read-only incident assessment stalls autonomous work](bugs/261013-jobcron-over-gating-readonly-incident-assessment.md) — recurrence focused on unnecessary authorization gates and campaign-wide dependency invention.
- [Cha PT calendar rollout accumulated disproportionate ceremony](bugs/261013-chapt-calendar-rollout-overcomplicated-bootstrap-plan.md) — near miss caused by carrying proof-oriented migration scaffolding into a narrow empty-state transition.

## Ponytail 5.3.3 decision (2026-11-18)

Decision of 2026-11-18: Ponytail 5.3.3 at commit 7801d061243d7b753bad0e0b3c057cd250b11755 is enabled at level `full` on the 56 profiles of the five boards and on `advisor`. The level is set per profile by `PONYTAIL_DEFAULT_MODE=full`, so `/Users/chanbla11mit/.config/ponytail/config.json` stays as it is. The orchestrators no longer force `minimal-implementation` on a card.

Owner message to `harness-orchestrator`, Telegram direct message, 2026-11-18, verbatim: "Yes, install the latest version of Ponytail, and yes, do your proposals. As for the decisions, have it always on and put it on all boards."

Owner message approving the plan with level `full` on all workers, reviewers and orchestrators of the five boards and on `advisor`, verbatim: "Yes."
