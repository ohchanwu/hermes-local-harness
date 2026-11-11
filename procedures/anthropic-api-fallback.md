# Anthropic API fallback for the Jobcron profiles

Procedure owner: harness board. Card `t_54fc49fb` added the repository mechanism and this procedure. The live configuration, the model identifiers and the live test are done on later cards, after the owner has added the API key.

Hermes facts below were read from the installed Hermes source at commit `9cf7960f` (`~/.hermes/hermes-agent`). Re-read them after a Hermes upgrade.

## 1. Owner decision and scope

- **Decision.** Owner, Telegram, 2026-11-09: "Harness change request: Anthropic API fallback behind the Claude subscription for the Jobcron fleet."
- **Scope.** Only `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` and `jobcron-reviewer`. These four profiles keep `claude-subscription` as the primary provider. They gain a fallback provider: the native Hermes `anthropic` provider.
- **Payment.** The fallback is paid from USD 200 of Anthropic Console promotional credits. The credits expire on 2026-11-19. After that date, follow section 7.
- **Recorded override.** `plugins/model-providers/claude-subscription/README.md` says "never configure an API-key substitute for this provider". It also says "pause on failure rather than silently substituting a provider". For these four profiles only, and only until the revert in section 7, the owner's decision overrides both statements. The README is unchanged. Every other profile keeps both rules.

## 2. Hermes configuration keys

- **Main fallback.** The top-level key `fallback_providers` holds a list of entries. Each entry has `provider` and `model` (`website/docs/user-guide/features/fallback-providers.md`; default `[]` at `hermes_cli/config_defaults.py:36`). Do not use `fallback_model`, the legacy single-entry key. `hermes_cli/fallback_config.py:103-120` (`get_fallback_chain`) still appends a `fallback_model` entry after the `fallback_providers` entries. On 2026-11-09 no non-retired profile had `fallback_model` set.
- **Auxiliary fallback.** `auxiliary.<task>.fallback_chain` is a list of entries, one list per auxiliary task. Each entry has `provider` and `model`, and may have a positive `timeout` in seconds (`website/docs/user-guide/configuration.md:1570` and `:1640`; read at `agent/auxiliary_client.py:4426`; the per-entry timeout at `:3971-3981`). The key has no default in `DEFAULT_CONFIG`. `hermes config set` therefore prints "not a recognized config key", but it still saves the value with exit status 0, and the auxiliary client reads it.

## 3. Harness mechanism

- **roster.yaml.** A profile entry may declare:
  - `fallback_providers`: a list of objects with exactly `provider` and `model`.
  - `auxiliary_fallback_chain`: an object whose keys are auxiliary task names from `HELPER_TASKS` (`scripts/verify-state`). Each value is a list of objects with `provider`, `model` and an optional positive numeric `timeout`.

  Any other entry field is a verify-state error, for example `api_key`, `key_env` or `base_url`. A field whose name contains `key`, `token` or `secret` is reported as a credential-like field, and the error message never contains the field's value. An absent field means that the profile must have no fallback (an empty list or no value).
- **scripts/switch-profile-model.**
  - `--apply-fallbacks` writes the roster-declared value of `fallback_providers` and of `auxiliary.<task>.fallback_chain` for every one of the sixteen helper tasks; an undeclared task gets `[]`.
  - `--clear-fallbacks` sets all seventeen keys to `[]`.
  - Either option works alone or with `--to`. Each run first backs up `config.yaml` as `config.yaml.pre-switch-<timestamp>`, and `--dry-run` prints the commands and writes nothing.
  - The script writes with `hermes config set <key> '<JSON list>'`: a value that starts with `[` is parsed as YAML/JSON and stored as a list (`hermes_cli/config.py:3330-3409`, `_looks_structured_value` and `_coerce_config_set_value`). An empty list is the cleared state. The script does not use `hermes config unset`, because it exits non-zero for a key that was never set (`hermes_cli/config.py`, `unset_config_value`).
  - Neither option changes `roster.yaml`, and neither writes a credential.
