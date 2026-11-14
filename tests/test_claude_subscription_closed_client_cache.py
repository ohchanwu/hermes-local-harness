"""A closed client asks Hermes to remove it from the Hermes auxiliary client cache.

Hermetic: Hermes source is not imported or executed. A stand-in module, placed at
sys.modules["agent.auxiliary_client"] for the duration of a test, has a dictionary as the cache, a
threading.Lock() as the cache lock, a function _evict_cached_client_instance(target) that acquires that
lock and removes the entries whose client is target, and a lookup that returns a stored client without a
check of whether it is closed and otherwise builds and stores a new one. Every runtime event is synthetic;
no CLI child process is started, no network is used and no file is written. The plugin modules are loaded
through the bare package of test_claude_subscription_provider.py.
"""
import gc
from pathlib import Path
import re
import sys
import threading
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402
import test_claude_subscription_failure_text as failure_text  # noqa: E402

client = provider.client
MODEL = provider.MODEL
MESSAGES = failure_text.MESSAGES
MODULE_NAME = "agent.auxiliary_client"
KEY = ("synthetic-home", "claude-subscription", False, MODEL)  # one cache key; the form is not relevant here
JOIN_SECONDS = 5
NO_STOP_REASON = "runtime message ended without a stop reason"
PROTOCOL_OSERROR = "runtime startup, I/O or malformed protocol: OSError"
RESET_FAILED = "session reset failed (SyntheticFailure); client closed"


def closed_error_pattern(cause):
    return (re.escape(failure_text.CLOSED + " (closed at ") + failure_text.TIME
            + re.escape(" by: " + cause + ")"))


class StandInCache:
    """The parts of the Hermes auxiliary client cache that this card relies on."""

    def __init__(self):
        self.entries = {}
        self.lock = threading.Lock()
        self.removal_calls = []
        self.built = []

    def evict(self, target):
        """_evict_cached_client_instance: acquires the lock, removes the entries whose client is target."""
        self.removal_calls.append(target)
        removed = False
        with self.lock:
            for key, entry in list(self.entries.items()):
                if entry is target:
                    del self.entries[key]
                    removed = True
        return removed

    def lookup(self, key=KEY):
        """Returns the stored client without a check of whether it is closed; otherwise builds and stores one."""
        with self.lock:
            if key in self.entries:
                return self.entries[key]
        built = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.built.append(built)
        with self.lock:
            return self.entries.setdefault(key, built)

    def holds(self, target):
        with self.lock:
            return any(entry is target for entry in self.entries.values())

    def module(self):
        module = types.ModuleType(MODULE_NAME)
        module._client_cache = self.entries
        module._client_cache_lock = self.lock
        module._evict_cached_client_instance = self.evict
        return module


class CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.cache = StandInCache()
        self.addCleanup(self.close_built)

    def close_built(self):
        for built in self.cache.built:
            built._runtime = None  # a synthetic runtime child of a test has nothing to clean up
            built.close()

    def load_module(self, module):
        """Place `module` (None: no module) at sys.modules["agent.auxiliary_client"] for this test."""
        patcher = patch.dict(sys.modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.modules.pop(MODULE_NAME, None)
        if module is not None:
            sys.modules[MODULE_NAME] = module

    def load_stand_in(self):
        self.load_module(self.cache.module())

    def open_stream(self, c, events):
        """A request on `c` whose runtime child is the synthetic runtime of the failure text tests."""
        c._scope = c._current_scope(None)
        c._model, c._tools, c._cli_version = MODEL, [], max(failure_text.compat.CLI_TESTED)
        tail = c._history.accept(list(MESSAGES))
        c._runtime = failure_text.SyntheticRuntime(events)
        c._busy.acquire()
        c._busy_owner = threading.get_ident()
        return client.Stream(c, c._drive(tail, 30))

    def fail_without_stop_reason(self, c):
        """A request on `c` that fails with a ProviderError; returns the error as the caller receives it."""
        stream = self.open_stream(c, [failure_text.init_event(), *failure_text.message_events(failure_text.NO_DELTA, 0)])
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            next(stream)
        return raised.exception, self.cache.holds(c)

    def fail_in_start(self, c, exception):
        """A request on `c` whose start raises `exception`; returns the error and whether the cache held `c`
        when the error reached the caller."""
        stream = self.open_stream(c, [])
        c._runtime = None
        with patch.object(c, "_start", side_effect=exception):
            try:
                next(stream)
            except BaseException as error:  # noqa: B902 - KeyboardInterrupt is one of the cases
                return error, self.cache.holds(c)
        self.fail("the request did not fail")

    def fail_reset(self, c):
        c._runtime = failure_text.FailingRuntime([])
        with self.assertRaises(client.ProviderError) as raised:
            try:
                c._reset_session()
            finally:
                held = self.cache.holds(c)
        c._runtime = None  # the remains were put back for close(); this runtime cannot be closed
        return raised.exception, held

    def refuse_create(self, c):
        """The closed-client error of one request on `c` through create(), and whether the cache held `c` then."""
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            c.create(model=MODEL, messages=list(MESSAGES))
        return raised.exception, self.cache.holds(c)

    def assert_new_client_after(self, closed):
        """The cache no longer holds `closed`; the next lookup returns a different client that is not closed."""
        self.assertFalse(self.cache.holds(closed))
        new = self.cache.lookup()
        self.assertIsNot(new, closed)
        self.assertFalse(new.is_closed())
        self.assertIs(self.cache.lookup(), new)

    def run_while_lock_held(self, action):
        """Run `action` in a thread while this thread holds the stand-in cache lock; it must return in time."""
        outcome = {}

        def target():
            try:
                action()
            except BaseException as exc:  # noqa: B902
                outcome["raised"] = exc
            outcome["returned"] = True

        with self.cache.lock:
            worker = threading.Thread(target=target, daemon=True)
            worker.start()
            worker.join(JOIN_SECONDS)
            self.assertFalse(worker.is_alive(), "the call waited for the Hermes cache lock")
        self.assertTrue(outcome.get("returned"))
        return outcome.get("raised")


class ReproductionTests(CacheTestCase):
    def test_without_a_loaded_module_a_closed_client_stays_cached_and_refuses_the_next_request(self):
        self.load_module(None)
        c = self.cache.lookup()
        error, held = self.fail_without_stop_reason(c)
        self.assertEqual(str(error), NO_STOP_REASON)
        self.assertTrue(c.is_closed())
        self.assertTrue(held)
        self.assertIs(self.cache.lookup(), c)
        refused, held = self.refuse_create(self.cache.lookup())
        self.assertRegex(str(refused), "^" + closed_error_pattern("request failed") + "$")
        self.assertTrue(held)
        self.assertNotIn(MODULE_NAME, sys.modules)  # the plugin did not import the module


class RemovalAfterAFailedRequestTests(CacheTestCase):
    """Item 2b: the request error handlers."""

    def setUp(self):
        super().setUp()
        self.load_stand_in()

    def test_a_request_that_fails_with_a_provider_error(self):
        c = self.cache.lookup()
        error, held = self.fail_without_stop_reason(c)
        self.assertIs(type(error), client.ProviderError)
        self.assertEqual(str(error), NO_STOP_REASON)
        self.assertFalse(held)
        self.assertEqual(self.cache.removal_calls, [c])
        self.assert_new_client_after(c)

    def test_a_request_that_fails_with_an_exception_that_the_handler_converts(self):
        c = self.cache.lookup()
        error, held = self.fail_in_start(c, OSError(failure_text.MARKER))
        self.assertIs(type(error), client.ProviderError)
        self.assertEqual(str(error), PROTOCOL_OSERROR)
        self.assertFalse(held)
        self.assert_new_client_after(c)

    def test_a_request_that_fails_with_another_exception(self):
        c = self.cache.lookup()
        error, held = self.fail_in_start(c, failure_text.SyntheticFailure(failure_text.MARKER))
        self.assertIs(type(error), failure_text.SyntheticFailure)
        self.assertFalse(held)
        self.assert_new_client_after(c)

    def test_a_request_that_ends_with_keyboard_interrupt_asks_for_no_removal(self):
        c = self.cache.lookup()
        error, held = self.fail_in_start(c, KeyboardInterrupt())
        self.assertIs(type(error), KeyboardInterrupt)
        self.assertTrue(c.is_closed())
        self.assertTrue(held)
        self.assertEqual(self.cache.removal_calls, [])

    def test_a_refusal_inside_the_lifecycle_lock_reaches_the_error_handler(self):
        # _check_active raises the closed-client error inside `with self._lifecycle` at the start of a
        # request; the removal is asked for by the error handler, after that lock is released.
        c = self.cache.lookup()
        stream = self.open_stream(c, [])
        c.cancel()
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
            next(stream)
        self.assertRegex(str(raised.exception), "^" + closed_error_pattern("cancel() called") + "$")
        self.assertEqual(self.cache.removal_calls, [c])
        self.assert_new_client_after(c)


class RemovalAfterAFailedSessionResetTests(CacheTestCase):
    """Item 2c."""

    def test_a_failed_session_reset(self):
        self.load_stand_in()
        c = self.cache.lookup()
        error, held = self.fail_reset(c)
        self.assertEqual(str(error), RESET_FAILED)
        self.assertTrue(c.is_closed())
        self.assertFalse(held)
        self.assert_new_client_after(c)


class RemovalWhenAClosedClientRefusesTests(CacheTestCase):
    """Item 2a and the remaining case of item 5."""

    def setUp(self):
        super().setUp()
        self.load_stand_in()

    def assert_stays_until_one_refusal(self, close, cause):
        c = self.cache.lookup()
        close(c)
        self.assertTrue(c.is_closed())
        self.assertTrue(self.cache.holds(c))
        self.assertIs(self.cache.lookup(), c)
        error, held = self.refuse_create(c)
        self.assertRegex(str(error), "^" + closed_error_pattern(cause) + "$")
        self.assertFalse(held)
        self.assert_new_client_after(c)

    def test_a_client_closed_with_close_while_no_request_is_in_progress(self):
        self.assert_stays_until_one_refusal(lambda c: c.close(), "close() called")

    def test_a_client_closed_with_cancel_while_no_request_is_in_progress(self):
        self.assert_stays_until_one_refusal(lambda c: c.cancel(), "cancel() called")

    def test_check_active_outside_the_lifecycle_lock_asks_for_the_removal(self):
        c = self.cache.lookup()
        c.cancel()
        with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError):
            c._check_active()
        self.assert_new_client_after(c)

    def test_check_active_inside_the_lifecycle_lock_does_not_wait_for_the_hermes_cache_lock(self):
        c = self.cache.lookup()
        c.cancel()

        def refuse():
            with c._lifecycle:
                c._check_active()

        with self.assertLogs(client.log.name, "WARNING"):
            raised = self.run_while_lock_held(refuse)
        self.assertIs(type(raised), client.ProviderError)
        self.assertEqual(self.cache.removal_calls, [])
        self.assertTrue(self.cache.holds(c))


