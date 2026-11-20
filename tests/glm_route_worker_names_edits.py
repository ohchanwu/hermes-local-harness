#!/usr/bin/env python3
"""Record and reversal of the policy source edits of card t_18a2dc93.

Specification: docs/specs/261116-glm-worker-profiles-by-route-and-claude-fallback.md, section 1
and card R1 of section 7 (owner decision of 2026-11-16). On every board the GLM worker
`<prefix>-worker-glm-1` becomes `<prefix>-worker-glm-easy-1`, `-glm-2` becomes `-glm-medium-1` and
`-glm-3` becomes `-glm-hard-1`, and a copy of each one is the second worker of its route:
`-glm-easy-2`, `-glm-medium-2` and `-glm-hard-2`.

GLM_ROUTE_WORKER_NAME_EDITS lists the exact (old text, new text, number of occurrences) edits of
the card in each policy source that it changed in place, in the order in which the card applied
them. RENAMED_GLM_WORKER_SOULS maps the path of each GLM worker SOUL source that the card moved
with `git mv` to its path before the card; the edits of such a source are listed under its new
path. NEW_GLM_WORKER_SOULS maps the path of each SOUL source that the card added to the path of
the SOUL source that it copies.

reverse_glm_route_worker_name_edits() reverses the edits byte for byte.
test_jev_easy_medium_worker_split.reverse_easy_medium_split_edits calls it first, so every test
that recovers the bytes of an earlier commit reverses this card's edits before the edits of the
earlier cards. This module imports only the standard library and
test_glm_claude_fallback (card t_50fd66f2, which imports only the standard library), so any
test module can import it without a circular import.
"""
from test_glm_claude_fallback import reverse_glm_claude_fallback_edits
from test_ponytail_policy_text import reverse_ponytail_policy_text_edits
from test_reasoning_effort_skill_text import reverse_reasoning_effort_skill_text_edits

BASELINE = "b62e851cb7c0cdf0f23f6fb32f3a0698470ba618"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
# Profile prefix -> Kanban board name.
BOARDS = {"jobcron": "jobcron", "chapt": "cha-pt", "harness": "harness", "jss": "jss-genr", "anki": "anki"}
PREFIXES = tuple(BOARDS)
# The prefixes whose GLM workers have a SOUL source in this repository.
GLM_SOUL_PREFIXES = ("chapt", "harness", "jss", "anki")
# Old worker number -> (route, model of the route).
ROUTE_OF_NUMBER = {1: ("easy", "glm-5.3-flash"), 2: ("medium", "glm-5.3"), 3: ("hard", "glm-5.3")}
ROUTES = ("easy", "medium", "hard")
# The six names of a board, in the order of section 1 of the specification.
SUFFIXES = ("easy-1", "easy-2", "medium-1", "medium-2", "hard-1", "hard-2")
# Profile prefix -> (version at BASELINE, version after this card).
VERSIONS = {
    "jobcron": ("0.6.9-jobcron.17", "0.6.9-jobcron.18"),
    "chapt": ("0.6.7-chapt.16", "0.6.7-chapt.17"),
    "harness": ("0.6.7-harness.14", "0.6.7-harness.15"),
    "jss": ("0.6.7-jss.18", "0.6.7-jss.19"),
    "anki": ("0.6.10-anki.12", "0.6.10-anki.13"),
}


def old_name(prefix, number):
    return f"{prefix}-worker-glm-{number}"


def new_name(prefix, suffix):
    return f"{prefix}-worker-glm-{suffix}"


def renamed(prefix, number):
    """The new name of the old GLM worker `<prefix>-worker-glm-<number>`."""
    return new_name(prefix, f"{ROUTE_OF_NUMBER[number][0]}-1")


def board_glm_workers(prefix):
    """The six GLM worker names of a board, in the order of section 1."""
    return [new_name(prefix, suffix) for suffix in SUFFIXES]


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def quoted(name):
    return f"`{name}`"


def three_or(prefix):
    return f"{quoted(old_name(prefix, 1))}, {quoted(old_name(prefix, 2))} or {quoted(old_name(prefix, 3))}"


def three_and(prefix):
    return f"{quoted(old_name(prefix, 1))}, {quoted(old_name(prefix, 2))} and {quoted(old_name(prefix, 3))}"


def six_or(prefix):
    names = [quoted(name) for name in board_glm_workers(prefix)]
    return ", ".join(names[:-1]) + " or " + names[-1]


def six_and(prefix):
    names = [quoted(name) for name in board_glm_workers(prefix)]
    return ", ".join(names[:-1]) + " and " + names[-1]


