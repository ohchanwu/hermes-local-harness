"""In-memory transcript validation and canonicalization."""
import base64
import binascii
import copy
import json
import re

from .errors import ProviderError


DATA_URL = re.compile(r"data:(image/(?:png|jpeg|gif|webp));base64,([A-Za-z0-9+/=\s]+)")


def content_blocks(content):
    """CLI stream-json user content: a plain string, or text and base64 image blocks."""
    if isinstance(content, str):
        return content
    blocks = []
    for part in content:
        if part["type"] == "text":
            blocks.append({"type": "text", "text": part["text"]})
        else:
            media_type, data = DATA_URL.fullmatch(part["image_url"]["url"]).groups()
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                       "data": "".join(data.split())}})
    return blocks


class History:
    """In-memory transcript owned by exactly one synchronous client."""
    def __init__(self):
        self.messages = []
        self.pending_id = None
        self.restored = None  # prior messages a new client must replay, until its first send

    def accept(self, messages):
        if not isinstance(messages, list) or not messages:
            raise ProviderError("messages must be a nonempty transcript")
        canonical = [self.canonical(m) for m in messages]
        self.restored = None
        if not self.messages:
            roles = [m["role"] for m in canonical]
            if roles not in (["user"], ["system", "user"]):
                self.restored = self.rebuild(canonical)
        else:
            if len(canonical) != len(self.messages) + 1 or canonical[:-1] != self.messages:
                raise ProviderError("history prefix changed, missing, replayed or compacted; use a new client")
            tail = canonical[-1]
            if self.pending_id:
                if tail["role"] != "tool" or tail.get("tool_call_id") != self.pending_id:
                    raise ProviderError("one matching tool result is required before continuation")
            elif tail["role"] != "user":
                raise ProviderError("expected one new user turn, not a stale tool result")
        self.messages = canonical
        self.pending_id = None
        return copy.deepcopy(canonical[-1])

    @staticmethod
    def rebuild(canonical):
        """Validate an existing transcript handed to a new client; return what to replay."""
        body = canonical[1:] if canonical[0]["role"] == "system" else canonical
        if not body or body[0]["role"] != "user" or body[-1]["role"] not in ("user", "tool"):
            raise ProviderError("a transcript must start with a user message and end with a user or tool message")
        # Track outstanding calls, as Hermes does: some models reuse one id for
        # every call, so a later call re-arms its id for one more result.
        outstanding = set()
        for message in body:
            outstanding.update(call["id"] for call in message.get("tool_calls", []))
            if message["role"] == "tool":
                if message["tool_call_id"] not in outstanding:
                    raise ProviderError("tool result without an outstanding call")
                outstanding.discard(message["tool_call_id"])
        if body[-1]["role"] == "tool":
            # A final result must answer the latest assistant message, with only its results in between.
            latest = next(i for i in range(len(body) - 1, -1, -1) if body[i]["role"] != "tool")
            ids = {call["id"] for call in body[latest].get("tool_calls", [])}
            if body[latest]["role"] != "assistant" or body[-1]["tool_call_id"] not in ids:
                raise ProviderError("a final tool result must answer the latest assistant tool call")
        return copy.deepcopy(body[:-1])

    @staticmethod
    def canonical(message):
        if not isinstance(message, dict):
            raise ProviderError("message must be an object")
        role = message.get("role")
        allowed = {"role", "content"}
        if role == "assistant":
            # Private reasoning cannot carry across sessions or providers; it is dropped.
            allowed |= {"tool_calls", "reasoning_content", "reasoning", "reasoning_details"}
        elif role == "tool":
            allowed |= {"tool_call_id"}
        elif role not in ("system", "user"):
            raise ProviderError("unsupported message role")
        if set(message) - allowed:
            raise ProviderError("unsupported message fields")
        text = message.get("content")
        if text is None and role == "assistant":
            text = ""
        if role == "user" and isinstance(text, list):
            text = History.canonical_parts(text)
        elif not isinstance(text, str):
            raise ProviderError("only plain text content, or user text and data-URL images, are supported")
        out: dict = {"role": role, "content": text}
        if role == "tool":
            if not isinstance(message.get("tool_call_id"), str) or not message["tool_call_id"]:
                raise ProviderError("tool result requires its original id")
            out["tool_call_id"] = message["tool_call_id"]
        calls = message.get("tool_calls")
        if calls:
            # Several calls may appear in replayed history; the live session itself
            # still produces and continues exactly one at a time.
            if not isinstance(calls, list):
                raise ProviderError("invalid tool calls")
            out["tool_calls"] = [History.canonical_call(call) for call in calls]
        return out

    @staticmethod
    def canonical_parts(parts):
        """User text and base64 data-URL images; remote URLs and other part types are rejected."""
        out = []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                out.append({"type": "text", "text": part["text"]})
            elif isinstance(part, dict) and part.get("type") == "image_url" and isinstance(part.get("image_url"), dict):
                url = part["image_url"].get("url")
                match = DATA_URL.fullmatch(url) if isinstance(url, str) else None
                if match is None:
                    raise ProviderError("images must be base64 data URLs of PNG, JPEG, GIF or WebP")
                try:
                    base64.b64decode(match.group(2), validate=True)
                except (binascii.Error, ValueError):
                    raise ProviderError("invalid base64 image data") from None
                out.append({"type": "image_url", "image_url": {"url": url}})
            else:
                raise ProviderError("unsupported user content part")
        if not out:
            raise ProviderError("empty user content")
        return out

    @staticmethod
    def canonical_call(call):
        if not isinstance(call, dict) or set(call) != {"id", "type", "function"} or call["type"] != "function":
            raise ProviderError("invalid tool call")
        fn = call["function"]
        if not isinstance(fn, dict) or set(fn) != {"name", "arguments"}:
            raise ProviderError("invalid tool function")
        if not isinstance(call["id"], str) or not call["id"] or not isinstance(fn["name"], str):
            raise ProviderError("invalid tool identity")
        try:
            args = json.loads(fn["arguments"])
        except (ValueError, TypeError):
            raise ProviderError("invalid JSON tool arguments") from None
        if not isinstance(args, dict):
            raise ProviderError("tool arguments must be an object")
        return {"id": call["id"], "type": "function", "function": {
            "name": fn["name"], "arguments": json.dumps(args, sort_keys=True, separators=(",", ":"))}}

    def assistant(self, message):
        self.messages.append(self.canonical(message))
        calls = message.get("tool_calls") or []
        self.pending_id = calls[0]["id"] if calls else None
