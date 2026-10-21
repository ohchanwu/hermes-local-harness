"""Helpers for tests that check that a rule is present in skill, SOUL or policy text.

A rule is present when its identifier and its obligation or prohibition words
appear together in one line (one Markdown paragraph or list item). The tests do
not compare whole sentences, so a change of wording that keeps the rule does not
fail them, and a removed or separated rule still fails them.
"""
import re


def line_with(text, *phrases):
    """The first line of text that contains every phrase, or None."""
    return next((line for line in text.splitlines() if all(phrase in line for phrase in phrases)), None)


def raw_section(text, heading):
    """The unflattened body of the `## heading` section of a Markdown text."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, heading
    return match.group(1)


def assert_rule(case, text, *phrases):
    """Fail the unittest case unless one line of text contains every phrase."""
    case.assertIsNotNone(line_with(text, *phrases), f"no line contains all of {phrases!r}")
