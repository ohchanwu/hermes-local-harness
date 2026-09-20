# Manual apply

1. Before a significant change, create a private recovery snapshot outside this repository and record `git -C ~/.hermes/hermes-agent rev-parse HEAD`.
2. Review `git diff -- roster.yaml policies/ skills/` and display only non-secret fields with `scripts/verify-state`.
3. Apply named non-secret settings with supported commands, for example `hermes config set kanban.max_in_progress_per_profile 1`. Keep `kanban.max_in_progress` unset with `hermes config unset kanban.max_in_progress` when explicitly authorized.
4. For the shared skill, manually copy the reviewed tracked files to the documented deployed skill location only after explicit authorization; never symlink it.
5. Run `scripts/verify-state`, commit the desired-state change, and retain the recovery snapshot outside Git.

Do not use this procedure for credentials. Do not remove unexpected state merely because verification reports it.
