# Decision: reviewers on Claude Opus 5.5, orchestrators on Claude Fable 5.2

Date: 2026-11-13

## Decision

Since 2026-11-13 the five reviewer profiles (`jobcron-reviewer`, `chapt-reviewer`, `harness-reviewer`, `jss-reviewer`, `anki-reviewer`) run the model `claude-opus-5-5` with reasoning effort `high`, and the six orchestrator profiles (`default`, `jobcron-orchestrator`, `chapt-orchestrator`, `harness-orchestrator`, `jss-orchestrator`, `anki-orchestrator`) run the model `claude-fable-5-2` with reasoning effort `medium`. The primary provider is `claude-subscription`; the fallback provider is `anthropic` with the same model. The reasoning effort of each role is recorded in [`procedures/switching-hermes-models.md`](../../procedures/switching-hermes-models.md), section "Role models and reasoning effort"; neither `roster.yaml` nor `scripts/switch-profile-model` holds it.

Before the change the reviewers ran `claude-fable-5-2` (and `claude-fable-5-1` until 2026-11-11), and the orchestrators ran `claude-opus-5-5`.

The change is recorded in card `t_0faca45d` on board `harness`, in its two commits `1951001577f28aef032fa0fcca3e2c023a929691` and `5a9da41923232e79ff74ab0185f0b6aa6be17ff7`, in `roster.yaml` (the `model` and `fallback_providers` values of the eleven profiles), and in `scripts/switch-profile-model` (the target table that switches a profile to `claude-opus` or `claude-fable`).

## Reasons

Three reasons, in this order.

### Measured use

In the measured period (section "Measurement" below) the reviewer profiles used more tokens than the orchestrator profiles. The reviewers made 2,412 model calls with 47,464,681 new input tokens and 4,396,124 output tokens; the orchestrators made 1,793 model calls with 22,782,739 new input tokens and 1,690,387 output tokens. The ratio of the reviewer values to the orchestrator values, each rounded to two decimal places, is:

- model calls: 1.35
- new input tokens: 2.08
- output tokens: 2.60

### Weekly limit of `claude-fable-5-2`

`claude-fable-5-2` has its own weekly limit on the account. Two repository places state it:

- [`plugins/model-providers/claude-subscription/README.md`](../../plugins/model-providers/claude-subscription/README.md): "Pinning Opus keeps Fable homes off Fable's weekly cap."
- [`docs/specs/261017-claude-subscription-helper-support.md`](../specs/261017-claude-subscription-helper-support.md): "Pinning Opus explicitly keeps the helpers of Fable profiles (reviewers, Advisor) off Fable's weekly cap."

The repository states no number for the limit, and this document gives none.

The owner's sentence of 2026-11-13: "Fable has its own weekly limit, so the role that uses fewer tokens (orchestrators) runs on Fable and the role that uses more (reviewers) runs on Opus 5.5".

### Price

The owner's statement of 2026-11-13: "Fable simply costs more per token than Opus." The repository holds no price data, and this document gives no price figure.

## Measurement

Period: 2026-11-11 00:00:00 up to, not including, 2026-11-13 20:00:00, local time Asia/Seoul.

Source: the lines that contain `API call #` in the files `logs/agent.log*` of the ten profiles `<prefix>-orchestrator` and `<prefix>-reviewer` for the prefixes `harness`, `jobcron`, `chapt`, `jss` and `anki`. The profile `default` is not in the measurement.

The recorded output of the run and the script that produced it are kept outside the repository at `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/cache/scratch/modeldoc/token_stats_261111_261113.txt` and `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/cache/scratch/modeldoc/token_stats.py`. The appendix copies the script byte for byte.

Four values are counted per call:

- `input`: all input tokens of a call.
- `cached_input`: the first number of the `cache=` field: input tokens read from the prompt cache.
- `new_input`: `input` minus `cached_input`.
- `output`: the output tokens of a call.

### Calls and tokens per profile and role

