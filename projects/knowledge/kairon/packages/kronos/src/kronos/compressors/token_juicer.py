"""TokenJuicer — HTML/text token compression for kronos pipelines."""

import hashlib
import re
from typing import Any


class TokenJuicer:
    def __init__(self) -> None:
        self._dedup_hashes: set[str] = set()

    def compress(self, text: str) -> dict[str, Any]:
        original_len = len(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"(https?://\S+?)(\?utm_\w+=[^&\s]+&?)+", r"\1", text)
        text = re.sub(r"https?://\S+", "[URL]", text)
        compressed_len = len(text)
        saved_pct = round((1 - compressed_len / max(original_len, 1)) * 100, 1)
        return {"original_len": original_len, "compressed_len": compressed_len, "saved_pct": saved_pct, "text": text}

    def dedup_check(self, text: str) -> bool:
        h = hashlib.sha256(text.encode()).hexdigest()
        if h in self._dedup_hashes:
            return False
        self._dedup_hashes.add(h)
        return True

    def dedup_stats(self) -> dict:
        return {"total_unique": len(self._dedup_hashes)}
