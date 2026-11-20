import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fx = Path(__file__).resolve().parent / "fixtures"
clean = json.loads((fx / "clean.yaml").read_text())
desired = json.loads((ROOT / "snapshots" / "sanitized-current-state.yaml").read_text())
roster = json.loads((ROOT / "roster.yaml").read_text())
TRACKED_SOURCE = "tracked-source"


# Observed hashes of a correctly deployed fleet are the bytes of the tracked
# sources (desired state carries no hash pins where a tracked source exists).
# A fixture stores no copy of such a hash: it records TRACKED_SOURCE, which
# verify-state fixture mode resolves to the tracked source's sha256 at run time.
# Only a hash with no tracked source (worker-astra's pins) is written as a hash.
def override_hashes():
    """profile -> {path: TRACKED_SOURCE or pin} of correctly deployed profile-local overrides."""
    return {profile: dict(files)
            for profile, files in desired["skill"]["profile_local_skill_overrides"].items()}

NOTIF = "hermes-terminal-outcome-notification"
ENABLED_NOTIF = f"enabled      git pinned@6ae2bf2d 0.2.0    {NOTIF}"
DISABLED_NOTIF = f"disabled     git pinned@6ae2bf2d 0.2.0    {NOTIF}"
# Observed `plugins list --plain` lines of Ponytail 5.3.3 at commit
# 7801d061243d7b753bad0e0b3c057cd250b11755, installed by hand with `git clone`, `git checkout --detach`
# and `plugins adopt` (procedures/manual-apply.md, section 3): Hermes prints `git pinned@<first 8
# characters of the commit>` (hermes_cli/plugins_cmd_git.py line 100) only for a `plugins install --ref`
# record (pinned true), so this source column is `git` alone (hermes_cli/plugins_cmd_listing.py:
# f"{status:12} {source:8} {version:8} {name}").
DISABLED_PONY = "disabled     git      5.3.3    ponytail"
ENABLED_PONY = "enabled      git      5.3.3    ponytail"
PONYTAIL = "ponytail"
# The install metadata entry that `plugins adopt` writes for that clone
# (hermes_cli/plugins_cmd_update.py, cmd_adopt).
PONY_INSTALL_METADATA = {"pinned": False, "revision": "7801d061243d7b753bad0e0b3c057cd250b11755",
                         "source": "https://github.com/DietrichGebert/ponytail.git"}
# Observed `plugins list --plain` line of an enabled jev plugin (card t_4f7740d0). The
# source and version columns are assumed values: no pin is declared for jev, so
# check_plugins compares only the leading `enabled` status.
JEV = "jev"
ENABLED_JEV = f"enabled      user     0.1.0    {JEV}"
# Observed `plugins list --plain --no-bundled` line of the user model-provider plugin
# claude-subscription in Hermes v0.23.3 (harness-worker, 2026-11-20). It is expected on every
# profile whose model.provider or fallback_providers names it (configured_providers).
CLAUDE_SUBSCRIPTION = "claude-subscription"
ENABLED_CLAUDE_SUBSCRIPTION = f"enabled      user     0.1.0    {CLAUDE_SUBSCRIPTION}"


def write(name, data):
    (fx / name).write_text(json.dumps(data, indent=2) + "\n")


def delta(mutate):
    d = copy.deepcopy(clean)
    mutate(d)
    return d


def base_plugins():
    """Fresh copy of the desired plugin matrix (clean.yaml may itself be mutated by a caller)."""
    plugins = {}
    roster_profiles = {profile["name"]: profile for profile in roster["profiles"]}
    for name in clean["profile_models"]:
        if name == "advisor":
            plugins[name] = {}
        else:
            plugins[name] = {}
            if name in desired["terminal_notification"]["producer_profiles"]:
                plugins[name][NOTIF] = ENABLED_NOTIF
            elif NOTIF in roster_profiles[name].get("installed_disabled_plugins", []):
                plugins[name][NOTIF] = DISABLED_NOTIF
        # A profile that requires ponytail has it enabled; a profile that only expects it
        # installed and disabled (the retired implementation profiles) has it disabled.
        if PONYTAIL in roster_profiles[name].get("required_plugins", []):
            plugins[name][PONYTAIL] = ENABLED_PONY
        elif PONYTAIL in roster_profiles[name].get("installed_disabled_plugins", []):
            plugins[name][PONYTAIL] = DISABLED_PONY
        if JEV in roster_profiles[name].get("required_plugins", []):
            plugins[name][JEV] = ENABLED_JEV
        if CLAUDE_SUBSCRIPTION in verifier_namespace["configured_providers"](roster_profiles[name]):
            plugins[name][CLAUDE_SUBSCRIPTION] = ENABLED_CLAUDE_SUBSCRIPTION
    return plugins


