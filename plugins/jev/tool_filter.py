"""Part B of the jev plugin: shorten large tool results with Jev.

Called by the ``transform_tool_result`` hook wrapper in ``__init__.py`` as

    transform(tool_name=..., args=..., result=..., session_id=..., profile=...,
              settings=..., ask=..., log=..., cache_dir=...)

and returns the replacement result string, or ``None`` when the result stays
unchanged. It never raises: every exception is caught and logged with its class
name in ``error_class``.

Result formats (installed Hermes checkout 9cf7960f27; each is a JSON object
serialized with ``json.dumps(..., ensure_ascii=False)``):
  terminal      field ``output`` (tools/terminal_tool_result.py, finalize_foreground_result)
  execute_code  field ``output`` (tools/code_execution_tool.py, _remote_result and the local path)
  browser_exec  field ``output`` (tools/browser_use_cli.py, browser_exec)
  search_files  field ``matches_text``, present when there are at least five
                matches (tools/file_operations_common.py, SearchResult.to_dict)
Any other shape, including a non-string result, is an unrecognised format.

Only the text field is changed. The replacement is done on the serialized
string itself, so every other field keeps its exact bytes and its position.

Log records (stream ``tool_results``) hold identifiers, sizes, probabilities,
timings and token counts only, never tool output or tool arguments. Every
result that Jev answered for has ``chunk_probabilities``: the probability of
each chunk, in chunk order.
"""
import datetime
import json
import os
import re
import secrets

TEXT_FIELDS = {
    "terminal": "output",
    "execute_code": "output",
    "browser_exec": "output",
    "search_files": "matches_text",
}

NEVER_FILTERED = ("read_file",)

QUESTION_TEXT = (
    "Does chunk {n} of the tool output in `state` contain an error, a failure, a "
    "warning, a result value, or other information needed to continue the work "
    "the command was run for?"
)

REMOVAL_LINE = ("[jev: {lines} lines removed here; the full output is saved in {path}; "
                "read it with read_file]")

DEFAULTS = {
    "tools": ["terminal", "execute_code", "search_files", "browser_exec"],
    "min_chars": 2000,
    "max_chars": 100000,
    "chunk_lines": 10,
    "chunk_chars": 500,
    "args_chars": 2000,
    "keep_threshold": 0.6,
    "max_kept_ratio": 0.9,
}

RECORD_FIELDS = (
    "ts", "profile", "event", "session_id", "tool", "chars_before", "chars_after",
    "chunks_kept", "chunks_total", "jev_latency_ms", "jev_input_tokens", "action",
    "reason", "error_class", "saved_file", "chunk_probabilities",
)


class UnexpectedAnswer(Exception):
    """Jev returned no usable probability for a chunk question."""


class InvalidSetting(Exception):
    """A tool_results setting has a value the filter cannot use."""


def _setting(settings, key):
    if isinstance(settings, dict) and key in settings:
        return settings[key]
    return DEFAULTS[key]


