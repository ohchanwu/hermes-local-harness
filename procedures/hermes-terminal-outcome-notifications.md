# Hermes terminal outcome notifications: deployment and rollback

Deployment is separately approval-gated. This matrix is authorized desired state, not proof that runtime rollout happened: `./scripts/verify-state --fixture tests/fixtures/clean.yaml` is the deployed shape; `terminal-deployment-pending.yaml` and `terminal-notification-rollback.yaml` must stay red.

After approval, replace these two placeholders only in the operator's private shell/runtime environment, never in this repository: `__ABSOLUTE_SHARED_OUTBOX__` is one absolute SQLite path outside every profile home, and `__ABSOLUTE_HERMES_KANBAN_DB__` is the one canonical absolute Kanban database path. Use the same values for all eleven producers and the worker. The approved source is `https://github.com/ohchanwu/hermes-local-harness.git#plugins/hermes-terminal-outcome-notification` at `7d38611e132bec178d1cbe89676adebf178fd4ad` (version `0.1.0`).

    export HERMES_TERMINAL_OUTBOX=__ABSOLUTE_SHARED_OUTBOX__
    export HERMES_KANBAN_DB=__ABSOLUTE_HERMES_KANBAN_DB__
    export HERMES_TERMINAL_PLUGIN_SOURCE=https://github.com/ohchanwu/hermes-local-harness.git#plugins/hermes-terminal-outcome-notification
    export HERMES_TERMINAL_PLUGIN_COMMIT=7d38611e132bec178d1cbe89676adebf178fd4ad
    for profile in default reviewer-sol worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2 worker-terra-1 worker-glm-full worker-sol worker-astra; do
      hermes -p "$profile" plugins install "$HERMES_TERMINAL_PLUGIN_SOURCE" --ref "$HERMES_TERMINAL_PLUGIN_COMMIT" --enable
      hermes -p "$profile" plugins list --plain --no-bundled
    done
    hermes plugins validate /Users/chanbla11mit/hermes-local-harness/plugins/hermes-terminal-outcome-notification --json

Put the same two exports in each producer's approved private runtime environment before restarting that producer; shell exports alone do not retrofit an already-running gateway. Create the private outbox parent as mode `0700`, then use the plist template with the same two absolute values (and the real Python/worker paths) at `~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`; only then run `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`. Configure the private Telegram route only in live Hermes configuration; never add it here. Run `./scripts/verify-state` only after every producer is restarted with its private environment and the worker is loaded; it must remain red during partial rollout.

Use `/watch-terminal-task ROOT_OR_FINALIZER_ID [title]` only on the campaign root or finalizer. `/notify-on-terminal [title]` arms exactly the next direct turn; Hermes binds it at the context-bearing `pre_llm_call` boundary. Confirm macOS notification permission and Focus behavior manually. Run the worker only after explicit notification-test authorization. The worker may duplicate one destination after a crash between external acceptance and the SQLite success update; inspect the 0600 outbox in its 0700 parent directory locally.

Rollback: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`, remove the plist, disable/remove the plugin from each deployed producer profile, then retain or archive the private outbox. `./scripts/verify-state` must become red until a separate reviewed rollback commit updates the roster, snapshot, matrix, and verifier expectation.
