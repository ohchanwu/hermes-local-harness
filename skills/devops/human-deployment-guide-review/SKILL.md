---
name: human-deployment-guide-review
description: "Use when reviewing a guide that a person runs against production. Six review steps that check the guide against the rules of the skill human-deployment-guide-writing."
version: 1.0.0
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [deployment, production, documentation, human-assisted, review]
    related_skills: [human-deployment-guide-writing]
---

# Human deployment guide review

This skill applies when you are the reviewer that the board designates and you review a guide that a person runs step by step against production on their own machine. In this skill, the operator is the person who runs the guide, the writer is the agent that wrote the guide, and the guide is one file that contains the steps.

The rule list for the review is the skill `human-deployment-guide-writing`. This skill does not repeat those rules, so that the review always uses the current rules of that skill.

## Review steps

1. Load the skill `human-deployment-guide-writing` with `skill_view(name="human-deployment-guide-writing")` before you read the guide, and use its numbered rules as the rule list. Do not review from memory or from a copy of the rules.
2. Check every rule of that skill against the guide line by line. Report each finding with the line number in the guide, the number of the rule that the line does not meet, and the change that the line needs.
3. Run the local parts of the guide in a new temporary directory, never in the operator's repository or home directory. Check the syntax of every command and every script with the shell that runs it, for example `zsh -n FILE` for a zsh script. Run every check and every script on made-up data; when a script contains a command that sends a request to a cloud account or connects to a host, do not run the script, and run each of its checks separately on made-up data. Compare every filled-in value, such as a commit ID, an AWS profile name, a region, a host name or a file path, with the repository, the Terraform configuration files and the production records of the project. Report each command that fails and each value that does not match as a finding.
4. Check the operator's machine read-only: the installed tools and their versions, the configured AWS profiles, and whether the repository is clean. For example, `command -v session-manager-plugin`, `go version`, `aws configure list-profiles` and `git status --porcelain` only read local state. Change nothing on the operator's machine. Never run anything against cloud accounts or hosts: do not run a command that sends a request to a cloud account or connects to a host, for example `aws sts get-caller-identity`, `aws sso login`, `aws ssm start-session`, `ssh`, `terraform plan` or `terraform apply`. Report each missing tool, each wrong version, each missing AWS profile and an unclean repository as a finding.
5. Reject any text in the guide that is not a concise explanation of a command, which states what the command does, why it is needed, and what it prints when it works. Reject any statement of what does not change. Report each rejected text with its line number as a finding.
6. Give the verdict on the review card: approve when there is no finding, or request changes with the list of all findings. Never edit the guide; the writer makes every change. When the writer sends a changed file, review the whole file again from step 1.
