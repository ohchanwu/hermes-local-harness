"""The proposed upstream patch for silent receipts, exercised on a patched copy (card t_a9b14c3c).

docs/bugs/261018-telegram-unserved-update-receipt.patch changes
plugins/platforms/telegram/update_admission.py so the group-99 observer alone no longer
completes a claim. This test runs the same real-PTB dispatch as
tests/test_telegram_formatted_dm_drop.py, but against a patched COPY of the installed telegram
plugin package:

- an update that no core handler serves is NOT receipted, and it logs exactly one INFO line
  with its update id and field names only (no text, no values, no chat or user ids);
- plain and formatted DM text are still delivered exactly once, with one receipt each and no
  such log line.

Hermetic: the package is copied into the temporary HERMES_HOME from
tests/hermes_isolated_home.py (never into ~/.hermes or the worktree), and the patch is applied
there with ``git apply`` under GIT_CEILING_DIRECTORIES. The child puts the copy ahead of the
installed package on ``plugins.__path__`` and reports which files it imported. The installed
tree is only read. The test skips with a reason, and never passes, when the copy or the
patch cannot be prepared this way. The expectedFailure against the unpatched installed adapter
stays in tests/test_telegram_formatted_dm_drop.py.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_isolated_home as hih  # noqa: E402
import test_telegram_formatted_dm_drop as probe  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PATCH = REPO / "docs" / "bugs" / "261018-telegram-unserved-update-receipt.patch"
PACKAGE = Path("plugins") / "platforms" / "telegram"
UNSERVED_UPDATE_ID = len(probe._cases())  # the dice update is the last case
# A field-names list: identifiers, optionally followed by one parenthesised identifier list.
_NAMES = r"[a-z_]+(?:\([a-z_,]+\))?"
_LOG_LINE = re.compile(r"\[Telegram\] Update (\d+) matched no core handler; not receipted "
                       rf"\(fields: ({_NAMES}(?:, {_NAMES})*)\)")

_RESULTS: dict | None = None
_PATCHED_ROOT: str | None = None
_SKIP: str | None = None


def _patch_base_blob() -> str:
    match = re.search(r"^index ([0-9a-f]+)\.\.", PATCH.read_text(encoding="utf-8"), re.M)
    assert match, "patch has no git index line"
    return match.group(1)


def _prepare_patched_copy(iso: hih.IsolatedHome) -> Path:
    """Copy the installed telegram package into the isolated home and apply the patch."""
    git = shutil.which("git")
    if git is None:
        raise unittest.SkipTest("git is not available to apply the patch to a copy")
    source = iso.checkout_root / PACKAGE
    admission = source / "update_admission.py"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(iso.home), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CEILING_DIRECTORIES": str(iso.home)}
    blob = subprocess.run([git, "hash-object", "--no-filters", str(admission)], env=env,
                          capture_output=True, text=True, check=False, cwd=iso.home)
    if blob.returncode != 0 or not blob.stdout.strip().startswith(_patch_base_blob()):
        raise unittest.SkipTest("installed update_admission.py is not the patch's base blob "
                                f"{_patch_base_blob()}; cannot prepare the patched copy")
    root = iso.home / "patched"
    try:
        shutil.copytree(source, root / PACKAGE, ignore=shutil.ignore_patterns("__pycache__"))
    except OSError as exc:
        raise unittest.SkipTest(f"cannot copy the installed telegram package: {exc}") from exc
    # The base blob matches, so a refusal here is a broken patch: fail, do not skip.
    applied = subprocess.run([git, "apply", "--verbose", str(PATCH)], env=env, cwd=root,
                             capture_output=True, text=True, check=False)
    if applied.returncode != 0:
        raise AssertionError(f"patch does not apply to its base:\n{applied.stderr[-2000:]}")
    return root / "plugins"


def _run() -> None:
    global _RESULTS, _PATCHED_ROOT, _SKIP
    if _RESULTS is not None or _SKIP is not None:
        return
    try:
        with hih.isolated_hermes_home() as iso:
            try:
                patched = _prepare_patched_copy(iso)
            except unittest.SkipTest as exc:
                _SKIP = str(exc)
                return
            _PATCHED_ROOT = str(patched.resolve())
            _RESULTS = probe.run_probe(iso, patched=str(patched))
    except hih.IsolatedHomeError as exc:
        _SKIP = f"installed Hermes not available in an isolated home: {exc}"


class PatchedAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _run()
        if _SKIP:
            raise unittest.SkipTest(_SKIP)

    def result(self, name: str) -> dict:
        assert _RESULTS is not None
        r = _RESULTS["cases"][name]
        self.assertIsNone(r["error"], f"{name}: process_update raised {r['error']}")
        return r

    def test_dispatch_ran_against_the_patched_copy(self):
        assert _RESULTS is not None and _PATCHED_ROOT is not None
        self.assertEqual(len(_RESULTS["files"]), 2)
        for module, path in _RESULTS["files"].items():
            with self.subTest(module=module):
                self.assertTrue(str(Path(path).resolve()).startswith(_PATCHED_ROOT + "/"), path)

    def test_unserved_update_not_receipted_and_logged_once_by_field_names(self):
        r = self.result("unserved")
        self.assertEqual(r["deliveries"], 0)
        self.assertFalse(r["receipt"], "an unserved update must stay unreceipted")
        self.assertEqual(len(r["admission_logs"]), 1, r["admission_logs"])
        line = r["admission_logs"][0]
        match = _LOG_LINE.fullmatch(line)
        assert match is not None, line
        self.assertEqual(int(match.group(1)), UNSERVED_UPDATE_ID)
        # Exactly the synthetic update's shape; "dice" is the decisive observation.
        self.assertEqual(match.group(2), "message(chat,date,dice,from,message_id), update_id")
        # Names only: no value from the synthetic update appears (chat/user ids, name, emoji).
        for value in ("42", "88", "Human", "\U0001F3B2", "1800000000"):
            self.assertNotIn(value, line)

    def test_plain_and_formatted_dm_text_still_delivered_once_with_one_receipt(self):
        for size in (1000, 3900):
            plain = self.result(f"plain{size}")
            self.assertEqual(plain["text"], probe._body(size)[0].strip())
            for kind in ("plain", "pre", "code", "bold", "mix", "blockquote"):
                with self.subTest(size=size, entities=kind):
                    r = self.result(f"{kind}{size}")
                    self.assertEqual(r["deliveries"], 1)
                    self.assertEqual(r["text"], plain["text"])
                    self.assertTrue(r["receipt"])
                    self.assertEqual((r["held"], r["pending"]), (0, 0))
                    self.assertEqual(r["admission_logs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