def skill_files_map():
    """skill -> profile -> {rel: TRACKED_SOURCE or pin}, per the desired deploy_profiles matrix; a file a
    profile-local override owns carries that override's bytes."""
    overrides = override_hashes()
    result = {}
    for entry in desired["skill"]["shared_skills"]:
        result[entry["name"]] = {}
        for profile in entry["deploy_profiles"]:
            files = {}
            for rel in entry["files"]:
                owned = [want for path, want in overrides.get(profile, {}).items()
                         if f"/{path}".endswith(f"/{entry['name']}/{rel}")]
                files[rel] = owned[0] if owned else TRACKED_SOURCE
            # A profile-only file that an override declares inside this skill's tree
            # (for example a reference file) is deployed in the same directory.
            marker = f"/{entry['name']}/"
            for path, want in overrides.get(profile, {}).items():
                if marker in f"/{path}":
                    files.setdefault(f"/{path}".split(marker, 1)[1], want)
            result[entry["name"]][profile] = files
    return result


def set_skill_files(d):
    d["skill_files"] = skill_files_map()
    d["profile_local_skill_overrides"] = override_hashes()


clean["profile_models"] = {profile["name"]: profile["model"] for profile in roster["profiles"]}
clean["profile_providers"] = {profile["name"]: profile["provider"] for profile in roster["profiles"]}
clean["profile_approval_modes"] = {
    profile: desired["approvals"]["mode"] for profile in desired["approvals"]["profiles"]}
# Observed config values of every managed settings group, merged per profile:
# managed_profile_settings (mirrored in the snapshot), orchestrator_profile_settings
# (roster.yaml only), claude_worker_profile_settings (roster.yaml only),
# glm_worker_reasoning_effort_settings (roster.yaml only) and
# glm_reviewer_profile_settings (roster.yaml only, card t_cca306ca).
clean["profile_managed_settings"] = {}
for group in (desired["managed_profile_settings"], roster["orchestrator_profile_settings"],
              roster["claude_worker_profile_settings"], roster["glm_worker_reasoning_effort_settings"],
              roster["glm_reviewer_profile_settings"]):
    for profile in group["profiles"]:
        clean["profile_managed_settings"].setdefault(profile, {}).update(copy.deepcopy(group["settings"]))
# Observed fallback settings of every non-retired roster profile, as the roster declares
# them: `hermes config get --json fallback_providers` and the fallback_chain values inside
# `hermes config get --json auxiliary` (an absent declaration is an empty list / no value).
clean["profile_fallback_settings"] = {
    profile["name"]: {
        "fallback_providers": copy.deepcopy(profile.get("fallback_providers", [])),
        "auxiliary": {task: {"fallback_chain": copy.deepcopy(chain)}
                      for task, chain in profile.get("auxiliary_fallback_chain", {}).items()},
    }
    for profile in roster["profiles"] if profile.get("lifecycle") != "retired"}
# Observed helper models of every non-retired roster profile that declares auxiliary_models,
# as the roster declares them: the provider and model values inside `hermes config get --json
# auxiliary`. The task lists come from scripts/verify-state (HELPER_TASKS, LIGHT_HELPER_TASKS).
verifier_namespace: dict = {"__file__": str(ROOT / "scripts" / "verify-state"), "__name__": "gen_fixtures_verifier"}
exec(compile((ROOT / "scripts" / "verify-state").read_text(), str(ROOT / "scripts" / "verify-state"), "exec"),
     verifier_namespace)
