"""The error texts for a stop reason that is not accepted, and the cause and time in the closed-client error.

Hermetic: every runtime event is synthetic and built in this file; no CLI child process is started, no
network is used and no file is written. The plugin modules are loaded through the bare package of
test_claude_subscription_provider.py. The texts are compared character for character, because Hermes
chooses its reaction to a provider error from the words of the error text.
"""
import datetime
import importlib
from pathlib import Path
import re
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
compat = importlib.import_module("subscription_plugin.compat")
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
stream_events = importlib.import_module("subscription_plugin.stream_events")
MODEL = provider.MODEL
TOOL_NAME = client.PREFIX + "read_file"
MESSAGES = [{"role": "system", "content": "Synthetic system"}, {"role": "user", "content": "Synthetic question"}]
NO_DELTA = object()  # the message has no message_delta event
TIME = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}"
CLOSED = "client closed or cancelled; no retry/resume"
MARKER = "SYNTHETIC-EXCEPTION-MESSAGE-7f3c"  # appears only in the message of a raised exception


def event(kind, **fields):
    return {"type": "stream_event", "event": {"type": kind, **fields}}


def message_events(stop, calls, text="Synthetic text."):
    """One complete synthetic message: a text block, `calls` tool_use blocks, then message_stop.

    `stop` is the stop reason of its message_delta event; NO_DELTA leaves that event out.
    """
    events = [event("message_start", message={"id": "msg_synthetic", "model": MODEL, "usage": {}}),
              event("content_block_start", index=0, content_block={"type": "text", "text": ""}),
              event("content_block_delta", index=0, delta={"type": "text_delta", "text": text}),
              event("content_block_stop", index=0)]
    snapshot = [{"type": "text", "text": text}]
    for number in range(calls):
        index, call_id = number + 1, f"toolu_synthetic_{number}"
        events += [event("content_block_start", index=index,
                         content_block={"type": "tool_use", "id": call_id, "name": TOOL_NAME, "input": {}}),
                   event("content_block_delta", index=index,
                         delta={"type": "input_json_delta", "partial_json": '{"path": "/synthetic"}'}),
                   event("content_block_stop", index=index)]
        snapshot.append({"type": "tool_use", "id": call_id, "name": TOOL_NAME, "input": {"path": "/synthetic"}})
    if stop is not NO_DELTA:
        events.append(event("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2}))
    for block in snapshot:
        events.append({"type": "assistant", "message": {"id": "msg_synthetic", "model": MODEL, "content": [block]}})
    events.append(event("message_stop"))
    return events


def feed_message(stop, calls):
    message = stream_events.Message({MODEL})
    for obj in message_events(stop, calls):
        message.feed(obj)
    return message


def baseline_raises(stop, calls):
    """The condition under which the baseline rejected a message at message_stop."""
    return stop not in ("end_turn", "max_tokens", "tool_use") or bool(calls) != (stop == "tool_use")


class StopReasonTextTests(unittest.TestCase):
    def assert_text(self, stop, calls, expected):
        with self.assertRaises(client.ProviderError) as raised:
            feed_message(stop, calls)
        self.assertIs(type(raised.exception), client.ProviderError)
        self.assertEqual(str(raised.exception), expected)

    def test_row_a_no_stop_reason_received(self):
        self.assert_text(NO_DELTA, 0, "runtime message ended without a stop reason")
        self.assert_text(None, 0, "runtime message ended without a stop reason")
        self.assert_text(NO_DELTA, 1, "runtime message ended without a stop reason")

    def test_row_b_stop_reason_refusal(self):
        self.assert_text("refusal", 0, "runtime stop reason refusal")
        self.assert_text("refusal", 1, "runtime stop reason refusal")

    def test_row_c_other_stop_reason_with_the_value_rule_of_the_stream_audit(self):
        for stop, shown in (("pause_turn", "pause_turn"), ("stop_sequence", "stop_sequence"),
                            ("model_context_window_exceeded", "model_context_window_exceeded"),
                            ("a" * 40, "a" * 40), ("a" * 41, "<other>"), ("pause turn", "<other>"),
                            (7, "<other>"), ({"reason": "x"}, "<other>"), ("", "<other>")):
            with self.subTest(stop=stop):
                self.assert_text(stop, 0, "runtime stop reason not supported: " + shown)
                self.assertEqual(stream_audit.label(stop, 40), shown)
        self.assert_text("pause_turn", 2, "runtime stop reason not supported: pause_turn")

    def test_row_c_uses_the_one_shared_label_function(self):
        self.assertIs(stream_audit.label, stream_events.label)

    def test_row_d_end_turn_with_tool_calls(self):
        self.assert_text("end_turn", 1, "runtime stop reason end_turn inconsistent with 1 tool calls")
        self.assert_text("end_turn", 2, "runtime stop reason end_turn inconsistent with 2 tool calls")

    def test_row_e_max_tokens_with_tool_calls(self):
        self.assert_text("max_tokens", 1, "runtime message stopped at the output limit with 1 tool calls")
        self.assert_text("max_tokens", 2, "runtime message stopped at the output limit with 2 tool calls")

    def test_row_f_tool_use_without_a_tool_call(self):
        self.assert_text("tool_use", 0, "runtime stop reason tool_use without a tool call")

    def test_accepted_stop_reasons_do_not_raise(self):
        for stop, calls in (("max_tokens", 0), ("end_turn", 0), ("tool_use", 1), ("tool_use", 2)):
            with self.subTest(stop=stop, calls=calls):
                message = feed_message(stop, calls)
                self.assertTrue(message.done)
                self.assertEqual((message.stop, len(message.calls)), (stop, calls))

    def test_an_input_raises_exactly_when_it_raised_at_the_baseline(self):
        stops = (NO_DELTA, None, "refusal", "end_turn", "max_tokens", "tool_use", "pause_turn", "a" * 41, 7)
        for stop in stops:
            for calls in (0, 1, 2):
                with self.subTest(stop=stop, calls=calls):
                    expected = baseline_raises(None if stop is NO_DELTA else stop, calls)
                    try:
                        feed_message(stop, calls)
                    except client.ProviderError:
                        raised = True
                    else:
                        raised = False
                    self.assertEqual(raised, expected)

    def test_no_text_contains_the_words_that_change_the_hermes_reaction(self):
        texts = [stream_events.stop_error_text(stop, calls)
                 for stop in (None, "refusal", "pause_turn", "end_turn", "max_tokens", "tool_use") for calls in (0, 1, 2)
                 if baseline_raises(stop, calls)]
        self.assertEqual(len(texts), 14)  # 3 each for None, refusal and pause_turn; 2, 2 and 1 for the other three
        for text in texts:
            self.assertNotIn("max_tokens", text)
            self.assertNotIn("output token limit", text)
            self.assertNotIn("refusal or unsupported", text)


class SyntheticRuntime:
    """Stands in for the CLI runtime child of one request: returns the given events, then nothing."""

    def __init__(self, events):
        self.events = list(events)

    def send(self, text, check_active, idle=None):
        check_active()

    def read(self):
        return self.events.pop(0) if self.events else None

    def output_pending(self):
        return bool(self.events)

    def close(self):
        pass

    def dispose(self):
        pass


class FailingRuntime(SyntheticRuntime):
    """A runtime child whose close() fails, as when ending the previous CLI session fails."""

    def close(self):
        raise SyntheticFailure(MARKER)


class SyntheticFailure(Exception):
    pass


def init_event():
    return {"type": "system", "subtype": "init", "model": MODEL, "tools": [], "apiKeySource": "none",
            "claude_code_version": compat.version_text(max(compat.CLI_TESTED))}


def result_event():
    return {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "modelUsage": {}, "usage": {}}


class ClosedClientTextTests(unittest.TestCase):
    def new_client(self):
        c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(c.close)
        return c

    def open_stream(self, c, events):
        """A request on `c` whose runtime child is SyntheticRuntime(events); nothing is started or written."""
        c._scope = c._current_scope(None)
        c._model, c._tools, c._cli_version = MODEL, [], max(compat.CLI_TESTED)
        tail = c._history.accept(list(MESSAGES))
        c._runtime = SyntheticRuntime(events)
        c._busy.acquire()
        c._busy_owner = threading.get_ident()
        return client.Stream(c, c._drive(tail, 30))

    def refusals(self, c):
        """The error text and the log lines of one refused request at each refusal site (create, _check_active)."""
        out = []
        for refuse in (lambda: c.create(model=MODEL, messages=list(MESSAGES)), c._check_active):
            with self.assertLogs(client.log.name, "WARNING") as logs, self.assertRaises(client.ProviderError) as raised:
                refuse()
            self.assertIs(type(raised.exception), client.ProviderError)
            out.append((str(raised.exception), [record.getMessage() for record in logs.records]))
        return out

    def assert_closed_by(self, c, cause, detail):
        """Both refusal sites give the closed-client error with `cause` and log `cause` with `detail`; returns the time."""
        times = []
        for error, lines in self.refusals(c):
            match = re.fullmatch(re.escape(CLOSED + " (closed at ") + f"({TIME})" + re.escape(" by: " + cause + ")"), error)
            self.assertIsNotNone(match, error)
            at = match.group(1)
            line = f"claude-subscription: request refused; the client was closed at {at} by: {cause}"
            self.assertEqual(lines, [line if detail is None else line + ": " + detail])
            times.append(at)
        self.assertEqual(times[0], times[1])
        moment = datetime.datetime.fromisoformat(times[0])
        self.assertLess(abs((datetime.datetime.now().astimezone() - moment).total_seconds()), 120)
        return times[0]

    def test_close_called(self):
        c = self.new_client()
        c.close()
        self.assert_closed_by(c, "close() called", None)

    def test_cancel_called(self):
        c = self.new_client()
        c.cancel()
        self.assertTrue(c.is_closed())
        self.assert_closed_by(c, "cancel() called", None)

    def test_stream_closed_before_its_first_iteration(self):
        c = self.new_client()
        self.open_stream(c, []).close()
        self.assert_closed_by(c, "stream closed before it finished", None)

    def test_stream_closed_while_it_yields_keeps_the_stream_cause(self):
        # Closing the stream also ends the request generator with GeneratorExit, a second closing that is not recorded.
        c = self.new_client()
        stream = self.open_stream(c, [init_event(), *message_events("end_turn", 0), result_event()])
        self.assertEqual(next(stream).choices[0].delta.role, "assistant")
        stream.close()
        self.assert_closed_by(c, "stream closed before it finished", None)

    def test_request_failed_on_a_message_without_a_stop_reason(self):
        c = self.new_client()
        stream = self.open_stream(c, [init_event(), *message_events(NO_DELTA, 0)])
        failure = "runtime message ended without a stop reason"
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            next(stream)
        self.assertEqual(str(raised.exception), failure)
        self.assertTrue(c.is_closed())
        self.assert_closed_by(c, "request failed", failure)
        for error, lines in self.refusals(c):
            self.assertNotIn(failure, error)
            self.assertIn(failure, lines[0])

    def test_request_failed_detail_is_the_first_200_characters_of_the_error_text(self):
        c = self.new_client()
        stream = self.open_stream(c, [])
        c._runtime = None
        text = "synthetic provider failure " + "x" * 300
        with patch.object(c, "_start", side_effect=client.ProviderError(text)):
            with self.assertRaises(client.ProviderError) as raised:
                next(stream)
        self.assertEqual(str(raised.exception), text)
        self.assert_closed_by(c, "request failed", text[:200])
        for error, lines in self.refusals(c):
            self.assertNotIn(text[:200], error)

    def test_request_failed_with_the_error_that_protocol_error_builds(self):
        c = self.new_client()
        stream = self.open_stream(c, [])
        c._runtime = None
        with patch.object(c, "_start", side_effect=OSError(MARKER)):
            with self.assertRaises(client.ProviderError) as raised:
                next(stream)
        failure = "runtime startup, I/O or malformed protocol: OSError"
        self.assertEqual(str(raised.exception), failure)
        self.assert_closed_by(c, "request failed", failure)
        for error, lines in self.refusals(c):
            self.assertNotIn("OSError", error)
            self.assertNotIn(MARKER, error + "".join(lines))

    def test_request_ended_with_an_exception_other_than_provider_error(self):
        c = self.new_client()
        stream = self.open_stream(c, [])
        c._runtime = None
        with patch.object(c, "_start", side_effect=SyntheticFailure(MARKER)):
            with self.assertRaises(SyntheticFailure):
                next(stream)
        self.assert_closed_by(c, "request ended with an exception other than ProviderError", "SyntheticFailure")
        for error, lines in self.refusals(c):
            self.assertNotIn("SyntheticFailure", error)
            self.assertNotIn(MARKER, error + "".join(lines))

    def test_session_reset_failed(self):
        c = self.new_client()
        c._runtime = FailingRuntime([])
        with self.assertRaises(client.ProviderError) as raised:
            c._reset_session()
        self.assertEqual(str(raised.exception), "session reset failed (SyntheticFailure); client closed")
        c._runtime = None  # the remains were put back for close(); this runtime cannot be closed
        self.assert_closed_by(c, "session reset failed", "SyntheticFailure")
        for error, lines in self.refusals(c):
            self.assertNotIn("SyntheticFailure", error)
            self.assertNotIn(MARKER, error + "".join(lines))

    def test_a_second_closing_keeps_the_first_cause_detail_and_time(self):
        c = self.new_client()
        c.cancel()
        first, at = c._closed_by, self.assert_closed_by(c, "cancel() called", None)
        time.sleep(1.1)  # a replaced time would differ in the seconds
        c.close()
        c.cancel()
        c._cancel(client.CLOSED_BY_REQUEST_ERROR, "synthetic later failure")
        self.assertIs(c._closed_by, first)
        self.assertEqual(self.assert_closed_by(c, "cancel() called", None), at)

    def test_a_failed_request_then_close_keeps_the_request_failure(self):
        c = self.new_client()
        stream = self.open_stream(c, [init_event(), *message_events("end_turn", 2)])
        failure = "runtime stop reason end_turn inconsistent with 2 tool calls"
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaisesRegex(client.ProviderError, "^" + failure + "$"):
            next(stream)
        c.close()
        self.assert_closed_by(c, "request failed", failure)

    def test_closed_state_without_a_recorded_cause_gives_the_text_without_cause_or_time(self):
        c = self.new_client()
        c._closed.set()
        c.close()  # closes nothing: the client was already closed, so no cause is recorded
        self.assertIsNone(c._closed_by)
        for refuse in (lambda: c.create(model=MODEL, messages=list(MESSAGES)), c._check_active):
            with self.assertNoLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
                refuse()
            self.assertEqual(str(raised.exception), CLOSED)


if __name__ == "__main__":
    unittest.main()
