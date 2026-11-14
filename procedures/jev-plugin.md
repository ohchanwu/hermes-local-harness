# jev plugin: install, settings, peak-hours hold, logs and rollback

The `jev` plugin (`/Users/chanbla11mit/hermes-local-harness/plugins/jev`, version 0.1.0) calls Jev, the decision model from TypeSafe, for two decisions, and writes logs that show whether it reduces Claude subscription token use:

- Card model routing: when an orchestrator creates a card with `kanban_create`, the plugin asks Jev whether the work is `easy`, `medium` or `hard`, and moves `easy` and `medium` cards to the board's GLM worker profiles, except every tenth such card of a board and route, which stays with the Claude worker as a control group.
- Reassignment after change requests: when a reviewer requests changes on a card of a GLM worker for the fifth time, the plugin moves the card to a Claude worker of the board.
- Tool result filter: when `terminal`, `execute_code`, `search_files` or `browser_exec` returns a large result, the plugin keeps only the parts Jev marks as needed and saves the full result to a file.
- GLM peak-hours hold: no GLM card starts on Monday to Friday from 15:00 to 19:00 Asia/Seoul time.
- Logs of the routing decisions, the tool result filter and every auxiliary model call.

The plugin uses only the Hermes plugin interface (`register_middleware`, `register_hook`) and the Python standard library. It never changes the installed Hermes checkout `/Users/chanbla11mit/.hermes/hermes-agent`.

## Install on a profile

The live installation, the gateway restart and the LaunchAgent belong to the deployment card and need the owner's authorization. Install the plugin the same way as `hermes-terminal-outcome-notification` (see `procedures/hermes-terminal-outcome-notifications.md`), from the reviewed commit. The source depends on whether the reviewed commit is pushed:

- While the reviewed commit exists only in the local repository (not pushed), install from the local repository. Hermes (`hermes_cli/plugins_cmd.py`, `_resolve_git_url`) accepts a `file://` URL with a `#plugins/jev` fragment and prints only a warning about the local URL scheme:

        hermes -p <profile> plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref <reviewed commit> --enable

- After the reviewed commit is pushed, install from GitHub:

        hermes -p <profile> plugins install https://github.com/ohchanwu/hermes-local-harness.git#plugins/jev --ref <reviewed commit> --enable

Then, for either source:

    hermes -p <profile> plugins list --plain --no-bundled
    hermes plugins validate /Users/chanbla11mit/hermes-local-harness/plugins/jev

`plugins list` prints `enabled      git pinned@<first 8 characters of the commit> 0.1.0    jev`, and `plugins/.install-metadata.json` in the profile records the source URL and the full commit. Card `t_f9262e33` installed commit `921f85b2d8987e0631b958a0026b30fa4609b40e` from the local `file://` source on all 31 profiles. Card `t_7e73d1b4` installed commit `0db3667ba3ee03fdc174b525f0c4abd34e08492d` from the same local `file://` source on the same 31 profiles on 2026-11-13. Card `t_806e0815` installed commit `485ca3e840ddc34860ee6668de2799035f4372e8` from the same local `file://` source on all 36 profiles on 2026-11-14. Each install also makes the running gateway reload its plugins (the command prints `Gateway reloaded plugins`); this is not a gateway restart, but it does load changed plugin Python files: `hermes plugins install ... --enable` calls `activate_plugin_now` (Hermes source `hermes_cli/plugins_activation.py` lines 96 to 127), which asks the gateway that serves the profile to run its `reload-plugins` command (`gateway/run_plugin_rewire.py` lines 81 to 118). That command runs `discover_plugins(force=True)`, which first removes every registration of the profile's plugins (`hermes_cli/plugins.py` lines 1366 to 1367) and then imports each directory plugin again after it has removed `hermes_plugins.<plugin>` and all of its submodules from `sys.modules` (`hermes_cli/plugins_loader.py` lines 687 to 708). The `tool_execution` middleware and the hooks of the new code are therefore active in gateway-served sessions from the next tool call, without `hermes gateway restart`. Only plugin tools and system prompt sections wait for the next session, and the `jev` plugin has neither. When the install command prints `Restart the gateway for the plugin to take effect` instead, no gateway answered, and the owner runs `hermes gateway restart` from a separate shell.

Plugins load only when they are listed in the profile's `plugins.enabled` (Hermes source `hermes_cli/plugins.py` line 1481), which `--enable` does.

Profiles (36 in total; `roster.yaml` lists `jev` in `required_plugins` of exactly these, and `scripts/verify-state` checks that list):

- The 21 Claude subscription profiles: `advisor`, and the orchestrator, reviewer and two Claude workers of each of the five boards (`jobcron-orchestrator`, `jobcron-reviewer`, `jobcron-worker`, `jobcron-worker-2`, `chapt-orchestrator`, `chapt-reviewer`, `chapt-worker`, `chapt-worker-2`, `harness-orchestrator`, `harness-reviewer`, `harness-worker`, `harness-worker-2`, `jss-orchestrator`, `jss-reviewer`, `jss-worker`, `jss-worker-2`, `anki-orchestrator`, `anki-reviewer`, `anki-worker`, `anki-worker-2`). Routing has an effect in every profile that calls `kanban_create`: the orchestrators, and also workers and reviewers that create follow-up cards (see "Creating the third GLM worker profile of each board"). The `kanban_unblock` part of the peak-hours hold has an effect only in the orchestrators, because Hermes refuses `kanban_unblock` in a run that the dispatcher started (`_require_orchestrator_tool` in `/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`). The auxiliary log and the tool result filter apply in every profile.
- The fifteen GLM worker profiles that the routes use, three for each board: `jobcron-worker-glm-1`, `jobcron-worker-glm-2`, `jobcron-worker-glm-3`, `chapt-worker-glm-1`, `chapt-worker-glm-2`, `chapt-worker-glm-3`, `harness-worker-glm-1`, `harness-worker-glm-2`, `harness-worker-glm-3`, `jss-worker-glm-1`, `jss-worker-glm-2`, `jss-worker-glm-3`, `anki-worker-glm-1`, `anki-worker-glm-2`, `anki-worker-glm-3`. The plugin must run in these profiles so that the card's model override is cleared at the review handoff (see "Model override at the review handoff"). Card `t_55432326` created the five profiles whose names end in `-glm-3` on 2026-11-14 (steps 1 to 5 of "Creating the third GLM worker profile of each board"). The owner added their Z.ai logins on 2026-11-14 (step 6), and the controller's one model call on each of the five profiles returned `READY`. Card `t_806e0815` installed commit `485ca3e840ddc34860ee6668de2799035f4372e8` on all 36 profiles on 2026-11-14 in the order of step 7; the install on the last profile, `harness-orchestrator`, ended at 11:37:18 Asia/Seoul time (UTC+09:00). In the final check (step 8), `scripts/verify-state` printed none of the lines that step 8 lists for the five profiles.

Gateway-served sessions load the installed plugin code when the install command prints `Gateway reloaded plugins` (see above); otherwise after the owner runs `hermes gateway restart` from a separate shell. Workers and reviewers started by the dispatcher load it when they start (`hermes -p <profile> --cli ... chat -q`), because each run is a new process.

## Creating the Anki GLM worker profiles

Card `t_71b4ef4a` added `anki-worker-glm-1` and `anki-worker-glm-2` to `roster.yaml`, `plugins/jev/config.json` and the policy sources only. The deployment card creates the two profiles with the owner's authorization. Until then `scripts/verify-state` reports both profiles as missing. For each `<profile>` of `anki-worker-glm-1` and `anki-worker-glm-2`:

1. Clone the Anki Claude worker:

        hermes profile create <profile> --clone-from anki-worker

   The clone copies these files and directories of `anki-worker` (Hermes source `hermes_cli/profiles.py`, `_CLONE_CONFIG_FILES`, `_CLONE_SUBDIR_FILES` and `_clone_plugins`, called from `_bootstrap_profile_dir`):
   - `config.yaml`, including the Anthropic API fallback of `anki-worker`: `fallback_providers` `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` and a `fallback_chain` on all sixteen helper tasks;
   - `.env`, which contains `ANTHROPIC_API_KEY` (written to `anki-worker` by `procedures/anthropic-api-fallback.md`, section 8);
   - `SOUL.md` and the installed skills;
   - `memories/MEMORY.md` and `memories/USER.md`;
   - the `plugins/` directory, with `ponytail` and `hermes-terminal-outcome-notification` (both installed and disabled on `anki-worker`), and `jev` if it is installed on `anki-worker` at that time.

   The clone copies no `auth.json`. The GLM worker profiles have no Anthropic API fallback (`procedures/anthropic-api-fallback.md`, section 1, limits it to the four Jobcron profiles and the claude-subscription profiles listed in section 8), so steps 2 to 4 remove the copied key, the copied memory files, the two copied plugins and the copied fallback values.
