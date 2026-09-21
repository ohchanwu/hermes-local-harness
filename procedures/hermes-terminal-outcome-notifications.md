# Hermes terminal outcome notifications: deployment and rollback

Deployment is separately approval-gated. Before enabling, pin the reviewed plugin source, copy it to every producer profile in `deployment/hermes-terminal-outcome-notification.example.yaml`, enable it with `hermes -p PROFILE plugins enable hermes-terminal-outcome-notification`, substitute local absolute paths in the plist template, and load it with `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`. Configure the private Telegram route only in live Hermes configuration; never add it here.

Confirm macOS notification permission and Focus behavior manually. Run the worker only after explicit notification-test authorization. The worker may duplicate one destination after a crash between external acceptance and the SQLite success update; inspect the 0600 outbox locally.

Rollback: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`, remove the plist, disable/remove the plugin from each deployed producer profile, then retain or archive the private outbox. Update the roster/snapshot only in a separate reviewed deployment or rollback change.
