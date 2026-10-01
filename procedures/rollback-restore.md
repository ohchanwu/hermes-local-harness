# Rollback restore: timestamped private backup trees

Exact, per-profile and per-path restore commands for the two owner-only backup
trees created during the 2026-10-02 v0.4.0 reconciliation (task t_dc4c9113).
Every `cp` below was generated from the actual trees and validated
non-destructively against the live layout on 2026-10-02: each source exists,
each destination parent exists, and the backup-to-live mapping resolves with no
unmapped files. No restore command here was executed as part of validation.

## Scope and provenance

Tree 1 — `/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900`
(mode 0700, owner `chanbla11mit`): the pre-reconciliation live bytes taken
before the drifted notification-plugin copies were reinstalled and the drifted
worker-astra skill copies were restored to canonical. Contents per producer
profile (`default`, `reviewer-sol`, `worker-flash-1/2/3`, `worker-luna-1/2`,
`worker-terra-1`, `worker-glm-full`, `worker-sol`, `worker-astra`):
`hermes-terminal-outcome-notification/` payload (`README.md`, `__init__.py`,
`core.py`, `plugin.yaml`, `worker.py`, plus stale `__pycache__` bytecode) and,
for `worker-astra` only, the drifted copies of
`production-deployment/`, `production-deployment-planning/` (SKILL.md plus
`references/`) and the three declared overrides as `<skill>-SKILL.md`
(`spike`, `systematic-debugging`, `test-driven-development`).

Byte characterization (verified against harness Git history): `worker.py`
matches the current tracked 0.2.0-era source (b0fba95 through the pinned
`6ae2bf2db8c06ecd0fb7f58b9230a03eb7ec2a86`); `plugin.yaml` is 0.1.0-era
(matches `0bc6686`); `README.md`/`__init__.py`/`core.py` match no single
tracked ref — the backup is a byte-faithful snapshot of the drifted live
state, not a tracked canonical version. Restoring it deliberately reintroduces
that drift; see "Post-restore verification".

Tree 2 — `/Users/chanbla11mit/.hermes/private/harness-skill-backups/20261002T063137+0900`
(mode 0700): `SKILL.md.v0.3.3` (24749 B, mode 0600, sha256
`1b71f24b06d64ceba08c17ff5525283051e63dffd4fe48691282380748b64c97`), the
orchestrator skill at tracked version v0.3.3, superseded by the current v0.4.0
(`12bdbc9c036dc44f3e807b26118f311a1e6a0304a15e8717d18941b85aea01a0`).

Neither tree contains credentials or authentication stores: the inventory is
plugin code, skill markdown, and Python bytecode only. Never copy `auth.json`,
`state.db*`, `sessions/`, or any other profile content into these trees.

## Safety boundaries

- Restoring tree 1's plugin payload reverts producers below the reviewed pin
  `0.2.0@6ae2bf2db8c06ecd0fb7f58b9230a03eb7ec2a86`; `./scripts/verify-state`
  must then fail. The reviewed recovery back to desired state is the supported
  reinstall command in
  `procedures/hermes-terminal-outcome-notifications.md` — never a verifier or
  snapshot edit.
- Rendering, reloading, or changing the notification worker remains separately
  approval-gated; full deployment rollback (bootout, plist removal, plugin
  removal) follows the "Rollback" paragraph of
  `procedures/hermes-terminal-outcome-notifications.md`. This runbook restores
  file bytes only.
- Restoring tree 1's worker-astra deployment skills or tree 2's orchestrator
  SKILL.md reintroduces deployed-copy hash drift; the reviewed recovery is the
  tracked-source copy procedure in `procedures/manual-apply.md` section 4.

## Ownership and modes

Run as `chanbla11mit` (uid 501), the owner of both the backups and the live
paths. `cp -p` preserves each backup file's mode and mtime. Expected modes
after restore:

- restored payload/skill markdown: `-rw-r--r--` (0644)
- restored orchestrator `SKILL.md`: `-rw-------` (0600)
- destination directories below a profile root or `~/.hermes/skills`: 0755
- profile-scoped roots (`~/.hermes/profiles/<p>`, its `plugins/`, `skills/`): 0700
- both backup trees and everything under them: 0700 — do not widen.

If a destination directory is missing, recreate it before copying with the
`install -d` commands below (`-m 755` for nested directories; `-m 700` only
when rebuilding a profile-scoped root). Explicit normalization for the one
exceptional file:

    chmod 600 /Users/chanbla11mit/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md

Read-only mode audit after restoring (expect exactly 0644 on all restored
payload/skill files; any other mode is a restore defect):

    ls -l /Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification
    ls -l /Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment{,/references}
    ls -l /Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/{spike,systematic-debugging,test-driven-development}
    stat -f '%Sp %N' /Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900 /Users/chanbla11mit/.hermes/private/harness-skill-backups/20261002T063137+0900

## Restore commands (exact, per profile and path)