def two_or(prefix, route):
    return f"{quoted(new_name(prefix, route + '-1'))} or {quoted(new_name(prefix, route + '-2'))}"


def old_split_sentence(prefix):
    """The route sentence of the `jev` bullet of each orchestrator skill at BASELINE (card t_cf518fd0)."""
    return (f"`easy` work goes to {quoted(old_name(prefix, 1))} (model `glm-5.3-flash`) and `medium` work to "
            f"{quoted(old_name(prefix, 2))} (model `glm-5.3`), and work that the plugin classifies as `hard` goes to "
            f"{quoted(old_name(prefix, 3))}.")


def new_split_sentence(prefix):
    return (f"`easy` work goes to {two_or(prefix, 'easy')} (model `glm-5.3-flash`), `medium` work to "
            f"{two_or(prefix, 'medium')} (model `glm-5.3`), and work that the plugin classifies as `hard` to "
            f"{two_or(prefix, 'hard')} (model `glm-5.3`); the plugin takes the two workers of each route in turn.")


# The part of the first line of every GLM worker SOUL source after the worker's label, at BASELINE.
OLD_SOUL_LINE_ONE = (". The profile model is `glm-5.3` on provider `zai`; a card that the `jev` plugin routed to this "
                     "profile sets the model override `glm-5.3-flash` or `glm-5.3`, and the run uses that model.")


def new_soul_line_one(route, model):
    return (f", a worker of the `jev` route `{route}` with model `{model}`. The profile model is `glm-5.3` on "
            f"provider `zai`; a card that the `jev` plugin routed to this profile sets the model override "
            f"`{model}`, and the run uses that model.")


def soul_label(prefix, number):
    """The text before OLD_SOUL_LINE_ONE that names the worker: the Harness sources have no number."""
    return "implementation worker" if prefix == "harness" else f"implementation worker {number}"


def new_soul_label(prefix, suffix):
    return "implementation worker" if prefix == "harness" else f"implementation worker {suffix}"


def _glm_worker_soul_edits(prefix, number):
    route, model = ROUTE_OF_NUMBER[number]
    edits = [(soul_label(prefix, number) + OLD_SOUL_LINE_ONE,
              new_soul_label(prefix, f"{route}-1") + new_soul_line_one(route, model), 1)]
    if prefix in ("harness", "jss") and number in (1, 2):
        # The Harness and jss-genr sources of the first two GLM workers name the routes of their cards.
        article = "an" if route == "easy" else "a"
        edits.append(("routes an `easy` or `medium` ", f"routes {article} `{route}` ", 1))
    # The profile's own scratch directory, twice in the attach paragraph.
    edits.append((old_name(prefix, number), renamed(prefix, number), 2))
    return tuple(edits)


def _edits():
    edits = {}
    for prefix in PREFIXES:
        edits[soul(f"{prefix}-reviewer")] = (
            ("one of the five ", "one of the eight ", 2),
            (three_or(prefix), six_or(prefix), 3),
        )
        edits[soul(f"{prefix}-reviewer-glm")] = (
            ("whose implementer is one of the three ", "whose implementer is one of the six ", 1),
            ("not one of those three GLM workers", "not one of those six GLM workers", 1),
            (three_or(prefix), six_or(prefix), 4),
        )
        edits[soul(f"{prefix}-orchestrator")] = ((three_or(prefix), six_or(prefix), 1),)
        old_version, new_version = VERSIONS[prefix]
        skill_edits = [
            (f"version: {old_version}\n", f"version: {new_version}\n", 1),
            (old_split_sentence(prefix), new_split_sentence(prefix), 1),
            (three_or(prefix), six_or(prefix), 3),
        ]
        if prefix in ("harness", "jss", "anki"):
            skill_edits.append((three_and(prefix), six_and(prefix), 1))
        edits[skill(prefix)] = tuple(skill_edits)
        if prefix in GLM_SOUL_PREFIXES:
            for number in ROUTE_OF_NUMBER:
                edits[soul(renamed(prefix, number))] = _glm_worker_soul_edits(prefix, number)
    return edits


# File (path after this card) -> ((old text, new text, number of occurrences), ...), in the order
# in which the card applied them. Each new text occurs exactly that number of times after the card.
GLM_ROUTE_WORKER_NAME_EDITS = _edits()
# Path after this card -> path at BASELINE, for the SOUL sources that the card moved with `git mv`.
RENAMED_GLM_WORKER_SOULS = {soul(renamed(prefix, number)): soul(old_name(prefix, number))
                            for prefix in GLM_SOUL_PREFIXES for number in ROUTE_OF_NUMBER}
