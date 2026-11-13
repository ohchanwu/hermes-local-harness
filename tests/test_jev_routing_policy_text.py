#!/usr/bin/env python3
"""Policy text of the GLM routing request of 2026-11-13 (card t_ac454595).

Offline checks of tracked repository files only: no live /Users/chanbla11mit/.hermes
reads, board access, network or model calls.

The card states in the policy sources of the five boards:
- Part 2: the orchestrator skills refer to the route criteria in
  plugins/jev/config.json and restate no other criterion text;
- Part 4.6: after the fifth change request on a card that a GLM worker
  implements, the `jev` plugin reassigns the card to a Claude worker of the
  board; neither the orchestrator (five skills) nor the reviewer (five reviewer
  SOULs) reverses it or treats it as an assignee mismatch, and
  scripts/jev-peak-hold does not hold a card of a Claude worker;
- Part 5: the rule for splitting a card that needs a design decision, and the
  reworded passages of the Jobcron and Cha PT skills that discouraged
  splitting;
- Part 6.3: the attachment and diff procedure of the GLM workers (the eight GLM
  worker SOULs in this repository; the two Jobcron GLM worker SOULs have no
  repository source, so procedures/jev-plugin.md holds their exact text);
- Part 8.7 and 8.8: route disabling needs the owner's permission.

ROUTING_POLICY_EDITS lists the exact (new, old) text this card changed in each
file under policies/, so tests that pin older bytes of these files can reverse
the change byte for byte with reverse_jev_routing_policy_edits().
test_jev_policy_sources.reverse_jev_policy_edits() calls it first. This module
imports no other test module, so any test module can import it.
"""
import hashlib
import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
HOLD_SCRIPT = "/Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold"
BASELINE = "18b8372c31935888f9830638a0ce85fcb955b83c"

# Key -> (Kanban board name, profile prefix, Claude workers, GLM workers)
BOARDS = {
    "harness": ("harness", "harness", ("harness-worker", "harness-worker-2"),
                ("harness-worker-glm-1", "harness-worker-glm-2")),
    "chapt": ("cha-pt", "chapt", ("chapt-worker", "chapt-worker-2"),
              ("chapt-worker-glm-1", "chapt-worker-glm-2")),
    "jobcron": ("jobcron", "jobcron", ("jobcron-worker", "jobcron-worker-2"),
                ("jobcron-worker-glm-1", "jobcron-worker-glm-2")),
    "jss": ("jss-genr", "jss", ("jss-worker", "jss-worker-2"), ("jss-worker-glm-1", "jss-worker-glm-2")),
    "anki": ("anki", "anki", ("anki-worker", "anki-worker-2"), ("anki-worker-glm-1", "anki-worker-glm-2")),
}
# The GLM worker SOULs in this repository (the jobcron GLM workers have none).
GLM_SOUL_KEYS = ("harness", "chapt", "jss", "anki")


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def _pair(names):
    return f"`{names[0]}` or `{names[1]}`"


# tests/test_jev_policy_sources.py allows the name jev in these files only as "`jev` plugin" and in
# "jev-peak-hold". tests/test_fleet_autonomy_policy.py and tests/test_jss_fleet_policy.py forbid
# Harness profile names and the harness repository path (except the peak-hours hold script) in the
# Jobcron, Cha PT and jss-genr skills, the anki skill limits the harness files the anki fleet reads, and
# tests/test_anki_fleet_policy.py allows no other path in the anki SOULs. So the texts name the
# plugin's configuration file in words, and only the Harness copy names the procedure and
# `harness-orchestrator`.
PROCEDURE = "the procedure of the `jev` plugin in `/Users/chanbla11mit/hermes-local-harness/procedures/`"

# Part 5, exact text of the GLM routing request.
SPLIT_RULE = ("When a card needs a design decision, split off every part that has its own acceptance check and "
              "needs no design decision into a separate card that depends on the design card. Name the exact files "
              "and the exact check command in that card.")

# Part 8.8 (the Constraints section of the request): the same text in all five skills.
ROUTE_DISABLING_RULE = (
    "Route disabling needs the owner's permission. No profile, script, scheduled job or plugin code turns off a "
    "route (a route's `enabled` set to false, a route removed, or a board's `glm_workers` emptied) unless the owner "
    "has first been notified with the figures and has stated permission for that route. This also applies to a "
    "rollback that turns off a route, and to `routing.enabled` set to false, which turns off every route of every "
    "board."
)
# Part 8.7, the step after the owner's statement.
ROUTE_DISABLING_STEP_HARNESS = (
    "A weekly scheduled job of this profile notifies the owner with the figures (see "
    f"{PROCEDURE}, section \"Report of Claude tokens saved, and the owner notification before a route is turned "
    "off\"). After an owner statement that names the route, `harness-orchestrator` (this profile) sets that "
    "route's `enabled` to false in the file `config.json` of the `jev` plugin in this repository, installs the "
    "plugin by the normal procedure (section \"Install on a profile\" of the same procedure) and reports the change "
    "to the owner. Without such a statement nothing changes."
)
ROUTE_DISABLING_STEP_PROJECT = (
    "A weekly scheduled job notifies the owner with the figures. After an owner statement that names the route, "
    "that route's `enabled` is set to false in the repository source of the `jev` plugin, the plugin is installed "
    "by the normal procedure, and the owner receives a report of the change; this orchestrator does not change the "
    "plugin or its configuration. Without such a statement nothing changes."
)


def route_disabling_text(key):
    step = ROUTE_DISABLING_STEP_HARNESS if key == "harness" else ROUTE_DISABLING_STEP_PROJECT
    return ROUTE_DISABLING_RULE + " " + step


def route_reference(key):
    """Part 2: the skills refer to the plugin's configuration file and restate no criterion text."""
    board = BOARDS[key][0]
    return (f"The `jev` plugin chooses the route `easy`, `medium` or `hard` of a card with the criterion texts in "
            f"`routing.boards.{board}.routes` of its configuration file `config.json`; this skill does not restate "
            "them.")


def escalation_skill_text(key):
    """Part 4.6 in an orchestrator skill (behaviour of plugins/jev/routing.py handle_request_changes)."""
    board, _prefix, claude, glm = BOARDS[key]
    details = (f" The details are in {PROCEDURE}, section \"Reassignment to a Claude worker after change "
               "requests\"." if key == "harness" else "")
    return (
        f"After the fifth change request on a card that {_pair(glm)} implements, the `jev` plugin clears the card's "
        f"model override, reassigns the card to a Claude worker of the board, {_pair(claude)} (the worker named "
        "when the card was created; otherwise the two alternate), and writes that worker's name on the card's "
        "`Assigned worker EXACT` line. Accept that reassignment: do not reverse it, do not assign the card back to "
        "a GLM worker, and do not treat it as an assignee mismatch. The script "
        f"`{HOLD_SCRIPT}` does not hold a card that is assigned to a Claude worker. If the plugin could not rewrite "
        "the `Assigned worker EXACT` line and the Claude worker blocks the card because the line names the GLM "
        f"worker, change the name on that line to the Claude worker with `hermes kanban --board {board} edit "
        "<task id> --body=<body>` and unblock the card. The setting is `routing.max_glm_change_requests` in the "
        "same `config.json`." + details
    )


def escalation_reviewer_text(key):
    """Part 4.6 in a reviewer SOUL."""
    _board, _prefix, claude, glm = BOARDS[key]
    return (
        f"After the fifth change request on a card that {_pair(glm)} implements, the `jev` plugin clears the card's "
        f"model override, reassigns the card to a Claude worker of this board, {_pair(claude)}, and writes that "
        "worker's name on the card's `Assigned worker EXACT` line. The plugin does this right after your "
        "`kanban_request_changes` call, whose result does not show it. Do not reverse that reassignment and do not "
        "treat it as an assignee mismatch: the earlier runs of the GLM worker and the later runs of the Claude "
        "worker on the card are all runs of implementation profiles of this board. The peak-hours hold of the "
        "`jev` plugin, also its script `jev-peak-hold`, does not hold a card that is assigned to a Claude worker."
    )


def attach_example(board):
    """One complete kanban_attach call (parameters of the Hermes tool schema, tools/kanban_tools_schemas.py)."""
    return (f"`kanban_attach(task_id: \"t_0123abcd\", filename: \"focused-test-output.txt\", "
            f"content_base64: \"T0sK\", content_type: \"text/plain\", board: {board})`")


def attachment_procedure(board, profile):
    """Part 6.3: attaching a file to a card and the diff for the reviewer, for one GLM worker profile."""
    scratch = f"/Users/chanbla11mit/.hermes/profiles/{profile}/cache/scratch"
    return (
        f"Attach a file to the card with the terminal command `hermes kanban --board {board} attach <task id> "
        "<absolute path of the file> --name <file name>`; it reads the file itself and accepts files up to 25 MB. "
        "Use the `kanban_attach` tool only for a file of at most 1,000 bytes: pass the file's bytes as Base64 text "
        "on one line without line breaks in `content_base64` (print it with `base64 -i <absolute path of the "
        f"file>`; on macOS `base64` writes one line), for example {attach_example(board)}, which attaches a file "
        "that contains the text `OK` and a line break. Longer Base64 text is not reliable in a tool result, because "
        "the `jev` plugin can shorten a `terminal` or `execute_code` result of more than 2,000 characters. Never put "
        "a file path or a `file://` URL in `content_base64`, and never use `kanban_attach_url` for a local file: it "
        "accepts only `http` and `https` URLs and refuses loopback and private network addresses. To give the "
        f"reviewer the diff of a committed change, run `mkdir -p {scratch} && git -C <worktree path> diff "
        f"<baseline commit> HEAD > {scratch}/<task id>.diff` after the last commit, with the full 40-character "
        "commit of the card's `Baseline EXACT` line and with an empty `git -C <worktree path> status --porcelain`, "
        "attach that file with the command above, and name the commit that `git -C <worktree path> rev-parse HEAD` "
        "prints in the review request. Attach only the unchanged output of that command: never write, edit, shorten "
        "or combine a diff by hand."
    )


def _version(old, new):
    return (f"version: {new}\n", f"version: {old}\n")


GLM_LINE_END = "assign a GLM worker yourself only when the owner asks for it.\n"
REVIEWER_ANCHOR = "A model or provider override that is still set on the card at review is not a reason to reject the card.\n\n"
GLM_SOUL_ANCHOR = "rework after a change request runs on this profile's own model `glm-5.3`.\n\n"
CARD_CONTRACT_ANCHOR = ("a repository line that uses `EXACT` instead of `ONLY` fails the card contract check.\n\n")
# The three passages of the Jobcron and Cha PT skills that discouraged splitting (Jobcron lines 391,
# 400 and 506, Cha PT lines 384, 393 and 491 at the baseline): (new, old).
SPLIT_PASSAGES = (
    ("Use parent-child links for real dependencies. Keep independent slices parallel. " + SPLIT_RULE
     + " Do not split a card only to keep every lane busy.\n",
     "Use parent-child links for real dependencies. Keep independent slices parallel. Do not decompose merely to "
     "keep every lane busy.\n"),
    ("- Prefer a larger bounded cap over splitting work solely to evade the timer. Split into dependent cards when "
     "the stages have their own acceptance criteria or handoffs, including the parts that Task Construction "
     "requires to be split off a card that needs a design decision.\n",
     "- Prefer a larger bounded cap over splitting work solely to evade the timer. Split into dependent cards only "
     "when the stages have real independent acceptance criteria or handoffs.\n"),
    ("- Do not enable automatic decomposition until observed use shows manual decomposition is the bottleneck. "
     "This does not limit the manual split that Task Construction requires for a card that needs a design "
     "decision.\n",
     "- Do not enable automatic decomposition until observed use shows manual decomposition is the bottleneck.\n"),
)


def _paragraph_block(key):
    """Jobcron and Cha PT: three paragraphs after the jev worker selection paragraph."""
    return (GLM_LINE_END + "\n" + route_reference(key) + "\n\n" + escalation_skill_text(key) + "\n\n"
            + route_disabling_text(key) + "\n\n", GLM_LINE_END + "\n")


def _bullet_block(key):
    """Harness, jss-genr and anki: three bullets after the jev worker selection bullet."""
    return (GLM_LINE_END + "- " + route_reference(key) + "\n- " + escalation_skill_text(key) + "\n- "
            + route_disabling_text(key) + "\n", GLM_LINE_END)


def _card_contract_rule():
    return (CARD_CONTRACT_ANCHOR + SPLIT_RULE + "\n\n", CARD_CONTRACT_ANCHOR)


def _reviewer_edit(key):
    return ((REVIEWER_ANCHOR + escalation_reviewer_text(key) + "\n\n", REVIEWER_ANCHOR),)


def _glm_soul_edit(key, profile):
    board = BOARDS[key][0]
    return ((GLM_SOUL_ANCHOR + attachment_procedure(board, profile) + "\n\n", GLM_SOUL_ANCHOR),)


VERSIONS = {skill("harness"): ("0.6.7-harness.7", "0.6.7-harness.8"),
            skill("chapt"): ("0.6.7-chapt.8", "0.6.7-chapt.9"),
            skill("jobcron"): ("0.6.9-jobcron.9", "0.6.9-jobcron.10"),
            skill("jss"): ("0.6.7-jss.9", "0.6.7-jss.10"),
            skill("anki"): ("0.6.10-anki.5", "0.6.10-anki.6")}

# File -> ((new text, old text), ...). Each new text occurs exactly once.
ROUTING_POLICY_EDITS = {
    skill("harness"): (_version(*VERSIONS[skill("harness")]), _card_contract_rule(), _bullet_block("harness")),
    skill("jss"): (_version(*VERSIONS[skill("jss")]), _card_contract_rule(), _bullet_block("jss")),
    skill("anki"): (_version(*VERSIONS[skill("anki")]), _card_contract_rule(), _bullet_block("anki")),
    skill("jobcron"): (_version(*VERSIONS[skill("jobcron")]), _paragraph_block("jobcron"), *SPLIT_PASSAGES),
    skill("chapt"): (_version(*VERSIONS[skill("chapt")]), _paragraph_block("chapt"), *SPLIT_PASSAGES),
}
for _key in BOARDS:
    ROUTING_POLICY_EDITS[soul(f"{BOARDS[_key][1]}-reviewer")] = _reviewer_edit(_key)
for _key in GLM_SOUL_KEYS:
    for _profile in BOARDS[_key][3]:
        ROUTING_POLICY_EDITS[soul(_profile)] = _glm_soul_edit(_key, _profile)

# Bytes of each file at baseline 18b8372c31935888f9830638a0ce85fcb955b83c.
BASELINE_SHA256 = {
    skill("harness"): "d21098ead6d72e7e356cb9ef64006910383fdb104cb04bdabbba8341d7caf75b",
    skill("jss"): "62b93b484021d424b22c084020108969592239f0eac7b0597bb7e11867c4fddc",
    skill("anki"): "08c593b36e6187df98e6732562c76da36246f311a34a58c58095a56ffe480f9a",
    skill("jobcron"): "3d0a1ba41acb0ca6f2c45347d41c969db3f0ff4c94a874cd20fa57186f269292",
    skill("chapt"): "fec8f4f986a9459d9bda5efcef042556d9df336d334eacdb650b1d0a4ec0e000",
    soul("harness-reviewer"): "c5d6141fb030f272f46679e7f1bb25cb9772572b325f4729210172eb53ac5c10",
    soul("chapt-reviewer"): "d5f11875d61259282c9523b794860694044516f095ebcfa0a4b1223331a737b7",
    soul("jobcron-reviewer"): "14dc889f4f2fcb362d5430af9f7486fa08dbc4cc642af55159e9e7c667f95f40",
    soul("jss-reviewer"): "2424395e1a7538bb9c8d4188e5a8129d09777d32798cfba88eca3aaafeb574d4",
    soul("anki-reviewer"): "f588fa42904d76945c9c2271129db710184acee4bb095e6d432432c851002ca8",
    soul("harness-worker-glm-1"): "113b2b20eb00d59add0647252f5407c62d5c4c400ece57d02a9d6ddccda468b8",
    soul("harness-worker-glm-2"): "113b2b20eb00d59add0647252f5407c62d5c4c400ece57d02a9d6ddccda468b8",
    soul("chapt-worker-glm-1"): "50d07586b84e9605abecccdd21573280f1ae756e9c57e9add5bc919c7447b6a8",
    soul("chapt-worker-glm-2"): "9c2f69b362365fa6201d67d776687012cefc16390d597f35805bb9f3ca6929e8",
    soul("jss-worker-glm-1"): "eeaea1f6fcd1c9b7809012c485a6b2f49ca2c4504ad386590e07cdf85cadab7a",
    soul("jss-worker-glm-2"): "06bdd7bbc704216ffecc04cc26c00719f832cf73a56f9d5da40429da69a7afaf",
    soul("anki-worker-glm-1"): "6430d831c2b3c60353b377ff70935f97f5979e95fd9563645b03862c826d639d",
    soul("anki-worker-glm-2"): "b5cc7a58efbc58adfeec687c5a546ff200b68d317554f1dc7963364497959bc1",
}


def reverse_jev_routing_policy_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in ROUTING_POLICY_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


# The route criterion texts before card t_df87b851 (plugins/jev/config.json at ac1e667), and
# fragments that only those texts contain.
OLD_CRITERIA = (
    "Very easy to easy work: a small, well-specified change in one or two files, a documentation or wording edit, "
    "or a mechanical change with an exact test.",
    "A well-specified change across several files, or a change that needs reading surrounding code but no design "
    "decision.",
    "Everything else, including design decisions, debugging without a known cause, security, payment, migration "
    "or deployment work.",
)
OLD_FRAGMENTS = ("documentation or wording edit", "Very easy to easy work", "A well-specified change across",
                 "debugging without a known cause", "security, payment, migration or deployment work")
REPORT_HEADING = "## Report of Claude tokens saved, and the owner notification before a route is turned off\n"
ATTACHMENT_HEADING = "## Attachment and diff procedure of the GLM workers\n"


def policy_files():
    files = sorted((ROOT / "policies").rglob("*")) + sorted((ROOT / "skills/multi-agent-coding-orchestrator").rglob("*"))
    return [path for path in files if path.is_file()]


class RoutingPolicyText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {path: (ROOT / path).read_text() for path in ROUTING_POLICY_EDITS}
        cls.procedure = (ROOT / "procedures/jev-plugin.md").read_text()

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        self.assertEqual(set(BASELINE_SHA256), set(ROUTING_POLICY_EDITS))
        for path, want in BASELINE_SHA256.items():
            with self.subTest(path=path):
                original = reverse_jev_routing_policy_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_every_orchestrator_skill_states_the_rules_once(self):
        for key, (board, prefix, _claude, _glm) in BOARDS.items():
            text = self.text[skill(prefix)]
            with self.subTest(board=board):
                self.assertRegex(text, rf"(?m)^version: {re.escape(VERSIONS[skill(prefix)][1])}$")
                self.assertEqual(text.count(SPLIT_RULE), 1)
                self.assertEqual(text.count(escalation_skill_text(key)), 1)
                self.assertEqual(text.count(ROUTE_DISABLING_RULE), 1)
                self.assertEqual(text.count(route_disabling_text(key)), 1)
                # Only the Harness copy names the profile that turns off a route after the owner's statement.
                if key == "harness":
                    self.assertIn("`harness-orchestrator` (this profile) sets that route's `enabled` to false", text)
                else:
                    self.assertNotIn("harness-orchestrator", route_disabling_text(key))
                    self.assertNotIn("hermes-local-harness", route_disabling_text(key))
                self.assertEqual(text.count(route_reference(key)), 1)
                # The rules follow the jev worker selection text and precede the next section.
                selection = text.index(GLM_LINE_END)
                self.assertLess(selection, text.index(route_reference(key)))
                self.assertLess(text.index(route_reference(key)), text.index(escalation_skill_text(key)))
                self.assertLess(text.index(escalation_skill_text(key)), text.index(ROUTE_DISABLING_RULE))

    def test_jobcron_and_chapt_passages_no_longer_discourage_splitting(self):
        for prefix in ("jobcron", "chapt"):
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                for new, old in SPLIT_PASSAGES:
                    self.assertEqual(text.count(new), 1)
                    self.assertNotIn(old, text)
                self.assertNotIn("Do not decompose merely", text)
                self.assertNotIn("Split into dependent cards only when", text)
                # The intent is kept: no split only to keep workers busy or to avoid the runtime cap.
                self.assertIn("Do not split a card only to keep every lane busy.", text)
                self.assertIn("Prefer a larger bounded cap over splitting work solely to evade the timer.", text)
        for prefix in ("harness", "jss", "anki"):
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                for word in ("decompos", "lane busy", "evade the timer"):
                    self.assertNotIn(word, text)

    def test_every_reviewer_soul_states_the_reassignment(self):
        block = (ROOT / "policies/writing-rules.md").read_text()
        for key, (board, prefix, _claude, _glm) in BOARDS.items():
            text = self.text[soul(f"{prefix}-reviewer")]
            with self.subTest(board=board):
                self.assertEqual(text.count(escalation_reviewer_text(key)), 1)
                self.assertTrue(text.endswith(block))

    def test_every_glm_worker_soul_has_the_attachment_procedure(self):
        block = (ROOT / "policies/writing-rules.md").read_text()
        for key in GLM_SOUL_KEYS:
            board = BOARDS[key][0]
            for profile in BOARDS[key][3]:
                text = self.text[soul(profile)]
                with self.subTest(profile=profile):
                    self.assertEqual(text.count(attachment_procedure(board, profile)), 1)
                    self.assertEqual(text.count(attach_example(board)), 1)
                    self.assertIn(f"git -C <worktree path> diff <baseline commit> HEAD > "
                                  f"/Users/chanbla11mit/.hermes/profiles/{profile}/cache/scratch/<task id>.diff", text)
                    self.assertTrue(text.endswith(block))

    def test_example_call_matches_the_hermes_tool_schema(self):
        call = attach_example("harness")
        arguments = dict(re.findall(r"(\w+): (\"[^\"]*\"|[\w-]+)", call))
        self.assertEqual(set(arguments), {"task_id", "filename", "content_base64", "content_type", "board"})
        import base64
        self.assertEqual(base64.b64decode(arguments["content_base64"].strip('"'), validate=True), b"OK\n")

    def test_procedure_holds_the_text_for_the_jobcron_glm_workers(self):
        section = self.procedure.split(ATTACHMENT_HEADING, 1)[1].split("\n## ", 1)[0]
        for profile in BOARDS["jobcron"][3]:
            with self.subTest(profile=profile):
                self.assertEqual(section.count(attachment_procedure("jobcron", profile)), 1)
                self.assertFalse((ROOT / soul(profile)).exists())
        for key in GLM_SOUL_KEYS:
            for profile in BOARDS[key][3]:
                self.assertIn(f"`/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/{profile}/SOUL.md`",
                              section)

    def test_procedure_report_section_and_route_rule(self):
        self.assertEqual(self.procedure.count(REPORT_HEADING), 1)
        section = self.procedure.split(REPORT_HEADING, 1)[1].split("\n## ", 1)[0]
        for marker in ("--after <deployment time>", "disable this route: owner permission required",
                       "`--no-agent`", "\"Route disabling needs the owner's permission\"",
                       "/Users/chanbla11mit/hermes-local-harness/scripts/jev-route-notice"):
            self.assertIn(marker, section)
        # The Part 8.8 rule text of card t_df87b851 is stated once and referred to, not repeated.
        rule = "No profile, script, scheduled job or plugin code turns off a route"
        self.assertEqual(self.procedure.count(rule), 1)
        self.assertNotIn(rule, section)
        attachment = self.procedure.split(ATTACHMENT_HEADING, 1)[1].split("\n## ", 1)[0]
        for text in (route_disabling_text("harness"), route_disabling_text("jobcron"), section, attachment):
            self.assertNotIn("~/", text)
            self.assertNotIn("$HOME", text)

    def test_procedure_names_the_key_for_orchestrators_started_outside_the_gateway(self):
        section = self.procedure.split("## TypeSafe API key\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("/Users/chanbla11mit/hermes-local-harness/scripts/run-harness-orchestrator", section)
        self.assertIn("/Users/chanbla11mit/.hermes/profiles/<orchestrator profile>/.env", section)
        for name in ("jobcron", "chapt", "harness", "jss", "anki"):
            self.assertIn(f"`{name}-orchestrator`", section)
        self.assertIn("Only the owner adds the line.", section)

    def test_no_policy_file_restates_a_different_criterion(self):
        config = json.loads((ROOT / "plugins/jev/config.json").read_text())
        criteria = {route["criterion"] for board in config["routing"]["boards"].values() for route in board["routes"]}
        self.assertEqual(len(criteria), 3)
        files = policy_files()
        self.assertTrue(files)
        for path in files:
            text = path.read_text(errors="ignore")
            with self.subTest(path=str(path.relative_to(ROOT))):
                for fragment in OLD_FRAGMENTS + OLD_CRITERIA:
                    self.assertNotIn(fragment, text)
                # A text that starts like a current criterion is that criterion in full.
                for criterion in criteria:
                    start = criterion[:40]
                    for match in re.finditer(re.escape(start), text):
                        self.assertEqual(text[match.start():match.start() + len(criterion)], criterion)
        for key, (_board, prefix, _claude, _glm) in BOARDS.items():
            self.assertIn(route_reference(key), self.text[skill(prefix)])

    def test_jev_named_only_as_a_plugin(self):
        for path, text in self.text.items():
            with self.subTest(path=path):
                for match in re.finditer(r"\bjev\b", text):
                    following = text[match.end():match.end() + 10]
                    self.assertTrue(following.startswith("` plugin") or following.startswith("-peak-hold"),
                                    following)


if __name__ == "__main__":
    unittest.main()
