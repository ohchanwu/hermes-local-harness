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

IMPL = ["worker-flash-1", "worker-flash-2", "worker-flash-3", "worker-luna-1", "worker-luna-2",
        "worker-terra-1", "worker-terra-2", "worker-glm-full", "worker-sol", "worker-astra",
        "jobcron-worker", "chapt-worker", "harness-worker", "jss-worker",
        "jobcron-worker-2", "chapt-worker-2", "harness-worker-2", "jss-worker-2",
        "anki-worker", "anki-worker-2"]
NOTIF = "hermes-terminal-outcome-notification"
ENABLED_NOTIF = f"enabled      git pinned@6ae2bf2d 0.2.0    {NOTIF}"
DISABLED_NOTIF = f"disabled     git pinned@6ae2bf2d 0.2.0    {NOTIF}"
DISABLED_PONY = "disabled     git pinned@16f29800 4.8.4    ponytail"
ENABLED_PONY = "enabled      git pinned@16f29800 4.8.4    ponytail"
# Observed `plugins list --plain` line of an enabled jev plugin (card t_4f7740d0). The
# source and version columns are assumed values: no pin is declared for jev, so
# check_plugins compares only the leading `enabled` status.
JEV = "jev"
ENABLED_JEV = f"enabled      user     0.1.0    {JEV}"


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
            if name in IMPL:
                plugins[name]["ponytail"] = DISABLED_PONY
        if JEV in roster_profiles[name].get("required_plugins", []):
            plugins[name][JEV] = ENABLED_JEV
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
# managed_profile_settings (mirrored in the snapshot) and orchestrator_profile_settings
# (roster.yaml only).
clean["profile_managed_settings"] = {}
for group in (desired["managed_profile_settings"], roster["orchestrator_profile_settings"]):
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
set_skill_files(clean)
clean["terminal_retry_policy"] = copy.deepcopy(
    json.loads((Path(__file__).resolve().parents[1] / "roster.yaml").read_text())["terminal_retry"])
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
    # t_4f7740d0 and one third GLM worker of card t_f4ce916d.
    d["dispatch_profiles"].remove("chapt-worker-glm-2")
    d["dispatch_profiles"].remove("anki-worker-glm-3")


write("glm-worker-dispatch-missing.yaml", delta(glm_worker_dispatch_missing))


def jev_plugin_missing(d):
    # jev is absent on one Claude profile and disabled on one GLM worker that require it.
    del d["plugins"]["harness-reviewer"][JEV]
    d["plugins"]["jobcron-worker-glm-1"][JEV] = "disabled     user     0.1.0    jev"


write("jev-plugin-missing.yaml", delta(jev_plugin_missing))


def compression_drift(d):
    # One profile carries a wrong value; another cannot report one key (unreadable).
    d["profile_managed_settings"]["advisor"]["compression.threshold_tokens"] = 250000
    del d["profile_managed_settings"]["harness-orchestrator"]["compression.idle_compact_after_seconds"]


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


def rogue(d):
    d["plugins"]["worker-flash-1"]["rogue-tool"] = "enabled      git 1.0.0    rogue-tool"


write("unexpected-plugin.yaml", delta(rogue))


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
