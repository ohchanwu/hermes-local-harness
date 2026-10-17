"""In-memory transcript validation and canonicalization."""
import copy
import json

from .errors import ProviderError


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
        calls = set()
        for message in body:
            calls.update(call["id"] for call in message.get("tool_calls", []))
            if message["role"] == "tool" and message["tool_call_id"] not in calls:
                raise ProviderError("tool result for a call not in the transcript")
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
        if not isinstance(text, str):
            raise ProviderError("only plain text message content is supported; no images or multipart content")
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
