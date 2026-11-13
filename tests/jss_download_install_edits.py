#!/usr/bin/env python3
"""Reversal of the source edits of card t_89838618 (owner decision, 2026-11-13).

The owner removed the rule that a download needs explicit owner approval, and permitted
installs from a reputable source, in six jss-genr sources. Tests that compare one of those
sources with an earlier reviewed version call reverse_download_install_edits() first, before
the reversal functions of earlier cards. This module imports no test module, so any test
module can import it without a circular import.
"""

_DECISION = (
    "Owner decision, 2026-11-13: downloading a file that the work needs (for example icon SVG files, "
    "technology logos, reference images) needs no owner approval, and installing a package from a reputable "
    "source needs no owner approval. \"Reputable sources\" is the owner's wording; a reputable source is the "
    "official package registry of the language or platform, or the publisher's own distribution channel (for "
    "example the npm registry, PyPI, Homebrew). An install from any other source still needs explicit owner "
    "authorization. Dependencies are still never committed. A downloaded file keeps the licence notice that its "
    "source requires. The privacy gate and the jss-genr repository's own rules on where third-party material is "
    "stored are unchanged.")
_WORKER_DECISION = (
    "Owner decision, 2026-11-13: you may download a file that the card's work needs and install a package from "
    "a reputable source (the official package registry of the language or platform, or the publisher's own "
    "distribution channel); for an install from any other source, block with the exact need.")
_NOT_REPUTABLE = "installs from a source that is not reputable"
_WORKER = (
    (f"reference the main checkout's copies read-only and never commit dependencies. {_WORKER_DECISION} "
     "Commit locally",
     "reference the main checkout's copies read-only and never install, download, or commit dependencies. "
     "Commit locally"),
)

# File -> ((new text, old text), ...). Each new text occurs exactly once in the file after this card.
DOWNLOAD_INSTALL_EDITS = {
    "policies/profile-souls/jss-orchestrator/SOUL.md": (
        ("log in to a job site, write to the portfolio site repository, access credentials, change live profile, "
         "skill, board, or gateway state, or perform another external write without explicit owner authorization. "
         f"{_DECISION} Sole standing exception",
         "log in to a job site, install or download dependencies, write to the portfolio site repository, access "
         "credentials, change live profile, skill, board, or gateway state, or perform another external write "
         "without explicit owner authorization. Sole standing exception"),
    ),
    "policies/profile-skills/jss-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md": (
        ("version: 0.6.7-jss.12\n", "version: 0.6.7-jss.11\n"),
        (f"- Credentials, {_NOT_REPUTABLE}, live profile, skill, board, or gateway changes, and other external "
         f"writes require separate explicit owner authorization.\n- {_DECISION}\n",
         "- Credentials, installs or downloads (`npm install`, `make setup`, pip), live profile, skill, board, or "
         "gateway changes, and other external writes require separate explicit owner authorization.\n"),
        ("(for example `NODE_PATH`). Never commit dependencies; a worker may download a file that the card's work "
         "needs and may install a package from a reputable source as Hard Scope defines it; if a build needs an "
         "install from another source, block with the exact error.\n",
         "(for example `NODE_PATH`). Never install, download, or commit dependencies; if a build cannot run "
         "without that, block with the exact error.\n"),
        (f"job-site login, {_NOT_REPUTABLE}, live policy changes,",
         "job-site login, installs, live policy changes,"),
        (f"\n- {_NOT_REPUTABLE}\n", "\n- installs or downloads\n"),
    ),
    "policies/profile-souls/jss-worker/SOUL.md": _WORKER,
    "policies/profile-souls/jss-worker-2/SOUL.md": _WORKER,
    "policies/profile-souls/jss-worker-glm-1/SOUL.md": _WORKER,
    "policies/profile-souls/jss-worker-glm-2/SOUL.md": _WORKER,
}


def reverse_download_install_edits(relative_path, text):
    """Return text with the t_89838618 edits reversed; text may be str or bytes. The text of a
    path that is not one of the six changed sources is returned unchanged."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in DOWNLOAD_INSTALL_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text