clean["profile_auxiliary_settings"] = {
    profile["name"]: {"auxiliary": {
        task: {"provider": provider, "model": model}
        for task, (provider, model) in verifier_namespace["expected_auxiliary_models"](
            profile["auxiliary_models"]).items()}}
    for profile in roster["profiles"]
    if profile.get("lifecycle") != "retired" and "auxiliary_models" in profile}
# Observed `hermes config get --json plugins.auto_apply` of every roster profile: false, because
# Hermes updates and plugin updates stay manual (owner instruction, 2026-11-20).
clean["profile_plugin_auto_apply"] = {profile["name"]: {"plugins.auto_apply": False} for profile in roster["profiles"]}
clean["dispatch_profiles"] = copy.deepcopy(desired["kanban"]["dispatch_profiles"])
clean["kanban"] = {key: copy.deepcopy(value) for key, value in desired["kanban"].items()
                   if key != "dispatch_profiles"}
clean["project_isolation"] = copy.deepcopy(desired["project_isolation"])
clean["project_repair_policy"] = copy.deepcopy(desired["project_repair_policy"])
clean["project_repair_cards"] = []
clean["profile_soul_hashes"] = {profile: TRACKED_SOURCE for profile in desired["profile_souls"]}
clean["repository_policy_hashes"] = {
    name: entry["sha256"] for name, entry in desired["repository_policies"].items()}
harness_adoption = (Path(__file__).resolve().parents[1] / "adoption" / "harness.md").read_text()
harness_entries = [adapter for adapter in clean["adapters"] if adapter.get("repo") == "harness"]
if harness_entries:
    harness_entries[0].update({
        "content": "Status: operational; attended live rollout verified.",
        "record": harness_adoption,
    })
else:
    clean["adapters"].append({
        "repo": "harness",
        "content": "Status: operational; attended live rollout verified.",
        "record": harness_adoption,
    })
# Marker text only (from the public tracked CLAUDE.md); never any jss-genr content beyond it.
jss_adapter = next(adapter for adapter in desired["adoption"]["adapters"] if adapter["repo"] == "jss-genr")
jss_observation = {
    "repo": "jss-genr",
    "content": jss_adapter["marker"],
    "record": (Path(__file__).resolve().parents[1] / "adoption" / "jss-genr.md").read_text(),
}
jss_entries = [adapter for adapter in clean["adapters"] if adapter.get("repo") == "jss-genr"]
if jss_entries:
    jss_entries[0].update(jss_observation)
else:
    clean["adapters"].append(jss_observation)
# Marker text only: the first line of the tracked anki README.md.
anki_adapter = next(adapter for adapter in desired["adoption"]["adapters"] if adapter["repo"] == "anki")
anki_observation = {
    "repo": "anki",
    "content": anki_adapter["marker"],
    "record": (Path(__file__).resolve().parents[1] / "adoption" / "anki.md").read_text(),
}
anki_entries = [adapter for adapter in clean["adapters"] if adapter.get("repo") == "anki"]
if anki_entries:
    anki_entries[0].update(anki_observation)
else:
    clean["adapters"].append(anki_observation)
clean["plugins"] = base_plugins()
# The line PONYTAIL_DEFAULT_MODE=full is present in the .env file of every profile that
# requires ponytail (one boolean per profile; no other line of the file is recorded).
clean["ponytail_mode_env"] = {profile["name"]: True for profile in roster["profiles"]
                              if PONYTAIL in profile.get("required_plugins", [])}
# The ponytail entry of the install metadata of every profile that requires ponytail
# (plugins/.install-metadata.json); verify-state reads the full revision and the source from it.
clean["ponytail_install_metadata"] = {profile["name"]: dict(PONY_INSTALL_METADATA) for profile in roster["profiles"]
                                      if PONYTAIL in profile.get("required_plugins", [])}
set_skill_files(clean)
clean["terminal_retry_policy"] = copy.deepcopy(
    json.loads((Path(__file__).resolve().parents[1] / "roster.yaml").read_text())["terminal_retry"])
# The LaunchAgent of the jev peak-hours hold is loaded (card t_cca306ca, item 2.6): the
# pass of a card from the GLM reviewer to the independent reviewer of a board needs it.
clean["jev_peak_hold_agent"] = copy.deepcopy(desired["jev_peak_hold_agent"])
# The skill sdlc-review is installed on every GLM reviewer (card t_cca306ca, item 2.3).
GLM_REVIEWER_SKILL_INSTALLED = True
clean["glm_reviewer_skills"] = {profile: GLM_REVIEWER_SKILL_INSTALLED
                                for profile in roster["glm_reviewer_profile_settings"]["profiles"]}
