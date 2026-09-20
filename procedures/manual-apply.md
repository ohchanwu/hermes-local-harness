# Manual apply / reconstruction procedure

Reconstruct the non-secret harness from this repository using supported Hermes CLI commands only. No apply script exists by design. Every command below was verified against the live CLI on 2026-09-20.

Global settings are scoped: always pass `-p default` explicitly so results do not depend on the caller's active profile (reviewer/worker profiles report `null` for unset-scoped queries).

## 0. Recovery point (before any change)

    hermes -p default config path          # note config location
    git -C ~/.hermes/hermes-agent rev-parse HEAD   # record source commit (expect 7c6f21a5e12ba9b1c674ec9b410fa6b8c45de4f8)
    # create a private snapshot outside Git per decisions/260920-harness-baseline.md; never snapshot into this repo

## 1. Profiles

Create each roster profile (13 total: default, advisor, reviewer-sol, worker-flash-1/2/3, worker-luna-1/2, worker-terra-1/2, worker-glm-full, worker-sol, worker-astra):

    hermes profile create worker-flash-1 --description "Flash implementation lane"

Complete separate authorization per profile when a credential is required (`hermes` will prompt on first use; never copy OAuth stores between profiles).

Set model/provider per profile:

    hermes -p worker-flash-1 config set model.default glm-5.3-flash
    hermes -p worker-flash-1 config set model.provider zai
    hermes -p worker-luna-1 config set model.default gpt-5.6-luna
    hermes -p worker-luna-1 config set model.provider openai-codex
    # terra/sol/astra lanes → gpt-5.6-terra / gpt-5.6-sol / gpt-6-astra @ openai-codex
    # glm-full lane → glm-5.3 @ zai; default/advisor/reviewer-sol → gpt-5.6-sol @ openai-codex

## 2. Ponytail on implementation profiles (all nine + terra-2 spare; NOT default/reviewer-sol/advisor)

Install pinned from Git and enable:

    hermes -p worker-flash-1 plugins install https://github.com/DietrichGebert/ponytail.git --ref 16f29800fd2681bdf24f3eb4ccffe38be3baec6b --enable
    # repeat per implementation profile; --ref pins exactly; catalog does not list ponytail

Verify full mode (plugin default is `full`; the resolver honors `PONYTAIL_DEFAULT_MODE` and `~/.config/ponytail/config.json` — leave both unset unless a mode override is an approved change):

    hermes -p worker-flash-1 plugins list --plain --no-bundled
    # expect: enabled      git pinned@16f29800 4.8.4    ponytail

## 3. Deploy the shared skill (manual copy; never symlink)

    mkdir -p ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts
    cp skills/multi-agent-coding-orchestrator/SKILL.md ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md
    cp skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py ~/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/scripts/

## 4. Global kanban settings (default-scoped)

    hermes -p default config set kanban.max_in_progress_per_profile 1
    hermes -p default config unset kanban.max_in_progress   # must stay unset: it counts reviewer runs

## 5. Dispatch allowlist (five implementation lanes + reviewer-sol)

Use the canonical helper, which refuses to remove a running implementation profile:

    python3 skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py \
      worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2
    # helper appends reviewer-sol automatically; --dry-run previews; --limit caps pool size

## 6. Verify and commit

    ./scripts/verify-state        # must exit 0
    git add -A && git commit -m "Apply <change>"   # commit desired-state change separately from applying

## Boundaries

- Do not use this procedure for credentials; authorization happens per profile through the supported interface.
- Do not remove unexpected state merely because verification reports it; removal is a separately reviewed manual action.
- Do not change the Hermes source checkout; it stays clean at the pinned commit.