- **scripts/verify-state.** In live mode it reads `hermes -p <profile> config get --json fallback_providers` and `hermes -p <profile> config get --json auxiliary` for every non-retired roster profile. In fixture mode it reads the fixture section `profile_fallback_settings`. A difference from the roster is reported as `fallback drift <profile> <key>: expected [...], actual [...]`. The whole `auxiliary` mapping is read because `config get` exits non-zero for a `fallback_chain` that was never set. An auxiliary task outside `HELPER_TASKS` that has a non-empty `fallback_chain` is also drift. In a drift message, the value of any field other than `provider`, `model` and `timeout` is replaced by `<not shown>`.

## 4. Credential (the owner does this; the harness never reads or prints the key)

1. In the Anthropic Console, create one API key for this purpose.
2. **Add the key to the `.env` file of each of the four profiles.** Run the three commands below in zsh, once, in one terminal. `read -rs` asks for the key with a prompt that does not show the typed text, and keeps the key only in the shell variable `K`. The typed command lines and the shell history contain `$K`, not the key. While each `hermes` process runs, the key is one of its process arguments.

   ```zsh
   read -rs "K?Anthropic API key: "; echo
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config set ANTHROPIC_API_KEY "$K"; done
   unset K
   ```

   - Each `config set` prints only `✓ Set ANTHROPIC_API_KEY in <path of the profile .env>`. A key name that ends in `_API_KEY` is written to the active profile's `.env`, not to `config.yaml` (`_is_env_config_key`, `hermes_cli/config.py:869-879`; `set_config_value`, `hermes_cli/config.py:3629-3638`; `save_provider_env_credential`, `hermes_cli/credential_lifecycle.py:163-199`).
3. **Do not use `hermes auth add anthropic --type api-key` in these four profiles until the Hermes defect is fixed** ([bug report](../docs/bugs/261109-anthropic-api-key-auth-add-dropped-in-named-profile.md)): in a named profile it prints `Added anthropic credential` but stores nothing.
4. **How Hermes uses the key.** At every credential pool load, Hermes adds an in-memory `anthropic` entry with label `ANTHROPIC_API_KEY` and source `env:ANTHROPIC_API_KEY` (`_seed_from_env`, `agent/credential_pool.py:2951-2991`; `_env_payload`, `agent/credential_pool.py:2899-2905`). `resolve_anthropic_token` reads `ANTHROPIC_API_KEY` (`agent/anthropic_credentials.py:702`), but `ANTHROPIC_TOKEN` or `CLAUDE_CODE_OAUTH_TOKEN` in the same environment takes precedence (line 697). On 2026-11-09 none of the four profile `.env` files defined either name (checked by name only); do not add them.
5. **Places the key must never be written:** `~/.hermes/.env`, `roster.yaml`, any Kanban card or comment, any log, or any commit. Only the four profile `.env` files receive the key, through step 2.
6. **Check without printing the key.** For each of the four profiles, run `hermes -p <profile> auth list anthropic`. The expected output is one entry, with label `ANTHROPIC_API_KEY` and source `env:ANTHROPIC_API_KEY`. The command prints the label, credential type, id, priority and source of each entry, but not the key (`hermes_cli/auth_commands.py:537-541`). If an entry with another source is listed, for example `claude_code` or `hermes_pkce`, do not continue with section 6 and report it to the owner.
7. **Billing boundary: `auth.adopt_external_logins` is `false` on the four profiles.** Owner decision, 2026-11-09. The reason: the Claude Code login uses the same Max plan allowance as the primary provider `claude-subscription`, and Hermes must not use that login directly.
   - With the default value `true` (`hermes_cli/config_defaults.py:1763`), Hermes can seed the Claude Code login (`~/.claude/.credentials.json`) into the `anthropic` credential pool as a `claude_code` entry (`agent/credential_pool.py:2621-2625`), and credential rotation after an authentication or rate-limit error could move the fallback onto it.
   - While `ANTHROPIC_API_KEY` is set and neither `ANTHROPIC_TOKEN` nor `CLAUDE_CODE_OAUTH_TOKEN` is set, Hermes already removes and does not seed the `claude_code` and `hermes_pkce` entries (`agent/credential_pool.py:2598-2615`). The setting `false` additionally stops Hermes from reading or refreshing the Claude Code login files at all (`adopt_external_logins_enabled`, `agent/credential_sources.py:32-38`), and removes a `claude_code` entry that an earlier process stored (`agent/credential_pool.py:2626-2629`).
   - The command for each of the four profiles is `hermes -p <profile> config set auth.adopt_external_logins false`. The earlier value was `true`; section 7 restores it.