# Excerpts of the installed Hermes source (v0.23.3, commit caafe538) that the per-card reasoning
# effort of plugins/jev depends on (card t_caf5dba0); verify-state parses them with ast.
HERMES_REASONING_EFFORT_SOURCES = {
    "hermes_cli/middleware.py": 'LLM_REQUEST_MIDDLEWARE = "llm_request"\n',
    "agent/turn_api_request.py": (
        "_llm_request_mw = apply_llm_request_middleware(\n"
        "    api_kwargs, task_id=effective_task_id, model=agent.model, provider=agent.provider,\n"
        ")\n"),
    "gateway/session_kanban.py": (
        "def bind_worker_context(frame):\n"
        "    import os\n"
        "    env = {'HERMES_KANBAN_TASK': context['task_id'], 'HERMES_KANBAN_BOARD': context['board']}\n"
        "    os.environ.update(env)\n"),
    "plugins/model-providers/zai/__init__.py": (
        "if is_5_2:\n"
        "    effort = _glm_5_2_reasoning_effort(reasoning_config, model=model)\n"
        "    if effort is not None:\n"
        '        top_level["reasoning_effort"] = effort\n'),
    "tools/kanban_tools_schemas.py": '"model": {"type": "string"},\n',
    "tools/kanban_tools.py": "new_tid = kb.create_task(conn, model_override=model_override)\n",
}
clean["hermes_reasoning_effort_sources"] = copy.deepcopy(HERMES_REASONING_EFFORT_SOURCES)
write("clean.yaml", clean)


write("behavior-changing-model-drift.yaml", delta(lambda d: d["profile_models"].__setitem__("worker-terra-1", "wrong-model")))
write("approval-mode-drift.yaml", delta(
    lambda d: d["profile_approval_modes"].__setitem__("jobcron-worker", "smart")))
write("active-extra.yaml", delta(lambda d: d["active_extras"].append("unapproved-running-profile")))
write("dormant-extra.yaml", delta(lambda d: d["dormant_extras"].append("unused-local-profile")))


def retired_glm_dispatch(d):
    # A GLM profile that is still retired stays installed and stopped, but is back on the
    # dispatch list (card t_71b4ef4a returned every project fleet GLM worker to service;
    # the generic profile worker-glm-full stays retired).
    d["dormant_extras"].append("worker-glm-full")
    d["dispatch_profiles"].append("worker-glm-full")


write("retired-glm-dispatch-drift.yaml", delta(retired_glm_dispatch))


def glm_worker_dispatch_missing(d):
    # Two of the GLM workers in service are missing from the dispatch list: one of card
    # t_4f7740d0 (renamed by card t_18a2dc93) and one second worker of a route that card
    # t_18a2dc93 added.
    d["dispatch_profiles"].remove("chapt-worker-glm-medium-1")
    d["dispatch_profiles"].remove("anki-worker-glm-hard-2")


write("glm-worker-dispatch-missing.yaml", delta(glm_worker_dispatch_missing))


def glm_reviewer_jev_plugin_missing(d):
    # The jev plugin is absent on one GLM reviewer that requires it (card t_cca306ca).
    del d["plugins"]["harness-reviewer-glm"][JEV]


write("glm-reviewer-jev-plugin-missing.yaml", delta(glm_reviewer_jev_plugin_missing))


def glm_reviewer_skill_missing(d):
    # The skill sdlc-review is not installed on one GLM reviewer (card t_cca306ca).
    d["glm_reviewer_skills"]["harness-reviewer-glm"] = False


write("glm-reviewer-skill-missing.yaml", delta(glm_reviewer_skill_missing))


def glm_reviewer_dispatch_missing(d):
    # One GLM reviewer is missing from the dispatch list (card t_cca306ca).
    d["dispatch_profiles"].remove("harness-reviewer-glm")


write("glm-reviewer-dispatch-missing.yaml", delta(glm_reviewer_dispatch_missing))