| Profile | Role | Model calls | Input | Cached input | New input | Output |
| --- | --- | --- | --- | --- | --- | --- |
| `harness-orchestrator` | orchestrator | 604 | 70,295,788 | 63,765,847 | 6,529,941 | 603,241 |
| `jobcron-orchestrator` | orchestrator | 562 | 79,075,420 | 71,218,404 | 7,857,016 | 487,196 |
| `chapt-orchestrator` | orchestrator | 20 | 2,525,755 | 2,378,032 | 147,723 | 15,828 |
| `jss-orchestrator` | orchestrator | 607 | 78,268,120 | 70,020,061 | 8,248,059 | 584,122 |
| `anki-orchestrator` | orchestrator | 0 | 0 | 0 | 0 | 0 |
| Total orchestrator | | 1,793 | 230,165,083 | 207,382,344 | 22,782,739 | 1,690,387 |
| `harness-reviewer` | reviewer | 736 | 77,906,754 | 69,822,557 | 8,084,197 | 973,968 |
| `jobcron-reviewer` | reviewer | 1,063 | 160,768,670 | 142,779,971 | 17,988,699 | 1,808,342 |
| `chapt-reviewer` | reviewer | 6 | 354,037 | 280,610 | 73,427 | 9,790 |
| `jss-reviewer` | reviewer | 607 | 73,809,280 | 52,490,922 | 21,318,358 | 1,604,024 |
| `anki-reviewer` | reviewer | 0 | 0 | 0 | 0 | 0 |
| Total reviewer | | 2,412 | 312,838,741 | 265,374,060 | 47,464,681 | 4,396,124 |

### Calls and output tokens per role and model

| Role | Model | Model calls | Output tokens |
| --- | --- | --- | --- |
| Orchestrator | `claude-fable-5-2` | 178 | 366,085 |
| Orchestrator | `claude-opus-5-5` | 1,615 | 1,324,302 |
| Reviewer | `claude-fable-5-1` | 98 | 132,916 |
| Reviewer | `claude-fable-5-2` | 2,182 | 4,165,545 |
| Reviewer | `claude-opus-5-5` | 132 | 97,663 |

### First and last call per profile and model

| Profile | Model | First call | Last call |
| --- | --- | --- | --- |
| `harness-orchestrator` | `claude-fable-5-2` | 2026-11-13 12:21:10 | 2026-11-13 19:59:01 |
| `harness-orchestrator` | `claude-opus-5-5` | 2026-11-11 10:25:07 | 2026-11-13 19:08:40 |
| `jobcron-orchestrator` | `claude-fable-5-2` | 2026-11-13 12:11:46 | 2026-11-13 18:24:21 |
| `jobcron-orchestrator` | `claude-opus-5-5` | 2026-11-11 10:34:31 | 2026-11-13 16:48:23 |
| `chapt-orchestrator` | `claude-opus-5-5` | 2026-11-12 16:35:39 | 2026-11-12 16:49:11 |
| `jss-orchestrator` | `claude-fable-5-2` | 2026-11-13 18:23:18 | 2026-11-13 19:59:28 |
| `jss-orchestrator` | `claude-opus-5-5` | 2026-11-11 10:34:17 | 2026-11-13 19:51:20 |
| `harness-reviewer` | `claude-fable-5-1` | 2026-11-11 10:53:44 | 2026-11-11 12:04:06 |
| `harness-reviewer` | `claude-fable-5-2` | 2026-11-11 12:33:10 | 2026-11-13 12:27:16 |
| `harness-reviewer` | `claude-opus-5-5` | 2026-11-13 12:27:38 | 2026-11-13 15:07:22 |
| `jobcron-reviewer` | `claude-fable-5-1` | 2026-11-11 10:50:43 | 2026-11-11 12:11:10 |
| `jobcron-reviewer` | `claude-fable-5-2` | 2026-11-11 14:58:47 | 2026-11-13 12:12:00 |
| `jobcron-reviewer` | `claude-opus-5-5` | 2026-11-13 14:08:14 | 2026-11-13 14:20:00 |
| `chapt-reviewer` | `claude-fable-5-2` | 2026-11-12 16:41:57 | 2026-11-12 16:45:13 |
| `jss-reviewer` | `claude-fable-5-1` | 2026-11-11 11:47:58 | 2026-11-11 12:23:41 |
| `jss-reviewer` | `claude-fable-5-2` | 2026-11-11 12:26:08 | 2026-11-12 00:30:13 |