class CallsThatNeverAskForTheRemovalTests(CacheTestCase):
    """Item 3: each call returns while the Hermes cache lock is held by another thread."""

    def setUp(self):
        super().setUp()
        self.load_stand_in()

    def assert_no_removal(self, c):
        self.assertTrue(c.is_closed())
        self.assertEqual(self.cache.removal_calls, [])
        self.assertTrue(self.cache.holds(c))

    def test_close(self):
        c = self.cache.lookup()
        self.assertIsNone(self.run_while_lock_held(c.close))
        self.assert_no_removal(c)

    def test_close_and_stream_close_while_a_request_is_open(self):
        c = self.cache.lookup()
        stream = self.open_stream(c, [])
        c.cancel()
        self.assertIsNone(self.run_while_lock_held(c.close))
        self.assertIsNone(self.run_while_lock_held(stream.close))
        self.assert_no_removal(c)

    def test_cancel(self):
        c = self.cache.lookup()
        self.assertIsNone(self.run_while_lock_held(c.cancel))
        self.assert_no_removal(c)

    def test_exit_of_the_context_manager(self):
        c = self.cache.lookup()
        self.assertIsNone(self.run_while_lock_held(lambda: c.__exit__(None, None, None)))
        self.assert_no_removal(c)

    def test_stream_close_of_an_unfinished_stream(self):
        c = self.cache.lookup()
        stream = self.open_stream(c, [failure_text.init_event(), *failure_text.message_events("end_turn", 0),
                                      failure_text.result_event()])
        next(stream)
        self.assertIsNone(self.run_while_lock_held(stream.close))
        self.assert_no_removal(c)

    def test_stream_close_before_the_first_iteration(self):
        c = self.cache.lookup()
        stream = self.open_stream(c, [])
        self.assertIsNone(self.run_while_lock_held(stream.close))
        self.assert_no_removal(c)

    def test_closing_an_unfinished_request_generator(self):
        c = self.cache.lookup()
        stream = self.open_stream(c, [failure_text.init_event(), *failure_text.message_events("end_turn", 0),
                                      failure_text.result_event()])
        next(stream)
        self.assertIsNone(self.run_while_lock_held(stream.iterator.close))  # GeneratorExit in the request
        self.assert_no_removal(c)
        c._release_busy()

    def test_garbage_collection_of_an_abandoned_request_generator(self):
        c = self.cache.lookup()
        stream = self.open_stream(c, [failure_text.init_event(), *failure_text.message_events("end_turn", 0),
                                      failure_text.result_event()])
        next(stream)
        c._release_busy()

        def collect():
            nonlocal stream
            stream = None
            gc.collect()

        self.assertIsNone(self.run_while_lock_held(collect))
        self.assert_no_removal(c)


