# jev plugin: install, settings, peak-hours hold, logs and rollback

The `jev` plugin (`/Users/chanbla11mit/hermes-local-harness/plugins/jev`, version 0.1.0) calls Jev, the decision model from TypeSafe, for two decisions, and writes logs that show whether it reduces Claude subscription token use:

- Card model routing: when an orchestrator creates a card with `kanban_create`, the plugin asks Jev whether the work is `easy`, `medium`, `hard` or `very_hard`, and moves `easy`, `medium` and `hard` cards to a GLM worker profile of the board (`easy` goes to the two workers of the list `easy_route_workers`, `<board>-worker-glm-easy-1` and `<board>-worker-glm-easy-2`, with model `glm-5.3-flash`; `medium` goes to the two workers of the list `medium_route_workers`, `<board>-worker-glm-medium-1` and `<board>-worker-glm-medium-2`, with model `glm-5.3`; `hard` goes to the two workers of the list `glm_max_workers`, `<board>-worker-glm-hard-1` and `<board>-worker-glm-hard-2`, with model `glm-5.3`; the plugin takes the two workers of each list in turn), except every tenth such card of a board and applied route, which stays with the Claude worker as a control group. A `very_hard` card is created exactly as the orchestrator asked, on the Claude worker it named.
- Reassignment after change requests: the plugin moves a card of a GLM worker to a Claude worker of the board at the third change request on a card that the plugin routed as `hard`, and at the fifth change request on any other card of a GLM worker.
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

`plugins list` prints `enabled      git pinned@<first 8 characters of the commit> 0.1.0    jev`, and `plugins/.install-metadata.json` in the profile records the source URL and the full commit. Card `t_f9262e33` installed commit `921f85b2d8987e0631b958a0026b30fa4609b40e` from the local `file://` source on all 31 profiles. Card `t_7e73d1b4` installed commit `0db3667ba3ee03fdc174b525f0c4abd34e08492d` from the same local `file://` source on the same 31 profiles on 2026-11-13. Card `t_806e0815` installed commit `485ca3e840ddc34860ee6668de2799035f4372e8` from the same local `file://` source on all 36 profiles on 2026-11-14. Card `t_ac898be6` installed commit `3f2c05524458a503955f8274f30fdefef8992976` from the same local `file://` source on all 36 profiles on 2026-11-14, where the install on the last profile, `harness-orchestrator`, ended at 18:20:48 Asia/Seoul time (UTC+09:00), and the same card deployed the five orchestrator skill files of card `t_c7cc3830`. Each install also makes the running gateway reload its plugins (the command prints `Gateway reloaded plugins`); this is not a gateway restart, but it does load changed plugin Python files: `hermes plugins install ... --enable` calls `activate_plugin_now` (Hermes source `hermes_cli/plugins_activation.py` lines 96 to 127), which asks the gateway that serves the profile to run its `reload-plugins` command (`gateway/run_plugin_rewire.py` lines 81 to 118). That command runs `discover_plugins(force=True)`, which first removes every registration of the profile's plugins (`hermes_cli/plugins.py` lines 1366 to 1367) and then imports each directory plugin again after it has removed `hermes_plugins.<plugin>` and all of its submodules from `sys.modules` (`hermes_cli/plugins_loader.py` lines 687 to 708). The `tool_execution` middleware and the hooks of the new code are therefore active in gateway-served sessions from the next tool call, without `hermes gateway restart`. Only plugin tools and system prompt sections wait for the next session, and the `jev` plugin has neither. When the install command prints `Restart the gateway for the plugin to take effect` instead, no gateway answered, and the owner runs `hermes gateway restart` from a separate shell. Card `t_7f89366b` installed commit `7d0d738c2e212ee573cbee9bf419e6f5dd87db4f` from the same local `file://` source on all 36 profiles on 2026-11-15, where the install on the last profile, `harness-orchestrator`, ended at 09:48:38 Asia/Seoul time (UTC+09:00), and the same card deployed the 12 policy files of card `t_e14a6d6a` (seven `SOUL.md` files and five orchestrator skill files).

Plugins load only when they are listed in the profile's `plugins.enabled` (Hermes source `hermes_cli/plugins.py` line 1481), which `--enable` does.

Profiles (51 in total; `roster.yaml` lists `jev` in `required_plugins` of exactly these, and `scripts/verify-state` checks that list):

- The 21 Claude subscription profiles: `advisor`, and the orchestrator, reviewer and two Claude workers of each of the five boards (`jobcron-orchestrator`, `jobcron-reviewer`, `jobcron-worker`, `jobcron-worker-2`, `chapt-orchestrator`, `chapt-reviewer`, `chapt-worker`, `chapt-worker-2`, `harness-orchestrator`, `harness-reviewer`, `harness-worker`, `harness-worker-2`, `jss-orchestrator`, `jss-reviewer`, `jss-worker`, `jss-worker-2`, `anki-orchestrator`, `anki-reviewer`, `anki-worker`, `anki-worker-2`). Routing has an effect in every profile that calls `kanban_create`: the orchestrators, and also workers and reviewers that create follow-up cards (see "Creating the third GLM worker profile of each board"). The `kanban_unblock` part of the peak-hours hold has an effect only in the orchestrators, because Hermes refuses `kanban_unblock` in a run that the dispatcher started (`_require_orchestrator_tool` in `/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`). The auxiliary log and the tool result filter apply in every profile.
- The thirty GLM worker profiles that the routes use, six for each board: `jobcron-worker-glm-easy-1`, `jobcron-worker-glm-easy-2`, `jobcron-worker-glm-medium-1`, `jobcron-worker-glm-medium-2`, `jobcron-worker-glm-hard-1`, `jobcron-worker-glm-hard-2`, `chapt-worker-glm-easy-1`, `chapt-worker-glm-easy-2`, `chapt-worker-glm-medium-1`, `chapt-worker-glm-medium-2`, `chapt-worker-glm-hard-1`, `chapt-worker-glm-hard-2`, `harness-worker-glm-easy-1`, `harness-worker-glm-easy-2`, `harness-worker-glm-medium-1`, `harness-worker-glm-medium-2`, `harness-worker-glm-hard-1`, `harness-worker-glm-hard-2`, `jss-worker-glm-easy-1`, `jss-worker-glm-easy-2`, `jss-worker-glm-medium-1`, `jss-worker-glm-medium-2`, `jss-worker-glm-hard-1`, `jss-worker-glm-hard-2`, `anki-worker-glm-easy-1`, `anki-worker-glm-easy-2`, `anki-worker-glm-medium-1`, `anki-worker-glm-medium-2`, `anki-worker-glm-hard-1`, `anki-worker-glm-hard-2`. Card `t_18a2dc93` (owner decision of 2026-11-16) gave the fifteen GLM worker profiles of the cards before it the names of their routes (`-glm-1` became `-glm-easy-1`, `-glm-2` became `-glm-medium-1` and `-glm-3` became `-glm-hard-1`) and added a second worker for each route (`-glm-easy-2`, `-glm-medium-2` and `-glm-hard-2`), in the repository only; until the deployment card renames and creates the live profiles, the live profiles keep the earlier names, and the records of earlier cards in this file use the names of their time. The plugin must run in these profiles so that the card's model override is cleared at the review handoff (see "Model override at the review handoff"). Card `t_55432326` created the five profiles whose names end in `-glm-3` on 2026-11-14 (steps 1 to 5 of "Creating the third GLM worker profile of each board"). The owner added their Z.ai logins on 2026-11-14 (step 6), and the controller's one model call on each of the five profiles returned `READY`. Card `t_806e0815` installed commit `485ca3e840ddc34860ee6668de2799035f4372e8` on all 36 profiles on 2026-11-14 in the order of step 7; the install on the last profile, `harness-orchestrator`, ended at 11:37:18 Asia/Seoul time (UTC+09:00). In the final check (step 8), `scripts/verify-state` printed none of the lines that step 8 lists for the five profiles.

Gateway-served sessions load the installed plugin code when the install command prints `Gateway reloaded plugins` (see above); otherwise after the owner runs `hermes gateway restart` from a separate shell. Workers and reviewers started by the dispatcher load it when they start (`hermes -p <profile> --cli ... chat -q`), because each run is a new process.

Card `t_6dafd139` on 2026-11-16 first set up the five GLM reviewer profiles `jobcron-reviewer-glm`, `chapt-reviewer-glm`, `harness-reviewer-glm`, `jss-reviewer-glm` and `anki-reviewer-glm`: it copied `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md` to `/Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md`, set `agent.reasoning_effort` to `max` with `hermes -p <profile> config set`, copied `/Users/chanbla11mit/hermes-local-harness/scripts/jev-glm-reviewer-hook` to `/Users/chanbla11mit/.hermes/profiles/<profile>/agent-hooks/jev-glm-reviewer-hook` and added that path as a `pre_tool_call` hook (matcher `kanban_complete|kanban_request_review`, `timeout` 10, `fail_closed` true) with `hermes -p <profile> config set hooks.pre_tool_call`, and added the five profiles to `kanban.dispatch_profiles` of `/Users/chanbla11mit/.hermes/config.yaml` with `/Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch add --clear-fallbacks`. The same card then installed commit `60a79fca167beb5fe37add10b79ef19eb777f0f7` from the same local `file://` source with `--force` on the 36 profiles listed above and on the five GLM reviewer profiles, 41 profiles in total; the installs ended from 05:43:02 to 05:46:09 Asia/Seoul time (UTC+09:00), the last on `anki-orchestrator`, and every install printed `Gateway reloaded plugins`. `routing.glm_review.enabled` stayed false in every installed `config.json`.