### 0. Recreate missing destination directories (only the ones that are absent)

    install -d -m 755 "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment/references"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning/references"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/spike"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/systematic-debugging"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/test-driven-development"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins"
    install -d -m 755 "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification"
    install -d -m 755 "/Users/chanbla11mit/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator"

Only when rebuilding a profile home from scratch, its scoped roots are 0700:

    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins"
    install -d -m 700 "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins"

### A. Notification plugin payload — 11 producers (drift tree)

    # default
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification/worker.py"

    # reviewer-sol
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-flash-1
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-flash-2
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-flash-3
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-luna-1
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-luna-2
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-terra-1
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-glm-full
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-sol
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification/worker.py"

    # worker-astra
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification/README.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification/README.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification/__init__.py" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification/__init__.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification/core.py" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification/core.py"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification/plugin.yaml" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification/plugin.yaml"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification/worker.py" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification/worker.py"

### B. worker-astra deployment skills (drift tree)

    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment/SKILL.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment/SKILL.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment/references/live-state-reconciliation.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment/references/live-state-reconciliation.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment/references/release-ci-portability.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment/references/release-ci-portability.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment-planning/SKILL.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning/SKILL.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment-planning/references/frontend-origin-separation.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning/references/frontend-origin-separation.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment-planning/references/temporary-cloud-bootstrap-iam.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning/references/temporary-cloud-bootstrap-iam.md"

### C. worker-astra declared overrides (drift tree)

Validated 2026-10-02: these three backup copies are byte-identical to the
current live overrides, so this block is presently a no-op; it is the exact
command set if any of those files is later damaged.

    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/spike-SKILL.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/spike/SKILL.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/systematic-debugging-SKILL.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/systematic-debugging/SKILL.md"
    cp -p "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/test-driven-development-SKILL.md" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/software-development/test-driven-development/SKILL.md"

### D. Orchestrator SKILL v0.3.3 (skill tree)

    cp -p "/Users/chanbla11mit/.hermes/private/harness-skill-backups/20261002T063137+0900/SKILL.md.v0.3.3" "/Users/chanbla11mit/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"

## Post-restore verification

Byte readback (expect no output beyond the documented `__pycache__` noise:
stale bytecode differs or is absent on one side; it is regenerable cache, not
restore material):

    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/default/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/reviewer-sol/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/reviewer-sol/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-1/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-flash-1/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-2/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-flash-2/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-flash-3/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-flash-3/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-1/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-luna-1/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-luna-2/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-luna-2/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-terra-1/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-terra-1/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-glm-full/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-glm-full/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-sol/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-sol/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/hermes-terminal-outcome-notification" "/Users/chanbla11mit/.hermes/profiles/worker-astra/plugins/hermes-terminal-outcome-notification"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment"
    diff -rq "/Users/chanbla11mit/.hermes/private/harness-drift-backups/20261002T064500+0900/worker-astra/production-deployment-planning" "/Users/chanbla11mit/.hermes/profiles/worker-astra/skills/devops/production-deployment-planning"
    cmp "/Users/chanbla11mit/.hermes/private/harness-skill-backups/20261002T063137+0900/SKILL.md.v0.3.3" "/Users/chanbla11mit/.hermes/skills/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"

Verifier — a restore is a deliberate return to drifted state, so
`./scripts/verify-state` from the harness root must fail with exactly these
indicators (any other failure is an unrelated defect):

- after section A: `plugin drift <profile>: hermes-terminal-outcome-notification expected pinned 0.2.0@6ae2bf2db8c06ecd0fb7f58b9230a03eb7ec2a86` for each restored producer;
- after section B: `deployed skill hash mismatch: production-deployment worker-astra/SKILL.md` and the matching `production-deployment-planning` line;
- after section D: `deployed skill hash mismatch: multi-agent-coding-orchestrator default/SKILL.md`.

## Reviewed recovery back to desired state

- Plugin pin: re-run the reviewed supported install per producer from
  `procedures/hermes-terminal-outcome-notifications.md`
  (`hermes -p <profile> plugins install https://github.com/ohchanwu/hermes-local-harness.git#plugins/hermes-terminal-outcome-notification --ref 6ae2bf2db8c06ecd0fb7f58b9230a03eb7ec2a86 --enable`).
- Deployed skills: re-copy from the tracked canonical sources per
  `procedures/manual-apply.md` section 4, then `./scripts/verify-state`.
- Tracked expectation changes: `git -C /Users/chanbla11mit/hermes-local-harness revert 1a88cc8` (reviewed rollback commit).
- Dispatch allowlist: canonical helper only, from a control-plane context
  (`python3 skills/multi-agent-coding-orchestrator/scripts/set-active-lanes.py worker-flash-1 worker-flash-2 worker-flash-3 worker-luna-1 worker-luna-2`).

## Change log

- 2026-10-02: created during task t_dc4c9113 revision 1 from a live inventory
  of both trees; all 65 `cp -p` sources and destination parents validated
  non-destructively; no restore executed.