class ErrorOfTheCallerIsUnchangedTests(CacheTestCase):
    """Item 1: an absent module, an absent or not callable attribute, and a function that raises."""

    def modules(self):
        without_attribute = types.ModuleType(MODULE_NAME)
        not_callable = types.ModuleType(MODULE_NAME)
        not_callable._evict_cached_client_instance = "not callable"
        raising = types.ModuleType(MODULE_NAME)

        def evict(target):
            raise RuntimeError(failure_text.MARKER)

        raising._evict_cached_client_instance = evict
        return {"module absent": None, "attribute absent": without_attribute,
                "attribute not callable": not_callable, "function raises RuntimeError": raising}

    def test_each_failure_gives_the_baseline_error(self):
        for name, module in self.modules().items():
            with self.subTest(name):
                self.load_module(module)
                error, _ = self.fail_without_stop_reason(self.cache.lookup(KEY + (name, "provider")))
                self.assertIs(type(error), client.ProviderError)
                self.assertEqual(str(error), NO_STOP_REASON)

                error, _ = self.fail_in_start(self.cache.lookup(KEY + (name, "converted")), OSError(failure_text.MARKER))
                self.assertIs(type(error), client.ProviderError)
                self.assertEqual(str(error), PROTOCOL_OSERROR)

                error, _ = self.fail_in_start(self.cache.lookup(KEY + (name, "other")),
                                              failure_text.SyntheticFailure(failure_text.MARKER))
                self.assertIs(type(error), failure_text.SyntheticFailure)

                error, _ = self.fail_reset(self.cache.lookup(KEY + (name, "reset")))
                self.assertEqual(str(error), RESET_FAILED)

                closed = self.cache.lookup(KEY + (name, "closed"))
                closed.close()
                error, _ = self.refuse_create(closed)
                self.assertIs(type(error), client.ProviderError)
                self.assertRegex(str(error), "^" + closed_error_pattern("close() called") + "$")
                with self.assertLogs(client.log.name, "WARNING"), self.assertRaises(client.ProviderError) as raised:
                    closed._check_active()
                self.assertRegex(str(raised.exception), "^" + closed_error_pattern("close() called") + "$")

                self.assertNotIn(failure_text.MARKER, str(error))
                self.assertEqual(sys.modules.get(MODULE_NAME), module)


class ClosedClientStaysClosedTests(CacheTestCase):
    """Item 4: a client removed from the cache still reports closed and refuses every later request."""

    def test_removed_client_stays_closed(self):
        self.load_stand_in()
        c = self.cache.lookup()
        error, held = self.fail_without_stop_reason(c)
        self.assertFalse(held)
        self.assertTrue(c.is_closed())
        for _ in range(2):
            refused, _ = self.refuse_create(c)
            self.assertRegex(str(refused), "^" + closed_error_pattern("request failed") + "$")
            self.assertTrue(c.is_closed())
        self.assertEqual(self.cache.removal_calls, [c, c, c])
        self.assert_new_client_after(c)


if __name__ == "__main__":
    unittest.main()
