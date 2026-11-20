"""extra_body["card_reasoning_effort"] sets the --effort argument of the Claude CLI session.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI,
no network, no token file, a temporary HERMES_HOME).
"""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
KEY = "card_reasoning_effort"
SETTING = "HERMES_CLAUDE_SUBSCRIPTION_EFFORT"


class CardEffortTests(unittest.TestCase):
    setUp = provider.ClientTests.setUp
    request = provider.ClientTests.request
    followup = provider.ClientTests.followup

    def runtime_launches(self):
        return [argv for argv in self.launches if "--version" not in argv]

    def effort(self):
        argv = self.runtime_launches()[-1]
        return argv[argv.index("--effort") + 1]

    def ignored(self):
        return [entry for entry in self.c.audit if entry["stage"] == "card_effort_ignored"]

    def test_key_absent_keeps_the_setting_and_the_default(self):
        self.request()
        self.assertEqual(self.effort(), "medium")
        self.assertEqual(self.ignored(), [])
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)
        with patch.dict(os.environ, {SETTING: "high"}):
            self.request(extra_body={"response_format": {"type": "json_object"}})
        self.assertEqual(self.effort(), "high")
        self.assertEqual(self.ignored(), [])

    def test_each_allowed_value_reaches_the_effort_argument(self):
        for value in client.EFFORTS:
            with self.subTest(value=value):
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                # An invalid setting is not refused when the card value is the value used.
                with patch.dict(os.environ, {SETTING: "extreme"}):
                    self.request(extra_body={KEY: value})
                self.assertEqual(self.effort(), value)
                self.assertEqual(self.ignored(), [])

    def test_invalid_value_falls_back_to_the_setting_and_records_one_entry(self):
        for value in ("extreme", "HIGH", "", None, 5, ["high"], {"effort": "high"}):
            with self.subTest(value=value):
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                with patch.dict(os.environ, {SETTING: "xhigh"}):
                    self.request(extra_body={KEY: value})
                self.assertEqual(self.effort(), "xhigh")
                self.assertEqual(self.ignored(), [{"stage": "card_effort_ignored", "key": KEY,
                                                   "reason": "value not in EFFORTS"}])
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)
        self.request(extra_body={KEY: "extreme"})
        self.assertEqual(self.effort(), "medium")
        self.assertNotIn("extreme", json.dumps(self.c.audit))

    def test_invalid_value_and_invalid_setting_is_refused_before_effects(self):
        with patch.dict(os.environ, {SETTING: "extreme"}), \
                self.assertRaisesRegex(client.ProviderError, "invalid effort setting"):
            self.request(extra_body={KEY: "huge"})
        self.assertEqual(self.launches, [])

    def test_different_value_on_a_later_request_keeps_the_first(self):
        self.request(extra_body={KEY: "high"})
        response = self.followup("next", extra_body={KEY: "low"})
        self.assertEqual(response.choices[0].finish_reason, "stop")
        self.assertEqual(len(self.runtime_launches()), 1)
        self.assertEqual(self.effort(), "high")
        self.assertEqual(self.c._effort, "high")
        stages = [entry["stage"] for entry in self.c.audit]
        self.assertNotIn("session_reset", stages)
        self.assertEqual(self.ignored(), [{"stage": "card_effort_ignored", "key": KEY,
                                           "reason": "effort fixed at the first request",
                                           "effort": "high", "requested": "low"}])
        self.followup("again", extra_body={KEY: "high"})  # the same value records nothing
        self.assertEqual(len(self.ignored()), 1)

    def test_other_unknown_extra_body_keys_are_ignored(self):
        for body, effort in (({KEY: "high", "other": 1}, "high"), ({"reasoning_effort": "high"}, "medium"),
                             ({"effort": "high"}, "medium")):
            with self.subTest(body=body), patch.object(client, "_warned", set()), \
                    self.assertLogs(client.log.name, "WARNING"):
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                self.request(extra_body=body)
                self.assertEqual(self.effort(), effort)


if __name__ == "__main__":
    unittest.main()
