"""Client for the TypeSafe System One endpoint (model Jev), standard library only.

``ask(state, questions, *, settings)`` sends one request and returns a
``JevResult``. Every failure (missing key, timeout, HTTP error, connection
error, unexpected response) raises ``JevError`` whose ``error_class`` names
the failure. The API key is read from the process environment at call time;
it is never logged, printed, stored or included in an exception message.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.14.0"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_KEY_ENV = "TYPESAFE_API_KEY"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class JevError(Exception):
    """A failed Jev call. ``error_class`` is a short class name such as ``Timeout``."""

    def __init__(self, error_class: str, status: Optional[int] = None) -> None:
        super().__init__(error_class if status is None else f"{error_class} {status}")
        self.error_class = error_class
        self.status = status


@dataclass
class JevResult:
    answers: Dict[str, Any] = field(default_factory=dict)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: int = 0


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (TimeoutError, socket.timeout))


def _token_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def ask(state: Any, questions: Mapping[str, Any], *, settings: Optional[Mapping[str, Any]] = None) -> JevResult:
    """Send ``state`` and ``questions`` to Jev and return the parsed answers."""
    settings = settings or {}
    key_env = str(settings.get("api_key_env") or DEFAULT_KEY_ENV)
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise JevError("MissingKey")
    endpoint = str(settings.get("endpoint") or DEFAULT_ENDPOINT)
    try:
        timeout = float(settings.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS
    try:
        body = json.dumps({
            "model": str(settings.get("model") or DEFAULT_MODEL),
            "state": state,
            "questions": dict(questions),
        }).encode("utf-8")
    except Exception:
        raise JevError("InvalidRequest") from None
    request = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    del key
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            exc.close()
        except Exception:
            pass
        raise JevError("HTTPError", status) from None
    except Exception as exc:  # URLError, timeout, connection reset, ...
        if _is_timeout(exc):
            raise JevError("Timeout") from None
        raise JevError(type(exc).__name__) from None
    latency_ms = int((time.monotonic() - started) * 1000)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise JevError("UnexpectedResponse")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise JevError("UnexpectedResponse") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise JevError("UnexpectedResponse")
    usage = payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return JevResult(
        answers=payload["answers"],
        input_tokens=_token_count(usage.get("input_tokens")),
        output_tokens=_token_count(usage.get("output_tokens")),
        latency_ms=latency_ms,
    )