2. The owner removes the copied Anthropic API key from the profile's `.env`, before any other step:

        hermes -p <profile> config unset ANTHROPIC_API_KEY

   The command prints `✓ Unset ANTHROPIC_API_KEY from <path of the profile .env>` and no key value (`procedures/anthropic-api-fallback.md`, section 7, step 3). Then `hermes -p <profile> auth list anthropic` must list no entry with source `env:ANTHROPIC_API_KEY`. Nobody else opens or changes the profile's `.env`.
3. Delete the two copied memory files, as `procedures/manual-apply.md` requires for a cloned profile, and remove the two copied plugins, because the roster entry declares `installed_disabled_plugins` `[]`:

        rm /Users/chanbla11mit/.hermes/profiles/<profile>/memories/MEMORY.md /Users/chanbla11mit/.hermes/profiles/<profile>/memories/USER.md
        hermes -p <profile> plugins remove ponytail
        hermes -p <profile> plugins remove hermes-terminal-outcome-notification

   Without the plugin removal, `scripts/verify-state` prints `WARN: dormant unexpected plugin <profile>: ponytail` and the same line for `hermes-terminal-outcome-notification`.
4. Set the model and provider and clear the copied fallback values: model `glm-5.3`, provider `zai`, base URL `https://api.z.ai/api/coding/paas/v4`, the helper tasks on the same target, `fallback_providers` and every `auxiliary.<task>.fallback_chain` set to `[]`, and the profile in `kanban.dispatch_profiles`. The switch script does all of this in one command after it backs up the profile's `config.yaml` (preview first with `--dry-run`):

        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch add --clear-fallbacks

   Without `--clear-fallbacks` the switch script writes no fallback key: the profile keeps the Anthropic API fallback of `anki-worker`, and `scripts/verify-state` reports 17 `fallback drift` lines for the profile. Then `hermes -p <profile> config get --json fallback_providers` must print `[]`.
5. Replace the cloned SOUL with the tracked source `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md`, copied to `/Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md`.
6. Install and enable the `jev` plugin on the profile as described in "Install on a profile". If the clone already carries `jev`, check with `hermes -p <profile> plugins list --plain --no-bundled` that it is enabled and installed from the reviewed commit instead of installing it again.
7. The owner adds the Z.ai login, because a cloned profile has no `auth.json`:

        hermes -p <profile> auth add zai

   Nobody else runs this command or handles the key.
8. Run `python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state`. The expected result is no `missing profile`, `fallback drift` or `dormant unexpected plugin` line for the profile.

`jss-worker-glm-1` and `jss-worker-glm-2` exist, run `glm-5.3` on provider `zai` and have no `auth.json` either. They need the same owner step 7 (`hermes -p jss-worker-glm-1 auth add zai` and `hermes -p jss-worker-glm-2 auth add zai`), their SOULs from `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-1/SOUL.md` and `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-2/SOUL.md`, the `jev` plugin, and an entry in `kanban.dispatch_profiles`. A GLM worker without a Z.ai login fails its run when the dispatcher starts it, so add the login before the board's routes take effect.

## Creating the third GLM worker profile of each board

Card `t_f4ce916d` (owner request of 2026-11-14: one more GLM worker for every board, the same as the existing GLM workers, routed by the `jev` plugin to `glm-5.3-flash` or `glm-5.3`) added `harness-worker-glm-3`, `chapt-worker-glm-3`, `jobcron-worker-glm-3`, `jss-worker-glm-3` and `anki-worker-glm-3` to `roster.yaml`, `scripts/verify-state`, `snapshots/sanitized-current-state.yaml`, `plugins/jev/config.json` and the policy sources only. Card `t_55432326` created the five profiles on 2026-11-14 with the owner's authorization: it did steps 1 to 5 below for each of the five profiles and deployed the fifteen SOUL and skill files that card `t_f4ce916d` changed (the five reviewer SOULs, the five orchestrator SOULs and the five orchestrator skills; see step 8). The SOUL of `jobcron-worker-glm-3` that card `t_55432326` wrote in step 3 has SHA-256 `0b9da3f4f22618cbb61021a83529188ad2eb0cf940c62ea6be2d68f9da0e0efb`. The owner added the Z.ai login of each of the five profiles on 2026-11-14 (step 6), and the controller's one model call on each of the five profiles (`hermes -p <profile> chat -q "Reply with exactly READY. Do not call any tools." --oneshot -Q`) exited with code 0 and returned `READY`. Card `t_806e0815` installed commit `485ca3e840ddc34860ee6668de2799035f4372e8` from the local `file://` source on all 36 profiles on 2026-11-14 in the order of step 7: first the five new profiles and the five reviewers (installs ended from 11:32:54 to 11:34:41 Asia/Seoul time, UTC+09:00), then the other 26 profiles with the five orchestrators last; the install on the last profile, `harness-orchestrator`, ended at 11:37:18. After every install the profile's `plugins/.install-metadata.json` recorded that commit with `pinned` true, `plugins list` printed `jev` as `enabled`, and the installed tracked files were equal to `plugins/jev` of that commit; no install output named a plugin scan verdict `caution` or `dangerous`. Afterwards the installed `config.json` had the same SHA-256 on all 36 profiles and named three GLM workers for each of the five boards. In the final check (step 8), card `t_806e0815` ran `python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state` before the first install and after the last install: the two outputs were equal, neither contained any of the lines that step 8 lists for the five new profiles, nor `FAIL: profile SOUL drift` or `FAIL: profile-local skill override drift`, and the only `FAIL` lines in both were the seven lines that `HERMES_KANBAN_DB` in the process environment of a worker started by the dispatcher causes (one `multi-board gateway is still pinned to one database` line and six `unable to read open ... card list` lines).

Each new profile is a copy of the first GLM worker of the same board:

| New profile | Source profile | SOUL of the new profile |
|---|---|---|
| `harness-worker-glm-3` | `harness-worker-glm-1` | `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-3/SOUL.md` |
| `chapt-worker-glm-3` | `chapt-worker-glm-1` | `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-3/SOUL.md` |
| `jobcron-worker-glm-3` | `jobcron-worker-glm-1` | made from `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md` (step 3) |
| `jss-worker-glm-3` | `jss-worker-glm-1` | `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-3/SOUL.md` |
| `anki-worker-glm-3` | `anki-worker-glm-1` | `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-3/SOUL.md` |

Every profile that has the `jev` plugin routes its own `kanban_create` calls, not only the orchestrators: `_tool_execution` in `/Users/chanbla11mit/hermes-local-harness/plugins/jev/__init__.py` passes every `kanban_create` call to `routing.handle_create`, whatever the profile; the routing code in `/Users/chanbla11mit/hermes-local-harness/plugins/jev/routing.py` reads the name of the calling profile only in `handle_request_review`, so no condition of the `kanban_create` path depends on the calling profile; and Hermes allows `kanban_create` in workers and reviewers (in `/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py` only `kanban_list` and `kanban_unblock` call `_require_orchestrator_tool`), whose Kanban worker protocol tells them to create follow-up cards with `kanban_create`. A profile whose installed `config.json` names three GLM workers per board can therefore route a new card to a `-3` profile, and a GLM worker without a Z.ai login fails its run when the dispatcher starts it. For this reason the order is:

- Steps 1 to 6 for each of the five new profiles. During these steps no profile has the reviewed commit of the `config.json` that names three GLM workers per board; the copies keep the `jev` plugin of their source profile, whose `config.json` names two GLM workers per board, so no profile routes a card to a `-3` profile.
- Step 7 only after all five new profiles have their Z.ai login (step 6).
- Step 8 at the end.

For each `<profile>` with its `<source>` from the table:

1. Copy the source profile:

        hermes profile create <profile> --clone-from <source>

   Without `--clone-all`, `create_profile` calls `_bootstrap_profile_dir` (Hermes source `/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/profiles.py`, Hermes commit `9cf7960f27`), which copies these files and directories of `<source>`, each only when it exists (the same function also calls `clone_memory_provider_config`, and `create_profile` then removes messaging channel settings with `strip_channel_settings`):
   - `config.yaml` (`_CLONE_CONFIG_FILES`). Read on 2026-11-14 for card `t_f4ce916d` (key values only): in all five source profiles `model.default` is `glm-5.3`, `model.provider` is `zai`, `model.base_url` is `https://api.z.ai/api/coding/paas/v4`, every helper task under `auxiliary` has provider `zai` and model `glm-5.3` and no `fallback_chain` entries, `plugins.enabled` is `[jev]` and `plugins.disabled` is `[]`, and there is no fallback: `fallback_providers` is absent in four of the profiles and `[]` in `anki-worker-glm-1`.
   - `.env` (`_CLONE_CONFIG_FILES`), copied as a whole file with mode 0600 (`_clone_file`). Nobody opens, prints or changes the copied `.env`. The controller of card `t_f4ce916d` checked on 2026-11-14, without reading any value, that the `.env` of every existing GLM worker has no line that starts with `ANTHROPIC_API`.
   - `SOUL.md` (`_CLONE_CONFIG_FILES`); step 3 replaces it.
   - the installed skills, the directory `skills/`.
   - `memories/MEMORY.md` and `memories/USER.md` (`_CLONE_SUBDIR_FILES`). On 2026-11-14 `harness-worker-glm-1`, `chapt-worker-glm-1` and `jobcron-worker-glm-1` have `memories/MEMORY.md`; no source profile has `memories/USER.md`.
   - the directory `plugins/` with `.install-metadata.json` (`_clone_plugins`). On 2026-11-14 it holds the plugin directory `jev` in all five source profiles and also `model-providers` (with `claude-subscription` in it) in `anki-worker-glm-1`.

   The copy contains no `auth.json`: `auth.json` is in none of these lists (only `--clone-all` copies the whole profile directory, and this procedure does not use it). The new profile therefore has no Z.ai login until step 6.
