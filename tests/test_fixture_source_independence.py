#!/usr/bin/env python3
"""Fixtures store no copy of a tracked-source hash (t_1b8acbde).

A fixture records an observed skill or SOUL copy that equals its tracked source
as "tracked-source"; verify-state fixture mode resolves that value to the
sha256 of the tracked source at run time. So an edit to a tracked skill or SOUL
source needs no fixture edit, and a fixture that simulates a mismatch keeps an
explicit wrong hash and stays red.

The edits are made in a copy of the `git ls-files` list inside this test's own
TemporaryDirectory. verify-state runs only in fixture mode; nothing is written
outside the temporary directory, and no network is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "snapshots/sanitized-current-state.yaml"
MISMATCH_FIXTURES = ("tests/fixtures/deployed-skill-divergence.yaml", "tests/fixtures/chapt-profile-soul-drift.yaml")
APPENDED_LINE = "Plain text line appended by test_fixture_source_independence.\n"
TRACKED_SOURCE = "tracked-source"


def tracked_files():
    result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [name for name in result.stdout.decode().split("\0") if name]


def source_files(files):
    """Tracked skill sources under skills/ and policies/profile-skills/, and every
    tracked SOUL source named in the snapshot `profile_souls`."""
    snapshot = json.loads((ROOT / SNAPSHOT).read_text())
    souls = {entry["source"] for entry in snapshot["profile_souls"].values()}
    tracked = set(files)
    missing = souls - tracked
    assert not missing, f"SOUL sources named in the snapshot are not tracked: {sorted(missing)}"
    skills = [name for name in files if name.startswith(("skills/", "policies/profile-skills/"))]
    assert skills, "no tracked skill source found"
    return sorted(set(skills) | souls)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(root, fixture):
    """(exit code, FAIL lines) of `python3 scripts/verify-state --fixture <fixture>` in root."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "scripts/verify-state", "--fixture", str(fixture)], cwd=root,
                            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.returncode, [line for line in result.stdout.splitlines() if line.startswith("FAIL")], result.stdout


class RepositoryCopy:
    """A copy of the tracked file list (working-tree bytes) in its own TemporaryDirectory."""

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="fixture-source-independence-")
        self.root = Path(self.directory.name).resolve() / "repo"
        for name in tracked_files():
            source = ROOT / name
            if source.is_symlink():
                raise AssertionError(f"symlink in the tracked tree: {name}")
            if not source.is_file():
                raise AssertionError(f"tracked file missing from the worktree: {name}")
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            shutil.copymode(source, target)
        return self.root

    def __exit__(self, *args):
        self.directory.cleanup()


class FixtureSourceIndependence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tracked_files()
        cls.sources = source_files(cls.files)

    def test_source_edits_need_no_fixture_edit_and_mismatch_fixtures_stay_red(self):
        baseline = {}
        for fixture in MISMATCH_FIXTURES:
            code, fails, output = verify(ROOT, fixture)
            self.assertNotEqual(code, 0, output)
            self.assertTrue(fails, output)
            baseline[fixture] = fails
        with RepositoryCopy() as root:
            for name in self.sources:
                before = sha(root / name)
                with open(root / name, "a") as handle:
                    handle.write(APPENDED_LINE)
                self.assertNotEqual(sha(root / name), before, name)
            code, fails, output = verify(root, "tests/fixtures/clean.yaml")
            self.assertEqual((code, fails), (0, []), output)
            self.assertIn("OK: desired state matches observed state", output)
            for fixture in MISMATCH_FIXTURES:
                with self.subTest(fixture=fixture):
                    code, fails, output = verify(root, fixture)
                    self.assertNotEqual(code, 0, output)
                    self.assertEqual(fails, baseline[fixture], output)

    def test_no_fixture_contains_a_tracked_source_hash(self):
        hashes = {sha(ROOT / name): name for name in self.sources}
        fixtures = sorted(path for path in (ROOT / "tests/fixtures").rglob("*") if path.is_file())
        self.assertTrue(fixtures)
        for path in fixtures:
            text = path.read_text(errors="replace")
            with self.subTest(fixture=str(path.relative_to(ROOT))):
                found = sorted(name for digest, name in hashes.items() if digest in text)
                self.assertEqual(found, [], "fixture stores the sha256 of a tracked source")

    def test_placeholder_without_a_tracked_source_stays_red(self):
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        snapshot = json.loads((ROOT / SNAPSHOT).read_text())
        pinned = [(profile, path) for profile, files in snapshot["skill"]["profile_local_skill_overrides"].items()
                  for path, declared in files.items() if declared != TRACKED_SOURCE]
        self.assertTrue(pinned)  # worker-astra's learned overrides carry explicit hashes
        profile, path = pinned[0]
        cases = (
            (lambda d: d["profile_local_skill_overrides"][profile].__setitem__(path, TRACKED_SOURCE),
             f"FAIL: profile-local skill override drift: {profile}/{path}"),
            (lambda d: d["skill_files"]["minimal-implementation"]["harness-worker"].__setitem__(
                "references/undeclared.md", TRACKED_SOURCE),
             "FAIL: unexpected deployed skill file: minimal-implementation harness-worker/references/undeclared.md"),
            (lambda d: d["profile_soul_hashes"].__setitem__("unknown-profile", TRACKED_SOURCE),
             "FAIL: unexpected profile SOUL observation: unknown-profile"),
        )
        with tempfile.TemporaryDirectory(prefix="fixture-source-independence-obs-") as directory:
            observation = Path(directory) / "observation.yaml"
            for mutate, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic):
                    fixture = json.loads(json.dumps(clean))
                    mutate(fixture)
                    observation.write_text(json.dumps(fixture))
                    code, fails, output = verify(ROOT, observation)
                    self.assertEqual((code, fails), (1, [diagnostic]), output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
