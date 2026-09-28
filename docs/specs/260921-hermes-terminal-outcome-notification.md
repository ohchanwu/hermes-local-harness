# Hermes Terminal Outcome Notification Specification

Status: Revised draft — approved design corrections incorporated; implementation remains separately authorization-gated

## 1. Purpose

Notify the user through both Telegram and macOS when a watched Hermes orchestrator campaign:

1. completes successfully; or
2. reaches a genuine human-relevant block.

The system must not notify for intermediate activity such as tool calls, streamed output, checkpoints, subagent completion, ordinary review revisions, or recoverable worker failures.

## 2. Design principles

- Terminal outcomes, not activity, generate notifications.
- Campaign tracking is explicit rather than inferred from duration, token count, or tool-call volume.
- Kanban state is authoritative for Kanban-managed campaigns.
- Direct CLI/TUI campaigns use an explicit one-shot watch and a structured terminal outcome.
- Notification generation requires no LLM call.
- Delivery is durable, best-effort deduplicated, and independently retryable per destination.
- The delivery contract is at-least-once. A narrow duplicate window exists if a destination accepts a message and the worker crashes before recording success.
- Telegram and macOS receive the same normalized event but use separate delivery adapters.
- Notification bodies contain concise operational summaries, not transcripts, raw tool output, or secrets.
- The design uses documented Hermes extension points and does not modify Hermes core.

## 3. Non-goals

This system does not:

- notify after every tool call;
- notify after every agent-loop iteration;
- notify when a subagent or ordinary child card completes;
- stream progress updates;
- classify arbitrary assistant prose with an LLM;
- replace Kanban task state;
- replace Hermes's Telegram gateway;
- require Hermes Desktop to remain open;
- modify or patch the Hermes source checkout;
- treat all ordinary conversations as watched campaigns.

## 4. Supported campaign modes

### 4.1 Kanban-managed campaign

A multi-agent campaign should have one designated root or finalizer card. Child tasks, reviews, revisions, and verification feed into this card.

Only the root/finalizer card is watched.

The watched card may complete only after:

- required child work is complete;
- required review and revision cycles are complete;
- final verification is complete; and
- the campaign's final handoff has been recorded.

A child-card terminal event is not a campaign terminal event.

### 4.2 Direct CLI/TUI campaign

A direct orchestrator turn is watched only when explicitly armed. The watch is one-shot and disarms after one terminal outcome.

Conceptual activation interfaces include:

- an in-session command such as `/notify-on-terminal`; or
- an explicit user instruction that causes the orchestrator to arm notification for the current turn.

The final implementation should choose one deterministic interface. It must not infer campaign importance from elapsed time, tokens, or tool count.

### 4.3 Existing unarmed campaigns

The system is not required to reconstruct or retroactively monitor a campaign that began before notification tracking was armed. Transcript polling should not be introduced solely to cover an already-running unarmed turn.

## 5. Terminal outcome contract

### 5.1 Outcomes

The normalized terminal outcomes are:

- `completed`
- `blocked`
- `failed`
- `interrupted`
- `timed_out`
- `unknown`

`completed` and `blocked` are explicit orchestrator outcomes. Runtime state may produce `failed`, `interrupted`, `timed_out`, or `unknown` when the orchestrator cannot record a normal terminal outcome. `unknown` means recovery found an armed campaign but could not prove either a successful final response or a more specific failure outcome; it must never be rewritten as `completed` merely because an LLM call finished.

### 5.2 Direct-turn outcome recording

For a watched direct turn, the orchestrator records a terminal proposal through a small local tool before returning its final response:

```text
campaign_terminal(
    status="completed" | "blocked",
    summary="short operational summary"
)
```

This tool only records state. It must not send a notification immediately.

The notification becomes eligible only when Hermes emits the encompassing `on_session_end` lifecycle event. This prevents the state-setting tool call from becoming an intermediate notification.