2. Delete the copied memory files, as `procedures/manual-apply.md` requires for a copied profile. `-f` is needed because a source profile can have neither file:

        rm -f /Users/chanbla11mit/.hermes/profiles/<profile>/memories/MEMORY.md /Users/chanbla11mit/.hermes/profiles/<profile>/memories/USER.md

3. Replace the copied SOUL:
   - For `harness-worker-glm-3`, `chapt-worker-glm-3`, `jss-worker-glm-3` and `anki-worker-glm-3`, copy the tracked source:

            cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md

   - For `jobcron-worker-glm-3`, which has no tracked source, write the live file of `jobcron-worker-glm-1` with the profile name and the worker number replaced:

            sed -e 's/jobcron-worker-glm-1/jobcron-worker-glm-3/g' -e 's/implementation worker 1/implementation worker 3/g' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-3/SOUL.md

     On 2026-11-14 that live file has `implementation worker 1` once (first line: `You are Jobcron GLM Full implementation worker 1.`) and `jobcron-worker-glm-1` twice (the paths in the attachment and diff paragraph). Afterwards `diff /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-3/SOUL.md` shows only these replacements.
4. Check the plugins:

        hermes -p <profile> plugins list --plain --no-bundled
        ls -a /Users/chanbla11mit/.hermes/profiles/<profile>/plugins /Users/chanbla11mit/.hermes/profiles/<source>/plugins

   The first command must print the line of `jev` with the status `enabled`, and the same plugin lines as `hermes -p <source> plugins list --plain --no-bundled`. The two directory listings must be equal: only the plugins of `<source>` are present. The copied `jev` is the commit that is installed in `<source>`, whose `config.json` names only two GLM workers per board. The plugin in a GLM worker clears the card's model override at the review handoff only when the profile's own name is among the `glm_workers` of its installed `config.json` (`/Users/chanbla11mit/hermes-local-harness/plugins/jev/routing.py`, `handle_request_review`), and the plugin in a reviewer moves a card to a Claude worker after the fifth change request only when the card's assignee is among the board's `glm_workers` of the reviewer's installed `config.json` (`handle_request_changes`). Do not install the reviewed commit in this step; step 7 installs it, first on the five new profiles and the five reviewers.
5. Add the profile to `kanban.dispatch_profiles` of `/Users/chanbla11mit/.hermes/config.yaml`. The switch script writes this entry only together with `--to`; with `--to glm` it sets the same model, provider, base URL and helper tasks that the copy already has, with `--clear-fallbacks` it writes `fallback_providers` `[]` and `[]` for every `auxiliary.<task>.fallback_chain`, and it backs up the profile's `config.yaml` first. Preview with `--dry-run`, then run:

        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch add --clear-fallbacks

   The script also writes the profile's model and provider into `/Users/chanbla11mit/hermes-local-harness/roster.yaml`; they are already `glm-5.3` and `zai`, so `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain` stays empty. The switch script adds the profile at the end of `kanban.dispatch_profiles` (`set_dispatch` in `/Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model`), and `/Users/chanbla11mit/hermes-local-harness/snapshots/sanitized-current-state.yaml` records the five `-worker-glm-3` entries at the end of that list in the order in which card `t_55432326` added them: `harness-worker-glm-3`, `chapt-worker-glm-3`, `jobcron-worker-glm-3`, `jss-worker-glm-3`, `anki-worker-glm-3`.
6. The owner adds the Z.ai login of the profile, because the copy has no `auth.json`:

        hermes -p <profile> auth add zai

   Nobody else runs this command or handles the key.
7. This step is done once for all 36 profiles, not once for each new profile. Only after all five new profiles have their Z.ai login, install the reviewed commit, whose `config.json` names three GLM workers per board, on no profile before that point and in this order:
   1. on the five new profiles, then on the five reviewers (`jobcron-reviewer`, `chapt-reviewer`, `harness-reviewer`, `jss-reviewer`, `anki-reviewer`). These ten profiles need the new `config.json` before any card reaches a `-3` profile: the `-3` profile for `handle_request_review` and the reviewers for `handle_request_changes` (step 4);
   2. then on the other 26 profiles of the 36: `advisor`, the two Claude workers and the GLM workers `-glm-1` and `-glm-2` of each board, and the five orchestrators (`jobcron-orchestrator`, `chapt-orchestrator`, `harness-orchestrator`, `jss-orchestrator`, `anki-orchestrator`).

   Install as "Install on a profile" describes, with `--force` added, because every one of the 36 profiles already has `jev`: Hermes refuses an install over an existing plugin without `--force` (Hermes source `/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/plugins_cmd_install.py`, Hermes commit `9cf7960f27`, message `Plugin 'jev' already exists. Use force reinstall ...`), and `install --force --ref` replaces the plugin's code with the given commit. For the local source:

        hermes -p <profile> plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref <reviewed commit> --enable --force

   `--force` also lets a plugin scan result with the verdict `caution` pass without the confirmation question; a `dangerous` verdict is still blocked (`/Users/chanbla11mit/.hermes/hermes-agent/tools/plugin_guard.py`, `should_allow_plugin_install`). If the output of an install names a `caution` verdict, stop before the next install and report the findings to the owner.

   From the first of these installs on, every profile that has the new `config.json` can route cards to the new profiles (see the paragraph before step 1); all five new profiles have their login by then, so their runs do not fail for a missing Z.ai login.
8. Run `python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state`. Afterwards none of these lines may be printed for the profile. The live run of card `t_f4ce916d` on 2026-11-14 printed the first nine kinds for each of the five missing profiles:
   - `FAIL: missing profile: <profile>`
   - `FAIL: provider drift <profile>: expected zai`
   - `FAIL: approval mode drift <profile>: expected off, actual '<unreadable>'`
   - `FAIL: unable to read plugin list <profile>`
   - `FAIL: fallback drift <profile> fallback_providers: expected [], actual <unreadable>`
   - `FAIL: fallback drift <profile> auxiliary: expected a readable auxiliary mapping, actual <unreadable>`
   - `FAIL: GLM worker missing from kanban.dispatch_profiles: <profile>`
   - `FAIL: concurrency/dispatch drift kanban.dispatch_profiles: expected [...], actual [...]` (one line for the whole list; `scripts/verify-state` compares the whole list, including the order of its entries, and the line is absent when the live list equals the `kanban.dispatch_profiles` list of `/Users/chanbla11mit/hermes-local-harness/snapshots/sanitized-current-state.yaml` entry for entry)
   - `FAIL: deployed skill copy missing: <skill> <profile>/<file>`, for each file of each shared skill whose `deploy_profiles` in `/Users/chanbla11mit/hermes-local-harness/snapshots/sanitized-current-state.yaml` names the profile (the copy of step 1 brings these skills)
   - `FAIL: plugin drift <profile>: required jev not enabled (actual ...)`
   - `WARN: dormant unexpected plugin <profile>: <plugin>`

   The SOULs of the five reviewers and the five orchestrators and the five orchestrator skills that card `t_f4ce916d` changed are deployed by the same deployment card. Deploy the five reviewer SOULs before step 7: a reviewer whose SOUL is from before card `t_f4ce916d` accepts review only for the four implementation profiles named there, so it would not accept a card that a `-3` profile implemented. Until these SOULs and skills are deployed, the live run prints `FAIL: profile SOUL drift <profile>` for the nine of these SOULs that `scripts/verify-state` checks (`PROFILE_SOUL_PATHS` has no entry for `jobcron-reviewer`) and `FAIL: profile-local skill override drift: <orchestrator profile>/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` for the five orchestrators; after that deployment these lines must be absent as well.

## Attachment and diff procedure of the GLM workers

Card `t_ac454595` (GLM routing request of 2026-11-13, Part 6.3) added an exact procedure for attaching a file to a card and for producing the diff that the reviewer reads to the instructions of the ten GLM workers. On card `t_7097923f` a GLM worker had four failed `kanban_attach` and `kanban_attach_url` calls, and the reviewer rejected a malformed diff. The procedure rests on these facts of the installed Hermes source `/Users/chanbla11mit/.hermes/hermes-agent`:

