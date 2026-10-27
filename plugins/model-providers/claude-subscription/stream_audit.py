"""Content-free record of one request's runtime stream, written to a file when the stream fails.

Reply text is held in memory only, to compute its length, hash and relation to the
previous message. The file holds allowlisted fields: event types, identifiers,
counts, hashes and relations. It never holds text, thinking, tool arguments or
results, prompts, environment, paths or credentials. A stream/snapshot mismatch adds a
classification of the two compared sides (key names, types, lengths, hashes, character
classes at the first difference) and, per unequal string key, `escape_decoding`: how the
snapshot's extra backslash-u decoding of the streamed value compares (counts, lengths,
indexes, character classes), never their values. A rejected MCP invocation
(client._match) adds `mcp_match_failure`: the call site, which condition failed, and
counts and booleans about the request and the candidate calls, never names or values.

One bounded exception: when a runtime stdout line is not JSON, `rejected_line` holds its
length, its sha256 and at most its first PREFIX_BYTES bytes as text, after Hermes's secret
redaction (agent.redact, forced on). A token that the PREFIX_BYTES boundary cuts is left out
whole, so redaction never sees a shortened secret. Without working redaction the prefix is
left out (null), never stored unredacted.
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
import unicodedata

from . import stream_events

SCHEMA_VERSION = 1
MAX_MESSAGES = 32    # per request
MAX_RUNS = 256       # run-length-encoded event types, per message and for the whole request
MAX_BLOCKS = 64      # per message
MAX_AUDIT = 200      # newest client audit entries kept
DRAIN_SECONDS, DRAIN_IDLE_SECONDS = 5.0, 1.0
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]+")
PREFIX_BYTES = 200   # of a rejected (non-JSON) runtime stdout line
TOKEN_BYTE = re.compile(rb"[A-Za-z0-9+/=_.~:%-]")    # bytes that can belong to a credential-like token
TOKEN_TAIL = re.compile(rb"[A-Za-z0-9+/=_.~:%-]+\Z")

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
    "snapshot_unicode_escape_accepted": ("index", "decoded"),  # plus bounded key names, never values
    "mcp_unicode_escape_accepted": ("call_site", "mcp_call", "sequence", "decoded"),  # plus bounded key names, never values
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
    if stage in ("snapshot_unicode_escape_accepted", "mcp_unicode_escape_accepted") and isinstance(entry.get("keys"), list):
        out["keys"], out["keys_truncated"] = only_keys(entry["keys"])
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
        if isinstance(obj, bytes):  # a stdout line that was not JSON; payload's rejected_line describes it
            self.events.add("<non-json-line>")
            return
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


MAX_MISMATCH_CALLS, MAX_MISMATCH_KEYS, MAX_ONLY_KEYS = 20, 50, 20
TYPES = {dict: "object", list: "array", str: "string", bool: "boolean", int: "integer", float: "number", type(None): "null"}


def kind_of(value):
    return TYPES.get(type(value), "<other>")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def strict_equal(a, b):
    """Equal with equal JSON types throughout, so 1 and 1.0 (equal to Python's ==) differ here."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def character(text, index):
    """Only the class of one character, never the character or its code point."""
    if index >= len(text):
        return None
    char = text[index]
    category = unicodedata.category(char)
    return {"category": category, "ascii": ord(char) < 128, "surrogate": category == "Cs", "control": category == "Cc"}


def string_difference(stream, snapshot):
    index = common_prefix(stream, snapshot)
    return {"first_difference": index,
            "prefix": "stream" if index == len(stream) else "snapshot" if index == len(snapshot) else None,
            "stream_char": character(stream, index), "snapshot_char": character(snapshot, index)}


def escape_decoding(stream, snapshot):
    """How the snapshot's extra backslash-u decoding (stream_events._decode) of a streamed string compares; no content.

    Counts of _ESCAPE matches and of what became of them, the decoded length, and whether the decoded value
    equals the snapshot. If not: the first index where they differ, the streamed index of that character, the
    class of the decoded and the snapshot character there, whether an _ESCAPE match starts at that streamed
    index, and if one does, whether a second backslash directly precedes it.
    """
    decoded, outcomes = stream_events._decode(stream)
    reasons = [outcome for outcome, _, _ in outcomes]
    out = {"sequences": len(outcomes), "decoded_sequences": reasons.count(stream_events.DECODED),
           "kept_odd_backslashes": reasons.count(stream_events.KEPT_ODD_BACKSLASHES),
           "kept_surrogate": reasons.count(stream_events.KEPT_SURROGATE),
           "kept_control": reasons.count(stream_events.KEPT_CONTROL),
           "decoded_length": len(decoded), "decoded_equal": decoded == snapshot}
    if decoded == snapshot:
        return out
    index = common_prefix(decoded, snapshot)
    position = index  # streamed index of decoded[index]: each decoded sequence before it is one character
    for outcome, start, end in outcomes:
        if start >= position:
            break
        if outcome == stream_events.DECODED:
            position += end - start - 1
    at_sequence = any(start == position for _, start, _ in outcomes)
    out.update(first_difference=index, stream_index=position, decoded_char=character(decoded, index),
               snapshot_char=character(snapshot, index), sequence_at_difference=at_sequence,
               backslash_before_sequence=(position > 0 and stream[position - 1] == stream_events.BACKSLASH)
               if at_sequence else None)
    return out


def key_name(key):
    return label(key[:40], 40) if isinstance(key, str) else "<other>"


def compare_value(key, stream, snapshot):
    out = {"key": key_name(key), "stream_type": kind_of(stream), "snapshot_type": kind_of(snapshot)}
    forms = [canonical(v) for v in (stream, snapshot)]
    out.update(stream_length=len(stream) if isinstance(stream, str) else len(forms[0]),
               snapshot_length=len(snapshot) if isinstance(snapshot, str) else len(forms[1]),
               equal=strict_equal(stream, snapshot), equal_canonical=json.loads(forms[0]) == json.loads(forms[1]),
               stream_sha256=hashlib.sha256(forms[0].encode()).hexdigest(),
               snapshot_sha256=hashlib.sha256(forms[1].encode()).hexdigest())
    if isinstance(stream, str) and isinstance(snapshot, str) and stream != snapshot:
        out.update(string_difference(stream, snapshot))
        out["escape_decoding"] = escape_decoding(stream, snapshot)
    return out


def only_keys(keys):
    names = sorted(key_name(k) for k in keys)
    return names[:MAX_ONLY_KEYS], max(0, len(names) - MAX_ONLY_KEYS)


def declared_name(name, declared):
    return name if isinstance(name, str) and name in declared else "<undeclared>"


def compare_call(index, stream, snapshot, declared):
    """One streamed call (id, name, arguments, fragments) against one snapshot tool_use block; either may be absent."""
    sides = [(c.get("id"), c.get("name"), c.get(key)) if isinstance(c, dict) else (None, None, None)
             for c, key in ((stream, "arguments"), (snapshot, "input"))]
    (stream_id, stream_name, stream_input), (snapshot_id, snapshot_name, snapshot_input) = sides
    fragments = stream.get("fragments") or [] if isinstance(stream, dict) else []
    out = {"index": index, "id_equal": stream is not None and snapshot is not None and stream_id == snapshot_id,
           "name_equal": stream is not None and snapshot is not None and stream_name == snapshot_name,
           "stream_name": None if stream is None else declared_name(stream_name, declared),
           "snapshot_name": None if snapshot is None else declared_name(snapshot_name, declared),
           "stream_input_type": "<missing>" if stream is None else kind_of(stream_input),
           "snapshot_input_type": "<missing>" if snapshot is None else kind_of(snapshot_input),
           "fragments": len(fragments), "fragment_chars": sum(len(f) for f in fragments)}
    if isinstance(stream_input, dict) and isinstance(snapshot_input, dict):
        out["only_in_stream"], out["only_in_stream_truncated"] = only_keys(stream_input.keys() - snapshot_input.keys())
        out["only_in_snapshot"], out["only_in_snapshot_truncated"] = only_keys(snapshot_input.keys() - stream_input.keys())
        common = sorted(stream_input.keys() & snapshot_input.keys())
        out["keys"] = [compare_value(k, stream_input[k], snapshot_input[k]) for k in common[:MAX_MISMATCH_KEYS]]
        out["keys_truncated"] = max(0, len(common) - MAX_MISMATCH_KEYS)
    return out


def snapshot_mismatch(kind, streamed, snapshot, declared=()):
    """Classify a stream/snapshot difference by identity, type, length, hash and character class; no content."""
    if kind == "text":
        forms = [canonical(t) for t in (streamed, snapshot)]
        return {"kind": "text", "stream_chars": len(streamed), "snapshot_chars": len(snapshot),
                "stream_sha256": hashlib.sha256(forms[0].encode()).hexdigest(),
                "snapshot_sha256": hashlib.sha256(forms[1].encode()).hexdigest(), **string_difference(streamed, snapshot)}
    count = max(len(streamed), len(snapshot))
    return {"kind": "tool_use", "streamed_calls": len(streamed), "snapshot_tool_uses": len(snapshot),
            "calls": [compare_call(i, streamed[i] if i < len(streamed) else None,
                                   snapshot[i] if i < len(snapshot) else None, set(declared))
                      for i in range(min(count, MAX_MISMATCH_CALLS))],
            "calls_truncated": max(0, count - MAX_MISMATCH_CALLS)}


def redactor():
    """Hermes's secret redaction, forced on; imported only when a rejected line is recorded."""
    from agent.redact import redact_sensitive_text
    return lambda text: redact_sensitive_text(text, force=True)


def rejected(line):
    """Length, sha256 and a bounded, redacted prefix of a runtime stdout line that was not JSON."""
    kept = line[:PREFIX_BYTES]
    if len(line) > PREFIX_BYTES and TOKEN_BYTE.fullmatch(line[PREFIX_BYTES:PREFIX_BYTES + 1]):
        # The boundary cuts a token: keep none of it, since redaction may not recognize a shortened secret.
        tail = TOKEN_TAIL.search(kept)
        kept = kept[:tail.start()] if tail else kept
    out = {"bytes": len(line), "sha256": hashlib.sha256(line).hexdigest(), "prefix_bytes": len(kept)}
    try:
        text = redactor()(kept.decode("utf-8", errors="backslashreplace"))
        if not isinstance(text, str):
            raise TypeError("redaction returned no text")
    except Exception:
        out.update(prefix_bytes=0, prefix=None, prefix_omitted="redaction unavailable")
        return out
    # Escapes and redaction markers can lengthen the text; the stored prefix stays within PREFIX_BYTES.
    out["prefix"] = text.encode("utf-8", errors="backslashreplace")[:PREFIX_BYTES].decode("utf-8", errors="ignore")
    return out


MATCH_SITES = ("message_calls", "remaining_calls")
MATCH_CONDITIONS = ("call_sequence_differs", "result_not_acknowledged", "invalid_rpc_id_type", "tool_not_advertised",
                    "no_equal_call")
MATCH_COUNTS = ("mcp_call", "sequence", "delivered_unacknowledged", "candidates", "same_name_candidates")
MATCH_FLAGS = ("name_advertised", "keep_last_in_request", "matches_dropped_call", "same_name_equal_after_escape_decoding",
               "runtime_output_pending")


def match_failure(detail):
    """The client's record of a rejected MCP invocation (client._match), reduced to allowlisted counts and booleans.

    A value of an unexpected type is kept as its JSON type in angle brackets, never as the value.
    """
    detail = mapping(detail)
    out = {key: detail.get(key) if detail.get(key) in allowed else "<other>"
           for key, allowed in (("call_site", MATCH_SITES), ("condition", MATCH_CONDITIONS))}
    out.update({key: detail.get(key) if type(detail.get(key)) is int else f"<{kind_of(detail.get(key))}>"
                for key in MATCH_COUNTS})
    out.update({key: detail.get(key) is True for key in MATCH_FLAGS})
    return out


def payload(error, session_id, model, cli_version, audit, stream_log, declared=(), rejected_line=None):
    entries = list(audit)[-MAX_AUDIT:]
    record = {"schema_version": SCHEMA_VERSION, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "session_id": session_label(session_id), "model": label(model, 80), "cli_version": label(cli_version, 40),
              "error": {"class": type(error).__name__, "message": str(error)[:500]},
              "audit": [sanitize(e) for e in entries], "audit_truncated": len(audit) - len(entries),
              "stream": stream_log.report()}
    sides = getattr(error, "snapshot_sides", None)
    if sides is not None:
        try:
            record["snapshot_mismatch"] = snapshot_mismatch(*sides, declared=declared)
        except Exception as exc:  # the classification must never cost the rest of the record
            record["snapshot_mismatch"] = {"classification_failed": type(exc).__name__}
    failure = getattr(error, "match_failure", None)
    if failure is not None:
        record["mcp_match_failure"] = match_failure(failure)
    if rejected_line is not None:
        record["rejected_line"] = rejected(rejected_line)
    return record


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