`post_llm_call` may retain a bounded candidate summary, but it is not evidence that the turn completed. A recovered direct turn may become `completed` only when durable session state proves that a final assistant response was committed after the terminal proposal and the encompassing turn ended normally. If that evidence is absent, recovery records `unknown` or a more specific runtime outcome; it must not infer success.

### 5.3 Kanban outcome recording

For Kanban campaigns:

- `kanban_task_completed` proposes `completed` for the watched root/finalizer card.
- `kanban_task_blocked` creates only a block candidate. It proposes `blocked` only after the block policy in section 6 classifies the current durable state as human-relevant and final for the watched generation.
- The notifier reads durable task state before emitting an event; it does not rely only on free-form event prose.

## 6. Genuine-block policy

### 6.1 Notify

A block is notification-worthy when human attention is required, including:

- `needs_input`;
- a capability boundary that cannot be resolved automatically;
- an explicit `HUMAN_BLOCK`;
- approval or a product decision required from the user;
- exhausted retry or revision allowance;
- repeated failure routed to triage;
- crash or timeout with no automatic retry remaining;
- required human review or another explicit human gate.

An exact, current-run-fenced `RETRY_TERMINAL` verdict for an opted-in `glm-review-v2` autonomous
Astra campaign is explicitly non-human: it cancels any pending block candidate. The classifier
must require the complete structured marker, including the root task, campaign generation,
repository, protected baseline, worktree/branch, rejected candidate SHA, review run, attribution,
concrete findings, `strategy`, `rung: astra`, and `terminal_retry_policy: astra-until-approve-v1`.
`needs_input` and `capability` remain human-relevant even if the reason contains such a marker; a
malformed, stale, v1, or side-by-side marker must fail closed to the ordinary block policy.
The `campaign_generation` carried by the verdict is a durable campaign identity, not the
notifier's delivery generation: the plugin establishes and advances it (never regresses it)
only when `kanban_task_blocked` records a fully fenced verdict bound to the watched task and
the firing review run, and `kanban_task_claimed` advances only the delivery generation used to
cancel stale pending events. A legitimate campaign therefore suppresses across arbitrary claim
cycles at any durable generation, while a verdict older than the durable identity fails closed
and alerts.

### 6.2 Suppress

Do not notify for:

- dependency waiting with an identified owner and automatic resume condition;
- a transient failure while an automatic retry remains;
- ordinary reviewer-requested revision;
- a blocked child the orchestrator can route around or escalate automatically;
- a failed tool call while the orchestrator continues debugging;
- subagent completion or failure that the parent is still handling;
- intermediate commits, checkpoints, tests, or verification passes;
- ordinary task-field updates;
- worker claim/start events.

### 6.3 Finality and recheck

A watched Kanban card is notification-worthy as `blocked` only when its durable block classification explicitly requires human action, such as `needs_input`, `capability`, escalation to triage after exhausted retries, or an explicit human gate. A raw `blocked` status or `kanban_task_blocked` callback is insufficient because Hermes also uses blocked transitions for dependency waits, transient failures, review-ladder promotion, and other recoverable control-plane states.

The plugin should debounce a block candidate for a short bounded interval and then reread the card, its block classification, remaining retry or revision policy, parents, and current run. The delivery worker must recheck the same durable state immediately before sending. If the card was reactivated, reassigned for automatic continuation, promoted to another review rung, completed, or otherwise ceased to require human action, cancel the pending block event without notification. An alert already accepted by a destination cannot be retracted.

## 7. Hermes lifecycle integration

The implementation should use a standalone Hermes plugin and documented hooks.

### 7.1 Relevant hooks

