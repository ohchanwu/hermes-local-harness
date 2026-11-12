#!/usr/bin/env python3
"""Policy sources of the jobcron, cha-pt and harness boards follow the jev plugin (t_b722c617).

Offline checks of tracked repository files only: no live /Users/chanbla11mit/.hermes
reads, board access, network or model calls.

The jev plugin (procedures/jev-plugin.md) can change the assignee of a new
implementation card from one of the board's two Claude workers to one of the
board's two GLM workers and set the card's model and provider, and it holds
cards of GLM workers on Monday to Friday from 15:00 to 19:00 Asia/Seoul. The
reviewer, orchestrator and GLM worker policy sources of the three boards state
this:
- each reviewer SOUL accepts the four implementation profiles of its board and
  does not reject a card because a model or provider override is still set;
- each orchestrator SOUL and orchestrator skill accepts the plugin's change of
  assignee, model and provider, keeps them in Card Setup step 2, and treats a
  `jev-peak-hold` hold at Card Setup step 5 as expected;
- each GLM worker SOUL of harness and cha-pt states the model override and the
  review request call with the board.

JEV_POLICY_EDITS lists the exact (new, old) text this card changed in each
file, so tests that pin older bytes of these files can reverse the change byte
for byte with reverse_jev_policy_edits(). This module imports no other test
module, so any test module can import it.
"""
import hashlib
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
HOLD_SCRIPT = "/Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold"

# Board -> (Kanban board name, profile prefix, Claude workers, GLM workers, reviewer)
BOARDS = {
    "harness": ("harness", "harness", ("harness-worker", "harness-worker-2"),
                ("harness-worker-glm-1", "harness-worker-glm-2"), "harness-reviewer"),
    "chapt": ("cha-pt", "chapt", ("chapt-worker", "chapt-worker-2"),
              ("chapt-worker-glm-1", "chapt-worker-glm-2"), "chapt-reviewer"),
    "jobcron": ("jobcron", "jobcron", ("jobcron-worker", "jobcron-worker-2"),
                ("jobcron-worker-glm-1", "jobcron-worker-glm-2"), "jobcron-reviewer"),
}


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def _names(profiles):
    return f"`{profiles[0]}` or `{profiles[1]}`"


def reviewer_paragraph(key):
    board, _prefix, claude, glm, _reviewer = BOARDS[key]
    return (
        f"The orchestrator creates implementation cards for {_names(claude)}; the `jev` plugin can change "
        f"the assignee to {_names(glm)} and set the card's model and provider when the card is created. "
        "Such a card is reviewed like any other implementation card. A model or provider override that is "
        "still set on the card at review is not a reason to reject the card.\n\n"
    )


def orchestrator_soul_sentences(key):
    _board, _prefix, claude, glm, _reviewer = BOARDS[key]
    return (
        f" The `jev` plugin can change the assignee of a new card from {_names(claude)} to {_names(glm)}, "
        "and set the card's model and provider, inside `kanban_create`; accept that change, because it is "
        "not an assignee mismatch. Assign a GLM worker yourself only when the owner asks for it."
    )


def worker_selection_text(key):
    board, _prefix, claude, glm, reviewer = BOARDS[key]
    return (
        f"The `jev` plugin can change the assignee of a card that `kanban_create` creates for {_names(claude)} "
        f"to `{glm[0]}` or `{glm[1]}`, alternating between the two, and set the card's `model` and `provider` "
        "(`glm-5.3-flash` or `glm-5.3` on provider `zai`) for work that the plugin classifies as `easy` or "
        f"`medium`. Accept that change: it is not an assignee mismatch, the reviewer stays `{reviewer}`, and "
        "same-card review, local integration and every prohibition are unchanged. The `kanban_create` result "
        f"does not show the change; `kanban_show(..., board: {board})` does. Still create every implementation "
        f"card for {_names(claude)}; assign a GLM worker yourself only when the owner asks for it."
    )


def setup_step_two(key):
    board = BOARDS[key][0]
    return (
        f"2. Read the stored card with `kanban_show(..., board: {board})` first. Then write the exact ID, "
        "worktree path, and branch into the body, and keep the stored assignee, model and provider and the "
        "stored `Assigned worker EXACT` line: the `jev` plugin may have changed them inside `kanban_create`, "
        "and the full body you write must not put the Claude worker name back.\n"
    )


OLD_STEP_TWO = "2. Read the new ID and write the exact ID, worktree path, and branch into the body.\n"


def setup_step_five(key):
    glm = BOARDS[key][3]
    return (
        "5. Unblock the card so it becomes `ready`. From Monday to Friday, 15:00 to 19:00 Asia/Seoul, the "
        f"`jev` plugin moves a card that is assigned to {_names(glm)} to `scheduled` instead of unblocking it, "
        "with a reason that starts with the marker `jev-peak-hold` (the tool result has `status` "
        f"`scheduled` and `held_until`), and the script `{HOLD_SCRIPT}` holds such a card the same way when it "
        "becomes `ready` by another path. This is expected: the card is released at 19:00 to `ready`, or to "
        "`todo` while a parent is open. It is not a blocker and not an owner question; do not unblock it "
        "again and do not reassign it to a Claude worker to start it earlier. The owner turns the hold off and "
        f"on and reads its state with `python3 {HOLD_SCRIPT} off`, `python3 {HOLD_SCRIPT} on` and "
        f"`python3 {HOLD_SCRIPT} status`.\n"
    )


OLD_STEP_FIVE = "5. Unblock the card so it becomes `ready`.\n"
TWO_WORKERS = ("Each project has two implementation workers. Assign implementation only to them, never to a "
               "foreign-project or legacy worker. Spread independent ready cards across the two workers; keep "
               "cards that touch the same files serialized or dependency-linked. Review revision stays on the "
               "same assignee.\n")


def _version(old, new):
    return (f"version: {new}\n", f"version: {old}\n")


def _glm_model_note(board, reviewer):
    return (
        f"Request same-card independent review only from `{reviewer}`, with "
        f"`kanban_request_review(..., reviewer: {reviewer}, board: {board})`. The `jev` plugin clears the "
        "card's model override when this profile requests review, so the reviewer runs on its own model; "
        "rework after a change request runs on this profile's own model `glm-5.3`."
    )


HARNESS_GLM_FIRST = (
    "You are a Hermes local harness implementation worker running GLM-5.3. ",
    "You are a Hermes local harness implementation worker. The profile model is `glm-5.3` on provider "
    "`zai`; a card that the `jev` plugin routed to this profile sets the model override `glm-5.3-flash` or "
    "`glm-5.3`, and the run uses that model. ",
)
HARNESS_GLM_REVIEW = "Request same-card independent review only from `harness-reviewer`."
HARNESS_GLM_LANE = ("Use this lane for large-context, repo-wide, long-horizon, broadly specified, multimodal, "
                    "or independent parallel Harness work. ")
HARNESS_GLM_LANE_NEW = ("Cards reach this profile when the `jev` plugin routes an `easy` or `medium` Harness "
                        "card to it, or when the owner asks for it. ")
HARNESS_GLM_EDITS = (
    (HARNESS_GLM_FIRST[1], HARNESS_GLM_FIRST[0]),
    (_glm_model_note("harness", "harness-reviewer"), HARNESS_GLM_REVIEW),
    (HARNESS_GLM_LANE_NEW, HARNESS_GLM_LANE),
)


def _chapt_glm_edits(number):
    return (
        (f"You are Cha PT GLM implementation worker {number}. The profile model is `glm-5.3` on provider "
         "`zai`; a card that the `jev` plugin routed to this profile sets the model override `glm-5.3-flash` "
         "or `glm-5.3`, and the run uses that model. ",
         f"You are Cha PT GLM Full implementation worker {number}. "),
        (_glm_model_note("cha-pt", "chapt-reviewer"),
         "Request same-card independent review only from `chapt-reviewer`."),
    )


# File -> ((new text, old text), ...). Each new text occurs exactly once.
JEV_POLICY_EDITS = {
    soul("harness-reviewer"): (
        ("implemented by one of the four Harness implementation profiles `harness-worker`, `harness-worker-2`, "
         "`harness-worker-glm-1` or `harness-worker-glm-2`, and pinned to repository "
         "`/Users/chanbla11mit/hermes-local-harness`.\n\n" + reviewer_paragraph("harness"),
         "implemented by `harness-worker` or `harness-worker-2`, and pinned to repository "
         "`/Users/chanbla11mit/hermes-local-harness`.\n\n"),
    ),
    soul("chapt-reviewer"): (
        ("implemented by one of the four Cha PT implementation profiles `chapt-worker`, `chapt-worker-2`, "
         "`chapt-worker-glm-1` or `chapt-worker-glm-2`, and pinned to",
         "implemented by `chapt-worker` or `chapt-worker-2`, and pinned to"),
        ("`/Users/chanbla11mit/projects/cha-webpt-website-sync`.\n\n" + reviewer_paragraph("chapt"),
         "`/Users/chanbla11mit/projects/cha-webpt-website-sync`.\n\n"),
    ),
    soul("jobcron-reviewer"): (
        ("Implementation reviews require work implemented by one of the four authorized Jobcron implementation "
         "profiles: `jobcron-worker`, `jobcron-worker-2`, `jobcron-worker-glm-1` or `jobcron-worker-glm-2`. "
         "Preserve and verify the actual implementer provenance; never relabel a run. Reject and block any "
         "project, workspace, or authorship boundary mismatch.\n\n" + reviewer_paragraph("jobcron"),
         "Implementation reviews require work implemented by an authorized Jobcron implementation profile, "
         "`jobcron-worker` or `jobcron-worker-2`. Preserve and verify the actual implementer provenance; never "
         "relabel a run. Reject and block any project, workspace, or authorship boundary mismatch.\n\n"),
    ),
    soul("harness-orchestrator"): (
        ("same-card independent review only to `harness-reviewer`." + orchestrator_soul_sentences("harness"),
         "same-card independent review only to `harness-reviewer`."),
    ),
    soul("chapt-orchestrator"): (
        ("same-card independent review only to `chapt-reviewer`." + orchestrator_soul_sentences("chapt"),
         "same-card independent review only to `chapt-reviewer`."),
    ),
    soul("jobcron-orchestrator"): (
        ("assign same-card review only to `jobcron-reviewer`." + orchestrator_soul_sentences("jobcron"),
         "assign same-card review only to `jobcron-reviewer`."),
    ),
    soul("harness-worker-glm-1"): HARNESS_GLM_EDITS,
    soul("harness-worker-glm-2"): HARNESS_GLM_EDITS,
    soul("chapt-worker-glm-1"): _chapt_glm_edits(1),
    soul("chapt-worker-glm-2"): _chapt_glm_edits(2),
    skill("harness"): (
        _version("0.6.7-harness.6", "0.6.7-harness.7"),
        ("- The implementation workers are `harness-worker` and `harness-worker-2`.\n- The `jev` plugin can "
         "move a new card to the GLM workers `harness-worker-glm-1` and `harness-worker-glm-2` (see Worker "
         "Selection).\n",
         "- The implementation workers are `harness-worker` and `harness-worker-2`.\n"),
        (setup_step_two("harness"), OLD_STEP_TWO),
        (setup_step_five("harness"), OLD_STEP_FIVE),
        ("same files serialized or dependency-linked.\n- " + worker_selection_text("harness") + "\n",
         "same files serialized or dependency-linked.\n"),
        ("5. Confirm the worker profile and reviewer match the fixed roster; a GLM worker that the `jev` "
         "plugin set is a match.\n",
         "5. Confirm the worker profile and reviewer match the fixed roster.\n"),
    ),
    skill("chapt"): (
        _version("0.6.7-chapt.7", "0.6.7-chapt.8"),
        (TWO_WORKERS + "\n" + worker_selection_text("chapt") + "\n", TWO_WORKERS),
        (setup_step_two("chapt"), OLD_STEP_TWO),
        (setup_step_five("chapt"), OLD_STEP_FIVE),
    ),
    skill("jobcron"): (
        _version("0.6.9-jobcron.8", "0.6.9-jobcron.9"),
        (TWO_WORKERS + "\n" + worker_selection_text("jobcron") + "\n", TWO_WORKERS),
        (setup_step_two("jobcron"), OLD_STEP_TWO),
        (setup_step_five("jobcron"), OLD_STEP_FIVE),
    ),
}

# Bytes of each file at baseline 7880b992ad4bba794add815bdd55e6087b66b1a4.
BASELINE_SHA256 = {
    soul("harness-reviewer"): "343b968109028bc504ec024af1dd5101ce4d498eb22a5cb9646149ec60f7c211",
    soul("chapt-reviewer"): "e2c132301890733d85f8a09a9c037eb09221c740319afaaae70769107244ebdb",
    soul("jobcron-reviewer"): "77a1edfc816e8e0bd38467a1b17b28413019332b0faf6c453440796fe7914327",
    soul("harness-orchestrator"): "fa5c430cf9db34da64b5fc5c7609f4c16a6e1b8dd1d153bc3057fbac7ec1a413",
    soul("chapt-orchestrator"): "06e68f4e75d99bfdf7a4e5eb1f1f4ffa8c3a4ccb51dd36da2a6423764730b9d6",
    soul("jobcron-orchestrator"): "1d670a9cd9a12ea3cc49837c84f95cac8e1fce463db3e47989b1ebb3c90565aa",
    soul("harness-worker-glm-1"): "a48d82a0f2093c0431aa10b16c5f12e5a2906909f0bd8a21381f0f291723765c",
    soul("harness-worker-glm-2"): "a48d82a0f2093c0431aa10b16c5f12e5a2906909f0bd8a21381f0f291723765c",
    soul("chapt-worker-glm-1"): "67e20559e42c20e141d1d2bc52703fbd9094be2b05e0db9c8c3e50193e30ddbb",
    soul("chapt-worker-glm-2"): "6587fb5ec47e6250eefe5e3eda0d64bff1069110dee7e0e26afa5a43c32fb0de",
    skill("harness"): "2104c3a371b9f3d7077c15c90ea9a6ea18d864d4f99786236b57e7f3990ac445",
    skill("chapt"): "fe6a85efe9c7ea587584f22e0077cb1f8ed11da8abe5cb6d3a8cadceac8fc085",
    skill("jobcron"): "8a754651b5e50fe468a0cb8eae2483a0f33940910156485aab4cf8c7fbf8caf2",
}
VERSIONS = {skill("harness"): "0.6.7-harness.7", skill("chapt"): "0.6.7-chapt.8",
            skill("jobcron"): "0.6.9-jobcron.9"}


def reverse_jev_policy_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in JEV_POLICY_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def implementation_profiles(text, prefix):
    """Every `<prefix>-worker...` profile name in text."""
    return set(re.findall(rf"`({prefix}-worker(?:-[a-z0-9]+)*)`", text))


class JevPolicySources(unittest.TestCase):
    def setUp(self):
        self.text = {path: (ROOT / path).read_text() for path in JEV_POLICY_EDITS}

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in BASELINE_SHA256.items():
            with self.subTest(path=path):
                original = reverse_jev_policy_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_each_reviewer_names_exactly_the_four_implementation_profiles_of_its_board(self):
        for key, (_board, prefix, claude, glm, reviewer) in BOARDS.items():
            text = self.text[soul(reviewer)]
            with self.subTest(reviewer=reviewer):
                self.assertEqual(implementation_profiles(text, prefix), set(claude) | set(glm))
                first = text.split("\n\n", 1)[0]
                self.assertEqual(implementation_profiles(first, prefix), set(claude) | set(glm))
                self.assertIn("A model or provider override that is still set on the card at review is not a "
                              "reason to reject the card.", text)

    def test_orchestrator_souls_accept_the_plugin_change_of_assignee(self):
        for key, (_board, prefix, claude, glm, _reviewer) in BOARDS.items():
            text = self.text[soul(f"{prefix}-orchestrator")]
            with self.subTest(key=key):
                self.assertEqual(text.count(orchestrator_soul_sentences(key)), 1)
                self.assertIn(f"Assign implementation only to {_names(claude)}", text)
                self.assertIn("Assign a GLM worker yourself only when the owner asks for it.", text)

    def test_orchestrator_skills_card_setup_and_worker_selection(self):
        for key, (board, prefix, _claude, glm, _reviewer) in BOARDS.items():
            text = self.text[skill(prefix)]
            with self.subTest(key=key):
                self.assertRegex(text, rf"(?m)^version: {re.escape(VERSIONS[skill(prefix)])}$")
                self.assertEqual(text.count(worker_selection_text(key)), 1)
                setup = text.split("## Card Setup\n", 1)[1].split("\n## ", 1)[0]
                steps = {line[:2]: line for line in setup.splitlines() if re.match(r"^[1-5]\. ", line)}
                self.assertEqual(steps["2."] + "\n", setup_step_two(key))
                self.assertEqual(steps["5."] + "\n", setup_step_five(key))
                self.assertNotIn(OLD_STEP_TWO, text)
                for command in ("off", "on", "status"):
                    self.assertIn(f"`python3 {HOLD_SCRIPT} {command}`", steps["5."])
                self.assertIn("It is not a blocker and not an owner question", steps["5."])
                self.assertNotIn("~/", steps["5."] + steps["2."])
                self.assertNotIn("$HOME", steps["5."] + steps["2."])
                for call in re.findall(r"kanban_[a-z_]+\(([^)]*)\)", worker_selection_text(key) + steps["2."]):
                    self.assertIn(f"board: {board}", call)
                # Same-card review by the board reviewer is unchanged.
                self.assertIn(f"`{BOARDS[key][4]}`", worker_selection_text(key))

    def test_glm_worker_souls_state_the_model_override_and_the_review_call(self):
        for key in ("harness", "chapt"):
            board, prefix, _claude, glm, reviewer = BOARDS[key]
            for profile in glm:
                text = self.text[soul(profile)]
                with self.subTest(profile=profile):
                    self.assertIn("`glm-5.3-flash`", text)
                    self.assertIn("`glm-5.3`", text)
                    self.assertEqual(text.count(f"`kanban_request_review(..., reviewer: {reviewer}, board: {board})`"),
                                     1)
                    self.assertNotRegex(text.lower(), r"retire")
                    self.assertNotIn("GLM Full", text)
                    self.assertNotIn("multimodal", text)

    def test_jev_named_only_as_a_plugin(self):
        for path, text in self.text.items():
            with self.subTest(path=path):
                for match in re.finditer(r"\bjev\b", text):
                    following = text[match.end():match.end() + 10]
                    self.assertTrue(following.startswith("` plugin") or following.startswith("-peak-hold"),
                                    following)


if __name__ == "__main__":
    unittest.main()