def _int_setting(settings, key, minimum):
    """Return the setting as an int of at least ``minimum``, else raise InvalidSetting.

    Booleans, floats, strings and other types are rejected rather than converted,
    so that a value such as 0.5 cannot become 0.
    """
    value = _setting(settings, key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidSetting(key)
    return value


def _now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _record(profile, session_id, tool_name, **fields):
    record: dict = {key: None for key in RECORD_FIELDS}
    record.update(ts=_now_iso(), profile=profile, session_id=session_id or None,
                  tool=tool_name, event="filter")
    record.update(fields)
    return record


def _write_log(log, record):
    """Write one record; a failing log function never breaks the tool result."""
    try:
        log("tool_results", record)
    except Exception:
        pass


def _is_inside(path, directory):
    try:
        path = os.path.realpath(os.path.abspath(path))
        directory = os.path.realpath(os.path.abspath(directory))
        return os.path.commonpath([path, directory]) == directory and path != directory
    except (TypeError, ValueError):
        return False


def _field_text(result, field):
    """Return the string value of the field in the JSON object ``result``, or None."""
    if not isinstance(result, str):
        return None
    try:
        parsed = json.loads(result)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    text = parsed.get(field)
    return text if isinstance(text, str) else None


def _encoded_literal(result, text):
    """Return (encoded, ensure_ascii) where ``encoded`` occurs exactly once in ``result``.

    ``encoded`` is the JSON string literal of ``text``. Returns None when neither
    serialized form occurs exactly once.
    """
    for ensure_ascii in (False, True):
        encoded = json.dumps(text, ensure_ascii=ensure_ascii)
        if result.count(encoded) == 1:
            return encoded, ensure_ascii
    return None


def _split_units(text, chunk_chars):
    """Split text into line units; a line longer than chunk_chars is cut into pieces."""
    if isinstance(chunk_chars, bool) or not isinstance(chunk_chars, int) or chunk_chars < 1:
        # A value below 1 would make the loop below run without end.
        raise InvalidSetting("chunk_chars")
    units = []
    for line in text.splitlines(keepends=True):
        while len(line) > chunk_chars:
            units.append(line[:chunk_chars])
            line = line[chunk_chars:]
        if line:
            units.append(line)
    return units


def _make_chunks(text, chunk_lines, chunk_chars):
    """Chunks of at most chunk_lines units and at most chunk_chars characters.

    ``"".join(chunks) == text`` always holds.
    """
    if isinstance(chunk_lines, bool) or not isinstance(chunk_lines, int) or chunk_lines < 1:
        raise InvalidSetting("chunk_lines")
    chunks, current, size = [], [], 0
    for unit in _split_units(text, chunk_chars):
        if current and (len(current) >= chunk_lines or size + len(unit) > chunk_chars):
            chunks.append("".join(current))
            current, size = [], 0
        current.append(unit)
        size += len(unit)
    if current:
        chunks.append("".join(current))
    return chunks


def _args_text(args, limit):
    try:
        text = json.dumps(args, ensure_ascii=False, default=str, sort_keys=True)
    except (TypeError, ValueError):
        text = str(args)
    return text[:limit]


def _probabilities(answers, count):
    if not isinstance(answers, dict):
        raise UnexpectedAnswer("answers is not an object")
    probabilities = []
    for n in range(1, count + 1):
        answer = answers.get(f"chunk_{n}")
        value = answer.get("noul") if isinstance(answer, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise UnexpectedAnswer(f"no probability for chunk {n}")
        probabilities.append(float(value))
    return probabilities


def _save_original(cache_dir, tool_name, text):
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)
    os.chmod(cache_dir, 0o700)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_tool = re.sub(r"[^A-Za-z0-9_-]", "_", tool_name)
    path = os.path.join(os.path.abspath(cache_dir), f"{stamp}-{safe_tool}-{secrets.token_hex(4)}.txt")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    os.chmod(path, 0o600)
    return path


def _remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _rebuild(chunks, keep, saved_path):
    parts = []
    removed = []
    for chunk, kept in zip(chunks, keep):
        if kept:
            if removed:
                _append_removal(parts, removed, saved_path)
                removed = []
            parts.append(chunk)
        else:
            removed.append(chunk)
    if removed:
        _append_removal(parts, removed, saved_path)
    return "".join(parts)


def _append_removal(parts, removed, saved_path):
    lines = len("".join(removed).splitlines())
    prefix = "" if not parts or parts[-1].endswith("\n") else "\n"
    parts.append(prefix + REMOVAL_LINE.format(lines=lines, path=saved_path) + "\n")


def _filter(*, tool_name, args, result, session_id, profile, settings, ask, log, cache_dir):
    if isinstance(settings, dict) and settings.get("enabled") is False:
        return None
    if tool_name in NEVER_FILTERED:
        path = args.get("path") if isinstance(args, dict) else None
        if isinstance(path, str) and path and _is_inside(path, cache_dir):
            _write_log(log, _record(profile, session_id, tool_name, event="saved_read",
                                    saved_file=os.path.realpath(os.path.abspath(path))))
        return None
    if not isinstance(tool_name, str) or tool_name.startswith("kanban_"):
        return None
    if tool_name not in _setting(settings, "tools") or tool_name not in TEXT_FIELDS:
        return None

    text = _field_text(result, TEXT_FIELDS[tool_name])
    if text is None:
        _write_log(log, _record(profile, session_id, tool_name, action="skipped",
                                reason="unrecognised_format"))
        return None
    before = len(text)
    if before <= _setting(settings, "min_chars"):
        _write_log(log, _record(profile, session_id, tool_name, action="skipped",
                                reason="below_min_chars", chars_before=before, chars_after=before))
        return None
    if before > _setting(settings, "max_chars"):
        _write_log(log, _record(profile, session_id, tool_name, action="skipped",
                                reason="above_max_chars", chars_before=before, chars_after=before))
        return None
    located = _encoded_literal(result, text)
    if located is None:
        _write_log(log, _record(profile, session_id, tool_name, action="skipped",
                                reason="unrecognised_format", chars_before=before,
                                chars_after=before))
        return None
    encoded, ensure_ascii = located
    try:
        chunk_lines = _int_setting(settings, "chunk_lines", 1)
        chunk_chars = _int_setting(settings, "chunk_chars", 1)
        args_chars = _int_setting(settings, "args_chars", 0)
    except InvalidSetting as exc:
        # Checked before the original is saved, so no file is left in cache_dir.
        _write_log(log, _record(profile, session_id, tool_name, action="unchanged",
                                reason=f"invalid_setting_{exc.args[0]}",
                                error_class="InvalidSetting", chars_before=before,
                                chars_after=before))
        return None

    saved_path = _save_original(cache_dir, tool_name, text)
    record = _record(profile, session_id, tool_name, chars_before=before, chars_after=before,
                     saved_file=saved_path)
    try:
        chunks = _make_chunks(text, chunk_lines, chunk_chars)
        record["chunks_total"] = len(chunks)
        if len(chunks) < 3:
            # First and last chunks are always kept, so nothing could be removed.
            record.update(action="unchanged", reason="too_few_chunks", chunks_kept=len(chunks),
                          saved_file=None)
            _remove_quietly(saved_path)
            _write_log(log, record)
            return None
        state = {
            "tool": tool_name,
            "arguments": _args_text(args, args_chars),
            "chunks": {str(n): chunk for n, chunk in enumerate(chunks, start=1)},
        }
        questions = {
            f"chunk_{n}": {"type": "noul", "instructions": QUESTION_TEXT.format(n=n)}
            for n in range(1, len(chunks) + 1)
        }
        answer = ask(state, questions)
        record["jev_latency_ms"] = getattr(answer, "latency_ms", None)
        record["jev_input_tokens"] = getattr(answer, "input_tokens", None)
        probabilities = _probabilities(getattr(answer, "answers", None), len(chunks))
        record["chunk_probabilities"] = probabilities
        threshold = float(_setting(settings, "keep_threshold"))
        last = len(chunks) - 1
        keep = [i in (0, last) or p >= threshold for i, p in enumerate(probabilities)]
        record["chunks_kept"] = sum(keep)
        new_text = _rebuild(chunks, keep, saved_path)
        if all(keep) or len(new_text) >= float(_setting(settings, "max_kept_ratio")) * before:
            record.update(action="unchanged", reason="kept_ratio_at_or_above_max", saved_file=None)
            _remove_quietly(saved_path)
            _write_log(log, record)
            return None
        replacement = json.dumps(new_text, ensure_ascii=ensure_ascii)
        new_result = result.replace(encoded, replacement, 1)
        record.update(action="filtered", reason=None, chars_after=len(new_text))
        _write_log(log, record)
        return new_result
    except Exception as exc:
        record.update(action="unchanged", reason="jev_error",
                      error_class=getattr(exc, "error_class", None) or type(exc).__name__,
                      saved_file=None)
        _remove_quietly(saved_path)
        _write_log(log, record)
        return None


def transform(*, tool_name, args, result, session_id, profile, settings, ask, log, cache_dir):
    """Return the filtered result string, or None to leave the result unchanged."""
    try:
        return _filter(tool_name=tool_name, args=args, result=result, session_id=session_id,
                       profile=profile, settings=settings, ask=ask, log=log, cache_dir=cache_dir)
    except Exception as exc:
        _write_log(log, _record(profile, session_id if isinstance(session_id, str) else None,
                                tool_name if isinstance(tool_name, str) else None,
                                action="unchanged", reason="internal_error",
                                error_class=type(exc).__name__))
        return None