- `post_llm_call`: captures only a bounded candidate response or summary. It is never success evidence by itself.
- `on_session_end`: canonical direct-turn terminal boundary; carries completion, failure, interruption, and exit-reason state.
- `on_session_reset`: marks the new session unarmed and triggers surface-specific predecessor cleanup using only identifiers the hook actually provides.
- `agent_loop_stopped`: records an interrupted in-flight gateway turn, including the running-agent `/new` fast path; it is supporting evidence and never a notification trigger by itself.
- `kanban_task_completed`: durable Kanban completion transition.
- `kanban_task_blocked`: durable Kanban block candidate that still requires the section 6 classification and recheck.

### 7.2 Session reset behavior

The implementation must treat reset payloads according to the current surface contract rather than assuming every hook supplies an old/new pair:

- The messaging gateway `/new` path supplies `old_session_id` and `new_session_id`; cancel the old armed record and create the new unarmed boundary atomically.
- Classic CLI and TUI/Desktop reset hooks may supply only the new `session_id`. They must never guess an old session from recency alone. The new session is marked unarmed immediately. Cleanup of the predecessor relies first on the preceding `on_session_end` or `agent_loop_stopped` evidence. If that evidence is missing, bounded reconciliation may cancel only a predecessor proven by durable session lineage or a surface-specific lane mapping captured when the watch was armed.
- If no supported signal proves which old session was replaced, leave unrelated watches untouched and classify the ambiguous armed record through the normal fail-closed recovery path; never infer completion.

User-requested `/new` or `/reset` does not transfer a watch. Automatic compression or an internal session-ID rotation is different: if durable parent/continuation lineage proves that the same logical turn continues, retain the campaign identifier and generation across that lineage; otherwise fail closed rather than guessing. No Hermes core hook change is required by this design.

### 7.3 Prohibited notification triggers

These events may be observed for diagnostics but must never directly notify the user:

- `post_tool_call`
- `agent:step`
- `on_stream_end`
- `on_interim_message`
- `subagent_stop`
- `agent_loop_stopped`
- `kanban_task_claimed`
- ordinary child-task completion

### 7.4 Hook behavior

Hook callbacks should perform only bounded local work:

1. validate the event;
2. determine whether its campaign is watched;
3. normalize the candidate outcome;
4. write or update a durable outbox row; and
5. return.

Hooks should not perform synchronous Telegram or macOS delivery.

## 8. Durable outbox

### 8.1 Storage

Use a small local SQLite database owned by the default Hermes profile or notification plugin. It should not be placed in the Hermes source checkout.

Suggested logical fields:

```text
event_id
campaign_id
generation
terminal_status
title
short_summary
task_id
session_id
created_at
cancelled_at
cancellation_reason
telegram_delivery_status
telegram_attempt_count
telegram_last_error
macos_delivery_status
macos_attempt_count
macos_last_error
```

Do not store full prompts, transcripts, raw tool output, credentials, or arbitrary environment data.

### 8.2 Deduplication

Use this logical uniqueness key:

```text
campaign_id + generation + terminal_status
```

Repeated callbacks for the same terminal transition update the same event rather than generating another outbox row. This prevents duplicates caused by repeated callbacks and ordinary worker restarts; it does not provide transactional exactly-once delivery across an external destination and SQLite.

A resumed campaign receives a new generation. This permits:

1. one blocked notification for generation N; and
2. one later completion notification for generation N+1.

### 8.3 Independent delivery state

Telegram and macOS delivery state must be tracked independently.

If Telegram fails after macOS succeeds:

- do not repeat the macOS notification;
- retain and retry only the Telegram delivery.

If the delivery worker restarts, it resumes pending events without intentionally retrying deliveries already recorded as successful. If a destination accepted a message but the worker crashed before recording success, the pending attempt may be delivered again. This narrow crash window is an explicit consequence of the at-least-once contract.

## 9. Delivery worker

Use a lightweight macOS LaunchAgent to drain the outbox. The worker performs no model inference.

Responsibilities:

- claim pending destination deliveries atomically with a bounded lease;
- deliver to each pending destination;
- record success or bounded failure details immediately after each attempt;
- retry transient failures with bounded backoff;
- avoid tight retry loops;
- retain failed events for operator inspection;
- never synthesize or expand notification content with an LLM.

