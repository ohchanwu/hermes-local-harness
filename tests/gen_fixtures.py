import copy
import json
from pathlib import Path

fx = Path(__file__).resolve().parent / "fixtures"
clean = json.loads((fx / "clean.yaml").read_text())
desired = json.loads((Path(__file__).resolve().parents[1] / "snapshots" / "sanitized-current-state.yaml").read_text())
roster = json.loads((Path(__file__).resolve().parents[1] / "roster.yaml").read_text())

IMPL = ["worker-flash-1", "worker-flash-2", "worker-flash-3", "worker-luna-1", "worker-luna-2",
        "worker-terra-1", "worker-terra-2", "worker-glm-full", "worker-sol", "worker-astra",
        "jobcron-worker", "jobcron-worker-glm-1", "jobcron-worker-glm-2",
        "chapt-worker", "chapt-worker-glm-1", "chapt-worker-glm-2"]
NOTIF = "hermes-terminal-outcome-notification"
ENABLED_NOTIF = f"enabled      git pinned@6ae2bf2d 0.2.0    {NOTIF}"
DISABLED_NOTIF = f"disabled     git pinned@6ae2bf2d 0.2.0    {NOTIF}"
DISABLED_PONY = "disabled     git pinned@16f29800 4.8.4    ponytail"
ENABLED_PONY = "enabled      git pinned@16f29800 4.8.4    ponytail"


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
    return plugins


def skill_files_map():
    """skill -> profile -> {rel: sha}, per the desired deploy_profiles matrix."""
    return {entry["name"]: {profile: copy.deepcopy(entry["files"])
                            for profile in entry["deploy_profiles"]}
            for entry in desired["skill"]["shared_skills"]}


def set_skill_files(d):
    d["skill_files"] = skill_files_map()
    d["profile_local_skill_overrides"] = copy.deepcopy(
        desired["skill"]["profile_local_skill_overrides"])


clean["profile_models"] = {profile["name"]: profile["model"] for profile in roster["profiles"]}
clean["profile_providers"] = {profile["name"]: profile["provider"] for profile in roster["profiles"]}
clean["profile_approval_modes"] = {
    profile: desired["approvals"]["mode"] for profile in desired["approvals"]["profiles"]}
clean["dispatch_profiles"] = copy.deepcopy(desired["kanban"]["dispatch_profiles"])
clean["kanban"] = {key: copy.deepcopy(value) for key, value in desired["kanban"].items()
                   if key != "dispatch_profiles"}
clean["project_isolation"] = copy.deepcopy(desired["project_isolation"])
clean["project_repair_policy"] = copy.deepcopy(desired["project_repair_policy"])
clean["project_repair_cards"] = []
clean["profile_soul_hashes"] = {
    profile: entry["sha256"] for profile, entry in desired["profile_souls"].items()}
clean["repository_policy_hashes"] = {
    name: entry["sha256"] for name, entry in desired["repository_policies"].items()}
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
    del d["skill_files"]["minimal-implementation"]["worker-terra-2"]


write("skill-deployment-missing.yaml", delta(skill_missing))


def supporting_file_drift(d):
    set_skill_files(d)
    d["skill_files"]["production-deployment"]["worker-astra"]["references/release-ci-portability.md"] = "0" * 64


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
