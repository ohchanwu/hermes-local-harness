# Hermes terminal outcome notification plugin

Arming is deterministic: the `arm_campaign` TOOL binds the watch to the session ID the HOST
supplies at tool dispatch (`tools/registry.dispatch → handler(args, session_id=…)`), so the watch
always binds exactly the session that asked; concurrent gateway/TUI sessions can never claim each
other's arms. Plugin slash handlers receive only raw text on every surface (CLI `cli.py`,
gateway `run_inbound.py`, TUI `methods_tools.py`), so `/notify-on-terminal` fails closed with a
pointer to the tool — it never guesses a session. `campaign_terminal` records the `completed` or
`blocked` proposal; `on_session_end` is the only direct notification boundary; `post_llm_call` is
candidate-only. `pre_llm_call` refreshes activity and follows durable `parent_session_id`
continuation lineage across compression rotations (it supplies `platform`, never `session_key`,
so the lane column stays reserved for real session-key identity). `agent_loop_stopped` supplies
only `session_key`; the plugin resolves it to live session ids through Hermes's own durable
routing table (`state.db` `sessions.session_key`, inherited across compression forks — read-only,
override with `HERMES_TERMINAL_STATE_DB`), so interrupted gateway turns recover as `interrupted`
from evidence, and every resolution failure fails closed to `unknown`.

`watch_terminal_task` (tool or `/watch-terminal-task TASK_ID [title]`) explicitly watches one root
or finalizer card. Re-arming a direct turn always mints a fresh campaign (generation increments),
so two consecutive armed turns in one session each deliver their own notification. A watched
task whose board row is gone reports `missing` and the candidate is cancelled — never sent.
`kanban_task_claimed` bumps the campaign generation; `kanban_task_blocked`
records the firing `run_id` as durable evidence. The worker rechecks both — plus block
classification, recurrences, and current/max run — immediately before every destination send, so
an old-generation or stale-run block candidate can never alert. Board-unavailable reads are
retained with bounded, separately-counted recheck retries (never consuming send attempts), then
escalate to a visible `failed` row. A stranded armed direct turn (crash/hard kill, no
`on_session_end`) is recovered by the worker's per-cycle scan as `interrupted` (with stop
evidence) or fail-closed `unknown` — never `completed`.

An automatic Astra terminal retry is not a human block. Before the ordinary blocker heuristics,
the worker recognizes only an exact JSON `RETRY_TERMINAL` verdict fenced to the current run with
`strategy`, `rung: astra`, `ladder_version: glm-review-v2`, `authorization_mode: autonomous`,
and `terminal_retry_policy: astra-until-approve-v1`. Malformed, stale, v1, side-by-side, or prose
markers fail closed to ordinary human-block classification; a valid retry cancels the pending
candidate and the next claimed run advances the notification generation.

Producers and the LaunchAgent must use the same absolute `HERMES_TERMINAL_OUTBOX` path. The worker
also needs `HERMES_KANBAN_DB` (or `--kanban-db`) to recheck human-relevant block finality. Its
SQLite file is mode 0600 and parent directory mode 0700.

Run manually only after approved deployment:

    HERMES_TERMINAL_OUTBOX=/absolute/private/outbox.sqlite3 HERMES_KANBAN_DB=/absolute/private/kanban.db python worker.py --db "$HERMES_TERMINAL_OUTBOX"

The worker uses `hermes send --to telegram` and a safely quoted `osascript display notification`,
with independent destination retries and terminal `failed` status after bounded attempts. The
at-least-once contract permits one duplicate only if a destination accepts a message and the
process crashes before recording success.

No private target, token, transcript, or runtime database belongs in this repository.

The reviewed local candidate pin for this release is `b0fba955e274465f811123fc5611d2395775b5b0`.
Publishing or installing that candidate remains separately authorization-gated.
