# Hermes terminal outcome notification plugin

`campaign_terminal` records a `completed` or `blocked` proposal for a one-shot direct watch armed by `/notify-on-terminal`. It does not send from a hook. `on_session_end` is the only direct notification boundary; `post_llm_call` is candidate-only.

The shared SQLite database belongs under `$HERMES_HOME/terminal-outcome-notifications/outbox.sqlite3` (mode 0600). The worker uses `hermes send --to telegram` and `osascript`, with destination state tracked independently. Its at-least-once contract permits a duplicate only if a destination accepted a message and the process crashed before recording success.

Run manually after approved deployment:

    python worker.py --db "$HERMES_HOME/terminal-outcome-notifications/outbox.sqlite3"

No private target, token, transcript, or runtime database belongs in this repository.
