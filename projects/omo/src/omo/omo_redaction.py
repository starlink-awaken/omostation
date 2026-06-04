from __future__ import annotations

import re

SENSITIVE_PAIR_PATTERNS = [
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s\n]+)"),
    re.compile(r"(?i)(secret\s*[=:]\s*)([^\s\n]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*)([^\s\n]+)"),
    re.compile(r"(?i)(api_key\s*[=:]\s*)([^\s\n]+)"),
]


def redact_sensitive_text(text: str) -> str:
    masked = text
    for pattern in SENSITIVE_PAIR_PATTERNS:
        masked = pattern.sub(r"\1***REDACTED***", masked)
    return masked