## 5. Model identifiers

- **Source and date.** Card `t_731d4476` requested the live Anthropic model list once, on 2026-11-11 at 10:40 KST, for `jobcron-worker`. The identifiers in this procedure come only from that list, not from documentation or memory.
- **Why the picker was not used.** The earlier plan was to run `hermes -p jobcron-worker model --refresh` and close the picker without choosing anything. `hermes model` is an interactive picker (`hermes_cli/subcommands/model.py:8-15`), and a wrong key press changes the profile's default model. The card therefore called the function that the picker uses to fetch the Anthropic list, `_fetch_anthropic_models` (`hermes_cli/models.py:2138`), directly. The picker reaches it through `provider_model_ids` and `_anthropic_catalog` (`hermes_cli/models.py:1442-1448`, registered at `:1554`). `_anthropic_catalog` passes `base_url=None` and `api_key=None` when `model.provider` is not `anthropic`; on `jobcron-worker` it is `claude-subscription`. The direct call used the same arguments. The card did not use `provider_model_ids`, because that function returns a built-in catalog when the live request fails (`hermes_cli/models.py:1747-1775`).
- **How the call ran.** Installed Hermes Python (`~/.hermes/hermes-agent/venv/bin/python`, Hermes commit `9cf7960f`), under `env -i` with only `HOME`, `PATH` and `HERMES_HOME=/Users/chanbla11mit/.hermes/profiles/jobcron-worker`, so no token from the calling environment could be used. The profile environment was loaded only with `load_hermes_dotenv(project_env=<hermes-agent>/.env)` (`hermes_cli/env_loader.py:455`), the same call that the CLI makes at start (`hermes_cli/main.py:713`). The script opened no `.env` or `auth.json` file itself and printed only the returned model identifiers.
- **Which credential listed the models.** Before the request, the script checked with the Hermes functions, without printing any value:
  - `_first_env("ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")` is empty, and `ANTHROPIC_API_KEY` is set.
  - `resolve_anthropic_token()` returns the `ANTHROPIC_API_KEY` value (`agent/anthropic_credentials.py:691-709`, the API key branch at line 702).
  - `_is_oauth_token` is False for that value (`agent/anthropic_credentials.py:63-67`), so it has the shape of an Anthropic Console API key.

  `_fetch_anthropic_models` therefore sent the value in the `x-api-key` header (`hermes_cli/models.py:2165`), not as an OAuth Bearer token. The list came from the `ANTHROPIC_API_KEY` value in the `jobcron-worker` profile `.env`. The first attempt, on 2026-11-09, stopped at the `_is_oauth_token` check and made no request, because the value then had the shape of an OAuth or setup token; the owner replaced the value on 2026-11-11.
