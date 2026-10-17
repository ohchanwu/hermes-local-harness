"""In-memory transcript validation and canonicalization."""
import copy
import json

from .errors import ProviderError


class History:
    """In-memory transcript owned by exactly one synchronous client."""
    def __init__(self):
        self.messages = []
        self.pending_id = None

    def accept(self, messages):
        if not isinstance(messages, list) or not messages:
            raise ProviderError("messages must be a nonempty transcript")
        canonical = [self.canonical(m) for m in messages]
        if not self.messages:
            roles = [m["role"] for m in canonical]
            if roles not in (["user"], ["system", "user"]):
                raise ProviderError("new clients require a fresh system/user turn; imported history is unsupported")
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
    def canonical(message):
        if not isinstance(message, dict):
            raise ProviderError("message must be an object")
        role = message.get("role")
        allowed = {"role", "content"}
        if role == "assistant":
            allowed |= {"tool_calls", "reasoning_content"}
        elif role == "tool":
            allowed |= {"tool_call_id"}
        elif role not in ("system", "user"):
            raise ProviderError("unsupported message role")
        if set(message) - allowed or message.get("reasoning_content"):
            raise ProviderError("unsupported message fields or imported reasoning")
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
            if not isinstance(calls, list) or len(calls) != 1:
                raise ProviderError("parallel/multiple tool calls are unsupported")
            call = calls[0]
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
            out["tool_calls"] = [{"id": call["id"], "type": "function", "function": {
                "name": fn["name"], "arguments": json.dumps(args, sort_keys=True, separators=(",", ":"))}}]
        return out

    def assistant(self, message):
        self.messages.append(self.canonical(message))
        calls = message.get("tool_calls") or []
        self.pending_id = calls[0]["id"] if calls else None
