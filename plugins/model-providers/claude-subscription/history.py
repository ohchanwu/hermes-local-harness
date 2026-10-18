"""In-memory transcript validation and canonicalization."""
import base64
import binascii
import copy
import json
import re

from .errors import ProviderError


IMAGE_BOUND = 5 * 1024 * 1024  # decoded bytes per image, the API's limit
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
        self.pending_ids = []  # the last assistant message's tool calls, each owed one result
        self.dropped = []  # calls Hermes removed from that message's batch (duplicates, over-limit delegations)
        self.restored = None  # prior messages a new client must replay, until its first send
        self.skipped = 0  # leading tool-call rows of that transcript left out of the replay

    def accept(self, messages):
        """Validate the next request's transcript; return its new messages (the tail)."""
        if not isinstance(messages, list) or not messages:
            raise ProviderError("messages must be a nonempty transcript")
        canonical = [self.canonical(m) for m in messages]
        self.restored = None
        self.skipped = 0
        self.dropped = []
        tail = canonical[-1:]  # a fresh start or a rebuild continues from the last message
        if not self.messages:
            roles = [m["role"] for m in canonical]
            if roles not in (["user"], ["system", "user"]):
                self.restored, self.skipped = self.rebuild(canonical)
        elif self.pending_ids:
            # Hermes may drop calls from the batch (duplicates, delegations over its limit)
            # before recording the assistant message; it answers only the calls it kept.
            count, mine = len(self.messages), self.messages[-1]
            kept = canonical[count - 1] if len(canonical) >= count else {}
            if (canonical[:count - 1] != self.messages[:count - 1] or kept.get("role") != "assistant"
                    or kept.get("content") != mine["content"] or not kept.get("tool_calls")
                    or not self.subsequence(kept["tool_calls"], mine["tool_calls"])):
                raise ProviderError("history prefix changed, missing, replayed or compacted; use a new client")
            tail = canonical[count:]
            if (any(m["role"] != "tool" for m in tail)
                    or sorted(m["tool_call_id"] for m in tail) != sorted(c["id"] for c in kept["tool_calls"])):
                raise ProviderError("exactly one matching result per tool call is required before continuation")
            dropped = [c for c in mine["tool_calls"] if c not in kept["tool_calls"]]
            self.dropped = dropped
        else:
            if len(canonical) != len(self.messages) + 1 or canonical[:-1] != self.messages:
                raise ProviderError("history prefix changed, missing, replayed or compacted; use a new client")
            tail = canonical[-1:]
            if tail[0]["role"] != "user":
                raise ProviderError("expected one new user turn, not a stale tool result")
        self.messages = canonical
        self.pending_ids = []
        return copy.deepcopy(tail)

    @staticmethod
    def subsequence(kept, calls):
        """Whether kept is calls with some entries removed, order preserved."""
        remaining = iter(calls)
        return all(any(call == candidate for candidate in remaining) for call in kept)

    @staticmethod
    def rebuild(canonical):
        """Validate an existing transcript handed to a new client.

        Return what to replay and how many leading rows were left out of it.
        """
        body = canonical[1:] if canonical[0]["role"] == "system" else canonical
        if not body or body[-1]["role"] not in ("user", "tool"):
            raise ProviderError("a transcript must start with a user message and end with a user or tool message")
        # Hermes' context compaction can keep one or more complete tool-call groups
        # (an assistant message with calls, then exactly one result per call) ahead of
        # the user message that carries its summary. The summary covers them, so they
        # are left out of the replay; History still tracks the transcript as sent.
        skipped = 0
        while skipped < len(body) and body[skipped]["role"] != "user":
            head = body[skipped]
            if head["role"] != "assistant" or not head.get("tool_calls"):
                raise ProviderError("a transcript must start with a user message and end with a user or tool message")
            end = skipped + 1
            while end < len(body) and body[end]["role"] == "tool":
                end += 1
            if (sorted(m["tool_call_id"] for m in body[skipped + 1:end])
                    != sorted(call["id"] for call in head["tool_calls"])):
                raise ProviderError("a leading tool call group needs exactly one result per call")
            skipped = end
        body = body[skipped:]
        if not body:
            raise ProviderError("leading tool call groups must be followed by a user message")
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
            # Final results must answer every call of the latest assistant message, and nothing else.
            latest = next(i for i in range(len(body) - 1, -1, -1) if body[i]["role"] != "tool")
            ids = sorted(call["id"] for call in body[latest].get("tool_calls", []))
            if body[latest]["role"] != "assistant" or sorted(m["tool_call_id"] for m in body[latest + 1:]) != ids:
                raise ProviderError("final tool results must answer every call of the latest assistant message")
        return copy.deepcopy(body[:-1]), skipped

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
            # Several calls per message: Hermes returns one result for each.
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
                    size = len(base64.b64decode("".join(match.group(2).split()), validate=True))
                except (binascii.Error, ValueError):
                    raise ProviderError("invalid base64 image data") from None
                if size > IMAGE_BOUND:
                    raise ProviderError("images are limited to 5 MB each")
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
        self.pending_ids = [call["id"] for call in message.get("tool_calls") or []]
