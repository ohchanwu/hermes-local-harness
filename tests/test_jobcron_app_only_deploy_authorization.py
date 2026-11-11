#!/usr/bin/env python3
"""The owner-requested application-only production deploy of jobcron-orchestrator (t_b7455361).

Offline checks of tracked repository files only: no live ~/.hermes reads, board
access, network or model calls. The section "Owner-requested application-only
production deploy" of the jobcron-orchestrator production-deployment skill
defines one standing exception to the prohibition on production and cloud
state, credentials, deployments, pushes and PRs. Line 7 of the
jobcron-orchestrator SOUL and the "### Autonomous" text of the
jobcron-orchestrator multi-agent-coding-orchestrator skill keep that
prohibition and refer to the section by name.

APP_ONLY_DEPLOY_EDITS lists the exact (new, old) text this card changed in each
file, so tests that pin older bytes of these files can reverse the change byte
for byte with reverse_app_only_deploy_edits(). The later deploy campaign change
(t_90a548ad) rewrote the section in the deployment skill; DEPLOY_CAMPAIGN_EDITS
lists its (new, old) text, and reverse_deploy_campaign_edits() must be applied
to the deployment skill before reverse_app_only_deploy_edits(). The checks in
this module read the current section; tests/test_jobcron_deploy_campaign.py
checks the deploy campaign rules in detail. This module imports only
test_fable_5_2_declared_model, which imports no other test module, so any test
module can import it.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import re
import subprocess
from pathlib import Path
import unittest

from test_fable_5_2_declared_model import reverse_fable_5_2_edits

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "jobcron-orchestrator"
SOUL = f"policies/profile-souls/{PROFILE}/SOUL.md"
ORCHESTRATOR_SKILL_RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
DEPLOYMENT_SKILL_RELATIVE = "devops/production-deployment/SKILL.md"
ORCHESTRATOR_SKILL = f"policies/profile-skills/{PROFILE}/{ORCHESTRATOR_SKILL_RELATIVE}"
DEPLOYMENT_SKILL = f"policies/profile-skills/{PROFILE}/{DEPLOYMENT_SKILL_RELATIVE}"
CHANGED_FILES = (SOUL, ORCHESTRATOR_SKILL, DEPLOYMENT_SKILL)

# Bytes of each file at baseline 0e6cc93d1a27f7dee1a77948155de46ab2c7941e,
# recovered by reversing APP_ONLY_DEPLOY_EDITS.
BASELINE_SHA256 = {
    SOUL: "9124a006cc3e7e7b77875a947593e6491c300a079239379953bf285fce999e02",
    ORCHESTRATOR_SKILL: "80b045b9877f329a1f321376b698c9ecde2a198d34b20655866708b6c8109076",
    DEPLOYMENT_SKILL: "3d6bb5c74e1b43c2742f3bad21cc0557503a8bcd816d64ffc60bba6bb9f5c39f",
}

SECTION_NAME = "Owner-requested application-only production deploy"
SECTION_REFERENCE = f'the section "{SECTION_NAME}" of the `production-deployment` skill'

SOUL_PROHIBITION = (
    "Never access or mutate Cha PT work, another board, production/cloud state, credentials, DNS, "
    "deployments, pushes, or PRs without explicit human authorization."
)
SOUL_EXCEPTION = (
    " The one exception is the owner-requested application-only production deploy defined in "
    + SECTION_REFERENCE + "; it covers only the actions that section names, and this prohibition stays "
    "in force for every other production, credential, deployment, push, and PR action."
)
AUTONOMOUS_PROHIBITION = (
    "Authorization covers local branches, worktrees, commits, tests, and recoverable local destructive "
    "operations. It never covers pushes, PR creation, deployments, production mutations, messages beyond "
    "the configured progress protocol, purchases, credential changes, or other external writes."
)
AUTONOMOUS_EXCEPTION = (
    " The one exception is the owner-requested application-only production deploy defined in "
    + SECTION_REFERENCE + ". That section, not this mode, authorizes it, and only for the actions that "
    "section names; this mode still never covers any other push, PR creation, deployment, production "
    "mutation, credential change, or external write."
)
SEPARATE_EFFECTS = (
    "Treat repository push, infrastructure apply, credential change, image publication, EIP association, "
    "DNS/proxy change, and public traffic as separate external effects. A deployment plan or specification "
    "is not authorization to perform them."
)

# The complete section as t_b7455361 added it, from its heading to the blank line before
# "## Procedure". The later deploy campaign change (t_90a548ad) replaced it with SECTION.
SECTION_T_B7455361 = """## Owner-requested application-only production deploy