def glm_reviewer_model_drift(d):
    # One GLM reviewer runs claude-opus-5-5 instead of glm-5.3 (card t_cca306ca).
    d["profile_models"]["harness-reviewer-glm"] = "claude-opus-5-5"


write("glm-reviewer-model-drift.yaml", delta(glm_reviewer_model_drift))


def launch_agent_not_loaded(d):
    # The LaunchAgent of the jev peak-hours hold is not loaded (card t_cca306ca).
    d["jev_peak_hold_agent"]["loaded"] = False


write("launch-agent-not-loaded.yaml", delta(launch_agent_not_loaded))


def hermes_source(path, text):
    """A fixture whose excerpt of one installed Hermes source file is replaced (card t_caf5dba0)."""
    return delta(lambda d: d["hermes_reasoning_effort_sources"].__setitem__(path, text))


# One fixture for each FAIL condition and one for the WARN case of the check of the Hermes
# behaviour that the per-card reasoning effort depends on.
write("hermes-llm-request-middleware-drift.yaml",
      hermes_source("hermes_cli/middleware.py", 'LLM_REQUEST_MIDDLEWARE = "llm_call"\n'))
write("hermes-turn-request-middleware-drift.yaml", hermes_source(
    "agent/turn_api_request.py", "_llm_request_mw = apply_llm_request_middleware(api_kwargs, model=agent.model)\n"))
write("hermes-dispatch-kanban-environment-drift.yaml", hermes_source(
    "gateway/session_kanban.py",
    "def bind_worker_context(frame):\n"
    "    import os\n"
    "    env = {'HERMES_KANBAN_TASK': context['task_id']}\n"
    "    os.environ.update(env)\n"))
write("hermes-zai-reasoning-effort-drift.yaml", hermes_source(
    "plugins/model-providers/zai/__init__.py", 'extra_body["reasoning_effort"] = effort\n'))
write("hermes-kanban-tool-reasoning-effort.yaml", hermes_source(
    "tools/kanban_tools_schemas.py", '"reasoning_effort": {"type": "string"},\n'))


def jev_plugin_missing(d):
    # jev is absent on one Claude profile and disabled on one GLM worker that require it.
    del d["plugins"]["harness-reviewer"][JEV]
    d["plugins"]["jobcron-worker-glm-easy-1"][JEV] = "disabled     user     0.1.0    jev"


write("jev-plugin-missing.yaml", delta(jev_plugin_missing))


def compression_drift(d):
    # One profile carries a wrong value; another cannot report one key (unreadable);
    # one Claude worker profile carries a wrong compression threshold.
    d["profile_managed_settings"]["advisor"]["compression.threshold_tokens"] = 250000
    del d["profile_managed_settings"]["harness-orchestrator"]["compression.idle_compact_after_seconds"]
    d["profile_managed_settings"]["jobcron-worker"]["compression.threshold_tokens"] = 500000


write("compression-drift.yaml", delta(compression_drift))


def orchestrator_skill_settings_drift(d):
    # One orchestrator still has no pinned skill; another cannot report write_approval (unreadable).
    d["profile_managed_settings"]["jobcron-orchestrator"]["skills.auto_load"] = []
    del d["profile_managed_settings"]["anki-orchestrator"]["skills.write_approval"]


write("orchestrator-skill-settings-drift.yaml", delta(orchestrator_skill_settings_drift))


def fallback_drift(d):
    # Synthetic values only. One profile gained a main fallback the roster does not declare;
    # another gained an auxiliary fallback_chain entry carrying an extra credential-named field
    # (its value must never reach a message); a third cannot report its auxiliary mapping.
    settings = d["profile_fallback_settings"]
    settings["jobcron-worker"]["fallback_providers"] = [
        {"provider": "anthropic", "model": "synthetic-fallback-model"}]
    settings["harness-worker"]["auxiliary"]["title_generation"] = {"fallback_chain": [
        {"provider": "anthropic", "model": "synthetic-helper-model", "api_key": "synthetic-value-not-shown"}]}
    del settings["anki-worker"]["auxiliary"]


write("fallback-drift.yaml", delta(fallback_drift))


