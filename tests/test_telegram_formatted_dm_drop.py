"""Telegram DM text with formatting entities: admission -> message handler (card t_6f475561).

Owner report (2026-10-18): a private-chat text carrying formatting entities (e.g. ``pre``
from a copied code block) is acknowledged and receipted but never batched, logged or turned.

What this file proves against the installed adapter (read-only import, real PTB dispatch):

(a) control: plain ~1k and ~4k DM text reaches the message handler exactly once;
(b) the same text with ``pre`` / ``code`` / ``bold`` / mixed / blockquote entities, with
    non-BMP emoji before the entity so UTF-16 offsets differ from code points, ALSO reaches
    the handler exactly once with text equal to the plain delivery.  The reported drop does
    NOT reproduce in the adapter path for a well-formed ``message.text`` update, so these
    are ordinary regression assertions, not expected failures (see the evidence doc);
(c) a text-less ``rich_message`` DM from the authorized user (content only in
    ``rich_message.blocks``) reaches the handler exactly once with its flattened text
    (fixed upstream in ceeeec8374fd and b3daabee04ca, issue #63485, in v0.23.3);
(d) an admitted update that no core handler serves (a ``new_chat_title`` service message) is
    not delivered and not receipted, and it logs exactly one INFO line with its update id and
    field names only (fixed upstream in 4a2b984fd2ed, issue #141570; upstream tests added in
    edb9736963cf).
    Before v0.23.3 the group-99 ``TypeHandler`` observer completed such a claim, so the
    receipt was written with no batch, no turn and no log line.

Hermetic: temporary HERMES_HOME via tests/hermes_isolated_home.py (never ~/.hermes), the
committed venv interpreter with ``-I -B`` (no byte-compile into the installed tree), a
stubbed Bot API request object (only getMe is answered, offline), INET/INET6 sockets
blocked in the child, no bot token, synthetic text only.  Skips (never passes) when the
installed Hermes cannot be provided in an isolated home.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_isolated_home as hih  # noqa: E402

RESULT_MARKER = "TG_FORMATTED_DM_RESULT:"

# asyncio needs AF_UNIX socketpairs for its self-pipe, so block only internet families.
_CHILD = r'''
import socket as _sm
_REAL = _sm.socket
class _NoInet(_REAL):
    def __init__(self, family=-1, *a, **k):
        fam = family if family != -1 else _sm.AF_INET
        if fam in (_sm.AF_INET, _sm.AF_INET6):
            raise AssertionError("telegram formatted-dm probe attempted network")
        super().__init__(family, *a, **k)
_sm.socket = _NoInet

import asyncio, json, logging, os, sys
sys.path.insert(0, {root!r})
import hermes_bootstrap  # noqa: F401
from unittest.mock import AsyncMock, patch
from telegram import Update
from telegram.request import BaseRequest
from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter

BOT_ID = 111
ADMISSION_LOGGER = "plugins.platforms.telegram.update_admission"
RECORDS = []
class _Collect(logging.Handler):
    def emit(self, record):
        message = record.getMessage() if record.name == ADMISSION_LOGGER else None
        RECORDS.append((record.levelno, record.name, message))
logging.getLogger().addHandler(_Collect())
logging.getLogger().setLevel(logging.DEBUG)


class NoNetwork(BaseRequest):
    @property
    def read_timeout(self):
        return 1
    async def initialize(self):
        pass
    async def shutdown(self):
        pass
    async def do_request(self, url, method, request_data=None, **kw):
        endpoint = url.rsplit("/", 1)[-1]
        assert endpoint == "getMe", "no Bot API call other than getMe: " + endpoint
        return 200, json.dumps({{"ok": True, "result": {{
            "id": BOT_ID, "is_bot": True, "first_name": "Offline", "username": "offline_bot"}}}}).encode()


def build(bot, uid, extra):
    message = {{"message_id": 500 + uid, "date": 1800000000,
               "chat": {{"id": 42, "type": "private", "first_name": "Human"}},
               "from": {{"id": 88, "is_bot": False, "first_name": "Human"}}}}
    message.update(extra)
    return Update.de_json({{"update_id": uid, "message": message}}, bot)


async def main(cases):
    os.environ["TELEGRAM_ALLOWED_USERS"] = "88"
    os.environ["TELEGRAM_WEBHOOK_URL"] = ""
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="111:offline-test", extra={{}}))
    adapter._message_handler = AsyncMock()
    delivered = []
    def start(event, session_key):
        delivered.append(event)
        return True
    out = []
    with patch.object(adapter, "_build_ptb_requests", AsyncMock(return_value=(NoNetwork(), NoNetwork()))), \
         patch.object(adapter, "_start_polling_mode", AsyncMock()), \
         patch.object(adapter, "_start_post_connect_housekeeping", lambda: None), \
         patch.object(adapter, "_restart_task_attr", lambda name, coro: coro.close()), \
         patch.object(adapter, "_set_status_indicator", AsyncMock()), \
         patch.object(adapter, "_start_session_processing", start):
        assert await adapter.connect(is_reconnect=False)
        app = adapter._app
        for uid, (name, extra) in enumerate(cases, start=1):
            before, log_before = len(delivered), len(RECORDS)
            error = None
            try:
                await app.process_update(build(app.bot, uid, extra))
                for _ in range(3):  # drain text-batch flush tasks (no fixed sleeps)
                    tasks = [t for t in adapter._pending_text_batch_tasks.values() if not t.done()]
                    if not tasks:
                        break
                    await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(0)
            except Exception as exc:  # pragma: no cover - reported, never swallowed
                error = type(exc).__name__
            got = delivered[before:]
            window = RECORDS[log_before:]
            out.append({{
                "name": name, "deliveries": len(got),
                "text": got[0].text if got else None,
                "receipt": "%d:%d" % (BOT_ID, uid) in adapter._seen_update_ids,
                "held": len(getattr(adapter, "_held_inbound_events", None) or []),
                "pending": len(adapter._pending_text_batches),
                "info_or_higher_logs": sum(1 for lvl, _, _ in window if lvl >= logging.INFO),
                "admission_logs": [msg for lvl, _, msg in window if msg is not None and lvl >= logging.INFO],
                "error": error,
            }})
        await adapter.disconnect()
    return out

cases = json.loads(sys.argv[1])
print({marker!r} + json.dumps(asyncio.run(main(cases))))
'''

PREFIX = "\U0001F600 intro \U0001F680\n"  # two non-BMP emoji before every entity

# Text-less message whose content is only in rich_message blocks (Bot API field kept by PTB in
# api_kwargs), and the text the installed rich_message_text flattens it to.
RICH_MESSAGE = {"blocks": [
    {"type": "paragraph", "text": ["\U0001F600 synthetic ", {"type": "bold", "text": "rich"}, " paragraph"]},
    {"type": "list", "items": [
        {"label": "-", "blocks": [{"type": "paragraph", "text": "first item"}]},
        {"label": "-", "blocks": [{"type": "paragraph", "text": "second item"}]}]}]}
RICH_TEXT = "\U0001F600 synthetic rich paragraph\n- first item\n- second item"
UNSERVED_TITLE = "Synthetic title"


def _u16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _body(total: int) -> tuple[str, str]:
    line = "def f(x):  # \U0001F9EA synthetic\n    return x * 2\n"
    code = (line * (total // len(line) + 1))[: total - len(PREFIX)]
    return PREFIX + code, code


def _cases() -> list[tuple[str, dict]]:
    cases = []
    for size in (1000, 3900):  # 3900 code points = 4024 UTF-16 units, under the 4096 limit
        text, code = _body(size)
        off, length = _u16(PREFIX), _u16(code)
        assert off != len(PREFIX), "fixture must make UTF-16 offsets differ from code points"
        variants = {
            "plain": None,
            "pre": [{"type": "pre", "offset": off, "length": length, "language": "python"}],
            "code": [{"type": "code", "offset": off, "length": 8}],
            "bold": [{"type": "bold", "offset": 0, "length": 2}],
            "mix": [{"type": "bold", "offset": 0, "length": 2},
                    {"type": "code", "offset": off, "length": 3},
                    {"type": "pre", "offset": off + 5, "length": length - 5}],
            "blockquote": [{"type": "expandable_blockquote", "offset": 0, "length": _u16(text)}],
        }
        for kind, entities in variants.items():
            extra = {"text": text}
            if entities:
                extra["entities"] = entities
            cases.append((f"{kind}{size}", extra))
    cases.append(("rich", {"rich_message": RICH_MESSAGE}))
    # An admitted message no core handler matches; the same shape as upstream's own test.
    cases.append(("unserved", {"new_chat_title": UNSERVED_TITLE}))
    return cases


_RESULTS: dict[str, dict] | None = None
_SKIP: str | None = None


def run_probe(iso: hih.IsolatedHome) -> dict:
    """Run the real-PTB dispatch child in *iso*; returns ``{case name: result}``."""
    import subprocess
    script = iso.home / "telegram_formatted_dm_probe.py"
    script.write_text(_CHILD.format(root=str(iso.checkout_root), marker=RESULT_MARKER),
                      encoding="utf-8")
    proc = subprocess.run(iso.child_command(script) + [json.dumps(_cases())], env=iso.env,
                          capture_output=True, text=True, timeout=240, check=False)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(RESULT_MARKER)]
    if proc.returncode != 0 or not lines:
        raise AssertionError(f"probe child failed rc={proc.returncode}\nstdout: {proc.stdout[-3000:]}\n"
                             f"stderr: {proc.stderr[-3000:]}")
    return {r["name"]: r for r in json.loads(lines[-1][len(RESULT_MARKER):])}


def _run_child() -> None:
    global _RESULTS, _SKIP
    if _RESULTS is not None or _SKIP is not None:
        return
    try:
        with hih.isolated_hermes_home() as iso:
            _RESULTS = run_probe(iso)
    except hih.IsolatedHomeError as exc:
        _SKIP = f"installed Hermes not available in an isolated home: {exc}"


class _ProbeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _run_child()
        if _SKIP:
            raise unittest.SkipTest(_SKIP)

    def result(self, name: str) -> dict:
        assert _RESULTS is not None
        r = _RESULTS[name]
        self.assertIsNone(r["error"], f"{name}: process_update raised {r['error']}")
        return r


class PlainDmControl(_ProbeCase):
    """(a) plain ~1k and ~4k DM text reaches the message handler exactly once."""

    def test_plain_dm_text_delivered_once(self):
        for size in (1000, 3900):
            with self.subTest(size=size):
                r = self.result(f"plain{size}")
                self.assertEqual(r["deliveries"], 1)
                self.assertTrue(r["receipt"])
                self.assertEqual(r["text"], _body(size)[0].strip())
                self.assertEqual((r["held"], r["pending"]), (0, 0))


class FormattedDmDelivery(_ProbeCase):
    """(b) entity-carrying DM text: reaches the handler once, text equal to the plain delivery.

    Not an expectedFailure: the reported drop does not reproduce for a well-formed
    ``message.text`` update.  expand_link_entities (telegram_entities.py:24-68) only acts on
    ``text_link``; formatting entities never reach mention/command gating in a DM
    (_should_process_message returns True for non-group chats, adapter.py:6495-6496).
    """

    def test_formatted_dm_text_delivered_once_equal_to_plain(self):
        for size in (1000, 3900):
            plain = self.result(f"plain{size}")
            for kind in ("pre", "code", "bold", "mix", "blockquote"):
                with self.subTest(size=size, entities=kind):
                    r = self.result(f"{kind}{size}")
                    self.assertEqual(r["deliveries"], 1)
                    self.assertEqual(r["text"], plain["text"])
                    self.assertTrue(r["receipt"])
                    self.assertEqual((r["held"], r["pending"]), (0, 0))
                    self.assertEqual(r["admission_logs"], [])


class TextlessRichMessageDelivery(_ProbeCase):
    """(c) a text-less ``rich_message`` DM is delivered once with its flattened text."""

    def test_textless_rich_message_delivered_once_with_its_text(self):
        r = self.result("rich")
        self.assertEqual(r["deliveries"], 1)
        self.assertEqual(r["text"], RICH_TEXT)
        self.assertTrue(r["receipt"])
        self.assertEqual((r["held"], r["pending"]), (0, 0))
        self.assertEqual(r["admission_logs"], [])


class UnservedUpdateNotReceipted(_ProbeCase):
    """(d) an update no core handler serves: not delivered, not receipted, logged by names only."""

    def test_unserved_update_not_receipted_and_logged_once_without_content(self):
        r = self.result("unserved")
        update_id = len(_cases())  # the unserved update is the last case
        self.assertEqual(r["deliveries"], 0)
        self.assertFalse(r["receipt"], "an unserved update must stay unreceipted")
        self.assertEqual(r["admission_logs"], [
            f"[Telegram] Update {update_id} matched no core handler; not receipted "
            "(fields: message(chat,date,from,message_id,new_chat_title), update_id)"])
        # No value from the synthetic update appears: chat id, user id, name, title, date, message id.
        for value in ("42", "88", "Human", UNSERVED_TITLE, "1800000000", str(500 + update_id)):
            self.assertNotIn(value, r["admission_logs"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
