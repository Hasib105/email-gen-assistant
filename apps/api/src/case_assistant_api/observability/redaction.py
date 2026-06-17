"""Central log redaction helpers.

The goal is to keep logs useful for operations while making the default path
safe for secrets and common PII. Domain-specific masking still happens before
LLM boundaries; this module protects observability data.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import cast

from structlog.types import EventDict

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?!\d{4}-\d{2}-\d{2}\b)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
SLACK_TOKEN_RE = re.compile(r"\bxox(?:a|b|p|r|s)-[A-Za-z0-9-]{10,}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
GEMINI_KEY_RE = re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b")
BOOKING_LABEL_RE = re.compile(
    r"(?i)\b(booking(?:[_ -]?(?:ref|reference))?\s*[:=#-]?\s*)([A-Z0-9]{5,16})\b"
)

SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "client_secret",
    "email",
    "password",
    "phone",
    "secret",
    "signing_secret",
    "token",
)


def redact_sensitive(value: object) -> object:
    """Return a copy of value with common secrets and PII redacted."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        items = cast("Mapping[object, object]", value)
        return {
            str(key): ("[REDACTED]" if _is_sensitive_key(str(key)) else redact_sensitive(item))
            for key, item in items.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        items = cast("Sequence[object]", value)
        return [redact_sensitive(item) for item in items]
    return value


def redact_event_dict(
    _logger: object,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Structlog processor that redacts each event field before rendering."""
    return {str(key): redact_sensitive(value) for key, value in event_dict.items()}


def _redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("EMAIL_REDACTED", value)
    redacted = PHONE_RE.sub("PHONE_REDACTED", redacted)
    redacted = SLACK_TOKEN_RE.sub("SLACK_TOKEN_REDACTED", redacted)
    redacted = OPENAI_KEY_RE.sub("API_KEY_REDACTED", redacted)
    redacted = GEMINI_KEY_RE.sub("API_KEY_REDACTED", redacted)
    return BOOKING_LABEL_RE.sub(r"\1BOOKING_REF_REDACTED", redacted)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEYS)
