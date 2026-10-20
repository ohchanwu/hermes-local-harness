# Harness change: add Ray's scraper repo to the Cha PT fleet, with owner-approved pushes to its `main`

Implement this through your normal reviewed Harness workflow (desired-state source, independent review, deploy, readback). Keep the change minimal. Don't patch installed Hermes source or edit the Kanban database directly.

## Goal
Add exactly one more repository to the `chapt-orchestrator` controller's scope. Allow the controller (only the controller) to push reviewed commits to that repository's `main`, but only with the owner's explicit approval for each push.

## Repository
- Remote EXACT: `git@github.com:raysong-sudo/cha-webpt-website-sync.git` (web: `https://github.com/raysong-sudo/cha-webpt-website-sync`).
- Local checkout: use an existing authorized checkout if there is one. Otherwise create a clone at `/Users/chanbla11mit/projects/cha-webpt-website-sync`, unless you find a conflict.
- Hermes project: create a dedicated project (proposed slug `cha-webpt-website-sync`) bound to that checkout. Stock Kanban worktrees must then be created under that repository, not under the board's default backend root. The board stays `cha-pt`, and its default root stays unchanged.
- Historical observation, not a baseline: `main` = `172e831ed6921f339f81f4fd97561476445196b4`, and branch `codex/webpt-scraper-package-for-ty` = `2c292b1da23aa668897b3a76074794c0e32c645e`.
- Strict non-interactive SSH works for read and for receive-pack service discovery. No push has been attempted. GitHub API auth is down, so `main`'s branch protection is unknown. Don't repair credentials as part of this change.

## Surfaces to update consistently
- `chapt-orchestrator`'s injected system instructions. They currently say "exactly two repositories" and ban pushes. A skill update alone can't override them.
- The repo/worktree/baseline/contract validation and receipt checks for the controller, `chapt-worker`, `chapt-worker-glm-1`, `chapt-worker-glm-2` and `chapt-reviewer`.
- Any skills or templates that list the allowed repositories.

## Rules to encode
1. **Scope.** The allowlist becomes exactly three repos: `cha-pt`, `cha-pt-frontend` and the scraper repo. Each card is still pinned to one repo, one isolated worktree owned by that repo, one protected baseline and one explicit test contract. Reject any mismatch.
2. **Scraper cards** set Hermes project `cha-webpt-website-sync` and declare `Scraper project EXACT cha-webpt-website-sync.` Workers and the reviewer work only locally and stop at a tested, committed, independently reviewed handoff. They never push, open PRs or touch the remote.
3. **Controller push to `main`, per-push approval:**
   - A push requires an owner message in this chat that names the repo, `main` and the exact reviewed commit SHA (e.g. "Push `<sha>` to Ray's main"). Approval never carries over to another SHA, branch or repo. A general "go ahead" is not a push approval.
   - Before the push: fetch, then confirm the remote `main` is an ancestor of the approved SHA (fast-forward only). Confirm the SHA is the one `chapt-reviewer` approved.
   - Push with `git push <exact-remote> <sha>:refs/heads/main`. Never force-push, delete refs, or push tags or other branches.
   - After the push, read back `ls-remote` and report the result.
   - If remote `main` has moved, or the push is rejected (e.g. branch protection), stop and report. Don't rebase, merge or retry on your own. Any new commit goes back through a card, review and a fresh approval.
4. **Still prohibited:** PRs, merges via the API, workflow or branch-protection changes, credential repair, live WebPT capture/upload, scheduler/launchd activation, and putting tokens, patient data or real CSVs in prompts, Git or evidence.
5. **Preserve:** backend and frontend rules (including the `cha-pt-frontend` project and its editable/protected-path contract); existing cards and their recorded tuples, especially P4; history and counters; the Cha PT-only worker-stop rule (a stop affects only owned Cha PT workers, reviewers, previews and watchers, never Harness, Jobcron or anything unrelated); and no automatic restart from delayed callbacks.

## Tests (synthetic or read-only, no real push)
- A scraper card gets a worktree under the scraper checkout, and its review handoff works.
- Unknown repos and mismatched repo/project/worktree/baseline/contract/board/profile are rejected.
- Worker and reviewer push attempts are refused.
- The controller refuses to push without an approval naming the SHA, for a different SHA, for a non-fast-forward, with force, or to another ref.
- Backend and frontend routing are unchanged, existing cards are unchanged, and stop isolation still holds.

## Rollout
Deploy only the affected profiles and instructions. Don't restart the whole gateway or completed worker sessions by default. Tell me the exact step `chapt-orchestrator` needs to load the new instructions (refresh or fresh session), and give a rollback. Report the changed files, review result, deployed revision and anything still unresolved.
