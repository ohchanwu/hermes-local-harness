import copy
import json
from pathlib import Path

fx = Path(__file__).resolve().parent / "fixtures"
clean = json.loads((fx / "clean.yaml").read_text())


def write(name, data):
    (fx / name).write_text(json.dumps(data, indent=2) + "\n")


def delta(mutate):
    d = copy.deepcopy(clean)
    mutate(d)
    return d


write("behavior-changing-model-drift.yaml", delta(lambda d: d["profile_models"].__setitem__("worker-terra-1", "wrong-model")))
write("active-extra.yaml", delta(lambda d: d["active_extras"].append("unapproved-running-profile")))
write("dormant-extra.yaml", delta(lambda d: d["dormant_extras"].append("unused-local-profile")))
write("unexpected-plugin.yaml", delta(lambda d: d["plugins"]["worker-flash-1"].__setitem__("rogue-tool", "enabled      git 1.0.0    rogue-tool")))
write("missing-plugin.yaml", delta(lambda d: d["plugins"]["worker-luna-1"].__setitem__("ponytail", "disabled     git pinned@16f29800 4.8.4    ponytail")))
write("deployed-skill-divergence.yaml", delta(lambda d: d["skill_files"].__setitem__("scripts/set-active-lanes.py", "0" * 64)))


def drop_cha_pt(d):
    d["adapters"] = [{"repo": "cha-pt", "content": ""}, d["adapters"][1]]


write("adapter-missing.yaml", delta(drop_cha_pt))
write("incomplete-empty.yaml", {})


def drop_worker_sol(d):
    del d["profile_models"]["worker-sol"]


write("incomplete-omits-profile.yaml", delta(drop_worker_sol))


def pause_jobcron(d):
    d["adapters"] = [d["adapters"][0], {"repo": "jobcron", "content": "# adapter\nStatus: paused\n"}]


write("adoption-status-drift.yaml", delta(pause_jobcron))
print("ok:", sorted(p.name for p in fx.glob("*.yaml")))