- **Returned list.** 15 identifiers, in the order Hermes sorts them (Opus, then Sonnet, then Haiku, then others; `hermes_cli/models.py:2196`): `claude-opus-4-5-20251101`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-opus-5`, `claude-opus-5-5`, `claude-sonnet-4-5-20250929`, `claude-sonnet-4-6`, `claude-sonnet-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`, `claude-haiku-5-5`, `claude-fable-5`, `claude-fable-5-1`, `claude-fable-5-2`.
- **Chosen identifiers.**
  - Opus: `claude-opus-5-5`, the only Claude Opus 5.5 identifier in the list.
  - Fable: `claude-fable-5-2`, the only Claude Fable 5.2 identifier in the list. Owner decision, 2026-11-11: the Fable profiles, including `jobcron-reviewer`, move from Fable 5.1 to Fable 5.2 on a separate card. Until that card, the primary model of `jobcron-reviewer` stays `claude-fable-5-1`.
  - Haiku: `claude-haiku-5-5`, the newest Haiku identifier in the list. The other one is `claude-haiku-4-5-20251001`, which is also the Hermes built-in default.
- **Where the list is cached.** `_fetch_anthropic_models` itself writes no cache file; the call above therefore wrote none. The picker's disk cache is written by the `provider_model_ids` cache layer to `~/.hermes/profiles/<profile>/provider_models_cache.json` (`_provider_models_cache_path`, `hermes_cli/models.py:1869`). Each entry is keyed by provider and a credential fingerprint, which is a short hash, not the key (`_credential_fingerprint`, `hermes_cli/models.py:1874`). `hermes_cli/models_profile_cache.py` keeps only in-memory values per profile.
- **Proof of use.** The list shows which identifiers the key can see. The live test in section 6 is what proves that each identifier works with the API key.

## 6. Intended values, apply steps and live test plan

### Intended values (identifiers from section 5; declared in `roster.yaml` by card `t_731d4476`)

| Profile | `fallback_providers` |
|---|---|
| `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` | `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` |
| `jobcron-reviewer` | `[{"provider": "anthropic", "model": "claude-fable-5-2"}]` |

| Auxiliary task | `auxiliary_fallback_chain.<task>` (all four profiles) |
|---|---|
| `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub`, `vision` | `[{"provider": "anthropic", "model": "claude-haiku-5-5"}]` |
| `compression`, `goal_judge`, `review`, `background_review`, `kanban_decomposer`, `triage_specifier`, `curator`, `monitor`, `approval`, `mcp` | `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` |

On 2026-11-11 the four profiles had exactly these sixteen auxiliary tasks with a `provider` and `model` (all `claude-subscription` / `claude-opus-5-5`), read by name with `hermes -p <profile> config get --json auxiliary`. The `auxiliary` section also has `moa_reference` and `moa_aggregator`. These are Hermes default entries (`hermes_cli/config_defaults.py:817-818`, provider `auto`, no model) and are not in `HELPER_TASKS`, so they get no fallback chain.

### Compression fallback model check

1. `check_compression_model_feasibility` (`agent/conversation_compression.py:2085`) runs at session start. It uses the `compression` fallback chain only when the primary compression route cannot build a client (lines 2105-2112).
2. When the check does run, two rules apply:
   - A context window below `MINIMUM_CONTEXT_LENGTH` = 64,000 tokens (`agent/model_metadata.py:272`) raises an error, and the session does not start.
   - A context window below the profile's `compression.threshold_tokens` lowers that threshold for the session.
3. When the chain is used later, after a compression call fails, an entry whose context window is below 64,000 tokens is skipped (`_task_minimum_context_length` and `_context_too_small`, `agent/auxiliary_client.py:4380-4382` and `:4397`).
4. The check also runs again after the main runtime changes, for example when a fallback activates (`revalidate_compression_feasibility`, `agent/conversation_compression.py:2177`), and it can be deferred until a request first reaches 64,000 tokens (`ensure_compression_feasibility_checked`, line 2193).
5. **Result (card `t_731d4476`, 2026-11-11; no model call and no network request).** `claude-opus-5-5` as the `compression` fallback chain model on provider `anthropic` passes the check for all four profiles.

   | Profile | Main model (provider `claude-subscription`) | Main context window | Compression trigger (`threshold_tokens`) | Fallback model context window | Result |
   |---|---|---|---|---|---|
   | `jobcron-orchestrator` | `claude-opus-5-5` | 1,000,000 | 150,000 (configured cap) | 1,000,000 | pass |
   | `jobcron-worker` | `claude-opus-5-5` | 1,000,000 | 500,000 | 1,000,000 | pass |
   | `jobcron-worker-2` | `claude-opus-5-5` | 1,000,000 | 500,000 | 1,000,000 | pass |
   | `jobcron-reviewer` | `claude-fable-5-1` | 1,000,000 | 500,000 | 1,000,000 | pass |

   - **How the numbers were obtained.** `get_model_context_length` (`agent/model_metadata.py:2245`) was run with the installed Hermes Python for each profile home, with network connections blocked, no `.env` loaded and no API key. For `claude-opus-5-5` on `anthropic` at `https://api.anthropic.com` it returned 1,000,000: no persistent cache entry (step 1, line 2303); the live `/v1/models` step is skipped without a key (step 4, lines 2325-2329; `_query_anthropic_context_length` at line 1670 returns nothing for an empty key); the models.dev lookup without network (`lookup_models_dev_context`, step 5, line 2330) gives 1,000,000; the built-in table entry `claude-opus-5` also gives 1,000,000 (line 293, used in step 8, line 2353). Each main model on `claude-subscription` also resolves to 1,000,000, which matches `MODELS` in `plugins/model-providers/claude-subscription/compat.py`.
   - **Trigger.** Each profile has `compression.threshold` 0.5 and no `model.max_tokens`. `_compute_threshold_tokens` (`agent/context_compressor.py:2863`) gives 1,000,000 × 0.5 = 500,000. `jobcron-orchestrator` has `compression.threshold_tokens` 150,000, which caps its trigger (`_effective_threshold_cap`, line 2759); the other three profiles have no value.
   - **Comparison.** 1,000,000 is at least `MINIMUM_CONTEXT_LENGTH` 64,000 (`agent/model_metadata.py:272`), so no error is raised (`agent/conversation_compression.py:2149`). 1,000,000 is at least each trigger, so the trigger is not lowered (line 2160). When the main runtime itself is on the fallback (`claude-opus-5-5`, or `claude-fable-5-2` for `jobcron-reviewer`, both 1,000,000 by the same offline lookup), the triggers stay 150,000 and 500,000, and the result is the same.
   - **Limit.** At run time, with the Console key, Hermes first asks Anthropic's `/v1/models` for `max_input_tokens` (step 4). This card did not read that value: the single allowed request returned identifiers only. If Anthropic reports a value below the trigger but at least 64,000, Hermes lowers the trigger for that session (lines 2160-2164); the session still starts.

