"""Render an existing transcript as the first input of a rebuilt session."""
import secrets

NOTE = ("This conversation was restored from a transcript after a restart. "
        "The tool calls shown already ran; do not repeat them unless needed.")


def render_message(message):
    if message["role"] == "tool":
        return [f"[tool result id={message['tool_call_id']}]\n{message['content']}"]
    parts = [f"[{message['role']}]\n{message['content']}"] if message["content"] or not message.get("tool_calls") else []
    for call in message.get("tool_calls", []):
        fn = call["function"]
        parts.append(f"[assistant tool call {fn['name']} id={call['id']}]\n{fn['arguments']}")
    return parts


def render_restored(restored, tail):
    """Return (text, nonce): a nonce-delimited block, so message text cannot close it."""
    nonce = secrets.token_hex(16)
    entries = [part for message in restored for part in render_message(message)]
    if tail["role"] == "tool":
        entries += render_message(tail)
    text = "\n\n".join([f"<restored-transcript-{nonce}>", NOTE, *entries, f"</restored-transcript-{nonce}>"])
    if tail["role"] == "tool":
        return text + "\n\nThe last tool result above is new. Continue the task using it.", nonce
    return text + "\n\nNew message from the user:\n" + tail["content"], nonce
