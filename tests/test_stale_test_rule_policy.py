#!/usr/bin/env python3
"""Offline checks for the second SOUL policy file of card t_46b5e63e.

scripts/verify-state requires every SOUL in PROFILE_SOUL_PATHS to contain the whole
content of policies/stale-test-rule.md as one exact byte substring, tracked and live.
The cases below remove the block from one SOUL and require the verifier to fail.

reverse_stale_test_rule_edits() lets tests that compare a file with an earlier
reviewed version reverse this card's change: for a file that this card changed, when
the given bytes are the bytes of that file after this card, it returns the bytes of
the file at this card's baseline commit; it reverses the later edits of card t_f4ce916d
first. This module imports only jss_download_install_edits and
test_third_glm_worker_policy at load time, which import no other test module, so any test
module can import it.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jss_download_install_edits import reverse_download_install_edits
from test_third_glm_worker_policy import reverse_third_glm_worker_edits

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "d338ca675793238535ade9ef2a02c83488353e67"
POLICY = "policies/stale-test-rule.md"
POLICY_SHA256 = "3c72c5cb24817ddbf0df9f93608cd0036bb6604ed9750c4cdf3b98d80f3b57e7"
# SHA-256 of each file that card t_46b5e63e changed, after the card.
AFTER_SHA256 = {
    "policies/overgating-review.md":
        "04cd3aa7c76b93ae0b90576b1e566314f288c9ab679545e59f329606ef625c9b",
    "policies/profile-skills/anki-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md":
        "c4902aa7eca9f195c70c751820ba22d98dd97a3db48c97279b33829d7cea23b5",
    "policies/profile-skills/chapt-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md":
        "47ceec5013ca612d58056c803cd77dc4cceff601d9939beefd9c5d56bbf12f7c",
    "policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md":
        "497401eb5e37f34179d42858a6a92e48033c87ba470c67905465792bea226762",
    "policies/profile-skills/jobcron-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md":
        "0d91fcacc10be222f774ca19c9e0a0cae9f02714e54538e352e66689ea5f0f4e",
    "policies/profile-skills/jss-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md":
        "598f4329c570f6baafa3e6bc32b15b35ae3d7fa266cd57dbd7b83d031e6c47f6",
    "policies/profile-souls/anki-orchestrator/SOUL.md":
        "b388ff66e6936631c7bad14bbba773ab6746950245819a611525781d823a992b",
    "policies/profile-souls/anki-reviewer/SOUL.md":
        "5560226d767caa0e58de349f696881e8b6dced45729cd1d8fed657239657f61f",
    "policies/profile-souls/anki-worker-2/SOUL.md":
        "3d7ac899dd345bf5cf3a243973024803ca675fa0dd935662cd23ec8b67b47401",
    "policies/profile-souls/anki-worker-glm-1/SOUL.md":
        "c1556d8d51511ede6e5599ec69b9350a1efbb1fa6bfc78a68e7729f41b122265",
    "policies/profile-souls/anki-worker-glm-2/SOUL.md":
        "b76597caba74a1689d8ba615552495998ee8c259f2f93708e9514b52b93b00c6",
    "policies/profile-souls/anki-worker/SOUL.md":
        "3d7ac899dd345bf5cf3a243973024803ca675fa0dd935662cd23ec8b67b47401",
    "policies/profile-souls/chapt-orchestrator/SOUL.md":
        "08f9ebaff70d91c9979348119faa4342e08cf43c9d8de836d30a001d7006c6db",
    "policies/profile-souls/chapt-reviewer/SOUL.md":
        "5ba39e2ddc32f858a4e4827537327ad0372cecdcb4736eea2c0fa181e2c3a967",
    "policies/profile-souls/chapt-worker-2/SOUL.md":
        "9913bb383f4c91a6505bad100fca13d35d08f4ea62260f50aed87a50965e46ca",
    "policies/profile-souls/chapt-worker-glm-1/SOUL.md":
        "f145b70a7c8feac42fa30419d048c00ebfa8fec749dc42fbb03f5eda320fe784",
    "policies/profile-souls/chapt-worker-glm-2/SOUL.md":
        "b99843060015e8ac6ef8df344b97c989ebf5703cfcf9ab3860111d010c289930",
    "policies/profile-souls/chapt-worker/SOUL.md":
        "9913bb383f4c91a6505bad100fca13d35d08f4ea62260f50aed87a50965e46ca",
    "policies/profile-souls/harness-orchestrator/SOUL.md":
        "4c7e92808f33b81191f48e138deedd3b8b6706574cf9563ac39be178bde6b68b",
    "policies/profile-souls/harness-reviewer/SOUL.md":
        "080e9cc0f45bbbdad3e7513d3c5e6ec13d8f0302d542d67c20909f623920d413",
    "policies/profile-souls/harness-worker-2/SOUL.md":
        "b9064f45e823d05cf0bfc236c48b6c305f1199cb82233ca1589a68220a0ec1d0",
    "policies/profile-souls/harness-worker-glm-1/SOUL.md":
        "96c9e375b399d90a03af206a0afe7fa9d5b91b74a5ed205c9079f1fb376fdf8a",
    "policies/profile-souls/harness-worker-glm-2/SOUL.md":
        "9dd2941914724a648c375a80f5dffcc20642bd08493f2f96028714b67fb9a4c7",
    "policies/profile-souls/harness-worker/SOUL.md":
        "b9064f45e823d05cf0bfc236c48b6c305f1199cb82233ca1589a68220a0ec1d0",
    "policies/profile-souls/jobcron-orchestrator/SOUL.md":
        "bc3f7e7642abd48b9dc70c86649dc977fcc497dc96f9641fb2833538fcff62b2",
    "policies/profile-souls/jobcron-reviewer/SOUL.md":
        "075fb2d07a753cf53109b8c4a80ef095b660feb943ee87ba92a115f098c59dfd",
    "policies/profile-souls/jss-orchestrator/SOUL.md":
        "7bd7a0fc43941f32c030ede6c583250a38c8c89d1e03b03960215e5f86305984",
    "policies/profile-souls/jss-reviewer/SOUL.md":
        "0cdc81e4f3382611819fa5d8cc64b2982cea1589e2985e6a3ec5ccc58d07521f",
    "policies/profile-souls/jss-worker-2/SOUL.md":
        "917ed645845150d4d69a842eb059dd2ef8e53d15e04072282947ae45556637c2",
    "policies/profile-souls/jss-worker-glm-1/SOUL.md":
        "9e0a1e3fc1bf83f23fc512c3f3b7b84b8ca838cdd2cae2671aa0aa5d165f6d9d",
    "policies/profile-souls/jss-worker-glm-2/SOUL.md":
        "f1d8319c613637db122c0e90a9d0e45637caf297a8a19637d65bead0a6372061",
    "policies/profile-souls/jss-worker/SOUL.md":
        "917ed645845150d4d69a842eb059dd2ef8e53d15e04072282947ae45556637c2",
    "skills/harness-bug-report/SKILL.md":
        "c897b838fb1c9afaefdb4666adfaed7f54442371512aac3b7d5da696ebbfa4f2",
    "skills/minimal-implementation/SKILL.md":
        "00567282516c8893fd5f51a9db3c45e6248b471b4783f6ea46609d96284def7f",
    "skills/multi-agent-coding-orchestrator/SKILL.md":
        "00263911436aa5c1e7d596234c18e19ac6476b192f2ffc52581b158cd9eec9c3",
}


def baseline_bytes(relative_path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{relative_path}"],
                          stdout=subprocess.PIPE, check=True).stdout


def reverse_stale_test_rule_edits(relative_path, text):
    """Return the bytes of relative_path at BASELINE when text is that file after card
    t_46b5e63e, else text unchanged; text may be str or bytes. The later edits of card
    t_f4ce916d are reversed first."""
    text = reverse_third_glm_worker_edits(relative_path, text)
    want = AFTER_SHA256.get(relative_path)
    if want is None:
        return text
    data = text if isinstance(text, bytes) else text.encode()
    if hashlib.sha256(data).hexdigest() != want:
        return text
    old = baseline_bytes(relative_path)
    return old if isinstance(text, bytes) else old.decode()


class PolicyFile(unittest.TestCase):
    def test_policy_file_bytes(self):
        data = (ROOT / POLICY).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), POLICY_SHA256)

    def test_helper_returns_baseline_bytes_only_for_the_bytes_after_this_card(self):
        self.assertTrue(AFTER_SHA256)
        for relative_path, want in AFTER_SHA256.items():
            with self.subTest(path=relative_path):
                # The later download and install change (t_89838618) and the later third GLM worker
                # change (t_f4ce916d) are reversed first.
                current = reverse_download_install_edits(relative_path, (ROOT / relative_path).read_bytes())
                current = reverse_third_glm_worker_edits(relative_path, current)
                self.assertEqual(hashlib.sha256(current).hexdigest(), want)
                self.assertEqual(reverse_stale_test_rule_edits(relative_path, current), baseline_bytes(relative_path))
                self.assertEqual(reverse_stale_test_rule_edits(relative_path, current.decode()),
                                 baseline_bytes(relative_path).decode())
                other = current + b"\n"
                self.assertIs(reverse_stale_test_rule_edits(relative_path, other), other)


class VerifierCheck(unittest.TestCase):
    def test_tracked_soul_without_the_block_fails(self):
        # scripts/verify-state runs as its own process over a copy of the repository, so
        # that the case also runs under Python 3.9, whose pathlib passes an opener that the
        # read guard of incident_recovery_verify_fixture rejects.
        from test_verify_state_derived_expectations import TempTree
        block = (ROOT / POLICY).read_bytes()
        with TempTree() as root:
            soul = root / "policies/profile-souls/harness-worker/SOUL.md"
            data = soul.read_bytes()
            self.assertEqual(data.count(block), 1)
            soul.write_bytes(data.replace(block, b""))
            result = subprocess.run(
                [sys.executable, str(root / "scripts/verify-state"), "--fixture",
                 str(root / "tests/fixtures/clean.yaml")],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        fails = {line[len("FAIL: "):] for line in result.stdout.splitlines() if line.startswith("FAIL: ")}
        self.assertEqual((result.returncode, fails),
                         (1, {"policy block policies/stale-test-rule.md missing from tracked SOUL harness-worker"}),
                         result.stdout)

    def test_live_soul_without_the_block_fails(self):
        from test_verify_state_derived_expectations import tree_verifier
        verifier = tree_verifier(ROOT)
        block = (ROOT / POLICY).read_bytes()
        with tempfile.TemporaryDirectory(prefix="stale-test-rule-live-") as directory:
            paths = {}
            for profile, entry in verifier.PROFILE_SOUL_PATHS.items():
                live = Path(directory) / profile / "SOUL.md"
                live.parent.mkdir()
                data = (ROOT / entry["source"]).read_bytes()
                live.write_bytes(data.replace(block, b"") if profile == "harness-reviewer" else data)
                paths[profile] = {**entry, "live": str(live)}
            errors = []
            with patch.dict(verifier.PROFILE_SOUL_PATHS, copy.deepcopy(paths)), redirect_stdout(io.StringIO()):
                verifier.check_writing_rules(errors, live=True)
        self.assertEqual(errors, ["policy block policies/stale-test-rule.md missing from live SOUL harness-reviewer"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
