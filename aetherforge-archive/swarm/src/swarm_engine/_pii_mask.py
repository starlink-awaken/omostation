"""PII masking utilities extracted from intent_digestor.py (ARCH-003 SRP refactor)."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-+]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<!\w)(\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}")
_NAME_RE = re.compile(
    r"(?<![a-zA-Z])(?:(?:Dr|Mr|Mrs|Ms|Miss|Prof|Prof\.)[\s]+)?"
    r"(?:[A-ZÄÖÜÉÀÈÌ][a-zäöüéàèì]+[\s]+){1,3}[A-ZÄÖÜÉÀÈÌ][a-zäöüéàèì]+",
    re.UNICODE,
)
_ADDRESS_RE = re.compile(
    r"\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|court|ct|road)[\s,]+[\w\s]+",
    re.IGNORECASE,
)


def mask_pii(text: str) -> str:
    """Redact PII from free-form text before logging."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    text = _PHONE_RE.sub("[PHONE_REDACTED]", text)
    text = _NAME_RE.sub("[NAME_REDACTED]", text)
    text = _ADDRESS_RE.sub("[ADDRESS_REDACTED]", text)
    return text