The design should prefer one small worker over separate polling processes for Telegram and macOS.

The worker guarantees at-least-once attempts, not exactly-once external delivery. SQLite uniqueness, atomic claims, leases, and destination-specific success markers suppress known duplicates, but no adapter may claim that the external send and local success update are one transaction.

## 10. Telegram delivery

Use the supported `hermes send --to telegram` path rather than calling the Telegram Bot API directly. This reuses Hermes-managed credentials and does not require a running gateway.

Requirements:

- route to the configured Telegram DM or selected topic;
- keep Telegram notification behavior at `important`;
- send one concise message per terminal event;
- do not send tool progress, streaming chunks, or ordinary status callbacks as audible push notifications;
- reuse existing Hermes-managed credentials and channel routing;
- do not copy bot tokens into plugin configuration or logs.

Example completion:

```text
✅ Hermes campaign completed
Remove gstack from active environment

Removed active integrations and verified native replacements.
Task: t_abcd
```

Example block:

```text
⚠️ Hermes campaign needs attention
Remove gstack from active environment

Blocked: ambiguous user-authored state requires a preservation decision.
Task: t_abcd
```

## 11. macOS delivery

Initially use the built-in macOS notification surface through `osascript display notification`.

Requirements:

- no additional package for the first implementation;
- concise title and body;
- no transcript or sensitive content;
- delivery attempted by the local outbox worker;
- permissions and Focus-mode behavior documented during setup.

If `osascript` proves unreliable, replace only the macOS adapter with `terminal-notifier` or a minimal signed helper. Do not redesign the event or outbox model.

Hermes Desktop notifications must not be the sole local delivery mechanism because notifications received while the app is closed are not replayed when it reopens.

## 12. Notification content and privacy

A notification may contain:

- terminal status;
- campaign title;
- one-line summary or block reason;
- task or session identifier;
- a short instruction such as “Open Telegram to review.”

A notification must not contain:

- full prompts or responses;
- raw logs or stack traces;
- tool arguments or outputs;
- credentials, API keys, tokens, or connection strings;
- large diffs;
- unrelated paths or project details;
- every child-task outcome.

Summaries should be supplied by the terminal-state producer and bounded in length. The notifier must not use an LLM to summarize them.

## 13. Reliability and failure behavior

- A broken notification callback must not crash or block the agent.
- A delivery failure must not change campaign state.
- Outbox writes must be transactional.
- Event claiming must prevent concurrent duplicate delivery.
- Retries must be destination-specific and bounded.
- Permanent failures remain visible in local status/log output.
- A notifier restart must resume pending events.
- Delivery is at-least-once; the documented post-send/pre-commit crash window may duplicate an externally accepted notification.
- Recovery must never promote an ambiguous armed direct turn to `completed` without durable final-response evidence.
- Telegram unavailability must not prevent macOS delivery.
- macOS notification failure must not prevent Telegram delivery.
- The system should expose a read-only command for pending, delivered, and failed events.

## 14. Configuration

Keep configuration minimal and outside Hermes core. Suggested settings:

```yaml
enabled: true
telegram:
  enabled: true
  target: configured Hermes Telegram chat/thread
macos:
  enabled: true
watch:
  direct_turns: explicit_only
  kanban: root_or_finalizer_only
notify_on:
  completed: true
  blocked: true
  failed: true
  interrupted: true
  timed_out: true
  unknown: true
summary_max_chars: bounded value
delivery:
  max_attempts: bounded value
  retry_backoff: bounded sequence
  block_debounce: short bounded value
```

Do not add broad configuration until a real requirement appears.

## 15. Canonical control repository and deployment

`/Users/chanbla11mit/hermes-local-harness` is the canonical public-safe source for this feature. The approved specification is stored at `docs/specs/260921-hermes-terminal-outcome-notification.md`; the former Desktop draft is no longer canonical. The repository must own:

