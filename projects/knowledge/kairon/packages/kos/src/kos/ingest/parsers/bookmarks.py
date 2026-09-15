# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""浏览器书签解析器 — 将书签文件解析为JSON-LD格式。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def parse_file(input_path: str | Path) -> list[dict[str, Any]]:
    """解析书签 JSON 文件。"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    with open(path, encoding="utf-8") as f:
        bookmarks = json.load(f)

    facts: list[dict[str, Any]] = []
    for bm in bookmarks:
        fact_id = str(uuid.uuid4())
        facts.append(
            {
                "id": fact_id,
                "@type": "Bookmark",
                "topic": bm.get("title", "Untitled"),
                "pred": "bookmarked",
                "content": bm.get("url", ""),
                "metadata": {
                    "source": "bookmarks",
                    "tags": bm.get("tags", []),
                    "folder": bm.get("folder", ""),
                    "date_added": bm.get("date_added", ""),
                },
            }
        )

    return facts


def to_jsonld(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "@context": "https://sharedbrain.local/kg/personal/v1",
        "source": "browser_bookmarks",
        "facts": facts,
    }
