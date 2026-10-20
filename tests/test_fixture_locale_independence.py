#!/usr/bin/env python3
"""Guarded fixture runs do not depend on the caller's locale environment variables.

With LANG and LC_* set, argparse (through gettext) would check translation files under
the Python installation. LocalReads removes those variables for the guarded run and
restores them afterwards; it does not allow the translation paths.
"""
import gettext
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import BoundaryError, LocalReads, ROOT, exercise, matches

LOCALE = {"LANGUAGE": "en_US:en", "LC_ALL": "en_US.UTF-8",
          "LC_MESSAGES": "en_US.UTF-8", "LANG": "en_US.UTF-8"}


class FixtureLocaleIndependence(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, LOCALE)
        environment.start()
        self.addCleanup(environment.stop)

    def test_clean_fixture_succeeds_with_locale_set_and_environment_restored(self):
        before = dict(os.environ)
        name, code, output = exercise(ROOT / "tests/fixtures/clean.yaml")
        self.assertTrue(matches(name, code, output), output)
        self.assertEqual(code, 0)
        self.assertEqual(dict(os.environ), before)

    def test_locale_variables_absent_inside_guard_and_restored_after_error(self):
        before = dict(os.environ)
        with self.assertRaises(ValueError):
            with LocalReads():
                for name in LOCALE:
                    self.assertNotIn(name, os.environ)
                raise ValueError("error raised inside the guard")
        self.assertEqual(dict(os.environ), before)
        for name, value in LOCALE.items():
            self.assertEqual(os.environ[name], value)

    def test_guard_still_refuses_python_installation_locale_directory(self):
        locale_directory = Path(sys.base_prefix) / "share" / "locale"
        with LocalReads():
            with self.assertRaises(BoundaryError):
                os.stat(locale_directory)
            with self.assertRaises(BoundaryError):
                os.path.exists(locale_directory / "en_US" / "LC_MESSAGES" / "argparse.mo")
            with self.assertRaises(BoundaryError):
                gettext.find("argparse", str(locale_directory), languages=["en_US"])


if __name__ == "__main__":
    unittest.main()
