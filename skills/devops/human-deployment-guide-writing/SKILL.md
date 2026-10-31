---
name: human-deployment-guide-writing
description: "Use when writing steps a person runs against production. Twelve rules for a guide file that the operator runs command by command."
version: 1.0.0
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [deployment, production, documentation, human-assisted]
---

# Human deployment guide writing

This skill applies when you write a guide that a person runs step by step against production on their own machine. In this skill, the operator is the person who runs the guide, and the guide is one file that contains the steps.

Follow all twelve rules. Each rule is followed by its reason in one sentence.

## Rules

1. Check the operator's machine before you write any step: the AWS profile and its SSO sign-in, the CLI plugins, the tool versions, the shell (zsh), and whether the repository is clean. Make anything that is missing step 0 of the guide, with its exact command.
   Reason: a command written for a machine that was not checked fails on the operator's machine, for example an AWS command without `--profile` uses an old default key, and an untracked file makes the repository unclean so that a later step refuses to run.

2. Fill in every value in every command. Use a placeholder only for a value that is created during the run, and make the command that creates that value store it in a shell variable that the later commands use.
   Reason: the operator cannot know a value that the writer of the guide already knew, such as a full commit ID, and a value that the operator copies by hand from earlier output can be copied wrongly.

3. Write every step as a command, never as a description of something to do.
   Reason: a description such as "sign in through your usual AWS session" leaves the operator to find a command, and the command that the operator finds is not the command that was tested.

4. Give each command a concise explanation of what it does, why it is needed, and what it prints when it works, so that the operator learns from the guide. Add no other text: no summary, no decisions, no history, no statements of what does not change, and no failure sections.
   Reason: other text makes the guide longer without making any command easier to run, and it can contain stale values, such as an old commit ID in a summary.

5. Make any step that is longer than a few lines, or that contains text to paste, a script file or a `pbcopy` block, and prepare that file or block before you hand over the guide. A `pbcopy` block is one command of the form `pbcopy <<'EOF'`, the text, and a line `EOF`, which puts the text on the macOS clipboard.
   Reason: long or multi-line text copied out of a rendered document breaks easily, and text to paste that the operator has no way to get stops the run.

6. Test every command locally up to the point where it would touch production: check the syntax and the quoting, check every `sudo` command that contains a file name pattern, and run every check on made-up data.
   Reason: errors of syntax, quoting and pattern expansion appear only when a command runs, for example in `sudo sha256sum /root/dir/*` the shell of the unprivileged user expands the pattern before `sudo` runs, so the command fails, while `sudo sh -c 'sha256sum /root/dir/*'` lets the shell of the root user expand it.

7. Make the guide self-contained: write every command in full in the guide, and do not refer to any other document.
   Reason: a reference such as "see section 8 of the main guide" makes the operator search another file, and that file can differ from the file that the writer had in mind.

8. Read every secret with a silent prompt, for example the zsh command `read -rs 'DB_PASSWORD?Database password: '`, which does not show the typed text. When a secret or another value must be kept for later, write only one line: "Store X in your password manager under entry Y."
   Reason: one entry in the operator's password manager keeps the value safe, while local files with restricted permissions add steps and leave copies of the secret on disk.

9. Before a step that cannot be undone, make the guide save only the values that are needed to undo that step.
   Reason: the values that are needed to undo a step are lost once the step runs, and saving any other value adds steps that the operator does not need.

10. Deliver the guide as one file at a fixed location, not in a scratch directory that is pruned, and send that file once as an attachment. Never send commands through chat. After a change, send the file again with the one line "changed step N", where N is the number of the changed step.
    Reason: chat platforms change command text, for example by masking a secret name as `***`, removing line breaks or converting file names to links, and a file in a pruned scratch directory disappears before the operator runs it.

11. Before the operator receives the guide, have it reviewed by the reviewer that the board designates, on a card of the project board, with the companion skill `human-deployment-guide-review`; the reviewer checks the guide against the twelve rules of this skill. Fix every requested change in the file, and have the file reviewed again.
    Reason: the writer of a guide does not see the gaps that stop the operator, and an independent review finds them before the operator runs the guide.

12. During the run, give short replies that answer the question that the operator asked, and ask before you change anything on the operator's machine.
    Reason: long or repeated replies hide the answer, a question that is not answered stops the run, and a change that the operator did not approve, such as deleting an untracked file, can remove the operator's work.

## Machine check for rule 1

Each of these commands only reads state:

- `echo "$SHELL"` prints `/bin/zsh` when the login shell is zsh.
- `aws configure list-profiles` lists the configured AWS profiles. Every AWS command in the guide names one of them with `--profile`.
- `aws sts get-caller-identity --profile PROFILE` prints the account and the role when the SSO sign-in of that profile is valid. When it fails, step 0 contains `aws sso login --profile PROFILE`.
- `command -v session-manager-plugin` prints a path when the Session Manager plugin of the AWS CLI is installed; `aws ssm start-session` needs it.
- The version command of each tool that the guide uses, for example `go version`, prints a version that you compare with the version that the repository requires, for example the `go` and `toolchain` lines of `go.mod`.
- `git status --porcelain` in the repository prints nothing when the repository is clean. It lists untracked files, including broken symbolic links.
