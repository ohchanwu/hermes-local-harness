"""Parser for one streamed runtime assistant message."""
import json

from .errors import ProviderError


class Message:
    """One real streamed assistant message, not a canned completion rechunked.

    feed() returns this message's deltas and also keeps them in `deltas`; the client
    holds them until the message is final, so nothing of it reaches Hermes earlier.
    """
    def __init__(self, served):
        self.served = served
        self.id = None
        self.model = None
        self.blocks = {}
        self.text = ""
        self.stop = None
        self.done = False
        self.snapshot = []  # content blocks from the runtime's per-block assistant snapshots
        self.usage = {}
        self.calls = []  # every tool call in this message, in order; Hermes runs them as one batch
        self.deltas = []  # text deltas in order, held by the client until the message is final
        self.answered = []  # tool_use ids the runtime itself answered (user tool_result events)
        self.answered_errors = 0  # how many of those it marked is_error
        self.stream_id = None       # the first message id, kept for every chunk across restarts
        self.interrupted = None     # error type of a mid-stream API failure
        self.restarts = 0

    def facts(self):
        """The fields second_message.decide() compares."""
        return {"id": self.id, "model": self.model, "stop": self.stop, "text": self.text,
                "calls": [{"id": c["id"], "name": c["name"], "arguments": c["arguments"]} for c in self.calls]}

    def observe_user(self, obj):
        """Record tool results the runtime fed back itself while this message was current."""
        if self.id is None:
            return  # before any message: results Hermes delivered for an earlier turn
        content = obj.get("message", {}).get("content") if isinstance(obj.get("message"), dict) else None
        for item in content if isinstance(content, list) else ():
            if isinstance(item, dict) and item.get("type") == "tool_result" and isinstance(item.get("tool_use_id"), str):
                self.answered.append(item["tool_use_id"])
                self.answered_errors += item.get("is_error") is True

    def feed(self, obj):
        deltas = self._feed(obj)
        self.deltas.extend(d for d in deltas if "content" in d)
        return deltas

    def _feed(self, obj):
        kind = obj.get("type")
        if kind == "assistant":
            msg = obj.get("message", {})
            # The CLI sends one snapshot per content block, each carrying only that block.
            if obj.get("error") or msg.get("model") not in self.served:
                # Short runtime codes only (e.g. rate_limit, invalid_request), never message text.
                error = obj.get("error")
                code = (error if isinstance(error, str) else "unrecognized error" if error else "unexpected model")[:80]
                raise ProviderError(f"runtime assistant error: {code} (model {str(msg.get('model'))[:80]})")
            if self.id is None or self.done or msg.get("id") != self.id or not isinstance(msg.get("content"), list):
                raise ProviderError("assistant snapshot outside its streamed message")
            self.snapshot.extend(msg["content"])
            self.usage.update(msg.get("usage") or {})
            return []
        if kind != "stream_event":
            return []
        ev = obj.get("event", {})
        event = ev.get("type")
        if event == "ping":
            return []
        if event == "message_start":
            msg = ev.get("message", {})
            if msg.get("model") not in self.served or not isinstance(msg.get("id"), str) or not msg["id"]:
                raise ProviderError("unexpected streamed message model or id")
            restart = self.id is not None
            if restart:
                # The CLI retries a failed API call itself and streams the reply again from the start.
                # Nothing of an unfinished message has reached Hermes, so the partial one is dropped.
                if self.done:
                    raise ProviderError("duplicate streamed message")  # the client decides second messages
                restarts, stream_id = self.restarts + 1, self.stream_id
                self.__init__(self.served)
                self.restarts, self.stream_id = restarts, stream_id
            self.id = msg["id"]
            self.model = msg["model"]
            self.stream_id = self.stream_id or self.id
            self.usage.update(msg.get("usage") or {})
            return [] if restart else [{"role": "assistant"}]
        if not self.id or self.done or self.interrupted:
            raise ProviderError("event outside message boundary")
        if event == "error":
            # A mid-stream API failure; only a restarted message may follow.
            error = ev.get("error")
            self.interrupted = str(error.get("type") if isinstance(error, dict) else "unknown")[:40] or "unknown"
            return []
        index = ev.get("index")
        if event == "content_block_start":
            block = ev.get("content_block", {})
            if type(index) is not int or index in self.blocks:
                raise ProviderError("invalid/duplicate content block")
            self.blocks[index] = {"kind": block.get("type"), "closed": False}
            if block.get("type") == "tool_use":
                if (not isinstance(block.get("id"), str) or not block["id"] or not isinstance(block.get("name"), str)
                        or block["id"] in {c["id"] for c in self.calls}):
                    raise ProviderError("duplicate or invalid runtime tool call")
                self.blocks[index]["call"] = len(self.calls)
                self.calls.append({"id": block["id"], "name": block["name"], "arguments": block.get("input", {}), "fragments": []})
            elif block.get("type") not in ("text", "thinking", "redacted_thinking"):
                raise ProviderError("unsupported runtime content block")
            if block.get("type") == "text" and block.get("text"):
                self.text += block["text"]
                return [{"content": block["text"]}]
        elif event == "content_block_delta":
            block = self.blocks.get(index)
            if block is None or block["closed"]:
                raise ProviderError("delta for missing/closed block")
            delta = ev.get("delta", {})
            if block["kind"] == "tool_use":
                if delta.get("type") != "input_json_delta" or not isinstance(delta.get("partial_json"), str):
                    raise ProviderError("invalid tool argument delta")
                self.calls[block["call"]]["fragments"].append(delta["partial_json"])
                return []  # serial validation fence: no tool escapes a partial message
            if block["kind"] == "text":
                if delta.get("type") != "text_delta" or not isinstance(delta.get("text"), str):
                    raise ProviderError("invalid text delta")
                self.text += delta["text"]
                return [{"content": delta["text"]}]
            if delta.get("type") not in ("thinking_delta", "signature_delta"):
                raise ProviderError("unsupported thinking delta")
        elif event == "content_block_stop":
            block = self.blocks.get(index)
            if block is None or block["closed"]:
                raise ProviderError("duplicate/missing block stop")
            block["closed"] = True
            call = self.calls[block["call"]] if block["kind"] == "tool_use" else None
            if call is not None and call["fragments"]:
                call["arguments"] = json.loads("".join(call["fragments"]))
                if not isinstance(call["arguments"], dict):
                    raise ProviderError("tool arguments must be an object")
        elif event == "message_delta":
            self.stop = ev.get("delta", {}).get("stop_reason")
            self.usage.update(ev.get("usage") or {})
        elif event == "message_stop":
            if any(not b["closed"] for b in self.blocks.values()) or not self.snapshot:
                raise ProviderError("incomplete assistant message")
            if self.stop not in ("end_turn", "max_tokens", "tool_use") or bool(self.calls) != (self.stop == "tool_use"):
                raise ProviderError("runtime refusal or unsupported stop reason")
            if [b.get("type") for b in self.snapshot] != [b["kind"] for _, b in sorted(self.blocks.items())]:
                raise ProviderError("stream/snapshot block mismatch")
            text = "".join(b.get("text", "") for b in self.snapshot if b.get("type") == "text")
            if text != self.text:
                raise ProviderError("stream/snapshot content mismatch")
            tools = [b for b in self.snapshot if b.get("type") == "tool_use"]
            expected = [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]} for c in self.calls]
            if [{k: b.get(k) for k in ("type", "id", "name", "input")} for b in tools] != expected:
                raise ProviderError("stream/snapshot tool identity or arguments mismatch")
            self.done = True
        else:
            raise ProviderError(f"unknown assistant stream event: {str(event)[:40]}")
        return []
