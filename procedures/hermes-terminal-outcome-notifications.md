# Hermes terminal outcome notifications: deployment and rollback

Deployment is separately approval-gated. This matrix is authorized desired state, not proof that runtime rollout happened: `./scripts/verify-state --fixture tests/fixtures/clean.yaml` is the deployed shape; `terminal-deployment-pending.yaml` and `terminal-notification-rollback.yaml` must stay red.

After approval, replace these two placeholders only in the operator's private shell/runtime environment, never in this repository: `__ABSOLUTE_SHARED_OUTBOX__` is one absolute SQLite path outside every profile home, and `__ABSOLUTE_HERMES_KANBAN_DB__` is the one canonical absolute Kanban database path. Use the same values for all eleven producers and the worker. The approved source is `https://github.com/ohchanwu/hermes-local-harness.git#plugins/hermes-terminal-outcome-notification` at `5914ec8519ee5209c1cfb6cde06dce5e46186fb1` (version `0.2.0`).

Run this exact sequence from `/Users/chanbla11mit/hermes-local-harness` after approval. It fails before installation for placeholders or relative paths, stores only the two private values in a mode-0600 file, gives the outbox parent mode 0700, restarts the multiplexed producer gateway after its environment is set, and renders then loads the worker.

    set -eu
    ROOT=/Users/chanbla11mit/hermes-local-harness
    PRIVATE_ENV="$HOME/.hermes/terminal-outcome-notification.env"
    HERMES_TERMINAL_OUTBOX=__ABSOLUTE_SHARED_OUTBOX__
    HERMES_KANBAN_DB=__ABSOLUTE_HERMES_KANBAN_DB__
    case "$HERMES_TERMINAL_OUTBOX:$HERMES_KANBAN_DB" in /*:/*) ;; *) printf '%s\n' 'absolute outbox and Kanban DB paths are required' >&2; exit 1;; esac
    case "$HERMES_TERMINAL_OUTBOX:$HERMES_KANBAN_DB" in *__ABSOLUTE_*__) printf '%s\n' 'replace both private placeholders' >&2; exit 1;; esac
    install -d -m 700 "$(dirname "$PRIVATE_ENV")" "$(dirname "$HERMES_TERMINAL_OUTBOX")"
    (umask 077; printf 'export HERMES_TERMINAL_OUTBOX=%q\nexport HERMES_KANBAN_DB=%q\n' "$HERMES_TERMINAL_OUTBOX" "$HERMES_KANBAN_DB" > "$PRIVATE_ENV")
    chmod 600 "$PRIVATE_ENV"
    . "$PRIVATE_ENV"
    launchctl setenv HERMES_TERMINAL_OUTBOX "$HERMES_TERMINAL_OUTBOX"
    launchctl setenv HERMES_KANBAN_DB "$HERMES_KANBAN_DB"
    for profile in default reviewer-sol worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2 worker-terra-1 worker-glm-full worker-sol worker-astra; do
      hermes -p "$profile" plugins install https://github.com/ohchanwu/hermes-local-harness.git#plugins/hermes-terminal-outcome-notification --ref 5914ec8519ee5209c1cfb6cde06dce5e46186fb1 --enable
      hermes -p "$profile" plugins list --plain --no-bundled
    done
    hermes plugins validate "$ROOT/plugins/hermes-terminal-outcome-notification" --json
    hermes gateway restart
    PLIST="$HOME/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist"
    HERMES_EXE="$(command -v hermes)"
    [ "${HERMES_EXE#/}" != "$HERMES_EXE" ] || { printf '%s\n' 'absolute Hermes executable path is required' >&2; exit 1; }
    HERMES_WORKER_PATH="$(dirname "$HERMES_EXE"):/usr/bin:/bin:/usr/sbin:/sbin"
    cp "$ROOT/deployment/com.nous.hermes-terminal-outcome-notification.plist.template" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 $(command -v python3)" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :ProgramArguments:1 $ROOT/plugins/hermes-terminal-outcome-notification/worker.py" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :ProgramArguments:3 $HERMES_TERMINAL_OUTBOX" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :ProgramArguments:5 $HERMES_KANBAN_DB" "$PLIST"
    plutil -replace EnvironmentVariables.HERMES_TERMINAL_OUTBOX -string "$HERMES_TERMINAL_OUTBOX" "$PLIST"
    plutil -replace EnvironmentVariables.HERMES_KANBAN_DB -string "$HERMES_KANBAN_DB" "$PLIST"
    plutil -insert EnvironmentVariables.PATH -string "$HERMES_WORKER_PATH" "$PLIST"
    plutil -lint "$PLIST"
    if launchctl print "gui/$(id -u)/com.nous.hermes-terminal-outcome-notification" >/dev/null 2>&1; then launchctl bootout "gui/$(id -u)" "$PLIST"; fi
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    ./scripts/verify-state

The `launchctl` environment applies to the currently logged-in user domain; after a login, source the private file, repeat the two `launchctl setenv` commands, then run `hermes gateway restart` before using producers. Configure the private Telegram route only in live Hermes configuration; never add it here. The verifier stays red until every plugin is enabled, the running multiplex gateway itself has inherited `HERMES_TERMINAL_OUTBOX`/`HERMES_KANBAN_DB` (verified from the live gateway process environment, so skipping `hermes gateway restart` stays red), and the loaded LaunchAgent's effective `--db`/`--kanban-db` arguments and environment match the same shared paths (verified from `launchctl print`, so re-rendering the plist without `bootout`/`bootstrap` stays red).

Use `/watch-terminal-task ROOT_OR_FINALIZER_ID [title]` only on the campaign root or finalizer. `/notify-on-terminal [title]` arms exactly the next direct turn; Hermes binds it at the context-bearing `pre_llm_call` boundary. Confirm macOS notification permission and Focus behavior manually. Run the worker only after explicit notification-test authorization. The worker may duplicate one destination after a crash between external acceptance and the SQLite success update; inspect the 0600 outbox in its 0700 parent directory locally.

Rollback: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nous.hermes-terminal-outcome-notification.plist`, remove the plist, disable/remove the plugin from each deployed producer profile, then retain or archive the private outbox. `./scripts/verify-state` must become red until a separate reviewed rollback commit updates the roster, snapshot, matrix, and verifier expectation.
