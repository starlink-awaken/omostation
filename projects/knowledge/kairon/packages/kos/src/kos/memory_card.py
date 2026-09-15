"""Memory Card — 将 KOS domain 知识分段为 ≤3000 token 的 Markdown 片段"""

import re
import time
from pathlib import Path
from typing import Any

CARD_DIR = Path.home() / ".kos" / "memory_cards"
TOKEN_LIMIT = 3000
AVG_CHAR_PER_TOKEN = 4  # Chinese text ~1.5 chars/token, English ~4


def _estimate_tokens(text: str) -> int:
    return len(text) // AVG_CHAR_PER_TOKEN


def _truncate_to_limit(text: str) -> str:
    if _estimate_tokens(text) <= TOKEN_LIMIT:
        return text
    limit_chars = TOKEN_LIMIT * AVG_CHAR_PER_TOKEN
    # Try to break at paragraph boundary
    truncated = text[:limit_chars]
    last_para = truncated.rfind("\n\n")
    if last_para > len(truncated) * 0.7:
        truncated = truncated[:last_para]
    return truncated + f"\n\n[truncated: {_estimate_tokens(text)} tokens → {TOKEN_LIMIT}]"


def segment_text(text: str, title: str = "") -> list[dict]:
    """Segment text into ≤3000 token cards"""
    cards = []
    paragraphs = text.split("\n\n")
    current = ""
    for para in paragraphs:
        if _estimate_tokens(current + para) > TOKEN_LIMIT and current:
            cards.append(
                {
                    "title": title,
                    "content": current.strip(),
                    "tokens": _estimate_tokens(current),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
            current = para
        else:
            current += "\n\n" + para if current else para
    if current:
        cards.append(
            {
                "title": title,
                "content": current.strip(),
                "tokens": _estimate_tokens(current),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return cards


def save_card(card: dict) -> dict:
    from kos.adapters.memtheta_adapter import memtheta_adapter

    CARD_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]+", "_", card["title"][:30])
    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_{slug}.md"
    content = f"---\ntitle: {card['title']}\ntimestamp: {card['timestamp']}\ntokens: {card['tokens']}\n---\n\n{card['content']}"

    # 1. Backward compat local fallback
    (CARD_DIR / fname).write_text(content, encoding="utf-8")
    card["file"] = fname

    # 2. Dual-Track Pipeline: Write raw trace and push Theta state
    # We treat save_card as an implicit "Update" operator with default confidence
    # for the given file slug.
    memtheta_adapter.update(
        target_id=fname, context=card["content"], confidence=0.8, trigger_source="memory_card.save_card"
    )

    return card


def query(q: str, limit: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for f in sorted(CARD_DIR.glob("*.md"), reverse=True)[:50]:
        content = f.read_text(encoding="utf-8", errors="replace")
        if q.lower() in content.lower():
            results.append({"file": f.name, "content": content[:200], "relevance": content.lower().count(q.lower())})
    return sorted(results, key=lambda x: -x["relevance"])[:limit]


def status() -> dict:
    cards = list(CARD_DIR.glob("*.md"))
    return {"total_cards": len(cards), "total_tokens": sum(1 for _ in cards) * TOKEN_LIMIT, "card_dir": str(CARD_DIR)}
