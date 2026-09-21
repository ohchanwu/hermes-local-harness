# Hermes terminal outcome notification plugin

`/notify-on-terminal [title]` writes one pending explicit arm. The next `pre_llm_call` binds it to Hermes's actual opaque session ID; slash handlers never guess an ID. `campaign_terminal` records the `completed` or `blocked` proposal, and `on_session_end` is the only direct notification boundary. `post_llm_call` is candidate-only.

`/watch-terminal-task TASK_ID [title]` explicitly watches one root or finalizer card. Producers and the LaunchAgent must use the same absolute `HERMES_TERMINAL_OUTBOX` path. The worker also needs `HERMES_KANBAN_DB` (or `--kanban-db`) to recheck human-relevant block finality. Its SQLite file is mode 0600 and parent directory mode 0700.

Run manually only after approved deployment:

    HERMES_TERMINAL_OUTBOX=/absolute/private/outbox.sqlite3 HERMES_KANBAN_DB=/absolute/private/kanban.db python worker.py --db "$HERMES_TERMINAL_OUTBOX"

The worker uses `hermes send --to telegram` and a safely quoted `osascript display notification`, with independent destination retries and terminal `failed` status after bounded attempts. The at-least-once contract permits one duplicate only if a destination accepts a message and the process crashes before recording success.

No private target, token, transcript, or runtime database belongs in this repository.