# Path of each SOUL source that the card added -> path of the SOUL source that it copies.
NEW_GLM_WORKER_SOULS = {soul(new_name(prefix, f"{route}-2")): soul(new_name(prefix, f"{route}-1"))
                        for prefix in GLM_SOUL_PREFIXES for route in ROUTES}


def copy_text(prefix, route, source_text):
    """The text of the second worker's SOUL source of a route: the first worker's text with the
    profile name and the worker number replaced."""
    text = source_text.replace(new_name(prefix, f"{route}-1"), new_name(prefix, f"{route}-2"))
    if prefix != "harness":
        text = text.replace(f"implementation worker {route}-1,", f"implementation worker {route}-2,")
    return text


def apply_glm_route_worker_name_edits(relative_path, text):
    """Return the BASELINE text of a source with this card's edits applied (str). relative_path is
    the path after this card."""
    for old, new, count in GLM_ROUTE_WORKER_NAME_EDITS.get(relative_path, ()):
        found = text.count(old)
        if found != count:
            raise AssertionError(f"{relative_path}: expected {count} occurrences of {old[:60]!r}, found {found}")
        text = text.replace(old, new)
    return text


def reverse_glm_route_worker_name_edits(relative_path, text):
    """Return text with the t_18a2dc93 edits reversed; text may be str or bytes. relative_path is the
    path after this card (for a moved SOUL source, its new path). A path that the card did not change,
    and a text that contains none of the new texts, is returned as the same object, so a caller may
    apply it to a text that another caller already reversed. A text that contains some of the new
    texts but not each of them the recorded number of times raises AssertionError.

    The later SOUL sentence of card t_50fd66f2 is reversed first
    (test_glm_claude_fallback.reverse_glm_claude_fallback_edits)."""
    text = reverse_reasoning_effort_skill_text_edits(relative_path, text)
    text = reverse_ponytail_policy_text_edits(relative_path, text)
    text = reverse_glm_claude_fallback_edits(relative_path, text)
    edits = GLM_ROUTE_WORKER_NAME_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    counts = [value.count(new) for _old, new, _count in edits]
    if not any(counts):
        return text
    if counts != [count for _old, _new, count in edits]:
        raise AssertionError(f"{relative_path}: expected {[c for _o, _n, c in edits]} occurrences of the new "
                             f"texts, found {counts}")
    for old, new, _count in reversed(edits):
        value = value.replace(new, old)
    return value.encode() if as_bytes else value


def path_before_card(relative_path):
    """The path at BASELINE of a source that has relative_path after this card."""
    return RENAMED_GLM_WORKER_SOULS.get(relative_path, relative_path)


def path_after_card(relative_path):
    """The path after this card of a source that had relative_path at BASELINE."""
    for after, before in RENAMED_GLM_WORKER_SOULS.items():
        if before == relative_path:
            return after
    return relative_path


def text_before_card(root, relative_path, as_bytes=False):
    """The text at BASELINE of the source that had relative_path at BASELINE, recovered from the file
    under root (a pathlib.Path) after this card: read at its path after the card, with the card's edits
    reversed."""
    path = root / path_after_card(relative_path)
    data = path.read_bytes() if as_bytes else path.read_text()
    return reverse_glm_route_worker_name_edits(path_after_card(relative_path), data)


def source_text_of_copy(relative_path, text):
    """The text of the first worker's SOUL source of a route, recovered from the text of the second
    worker's SOUL source that the card added at relative_path (the reverse of copy_text); text may be
    str or bytes."""
    profile = relative_path.split("/")[-2]
    prefix, route = profile.split("-worker-glm-")[0], profile.split("-worker-glm-")[1].split("-")[0]
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    value = value.replace(new_name(prefix, f"{route}-2"), new_name(prefix, f"{route}-1"))
    if prefix != "harness":
        value = value.replace(f"implementation worker {route}-2,", f"implementation worker {route}-1,")
    return value.encode() if as_bytes else value


def before_card(relative_path, text):
    """Return (path at BASELINE, text at BASELINE) for a source that has relative_path and text after
    this card; text may be str or bytes. A SOUL source that the card moved gives its path before the
    move; a SOUL source that the card added gives the path and the text of the source that it copies.
    A path that the card did not change is returned with the text unchanged."""
    if relative_path in NEW_GLM_WORKER_SOULS:
        text = source_text_of_copy(relative_path, text)
        relative_path = NEW_GLM_WORKER_SOULS[relative_path]
    return path_before_card(relative_path), reverse_glm_route_worker_name_edits(relative_path, text)