- standalone plugin source and tests;
- the delivery-worker source and tests;
- the LaunchAgent plist template, identifier, installation procedure, and rollback procedure;
- sanitized non-secret configuration schema and examples;
- the expected plugin deployment matrix for every active profile or process that can emit relevant session or Kanban hooks;
- roster, sanitized snapshot, and `scripts/verify-state` updates that treat the plugin as expected behavior rather than an unexpected plugin;
- manual deployment instructions using supported Hermes plugin/configuration commands and ordinary file installation.

The deployed copies under Hermes profile homes and `~/Library/LaunchAgents` are runtime state, not canonical source. No automatic apply script is required; deployment remains explicit and reviewable. The tracked repository must not contain Telegram chat or thread IDs, bot tokens, credentials, the runtime SQLite database, transcripts, logs, or raw private state.

Because Kanban completion and block hooks fire in the process that drives the transition, the event-producing plugin portion must be enabled in the default orchestrator profile and every active worker or reviewer profile that can complete or block a watched card. Direct-turn arming commands should be exposed only where direct orchestrator campaigns are supported. All producer instances write to the same permission-restricted SQLite outbox using concurrency-safe transactions.

Any implementation change requires independent `reviewer-sol` review before local integration. Enabling the plugin, installing or loading the LaunchAgent, changing live profile configuration, or sending test notifications are deployment/external effects and require their own explicit authorization.

The reviewed local v0.2.0 candidate pin is `a627cdd9ed2d8d7c2db268cad02c819154ef6b1c`; publication and profile installation remain separate authorized actions.

## 16. Implementation sequence

### Phase 0: control-repository integration

- Add the approved specification to the control repository at the canonical path named in section 15.
- Add plugin, worker, plist template, tests, sanitized configuration, deployment matrix, and rollback documentation there first.
- Extend the verifier and its fixtures to understand the proposed deployment matrix, but do not declare the plugin required in the live roster or snapshot before deployment is authorized.
- Verify the control repository remains public-safe and `scripts/verify-state` passes against the still-unmodified live harness.

### Phase 1: terminal event and macOS proof

- Create the standalone plugin.
- Add explicit one-shot direct-campaign arming.
- Capture `post_llm_call`, `on_session_end`, `on_session_reset`, and `agent_loop_stopped` with their distinct evidence roles and current surface-specific payloads.
- Add structured `completed`/`blocked` outcome recording.
- Add fail-closed `unknown` recovery for armed turns without durable final-response evidence.
- Implement gateway old/new atomic cancellation, new-only CLI/TUI reset handling, bounded lineage reconciliation, and continuation-lineage handling without guessing predecessor sessions.
- Create the durable outbox.
- Deliver a native macOS notification.
- Verify no notification occurs for tools or subagents.

### Phase 2: Telegram

- Route through `hermes send --to telegram`; do not require a running gateway or call the Bot API directly.
- Configure the exact chat and optional thread.
- Keep Telegram notifications at `important`.
- Test destination-specific retry and deduplication.

### Phase 3: Kanban

- Register completion and blocked lifecycle hooks.
- Watch only designated root/finalizer cards.
- Treat blocked callbacks as candidates; debounce and reread durable task state before classification and again before delivery.
- Suppress dependency and automatically recoverable blocks.
- Verify many child transitions produce one campaign-level terminal alert.

### Phase 4: failure and recovery testing

- Exercise duplicate callbacks.
- Restart the delivery worker with pending events.
- Exercise the post-send/pre-success-commit crash window and document that the at-least-once contract may duplicate that attempt.
- Temporarily break Telegram delivery.
- Temporarily deny or disable macOS notification delivery.
- Verify channel independence and bounded retries.
- Resume a blocked campaign and verify a later completion can notify once.

### Phase 5: authorized live deployment

