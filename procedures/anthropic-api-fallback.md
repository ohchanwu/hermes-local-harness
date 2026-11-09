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

- **Source.** The identifiers must come from the live Anthropic model list that `hermes -p jobcron-worker model --refresh` shows after the key exists. Do not copy them from documentation or from memory.
- **Run the picker without selecting.** `hermes model` is an interactive picker (`hermes_cli/subcommands/model.py:8-15`): `--refresh` deletes the model picker disk cache and fetches every provider's live `/v1/models` list. Close the picker without choosing anything. Then confirm that `hermes -p jobcron-worker config get model.provider` still prints `claude-subscription` and `model.default` is unchanged.
- **Which credential lists the models.** `_fetch_anthropic_models` (`hermes_cli/models.py:2136-2150`) uses `resolve_anthropic_token`: `ANTHROPIC_TOKEN` or `CLAUDE_CODE_OAUTH_TOKEN`, then `ANTHROPIC_API_KEY`, then a pool entry or the Claude Code login (`agent/anthropic_credentials.py:691-709`). After section 4, the list therefore comes from the API key in the profile `.env`. The live test in section 6 is what proves that each identifier works with the API key.
- **Where the list is cached.** `hermes_cli/models_profile_cache.py` keeps only in-memory values per profile; it writes no file. The disk cache is `~/.hermes/profiles/jobcron-worker/provider_models_cache.json` (`hermes_cli/models.py:1783` and `:1869-1871`, `_provider_models_cache_path`). Each entry is keyed by provider and a credential fingerprint, which is a short hash, not the key (`_credential_fingerprint`, `hermes_cli/models.py:1874`). A later card can read the `anthropic` model identifiers from that file without the key. It must not print any other part of the file.

## 6. Intended values, apply steps and live test plan

### Intended values (a later card fills in the verified identifiers)

| Profile | `fallback_providers` |
|---|---|
| `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` | `[{"provider": "anthropic", "model": "<Opus identifier>"}]` |
| `jobcron-reviewer` | `[{"provider": "anthropic", "model": "<Fable identifier>"}]` if the list contains a Fable identifier, otherwise the Opus identifier |

| Auxiliary task | `auxiliary_fallback_chain.<task>` (all four profiles) |
|---|---|
| `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub`, `vision` | `[{"provider": "anthropic", "model": "<Haiku identifier>"}]` |
| `compression`, `goal_judge`, `review`, `background_review`, `kanban_decomposer`, `triage_specifier`, `curator`, `monitor`, `approval`, `mcp` | `[{"provider": "anthropic", "model": "<Opus identifier>"}]` |

### Compression fallback model check

1. `check_compression_model_feasibility` (`agent/conversation_compression.py:2085`) runs at session start. It uses the `compression` fallback chain only when the primary compression route cannot build a client (lines 2105-2112).
2. When the check does run, two rules apply:
   - A context window below `MINIMUM_CONTEXT_LENGTH` = 64,000 tokens (`agent/model_metadata.py:272`) raises an error, and the session does not start.
   - A context window below the profile's `compression.threshold_tokens` lowers that threshold for the session.
3. When the chain is used later, after a compression call fails, an entry whose context window is below 64,000 tokens is skipped (`_task_minimum_context_length` and `_context_too_small`, `agent/auxiliary_client.py:4380-4382` and `:4397`).
4. The later card resolves the context window that Hermes reports for the Opus identifier on provider `anthropic` (`get_model_context_length`, `agent/model_metadata.py`). It confirms that the window is at least 64,000 and at least `compression.threshold_tokens` of each of the four profiles. `jobcron-orchestrator` has 150,000 (`managed_profile_settings` in `roster.yaml`). For the other three, read the value with `hermes -p <profile> config get compression.threshold_tokens`.

### Apply steps (a later card, with separate human authorization for the live writes)

1. The owner completes section 4 for all four profiles.
2. Read the identifiers (section 5) and complete the compression check above.
3. In the repository, add `fallback_providers` and `auxiliary_fallback_chain` to the four roster entries. Update `test_repository_roster_declarations` in `tests/test_fallback_provider_settings.py`, run `python3 tests/gen_fixtures.py` and the test contract, and get the change reviewed and committed.
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