### Apply steps (a later card, with separate human authorization for the live writes)

1. The owner completes section 4 for all four profiles. On 2026-11-11 the owner wrote the replacement key to the four profile `.env` files (controller check by variable name and `auth list` source only). Confirm step 7 of section 4 (`auth.adopt_external_logins` is `false`) before step 4 below.
2. Read the identifiers (section 5) and complete the compression check above. Done by card `t_731d4476`.
3. In the repository, add `fallback_providers` and `auxiliary_fallback_chain` to the four roster entries. Update `test_repository_roster_declarations` in `tests/test_fallback_provider_settings.py`, run `python3 tests/gen_fixtures.py` and the test contract, and get the change reviewed and committed. Done by card `t_731d4476`. From that commit until step 4 is done, `scripts/verify-state` in live mode reports `fallback drift` for the four profiles.
4. For each profile, preview the change, then apply it:

   ```sh
   scripts/switch-profile-model --profile <profile> --apply-fallbacks --dry-run
   scripts/switch-profile-model --profile <profile> --apply-fallbacks
   ```

5. Run `scripts/verify-state`. The expected result is no `fallback drift` line.

### Live test plan: make the primary provider fail for one run

1. **Method (read from source, not run yet).** Run one one-shot command with a per-invocation model override that the claude-subscription plugin rejects:

   ```sh
   hermes -p jobcron-worker -z "Reply with the single word OK." \
     -m not-an-allowlisted-model --provider claude-subscription --usage-file <path outside the repository>
   ```

2. **Why it is expected to work:**
   - `-m/--model` and `--provider` apply to this invocation only and change no `config.yaml` (`hermes_cli/_parser.py:161-167`).
   - The plugin's `_validate` rejects a model id outside its allowlist with `ProviderError` before it starts the Claude CLI (`plugins/model-providers/claude-subscription/client.py:192-196`), so the main model makes no subscription request.
   - Hermes classifies an exception with no HTTP status as `unknown` (`agent/error_classifier.py:66`). It retries up to the retry budget; each retry fails locally in the same way. Hermes then activates the next `fallback_providers` entry (`agent/turn_api_error.py:357-373`).
   - One-shot mode passes `get_fallback_chain(cfg)` to the agent (`hermes_cli/oneshot.py:585`).
3. **Known limits:**
   - The automatic session title runs in one-shot mode (`hermes_cli/oneshot.py:57-66`). Its auxiliary route is still `claude-subscription` with a valid model, so it can make one small subscription request. The `auxiliary.by_task` section of the usage file shows whether it ran.
   - Whether Hermes rejects the unknown model before the agent starts is not verified. In that case the run ends with no request and no fallback, and no safe forced-failure method is confirmed.
   - An environment override of `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` for one run does not work: the profile `.env` is loaded with `override=True` (`hermes_cli/env_loader.py:507`) and replaces the shell value.
   - The plugin's own failure paths at `client.py:634-641` (rate-limit rejection, runtime and protocol errors) occur only after the Claude CLI has started. They cannot be produced without a subscription request.
4. **Expected evidence.** The usage file names the `anthropic` provider and the fallback model. The response is "OK". `hermes -p jobcron-worker config get model.default` is unchanged.

## 7. Revert after 2026-11-19

1. For each of the four profiles, preview and then clear the fallback values:

   ```sh
   scripts/switch-profile-model --profile <profile> --clear-fallbacks --dry-run
   scripts/switch-profile-model --profile <profile> --clear-fallbacks
   ```

2. In the repository, remove `fallback_providers` and `auxiliary_fallback_chain` from the four roster entries. Restore the assertion in `test_repository_roster_declarations`, run `python3 tests/gen_fixtures.py` and the test contract, and get the change reviewed and committed.
3. The owner removes the key from the four profile `.env` files and restores `auth.adopt_external_logins` to its earlier value `true`:

   ```zsh
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config unset ANTHROPIC_API_KEY; done
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config set auth.adopt_external_logins true; done
   ```

   - `config unset ANTHROPIC_API_KEY` removes the `ANTHROPIC_API_KEY` line from the profile `.env`, removes the variable from the process environment and removes the credential pool entries seeded from it (`unset_config_value`, `hermes_cli/config.py:3800-3819`; `remove_provider_env_credential`, `hermes_cli/credential_lifecycle.py:202-221`; `remove_env_value`, `hermes_cli/config.py:2808-2826`). It prints `✓ Unset ANTHROPIC_API_KEY from <path of the profile .env>`, or exits with a non-zero status and `Config key not set: ANTHROPIC_API_KEY` when the profile has no such line.
   - This replaces the earlier `auth remove` step: no `auth.json` entry exists to remove.
   - Then `hermes -p <profile> auth list anthropic` must list no entry with source `env:ANTHROPIC_API_KEY`.
4. The owner deletes (revokes) the key in the Anthropic Console, under API keys.
5. Run `scripts/verify-state`. The expected result is no `fallback drift` line, and `hermes -p <profile> config get --json fallback_providers` prints `[]` for each profile.