- Obtain explicit deployment and test-notification authorization.
- Update the control repository's roster and sanitized snapshot to declare the reviewed plugin deployment matrix.
- Deploy the exact reviewed plugin to every declared producer profile using supported Hermes commands, install and load the reviewed LaunchAgent template, and set the private destination only in live configuration.
- Run the approved macOS and Telegram test notifications.
- Run `scripts/verify-state` and confirm desired and observed state match.

## 17. Acceptance tests

The implementation is accepted only when real execution verifies all of the following:

1. An ordinary tool call produces no alert.
2. A streamed or interim assistant message produces no alert.
3. A subagent completion produces no alert.
4. A child Kanban task completion produces no alert when only the root is watched.
5. A normal reviewer revision produces no alert.
6. A dependency wait with automatic resume produces no alert.
7. Outside the documented post-send/pre-commit crash window, a watched direct campaign completion produces one Telegram and one macOS notification.
8. Outside that same crash window, a watched Kanban campaign completion produces one Telegram and one macOS notification.
9. A stable, explicitly human-relevant block produces one notification on each destination; a transient or automatically recoverable block produces none.
10. A duplicate lifecycle callback reuses the same outbox event and does not cause another normal delivery attempt.
11. Telegram failure does not duplicate the successful macOS notification.
12. macOS failure does not duplicate the successful Telegram notification.
13. A pending event with no externally accepted attempt survives delivery-worker restart without duplicating another destination's confirmed success.
14. A blocked campaign can resume and later produce a distinct completion event in a new generation.
15. No notification or local log exposes secrets or raw transcript content.
16. Notification generation and retry consume zero model calls.
17. A crash after external acceptance but before the local success commit is documented and tested as a possible duplicate under the at-least-once contract.
18. An armed direct turn without durable final-response evidence becomes `unknown` or a more specific runtime outcome, never `completed`.
19. Gateway `/new` atomically cancels the identified old watch and leaves the new session unarmed; CLI and TUI/Desktop new-only reset payloads leave the new session unarmed and cancel only a predecessor proven by end/stop evidence, durable lineage, or the captured surface lane. Unrelated watches are untouched, and no ambiguous record becomes `completed`.
20. A block candidate that resumes or advances automatically before delivery is cancelled without notification.
21. The control-repository verifier accepts the declared deployment matrix and still rejects an undeclared enabled plugin.

## 18. Operational checks

The final implementation report should include:

- plugin location and provenance;
- LaunchAgent identifier and status;
- outbox path and permissions;
- Telegram destination configuration without exposing credentials;
- macOS notification permission status;
- exact test events and observed deliveries;
- proof that intermediate tool and child events were suppressed;
- retry and deduplication evidence;
- the observed at-least-once duplicate window and its operator-facing documentation;
- control-repository paths, deployment matrix, sanitized verifier changes, and proof that no secret or runtime database is tracked;
- uninstall and rollback steps.

## 19. Rollback

Rollback should be simple and complete:

1. disable and unload the LaunchAgent;
2. disable or remove the standalone plugin from every profile in the deployment matrix;
3. remove notification-specific profile instructions or commands;
4. retain or archive the outbox for inspection if desired;
5. update the control repository's roster, snapshot, and verifier expectations through a reviewed rollback commit;
6. verify normal Hermes CLI, TUI, gateway, and Kanban behavior without the plugin.

No rollback step should require reverting Hermes core.

## 20. Recommended decision

Implement a standalone Hermes plugin plus a small SQLite outbox and one macOS LaunchAgent. Explicitly arm direct CLI/TUI campaigns and automatically watch only designated root/finalizer Kanban tasks. Require structured terminal outcomes rather than guessing from prose.

This design provides durable at-least-once dual delivery with best-effort duplicate suppression while avoiding tool-call noise, token-consuming polling, and Hermes-core modifications. It explicitly documents the narrow external-send crash window rather than promising impossible exactly-once delivery.

## 21. References

- Hermes Event Hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Hermes Kanban: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Hermes Telegram integration: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram
