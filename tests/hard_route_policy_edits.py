#!/usr/bin/env python3
"""Reversal of the policy text edits of card t_e14a6d6a (specification
docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md, Part 5 step 2).

Cards t_3c7a581d and t_52be75ab changed the configuration of the `jev` plugin: `easy` and
`medium` cards go to `<prefix>-worker-glm-1` and `<prefix>-worker-glm-2` in turn, `hard` cards
go to `<prefix>-worker-glm-3`, `very_hard` cards stay with the Claude worker, and the route
`hard` has `max_glm_change_requests` 3 while the general value stays 5. Card t_e14a6d6a
changed the existing sentences of twelve policy files that named three routes and the fifth
change request:
- the five orchestrator skills: the worker selection sentence (item a.1), the list of routes
  (item a.2), the change request limit (item a.3), the removed sentence that named the
  setting `routing.max_glm_change_requests` (item a.4), the route disabling list (item a.5),
  and the version line (item b);
- the five reviewer SOUL files: the change request limit (item a.3);
- the SOUL files of `harness-worker-glm-3` and `jss-worker-glm-3`: the route of the cards
  that reach the profile (item a.6).
The card also corrected one reference in the exception line of the jss-reviewer SOUL file
(item a.7): the paragraph directly above that line does not name the overgating checklist.

HARD_ROUTE_POLICY_EDITS lists the exact (new text, old text) pairs of each file, in the order
in which the card applied them. reverse_hard_route_policy_edits() reverses them byte for byte.
jss_harness_repository_edits.reverse_harness_repository_edits calls it first, so every test
that recovers the bytes of an earlier commit reverses this card's edits before the edits of
the earlier cards. The later edits of card t_d3bb0983 (orchestrator_opus_5_5_edits) are
reversed first. This module imports only orchestrator_opus_5_5_edits, which imports no other
test module, so any test module can import it without a circular import.
"""
from orchestrator_opus_5_5_edits import reverse_opus_5_5_orchestrator_edits

BASELINE = "a0761ff0fb29cf3c2cbc7f27b79d5cab86278448"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PREFIXES = ("harness", "jobcron", "chapt", "jss", "anki")
# Skill version at BASELINE -> skill version after this card.
VERSIONS = {
    "harness": ("0.6.7-harness.11", "0.6.7-harness.12"),
    "jobcron": ("0.6.9-jobcron.13", "0.6.9-jobcron.14"),
    "chapt": ("0.6.7-chapt.12", "0.6.7-chapt.13"),
    "jss": ("0.6.7-jss.15", "0.6.7-jss.16"),
    "anki": ("0.6.10-anki.9", "0.6.10-anki.10"),
}


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def _glm(prefix, number):
    return f"`{prefix}-worker-glm-{number}`"


def worker_selection(prefix):
    """Item a.1: (new text, old text)."""
    return (
        f"to {_glm(prefix, 1)} or {_glm(prefix, 2)}, taking the two in turn, for work that the plugin classifies as "
        f"`easy` or `medium`, or to {_glm(prefix, 3)} for work that it classifies as `hard`, and set the card's "
        "`model` and `provider` (`glm-5.3-flash` or `glm-5.3` on provider `zai`).",
        f"to {_glm(prefix, 1)}, {_glm(prefix, 2)} or {_glm(prefix, 3)}, taking the three in turn, and set the card's "
        "`model` and `provider` (`glm-5.3-flash` or `glm-5.3` on provider `zai`) for work that the plugin "
        "classifies as `easy` or `medium`.",
    )


# Item a.2.
ROUTES = ("chooses the route `easy`, `medium`, `hard` or `very_hard` of a card",
          "chooses the route `easy`, `medium` or `hard` of a card")


def change_request_limit(prefix):
    """Item a.3: (new text, old text); the rest of the sentence is unchanged."""
    return (
        f"On a card that {_glm(prefix, 1)}, {_glm(prefix, 2)} or {_glm(prefix, 3)} implements, after the third change "
        "request when the `jev` plugin routed the card as `hard`, and after the fifth change request on any other "
        "card,",
        f"After the fifth change request on a card that {_glm(prefix, 1)}, {_glm(prefix, 2)} or {_glm(prefix, 3)} "
        "implements,",
    )


# Item a.4: the removed sentence, with its leading space.
REMOVED_SETTING_SENTENCE = " The setting is `routing.max_glm_change_requests` in the same `config.json`."


def removed_setting_sentence(prefix):
    """Item a.4: (new text, old text). The new text is the end of the sentence before the
    removed one and the text that follows the removed one, so that it occurs once."""
    following = " The details" if prefix == "harness" else "\n"
    before = "--body=<body>` and unblock the card."
    return (before + following, before + REMOVED_SETTING_SENTENCE + following)


# Item a.5.
ROUTE_DISABLING = ("or a board's `glm_workers` or `glm_max_workers` emptied)", "or a board's `glm_workers` emptied)")

# Item a.6.
WORKER_ROUTES = {
    "harness-worker-glm-3": ("routes a `hard` Harness card to it",
                             "routes an `easy` or `medium` Harness card to it"),
    "jss-worker-glm-3": ("routes a `hard` jss-genr card to it",
                         "routes an `easy` or `medium` jss-genr card to it"),
}

# Item a.7, in the exception line of the jss-reviewer SOUL file.
CHECKLIST_REFERENCE = (
    "The overgating checklist of the Harness repository that an earlier paragraph of this file names stays",
    "The overgating checklist of the Harness repository that the paragraph above names stays",
)


def _skill_edits(prefix):
    old, new = VERSIONS[prefix]
    return ((f"version: {new}\n", f"version: {old}\n"), worker_selection(prefix), ROUTES,
            change_request_limit(prefix), removed_setting_sentence(prefix), ROUTE_DISABLING)


# File -> ((new text, old text), ...), in the order in which the card applied them. Each new
# text occurs exactly once in the file after this card and not at all at BASELINE.
HARD_ROUTE_POLICY_EDITS = {}
for _prefix in PREFIXES:
    HARD_ROUTE_POLICY_EDITS[skill(_prefix)] = _skill_edits(_prefix)
for _prefix in PREFIXES:
    HARD_ROUTE_POLICY_EDITS[soul(f"{_prefix}-reviewer")] = (change_request_limit(_prefix),)
HARD_ROUTE_POLICY_EDITS[soul("jss-reviewer")] += (CHECKLIST_REFERENCE,)
for _profile, _edit in WORKER_ROUTES.items():
    HARD_ROUTE_POLICY_EDITS[soul(_profile)] = (_edit,)

# SHA-256 of each file at BASELINE (git show BASELINE:<path>).
BASELINE_SHA256 = {
    skill("harness"): "623f596d8fa9df94790f40ae0029caf78cd552a4d071ac48721f03cf1d493bda",
    skill("jobcron"): "e8734eecad69db2cba1da5568ab09457a8d1186a15c1d57917cbccb2052e5256",
    skill("chapt"): "9b7e16c17ab179e6374fc773fd504c40a124cf76b07e56a39dd5c43645e5d138",
    skill("jss"): "1e31cb83660de46128b534afa59bbf8a0d0f6fb671fccc83a1d6df66b0a364d7",
    skill("anki"): "1a0ad2da331956dd4a195b3b5085c35d6bbd133a28765a0b17b53cc43f32ad82",
    soul("harness-reviewer"): "ebaf6c00608be327f9deb8b168f103375e7b423ce2b60201320ea36703d9236d",
    soul("jobcron-reviewer"): "c2eb0cdabe3706807b8e329f8127cb23a8695b0b44156b5adb90b52b27ea869f",
    soul("chapt-reviewer"): "3060518f8a5f8eeac5d4952f943ee2a2dc6b1bbfde56752aeb26a257112e4571",
    soul("jss-reviewer"): "c3d51ac7b5de228fa7712aa082e10397b73b9e2e0373d712959f92765d5076a8",
    soul("anki-reviewer"): "7d9eafff2d91f0c071e8074d0fd8f0d2846c5c5ac8606e091ed6094ef10498f2",
    soul("harness-worker-glm-3"): "51dd9a805dc20ff399f2cc1adcd84cfa9fae870b2f50a2ddf95151ee0836821e",
    soul("jss-worker-glm-3"): "ebc9a246fcf02d2c425d412ab5905d6add57e805f96a116399dcf1d84b54650b",
}


def reverse_hard_route_policy_edits(relative_path, text):
    """Return text with the t_e14a6d6a edits reversed; text may be str or bytes. A path that
    the card did not change, and a text that contains none of the new texts, is returned as
    the same object, so a caller may apply it to a text that another caller already reversed.
    A text that contains some of the new texts but not each of them exactly once raises
    AssertionError. The later edits of card t_d3bb0983 are reversed first."""
    text = reverse_opus_5_5_orchestrator_edits(relative_path, text)
    edits = HARD_ROUTE_POLICY_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    counts = [value.count(new) for new, _old in edits]
    if not any(counts):
        return text
    if counts != [1] * len(edits):
        raise AssertionError(f"{relative_path}: expected one occurrence of each new text, found {counts}")
    for new, old in reversed(edits):
        value = value.replace(new, old, 1)
    return value.encode() if as_bytes else value


def apply_hard_route_policy_edits(relative_path, text):
    """Return text (str, the file at BASELINE) with the t_e14a6d6a edits applied."""
    for new, old in HARD_ROUTE_POLICY_EDITS.get(relative_path, ()):
        if text.count(old) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text