Card `t_e61ee47c` on 2026-11-16 set `routing.glm_review.enabled` to true in `plugins/jev/config.json` at the commit that adds this paragraph (a commit cannot contain its own ID; the card's handoff records the ID), and installed that commit from the same local `file://` source with `--force` on the same 41 profiles. Rollback is the install of commit `8845e54ebad421c4381d46f14843cbbb74492854` (value false) on the same 41 profiles by this section; a card that is in `review` with a GLM reviewer at that time is reassigned to the board's Opus reviewer by hand (`docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md` line 239).

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

   The clone copies no `auth.json`. The GLM worker profiles have no Anthropic API fallback (`procedures/anthropic-api-fallback.md`, section 1, limits it to the four Jobcron profiles and the claude-subscription profiles listed in section 8), so steps 2 to 4 remove the copied key, the copied memory files, the copied `hermes-terminal-outcome-notification` plugin and the copied fallback values, and step 3 keeps the copied `ponytail` plugin.
2. The owner removes the copied Anthropic API key from the profile's `.env`, before any other step:

        hermes -p <profile> config unset ANTHROPIC_API_KEY

   The command prints `✓ Unset ANTHROPIC_API_KEY from <path of the profile .env>` and no key value (`procedures/anthropic-api-fallback.md`, section 7, step 3). Then `hermes -p <profile> auth list anthropic` must list no entry with source `env:ANTHROPIC_API_KEY`. Nobody else opens or changes the profile's `.env`.
3. Delete the two copied memory files, as `procedures/manual-apply.md` requires for a cloned profile, and remove the copied `hermes-terminal-outcome-notification` plugin, because the roster entry declares `installed_disabled_plugins` `[]`:

        rm /Users/chanbla11mit/.hermes/profiles/<profile>/memories/MEMORY.md /Users/chanbla11mit/.hermes/profiles/<profile>/memories/USER.md
        hermes -p <profile> plugins remove hermes-terminal-outcome-notification

   Without the plugin removal, `scripts/verify-state` prints `WARN: dormant unexpected plugin <profile>: hermes-terminal-outcome-notification`.

   Keep the copied `ponytail` plugin, because every GLM worker profile of the five boards lists `ponytail` in `required_plugins` in `roster.yaml`. Run the Ponytail steps of `procedures/manual-apply.md`, section 3b, for the new profile: the enable command, the `.env` line command and the verification command with its expected output.
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

   The first command must print the line of `jev` with the status `enabled`, and the same plugin lines as `hermes -p <source> plugins list --plain --no-bundled`. The two directory listings must be equal: only the plugins of `<source>` are present. The copied `jev` is the commit that is installed in `<source>`, whose `config.json` names only two GLM workers per board. The plugin in a GLM worker clears the card's model override at the review handoff only when the profile's own name is among the `glm_workers` of its installed `config.json` (`/Users/chanbla11mit/hermes-local-harness/plugins/jev/routing.py`, `handle_request_review`), and the plugin in a reviewer moves a card to a Claude worker after the third change request on a card that the plugin routed as `hard`, and after the fifth change request on any other card, only when the card's assignee is among the board's `glm_workers` of the reviewer's installed `config.json` (`handle_request_changes`). Do not install the reviewed commit in this step; step 7 installs it, first on the five new profiles and the five reviewers.
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

## Renaming the GLM worker profiles and creating the second worker of each route

Card `t_aabef2e4` wrote this section in the repository only and ran none of its steps. The deployment card (its ID is `<card id>` below) runs the live steps D0 to D10 in the order given, with the owner's authorization. Source: `/Users/chanbla11mit/hermes-local-harness/docs/specs/261116-glm-worker-profiles-by-route-and-claude-fallback.md` (card `t_6957cef4`): section 2 (`hermes profile rename`), section 5 (fallback to the Claude subscription), section 7 (steps D0 to D10) and the open questions Q1 to Q5 of section 9. The owner answered the open questions in a Telegram direct message to `harness-orchestrator` on 2026-11-16: "1. Yes 2. Yes 3. Yes 4. Yes 5. Yes, that's ok. I approve the GLM doubling deployment D0 to D10, with yes to questions 1, 2 and 3." The steps below include these answers:

- Q1: the helper tasks of the GLM profiles get the fallback chains that card R2 declares in `roster.yaml`: the light helper tasks (`LIGHT_HELPER_TASKS` of `/Users/chanbla11mit/hermes-local-harness/scripts/verify-state`: `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub` and `vision`) fall back to `claude-subscription` `claude-haiku-5-5`, and the other helper tasks to the profile's own fallback model (step D6).
- Q2: step D3 also adds `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` to each GLM profile `.env` that does not have it, copied without printing from the same source `.env` as the two path lines. The four anki GLM profiles already have it.
- Q3: the owner approved deploying the changed SOULs of the five Opus reviewers, the five GLM reviewers, the five orchestrators and the 30 GLM workers, and the orchestrator skills of `anki`, `chapt`, `jobcron` and `jss` (steps D2, D4 and D7). Step D9 deploys the harness-orchestrator skill (owner decision 5 of the specification).
- Q4: the disabled cron job `94d7b3d1dc19` "Jobcron emergency autonomous deployment controller" in `/Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/cron/jobs.json` names `jobcron-worker-glm-1` and `jobcron-worker-glm-2` in its prompt. It is outside this procedure: board `jobcron` handles it, and this harness deployment does not read or change it.
- Q5: card creation does not stop during the deployment. A card that is created from D1 step 4 to D8 and routed to an old name by the `jev` configuration that is installed at that time is moved afterwards by D2a and by the repeated check of D2a in D8 step 4 and in D10.

Names. The 15 old names and their new names (`hermes profile rename`), on every board prefix `jobcron`, `chapt`, `harness`, `jss` and `anki`: `<prefix>-worker-glm-1` becomes `<prefix>-worker-glm-easy-1`, `<prefix>-worker-glm-2` becomes `<prefix>-worker-glm-medium-1` and `<prefix>-worker-glm-3` becomes `<prefix>-worker-glm-hard-1`. The 15 copies: `<prefix>-worker-glm-easy-2` from `<prefix>-worker-glm-easy-1`, `<prefix>-worker-glm-medium-2` from `<prefix>-worker-glm-medium-1` and `<prefix>-worker-glm-hard-2` from `<prefix>-worker-glm-hard-1`. The five GLM reviewers keep their names. Board names: prefix `chapt` is board `cha-pt` and prefix `jss` is board `jss-genr`; the other prefixes are also the board names.

Placeholders and directories:

- `<integrated commit>`: the full commit of local `main` of `/Users/chanbla11mit/hermes-local-harness` that holds cards R1 (`t_18a2dc93`), R2 (fallback declarations), R3 (`scripts/jev-report` and `previous_names`) and R4 (this section), each approved by its reviewer. Before D0, `git -C /Users/chanbla11mit/hermes-local-harness rev-parse HEAD` prints this commit and `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain` prints nothing. Every file that a step copies comes from this checkout, and `/Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model` reads `/Users/chanbla11mit/hermes-local-harness/roster.yaml` of this checkout (option `--roster`, default the checkout of the script), so the fallback declarations of R2 must be in it before D1.
- `/Users/chanbla11mit/.hermes/backups/<card id>`: the backup directory of the deployment. D1 step 1 creates it with mode 0700. Every backup and every card list of this procedure is written there and not to the scratch directory of a profile, because Hermes removes scratch entries that were not used for 24 hours, and the card list of D1 step 6 is still needed after the deployment (D2a step 3). A backup of the plugin `claude-subscription` must never be placed in `plugins/model-providers/` of a profile: Hermes imports every directory there as a model provider plugin (`providers/__init__.py`, `_user_plugins_dir` lines 297 to 305, and `_scan_home_layer` from line 359).
- `<date>`: the date of the rename in the form `2026-11-16`.

Local `main` already held card R1 when this section was written: merge commit `c91e172f9a19adb6a5964852ec10c2397d231f8a` (2026-11-16). The `com.nous.hermes-jev-peak-hold` LaunchAgent runs `/Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply` of the main checkout, and that script reads `plugins/jev/config.json` of the same checkout (`scripts/jev-peak-hold` lines 70 and 304). Since that merge the LaunchAgent therefore reads the 30 new names, and it holds in the peak hours only `ready` and `todo` cards that are assigned to a GLM worker named in that file (`scripts/jev-peak-hold` lines 5 to 7; `plugins/jev/peak_hold.py`, `glm_workers_by_board` and `all_glm_workers`). Until D2a moves them, cards that are assigned to an old name are not held in the peak hours.

Fallback to the Claude subscription. After step D6 every GLM worker profile and every GLM reviewer has the `fallback_providers` entry of card R2: `claude-subscription` `claude-haiku-5-5` on the ten workers of the route `easy`, `claude-subscription` `claude-sonnet-5-5` on the twenty workers of the routes `medium` and `hard` and on the five GLM reviewers; the `anthropic` provider is never used. The fallback starts when a Z.ai call fails with the quota error that was observed on 2026-11-13 (HTTP 429, code `1308`, "Usage limit reached for 5 hour"): Hermes classifies it as `billing` (`agent/error_classifier.py`, `_status_429`, lines 1049 to 1078; `rate_limit` if the response has a reset header), and for both reasons it switches to the first fallback entry at the first error of the call, without a retry (`agent/turn_recovery.py` lines 1666 to 1680 and 1884 to 1921). The switch comes later only while the credential pool can rotate to another available Z.ai entry (`_pool_may_recover_from_rate_limit`, `run_agent.py` lines 217 to 224), and a Z.ai overload 429 switches only after two retries (`agent/turn_recovery.py` lines 1899 to 1908). A card model override such as `-m glm-5.3-flash --provider zai` does not remove the chain: the CLI reads `fallback_providers` from the profile configuration whatever model it was started with (`hermes_cli/cli_init_mixin.py` line 295). The fallback lasts for the rest of the run: Hermes returns to the primary model only at the start of the next turn (`agent/agent_runtime_helpers.py` lines 1426 to 1434), and a worker that the dispatcher starts runs one `chat -q` turn; the next run of the same card starts on `zai` again. A fallback run still counts as the GLM worker profile for the `jev` rules, because every rule selects by the profile name in `HERMES_PROFILE` (`plugins/jev/jev_log.py` lines 44 to 52) and by the lists in `config.json`, never by the model: the card is held in the peak hours, its model override is cleared at the review handoff, it is counted against the change request limit of its route, and its first review is by the board's GLM reviewer. The provider takes its reasoning effort from `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` in the profile `.env` (step D3), not from `agent.reasoning_effort`, and the helper tasks use the `auxiliary.<task>.fallback_chain` entries of step D6. The Claude tokens of a fallback run lower the saving that `/Users/chanbla11mit/hermes-local-harness/scripts/jev-report` shows: the report sorts tokens by model family (`model_family`), so they count as Claude tokens of a card that was moved to a GLM worker.

Who runs the steps on other boards. A worker that the Kanban dispatcher starts can read and change the cards of its own board only. Run 596 of card `t_fb32c24a` (2026-11-16) stopped at D1 step 2 and recorded this cause (comment 547 on `t_fb32c24a`): in the terminal of a dispatched worker, Hermes sets `HERMES_DELEGATED_CHILD_CONTEXT` and `HERMES_KANBAN_DB`, so `hermes kanban --board <board> list` exits 1 with `delegate_task child contexts cannot mutate Kanban tasks or boards`, and `--board <board>` does not reach another board. The Hermes source agrees: `agent/delegation_context.py` lines 122 to 137 and 173 to 184 set the marker for the processes of a dispatched worker; the check that refuses the mutation is `agent/delegation_context.py` lines 141 to 162 (the error is raised at `hermes_cli/kanban_db.py` line 150); the dispatcher sets the board database and the board slug of a worker at `hermes_cli/kanban_db_dispatch.py` lines 2924 and 2929; and the module comment of `hermes_cli/kanban_db.py` lines 4 to 9 states that such a worker cannot see other boards. The steps of this section that read or change cards of the boards `jobcron`, `cha-pt`, `harness`, `jss-genr` and `anki` are run by `harness-orchestrator` from its own session, and each one is recorded in a comment on the deployment card. In deployment part A (`t_fb32c24a`) these are D1 steps 2, 3, 5, 6 and 7 and D2a steps 1 and 2 with the check of D2a (comments 548, 549, 551, 552 and 555). In deployment part B (`t_653b7074`) these are D8 step 4 and the card check of D10 (the program with `d10`, and D2a steps 1 and 2 where it lists a card) (comment 561). The worker runs every other step. The owner decision of 2026-11-16, given in a Telegram direct message to `harness-orchestrator`, reads: "You (harness-orchestrator) run the card reads, moves and comments on the five boards from your session. The worker does the renames, policy texts, .env lines and copies. No Hermes limit is removed." A deployment card is split so that the worker does not block the card for these steps, because Hermes moves a card to `triage` when its block recurrence count reaches `BLOCK_RECURRENCE_LIMIT`, which is 2 (`hermes_cli/kanban_db.py` line 114). A block whose kind equals the kind of the previous block of the card raises the count, and a planned block counts as well (lines 3402 to 3408; the count survives an unblock, line 3745). Run 597 of `t_fb32c24a` was such a planned block, of kind `needs_input`, and Hermes moved the card to `triage` at 15:41 KST on 2026-11-16 (event 11985, `block_loop_detected`, recurrences 2).

Reading the cards of the old names. Steps D1, D2a, D8 and D10 use this program. It changes nothing on the boards: it calls `hermes kanban --board <board> list --json` (`hermes_cli/kanban_parser.py` lines 234 to 248; without `--archived` the list has no archived card) and, for each card that is not `done`, `hermes kanban --board <board> show <task id> --json` (`hermes_cli/kanban.py` lines 473 to 497; the `events` field has `kind` and `payload`). It writes one file with the board, the task ID, the status, the assignee, the `implementer` of the latest `review_requested` event and whether the card already has the comment of D2a step 2, for every card whose assignee is an old name and every card whose latest `review_requested` event names an old implementer. It prints one line with the cards of conditions (a) and (b) of D1 step 3 and the cards that are assigned to an old name. Replace `<step>` with the step that runs it, for example `d1-2`:

    python3 - /Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-<step>.json <<'EOF'
    import json, re, subprocess, sys
    OLD = re.compile(r"^(jobcron|chapt|harness|jss|anki)-worker-glm-[123]$")
    BOARDS = ("jobcron", "cha-pt", "harness", "jss-genr", "anki")
    def kanban(board, *args):
        out = subprocess.run(["hermes", "kanban", "--board", board, *args, "--json"],
                             check=True, capture_output=True, text=True).stdout
        return json.loads(out)
    def payload(event):
        value = event.get("payload") or {}
        return json.loads(value) if isinstance(value, str) else value
    cards = []
    for board in BOARDS:
        for task in kanban(board, "list"):
            if task["status"] == "done":
                continue
            shown = kanban(board, "show", task["id"])
            requested = sorted((e for e in shown["events"] if e["kind"] == "review_requested"),
                               key=lambda e: e["created_at"])
            implementer = payload(requested[-1]).get("implementer") if requested else None
            if OLD.match(task["assignee"] or "") or OLD.match(implementer or ""):
                cards.append({"board": board, "id": task["id"], "status": task["status"],
                              "assignee": task["assignee"], "implementer": implementer,
                              "renamed_comment": any(" was renamed to " in (c["body"] or "")
                                                      for c in shown["comments"])})
    with open(sys.argv[1], "w") as f:
        json.dump(cards, f, indent=1)
    running = [c["id"] for c in cards if c["status"] == "running" and OLD.match(c["assignee"] or "")]
    review = [c["id"] for c in cards if c["status"] == "review" and OLD.match(c["implementer"] or "")]
    assigned = [c["id"] for c in cards if OLD.match(c["assignee"] or "")]
    print(f"cards {len(cards)}; (a) running on an old name: {running}; "
          f"(b) in review with an old implementer: {review}; assigned to an old name: {assigned}")
    EOF

The `implementer` of a `review_requested` event is the profile of the card's latest run (`hermes_cli/kanban_db.py` lines 3498 to 3506). A change request reads the `implementer` of the latest `review_requested` event (lines 3602 to 3607) and writes it as the assignee (line 3617), and `reopen_review_task` does the same (lines 3768 to 3797). A card in `review` has its reviewer as its assignee, so a wait that reads only the assignee does not see a card in `review` whose implementer is an old name. `unblock_task` returns a card that was blocked from `review` to `review` (`hermes_cli/kanban_db.py` lines 3724 to 3744, line 3742), so such a card can return to an old name long after the rename.

### D0. Smoke test of `claude-sonnet-5-5`

This uses the method of `procedures/haiku-helper-routing.md` step 4a and a temporary `HERMES_HOME`, so it changes no live state. Run it once:

    python3 /Users/chanbla11mit/hermes-local-harness/plugins/model-providers/claude-subscription/smoke.py --cli /Users/chanbla11mit/.hermes/runtimes/claude-code/2.1.302/claude --model claude-sonnet-5-5

- Check: the output is `SMOKE PASS cli=2.1.302 model=claude-sonnet-5-5`. On `SMOKE FAIL: <reason>`, stop and record the reason; no later step runs.
- Rollback: none, because nothing changes.

### D1. Back up, let the existing runs finish, then stop new runs on the old names

The dispatcher starts a card only when its assignee is in `kanban.dispatch_profiles` and the profile exists (`_gated`, `hermes_cli/kanban_db_dispatch.py` lines 1685 to 1690). For any other assignee it records `skipped_nonspawnable` and starts nothing (lines 2049 to 2064). After the old names leave the list, a `ready` card on an old name is never started: also not a `scheduled` card that the peak hold releases to `ready`, and not a card that a change request returns. A wait for zero cards that are assigned to an old name could therefore not end after that removal, so this step does not wait for it; step D2a moves those cards. `rename_profile` has no check for a running Kanban worker of the profile (specification section 2), so the rename waits for the runs instead. Until D7 the reviewers have their old SOULs, which name the old implementation profiles, so they accept a card whose implementer is an old name.

1. Create the backup directory and back up the dispatch list:

        mkdir -p -m 700 /Users/chanbla11mit/.hermes/backups/<card id>
        cp -p /Users/chanbla11mit/.hermes/config.yaml /Users/chanbla11mit/.hermes/backups/<card id>/config.yaml

2. Record the cards, read only: run the program of "Reading the cards of the old names" with `<step>` `d1-2`.
3. Let the existing runs finish while the 15 old names stay in `kanban.dispatch_profiles`. Run the program again every 5 minutes (`<step>` `d1-3`), and wait until both of these hold on every board:
   - (a) No card has status `running` with an old name as its assignee.
   - (b) No card in `review` has an old name as the `implementer` of its latest `review_requested` event.

   Cards in `ready`, `todo`, `scheduled`, `triage` or `blocked` that are assigned to an old name may remain; step D2a moves them. While the old names are in the list the dispatcher starts `ready` cards on them, so this wait has no fixed end. The deployment card may stop it after a time limit that it records in a comment on its own card, and go on to step 4. The wait of step 5 has no time limit.
4. Remove the 15 old names from `kanban.dispatch_profiles`, one at a time. Preview each command with `--dry-run` added first. The script writes the dispatch entry only together with `--to` (`scripts/switch-profile-model` lines 160 to 162); `--to glm` writes the model, provider and helper tasks that the profile already has, and the script backs up the profile's `config.yaml` to `config.yaml.pre-switch-<time>` in the profile directory first (line 208). After this the dispatcher starts no new run on these names (`kanban_db_dispatch.py` lines 1690 and 2049 to 2064):

        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-1 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-2 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-3 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-1 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-2 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-3 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-1 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-2 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-3 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-1 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-2 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-3 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-1 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-2 --to glm --dispatch remove
        python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-3 --to glm --dispatch remove

   The script also writes the profile's model and provider into `/Users/chanbla11mit/hermes-local-harness/roster.yaml`; the roster declares no entry for an old name after R1, so the script prints `roster: <old name> is not declared in ...; no roster change`, and `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain` stays empty.
5. Run the program again (`<step>` `d1-5`) and repeat it every 5 minutes until (a) and (b) hold on every board. A run can start between the last reading of step 3 and step 4, so the result of step 3 alone is not enough. This wait ends, for these reasons:
   - After step 4 no run starts on an old name, so no new `review_requested` event names an old implementer.
   - A running run ends, at the latest when it reaches its runtime limit.
   - A card in `review` leaves `review` when its reviewer approves it (`done`), requests changes (the card returns to `ready` on the old name and waits for D2a), or blocks it. A card that is blocked from `review` stays in the file of step 6, and step D2a handles it.
6. Write the card list again from new readings (`<step>` `d1-6`). Cards that changed status, and cards that were created since step 2, are then in it. The file `/Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-d1-6.json` is the card list of D2a, D8 step 4, D10 and the check after the deployment.
7. Count the notification subscriptions that name an old name, read only:

        sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/jobcron/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"
        sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/cha-pt/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"
        sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/harness/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"
        sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/jss-genr/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"
        sqlite3 -readonly /Users/chanbla11mit/.hermes/kanban/boards/anki/kanban.db "SELECT COUNT(*) FROM kanban_notify_subs WHERE notifier_profile LIKE '%-worker-glm-%'"

   If a count is not 0, stop and ask the owner.

- Check: the program of step 5 prints `(a) running on an old name: []` and `(b) in review with an old implementer: []`. `grep -c -- '-worker-glm-[123]$' /Users/chanbla11mit/.hermes/config.yaml` gives 0. The file `/Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-d1-6.json` exists.
- Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/config.yaml /Users/chanbla11mit/.hermes/config.yaml`. This returns the 15 old names to the dispatch list; use it only while the old profiles exist (before D2, or after the D2 rollback).

### D2. Rename the 15 profiles

Run the commands one at a time, and check the output of each before the next:

    hermes profile rename jobcron-worker-glm-1 jobcron-worker-glm-easy-1
    hermes profile rename jobcron-worker-glm-2 jobcron-worker-glm-medium-1
    hermes profile rename jobcron-worker-glm-3 jobcron-worker-glm-hard-1
    hermes profile rename chapt-worker-glm-1 chapt-worker-glm-easy-1
    hermes profile rename chapt-worker-glm-2 chapt-worker-glm-medium-1
    hermes profile rename chapt-worker-glm-3 chapt-worker-glm-hard-1
    hermes profile rename harness-worker-glm-1 harness-worker-glm-easy-1
    hermes profile rename harness-worker-glm-2 harness-worker-glm-medium-1
    hermes profile rename harness-worker-glm-3 harness-worker-glm-hard-1
    hermes profile rename jss-worker-glm-1 jss-worker-glm-easy-1
    hermes profile rename jss-worker-glm-2 jss-worker-glm-medium-1
    hermes profile rename jss-worker-glm-3 jss-worker-glm-hard-1
    hermes profile rename anki-worker-glm-1 anki-worker-glm-easy-1
    hermes profile rename anki-worker-glm-2 anki-worker-glm-medium-1
    hermes profile rename anki-worker-glm-3 anki-worker-glm-hard-1

With the live gateway the rename takes the multiplexer path: it stops serving the old name before the move and serves the new name after it, and the gateway migrates the session identity (`hermes_cli/profiles.py` lines 2484 to 2487 and 2538 to 2542; `hermes_cli/profile_identity.py` lines 195 to 215). The whole directory moves with one `rename` (line 2499), so `auth.json` with the Z.ai login, `.env`, `config.yaml`, `SOUL.md`, `skills/`, `plugins/`, `memories/`, `sessions/` and `state.db` move with it, and `profile.yaml` records the old name in `previous_names` (lines 2431 to 2443 and 2517), which card R3 reads. Do not restart the gateway while a Kanban worker runs, because the dispatcher runs in the gateway process.

Then back up the SOUL of each renamed profile and replace it:

    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-easy-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-easy-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-medium-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-medium-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-hard-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-hard-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-easy-1 && cp -p /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-easy-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-medium-1 && cp -p /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-medium-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-hard-1 && cp -p /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/chapt-worker-glm-hard-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-easy-1 && cp -p /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-easy-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-medium-1 && cp -p /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-medium-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-hard-1 && cp -p /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/harness-worker-glm-hard-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-easy-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-easy-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-medium-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-medium-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-hard-1 && cp -p /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/jss-worker-glm-hard-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-easy-1 && cp -p /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-easy-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-medium-1 && cp -p /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-medium-1/SOUL.md
    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-hard-1 && cp -p /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/anki-worker-glm-hard-1/SOUL.md

    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-easy-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-medium-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-1/SOUL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-hard-1/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-1/SOUL.md

The three Jobcron GLM workers have no SOUL source in this repository (see "Attachment and diff procedure of the GLM workers"). Write each one from its backup with the profile name and the worker number replaced, by the method of "Creating the third GLM worker profile of each board", step 3:

    sed -e 's/jobcron-worker-glm-1/jobcron-worker-glm-easy-1/g' -e 's/implementation worker 1/implementation worker easy-1/g' /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-easy-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/SOUL.md
    sed -e 's/jobcron-worker-glm-2/jobcron-worker-glm-medium-1/g' -e 's/implementation worker 2/implementation worker medium-1/g' /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-medium-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/SOUL.md
    sed -e 's/jobcron-worker-glm-3/jobcron-worker-glm-hard-1/g' -e 's/implementation worker 3/implementation worker hard-1/g' /Users/chanbla11mit/.hermes/backups/<card id>/jobcron-worker-glm-hard-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/SOUL.md

The fallback sentence that card R2 adds to the SOUL sources of the other boards is not in these three files, because they have no repository source.

- Check: each command prints `✓ Renamed <old name> → <new name>` (`hermes_cli/profiles.py` line 2508) and does not print `⚠ Profile was renamed, but the live gateway could not migrate session identity` (`hermes_cli/profile_identity.py` line 211). If it prints that warning, stop the rename sequence; after all Kanban workers have ended, restart the gateway, then run `hermes profile migrate-identity <old name> <new name>` as the warning says. `hermes profile list` shows the 15 new names and none of the old names. `python3 -c 'import json; print(sorted(n for n in json.load(open("/Users/chanbla11mit/.hermes/gateway_state.json"))["served_profiles"] if "-worker-glm-" in n))'` prints the 15 new names and none of the old names. For each new name, `ls /Users/chanbla11mit/.hermes/profiles/<new name>/auth.json` prints the path, and `grep -c '<old name>' /Users/chanbla11mit/.hermes/profiles/<new name>/profile.yaml` gives at least 1. `shasum -a 256` of each of the twelve copied SOULs equals that of its source. `diff /Users/chanbla11mit/.hermes/backups/<card id>/<new name>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<new name>/SOUL.md` of each Jobcron profile shows only the two replacements, and `grep -c -E 'jobcron-worker-glm-[123]([^0-9]|$)' /Users/chanbla11mit/.hermes/profiles/<new name>/SOUL.md` gives 0.
- Rollback: for each renamed profile, `hermes profile rename <new name> <old name>`, then `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/<new name>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<old name>/SOUL.md`. Then the D2a rollback, and the D1 rollback if the old names are to run again.

### D2a. Move the cards of the old names to the new names

Start this step directly after D2. Run the program of "Reading the cards of the old names" with `<step>` `d2a`.

1. Move each card of `/Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-d2a.json` whose assignee is an old name and whose status is not `running` and not `review`, to the new name of its assignee (`<prefix>-worker-glm-1` to `<prefix>-worker-glm-easy-1`, `-2` to `-medium-1`, `-3` to `-hard-1`):

        hermes kanban --board <board> assign <task id> <new name>

   (`hermes_cli/kanban_parser.py` line 251). `assign_task` refuses only a card that is `running` under a claim (`hermes_cli/kanban_db.py` lines 1634 to 1638); after D1 no such card remains on an old name. A new assignee starts with a failure count of 0 (lines 1639 to 1643). Do not move a card in `review`: its assignee is its reviewer.
2. Add one comment to each card of `/Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-d1-6.json` and of `/Users/chanbla11mit/.hermes/backups/<card id>/old-name-cards-d2a.json`, once for each card, both the moved cards and the cards that only have an old implementer. A card whose `renamed_comment` is true in the newer file already has it:

        hermes kanban --board <board> comment <task id> "Profile <old name> was renamed to <new name> by hermes profile rename on <date> (deployment card <card id>). The name <old name> in the card body and in earlier events is the same profile."

   (`hermes_cli/kanban_parser.py` lines 280 to 284). Card bodies name the assigned worker exactly, and the worker SOULs and, after D7, the reviewer SOULs treat a different profile name as a boundary mismatch, so the comment records the rename in the card history.
3. A card with an old implementer that is still `blocked`, or that returns to `review` later (`unblock_task`, `hermes_cli/kanban_db.py` line 3742), returns to the old name when its reviewer requests changes (line 3617), and the dispatcher records `skipped_nonspawnable` for it, because the profile does not exist (`kanban_db_dispatch.py` lines 2049 to 2064). Steps 1 and 2 are therefore repeated in D8 step 4 and in D10, and, after the deployment, after each change request on a card of the list, until the program prints no card that is not `done` or archived.

The moved cards start only after D6 adds the new names to `kanban.dispatch_profiles`.

- Check: the program run again with `<step>` `d2a-check` prints `assigned to an old name: []`. `hermes kanban --board <board> show <task id> --json` of each card of both files shows the comment in `comments`.
- Rollback: after the D2 rollback, `hermes kanban --board <board> assign <task id> <old name>` for each moved card. Comments are not removed; add one comment that records the rollback.

### D3. `.env` lines and the `claude-subscription` plugin on the renamed profiles and the GLM reviewers

Nobody opens or prints a `.env` file in this step; the commands copy whole lines between files and print only counts. The source is `/Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env` (the renamed `anki-worker-glm-1`), which has all three settings. The 16 target profiles are the twelve renamed profiles of `harness`, `chapt`, `jobcron` and `jss` and the GLM reviewers of those four boards; the four anki GLM profiles already have the three settings and are not changed.

1. Check the source: each of the three commands gives 1:

        grep -c '^HERMES_CLAUDE_SUBSCRIPTION_CLI=' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env
        grep -c '^HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE=' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env
        grep -c '^HERMES_CLAUDE_SUBSCRIPTION_EFFORT=' /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env

2. Back up the 16 `.env` files (`cp -p` keeps mode 0600):

        for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-medium-1 jobcron-worker-glm-hard-1 chapt-worker-glm-easy-1 chapt-worker-glm-medium-1 chapt-worker-glm-hard-1 harness-worker-glm-easy-1 harness-worker-glm-medium-1 harness-worker-glm-hard-1 jss-worker-glm-easy-1 jss-worker-glm-medium-1 jss-worker-glm-hard-1 jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm; do
          mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/$p && cp -p /Users/chanbla11mit/.hermes/profiles/$p/.env /Users/chanbla11mit/.hermes/backups/<card id>/$p/.env
        done

3. Append each of the settings `HERMES_CLAUDE_SUBSCRIPTION_CLI`, `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` and `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` that a target does not have. The `tail` test adds a line break first when the file does not end with one; it prints nothing:

        for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-medium-1 jobcron-worker-glm-hard-1 chapt-worker-glm-easy-1 chapt-worker-glm-medium-1 chapt-worker-glm-hard-1 harness-worker-glm-easy-1 harness-worker-glm-medium-1 harness-worker-glm-hard-1 jss-worker-glm-easy-1 jss-worker-glm-medium-1 jss-worker-glm-hard-1 jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm; do
          f=/Users/chanbla11mit/.hermes/profiles/$p/.env
          for name in HERMES_CLAUDE_SUBSCRIPTION_CLI HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE HERMES_CLAUDE_SUBSCRIPTION_EFFORT; do
            if [ "$(grep -c "^$name=" "$f")" = 0 ]; then
              [ -z "$(tail -c 1 "$f")" ] || printf '\n' >> "$f"
              grep "^$name=" /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-1/.env >> "$f"
            fi
          done
        done

4. Export the plugin of the integrated commit, and copy it to the 15 renamed profiles and the five GLM reviewers. An existing copy (on the four anki profiles) is moved to the backup directory first:

        mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/source
        git -C /Users/chanbla11mit/hermes-local-harness archive <integrated commit> plugins/model-providers/claude-subscription | tar -x -C /Users/chanbla11mit/.hermes/backups/<card id>/source
        for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-medium-1 jobcron-worker-glm-hard-1 chapt-worker-glm-easy-1 chapt-worker-glm-medium-1 chapt-worker-glm-hard-1 harness-worker-glm-easy-1 harness-worker-glm-medium-1 harness-worker-glm-hard-1 jss-worker-glm-easy-1 jss-worker-glm-medium-1 jss-worker-glm-hard-1 anki-worker-glm-easy-1 anki-worker-glm-medium-1 anki-worker-glm-hard-1 jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm; do
          live=/Users/chanbla11mit/.hermes/profiles/$p/plugins/model-providers/claude-subscription
          if [ -e "$live" ]; then mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/$p && mv "$live" /Users/chanbla11mit/.hermes/backups/<card id>/$p/claude-subscription; fi
          mkdir -p /Users/chanbla11mit/.hermes/profiles/$p/plugins/model-providers
          cp -Rp /Users/chanbla11mit/.hermes/backups/<card id>/source/plugins/model-providers/claude-subscription "$live"
        done

- Check: for each of the 20 profiles, this command prints `<profile> 1 1 1 0 600` (the three settings once each, no `ANTHROPIC_API` line, mode 0600):

      for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-medium-1 jobcron-worker-glm-hard-1 chapt-worker-glm-easy-1 chapt-worker-glm-medium-1 chapt-worker-glm-hard-1 harness-worker-glm-easy-1 harness-worker-glm-medium-1 harness-worker-glm-hard-1 jss-worker-glm-easy-1 jss-worker-glm-medium-1 jss-worker-glm-hard-1 anki-worker-glm-easy-1 anki-worker-glm-medium-1 anki-worker-glm-hard-1 jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm; do
        f=/Users/chanbla11mit/.hermes/profiles/$p/.env
        echo "$p $(grep -c '^HERMES_CLAUDE_SUBSCRIPTION_CLI=' $f) $(grep -c '^HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE=' $f) $(grep -c '^HERMES_CLAUDE_SUBSCRIPTION_EFFORT=' $f) $(grep -c '^ANTHROPIC_API' $f) $(stat -f '%Lp' $f)"
      done

  `diff -r -x __pycache__ /Users/chanbla11mit/.hermes/backups/<card id>/source/plugins/model-providers/claude-subscription /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription` prints nothing for each of the 20 profiles, and `shasum -a 256` of each copied `compat.py` equals `git -C /Users/chanbla11mit/hermes-local-harness show <integrated commit>:plugins/model-providers/claude-subscription/compat.py | shasum -a 256`.
- Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/<profile>/.env /Users/chanbla11mit/.hermes/profiles/<profile>/.env` for each of the 16 profiles. For each of the 20 profiles, `rm -rf /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription`, and on the four anki profiles `mv /Users/chanbla11mit/.hermes/backups/<card id>/<profile>/claude-subscription /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/model-providers/claude-subscription`.

### D4. Create the 15 new profiles by copy

Run this after D3, so that each copy gets the `.env` lines and the plugin of its source:

    hermes profile create jobcron-worker-glm-easy-2 --clone-from jobcron-worker-glm-easy-1
    hermes profile create jobcron-worker-glm-medium-2 --clone-from jobcron-worker-glm-medium-1
    hermes profile create jobcron-worker-glm-hard-2 --clone-from jobcron-worker-glm-hard-1
    hermes profile create chapt-worker-glm-easy-2 --clone-from chapt-worker-glm-easy-1
    hermes profile create chapt-worker-glm-medium-2 --clone-from chapt-worker-glm-medium-1
    hermes profile create chapt-worker-glm-hard-2 --clone-from chapt-worker-glm-hard-1
    hermes profile create harness-worker-glm-easy-2 --clone-from harness-worker-glm-easy-1
    hermes profile create harness-worker-glm-medium-2 --clone-from harness-worker-glm-medium-1
    hermes profile create harness-worker-glm-hard-2 --clone-from harness-worker-glm-hard-1
    hermes profile create jss-worker-glm-easy-2 --clone-from jss-worker-glm-easy-1
    hermes profile create jss-worker-glm-medium-2 --clone-from jss-worker-glm-medium-1
    hermes profile create jss-worker-glm-hard-2 --clone-from jss-worker-glm-hard-1
    hermes profile create anki-worker-glm-easy-2 --clone-from anki-worker-glm-easy-1
    hermes profile create anki-worker-glm-medium-2 --clone-from anki-worker-glm-medium-1
    hermes profile create anki-worker-glm-hard-2 --clone-from anki-worker-glm-hard-1

Without `--clone-all` the copy contains `config.yaml`, `.env` (mode 0600), `SOUL.md`, `skills/`, `memories/` and `plugins/`, and no `auth.json` (see "Creating the third GLM worker profile of each board", step 1). Then, by steps 2 to 4 of that section:

1. Delete the copied memory files:

        for p in jobcron-worker-glm-easy-2 jobcron-worker-glm-medium-2 jobcron-worker-glm-hard-2 chapt-worker-glm-easy-2 chapt-worker-glm-medium-2 chapt-worker-glm-hard-2 harness-worker-glm-easy-2 harness-worker-glm-medium-2 harness-worker-glm-hard-2 jss-worker-glm-easy-2 jss-worker-glm-medium-2 jss-worker-glm-hard-2 anki-worker-glm-easy-2 anki-worker-glm-medium-2 anki-worker-glm-hard-2; do
          rm -f /Users/chanbla11mit/.hermes/profiles/$p/memories/MEMORY.md /Users/chanbla11mit/.hermes/profiles/$p/memories/USER.md
        done

2. Replace the copied SOUL. Twelve profiles have a tracked source:

        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-easy-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-easy-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-medium-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-medium-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-hard-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/chapt-worker-glm-hard-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-easy-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-easy-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-medium-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-medium-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-hard-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/harness-worker-glm-hard-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-easy-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-easy-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-medium-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-medium-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-hard-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/jss-worker-glm-hard-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-easy-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-easy-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-medium-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-medium-2/SOUL.md
        cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-hard-2/SOUL.md /Users/chanbla11mit/.hermes/profiles/anki-worker-glm-hard-2/SOUL.md

   The three Jobcron copies are written from the SOUL of their source profile, which D2 wrote:

        sed -e 's/jobcron-worker-glm-easy-1/jobcron-worker-glm-easy-2/g' -e 's/implementation worker easy-1/implementation worker easy-2/g' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-easy-2/SOUL.md
        sed -e 's/jobcron-worker-glm-medium-1/jobcron-worker-glm-medium-2/g' -e 's/implementation worker medium-1/implementation worker medium-2/g' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-medium-2/SOUL.md
        sed -e 's/jobcron-worker-glm-hard-1/jobcron-worker-glm-hard-2/g' -e 's/implementation worker hard-1/implementation worker hard-2/g' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-1/SOUL.md > /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-hard-2/SOUL.md

3. Check the plugins of each copy against its source:

        hermes -p <new profile> plugins list --plain --no-bundled
        hermes -p <source profile> plugins list --plain --no-bundled
        ls -a /Users/chanbla11mit/.hermes/profiles/<new profile>/plugins /Users/chanbla11mit/.hermes/profiles/<source profile>/plugins

   Do not install the `jev` plugin of the integrated commit in this step; D8 does that.

- Check: the two `plugins list` outputs have the same lines, with `jev` `enabled`, and the two directory listings are equal. `ls /Users/chanbla11mit/.hermes/profiles/<new profile>/plugins/model-providers/claude-subscription` lists the plugin files. `test -e /Users/chanbla11mit/.hermes/profiles/<new profile>/auth.json || echo absent` prints `absent`. The `.env` check of D3 prints `<profile> 1 1 1 0 600` for each copy. `shasum -a 256` of each copied SOUL with a tracked source equals that of its source; for each Jobcron copy `diff` against its source profile's SOUL shows only the two replacements.
- Rollback: `hermes profile delete <new profile>` for each copy. The command asks `Type '<new profile>' to confirm:` (`hermes_cli/profiles.py`, `delete_profile`, lines 1845 to 1863); type the name. If D6 has already added the name to the dispatch list, run the D6 rollback for it first.

### D5. Owner: Z.ai login of the 15 new profiles

The owner runs these commands. Nobody else runs them or handles the key:

    hermes -p jobcron-worker-glm-easy-2 auth add zai
    hermes -p jobcron-worker-glm-medium-2 auth add zai
    hermes -p jobcron-worker-glm-hard-2 auth add zai
    hermes -p chapt-worker-glm-easy-2 auth add zai
    hermes -p chapt-worker-glm-medium-2 auth add zai
    hermes -p chapt-worker-glm-hard-2 auth add zai
    hermes -p harness-worker-glm-easy-2 auth add zai
    hermes -p harness-worker-glm-medium-2 auth add zai
    hermes -p harness-worker-glm-hard-2 auth add zai
    hermes -p jss-worker-glm-easy-2 auth add zai
    hermes -p jss-worker-glm-medium-2 auth add zai
    hermes -p jss-worker-glm-hard-2 auth add zai
    hermes -p anki-worker-glm-easy-2 auth add zai
    hermes -p anki-worker-glm-medium-2 auth add zai
    hermes -p anki-worker-glm-hard-2 auth add zai

The 15 renamed profiles keep their login, because `auth.json` moved with the directory (D2).

- Check: `ls /Users/chanbla11mit/.hermes/profiles/<new profile>/auth.json` prints the path for all 15 (no value is read). The owner then makes one model call on each new profile, `hermes -p <new profile> chat -q "Reply with exactly READY. Do not call any tools." --oneshot -Q`, which returns `READY`.
- Rollback: deleting the profile (D4 rollback) removes its login.

### D6. `fallback_providers`, helper fallback chains and `kanban.dispatch_profiles`

Before the first command of this step, D5 is complete for all 15 new profiles and D7 step 1 is done: a card that D2a moved starts as soon as its new name is in the list, and its review then needs a reviewer SOUL that names the new name.

`--apply-fallbacks` writes the `fallback_providers` and the `auxiliary.<task>.fallback_chain` of every helper task that card R2 declares in `/Users/chanbla11mit/hermes-local-harness/roster.yaml`, and refuses an invalid declaration without writing anything (`scripts/switch-profile-model` lines 181 to 189). By the owner's answer to Q1 the declaration gives each light helper task `claude-subscription` `claude-haiku-5-5` and each other helper task the profile's own fallback model. Preview each command with `--dry-run` added first; the script backs up each profile's `config.yaml`. For the 30 GLM workers, in the order of `kanban.dispatch_profiles` of `/Users/chanbla11mit/hermes-local-harness/snapshots/sanitized-current-state.yaml`; each command adds the name at the end of the list:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-easy-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-easy-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-medium-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-medium-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-hard-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-worker-glm-hard-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-easy-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-easy-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-medium-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-medium-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-hard-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-worker-glm-hard-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-easy-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-easy-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-medium-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-medium-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-hard-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-worker-glm-hard-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-easy-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-easy-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-medium-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-medium-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-hard-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-worker-glm-hard-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-easy-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-easy-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-medium-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-medium-2 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-hard-1 --to glm --dispatch add --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-worker-glm-hard-2 --to glm --dispatch add --apply-fallbacks

For the five GLM reviewers, which are already in the list:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jobcron-reviewer-glm --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile chapt-reviewer-glm --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile harness-reviewer-glm --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile jss-reviewer-glm --apply-fallbacks
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile anki-reviewer-glm --apply-fallbacks

From this step until D8 the installed `jev` configuration of every profile still names the old names, so a new card can be routed to an old name (D8 step 4 moves it), and the plugin in a new profile does not clear the model override at the review handoff, because its own name is not in its installed lists.

- Check: `hermes -p <profile> config get --json fallback_providers` prints the entry of card R2 for each of the 35 profiles; `hermes -p <profile> config get --json auxiliary.title_generation.fallback_chain` prints one entry with provider `claude-subscription` and model `claude-haiku-5-5`, and `hermes -p <profile> config get --json auxiliary.compression.fallback_chain` prints one entry with provider `claude-subscription` and the model of the profile's own `fallback_providers` entry. The dispatch list equals the snapshot, entry for entry; this command prints `True 50 50`:

      python3 -c 'import json, re; text = open("/Users/chanbla11mit/.hermes/config.yaml").read(); block = re.search(r"^  dispatch_profiles:\n((?:    - .*\n)*)", text, re.M).group(1); live = [line.strip()[2:] for line in block.splitlines()]; want = json.load(open("/Users/chanbla11mit/hermes-local-harness/snapshots/sanitized-current-state.yaml"))["kanban"]["dispatch_profiles"]; print(live == want, len(live), len(want))'

  The command reads the list in the same way as `set_dispatch` of `scripts/switch-profile-model` (the expression `DISPATCH`, line 62), and not with `hermes config get`, which reads the active profile.
- Rollback: for each of the 30 GLM workers, `python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> --to glm --dispatch remove --clear-fallbacks`; for each GLM reviewer, `python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <reviewer> --clear-fallbacks` (`scripts/verify-state` then reports `fallback drift` until the R2 declarations are reverted). With the D2 rollback, `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/config.yaml /Users/chanbla11mit/.hermes/config.yaml` restores the dispatch list of D1.

### D7. Reviewer SOULs, orchestrator SOULs and orchestrator skills

The owner approved these files (Q3). The 30 GLM worker SOULs are deployed in D2 and D4. A reviewer with an old SOUL does not accept a card from an implementation profile that its SOUL does not name ("Creating the third GLM worker profile of each board", step 8).

1. Before the first command of D6, the five Opus reviewer SOULs and the five GLM reviewer SOULs:

        for p in jobcron-reviewer chapt-reviewer harness-reviewer jss-reviewer anki-reviewer jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm; do
          mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/$p && cp -p /Users/chanbla11mit/.hermes/profiles/$p/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/$p/SOUL.md
          cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/$p/SOUL.md /Users/chanbla11mit/.hermes/profiles/$p/SOUL.md
        done

2. After D6, the five orchestrator SOULs and the orchestrator skills of `anki`, `chapt`, `jobcron` and `jss`:

        for p in jobcron-orchestrator chapt-orchestrator harness-orchestrator jss-orchestrator anki-orchestrator; do
          mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/$p && cp -p /Users/chanbla11mit/.hermes/profiles/$p/SOUL.md /Users/chanbla11mit/.hermes/backups/<card id>/$p/SOUL.md
          cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/$p/SOUL.md /Users/chanbla11mit/.hermes/profiles/$p/SOUL.md
        done
        for p in anki-orchestrator chapt-orchestrator jobcron-orchestrator jss-orchestrator; do
          cp -p /Users/chanbla11mit/.hermes/profiles/$p/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/backups/<card id>/$p/SKILL.md
          cp /Users/chanbla11mit/hermes-local-harness/policies/profile-skills/$p/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/$p/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md
        done

- Check: `shasum -a 256` of each live file equals that of its tracked source.
- Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/<profile>/SOUL.md /Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md` and `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/<profile>/SKILL.md /Users/chanbla11mit/.hermes/profiles/<profile>/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` for each changed file.

### D8. `jev` install of the integrated commit, and the repeated card check

1. Record the install metadata of each of the 56 `jev` profiles as the rollback reference (the 15 copies have the metadata of their source profile):

        for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-easy-2 jobcron-worker-glm-medium-1 jobcron-worker-glm-medium-2 jobcron-worker-glm-hard-1 jobcron-worker-glm-hard-2 chapt-worker-glm-easy-1 chapt-worker-glm-easy-2 chapt-worker-glm-medium-1 chapt-worker-glm-medium-2 chapt-worker-glm-hard-1 chapt-worker-glm-hard-2 harness-worker-glm-easy-1 harness-worker-glm-easy-2 harness-worker-glm-medium-1 harness-worker-glm-medium-2 harness-worker-glm-hard-1 harness-worker-glm-hard-2 jss-worker-glm-easy-1 jss-worker-glm-easy-2 jss-worker-glm-medium-1 jss-worker-glm-medium-2 jss-worker-glm-hard-1 jss-worker-glm-hard-2 anki-worker-glm-easy-1 anki-worker-glm-easy-2 anki-worker-glm-medium-1 anki-worker-glm-medium-2 anki-worker-glm-hard-1 anki-worker-glm-hard-2 jobcron-reviewer chapt-reviewer harness-reviewer jss-reviewer anki-reviewer jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm advisor jobcron-worker jobcron-worker-2 chapt-worker chapt-worker-2 harness-worker harness-worker-2 jss-worker jss-worker-2 anki-worker anki-worker-2 jobcron-orchestrator chapt-orchestrator harness-orchestrator jss-orchestrator anki-orchestrator; do
          mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/$p && cp -p /Users/chanbla11mit/.hermes/profiles/$p/plugins/.install-metadata.json /Users/chanbla11mit/.hermes/backups/<card id>/$p/install-metadata.json
        done

2. Install the integrated commit from the local source, one profile at a time, by the method of "Creating the third GLM worker profile of each board", step 7, in this order: first the 30 GLM workers and the ten reviewers, which need the new `config.json` before a card reaches a new name (`handle_request_review` and `handle_request_changes`), then `advisor` and the ten Claude workers, and the five orchestrators last:

        for p in jobcron-worker-glm-easy-1 jobcron-worker-glm-easy-2 jobcron-worker-glm-medium-1 jobcron-worker-glm-medium-2 jobcron-worker-glm-hard-1 jobcron-worker-glm-hard-2 chapt-worker-glm-easy-1 chapt-worker-glm-easy-2 chapt-worker-glm-medium-1 chapt-worker-glm-medium-2 chapt-worker-glm-hard-1 chapt-worker-glm-hard-2 harness-worker-glm-easy-1 harness-worker-glm-easy-2 harness-worker-glm-medium-1 harness-worker-glm-medium-2 harness-worker-glm-hard-1 harness-worker-glm-hard-2 jss-worker-glm-easy-1 jss-worker-glm-easy-2 jss-worker-glm-medium-1 jss-worker-glm-medium-2 jss-worker-glm-hard-1 jss-worker-glm-hard-2 anki-worker-glm-easy-1 anki-worker-glm-easy-2 anki-worker-glm-medium-1 anki-worker-glm-medium-2 anki-worker-glm-hard-1 anki-worker-glm-hard-2 jobcron-reviewer chapt-reviewer harness-reviewer jss-reviewer anki-reviewer jobcron-reviewer-glm chapt-reviewer-glm harness-reviewer-glm jss-reviewer-glm anki-reviewer-glm advisor jobcron-worker jobcron-worker-2 chapt-worker chapt-worker-2 harness-worker harness-worker-2 jss-worker jss-worker-2 anki-worker anki-worker-2 jobcron-orchestrator chapt-orchestrator harness-orchestrator jss-orchestrator anki-orchestrator; do
          hermes -p $p plugins install file:///Users/chanbla11mit/hermes-local-harness#plugins/jev --ref <integrated commit> --enable --force 2>&1 | tee /Users/chanbla11mit/.hermes/backups/<card id>/$p/jev-install.log
          if grep -q -i -E 'caution|dangerous' /Users/chanbla11mit/.hermes/backups/<card id>/$p/jev-install.log; then echo "stop: scan verdict on $p"; break; fi
        done

   `--force` lets a plugin scan verdict `caution` pass without a question, so the loop itself stops after an install whose output names `caution` or `dangerous`. Then report the findings to the owner before any further install. The list holds the profiles in the order above.
3. Check that local `main` is still the integrated commit: `git -C /Users/chanbla11mit/hermes-local-harness rev-parse HEAD` prints `<integrated commit>` and `git -C /Users/chanbla11mit/hermes-local-harness status --porcelain` prints nothing. R1 to R4 were integrated into local `main` before D0 (see the paragraph about merge commit `c91e172f9a19adb6a5964852ec10c2397d231f8a` above), so the `com.nous.hermes-jev-peak-hold` LaunchAgent already reads the new `config.json`.
4. Repeat D2a steps 1 and 2 on the cards of the five boards: run the program with `<step>` `d8`, move each listed card that is assigned to an old name and is not `running` or in `review`, and comment where `renamed_comment` is false. This moves a card that was created during the deployment and routed to an old name, and a card that a change request returned to an old name.

- Check: no install output names a `caution` or `dangerous` verdict. `hermes -p <profile> plugins list --plain --no-bundled` prints `jev` as `enabled` on all 56 profiles. `shasum -a 256 /Users/chanbla11mit/.hermes/profiles/<profile>/plugins/jev/config.json` is the same on all 56 profiles and equals `git -C /Users/chanbla11mit/hermes-local-harness show <integrated commit>:plugins/jev/config.json | shasum -a 256`. `tail -3 /Users/chanbla11mit/.hermes/jev/logs/peak-hold.out.log` and `tail -3 /Users/chanbla11mit/.hermes/jev/logs/peak-hold.err.log` show no new error. The program of step 4 prints `assigned to an old name: []` after the moves.
- Rollback: on each profile, install the commit recorded in `/Users/chanbla11mit/.hermes/backups/<card id>/<profile>/install-metadata.json` with the same command and `--ref <previous commit>`. A revert of local `main` needs the owner's authorization.

### D9. harness-orchestrator skill copy

The owner approved this copy (decision 5 of the specification). It is made in the same way as card `t_fb1a44e4` (`procedures/manual-apply.md`):

    mkdir -p /Users/chanbla11mit/.hermes/backups/<card id>/harness-orchestrator && cp -p /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/backups/<card id>/harness-orchestrator/SKILL.md
    cp /Users/chanbla11mit/hermes-local-harness/policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md

- Check: `shasum -a 256` of the live file equals that of the tracked source.
- Rollback: `cp -p /Users/chanbla11mit/.hermes/backups/<card id>/harness-orchestrator/SKILL.md /Users/chanbla11mit/.hermes/profiles/harness-orchestrator/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`.

### D10. Verifier and the last card check

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/verify-state

- Check: none of the failure kinds listed in "Creating the third GLM worker profile of each board", step 8, is printed for any of the 30 GLM worker names or the five GLM reviewers, and no `fallback drift` line is printed for them. The output has no new line compared with the last recorded live run. Then repeat D2a steps 1 and 2 with `<step>` `d10`: the program prints `assigned to an old name: []`. While a card of the program's list is not `done` or archived, the deployment card records it in its handoff, and the check of D2a step 3 continues, after the deployment, after each change request on such a card.
- Rollback: none; the verifier writes nothing.

## Attachment and diff procedure of the GLM workers

Card `t_ac454595` (GLM routing request of 2026-11-13, Part 6.3) added an exact procedure for attaching a file to a card and for producing the diff that the reviewer reads to the instructions of the ten GLM workers. On card `t_7097923f` a GLM worker had four failed `kanban_attach` and `kanban_attach_url` calls, and the reviewer rejected a malformed diff. The procedure rests on these facts of the installed Hermes source `/Users/chanbla11mit/.hermes/hermes-agent`:

- `kanban_attach` takes `filename` and `content_base64` (required), `content_type`, `task_id` and `board` (optional) (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools_schemas.py`, `KANBAN_ATTACH_SCHEMA`; `_schema` adds `board` to every Kanban tool), and decodes `content_base64` with `base64.b64decode(..., validate=True)` (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`, `_handle_attach`), so a file path, a `file://` URL or Base64 text with line breaks is rejected.
- The Kanban worker protocol that Hermes adds to the system prompt of every dispatched worker says "Do not shell out to `hermes kanban <verb>` for board operations. Use the `kanban_*` tools" (`/Users/chanbla11mit/.hermes/hermes-agent/agent/prompt_builder.py`, line 336, at Hermes commit `9cf7960f27`). The procedure therefore states that `hermes kanban attach` on the worker's own card is the only exception to that rule, and that every other board operation still uses the `kanban_*` tools.
- `kanban_attach_url` accepts only `http` and `https` URLs and refuses loopback and private network addresses (`/Users/chanbla11mit/.hermes/hermes-agent/tools/kanban_tools.py`, `_download_url_with_cap`).
- `hermes kanban --board <board> attach <task id> <path> [--name <file name>]` reads a local file, stores it with the same 25 MB limit, and refuses a task other than `HERMES_KANBAN_TASK` (`/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/kanban.py`, `_cmd_attach` and `_worker_run_id_for`).
- The tool result filter of this plugin cuts a line longer than `chunk_chars` (500) into pieces and can shorten a `terminal` or `execute_code` result of more than 2,000 characters (`/Users/chanbla11mit/hermes-local-harness/plugins/jev/tool_filter.py`, `_split_units` and `_make_chunks`), so Base64 text longer than that cannot be copied reliably from a tool result.

The tracked SOUL sources of the twenty-four GLM workers that have one contain the procedure as one paragraph: `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-easy-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-easy-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-medium-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-medium-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-hard-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/harness-worker-glm-hard-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-easy-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-easy-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-medium-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-medium-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-hard-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/chapt-worker-glm-hard-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-easy-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-easy-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-medium-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-medium-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-hard-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/jss-worker-glm-hard-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-easy-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-easy-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-medium-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-medium-2/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-hard-1/SOUL.md`, `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/anki-worker-glm-hard-2/SOUL.md`.

`jobcron-worker-glm-1` and `jobcron-worker-glm-2` have no SOUL source in this repository: `/Users/chanbla11mit/hermes-local-harness/roster.yaml` (`profile_souls`) and `/Users/chanbla11mit/hermes-local-harness/scripts/verify-state` (`PROFILE_SOUL_PATHS`) do not list them, and `/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/` has no directory for them (the same holds for `jobcron-worker` and `jobcron-worker-2`). Their live files `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md` and `/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-2/SOUL.md` have no line that starts with `#` (SHA-256 on 2026-11-13: `dbd702cf57c46b29e49373497e1ac2d1d6a43b3eba14682aa22f26c6e797b930` and `e05167d0aab81cd1c2f79c2caeaa181dc809e55a34d9d8cb916d3f449dc9c623`). Card `t_7e73d1b4` added the paragraph below for each of the two profiles to its live file on 2026-11-13, with the owner's authorization, as a new paragraph at the end of the file after one empty line, because neither file has a paragraph that starts with `Terminology and wording`. The SHA-256 values above are the values before the change; the values after the change are `ea3494552afed57734131fabafcd8b62205bb2a6ac9f9f63398dae11e1510968` (`jobcron-worker-glm-1`) and `d6e711330a6576958eb4c053b26e826b59c181532b3bd6127e2e72e64497fc0a` (`jobcron-worker-glm-2`).

`jobcron-worker-glm-3` has no SOUL source in this repository either. Its live file is the live file of `jobcron-worker-glm-1` with `jobcron-worker-glm-1` replaced by `jobcron-worker-glm-3` and `implementation worker 1` replaced by `implementation worker 3` (see "Creating the third GLM worker profile of each board", step 3), so it contains the paragraph for `jobcron-worker-glm-1` below with that replacement. The six Jobcron GLM workers of card `t_18a2dc93`, `jobcron-worker-glm-easy-1` to `jobcron-worker-glm-hard-2`, have no SOUL source in this repository either.

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
| `routing.threshold` | `0.6` | Minimum GLM sum: the sum of the probabilities of the board's GLM routes (`easy`, `medium` and `hard`) at which one of them is applied; also the minimum probability of the chosen route when that route is not a GLM route (`very_hard`) (see "Routes and their criteria") |
| `routing.state_max_chars` | `60000` | The card body is cut at this length before it is sent to Jev |
| `routing.question_instructions` | text | The Choice question sent to Jev |
| `routing.clear_override_at_review` | `true` | Clear the card's model override when a GLM worker requests review |
| `routing.control_group_every` | `10` | Every tenth card of a board and applied route that would get `easy`, `medium` or `hard` stays with the Claude worker (see "Control group"). `0` turns the control group off |
| `routing.max_glm_change_requests` | `5` | The general change request limit: a card of a GLM worker goes to a Claude worker when the card has this many change requests (see "Reassignment to a Claude worker after change requests"); a route can have its own value (the route `hard` has `3`). `0` turns the reassignment off for every route |
| `routing.known_models` | model IDs | Model IDs that are written to the log as given in `orchestrator_model`; any other `model` argument is logged as `unrecognized`. The models of the configured routes are always included |
| `routing.boards.<board>` | object | `implementation_workers`, `glm_workers` (four names: the two of `easy_route_workers`, then the two of `medium_route_workers`), `glm_max_workers` (two names, `<board>-worker-glm-hard-1` and `<board>-worker-glm-hard-2`), `easy_route_workers` (two names, `<board>-worker-glm-easy-1` and `<board>-worker-glm-easy-2`), `medium_route_workers` (two names, `<board>-worker-glm-medium-1` and `<board>-worker-glm-medium-2`), `routes` |
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
| `reasoning_effort.enabled` | `true` | Reasoning effort from the card line on or off (see "Reasoning effort of one card") |
| `reasoning_effort.allowed_levels` | `low`, `medium`, `high`, `xhigh`, `max` | Levels allowed in the card line |

## Routes and their criteria

For each `kanban_create` call the plugin sends Jev one Choice question. The state is the card title and the body cut at 60,000 characters; the options are the board's enabled routes with these criteria:

- `easy` (model `glm-5.3-flash`, provider `zai`, assignee from the board's `easy_route_workers`, that is `<board>-worker-glm-easy-1` and `<board>-worker-glm-easy-2` in turn): The card names the exact files to change and the exact command that checks the result, and the worker has no behaviour to work out. The topic of the card does not matter.
- `medium` (model `glm-5.3`, provider `zai`, assignee from the board's `medium_route_workers`, that is `<board>-worker-glm-medium-1` and `<board>-worker-glm-medium-2` in turn): A fully specified change across several files with no design decision. This includes tests, fixtures, user-facing text and wiring inside security, migration or deployment features.
- `hard` (model `glm-5.3`, provider `zai`, assignee from the board's `glm_max_workers`, that is `<board>-worker-glm-hard-1` and `<board>-worker-glm-hard-2` in turn, change request limit `3`): Everything that is not easy, medium or very hard: a design decision, a fault with an unknown cause, or logic for authentication, secrets, payment, a database migration or deployment when the card states the required behaviour. The topic alone does not make a card very hard.
- `very_hard` (no change: the Claude worker the orchestrator named, with that profile's own model): Work on authentication, secrets, payment, a database migration or production systems, and in addition either the card leaves the required behaviour or the approach undecided, or the problem is very complex: many parts that depend on each other and must be worked out together. Also any card whose worker itself runs commands against production or against the live Hermes installation.

Card `t_df87b851` set the `easy` and `medium` texts on all five boards (the owner's instruction of 2026-11-13 to change every route of every board); the earlier texts named topics (`easy`: a documentation or wording edit; `hard`: security, payment, migration or deployment work) and decided by topic, where the present texts decide by how exactly the card is specified. Card `t_3c7a581d` set the `hard` and `very_hard` texts on all five boards on the owner's approval of 2026-11-14 and changed the worker lists and models stated above; before it, `hard` had no `assignee_from`, no `model` and no `provider`, kept the card with the Claude worker, and `very_hard` did not exist. Card `t_cf518fd0` made the split of `easy` and `medium` work between the two workers of `glm_workers` on the owner's decision of 2026-11-16 (before it, both routes took the two workers of `glm_workers` in alternation): Hermes has one `fallback_providers` list per profile, whatever model the card sets, so each GLM worker profile must run one model; two `easy` cards of a board now run one after the other on `<board>-worker-glm-1` instead of at the same time. The list `glm_workers` still names both workers for the peak-hours hold, the report and the change request rules. Card `t_18a2dc93` (owner decision of 2026-11-16) renamed these two workers to `<board>-worker-glm-easy-1` and `<board>-worker-glm-medium-1` and the worker of `glm_max_workers` to `<board>-worker-glm-hard-1`, and added the second worker of each route, `<board>-worker-glm-easy-2`, `<board>-worker-glm-medium-2` and `<board>-worker-glm-hard-2`, so that two cards of the same route of a board can again run at the same time, each on a profile that runs one model; `glm_workers` names the four `easy` and `medium` workers.

The route is applied only when the first two conditions hold: the orchestrator left `model` empty and the `assignee` is one of the board's `implementation_workers`. Card `t_3c7a581d` left these two conditions unchanged, and cards that already exist when the change is installed are not rerouted, because the plugin decides the route only when a card is created. Card `t_92e29d10` (owner's instruction of 2026-11-14) replaced the third condition: the applied route now depends on the GLM routes together. The GLM routes of a board are its enabled routes that have `assignee_from` or `model` (today `easy`, `medium` and `hard`), and the GLM sum is the sum of their probabilities in Jev's answer, rounded to 6 decimal places. When the GLM sum is at least `threshold` (0.6), the applied route is the GLM route with the highest probability; when two or more GLM routes have the same highest probability, the applied route is the one of them that is listed later in the board's `routes` (`hard` in the shipped configuration, when `medium` and `hard` tie). This holds whichever route Jev chose, so a card goes to a GLM worker even when `very_hard` is the single most probable route: with the probabilities 0.25 (`medium`), 0.36 (`hard`) and 0.39 (`very_hard`), the GLM sum is 0.61 and the applied route is `hard`. Otherwise the applied route is the route that Jev chose only when its probability is at least `threshold` and that route is not a GLM route (`very_hard`); the card is then created exactly as the orchestrator asked, with `applied` `true`. In every other case the card is also created exactly as the orchestrator asked, with `not_applied_reason` `below_threshold`. The `route` record of every call keeps the route that Jev chose in `route`; `applied_route` names the applied route of a record with `applied` `true` and the route that would have been applied in a record with `not_applied_reason` `control_group`, and `glm_probability_sum` holds the GLM sum (see "Logs and report"). Card `t_92e29d10` introduced this rule on 2026-11-14 (owner's instruction). Before it, only the probability of the route that Jev chose was compared with `threshold`. On `easy` or `medium` the plugin sets `assignee` to the next worker of the board's `glm_workers` list (the two workers of `glm_workers` take turns; the counter is the board name under the section `counters` of `<log dir>/routing-state.json`, which holds only board names, list names, route names and counters), and on `hard` to the next worker of `glm_max_workers` (since card `t_18a2dc93` the two workers `<board>-worker-glm-hard-1` and `<board>-worker-glm-hard-2` take turns; counter `<board>:glm_max_workers`); it sets `model` and `provider`, and replaces the profile name on a body line that starts with `Assigned worker EXACT `. The reviewer is not changed. Any Jev error, timeout, HTTP error, missing key or unexpected answer leaves the card unchanged.

A repeated `kanban_create` with an `idempotency_key` that Hermes already knows returns the existing card, and Hermes does not apply the new arguments to it. The plugin cannot tell this case from a new card: the alternation counter and the control group counter still advance, and the `route` record says `applied` `true` (or `not_applied_reason` `control_group`) although the existing card is unchanged.

| Board | Implementation workers | GLM workers | GLM max workers | Enabled routes |
|---|---|---|---|---|
| `jobcron` | `jobcron-worker`, `jobcron-worker-2` | `jobcron-worker-glm-easy-1`, `jobcron-worker-glm-easy-2`, `jobcron-worker-glm-medium-1`, `jobcron-worker-glm-medium-2` | `jobcron-worker-glm-hard-1`, `jobcron-worker-glm-hard-2` | `easy`, `medium`, `hard`, `very_hard` |
| `cha-pt` | `chapt-worker`, `chapt-worker-2` | `chapt-worker-glm-easy-1`, `chapt-worker-glm-easy-2`, `chapt-worker-glm-medium-1`, `chapt-worker-glm-medium-2` | `chapt-worker-glm-hard-1`, `chapt-worker-glm-hard-2` | `easy`, `medium`, `hard`, `very_hard` |
| `harness` | `harness-worker`, `harness-worker-2` | `harness-worker-glm-easy-1`, `harness-worker-glm-easy-2`, `harness-worker-glm-medium-1`, `harness-worker-glm-medium-2` | `harness-worker-glm-hard-1`, `harness-worker-glm-hard-2` | `easy`, `medium`, `hard`, `very_hard` |
| `jss-genr` | `jss-worker`, `jss-worker-2` | `jss-worker-glm-easy-1`, `jss-worker-glm-easy-2`, `jss-worker-glm-medium-1`, `jss-worker-glm-medium-2` | `jss-worker-glm-hard-1`, `jss-worker-glm-hard-2` | `easy`, `medium`, `hard`, `very_hard` |
| `anki` | `anki-worker`, `anki-worker-2` | `anki-worker-glm-easy-1`, `anki-worker-glm-easy-2`, `anki-worker-glm-medium-1`, `anki-worker-glm-medium-2` | `anki-worker-glm-hard-1`, `anki-worker-glm-hard-2` | `easy`, `medium`, `hard`, `very_hard` |

Every board has GLM routing (card `t_71b4ef4a` added `jss-genr` and `anki`). Card `t_f4ce916d` added the third GLM worker of every board on 2026-11-14, and card `t_3c7a581d` moved it into the list `glm_max_workers`. Every board uses the same four routes with the same models, providers, worker lists and criteria. The reasoning effort of a `hard` card's GLM run is the profile value `agent.reasoning_effort` of the board's `-glm-hard-1` or `-glm-hard-2` profile, which `roster.yaml` declares as `max` in the group `glm_worker_reasoning_effort_settings` (settings `agent.reasoning_effort: max` for `jobcron-worker-glm-hard-1`, `jobcron-worker-glm-hard-2`, `chapt-worker-glm-hard-1`, `chapt-worker-glm-hard-2`, `harness-worker-glm-hard-1`, `harness-worker-glm-hard-2`, `jss-worker-glm-hard-1`, `jss-worker-glm-hard-2`, `anki-worker-glm-hard-1` and `anki-worker-glm-hard-2`); the `easy` and `medium` routes run on the four profiles that keep `high`. A board with fewer than two enabled routes gets no Jev call, and its cards stay with the Claude worker the orchestrator named; a board whose `easy`, `medium` and `hard` routes are all disabled in `config.json` keeps every card on Claude, because `very_hard` is the only remaining route and no GLM route is left.

### Model override at the review handoff

The dispatcher passes a card's `model` and `provider` override to every run of the card, including the reviewer's run (Hermes source `hermes_cli/kanban_db_dispatch.py` lines 2761 to 2766). Without a correction the Claude reviewer would start with a GLM model and the `zai` provider. Therefore, when a GLM worker profile calls `kanban_request_review`, the plugin first runs `hermes kanban --board <board> set-model <task id> none`, and then lets the review request run. Consequence: if the reviewer requests changes, the rework runs on the GLM worker profile's own model (`glm-5.3`), also for a card that started on the `easy` route with `glm-5.3-flash`.

### Control group

Setting `routing.control_group_every` (value `10`; `0` turns it off). For each `kanban_create` call where every condition for applying a GLM route holds (the orchestrator left `model` empty, the `assignee` is one of the board's `implementation_workers`, the applied route is a GLM route (`easy`, `medium` or `hard`) and the board has workers in the list that the applied route names), the plugin advances a counter for that board and applied route. On every tenth such card the card is created exactly as the orchestrator asked, so it stays with the Claude worker the orchestrator named. The counter is per board and applied route, under the applied route's name (`easy`, `medium` or `hard`); `very_hard` cards do not count, because no route is applied for them. The `route` record of a control card has `applied` `false`, `not_applied_reason` `control_group`, and `route` and `probabilities` as usual; its `applied_route` names the route that would have been applied. The alternation counter of the worker list that the applied route names does not advance for a control card.

The counters are kept in `<log dir>/routing-state.json` under the same file lock as the alternation counter, in a separate section `control_group_counters` (board name, then route name, then the count modulo `control_group_every`). A counter, not a random draw, decides, so that exactly one card in ten is a control card however few cards there are. Card `t_a40f99ed` changed the value from `5` to `10` on 2026-11-14 (owner's instruction). The file `routing-state.json` needs no change for it, because each counter is kept modulo the setting, and the comparison group now grows half as fast. `very_hard` cards and cards where a condition fails (`model_set`, `assignee_not_listed`, `below_threshold`, a Jev error) do not count. If the state file cannot be written, the card is created unchanged and the record has `not_applied_reason` `plugin_error`. The control cards are the comparison group for the Claude tokens saved by the GLM routes (`scripts/jev-report`).

### Reassignment to a Claude worker after change requests

Setting `routing.max_glm_change_requests` (value `5`; `0` turns it off). A route can have its own `max_glm_change_requests`; the route `hard` has `3`, and the routes `easy` and `medium` use the general value `5`. The middleware also handles `kanban_request_changes`, which the reviewer calls. The call runs first, unchanged, and its result is returned unchanged. Afterwards the plugin reads the card with `hermes kanban --board <board> show <task id> --json`. When all of the following hold, the card goes to a Claude worker of the board:

- the call did not return an error;
- the card's assignee, which Hermes `request_changes` has just set back to the implementer, is a GLM worker of the board: a name in the board's `glm_workers` list (the routes `easy` and `medium`) or in its `glm_max_workers` list (the route `hard`);
- the card now has at least the card's limit of events of kind `changes_requested`: with the limit `3`, the third change request sends a `hard` card to the Claude worker, so the GLM worker makes at most three attempts on a `hard` card; with the limit `5`, the fifth, as before, so a GLM worker makes at most five attempts on an `easy` or `medium` card. A run that ends by a crash, a timeout or a usage limit is not a change request and is not counted.
- the card's status is `ready` or `todo` (as Hermes leaves it), `running` (a dispatcher tick claimed it for the GLM worker in the meantime) or `scheduled` (the peak-hours hold held it in the meantime).

The limit of a card comes from two rules, in this order (card `t_52be75ab`, made on the owner's approval of 2026-11-14):

1. The card's `route` record: the last record in `decisions.jsonl` with `event` `route`, this task ID, this board and `applied` `true` names the applied route (`applied_route`, or `route` in records written before that field existed). When the board's `routes` has a route with that name, the limit of that route is the card's limit: the route's own `max_glm_change_requests` when that is a positive whole number, otherwise the general value. A card created before this change that has a `route` record for `easy` or `medium` therefore keeps the limit `5` even when its worker is the `-glm-3` profile.
2. Otherwise (no such record, a route name that the board's `routes` does not have, or a log file that cannot be read), the worker list: every route of the board, enabled or not, whose `assignee_from` names a list of the board that contains the assignee. When the limits of these routes are all the same number, that number is the limit; when there is no such route or the limits differ, the general value is the limit.

The general value `0` turns the reassignment off for every route, also for a route with its own value; the log file is then not read at all. A route's own value that is `0`, a negative number or not a whole number is ignored, and the general value applies. The log file is not read for a card whose assignee is not a GLM worker of the board.

The plugin then runs up to three commands:

1. `hermes kanban --board <board> set-model <task id> none` (clears a model override, so that the Claude worker does not start with a GLM model and the `zai` provider);
2. only when the first command worked, `hermes kanban --board <board> reassign <task id> <Claude worker> --reclaim`;
3. only when the second command worked, the plugin reads the card body again (`hermes kanban --board <board> show <task id> --json`) and, when a body line starts with `Assigned worker EXACT ` followed by the GLM worker's name, runs `hermes kanban --board <board> edit <task id> --body=<body>` with the Claude worker's name in place of the GLM worker's name on that line. The plugin wrote the GLM worker's name on that line when it routed the card at creation, and every Claude worker `SOUL.md` tells the worker to block without editing when the card names another profile as the assigned worker, so without this step the Claude worker would block instead of implementing. The same rule as at creation applies: only the name at the start of such a line changes; the same text inside another line, an indented line and a line that names another profile stay unchanged. A body without such a line gets no `edit` command. The `--body=<body>` form keeps a body whose first character is `-` one argument value. A body longer than 100,000 bytes is not sent, because `hermes kanban edit` has no `--body-file` option and the body must fit in one command-line argument (Linux limits one argument to 131,072 bytes, macOS all arguments and the environment together to 1,048,576 bytes).

The Claude worker is the `original_assignee` of the card's `route` record in `decisions.jsonl` (the worker the orchestrator named when it created the card); when there is no such record, the board's `implementation_workers` alternate (section `escalation_counters` of `routing-state.json`).

Why this works inside the reviewer process, and why the next run is the Claude worker's (checked on card `t_df87b851` with Hermes `9cf7960f27`):

- Hermes `request_changes` (`hermes_cli/kanban_db.py` lines 3575 to 3642) ends the reviewer's run and sets the card to `ready` (or `todo` while a parent is open) with the implementer as assignee. `reassign` (`assign_task`, lines 1625 to 1654) then changes `tasks.assignee`, and the dispatcher starts the profile named in `tasks.assignee` (`hermes_cli/kanban_db_dispatch.py` line 2845). The `assigned` event with a different profile also counts as a handoff for the dispatcher's open pull request check (lines 1624 to 1641 and `_is_handoff_event`).
- `hermes kanban set-model` and `hermes kanban reassign` do not check `HERMES_KANBAN_TASK` (`hermes_cli/kanban.py` `_cmd_set_model` and `_cmd_reassign`, lines 580 to 615), unlike `schedule` and `unblock`, and the dispatcher removes the delegated-child marker from the environment of every worker and reviewer it starts (`hermes_cli/kanban_db_dispatch.py` lines 2934 to 2935). A run of the installed Hermes code in an isolated Hermes home with the environment of a reviewer process confirmed it: after `request_changes`, `set-model <id> none` and `reassign <id> <profile>` both exited with status 0 and left the card `ready` on the new profile without an override, while `schedule` of another card was refused.
- Each `hermes kanban` command takes about 0.7 seconds, so about 1.5 to 2 seconds pass between the change request and the reassignment. If a dispatcher tick (every 60 seconds) claims the card for the GLM worker in that time, `--reclaim` ends that run (`reclaim_task`, `hermes_cli/kanban_db.py` lines 2638 to 2671) before the card is reassigned, so the GLM run is stopped within seconds of its start. For a card that is not running, `--reclaim` changes nothing.
- `hermes kanban edit` does not check `HERMES_KANBAN_TASK` either (`hermes_cli/kanban.py` `_cmd_edit`, lines 946 to 969; its only body option is `--body`, `hermes_cli/kanban_parser.py` lines 307 to 314). `edit_task` (`hermes_cli/kanban_db.py` lines 3211 to 3287) replaces `tasks.body` and adds one `edited` event. `edited` is not one of the event kinds that wake the orchestrator (`gateway/kanban_watchers_notifier.py` line 50, `_WAKE_KINDS`). A run of the plugin code against the installed Hermes code in an isolated Hermes home with the environment of a reviewer process confirmed it: after five real change requests the card was `ready` on the Claude worker without an override, its events ended with `model_override_set`, `assigned`, `edited`, and the body was exactly the expected body with the Claude worker on the `Assigned worker EXACT` line (the body began with `-` and had a line starting with `--body`). After four change requests nothing changed.
- The `edit` command ends about 0.7 seconds after the reassignment. A dispatcher tick in that time can start the Claude worker before the body is rewritten. The dispatcher gives a worker only the task ID (`hermes chat -q "work kanban task <id>"`, `hermes_cli/kanban_db_dispatch.py` line 2774), and the worker reads the body later with `kanban_show`, after its model session has started; the body is then normally already rewritten, but this is not guaranteed. The body is read and written by two separate steps, so an edit that the orchestrator makes to the same card body in that second is overwritten.

One `decisions` record with `event` `escalate` is written for each escalation: `board`, `task_id`, `original_assignee` (the GLM worker), `new_assignee` (the Claude worker, or the GLM worker again when the commands failed), `change_requests` (the count), `applied_route` (the route name when the card's `route` record gave the limit, otherwise `null`), `max_glm_change_requests` (the limit used), `applied`, `error_class` (`not_applied_reason` `no_claude_workers` or `plugin_error` when it applies). When the reassignment worked, the record also has `assigned_worker_line`: `rewritten`, `no_line` (the body has no line to change; no `edit` command ran) or `failed`, and `assigned_worker_line_error_class` (for example `CommandFailed`, `CommandTimeout`, `BodyTooLong`, or the class of a read error). The record never contains body text. If the first or second command fails, the card stays as Hermes left it: with the GLM worker, which runs the next attempt. A later change request on the same card, now implemented by a Claude worker, changes nothing. The reassignment changes only `tasks.assignee`, the model override and the `Assigned worker EXACT` body line: the card keeps its `workspace_path` and its branch, so the Claude worker continues in the same worktree and on the same branch.

If the third step fails (`assigned_worker_line` `failed`), the card stays as the reassignment left it: assigned to the Claude worker, without an override, with the body still naming the GLM worker on the `Assigned worker EXACT` line. The tool result is unchanged. What remains in that case: the Claude worker finds the profile mismatch and blocks the card under its `SOUL.md`; the orchestrator then changes the name on that line to the Claude worker with `hermes kanban --board <board> edit <task id> --body=<body>` (a card comment is not enough, because the worker checks the body) and unblocks the card. Find such cards with the `escalate` records that have `assigned_worker_line` `failed`.

A change request made with the command line (`hermes kanban request-changes`) instead of the `kanban_request_changes` tool is not seen by the middleware, so it never causes a reassignment, although it counts as one of the card's `changes_requested` events for the next change request made with the tool.

Orchestrators and reviewers must not reverse the reassignment (rule of the GLM routing request, Part 4.6, stated in the five orchestrator skills and the five reviewer `SOUL.md` files by card `t_ac454595`). The peak-hours hold never holds a card that is not assigned to a GLM worker, so an escalated card is never held (see "GLM peak-hours hold").

### Route disabling needs the owner's permission

No profile, script, scheduled job or plugin code turns off a route (a route's `enabled` set to false, a route removed, or a board's `glm_workers` or `glm_max_workers` emptied) unless the owner has first been notified with the figures and has stated permission for that route. This also applies to a rollback that turns off a route.

Setting `routing.enabled` to `false` turns off every route of every board, so the same rule applies to it. Setting `routing.control_group_every` or `routing.max_glm_change_requests` to `0` does not turn off a route.

## GLM peak-hours hold

Z.ai charges double on Monday to Friday from 15:00 to 19:00 Asia/Seoul time. In that window no card assigned to a GLM worker profile listed in `config.json` may be claimed by the dispatcher. A GLM run that started before 15:00 continues. `hard` cards, whose GLM worker is in the board's `glm_max_workers` list, are held like the `easy` and `medium` cards. `very_hard` cards, which stay with the Claude worker the orchestrator named, are never held.

How a card is held: it is moved to the Kanban `scheduled` status with the reason `jev-peak-hold until <date>T19:00:00+09:00`. Hermes sends no gateway notification for the `scheduled` event, and the `unblocked` event at release has no notification text and does not wake the orchestrator. A `blocked` status would wake the orchestrator for every hold, so it is not used except as the creation status below.

Holds and releases:

- `kanban_unblock` middleware (the usual path). Orchestrator Card Setup creates every card with `initial_status: blocked` and unblocks it with the `kanban_unblock` tool when setup is complete. Inside the window, when the card is `blocked` and assigned to a GLM worker of a configured board, the middleware runs `hermes kanban --board <board> schedule <id> "jev-peak-hold until ..."` instead of the unblock. Hermes accepts `schedule` for a `blocked` card, so the card goes from `blocked` directly to `scheduled` and is never `ready` inside the window. The tool result returned to the orchestrator has `status` `scheduled`, `held_until` and a note that says the card was not unblocked and how it is released. A card that is already held with the marker stays held. If the schedule command fails, the unblock runs unchanged and the script below holds the card. `kanban_unblock` is an orchestrator tool (Hermes refuses it when `HERMES_KANBAN_TASK` is set), so the `hermes kanban schedule` command works in that session. An unblock with the command line `hermes kanban unblock` instead of the tool is not seen by the middleware.
- `kanban_create` middleware. A card that ends up assigned to a GLM worker and that the caller did not create `blocked` or in triage is created with `initial_status: blocked` (the orchestrator's subscription is created after that event, so it is not delivered) and is then moved to `scheduled` with the marker. This is used only when all of the following are true, because only then can the plugin be sure the card is new and that both Kanban commands work: the call has no `idempotency_key` (Hermes returns the existing card for a known key), the session is not a dispatcher-started worker session (`HERMES_KANBAN_TASK` is not set; there `hermes kanban schedule` and `hermes kanban unblock` refuse every other card), the `hermes` command resolves to an executable, and the `kanban_create` result reports the card as `blocked`. In every other case the card is created exactly as requested and the script holds it on its next run. If the schedule command fails, the plugin runs `hermes kanban --board <board> unblock <id>` and the script holds the card on its next run. If that unblock also fails, the card stays `blocked` without the marker: the script does not release it, Hermes sends no notification for it, and the `hold` record has both error classes in `error_class` (for example `CommandFailed+CommandFailed`); find such cards with the `hold` records that have `applied` `false`.
- `scripts/jev-peak-hold --apply` (the other paths). It holds every `ready` or `todo` card of a GLM worker inside the window: cards already `ready` or `todo` at 15:00, cards created as requested in the cases above, cards returned to a GLM worker by a reviewer, cards retried after a crash, and cards unblocked with the command line. Just before each hold it reads the card again and skips it (`skipped hold <board> <id>`, no command, no record) when the card is no longer `ready` or `todo` or no longer assigned to a GLM worker, for example a card that the reassignment after change requests reassigned to a Claude worker after the script read the board. When that second read fails, the card is also skipped and the script prints the error class (`skipped hold <board> <id>: the card could not be read again (error_class=...)`); the next run, 10 seconds later, tries again.
- Release: the first `scripts/jev-peak-hold --apply` run at or after 19:00 runs `hermes kanban --board <board> unblock <id>` for every `scheduled` card whose latest `scheduled` reason starts with the marker. Hermes returns the card to `ready`, or to `todo` while a parent is open. Other `scheduled` or `blocked` cards are never released. A held card that is reassigned to a non-GLM profile, for example by the reassignment after change requests, is released on the next run.

A card whose assignee is not a GLM worker of its board is never held: the script selects only `ready` and `todo` cards of GLM workers and checks each card again before the hold, the `kanban_unblock` middleware checks the card's assignee with `hermes kanban --board <board> show <task id> --json`, and the `kanban_create` middleware checks the assignee the card is created with. A card that the reassignment after change requests reassigned to a Claude worker is therefore never held. The remaining window is the time of one `hermes kanban schedule` command (about one second) after the check; a card reassigned inside that window is released by the next script run, 10 seconds later.

`scripts/jev-peak-hold` (Python standard library; it runs under `/usr/bin/python3` and under `python3` from Homebrew):

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold              # prints planned holds and releases only
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --apply      # performs them
    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold --now 2026-11-11T16:00:00+09:00   # time for tests

`--kanban-db <path>` with one `--board <name>`, `--config <path>` and `--hermes <command>` exist for tests. Running it twice changes nothing the second time. It reads the boards only with the documented commands `hermes kanban --board <board> list --status <status> [--assignee <profile>] --json` and `hermes kanban --board <board> show <task id> --json` (change 1 of `docs/decisions/261120-plugin-behaviour-across-hermes-updates.md`), with the command `kanban.hermes_command` of the configuration and the time limit `kanban.command_timeout_seconds`; `--hermes` sets the command of the changes only, and `--kanban-db` only names the board. Hermes refuses `list` in a process that a dispatched worker started, because `list` first updates the `ready` status of cards; the script does not run in such a process. A board that cannot be read (the command is missing, exits with a status other than 0, exceeds the time limit or prints output that is not the expected JSON) is reported as `failed read <board> error_class=<class>` on every run (with `--apply` and with `off` also as a `decisions` record with `event` `read_error`, at most one record per board per hour; the time of the last record for each board is kept in `<log dir>/read-error-state.json`, which holds only board names and timestamps), the other boards are still processed, and the script exits with status 1. A failed hold or release also gives exit status 1. The script reads the repository copy `/Users/chanbla11mit/hermes-local-harness/plugins/jev/config.json` unless `--config` names another file, while the middleware reads the copy installed in each profile; keep the `peak_hold` and `routing.boards` sections of the two copies the same.

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

## Reasoning effort of one card

Decision record: [`docs/decisions/261120-per-card-reasoning-effort.md`](../docs/decisions/261120-per-card-reasoning-effort.md).

- Card line: one full body line `Reasoning effort EXACT <level>.` with one of `low`, `medium`, `high`, `xhigh`, `max` (`reasoning_effort.allowed_levels`). `kanban_create` adds a `jev_note` notice to its result when the body has more than one line that starts with `Reasoning effort`, a level that is not allowed, or a line that starts with `Reasoning effort` and does not have this form; the card is created unchanged.
- Profiles: only the board's `implementation_workers`, `glm_workers` and `glm_max_workers` in a dispatcher-started session. The `llm_request` middleware of `jev` reads the card once per process with `hermes kanban --board <board> show <task> --json`; for provider `zai` (GLM 5.2 and GLM 5.3) it sets the top-level `reasoning_effort` (`xhigh` becomes `max`; nothing when thinking is disabled), and for provider `claude-subscription` it sets `extra_body["card_reasoning_effort"]`. Reviewers, orchestrators and every other profile are not changed.
- Joint deployment: the `claude-subscription` provider refuses the key `card_reasoning_effort` until the provider change of card `t_db165633` is installed. Install this `jev` change and that provider change on the profiles at the same time; to turn the card line off, set `reasoning_effort.enabled` to `false` in the installed `config.json` (read on every call).
- Fallback: when the card cannot be read or the request does not have the expected form, the request is sent unchanged and the worker runs at the reasoning effort of its profile. `reasoning_effort.jsonl` in the log directory gets one record per process and task: `event` `applied` (with `board`, `task_id`, `provider`, `level`), `card_read_failed` or `failed` (with `error_class`). `scripts/verify-state` check `check_hermes_reasoning_effort_sources` reports a Hermes change that breaks this.

## Logs and report

Logs are JSON Lines files in `/Users/chanbla11mit/.hermes/jev/logs` (one directory for every profile; `HERMES_JEV_LOG_DIR` overrides it in tests), files mode 0600, directory mode 0700. Every record has `ts` (ISO 8601 with offset) and `profile`; unknown values are `null`. Records contain identifiers, sizes, counts, probabilities, timings and token counts only, never card text, tool output or message text.

- `decisions.jsonl`: `event` (`route`, `hold`, `release`, `toggle`, `clear_override`, `escalate`, `switch_error`, `read_error`), `board`, `task_id`, `original_assignee`, `new_assignee`, `orchestrator_model`, `route`, `probabilities`, `confidence`, `applied`, `applied_route`, `glm_probability_sum`, `not_applied_reason` (`routing_disabled`, `board_not_configured`, `single_route`, `jev_error`, `model_set`, `assignee_not_listed`, `below_threshold`, `no_glm_workers`, `control_group`, `create_failed`, `plugin_error`, `task_id_not_recognized`, `no_claude_workers`), `jev_latency_ms`, `jev_input_tokens`, `error_class`, `held_until`. `route` is the route that Jev chose. `applied_route` is the name of the applied route in a `route` record with `applied` `true`, the name of the route that would have been applied in a `route` record with `not_applied_reason` `control_group`, and the route name that gave the change request limit in an `escalate` record; `null` in every other record. `glm_probability_sum` is the sum of the probabilities of the board's GLM routes in Jev's answer, rounded to 6 decimal places (a GLM route without a number in the answer counts as 0), in every `route` record for which Jev's answer was parsed; `null` otherwise. A `toggle` record also has `enabled` and `changed_by`; an `escalate` record also has `change_requests` (the number of `changes_requested` events of the card), `max_glm_change_requests` (the limit used) and, when the reassignment worked, `assigned_worker_line` (`rewritten`, `no_line`, `failed`) and `assigned_worker_line_error_class`. A board name or assignee that is not in the configuration is logged as `null`, a `model` argument that is not in `routing.known_models` or a route as `unrecognized`, and a task ID from tool arguments that does not have the Hermes form `t_<hexadecimal digits>` as `null`.
- `tool_results.jsonl`: `event` (`filter`, `saved_read`), `session_id`, `tool`, `chars_before`, `chars_after`, `chunks_kept`, `chunks_total`, `jev_latency_ms`, `jev_input_tokens`, `action` (`filtered`, `unchanged`, `skipped`), `reason`, `error_class`, `saved_file`, `chunk_probabilities` (list of numbers in chunk order; `null` when Jev did not answer).
- `auxiliary.jsonl`: `aux_task`, `provider`, `model`, `input_tokens` (input plus cache read and cache write tokens), `output_tokens`, `status` (`ok`, `error`, `streaming`).

`scripts/jev-report` (written by a parallel card) reads these logs and the Kanban run history and prints the results per route, per tool and per auxiliary task, and the total Jev input tokens and cost (see "Report of Claude tokens saved, and the owner notification before a route is turned off").

## Report of Claude tokens saved, and the owner notification before a route is turned off

Deployment time of the routing change: `2026-11-13T23:23:38+09:00`, the time at which card `t_7e73d1b4` ended the install of commit `0db3667ba3ee03fdc174b525f0c4abd34e08492d` on the last of the 31 profiles. Use it for `<deployment time>` below.

`/Users/chanbla11mit/hermes-local-harness/scripts/jev-report` is read-only. Run it with the deployment time of the routing change:

    python3 /Users/chanbla11mit/hermes-local-harness/scripts/jev-report --after <deployment time>

Section 1 prints, for every card with a route record, the tokens of all sessions of all its runs (worker runs and reviewer runs, from the state database of every profile, including subagent sessions), with Claude tokens and GLM tokens on separate lines. The block "Claude tokens saved by GLM routing" compares two groups of done cards that have at least one linked session (it prints the number of done cards without a linked session): GLM-routed cards (cards with a route record whose route is `easy`, `medium` or `hard`, whose `applied` is `true`, and whose `new_assignee` is a non-empty name that differs from its `original_assignee`), and control cards of the same route (route records with `not_applied_reason` `control_group`). A route record with `applied` `true` whose `new_assignee` equals its `original_assignee`, or whose `new_assignee` is missing or `null`, puts its card in neither group; this includes the route records with route `hard` and equal `original_assignee` and `new_assignee` that were written before the configuration with four routes of card `t_3c7a581d` was installed, when the route `hard` kept a card with the Claude worker. The report takes a card's route from `applied_route` when it is present (a non-empty string), and otherwise from `route`. It prints the comparison per board and route and per route over all boards: saved = (mean Claude tokens per control card - mean Claude tokens per GLM-routed card) x number of GLM-routed cards. A card that was moved to a Claude worker after change requests stays in the GLM-routed group.

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