def glm_fallback_anthropic(d):
    # Card t_50fd66f2: one GLM worker falls back to the provider anthropic (the paid Console
    # key) instead of its roster fallback claude-subscription / claude-sonnet-5-5.
    d["profile_fallback_settings"]["harness-worker-glm-medium-1"]["fallback_providers"] = [
        {"provider": "anthropic", "model": "claude-sonnet-5-5"}]


write("glm-fallback-anthropic.yaml", delta(glm_fallback_anthropic))


def auxiliary_model_drift(d):
    # One profile still has a light task on the other-task model (helpers not switched yet);
    # another has a light task on a different provider; a third has an unset other-task model;
    # a fourth cannot report its auxiliary mapping.
    settings = d["profile_auxiliary_settings"]
    settings["harness-worker"]["auxiliary"]["title_generation"]["model"] = "claude-opus-5-5"
    settings["jss-reviewer"]["auxiliary"]["vision"]["provider"] = "anthropic"
    del settings["advisor"]["auxiliary"]["compression"]["model"]
    del settings["anki-worker"]["auxiliary"]


write("auxiliary-model-drift.yaml", delta(auxiliary_model_drift))


def plugin_auto_apply_enabled(d):
    # One profile applies plugin updates with no person involved (plugins.auto_apply: true).
    d["profile_plugin_auto_apply"]["harness-worker"]["plugins.auto_apply"] = True


write("plugin-auto-apply-enabled.yaml", delta(plugin_auto_apply_enabled))


def rogue(d):
    d["plugins"]["worker-flash-1"]["rogue-tool"] = "enabled      git 1.0.0    rogue-tool"


write("unexpected-plugin.yaml", delta(rogue))


def unused_provider_plugin(d):
    # claude-subscription is enabled on a retired profile whose model.provider and
    # fallback_providers do not name it, so it stays an unexpected plugin there.
    d["plugins"]["worker-flash-1"][CLAUDE_SUBSCRIPTION] = ENABLED_CLAUDE_SUBSCRIPTION


write("unused-provider-plugin.yaml", delta(unused_provider_plugin))


def missing_required(d):
    d["plugins"]["worker-luna-1"]["hermes-terminal-outcome-notification"] = f"disabled     git pinned@6ae2bf2d 0.2.0    {NOTIF}"


write("missing-plugin.yaml", delta(missing_required))


def pin_drift(d):
    d["plugins"]["worker-flash-1"]["ponytail"] = "disabled     git pinned@deadbeef 4.8.3    ponytail"


write("plugin-pin-drift.yaml", delta(pin_drift))


def ponytail_enabled(d):
    d["plugins"]["worker-flash-1"]["ponytail"] = ENABLED_PONY


write("ponytail-enabled-drift.yaml", delta(ponytail_enabled))


def ponytail_absent(d):
    del d["plugins"]["worker-terra-2"]["ponytail"]


write("ponytail-absent-drift.yaml", delta(ponytail_absent))


def ponytail_disabled_on_target(d):
    # Ponytail is installed but disabled on one profile that requires it enabled.
    d["plugins"]["harness-worker"][PONYTAIL] = DISABLED_PONY


write("ponytail-disabled-target-drift.yaml", delta(ponytail_disabled_on_target))


def ponytail_mode_line_absent(d):
    # The line PONYTAIL_DEFAULT_MODE=full is absent from the .env file of one profile.
    d["ponytail_mode_env"]["harness-worker-glm-medium-1"] = False


write("ponytail-mode-line-absent-drift.yaml", delta(ponytail_mode_line_absent))


def ponytail_revision_drift(d):
    # The ponytail clone of one profile that requires ponytail is at another revision.
    d["ponytail_install_metadata"]["jss-reviewer"]["revision"] = "0" * 40


write("ponytail-revision-drift.yaml", delta(ponytail_revision_drift))


def skill_divergence(d):
    set_skill_files(d)
    d["skill_files"]["multi-agent-coding-orchestrator"]["default"]["SKILL.md"] = "0" * 64


write("deployed-skill-divergence.yaml", delta(skill_divergence))


def chapt_profile_soul_drift(d):
    d["profile_soul_hashes"]["chapt-reviewer"] = "0" * 64


write("chapt-profile-soul-drift.yaml", delta(chapt_profile_soul_drift))


