"""Content-free record of one request's runtime stream, written to a file when the stream fails.

Reply text is held in memory only, to compute its length, hash and relation to the
previous message. The file holds allowlisted fields: event types, identifiers,
counts, hashes and relations. It never holds text, thinking, tool arguments or
results, prompts, environment, paths or credentials.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

SCHEMA_VERSION = 1
MAX_MESSAGES = 32    # per request
MAX_RUNS = 256       # run-length-encoded event types, per message and for the whole request
MAX_BLOCKS = 64      # per message
MAX_AUDIT = 200      # newest client audit entries kept
DRAIN_SECONDS, DRAIN_IDLE_SECONDS = 5.0, 1.0
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]+")

# Client audit stages and the only fields copied from each; tool_parked's arguments are left out.
AUDIT_FIELDS = {
    "session_reset": (), "untested_cli": ("version",), "launch": ("pid", "model"),
    "rebuild": ("messages", "tail", "skipped_leading", "sha256"), "user_input": ("number",),
    "init": ("model",), "runtime_retry": ("number",),
    "tool_parked": ("tool_use_id", "rpc_id", "name", "model", "calls"),
    "result_delivered": ("tool_use_id", "rpc_id", "text_sha256"),
    "result_returned": ("rpc_id", "tool_use_id"), "result": ("num_turns",),
    "second_message": ("outcome", "row", "number", "first_id", "second_id", "first_stop", "second_stop", "relation",
                       "same_model", "first_calls", "second_calls", "answered", "answered_errors", "requested",
                       "dropped_text_chars", "dropped_calls"),
}


def label(value, limit=120):
    """An identifier-like runtime string as is, otherwise a placeholder; never free text."""
    if value is None:
        return None
    if isinstance(value, str) and len(value) <= limit and IDENTIFIER.fullmatch(value):
        return value
    return "<other>"


def scalar(value):
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    return label(value)


def numbers(value):
    """Only the numeric fields of a usage record (token counts, cost); nothing nested."""
    if not isinstance(value, dict):
        return None
    return {label(k, 60): v for k, v in value.items()
            if type(v) in (int, float) and math.isfinite(v)}


def sanitize(entry):
    if not isinstance(entry, dict):
        return {"stage": "<other>"}
    stage = entry.get("stage")
    if stage not in AUDIT_FIELDS:
        return {"stage": label(stage, 40)}
    out = {"stage": stage, **{k: scalar(entry.get(k)) for k in AUDIT_FIELDS[stage] if k in entry}}
    if stage == "init" and isinstance(entry.get("tools"), list):
        out["tool_count"] = len(entry["tools"])
    if stage == "result":
        out["usage"] = numbers(entry.get("usage"))
        meta = entry.get("modelUsage")
        out["modelUsage"] = {label(k, 80): numbers(v) for k, v in meta.items()} if isinstance(meta, dict) else None
    return out


def mapping(value):
    return value if isinstance(value, dict) else {}


def session_label(session_id):
    if not isinstance(session_id, str):
        return "nosession"
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:80] or "nosession"


def common_prefix(before, after):
    count = 0
    for x, y in zip(before, after):
        if x != y:
            break
        count += 1
    return count


def relation(before, after):
    if not after:
        return "empty"
    if not before:
        return "previous_empty"
    if after == before:
        return "equal"
    if before.startswith(after):
        return "prefix_of_previous"
    if after.startswith(before):
        return "extends_previous"
    return "disjoint"


class Runs:
    """Event types in order, consecutive repeats counted, bounded."""
    def __init__(self):
        self.items, self.dropped = [], 0

    def add(self, name):
        if self.items and self.items[-1][0] == name:
            self.items[-1][1] += 1
        elif len(self.items) < MAX_RUNS:
            self.items.append([name, 1])
        else:
            self.dropped += 1


class StreamLog:
    """Per-request observer of runtime events. Keys starting with "_" stay in memory."""
    def __init__(self):
        self.events = Runs()
        self.messages = []
        self.dropped_messages = 0
        self.restarts = 0
        self.result = False
        self.drained = None

    def observe(self, obj, forwarded=False):
        """Record one runtime event; `forwarded` means its text reached Hermes."""
        try:
            self._observe(obj, forwarded)
        except Exception:  # the record must never change the request's outcome
            pass

    def _observe(self, obj, forwarded):
        if not isinstance(obj, dict):
            self.events.add("<non-object>")
            return
        kind = label(obj.get("type"), 40) or "<none>"
        current = self.messages[-1] if self.messages else None
        if kind == "assistant":
            self.events.add(kind)
            msg = obj.get("message")
            if current is not None:
                same = isinstance(msg, dict) and msg.get("id") == current["_id"]
                current["events"].add("assistant" if same else "assistant:other_message")
            return
        if kind != "stream_event":
            self.result = self.result or kind == "result"
            self.events.add(f"system:{label(obj.get('subtype'), 40)}" if kind == "system" else kind)
            return
        ev = mapping(obj.get("event"))
        event = label(ev.get("type"), 40) or "<none>"
        self.events.add("stream_event:" + event if event in ("message_start", "message_stop", "error") else "stream_event")
        if event == "message_start":
            self._start(mapping(ev.get("message")))
            return
        if current is None:
            return  # outside any message; the request-level events show it
        current["events"].add(event)
        index = ev.get("index")
        if event == "content_block_start":
            block = mapping(ev.get("content_block"))
            block_type = label(block.get("type"), 40)
            if len(current["blocks"]) < MAX_BLOCKS:
                current["blocks"].append({"index": index if type(index) is int else None, "type": block_type})
            else:
                current["blocks_truncated"] += 1
            if type(index) is int:
                current["_kinds"][index] = block_type
            if block_type == "text" and isinstance(block.get("text"), str):
                self._text(current, block["text"], forwarded)
        elif event == "content_block_delta":
            delta = mapping(ev.get("delta"))
            if (type(index) is int and current["_kinds"].get(index) == "text" and delta.get("type") == "text_delta"
                    and isinstance(delta.get("text"), str)):
                self._text(current, delta["text"], forwarded)
        elif event == "message_delta":
            delta = mapping(ev.get("delta"))
            current["stop_reason"] = label(delta.get("stop_reason"), 40)
        elif event == "message_stop":
            current["stopped"] = True
        elif event == "error":
            current["error_type"] = label(mapping(ev.get("error")).get("type"), 40)

    def _start(self, msg):
        previous = self.messages[-1] if self.messages else None
        restart = previous is not None and not previous["stopped"]
        self.restarts += restart
        if len(self.messages) >= MAX_MESSAGES:
            self.messages.pop(0)
            self.dropped_messages += 1
        events = Runs()
        events.add("message_start")
        self.messages.append({
            "id": label(msg.get("id")), "model": label(msg.get("model"), 80), "stop_reason": None, "stopped": False,
            "after_stopped_message": previous is not None and previous["stopped"], "restart": restart,
            "restarts": self.restarts, "error_type": None, "events": events, "blocks": [], "blocks_truncated": 0,
            "_id": msg.get("id"), "_model": msg.get("model"), "_kinds": {}, "_text": [], "_forwarded_chars": 0,
            "_streamed_text": False})

    @staticmethod
    def _text(entry, text, forwarded):
        entry["_text"].append(text)
        if forwarded:
            entry["_forwarded_chars"] += len(text)
            entry["_streamed_text"] = entry["_streamed_text"] or bool(text.strip())

    def drain(self, read, active):
        """After a failure, keep reading briefly (never forwarding) until the current message or turn ends."""
        start = last = time.monotonic()
        count, ended = 0, "complete"
        while True:
            current = self.messages[-1] if self.messages else None
            now = time.monotonic()
            if current is None or current["stopped"] or self.result:
                break
            if now - start >= DRAIN_SECONDS:
                ended = "time_bound"
                break
            if now - last >= DRAIN_IDLE_SECONDS:
                ended = "idle"
                break
            if not active():
                ended = "cancelled"
                break
            try:
                obj = read()
            except Exception:
                ended = "read_failed"
                break
            if obj is not None:
                last = time.monotonic()
                count += 1
                self.observe(obj)
        self.drained = {"events": count, "ended": ended, "seconds": round(time.monotonic() - start, 3)}

    def report(self):
        messages, previous = [], None
        for entry in self.messages:
            text = "".join(entry["_text"])
            item = {k: v for k, v in entry.items() if not k.startswith("_") and k != "events"}
            item.update(events=entry["events"].items, events_truncated=entry["events"].dropped,
                        streamed_text=entry["_streamed_text"], forwarded_chars=entry["_forwarded_chars"],
                        text_chars=len(text), text_sha256=hashlib.sha256(text.encode()).hexdigest())
            if previous is not None:
                before = "".join(previous["_text"])
                item.update(relation_to_previous=relation(before, text),
                            common_prefix_chars=common_prefix(before, text),
                            same_id_as_previous=entry["_id"] == previous["_id"],
                            same_model_as_previous=entry["_model"] == previous["_model"])
            messages.append(item)
            previous = entry
        return {"messages": messages, "messages_truncated": self.dropped_messages, "restarts": self.restarts,
                "result_seen": self.result, "runtime_events": self.events.items,
                "runtime_events_truncated": self.events.dropped, "drain": self.drained}


def payload(error, session_id, model, cli_version, audit, stream_log):
    entries = list(audit)[-MAX_AUDIT:]
    return {"schema_version": SCHEMA_VERSION, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session_id": session_label(session_id), "model": label(model, 80), "cli_version": label(cli_version, 40),
            "error": {"class": type(error).__name__, "message": str(error)[:500]},
            "audit": [sanitize(e) for e in entries], "audit_truncated": len(audit) - len(entries),
            "stream": stream_log.report()}


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def write(home, session_id, record):
    """Write the record once, owner-only (0600), atomically; never replaces an existing file."""
    directory = Path(home) / "sessions"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"stream_audit_{session_label(session_id)}_{_stamp()}.json"
    data = (json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".stream_audit_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)  # atomic, and fails rather than replace an existing file
    finally:
        os.unlink(temporary)
    return path