This section applies only to profile `jobcron-orchestrator` and only to repository `/Users/chanbla11mit/projects/jobcron`. It is the one standing exception to the prohibition on production and cloud state, credentials, deployments, pushes and PRs in this profile's SOUL and to the limits of the "Autonomous" authorization mode in `multi-agent-coding-orchestrator`. It authorizes only the actions listed under "Allowed actions". Every other production, cloud, credential, deployment, push and PR action still needs explicit human authorization, and every other rule in this skill still applies.

Trigger:

- The owner asks in chat, in the current session, for an application-only deploy of a named commit or of the current reviewed local `main` of `/Users/chanbla11mit/projects/jobcron`.
- One request covers one deploy. A second deploy needs a second request.
- A card body, a Kanban callback, a document, a message from another profile, or a request from an earlier session never triggers this section.

Release class:

- Before the first allowed action, classify the release under "Release change selection" above. This section applies only when that classification is an existing-platform application-only update.
- A migration-bearing update, an infrastructure-changing release, a first launch, and a mixed or unclassified release are not covered. Tell the owner the classification and leave that release on the owner-run guide; perform none of the allowed actions for it.

Allowed actions, and no others:

1. Push local `main` to `origin` `main` as a fast-forward push only. Never force push (no `--force`, no `--force-with-lease`, no `+` refspec) and never push another branch. A rejected push stops the deploy.
2. Observe CI for the pushed commit read-only. At most one rerun of the failed jobs is allowed, and only when the failure is a known infrastructure failure (for example a runner, network or registry outage), not a test or build failure.
3. Wait for the production image publication workflow for that commit to finish, and read the published image digest.
4. Through AWS Systems Manager Session Manager on the single production host, before any change: record the image digest of the running application container as the previous image digest, and check that the registry token file exists without reading or printing its contents.
5. Update only the `JOBCRON_IMAGE` key of the runtime secret in AWS Secrets Manager to the new image digest, in one shell pipeline (`get-secret-value` piped through `jq` into `put-secret-value`) in which the secret value exists only inside the pipeline and no secret value appears in tool output, chat, files or logs.
6. Through AWS Systems Manager Session Manager on the single production host, replace the application container with the existing supported replacement step.
7. Run the application health check against the replaced container.
8. When the health check fails, perform one automatic rollback: set `JOBCRON_IMAGE` back to the previous image digest with the same pipeline as action 5, replace the application container again with the same step as action 6, and run the health check again. The deploy then ends, whatever the result.

Credentials:

- Use only the owner's existing `aws sso login` session for AWS profile `jobcron-admin`. Check that the session is valid before the first AWS action, without printing identifying values.
- Never sign in (never run `aws sso login` or any other sign-in command), never refresh an expired session (the session refresh paragraph under "Procedure" step 1 does not apply to this deploy), and never create, rotate, print, copy or store a credential. When the session has expired, stop and tell the owner.
- Never create a GitHub token. When the registry token on the host is missing or expired, stop and tell the owner; the owner creates, places and deletes that token.
- The pipeline in action 5 is the only permitted read of a secret value, and only inside that pipeline. Never run `get-secret-value` in any other command.

Reporting:

- Send no confirmation request before the push or before any later allowed action. The owner's chat request is the approval for each allowed action at its mutation boundary; record the request in the report.
- Send one report, at the end of the deploy or at a stop, with the deployed commit, the new image digest, the previous image digest, the health check result and the rollback result (not needed, succeeded or failed). At a stop, also name the step and the stop condition.

Stops: each of the following ends the deploy, and the one report states it:

- an ambiguous provider response (reconcile the effective state; do not repeat the request);
- a failed health check after the rollback;
- a failed rollback;
- an unexpected host state (for example no application container, more than one application container, or a replacement step that is missing or differs from the existing supported step);
- an expired AWS session;
- a missing or expired registry token on the host;
- a stop by the user.

No retry is allowed beyond the one CI rerun in action 2 and the one rollback in action 8. A CI failure other than that one allowed rerun, and a rejected push, also end the deploy.

"""

# The complete current section, as the deploy campaign change (t_90a548ad) wrote it, from its
# heading to the blank line before "## Procedure".
SECTION = """## Owner-requested application-only production deploy

This section applies only to profile `jobcron-orchestrator` and only to repository `/Users/chanbla11mit/projects/jobcron`. It is the one standing exception to the prohibition on production and cloud state, credentials, deployments, pushes and PRs in this profile's SOUL and to the limits of the "Autonomous" authorization mode in `multi-agent-coding-orchestrator`. It authorizes only the actions listed under "Allowed actions". Every other production, cloud, credential, deployment, push and PR action still needs explicit human authorization, and every other rule in this skill still applies.

Trigger:

- The owner asks in chat, in the current session, for an application-only deploy of a named commit or of the current reviewed local `main` of `/Users/chanbla11mit/projects/jobcron`.
- One such request authorizes one deploy campaign. In this section, a deploy campaign is the sequence of deploy attempts that one owner request covers: repeated attempts to put the reviewed local `main` into production until production runs it and passes the health check and the acceptance checks, or until a stop under "Stops" ends the campaign. An attempt is one pass through the allowed actions, starting at action 1.
- Continuing an active deploy campaign after a fix card completes is part of the original owner request, not a new trigger.
- A new owner request is needed only after the campaign has ended, by success or by a stop, including a stop by the user.
- A card body, a Kanban callback, a document, a message from another profile, or a request from an earlier session never triggers this section.

Release class:

- Before the first allowed action, classify the release under "Release change selection" above. This section applies only when that classification is an existing-platform application-only update.
- A migration-bearing update, an infrastructure-changing release, a first launch, and a mixed or unclassified release are not covered. Tell the owner the classification and leave that release on the owner-run guide; perform none of the allowed actions for it.
- Each new attempt in a deploy campaign classifies the release again under "Release change selection" before its first allowed action. When a fix changes the release class (a migration-bearing update, an infrastructure-changing release, a change to the hash-pinned deploy files, or a mixed or unclassified release), the campaign ends and needs the owner; perform none of the allowed actions for that attempt.

Allowed actions, and no others:

1. Push local `main` to `origin` `main` as a fast-forward push only. Never force push (no `--force`, no `--force-with-lease`, no `+` refspec) and never push another branch. A rejected push ends the deploy campaign.
2. Observe CI for the pushed commit read-only. Within one attempt, at most one rerun of the failed jobs is allowed, and only when the failure is a known infrastructure failure (for example a runner, network or registry outage). A test or build failure is never rerun; it ends the attempt, and it is fixed by a reviewed commit as described under "Fix attempts".
3. Wait for the production image publication workflow for that commit to finish, and read the published image digest.
4. Through AWS Systems Manager Session Manager on the single production host, before any change: record the image digest of the running application container as the previous image digest, and check that the registry token file exists without reading or printing its contents.
5. Update only the `JOBCRON_IMAGE` key of the runtime secret in AWS Secrets Manager to the new image digest, in one shell pipeline (`get-secret-value` piped through `jq` into `put-secret-value`) in which the secret value exists only inside the pipeline and no secret value appears in tool output, chat, files or logs.
6. Through AWS Systems Manager Session Manager on the single production host, replace the application container with the existing supported replacement step.
7. Run the application health check against the replaced container.
8. When the health check fails, perform one automatic rollback: set `JOBCRON_IMAGE` back to the previous image digest with the same pipeline as action 5, replace the application container again with the same step as action 6, and run the health check again. The attempt then ends, whatever the result; the campaign continues only as described under "Fix attempts".

Fix attempts:

- After a CI test or build failure in an attempt, the orchestrator may, without a new owner request: dispatch a fix card to the project's workers, require independent review of the fix on the same card, integrate the reviewed fix into local `main`, and start the next attempt at action 1 (fast-forward push, CI, image publication).
- After one failed health check with a successful rollback, the campaign continues only when the cause is diagnosed as an application defect and fixed by a reviewed commit through the same steps. Otherwise the campaign ends and needs the owner.
- Dispatching, reviewing and integrating a fix are local project work. They add no production, cloud, credential, push or PR action to the allowed actions.

Credentials:

- Use only the owner's existing `aws sso login` session for AWS profile `jobcron-admin`. Check that the session is valid before the first AWS action, without printing identifying values.
- Never sign in (never run `aws sso login` or any other sign-in command), never refresh an expired session (the session refresh paragraph under "Procedure" step 1 does not apply to this deploy), and never create, rotate, print, copy or store a credential. When the session has expired, stop and tell the owner.
- Never create a GitHub token. When the registry token on the host is missing or expired, stop and tell the owner; the owner creates, places and deletes that token.
- The pipeline in action 5 is the only permitted read of a secret value, and only inside that pipeline. Never run `get-secret-value` in any other command.

Reporting:

- Send no confirmation request before the push or before any later allowed action, in any attempt of the campaign. The owner's chat request is the approval for each allowed action at its mutation boundary; record the request in the report.
- When an attempt fails and a fix card is dispatched, send the owner a short progress note that names the failed attempt, the failed step and the fix card. The note contains no confirmation request, and the campaign continues without a reply.
- Send one report, at the end of the deploy campaign or at a stop, with the deployed commit, the new image digest, the previous image digest, the health check result and the rollback result (not needed, succeeded or failed). At a stop, also name the step and the stop condition.

Stops: each of the following ends the deploy campaign and needs the owner, and the one report states it:

- an ambiguous provider response (reconcile the effective state; do not repeat the request);
- a failed health check after the rollback;
- a failed rollback;
- an unexpected host state (for example no application container, more than one application container, or a replacement step that is missing or differs from the existing supported step);
- an expired AWS session;
- a missing or expired registry token on the host;
- a stop by the user;
- a rejected push;
- unexpected infrastructure drift (for example an out-of-band create, delete, stop, replacement or network change, as described under "Procedure" step 3);
- a release class change at a new attempt (see "Release class");
- a second failed health check of a newly deployed image in the same campaign, whatever the rollback result;
- a failed health check whose cause is not diagnosed as an application defect that a reviewed commit can fix;
- a product decision, that is, a choice about application behavior that only the owner can make;
- any other failure of an attempt or of a fix card that "Fix attempts" does not cover, for example a known infrastructure failure in CI that remains after the one allowed rerun in action 2, an infrastructure failure of the image publication workflow in action 3, a CI failure that is neither a known infrastructure failure nor a test or build failure, a failed acceptance check after a passed health check, or a fix card that ends without a reviewed fix for any other reason;
- exhaustion of the bounded repair limits of a fix card without a reviewed fix.

Retry limits within a deploy campaign: a CI test or build failure is never rerun; the next attempt starts at action 1 only after a reviewed fix commit is integrated into local `main`. A CI rerun is allowed only for a known infrastructure failure, at most once per attempt. Each attempt has at most one rollback (action 8), and a campaign has at most one failed health check of a newly deployed image. A provider request with an ambiguous response is never repeated. No other retry is allowed. Every failure that "Fix attempts" does not cover ends the deploy campaign as a stop under "Stops". Every attempt uses only the allowed actions above: a fast-forward push of local `main` to `origin` `main` only, never a force push and never another branch.

"""

APP_ONLY_DEPLOY_EDITS = {
    SOUL: (
        (SOUL_PROHIBITION + SOUL_EXCEPTION + "\n", SOUL_PROHIBITION + "\n"),
    ),
    ORCHESTRATOR_SKILL: (
        ("version: 0.6.9-jobcron.8\n", "version: 0.6.9-jobcron.7\n"),
        (AUTONOMOUS_PROHIBITION + AUTONOMOUS_EXCEPTION + "\n", AUTONOMOUS_PROHIBITION + "\n"),
    ),
    DEPLOYMENT_SKILL: (
        ("version: 0.2.5-jobcron.2\n", "version: 0.2.5-jobcron.1\n"),
        (SECTION_T_B7455361 + "## Procedure\n", "## Procedure\n"),
    ),
}

# The exact (new, old) text that the later deploy campaign change (t_90a548ad) made. It
# changed only the version line and this section of the deployment skill.
DEPLOY_CAMPAIGN_EDITS = {
    DEPLOYMENT_SKILL: (
        ("version: 0.2.5-jobcron.3\n", "version: 0.2.5-jobcron.2\n"),
        (SECTION + "## Procedure\n", SECTION_T_B7455361 + "## Procedure\n"),
    ),
}

STOPS_LABEL = "Stops: each of the following ends the deploy campaign and needs the owner, and the one report states it:"
STOP_CONDITIONS = (
    "- an ambiguous provider response (reconcile the effective state; do not repeat the request);",
    "- a failed health check after the rollback;",
    "- a failed rollback;",
    "- an unexpected host state (",
    "- an expired AWS session;",
    "- a missing or expired registry token on the host;",
    "- a stop by the user;",
    "- a rejected push;",
    "- unexpected infrastructure drift (",
    "- a release class change at a new attempt (",
    "- a second failed health check of a newly deployed image in the same campaign, whatever the rollback result;",
    "- a failed health check whose cause is not diagnosed as an application defect that a reviewed commit can fix;",
    "- a product decision, that is, a choice about application behavior that only the owner can make;",
    "- any other failure of an attempt or of a fix card that \"Fix attempts\" does not cover, for example ",
    "- exhaustion of the bounded repair limits of a fix card without a reviewed fix.",
)


def _reverse(edits, relative_path, text):
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in edits.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def reverse_app_only_deploy_edits(relative_path, text):
    """Return text with the edits of t_b7455361 reversed; text may be str or bytes. Reverse the
    later deploy campaign change first with reverse_deploy_campaign_edits()."""
    return _reverse(APP_ONLY_DEPLOY_EDITS, relative_path, text)


def reverse_deploy_campaign_edits(relative_path, text):
    """Return text with the edits of t_90a548ad reversed; text may be str or bytes."""
    return _reverse(DEPLOY_CAMPAIGN_EDITS, relative_path, text)


def markdown_section(text, heading):
    """The section that starts at the exact heading line and ends before the next heading of
    the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    match = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", text, re.M | re.S)
    assert match is not None, heading
    return match.group(0)


def block(section, label):
    """The list in the section that follows the line `label` and a blank line, up to the next
    blank line."""
    match = re.search(rf"^{re.escape(label)}\n\n(.*?)(?=\n\n|\Z)", section, re.M | re.S)
    assert match is not None, label
    return match.group(1)


def tracked_files(*prefixes):
    output = subprocess.run(["git", "ls-files", "-z", "--", *prefixes], cwd=ROOT, check=True,
                            capture_output=True).stdout.decode()
    return [path for path in output.split("\0") if path]


