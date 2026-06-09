from __future__ import annotations

import re
from collections import Counter


def check_integrity(text: str) -> dict:
    lowered = text.lower()
    words = re.findall(r"\w+", lowered)
    repeated = Counter(words)
    top_repeat = max(repeated.values(), default=0)
    suspicious_markers = sum(
        1
        for marker in (
            "comprehensive analysis",
            "methodology",
            "further research is needed",
            "keyword",
        )
        if marker in lowered
    )
    suspicious = top_repeat >= 8 or suspicious_markers >= 2
    score = 90
    if suspicious:
        score = 35 if top_repeat >= 8 else 45
    return {
        "integrity_score": score,
        "score": score,
        "suspicious": suspicious,
        "reasons": ["repetition_or_template"] if suspicious else [],
    }
