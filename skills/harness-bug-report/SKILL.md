---
name: harness-bug-report
description: "Use when a Hermes or harness defect is suspected. File a harness-board card with evidence; never write outside your own repository."
version: 1.1.0
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [kanban, bug-report, harness]
---

# Harness bug report

This skill tells a project orchestrator how to report a suspected defect in Hermes or in the harness. The result is a card on the harness board. A harness worker then writes the `docs/bugs/` report and any fix in the harness repository, under the normal review procedure of the harness board. Section 8 states when the `advisor` profile may take the same two actions that section 2 authorizes.

## 1. When this skill applies

Apply this skill when the cause of a failure is in one of the following places:

- Hermes itself: the gateway, the Kanban dispatcher or the Kanban notifier, the context compressor, a provider adapter, or the command-line interface.
- A policy, skill or SOUL that the harness manages.
- The configuration of a worker profile.

The test is this question: would the same failure happen on another project's board with the same harness? If the answer is yes, the failure is a suspected harness defect.

Counter-case: a failure inside the project's own code, tests or data is not a harness defect. Report it as a card on the project's own board, not on the harness board.

When you are not sure which case applies, file a card on the harness board and state in the card body that you are not sure.

## 2. Authority

The owner explicitly authorized (2026-10-25) exactly these actions on board `harness` for every orchestrator that loads this skill:

- One `kanban_create` call per suspected defect.
- `kanban_comment` on a card that the same orchestrator filed.

These two actions are the only exception to the profile's rule against accessing another board. Every other action on the harness board remains prohibited: no other read, no other write, no claim, no unblock, no reassignment, and no comment on a card that this orchestrator did not file. There is no access to any other board under this skill.

The SOUL and the profile-local orchestrator skill still contain the general rule against accessing another board, and this skill names the one owner-authorized exception to that rule.

## 3. Evidence to collect before filing

Collect the following items and put all of them as text in the card body:

- The exact error text, or, when there is no error text, the observed behaviour and the expected behaviour.
- Local timestamps with the time zone, for example `2026-10-25 14:03 KST (UTC+09:00)`.
- The name of the filing profile.
- The project board and the card ID involved, if any.
- The session ID of the filing orchestrator, taken from the gateway session. Never guess a session ID; if it is not available, write that it is not available.
- Gateway log lines, if they are already visible to you.
- What the orchestrator already tried, and the result of each attempt.

The card body must contain no secret values, no tokens, no patient data or other personal data, and no raw `.env` content. Replace any such value with `[REDACTED]` and state what kind of value was removed, for example `[REDACTED] (API token)`.

## 4. How to file

Call the `kanban_create` tool with these arguments:

- board: `harness`
- assignee: `harness-worker`
- title: `<project>: <one-line defect>`, for example `jobcron: notifier sent no message when a card was blocked`
- body: the evidence from section 3

Do not use the command-line create (`hermes kanban ... create`) for this, because the command-line create does not subscribe the caller to the card.

Do not write any file under `/Users/chanbla11mit/hermes-local-harness`, and do not write any file under any repository that is not the orchestrator's own repository. Do not create a cron job. Do not send a message to the Harness Orchestrator directly.

## 5. After filing

`kanban_create` subscribes the filing session with delivery_mode `notify+wake`. The filing orchestrator is therefore woken when the harness card completes, is blocked, or asks for review.

Stay subscribed to the harness card: the filing orchestrator is the party that can confirm the fix on its own board.

When the filing orchestrator is woken because the harness card completed:

1. Re-test the original failure, if the failure is reproducible.
2. Add one comment on the harness card: "confirmed fixed", or "not fixed" followed by the new evidence, collected under the rules of section 3.

Then continue the project work. Do not wait for the harness card at any point.

## 6. What not to expect

Filing a card does not pause the project work. Filing a card does not authorize any workaround that changes harness-managed files in the project profile, such as the live SOUL, the live skills, or `config.yaml`.

If the defect blocks the project work, state that in the card body and tell the owner in chat.

## 7. When harness-orchestrator loads this skill

`harness-orchestrator` files its card on its own board `harness` under its normal card procedure. The exception in section 2 is not needed for it, because the harness board is its own board.

## 8. When the advisor profile loads this skill

The owner explicitly authorized (2026-10-25) the `advisor` profile to take exactly the two actions of section 2 on board `harness`:

- One `kanban_create` call per suspected defect.
- `kanban_comment` on a card that the advisor filed.

These two actions are the one owner-authorized exception to the advisor's default of read-only consultation. Every other action remains prohibited: no other board access, no claim, no unblock, no reassignment, no comment on a card that the advisor did not file, no file write, and no message to any orchestrator or to any orchestrator session.

This section applies when, during a consultation, the advisor's own investigation (for example of an orchestrator's stored transcript, of local files, or of system state) shows a failure that meets the test in section 1.

The advisor files the card without first asking the user, and states the ID of the card that it filed in the same reply to the user.

The advisor uses the arguments of section 4, with the title `<project>: <one-line defect>`, where `<project>` is the project whose work showed the defect, or `advisor` when no project is involved.

The evidence follows section 3, with these differences:

- The session ID is the advisor's own session ID.
- When the evidence comes from the stored transcript of another profile, give that profile name and that session ID, and quote only the lines that are needed, with secret values replaced as section 3 requires.

After filing, section 5 applies with "continue the consultation" in place of "continue the project work". Re-testing is limited to read-only observation.