def project_repository_allowlist_drift(d):
    d["project_isolation"]["cha-pt"]["repositories"].append(
        "/Users/chanbla11mit/projects/not-authorized")


write("project-repository-allowlist-drift.yaml", delta(project_repository_allowlist_drift))


def project_repair_policy_drift(d):
    d["project_repair_policy"]["max_attempts_per_approach"] = 2


write("project-repair-policy-drift.yaml", delta(project_repair_policy_drift))


def project_repair_card_drift(d):
    strategy = "Use transaction fencing around the retry clock"
    d["project_repair_cards"] = [{
        "id": "t_fixture_repair",
        "board": "jobcron",
        "body": "repair_policy: bounded-convergence-v1",
        "comments": [{
            "body": "repair_history: " + json.dumps([{
                "approach_id": "a1",
                "strategy": strategy,
                "strategy_sha256": __import__("hashlib").sha256(strategy.encode()).hexdigest(),
                "material_difference_review_run_id": None,
                "attempts": [{
                    "candidate_commit": None,
                    "implementation_run_id": "worker-1",
                    "review_run_id": None,
                    "infrastructure_retries": 0,
                    "outcome": "pending",
                }],
            }], separators=(",", ":")),
        }],
    }]


write("project-repair-card-drift.yaml", delta(project_repair_card_drift))


def frontend_repository_policy_drift(d):
    d["repository_policy_hashes"]["cha-pt-frontend"] = "0" * 64


write("frontend-repository-policy-drift.yaml", delta(frontend_repository_policy_drift))


def skill_missing(d):
    set_skill_files(d)
    # Retired profiles are excluded from deployment checks, so the missing copy is a live one.
    del d["skill_files"]["minimal-implementation"]["harness-worker-2"]


write("skill-deployment-missing.yaml", delta(skill_missing))


def supporting_file_drift(d):
    set_skill_files(d)
    d["skill_files"]["production-deployment"]["jobcron-worker"]["references/release-ci-portability.md"] = "0" * 64


write("deployment-skill-supporting-file-drift.yaml", delta(supporting_file_drift))
write("astra-local-override.yaml", delta(set_skill_files))


def remove_terminal_notification(d):
    for plugins in d["plugins"].values():
        plugins.pop(NOTIF, None)


write("terminal-deployment-pending.yaml", delta(remove_terminal_notification))
write("terminal-notification-rollback.yaml", delta(remove_terminal_notification))


def terminal_retry_default_drift(d):
    d["terminal_retry_policy"]["default"] = "astra-until-approve-v1"


def terminal_retry_missing_scope(d):
    del d["terminal_retry_policy"]["required_card_metadata"]


def terminal_retry_missing_human_gate(d):
    d["terminal_retry_policy"]["human_gates"] = []


write("terminal-retry-default-drift.yaml", delta(terminal_retry_default_drift))
write("terminal-retry-missing-scope.yaml", delta(terminal_retry_missing_scope))
write("terminal-retry-missing-human-gate.yaml", delta(terminal_retry_missing_human_gate))


def drop_cha_pt(d):
    d["adapters"] = [{"repo": "cha-pt", "content": ""}, d["adapters"][1]]


write("adapter-missing.yaml", delta(drop_cha_pt))
write("incomplete-empty.yaml", {})


def drop_worker_sol(d):
    del d["profile_models"]["worker-sol"]


write("incomplete-omits-profile.yaml", delta(drop_worker_sol))


def pause_jobcron(d):
    d["adapters"] = [d["adapters"][0], {"repo": "jobcron", "content": "# adapter\nStatus: paused\n", "record": d["adapters"][1]["record"]}]


write("adoption-status-drift.yaml", delta(pause_jobcron))


def pause_record(d):
    rec = d["adapters"][0]
    d["adapters"] = [{"repo": "cha-pt", "content": rec["content"], "record": "/Users/chanbla11mit/projects/cha-pt/docs/archive/260919-hermes-orchestration-transition.md\nStatus: paused, adoption not validated."}, d["adapters"][1]]


write("adoption-record-drift.yaml", delta(pause_record))
print("ok:", sorted(p.name for p in fx.glob("*.yaml")))
