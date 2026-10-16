"""Frozen oracles; no Hermes/Claude imports or account calls."""
import json
import os
from pathlib import Path
import socket
import sys
import unittest

import probe

ROOT = Path(__file__).resolve().parent
FIXTURE = json.loads((ROOT / "fixtures.json").read_text())
ALLOWED_READS = {
    ROOT / "test_probe.py",
    ROOT / "probe.py",
    ROOT / "fake_runtime.py",
    ROOT / "fixtures.json",
    ROOT.parents[1] / "private/feasibility/main-helpers.py.txt",
    ROOT.parents[1] / "private/feasibility/get-2.txt",
}
ACTIVE = False
ATTEMPTS = []
OWNED_HOMES = set()


def audit(event, args):
    if not ACTIVE:
        return
    if event.startswith("socket.") or event in {"http.client.connect", "urllib.Request"}:
        ATTEMPTS.append(event)
        raise AssertionError("Network denied")
    if event == "open":
        path = args[0]
        if isinstance(path, (str, bytes)):
            resolved = Path(os.fsdecode(path)).resolve()
            stdlib_source = resolved.is_relative_to(Path(sys.base_prefix).resolve()) and resolved.suffix == ".py"
            owned_directory = resolved in OWNED_HOMES and resolved.is_dir()
            if resolved not in ALLOWED_READS and not stdlib_source and not owned_directory:
                ATTEMPTS.append("forbidden_file_read")
                raise AssertionError("Non-allowlisted file access denied")
    if event == "subprocess.Popen":
        executable, argv, cwd, env = args
        assert executable == str(Path(sys.executable).resolve())
        assert argv[:3] == [executable, "-I", "-S"]
        assert Path(argv[3]) == ROOT / "fake_runtime.py"
        assert set(env) == {"HOME", "PATH", "LANG", "LC_ALL"}
        assert Path(env["HOME"]).is_relative_to(ROOT.parents[1] / "private/feasibility")
        OWNED_HOMES.add(Path(env["HOME"]).resolve())


sys.addaudithook(audit)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        global ACTIVE
        ATTEMPTS.clear()
        ACTIVE = True

    def tearDown(self):
        global ACTIVE
        ACTIVE = False

    def test_successful_profile_avoids_http_constructor(self):
        routes = probe.constructor_routes()
        self.assertEqual(routes, {"main": ["profile"], "auxiliary": ["profile"]})
        self.assertEqual(ATTEMPTS, [])
        print("SOURCE positive:", routes)

    def test_raising_profile_exposes_main_http_fallback(self):
        routes = probe.constructor_routes(factory_raises=True)
        self.assertEqual(routes, {"main": ["profile", "FORBIDDEN_HTTP_CONSTRUCTOR"],
                                  "auxiliary": ["profile"]})
        self.assertEqual(ATTEMPTS, [])
        print("SOURCE negative (unsafe route caught, not sent):", routes)

    def test_inert_structured_request_and_result_reaped(self):
        result = probe.exchange()
        self.assertTrue(result["reaped"])
        self.assertTrue(result["group_absent"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], [FIXTURE["request"], {
            "accepted_result": FIXTURE["result"],
            "environment_keys": ["HOME", "LANG", "LC_ALL", "PATH"],
        }])
        self.assertEqual(ATTEMPTS, [])
        print("INERT stdout/cleanup:", json.dumps(result, sort_keys=True))

    def test_inert_timeout_kills_owned_group_and_reaps(self):
        result = probe.exchange(timeout_mode=True)
        self.assertTrue(result["timed_out"])
        self.assertTrue(result["reaped"])
        self.assertTrue(result["group_absent"])
        self.assertLess(result["returncode"], 0)
        self.assertEqual(result["stdout"], [])
        self.assertEqual(ATTEMPTS, [])
        print("INERT timeout/cleanup:", json.dumps(result, sort_keys=True))

    def test_network_and_nonallowlisted_file_guard(self):
        with self.assertRaisesRegex(AssertionError, "Network denied"):
            socket.socket()
        # Synthetic nonexistent path, not a credential-store read.
        with self.assertRaisesRegex(AssertionError, "Non-allowlisted"):
            (ROOT / "forbidden-synthetic-file").read_text()
        self.assertEqual(ATTEMPTS, ["socket.__new__", "forbidden_file_read"])


def load_tests(loader, tests, pattern):
    assert tests.countTestCases() > 0, "Empty probe inventory"
    return tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
