import copy
import json
from pathlib import Path

fx = Path(__file__).resolve().parent / "fixtures"
clean = json.loads((fx / "clean.yaml").read_text())

ORCH_SKILL_SHA = "8ebad5c1649b67464d934cb38e935de326a82536621d9babdee649088498938e"
ORCH_HELPER_SHA = "157419c7c190b0a9f647271f7bd3839182f2e9324f8f9d74e43ec0553a5b77df"
MINIMPL_SKILL_SHA = "a017ca2b203644ce6d5bd688c0b06875bbbe3908fe9dc6212ff39098ab53d794"
SIMPREV_SKILL_SHA = "d058cd37b2cf161097dfc51eafd373414603f5feb22ff22e8fe1e198679edb47"

IMPL = ["worker-flash-1", "worker-flash-2", "worker-flash-3", "worker-luna-1", "worker-luna-2",
        "worker-terra-1", "worker-terra-2", "worker-glm-full", "worker-sol", "worker-astra"]
NOTIF = "hermes-terminal-outcome-notification"
ENABLED_NOTIF = f"enabled      git pinned@7d38611e 0.1.0    {NOTIF}"
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
    for name in clean["profile_models"]:
        if name == "advisor":
            plugins[name] = {}
        elif name == "default" or name == "reviewer-sol":
            plugins[name] = {NOTIF: ENABLED_NOTIF}
        else:
            plugins[name] = {NOTIF: ENABLED_NOTIF}
            if name in IMPL:
                plugins[name]["ponytail"] = DISABLED_PONY
    return plugins


def skill_files_map():
    """skill -> profile -> {rel: sha}, per the desired deploy_profiles matrix."""
    return {
        "multi-agent-coding-orchestrator": {
            profile: {
                "SKILL.md": ORCH_SKILL_SHA,
                "scripts/set-active-lanes.py": ORCH_HELPER_SHA,
            } for profile in ["default"]
        },
        "minimal-implementation": {
            profile: {"SKILL.md": MINIMPL_SKILL_SHA} for profile in IMPL
        },
        "simplification-review": {
            profile: {"SKILL.md": SIMPREV_SKILL_SHA} for profile in IMPL
        },
    }


def set_skill_files(d):
    d["skill_files"] = skill_files_map()


write("behavior-changing-model-drift.yaml", delta(lambda d: d["profile_models"].__setitem__("worker-terra-1", "wrong-model")))
write("active-extra.yaml", delta(lambda d: d["active_extras"].append("unapproved-running-profile")))
write("dormant-extra.yaml", delta(lambda d: d["dormant_extras"].append("unused-local-profile")))


def rogue(d):
    d["plugins"]["worker-flash-1"]["rogue-tool"] = "enabled      git 1.0.0    rogue-tool"


write("unexpected-plugin.yaml", delta(rogue))


def missing_required(d):
    d["plugins"]["worker-luna-1"]["hermes-terminal-outcome-notification"] = f"disabled     git pinned@7d38611e 0.1.0    {NOTIF}"


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
    d["skill_files"]["minimal-implementation"]["worker-flash-1"]["SKILL.md"] = "0" * 64


write("deployed-skill-divergence.yaml", delta(skill_divergence))


def skill_missing(d):
    set_skill_files(d)
    del d["skill_files"]["minimal-implementation"]["worker-terra-2"]


write("skill-deployment-missing.yaml", delta(skill_missing))


def remove_terminal_notification(d):
    for plugins in d["plugins"].values():
        plugins.pop(NOTIF, None)


write("terminal-deployment-pending.yaml", delta(remove_terminal_notification))
write("terminal-notification-rollback.yaml", delta(remove_terminal_notification))


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
    d["adapters"] = [{"repo": "cha-pt", "content": rec["content"], "record": "/Users/chanbla11mit/gt/cha_pt/mayor/rig/docs/specs/260919-hermes-orchestration-transition.md\nStatus: paused, adoption not validated."}, d["adapters"][1]]


write("adoption-record-drift.yaml", delta(pause_record))
print("ok:", sorted(p.name for p in fx.glob("*.yaml")))
