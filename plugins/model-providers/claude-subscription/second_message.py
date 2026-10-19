"""What to do when the runtime streams a second assistant message after one has completed.

One pure, deterministic decision over facts the client has already validated. Each
message is a mapping with `id`, `model`, `stop` (stop_reason), `text` (visible text)
and `calls` (tool calls as `id`, `name`, `arguments`). The evidence between them:

- `answered`: tool_use ids the runtime itself answered with a tool_result (a `user`
  event) after the first message's tool calls and before the second message began;
- `requested`: whether the CLI asked Hermes, over MCP, for one of the first message's
  calls before the second message began;
- `forwarded`: whether any of the first message already reached Hermes.

Rows, first match wins; anything else is FAIL, and the caller persists the stream audit:

  keep_first/replay       first complete (end_turn/tool_use), second identical in stop,
                          text and tool-call identity, same model, nothing answered.
  append/continuation     first cut off (max_tokens, so it has no calls), second
                          continues it (text extends it or is new text), same model,
                          new id, nothing answered.
  keep_last/internal_step first stopped for tool_use, the runtime answered exactly its
                          calls without Hermes (none was requested over MCP, nothing of
                          the first was forwarded), second is a new id on the same model
                          with only new tool-call ids. Hermes never ran the first
                          message's calls; the second is the reply to their results.
                          The client keeps the first's visible text ahead of the
                          second's and drops only the calls the runtime answered.
"""
from .stream_audit import relation

APPEND, KEEP_FIRST, KEEP_LAST, FAIL = "append", "keep_first", "keep_last", "fail"
COMPLETE = ("end_turn", "tool_use")


def identity(calls):
    return [(c["id"], c["name"], c["arguments"]) for c in calls]


def decide(first, second, *, answered=(), requested=False, forwarded=False):
    """Return (outcome, row). Row names are identifiers, recorded in the client audit."""
    answered = set(answered)
    first_ids = {c["id"] for c in first["calls"]}
    if first["model"] != second["model"]:
        return FAIL, "model_changed"
    if first["stop"] not in COMPLETE + ("max_tokens",) or second["stop"] not in COMPLETE + ("max_tokens",):
        return FAIL, "unknown_stop"
    if (first["stop"] in COMPLETE and second["stop"] == first["stop"] and second["text"] == first["text"]
            and identity(second["calls"]) == identity(first["calls"])):
        return (KEEP_FIRST, "replay") if not answered else (FAIL, "replay_after_internal_step")
    if first["id"] == second["id"]:
        return FAIL, "same_id_different_content"
    if first["stop"] == "max_tokens":
        if answered:
            return FAIL, "cut_off_with_tool_results"
        if relation(first["text"], second["text"]) in ("extends_previous", "disjoint", "previous_empty"):
            return APPEND, "continuation"
        return FAIL, "cut_off_without_continuation"
    if first["stop"] != "tool_use":
        return FAIL, "complete_not_replay"
    if not answered:
        return FAIL, "tool_use_without_internal_step"
    if answered != first_ids:
        return FAIL, "internal_step_partial"
    if requested:
        return FAIL, "internal_step_after_mcp_request"
    if forwarded:
        return FAIL, "internal_step_after_forwarding"
    if first_ids & {c["id"] for c in second["calls"]}:
        return FAIL, "internal_step_reused_call"
    return KEEP_LAST, "internal_step"


def appended_text(first_text, second_text):
    """The part of a continuation that is new: after the repeated prefix, or all of it."""
    return second_text[len(first_text):] if second_text.startswith(first_text) else second_text