`anki-orchestrator` and `anki-reviewer` have no row in this table because they have no call in the period.

## Limits of the measurement

- Most of the period lies before the change. The first call of an orchestrator profile on `claude-fable-5-2` in the period is on 2026-11-13 at 12:11:46 (`jobcron-orchestrator`), and the first call of a reviewer profile on `claude-opus-5-5` is on 2026-11-13 at 12:27:38 (`harness-reviewer`); the third table above gives the times for each profile. Orchestrator profiles also have calls on `claude-opus-5-5` after those times; the measurement did not determine the cause. In the period the reviewers made 2,280 of their 2,412 calls on a Fable model, and the orchestrators made 1,615 of their 1,793 calls on `claude-opus-5-5`. The numbers therefore show how much each role reads and writes. They do not show the use after the change.
- A token count is not the share of the plan allowance that was used: this document does not know how the plan weighs a `claude-fable-5-2` token against a `claude-opus-5-5` token.
- The period is about three days. `anki-orchestrator` and `anki-reviewer` have no call in the period; `chapt-orchestrator` has 20 calls and `chapt-reviewer` has 6.
- A log line without a `cache=` field counts as 0 cached tokens, so `new_input` is slightly too high and `cached_input` slightly too low.
- The log files rotate, so a later run of the script over the same period can find fewer lines.

## Appendix

The command of 2026-11-13 and the script `token_stats.py` that produced the recorded output, copied byte for byte into one fenced code block:

```
/Users/chanbla11mit/.hermes/hermes-agent/venv/bin/python -I token_stats.py "2026-11-11 00:00:00" "2026-11-13 20:00:00"

"""Sum the token counts of the "API call #" lines in the agent logs of the orchestrator and
reviewer profiles. Reads only those log lines; prints counts only."""
import collections, glob, re, sys
START, END = sys.argv[1], sys.argv[2]  # "YYYY-MM-DD HH:MM:SS", local time, END exclusive
RX = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*API call #\d+: model=(\S+).*? in=(\d+) out=(\d+)(?:.*? cache=(\d+)/\d+)?")
ROOT = "/Users/chanbla11mit/.hermes/profiles"
for role in ("orchestrator", "reviewer"):
    total = collections.Counter(); models = collections.Counter()
    for prefix in ("harness", "jobcron", "chapt", "jss", "anki"):
        c = collections.Counter(); first = {}; last = {}
        for path in sorted(glob.glob(f"{ROOT}/{prefix}-{role}/logs/agent.log*")):
            for line in open(path, errors="replace"):
                m = RX.match(line)
                if not m or not (START <= m.group(1) < END):
                    continue
                cached = int(m.group(5) or 0)
                c["calls"] += 1; c["input"] += int(m.group(3)); c["cached"] += cached; c["output"] += int(m.group(4))
                models[(m.group(2), "calls")] += 1; models[(m.group(2), "output")] += int(m.group(4))
                first.setdefault(m.group(2), m.group(1)); first[m.group(2)] = min(first[m.group(2)], m.group(1))
                last[m.group(2)] = max(last.get(m.group(2), ""), m.group(1))
        print(f"{prefix}-{role}: calls={c['calls']} input={c['input']} cached_input={c['cached']} "
              f"new_input={c['input'] - c['cached']} output={c['output']}")
        for model in sorted(first):
            print(f"    {model}: first {first[model]} last {last[model]}")
        total.update(c)
    print(f"TOTAL {role}: calls={total['calls']} input={total['input']} cached_input={total['cached']} "
          f"new_input={total['input'] - total['cached']} output={total['output']}")
    for model in sorted({k[0] for k in models}):
        print(f"    {model}: calls={models[(model, 'calls')]} output={models[(model, 'output')]}")
    print()

```