def load_verifier():
    loader = importlib.machinery.SourceFileLoader("verify_state_app_only_deploy",
                                                  str(ROOT / "scripts/verify-state"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AppOnlyDeployAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {path: (ROOT / path).read_text() for path in CHANGED_FILES}
        cls.section = markdown_section(cls.text[DEPLOYMENT_SKILL], f"## {SECTION_NAME}")

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in BASELINE_SHA256.items():
            with self.subTest(path=path):
                # Reverse the later deploy campaign change (t_90a548ad) and the later declared
                # Fable model change (t_a6bbe808) first.
                current = reverse_deploy_campaign_edits(path, (ROOT / path).read_bytes())
                current = reverse_fable_5_2_edits(path, current)
                original = reverse_app_only_deploy_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_exception_is_present_in_all_three_files(self):
        self.assertEqual(self.text[SOUL].splitlines()[6], SOUL_PROHIBITION + SOUL_EXCEPTION)
        autonomous = markdown_section(self.text[ORCHESTRATOR_SKILL], "### Autonomous")
        self.assertIn(AUTONOMOUS_PROHIBITION + AUTONOMOUS_EXCEPTION + "\n", autonomous)
        deployment = self.text[DEPLOYMENT_SKILL]
        self.assertEqual(re.findall(rf"(?m)^## {re.escape(SECTION_NAME)}$", deployment), [f"## {SECTION_NAME}"])
        self.assertEqual(self.section, SECTION)
        # The section follows "## Release change selection" and precedes "## Procedure".
        headings = re.findall(r"(?m)^## .+$", deployment)
        index = headings.index(f"## {SECTION_NAME}")
        self.assertEqual(headings[index - 1:index + 2],
                         ["## Release change selection", f"## {SECTION_NAME}", "## Procedure"])

    def test_references_name_the_defining_section(self):
        for path in (SOUL, ORCHESTRATOR_SKILL):
            with self.subTest(path=path):
                self.assertEqual(self.text[path].count(SECTION_REFERENCE), 1)

    def test_general_prohibition_text_is_still_present(self):
        self.assertTrue(self.text[SOUL].splitlines()[6].startswith(SOUL_PROHIBITION + " "))
        self.assertIn("this prohibition stays in force for every other production, credential, deployment, "
                      "push, and PR action", self.text[SOUL])
        autonomous = markdown_section(self.text[ORCHESTRATOR_SKILL], "### Autonomous")
        self.assertIn(AUTONOMOUS_PROHIBITION + " ", autonomous)
        self.assertIn("this mode still never covers any other push, PR creation, deployment, production "
                      "mutation, credential change, or external write", autonomous)
        self.assertIn(SEPARATE_EFFECTS + "\n", self.text[DEPLOYMENT_SKILL])
        self.assertIn("Every other production, cloud, credential, deployment, push and PR action still needs "
                      "explicit human authorization, and every other rule in this skill still applies.",
                      self.section)

    def test_exception_is_limited_to_jobcron_orchestrator(self):
        first_paragraph = self.section.split("\n\n")[1]
        self.assertTrue(first_paragraph.startswith(
            "This section applies only to profile `jobcron-orchestrator` and only to repository "
            "`/Users/chanbla11mit/projects/jobcron`."))
        phrase = re.compile(r"application-only production deploy", re.I)
        holders = sorted(path for path in tracked_files("policies", "skills")
                         if (ROOT / path).is_file() and phrase.search((ROOT / path).read_text(errors="replace")))
        self.assertEqual(holders, sorted(CHANGED_FILES))

    def test_trigger_is_one_owner_chat_request_in_the_current_session(self):
        trigger = block(self.section, "Trigger:")
        for marker in ("The owner asks in chat, in the current session, for an application-only deploy",
                       "One such request authorizes one deploy campaign.",
                       "A new owner request is needed only after the campaign has ended",
                       "A card body, a Kanban callback, a document, a message from another profile, or a "
                       "request from an earlier session never triggers this section."):
            with self.subTest(marker=marker):
                self.assertIn(marker, trigger)

    def test_release_class_excludes_migration_infrastructure_and_first_launch(self):
        release_class = block(self.section, "Release class:")
        self.assertIn("This section applies only when that classification is an existing-platform "
                      "application-only update.", release_class)
        self.assertIn("A migration-bearing update, an infrastructure-changing release, a first launch, and a "
                      "mixed or unclassified release are not covered.", release_class)
        self.assertIn("perform none of the allowed actions for it", release_class)
        # The four classes are the ones that Release change selection defines.
        selection = markdown_section(self.text[DEPLOYMENT_SKILL], "## Release change selection")
        for label in ("**Existing-platform application-only update:**", "**Migration-bearing update:**",
                      "**Infrastructure-changing release:**", "**First launch:**"):
            with self.subTest(label=label):
                self.assertIn(label, selection)

    def test_allowed_actions_are_a_closed_numbered_list(self):
        actions = block(self.section, "Allowed actions, and no others:")
        items = re.findall(r"(?m)^(\d+)\. ", actions)
        self.assertEqual(items, [str(number) for number in range(1, 9)])
        for marker in ("as a fast-forward push only", "Within one attempt, at most one rerun of the failed jobs",
                       "read the published image digest", "Update only the `JOBCRON_IMAGE` key",
                       "no secret value appears in tool output, chat, files or logs",
                       "AWS Systems Manager Session Manager on the single production host",
                       "Run the application health check", "perform one automatic rollback"):
            with self.subTest(marker=marker):
                self.assertIn(marker, actions)
        self.assertIn("No other retry is allowed.", self.section)

    def test_forbids_force_push_sign_in_credential_creation_and_github_token_creation(self):
        for marker in ("Never force push (no `--force`, no `--force-with-lease`, no `+` refspec) and never "
                       "push another branch.",
                       "Never sign in (never run `aws sso login` or any other sign-in command)",
                       "never refresh an expired session",
                       "never create, rotate, print, copy or store a credential",
                       "Never create a GitHub token.",
                       "Never run `get-secret-value` in any other command."):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.section)
        # The session refresh paragraph that the section excludes is under Procedure step 1.
        step_1 = markdown_section(self.text[DEPLOYMENT_SKILL], "### 1. Establish the operating mode and authority")
        self.assertIn("aws configure export-credentials", step_1)

    def test_names_every_stop_condition(self):
        stops = block(self.section, STOPS_LABEL)
        lines = stops.splitlines()
        self.assertEqual(len(lines), len(STOP_CONDITIONS))
        for line, start in zip(lines, STOP_CONDITIONS):
            with self.subTest(start=start):
                self.assertTrue(line.startswith(start), line)

    def test_reporting_is_one_report_with_no_confirmation_request(self):
        reporting = block(self.section, "Reporting:")
        self.assertIn("Send no confirmation request before the push", reporting)
        self.assertIn("with the deployed commit, the new image digest, the previous image digest, the health "
                      "check result and the rollback result", reporting)

    def test_versions_are_raised(self):
        self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.text[ORCHESTRATOR_SKILL]), ["0.6.9-jobcron.8"])
        self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.text[DEPLOYMENT_SKILL]), ["0.2.5-jobcron.3"])

    def test_snapshot_pins_match_the_file_hashes(self):
        snapshot = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_text())
        roster = json.loads((ROOT / "roster.yaml").read_text())
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        verifier = load_verifier()
        overrides = snapshot["skill"]["profile_local_skill_overrides"][PROFILE]
        for relative, path in ((ORCHESTRATOR_SKILL_RELATIVE, ORCHESTRATOR_SKILL),
                               (DEPLOYMENT_SKILL_RELATIVE, DEPLOYMENT_SKILL)):
            with self.subTest(path=path):
                self.assertEqual(overrides[relative], verifier.TRACKED_SOURCE)
                self.assertEqual(clean["profile_local_skill_overrides"][PROFILE][relative], verifier.TRACKED_SOURCE)
                self.assertEqual(verifier.local_override_expected(PROFILE, relative, overrides[relative]),
                                 hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        soul_entry = snapshot["profile_souls"][PROFILE]
        self.assertEqual(soul_entry, {"source": SOUL, "live": f"/Users/chanbla11mit/.hermes/profiles/{PROFILE}/SOUL.md"})
        self.assertEqual(roster["profile_souls"][PROFILE], soul_entry)
        self.assertEqual(clean["profile_soul_hashes"][PROFILE], verifier.TRACKED_SOURCE)
        self.assertEqual(verifier.profile_soul_expected(soul_entry),
                         hashlib.sha256((ROOT / SOUL).read_bytes()).hexdigest())
        # No desired-state or fixture file keeps a hash of the pre-change bytes.
        for path in ["snapshots/sanitized-current-state.yaml", "roster.yaml", *tracked_files("tests/fixtures")]:
            text = (ROOT / path).read_text(errors="replace")
            for changed, old_hash in BASELINE_SHA256.items():
                with self.subTest(path=path, changed=changed):
                    self.assertNotIn(old_hash, text)

    def test_new_text_is_ascii(self):
        for path, edits in (*APP_ONLY_DEPLOY_EDITS.items(), *DEPLOY_CAMPAIGN_EDITS.items()):
            for new, _old in edits:
                with self.subTest(path=path, new=new[:40]):
                    self.assertTrue(new.isascii())


if __name__ == "__main__":
    unittest.main()
