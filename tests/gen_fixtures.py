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
write("plugin-pin-drift.yaml", delta(lambda d: d["plugins"]["worker-flash-1"].__setitem__("ponytail", "enabled      git pinned@deadbeef 4.8.3    ponytail")))
write("deployed-skill-divergence.yaml", delta(lambda d: d["skill_files"].__setitem__("scripts/set-active-lanes.py", "0" * 64)))


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
    d["adapters"] = [{"repo": "cha-pt", "content": rec["content"], "record": "/Users/chanbla11mit/gt/cha_pt/mayor/rig/docs/superpowers/specs/260919-hermes-orchestration-transition.md\nStatus: paused, adoption not validated."}, d["adapters"][1]]


write("adoption-record-drift.yaml", delta(pause_record))
print("ok:", sorted(p.name for p in fx.glob("*.yaml")))