- `kanban_attach` takes `filename` and `content_base64` (required), `content_type`, `task_id` and `board` (optional) (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools_schemas.py`, `KANBAN_ATTACH_SCHEMA`; `_schema` adds `board` to every Kanban tool), and decodes `content_base64` with `base64.b64decode(..., validate=True)` (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`, `_handle_attach`), so a file path, a `file://` URL or Base64 text with line breaks is rejected.
- The Kanban worker protocol that Hermes adds to the system prompt of every dispatched worker says "Do not shell out to `hermes kanban <verb>` for board operations. Use the `kanban_*` tools" (`/Users/chanbla11mit/.hermes/hermes-agent/agent/prompt_builder.py`, line 336, at Hermes commit `9cf7960f27`). The procedure therefore states that `hermes kanban attach` on the worker's own card is the only exception to that rule, and that every other board operation still uses the `kanban_*` tools.
- `kanban_attach_url` accepts only `http` and `https` URLs and refuses loopback and private network addresses (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`, `_download_url_with_cap`).
- `hermes kanban --board <board> attach <task id> <path> [--name <file name>]` reads a local file, stores it with the same 25 MB limit, and refuses a task other than `HERMES_KANBAN_TASK` (`/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/kanban.py`, `_cmd_attach` and `_worker_run_id_for`).
- The tool result filter of this plugin cuts a line longer than `chunk_chars` (500) into pieces and can shorten a `terminal` or `execute_code` result of more than 2,000 characters (`/Users/chanbla11mit/hermes-local-harness/plugins/jev/tool_filter.py`, `_split_units` and `_make_chunks`), so Base64 text longer than that cannot be copied reliably from a tool result.

The tracked SOUL sources of the twelve GLM workers that have one contain the procedure as one paragraph: `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-3/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-3/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-3/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-3/SOUL.md`.

`jobcron-worker-glm-1` and `jobcron-worker-glm-2` have no SOUL source in this repository: `/Users/chanbla11mit/hermes-local-harness/roster.yaml` (`profile_souls`) and `/Users/chanbla11mit/hermes-local-harness/scripts/verify-state` (`PROFILE_SOUL_PATHS`) do not list them, and `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/` has no directory for them (the same holds for `jobcron-worker` and `jobcron-worker-2`). Their live files `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md` and `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-2/SOUL.md` have no line that starts with `#` (SHA-256 on 2026-11-13: `dbd702cf57c46b29e49373497e1ac2d1d6a43b3eba14682aa22f26c6e797b930` and `e05167d0aab81cd1c2f79c2caeaa181dc809e55a34d9d8cb916d3f449dc9c623`). Card `t_7e73d1b4` added the paragraph below for each of the two profiles to its live file on 2026-11-13, with the owner's authorization, as a new paragraph at the end of the file after one empty line, because neither file has a paragraph that starts with `Terminology and wording`. The SHA-256 values above are the values before the change; the values after the change are `ea3494552afed57734131fabafcd8b62205bb2a6ac9f9f63398dae11e1510968` (`jobcron-worker-glm-1`) and `d6e711330a6576958eb4c053b26e826b59c181532b3bd6127e2e72e64497fc0a` (`jobcron-worker-glm-2`).

`jobcron-worker-glm-3` has no SOUL source in this repository either. Its live file is the live file of `jobcron-worker-glm-1` with `jobcron-worker-glm-1` replaced by `jobcron-worker-glm-3` and `implementation worker 1` replaced by `implementation worker 3` (see "Creating the third GLM worker profile of each board", step 3), so it contains the paragraph for `jobcron-worker-glm-1` below with that replacement.

Paragraph for `jobcron-worker-glm-1`:

    Attach a file to the card with the terminal command `hermes kanban --board jobcron attach <task id> <absolute path of the file> --name <file name>`; it reads the file itself and accepts files up to 25 MB. This command is an exception to the rule "Do not shell out to `hermes kanban <verb>` for board operations" of the Hermes Kanban worker protocol: the exception covers only `attach` on your own card, the card named in `HERMES_KANBAN_TASK`, and every other board operation still uses the `kanban_*` tools. Use the `kanban_attach` tool only for a file of at most 1,000 bytes: pass the file's bytes as Base64 text on one line without line breaks in `content_base64` (print it with `base64 -i <absolute path of the file>`; on macOS `base64` writes one line), for example `kanban_attach(task_id: "t_0123abcd", filename: "focused-test-output.txt", content_base64: "T0sK", content_type: "text/plain", board: jobcron)`, which attaches a file that contains the text `OK` and a line break. Longer Base64 text is not reliable in a tool result, because the `jev` plugin can shorten a `terminal` or `execute_code` result of more than 2,000 characters. Never put a file path or a `file://` URL in `content_base64`, and never use `kanban_attach_url` for a local file: it accepts only `http` and `https` URLs and refuses loopback and private network addresses. To give the reviewer the diff of a committed change, run `mkdir -p /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/cache/scratch && git -C <worktree path> diff <baseline commit> HEAD > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/cache/scratch/<task id>.diff` after the last commit, with the full 40-character commit of the card's `Baseline EXACT` line and with an empty `git -C <worktree path> status --porcelain`, attach that file with the command above, and name the commit that `git -C <worktree path> rev-parse HEAD` prints in the review request. Attach only the unchanged output of that command: never write, edit, shorten or combine a diff by hand.

Paragraph for `jobcron-worker-glm-2`:

    Attach a file to the card with the terminal command `hermes kanban --board jobcron attach <task id> <absolute path of the file> --name <file name>`; it reads the file itself and accepts files up to 25 MB. This command is an exception to the rule "Do not shell out to `hermes kanban <verb>` for board operations" of the Hermes Kanban worker protocol: the exception covers only `attach` on your own card, the card named in `HERMES_KANBAN_TASK`, and every other board operation still uses the `kanban_*` tools. Use the `kanban_attach` tool only for a file of at most 1,000 bytes: pass the file's bytes as Base64 text on one line without line breaks in `content_base64` (print it with `base64 -i <absolute path of the file>`; on macOS `base64` writes one line), for example `kanban_attach(task_id: "t_0123abcd", filename: "focused-test-output.txt", content_base64: "T0sK", content_type: "text/plain", board: jobcron)`, which attaches a file that contains the text `OK` and a line break. Longer Base64 text is not reliable in a tool result, because the `jev` plugin can shorten a `terminal` or `execute_code` result of more than 2,000 characters. Never put a file path or a `file://` URL in `content_base64`, and never use `kanban_attach_url` for a local file: it accepts only `http` and `https` URLs and refuses loopback and private network addresses. To give the reviewer the diff of a committed change, run `mkdir -p /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-2/cache/scratch && git -C <worktree path> diff <baseline commit> HEAD > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-2/cache/scratch/<task id>.diff` after the last commit, with the full 40-character commit of the card's `Baseline EXACT` line and with an empty `git -C <worktree path> status --porcelain`, attach that file with the command above, and name the commit that `git -C <worktree path> rev-parse HEAD` prints in the review request. Attach only the unchanged output of that command: never write, edit, shorten or combine a diff by hand.

## TypeSafe API key

The plugin reads the key from the environment variable `TYPESAFE_API_KEY` at each call. A process reads only the `.env` of its own Hermes home (Hermes source `hermes_cli/env_loader.py` lines 455 to 509). Therefore the owner adds one line that sets the variable `TYPESAFE_API_KEY` to each of these files:

- `/Users/chanbla11mit/.hermes/.env`, for sessions served by the default gateway (the orchestrators);
- the `.env` of every profile that the dispatcher starts, in `/Users/chanbla11mit/.hermes/profiles/<profile>/.env`: the Claude workers, the GLM workers and the reviewers of the five boards. A worker or reviewer started by the dispatcher has its profile directory as its Hermes home and never reads `/Users/chanbla11mit/.hermes/.env`. Without the line, every Jev call of that profile fails with `MissingKey`, and the tool result filter leaves every result of that profile unchanged. (The reassignment after change requests makes no Jev call.)
- the `.env` of an orchestrator profile, `/Users/chanbla11mit/.hermes/profiles/<orchestrator profile>/.env`, for an orchestrator session that is started outside the gateway process. The skills tell the owner to launch an orchestrator with its wrapper script, for example `/Users/chanbla11mit/hermes-local-harness/scripts/run-harness-orchestrator`. Each of the five scripts `/Users/chanbla11mit/hermes-local-harness/scripts/run-<board>-orchestrator` runs `exec env HERMES_KANBAN_BOARD=<board> <orchestrator profile> chat --in <repository>`, and the command `/Users/chanbla11mit/.local/bin/<orchestrator profile>` runs `hermes -p <orchestrator profile>`, which sets the Hermes home to the orchestrator profile's directory (Hermes source `hermes_cli/main.py`, `_apply_profile_override`, lines 594 to 657). Such a session therefore reads the line only from the orchestrator profile's own `.env` (or from the environment of the shell that started it), not from `/Users/chanbla11mit/.hermes/.env`. The five orchestrator profile `.env` files (`jobcron-orchestrator`, `chapt-orchestrator`, `harness-orchestrator`, `jss-orchestrator`, `anki-orchestrator`) do not have that line (checked on 2026-11-13 by line count only, GLM routing request, section "Facts verified"). Until the owner adds it, every routing decision of such a session is logged with `error_class` `MissingKey` and every card is created unchanged. Only the owner adds the line.

Nobody else writes, prints or copies the value. A worker checks the line only by count, without printing it: `grep -c '^TYPESAFE_API_KEY' /Users/chanbla11mit/.hermes/profiles/<profile>/.env` prints `1`. The value is never written to a log, a card, the repository or a chat message.

Without the key the plugin still loads: every routing decision is logged with `error_class` `MissingKey` and the card is created unchanged; the tool result filter leaves results unchanged.

## Configuration file

`plugins/jev/config.json` in the installed plugin directory is read on every call, so a changed value applies without a restart. Each of `routing`, `peak_hold`, `tool_results` and `auxiliary_log` turns off with `"enabled": false`; turning off `routing`, or one of its routes, needs the owner's permission (see "Route disabling needs the owner's permission"). `routing.control_group_every` and `routing.max_glm_change_requests` take a whole number; `0`, a negative number, a missing value or a value of another type turns that part off.

| Setting | Value | Meaning |
|---|---|---|
| `jev.endpoint` | `https://api.typesafe.ai/v1/systemone` | TypeSafe endpoint (tests point it at a local fake server) |
| `jev.model` | `jev-1.14.0` | Jev model ID |
| `jev.timeout_seconds` | `5` | Timeout of every Jev call |
| `jev.api_key_env` | `TYPESAFE_API_KEY` | Name of the environment variable that holds the key |
| `kanban.home` | `/Users/chanbla11mit/.hermes` | Kanban root; board databases are `<home>/kanban/boards/<board>/kanban.db` (`HERMES_KANBAN_HOME` overrides) |
| `kanban.hermes_command` | `hermes` | Command used for `hermes kanban --board <board> ...` changes |
| `kanban.command_timeout_seconds` | `30` | Timeout of each `hermes kanban` command |
| `routing.enabled` | `true` | Card model routing on or off |
| `routing.threshold` | `0.6` | Minimum probability of the chosen route |
| `routing.state_max_chars` | `60000` | The card body is cut at this length before it is sent to Jev |
| `routing.question_instructions` | text | The Choice question sent to Jev |
| `routing.clear_override_at_review` | `true` | Clear the card's model override when a GLM worker requests review |
| `routing.control_group_every` | `10` | Every tenth card of a board and route that would get `easy` or `medium` stays with the Claude worker (see "Control group"). `0` turns the control group off |
| `routing.max_glm_change_requests` | `5` | A card of a GLM worker goes to a Claude worker when the card has this many change requests (see "Reassignment to a Claude worker after change requests"). `0` turns the reassignment off |
| `routing.known_models` | model IDs | Model IDs that are written to the log as given in `orchestrator_model`; any other `model` argument is logged as `unrecognized`. The models of the configured routes are always included |
| `routing.boards.<board>` | object | `implementation_workers`, `glm_workers`, `routes` |
| `peak_hold.enabled` | `true` | Peak-hours hold on or off in the configuration (the owner's switch file is the other condition) |
| `peak_hold.timezone` | `Asia/Seoul` | Time zone of the window |
| `peak_hold.weekdays` | `[0, 1, 2, 3, 4]` | Monday to Friday |
| `peak_hold.start`, `peak_hold.end` | `15:00`, `19:00` | Start inclusive, end exclusive |
| `peak_hold.marker` | `jev-peak-hold` | Text at the start of the `scheduled` reason of every held card |
| `tool_results.enabled` | `true` | Tool result filter on or off |
| `tool_results.tools` | `terminal`, `execute_code`, `search_files`, `browser_exec` | Tools whose results are filtered |
| `tool_results.min_chars`, `max_chars` | `2000`, `100000` | Output text length range that is filtered |
| `tool_results.chunk_lines`, `chunk_chars` | `10`, `500` | Chunk size |
| `tool_results.args_chars` | `2000` | Tool arguments are cut at this length in the Jev state |
| `tool_results.keep_threshold` | `0.6` | Minimum probability for keeping a chunk |
| `tool_results.max_kept_ratio` | `0.9` | If the kept text is this share of the original or more, the result is unchanged |
| `auxiliary_log.enabled` | `true` | Auxiliary call log on or off |

## Routes and their criteria

For each `kanban_create` call the plugin sends Jev one Choice question. The state is the card title and the body cut at 60,000 characters; the options are the board's enabled routes with these criteria:

- `easy` (model `glm-5.3-flash`, provider `zai`, assignee from the board's `glm_workers`): The card names the exact files to change and the exact command that checks the result, and the worker has no behaviour to work out. The topic of the card does not matter.
- `medium` (model `glm-5.3`, provider `zai`, assignee from the board's `glm_workers`): A fully specified change across several files with no design decision. This includes tests, fixtures, user-facing text and wiring inside security, migration or deployment features.
- `hard` (no change: the Claude worker the orchestrator named, with that profile's own model): Everything else: a design decision, a fault with an unknown cause, logic for authentication, secrets or payment, writing a database migration, or commands that will be run against production, including deployment guides.

Card `t_df87b851` set these three texts on all five boards (the owner's instruction of 2026-11-13 to change every route of every board). The earlier texts named topics (`easy`: a documentation or wording edit; `hard`: security, payment, migration or deployment work); the new texts decide by how exactly the card is specified.

The route is applied only when all three conditions hold: the orchestrator left `model` empty, the `assignee` is one of the board's `implementation_workers`, and the chosen route's probability is at least `threshold`. Otherwise the card is created exactly as the orchestrator asked. On `easy` or `medium` the plugin sets `assignee` to the next GLM worker of the board (the three take turns; the counter is in `<log dir>/routing-state.json`, which holds only board names, route names and counters), sets `model` and `provider`, and replaces the profile name on a body line that starts with `Assigned worker EXACT `. The reviewer is not changed. Any Jev error, timeout, HTTP error, missing key or unexpected answer leaves the card unchanged.

A repeated `kanban_create` with an `idempotency_key` that Hermes already knows returns the existing card, and Hermes does not apply the new arguments to it. The plugin cannot tell this case from a new card: the alternation counter and the control group counter still advance, and the `route` record says `applied` `true` (or `not_applied_reason` `control_group`) although the existing card is unchanged.

| Board | Implementation workers | GLM workers | Enabled routes |
|---|---|---|---|
| `jobcron` | `jobcron-worker`, `jobcron-worker-2` | `jobcron-worker-glm-1`, `jobcron-worker-glm-2`, `jobcron-worker-glm-3` | `easy`, `medium`, `hard` |
| `cha-pt` | `chapt-worker`, `chapt-worker-2` | `chapt-worker-glm-1`, `chapt-worker-glm-2`, `chapt-worker-glm-3` | `easy`, `medium`, `hard` |
| `harness` | `harness-worker`, `harness-worker-2` | `harness-worker-glm-1`, `harness-worker-glm-2`, `harness-worker-glm-3` | `easy`, `medium`, `hard` |
| `jss-genr` | `jss-worker`, `jss-worker-2` | `jss-worker-glm-1`, `jss-worker-glm-2`, `jss-worker-glm-3` | `easy`, `medium`, `hard` |
| `anki` | `anki-worker`, `anki-worker-2` | `anki-worker-glm-1`, `anki-worker-glm-2`, `anki-worker-glm-3` | `easy`, `medium`, `hard` |

Every board has GLM routing (card `t_71b4ef4a` added `jss-genr` and `anki`). Card `t_f4ce916d` added the third GLM worker of every board on 2026-11-14. Every board uses the same three routes with the same models, providers and criteria. A board whose `easy` and `medium` routes are both disabled in `config.json` gets no Jev call, and its cards stay on Claude.

### Model override at the review handoff

The dispatcher passes a card's `model` and `provider` override to every run of the card, including the reviewer's run (Hermes source `hermes_cli/kanban_db_dispatch.py` lines 2761 to 2766). Without a correction the Claude reviewer would start with a GLM model and the `zai` provider. Therefore, when a GLM worker profile calls `kanban_request_review`, the plugin first runs `hermes kanban --board <board> set-model <task id> none`, and then lets the review request run. Consequence: if the reviewer requests changes, the rework runs on the GLM worker profile's own model (`glm-5.3`), also for a card that started on the `easy` route with `glm-5.3-flash`.

### Control group

Setting `routing.control_group_every` (value `10`; `0` turns it off). For each `kanban_create` call where every condition for applying an `easy` or `medium` route holds (the orchestrator left `model` empty, the `assignee` is one of the board's `implementation_workers`, the route's probability is at least `threshold`, and the board has GLM workers), the plugin advances a counter for that board and route. On every tenth such card the card is created exactly as the orchestrator asked, so it stays with the Claude worker the orchestrator named. The `route` record of that card has `applied` `false`, `not_applied_reason` `control_group`, and `route` and `probabilities` as usual. The GLM worker alternation counter does not advance for a control card.

The counters are kept in `<log dir>/routing-state.json` under the same file lock as the alternation counter, in a separate section `control_group_counters` (board name, then route name, then the count modulo `control_group_every`). A counter, not a random draw, decides, so that exactly one card in ten is a control card however few cards there are. Card `t_a40f99ed` changed the value from `5` to `10` on 2026-11-14 (owner's instruction). The file `routing-state.json` needs no change for it, because each counter is kept modulo the setting, and the comparison group now grows half as fast. `hard` cards and cards where a condition fails (`model_set`, `assignee_not_listed`, `below_threshold`, a Jev error) do not count. If the state file cannot be written, the card is created unchanged and the record has `not_applied_reason` `plugin_error`. The control cards are the comparison group for the Claude tokens saved by the GLM routes (`scripts/jev-report`).

### Reassignment to a Claude worker after change requests

Setting `routing.max_glm_change_requests` (value `5`; `0` turns it off). The middleware also handles `kanban_request_changes`, which the reviewer calls. The call runs first, unchanged, and its result is returned unchanged. Afterwards the plugin reads the card from the board database (read only). When all of the following hold, the card goes to a Claude worker of the board:

- the call did not return an error;
- the card's assignee, which Hermes `request_changes` has just set back to the implementer, is one of the board's `glm_workers`;
- the card now has at least `max_glm_change_requests` events of kind `changes_requested`; with the value `5`, the fifth change request sends the card to a Claude worker, so a GLM worker makes at most five attempts on a card;
- the card's status is `ready` or `todo` (as Hermes leaves it), `running` (a dispatcher tick claimed it for the GLM worker in the meantime) or `scheduled` (the peak-hours hold held it in the meantime).

The plugin then runs up to three commands:

1. `hermes kanban --board <board> set-model <task id> none` (clears a model override, so that the Claude worker does not start with a GLM model and the `zai` provider);
2. only when the first command worked, `hermes kanban --board <board> reassign <task id> <Claude worker> --reclaim`;
3. only when the second command worked, the plugin reads the card body again (read only) and, when a body line starts with `Assigned worker EXACT ` followed by the GLM worker's name, runs `hermes kanban --board <board> edit <task id> --body=<body>` with the Claude worker's name in place of the GLM worker's name on that line. The plugin wrote the GLM worker's name on that line when it routed the card at creation, and every Claude worker `SOUL.md` tells the worker to block without editing when the card names another profile as the assigned worker, so without this step the Claude worker would block instead of implementing. The same rule as at creation applies: only the name at the start of such a line changes; the same text inside another line, an indented line and a line that names another profile stay unchanged. A body without such a line gets no `edit` command. The `--body=<body>` form keeps a body whose first character is `-` one argument value. A body longer than 100,000 bytes is not sent, because `hermes kanban edit` has no `--body-file` option and the body must fit in one command-line argument (Linux limits one argument to 131,072 bytes, macOS all arguments and the environment together to 1,048,576 bytes).

The Claude worker is the `original_assignee` of the card's `route` record in `decisions.jsonl` (the worker the orchestrator named when it created the card); when there is no such record, the board's `implementation_workers` alternate (section `escalation_counters` of `routing-state.json`).

Why this works inside the reviewer process, and why the next run is the Claude worker's (checked on card `t_df87b851` with Hermes `9cf7960f27`):

- Hermes `request_changes` (`hermes_cli/kanban_db.py` lines 3575 to 3642) ends the reviewer's run and sets the card to `ready` (or `todo` while a parent is open) with the implementer as assignee. `reassign` (`assign_task`, lines 1625 to 1654) then changes `tasks.assignee`, and the dispatcher starts the profile named in `tasks.assignee` (`hermes_cli/kanban_db_dispatch.py` line 2845). The `assigned` event with a different profile also counts as a handoff for the dispatcher's open pull request check (lines 1624 to 1641 and `_is_handoff_event`).
- `hermes kanban set-model` and `hermes kanban reassign` do not check `HERMES_KANBAN_TASK` (`hermes_cli/kanban.py` `_cmd_set_model` and `_cmd_reassign`, lines 580 to 615), unlike `schedule` and `unblock`, and the dispatcher removes the delegated-child marker from the environment of every worker and reviewer it starts (`hermes_cli/kanban_db_dispatch.py` lines 2934 to 2935). A run of the installed Hermes code in an isolated Hermes home with the environment of a reviewer process confirmed it: after `request_changes`, `set-model <id> none` and `reassign <id> <profile>` both exited with status 0 and left the card `ready` on the new profile without an override, while `schedule` of another card was refused.
- Each `hermes kanban` command takes about 0.7 seconds, so about 1.5 to 2 seconds pass between the change request and the reassignment. If a dispatcher tick (every 60 seconds) claims the card for the GLM worker in that time, `--reclaim` ends that run (`reclaim_task`, `hermes_cli/kanban_db.py` lines 2638 to 2671) before the card is reassigned, so the GLM run is stopped within seconds of its start. For a card that is not running, `--reclaim` changes nothing.
- `hermes kanban edit` does not check `HERMES_KANBAN_TASK` either (`hermes_cli/kanban.py` `_cmd_edit`, lines 946 to 969; its only body option is `--body`, `hermes_cli/kanban_parser.py` lines 307 to 314). `edit_task` (`hermes_cli/kanban_db.py` lines 3211 to 3287) replaces `tasks.body` and adds one `edited` event. `edited` is not one of the event kinds that wake the orchestrator (`gateway/kanban_watchers_notifier.py` line 50, `_WAKE_KINDS`). A run of the plugin code against the installed Hermes code in an isolated Hermes home with the environment of a reviewer process confirmed it: after five real change requests the card was `ready` on the Claude worker without an override, its events ended with `model_override_set`, `assigned`, `edited`, and the body was exactly the expected body with the Claude worker on the `Assigned worker EXACT` line (the body began with `-` and had a line starting with `--body`). After four change requests nothing changed.
- The `edit` command ends about 0.7 seconds after the reassignment. A dispatcher tick in that time can start the Claude worker before the body is rewritten. The dispatcher gives a worker only the task ID (`hermes chat -q "work kanban task <id>"`, `hermes_cli/kanban_db_dispatch.py` line 2774), and the worker reads the body later with `kanban_show`, after its model session has started; the body is then normally already rewritten, but this is not guaranteed. The body is read and written by two separate steps, so an edit that the orchestrator makes to the same card body in that second is overwritten.

One `decisions` record with `event` `escalate` is written for each escalation: `board`, `task_id`, `original_assignee` (the GLM worker), `new_assignee` (the Claude worker, or the GLM worker again when the commands failed), `change_requests` (the count), `applied`, `error_class` (`not_applied_reason` `no_claude_workers` or `plugin_error` when it applies). When the reassignment worked, the record also has `assigned_worker_line`: `rewritten`, `no_line` (the body has no line to change; no `edit` command ran) or `failed`, and `assigned_worker_line_error_class` (for example `CommandFailed`, `CommandTimeout`, `BodyTooLong`, or the class of a read error). The record never contains body text. If the first or second command fails, the card stays as Hermes left it: with the GLM worker, which runs the next attempt. A sixth change request on the same card, now implemented by a Claude worker, changes nothing.

If the third step fails (`assigned_worker_line` `failed`), the card stays as the reassignment left it: assigned to the Claude worker, without an override, with the body still naming the GLM worker on the `Assigned worker EXACT` line. The tool result is unchanged. What remains in that case: the Claude worker finds the profile mismatch and blocks the card under its `SOUL.md`; the orchestrator then changes the name on that line to the Claude worker with `hermes kanban --board <board> edit <task id> --body=<body>` (a card comment is not enough, because the worker checks the body) and unblocks the card. Find such cards with the `escalate` records that have `assigned_worker_line` `failed`.

A change request made with the command line (`hermes kanban request-changes`) instead of the `kanban_request_changes` tool is not seen by the middleware, so it never causes a reassignment, although it counts as one of the card's `changes_requested` events for the next change request made with the tool.

Orchestrators and reviewers must not reverse the reassignment (rule of the GLM routing request, Part 4.6, stated in the five orchestrator skills and the five reviewer `SOUL.md` files by card `t_ac454595`). The peak-hours hold never holds a card that is not assigned to a GLM worker, so an escalated card is never held (see "GLM peak-hours hold").

### Route disabling needs the owner's permission

No profile, script, scheduled job or plugin code turns off a route (a route's `enabled` set to false, a route removed, or a board's `glm_workers` emptied) unless the owner has first been notified with the figures and has stated permission for that route. This also applies to a rollback that turns off a route.

Setting `routing.enabled` to `false` turns off every route of every board, so the same rule applies to it. Setting `routing.control_group_every` or `routing.max_glm_change_requests` to `0` does not turn off a route.

## GLM peak-hours hold

Z.ai charges double on Monday to Friday from 15:00 to 19:00 Asia/Seoul time. In that window no card assigned to a GLM worker profile listed in `config.json` may be claimed by the dispatcher. A GLM run that started before 15:00 continues. Claude cards (the `hard` route) are never held.

How a card is held: it is moved to the Kanban `scheduled` status with the reason `jev-peak-hold until <date>T19:00:00+09:00`. Hermes sends no gateway notification for the `scheduled` event, and the `unblocked` event at release has no notification text and does not wake the orchestrator. A `blocked` status would wake the orchestrator for every hold, so it is not used except as the creation status below.

Holds and releases:

- `kanban_unblock` middleware (the usual path). Orchestrator Card Setup creates every card with `initial_status: blocked` and unblocks it with the `kanban_unblock` tool when setup is complete. Inside the window, when the card is `blocked` and assigned to a GLM worker of a configured board, the middleware runs `hermes kanban --board <board> schedule <id> "jev-peak-hold until ..."` instead of the unblock. Hermes accepts `schedule` for a `blocked` card, so the card goes from `blocked` directly to `scheduled` and is never `ready` inside the window. The tool result returned to the orchestrator has `status` `scheduled`, `held_until` and a note that says the card was not unblocked and how it is released. A card that is already held with the marker stays held. If the schedule command fails, the unblock runs unchanged and the script below holds the card. `kanban_unblock` is an orchestrator tool (Hermes refuses it when `HERMES_KANBAN_TASK` is set), so the `hermes kanban schedule` command works in that session. An unblock with the command line `hermes kanban unblock` instead of the tool is not seen by the middleware.
- `kanban_create` middleware. A card that ends up assigned to a GLM worker and that the caller did not create `blocked` or in triage is created with `initial_status: blocked` (the orchestrator's subscription is created after that event, so it is not delivered) and is then moved to `scheduled` with the marker. This is used only when all of the following are true, because only then can the plugin be sure the card is new and that both Kanban commands work: the call has no `idempotency_key` (Hermes returns the existing card for a known key), the session is not a dispatcher-started worker session (`HERMES_KANBAN_TASK` is not set; there `hermes kanban schedule` and `hermes kanban unblock` refuse every other card), the `hermes` command resolves to an executable, and the `kanban_create` result reports the card as `blocked`. In every other case the card is created exactly as requested and the script holds it on its next run. If the schedule command fails, the plugin runs `hermes kanban --board <board> unblock <id>` and the script holds the card on its next run. If that unblock also fails, the card stays `blocked` without the marker: the script does not release it, Hermes sends no notification for it, and the `hold` record has both error classes in `error_class` (for example `CommandFailed+CommandFailed`); find such cards with the `hold` records that have `applied` `false`.
- `scripts/jev-peak-hold --apply` (the other paths). It holds every `ready` or `todo` card of a GLM worker inside the window: cards already `ready` or `todo` at 15:00, cards created as requested in the cases above, cards returned to a GLM worker by a reviewer, cards retried after a crash, and cards unblocked with the command line. Just before each hold it reads the card again and skips it (`skipped hold <board> <id>`, no command, no record) when the card is no longer `ready` or `todo` or no longer assigned to a GLM worker, for example a card that the reassignment after change requests reassigned to a Claude worker after the script read the board. When that second read fails, the card is also skipped and the script prints the error class (`skipped hold <board> <id>: the card could not be read again (error_class=...)`); the next run, 10 seconds later, tries again.
- Release: the first `scripts/jev-peak-hold --apply` run at or after 19:00 runs `hermes kanban --board <board> unblock <id>` for every `scheduled` card whose latest `scheduled` reason starts with the marker. Hermes returns the card to `ready`, or to `todo` while a parent is open. Other `scheduled` or `blocked` cards are never released. A held card that is reassigned to a non-GLM profile, for example by the reassignment after change requests, is released on the next run.

A card whose assignee is not a GLM worker of its board is never held: the script selects only `ready` and `todo` cards of GLM workers and checks each card again before the hold, the `kanban_unblock` middleware checks the card's assignee in the board database, and the `kanban_create` middleware checks the assignee the card is created with. A card that the reassignment after change requests reassigned to a Claude worker is therefore never held. The remaining window is the time of one `hermes kanban schedule` command (about one second) after the check; a card reassigned inside that window is released by the next script run, 10 seconds later.

`scripts/jev-peak-hold` (Python standard library; it runs under `/usr/bin/python3` and under `python3` from Homebrew):

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold              # prints planned holds and releases only
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply      # performs them
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --now 2026-11-11T16:00:00+09:00   # time for tests

`--kanban-db <path>` with one `--board <name>`, `--config <path>` and `--hermes <command>` exist for tests. Running it twice changes nothing the second time. It reads each board database with a SQLite connection that has `PRAGMA query_only` set, which works for a WAL-mode database that has no `-wal` and `-shm` files with the older SQLite in `/usr/bin/python3`. A board database that cannot be read is reported as `failed read <board> error_class=<class>` on every run (with `--apply` and with `off` also as a `decisions` record with `event` `read_error`, at most one record per board per hour; the time of the last record for each board is kept in `<log dir>/read-error-state.json`, which holds only board names and timestamps), the other boards are still processed, and the script exits with status 1. A failed hold or release also gives exit status 1. The script reads the repository copy `/Users/chanbla11mit/hermes-local-harness/plugins/jev/config.json` unless `--config` names another file, while the middleware reads the copy installed in each profile; keep the `peak_hold` and `routing.boards` sections of the two copies the same.

Schedule: a LaunchAgent with label `com.nous.hermes-jev-peak-hold` runs `/usr/bin/python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply` every 10 seconds (`StartInterval` 10), with the directory of the `hermes` executable in its `PATH` (the default `PATH` of launchd does not contain `/opt/homebrew/bin`). The deployment card installs it with the owner's authorization. Outside the window each run only releases cards held with the marker, so one schedule serves both holding and releasing. A run that finds nothing to do only reads the board databases.

Remaining race between a dispatcher tick and the script:

- No race for a card unblocked with the `kanban_unblock` tool inside the window (orchestrator Card Setup step 5) and for a card held at creation: the card goes from `blocked` to `scheduled` and is never `ready`.
- A race for every card that becomes `ready` for a GLM worker inside the window by another path (listed under `scripts/jev-peak-hold --apply` above, and the fallbacks when a schedule command fails). The dispatcher claims `ready` cards once per `kanban.dispatch_interval_seconds` (default 60 seconds; Hermes source `gateway/kanban_watchers_dispatcher.py` line 50, read once when the gateway starts), and the script runs every 10 seconds. Such a card is claimed by the dispatcher before the next script run when a dispatcher tick comes first. For a fixed offset between the two cycles, the share of such cards is the time from the last script run before a dispatcher tick to that tick, divided by 60 seconds: at most one card in six (an offset of almost 10 seconds), and about one card in twelve averaged over the offset (5 of 60 seconds). A GLM run that the dispatcher started before the script read the board continues. If the dispatcher claims the card between the script's read of the board and its `hermes kanban schedule` command (about one second per card), Hermes accepts `schedule` for the `running` card and ends that run (Hermes source `hermes_cli/kanban_db.py` lines 4040 to 4057); the card is released at 19:00. Only a run that started inside the window can be affected this way, never a run that started before 15:00. The same applies at 15:00 to cards that were already `ready`.
- Release happens up to 10 seconds after 19:00.

Every hold and every release writes one `decisions` record (`event` `hold` or `release`, `held_until`).

## Turning the peak-hours hold off and on

The owner can turn the hold off in an emergency and back on, without reinstalling the plugin, editing `config.json` or restarting the gateway. The switch is the file `/Users/chanbla11mit/.hermes/jev/peak-hold.json` (mode 0600; content `enabled`, `changed_at`, `changed_by`). An absent file means on. A file that cannot be read is treated as on and logged with its `error_class`. The middleware and the script read it on every call; the hold is active only when both `peak_hold.enabled` in `config.json` and the switch are true.

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off      # turn off and release every held card at once
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold on       # turn on; cards are held again from the next run inside the window
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold status   # on or off, when and by whom, number of held cards

`off` and `on` are idempotent. Each change writes one `decisions` record with `event` `toggle` and the new value in `enabled`. `--by <name>` sets `changed_by` (default: `HERMES_PROFILE`, then the login name).

## Tool result filter

The `transform_tool_result` hook calls `plugins/jev/tool_filter.py` (written by a parallel card). It acts only on `terminal`, `execute_code`, `search_files` and `browser_exec`, and only when the output text is longer than 2,000 and at most 100,000 characters. It never changes `read_file` or `kanban_*` results. It saves the full output under `<HERMES_HOME>/cache/jev` with mode 0600 before changing anything, splits the output into chunks of 10 lines (at most 500 characters), asks Jev one yes-or-no question per chunk in one request, keeps the first chunk, the last chunk and every chunk with probability 0.6 or more, and replaces each run of removed chunks with one line that gives the number of removed lines and the saved file path. If the kept text is 90% of the original or more, or the format is not recognised, or anything fails, the result is unchanged. A result of a little more than 2,000 characters gives at least 4 chunks, because a result with fewer than 3 chunks is never changed. A later `read_file` of a saved file writes a `saved_read` record.

Every `tool_results` record of a result that Jev answered for has `chunk_probabilities`: the probability of each chunk, as a list of numbers in chunk order (the first number is chunk 1). With these numbers the effect of another `keep_threshold` value can be computed from the log.

Number of questions per request (checked on card `t_df87b851`): TypeSafe sets no limit on the number of questions in one request ("There is no limit on the number of questions in a request. What limits a request is its size", https://docs.typesafe.ai/primitives.md, section "How many questions you can ask"; the OpenAPI schema https://api.typesafe.ai/openapi.json gives `questions` a `minProperties` of 1 and no maximum). The limits are 64k tokens per request and 32k tokens per question, which counts the state and that question (https://docs.typesafe.ai/models.md, `jev-1.14.0`). Therefore no rule enlarges the chunks of a large result. Measured through `plugins/jev/jev_client.py` with synthetic output on 2026-11-13: 5 chunks (2,000 characters) 332 ms, 22 chunks 346 ms, 44 chunks 378 ms, 110 chunks (50,000 characters, 25,632 input tokens) 552 ms, and 300 questions about a 2,000-character state 462 ms; the time grows with the input tokens, not with the number of questions, and stays far below the 5-second timeout. A 100,000-character output was refused with HTTP status 400 with 220 chunks, with 52 chunks of the earlier size and with one question, so the limit is the size of the state, not the number of questions. With text like the synthetic test output (about one token for two characters), an output of more than about 60,000 characters exceeds the 32k tokens per question; Jev then returns HTTP status 400 and the result stays unchanged (`reason` `jev_error`, `error_class` `HTTPError`). `max_chars` (`100000`) is above that size; card `t_df87b851` did not change it.

## Logs and report

Logs are JSON Lines files in `/Users/chanbla11mit/.hermes/jev/logs` (one directory for every profile; `HERMES_JEV_LOG_DIR` overrides it in tests), files mode 0600, directory mode 0700. Every record has `ts` (ISO 8601 with offset) and `profile`; unknown values are `null`. Records contain identifiers, sizes, counts, probabilities, timings and token counts only, never card text, tool output or message text.

- `decisions.jsonl`: `event` (`route`, `hold`, `release`, `toggle`, `clear_override`, `escalate`, `switch_error`, `read_error`), `board`, `task_id`, `original_assignee`, `new_assignee`, `orchestrator_model`, `route`, `probabilities`, `confidence`, `applied`, `not_applied_reason` (`routing_disabled`, `board_not_configured`, `single_route`, `jev_error`, `model_set`, `assignee_not_listed`, `below_threshold`, `no_glm_workers`, `control_group`, `create_failed`, `plugin_error`, `task_id_not_recognized`, `no_claude_workers`), `jev_latency_ms`, `jev_input_tokens`, `error_class`, `held_until`. A `toggle` record also has `enabled` and `changed_by`; an `escalate` record also has `change_requests` (the number of `changes_requested` events of the card) and, when the reassignment worked, `assigned_worker_line` (`rewritten`, `no_line`, `failed`) and `assigned_worker_line_error_class`. A board name or assignee that is not in the configuration is logged as `null`, a `model` argument that is not in `routing.known_models` or a route as `unrecognized`, and a task ID from tool arguments that does not have the Hermes form `t_<hexadecimal digits>` as `null`.
- `tool_results.jsonl`: `event` (`filter`, `saved_read`), `session_id`, `tool`, `chars_before`, `chars_after`, `chunks_kept`, `chunks_total`, `jev_latency_ms`, `jev_input_tokens`, `action` (`filtered`, `unchanged`, `skipped`), `reason`, `error_class`, `saved_file`, `chunk_probabilities` (list of numbers in chunk order; `null` when Jev did not answer).
- `auxiliary.jsonl`: `aux_task`, `provider`, `model`, `input_tokens` (input plus cache read and cache write tokens), `output_tokens`, `status` (`ok`, `error`, `streaming`).

`scripts/jev-report` (written by a parallel card) reads these logs and the Kanban run history and prints the results per route, per tool and per auxiliary task, and the total Jev input tokens and cost (see "Report of Claude tokens saved, and the owner notification before a route is turned off").

## Report of Claude tokens saved, and the owner notification before a route is turned off

Deployment time of the routing change: `2026-11-13T23:23:38+09:00`, the time at which card `t_7e73d1b4` ended the install of commit `0db3667ba3ee03fdc174b525f0c4abd34e08492d` on the last of the 31 profiles. Use it for `<deployment time>` below.

`/Users/chanbla11mit/hermes-local-harness/scripts/jev-report` is read-only. Run it with the deployment time of the routing change:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-report --after <deployment time>

Section 1 prints, for every card with a route record, the tokens of all sessions of all its runs (worker runs and reviewer runs, from the state database of every profile, including subagent sessions), with Claude tokens and GLM tokens on separate lines. The block "Claude tokens saved by GLM routing" compares two groups of done cards that have at least one linked session (it prints the number of done cards without a linked session): cards with an applied `easy` or `medium` route, and control cards of the same route (route records with `not_applied_reason` `control_group`). It prints the comparison per board and route and per route over all boards: saved = (mean Claude tokens per control card - mean Claude tokens per GLM-routed card) x number of GLM-routed cards. A card that was moved to a Claude worker after 5 change requests stays in the GLM-routed group.

For each route over all boards, the report prints `route <route>: disable this route: owner permission required` when saved is zero or negative with at least 10 GLM-routed cards and at least 3 control cards. The report changes no setting. Turning off the route still needs the owner's permission (see "Route disabling needs the owner's permission").

`/Users/chanbla11mit/hermes-local-harness/scripts/jev-route-notice` runs the same calculation. When the report has a rule line for a route that is on, it prints one message text: the route, the saved figure, the two mean values and the two card counts; the text asks the owner for permission and states that the route stays on until the owner answers. Without such a rule line it prints nothing. It reads the settings file `plugins/jev/config.json` of the checkout that holds the script (for the scheduled job below, `/Users/chanbla11mit/hermes-local-harness/plugins/jev/config.json`), read only, and sends no message for a route that no board still offers (`routing.enabled` false, or on every board the route is absent or disabled, fewer than two routes are enabled, or the worker list named by the route's `assignee_from` is empty), so the weekly message for a route stops once its disabling is in that file; when the file cannot be read, every route counts as on and the message is still sent.

Card `t_7e73d1b4` created the scheduled job "jev route notice" of `harness-orchestrator` on 2026-11-13 with the owner's authorization (planned on card `t_e5f9a323`, run 357): job ID `1dae3956324f`, schedule `0 9 * * 1` (Monday 09:00 KST), delivery target `telegram:8303859998` (the owner's direct-message chat with the `harness-orchestrator` bot), created with `--no-agent`, so it makes no model call, running `/usr/bin/python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-route-notice --after <deployment time>` through the wrapper file `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/scripts/jev_route_notice.py`. A `--no-agent` job delivers non-empty standard output as one message and treats empty standard output as a silent run, so when a rule line is present the owner receives one Telegram message through the `harness-orchestrator` bot, and a week without a rule line sends nothing. After an owner statement that names the route, `harness-orchestrator` sets that route's `enabled` to false in `/Users/chanbla11mit/hermes-local-harness/plugins/jev/config.json`, installs it by the procedure above ("Install on a profile"), and reports the change to the owner. Without such a statement nothing changes.

## Rollback

1. Turn off a single part at once in the installed `config.json` (read at every call, no restart):
   - control group: `routing.control_group_every` `0`;
   - reassignment after change requests: `routing.max_glm_change_requests` `0`;
   - tool result filter: `tool_results.enabled` `false`, or the earlier values `min_chars` `8000`, `keep_threshold` `0.3`, `max_kept_ratio` `0.8`, `chunk_lines` `40`, `chunk_chars` `2000`;
   - auxiliary log: `auxiliary_log.enabled` `false`;
   - peak-hours hold: `python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off` is enough;
   - a route (its `enabled` `false`) or all routing (`routing.enabled` `false`): only after the owner has been notified with the figures and has stated permission for that route (see "Route disabling needs the owner's permission").
2. Plugin code: revert the commits and install the plugin again from the reverted commit by "Install on a profile". Routing acts only in sessions that call `kanban_create`, which are the orchestrator sessions. Removing the plugin from an orchestrator profile (`hermes -p <profile> plugins disable jev`, then the owner runs `hermes gateway restart` from a separate shell so gateway-served sessions drop it) turns off every route for the cards that orchestrator creates, so it needs the owner's permission like step 1. Removing the plugin from a worker or reviewer profile turns off no route; it turns off only what the plugin does in that profile's own sessions (for example the reassignment after change requests in a reviewer profile).
3. Before or after step 2, run `python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold off` so no card stays held, and remove the `com.nous.hermes-jev-peak-hold` LaunchAgent.
4. Cards already created on a GLM route keep their assignee and model override; reassign them with `hermes kanban --board <board> assign <id> <profile>` and `hermes kanban --board <board> set-model <id> none` if needed.
5. Keep or archive `/Users/chanbla11mit/.hermes/jev/logs` for the report.
