#!/usr/bin/env python3
# ruff: noqa
"""KOS Ingest — quick knowledge capture.

Usage:
    kos ingest "一句话"                          → save as note
    kos ingest "https://..."                     → fetch + save
    kos ingest ~/doc.pdf ~/report.docx           → copy + index
"""

import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent

from kos.config import get_artifact_path, get_workspace_manifest  # type: ignore[import-not-found]
from typing import Any, Optional, cast

INBOX = Path.home() / "Documents" / "KOS-Inbox"
INBOX.mkdir(parents=True, exist_ok=True)

# Dedup registry: hash → ingested path
DEDUP_FILE = INBOX / ".dedup.json"


def _load_dedup() -> dict:  # type: ignore[type-arg]
    if DEDUP_FILE.exists():
        try:
            return cast("dict[Any, Any]", json.loads(DEDUP_FILE.read_text()))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_dedup(data: dict):  # type: ignore[no-untyped-def, type-arg]
    DEDUP_FILE.write_text(json.dumps(data, ensure_ascii=False))


def _hash_content(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _is_duplicate(text: str) -> dict | None:  # type: ignore[type-arg]
    """Check if content already exists. Returns duplicate info or None."""
    h = _hash_content(text)
    dedup = _load_dedup()
    if h in dedup:
        return cast("dict[Any, Any]", dedup[h])
    return None


def _mark_ingested(text: str, info: dict):  # type: ignore[no-untyped-def, type-arg]
    h = _hash_content(text)
    dedup = _load_dedup()
    dedup[h] = {
        "path": info.get("ingested", ""),
        "title": info.get("title", ""),
        "time": datetime.now().isoformat()[:19],
    }
    # Keep last 1000 entries
    if len(dedup) > 1000:
        keys = sorted(dedup.keys())[-900:]
        dedup = {k: dedup[k] for k in keys}
    _save_dedup(dedup)


def is_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def is_file(text: str) -> bool:
    p = Path(text).expanduser()
    return p.exists() and p.is_file()


def ingest_text(text: str, title: Optional[str] = None) -> dict[str, Any]:
    """Save a text snippet as a markdown note and dual-write to Mem0 memory."""
    if not title:
        title = text[:50].replace("\n", " ").strip()
    safe_name = re.sub(r"[^\w\s-]", "", title)[:60].strip()
    if not safe_name:
        safe_name = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = INBOX / f"{safe_name}.md"
    content = f"# {title}\n\n> KOS ingest · {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{text}\n"
    filepath.write_text(content, encoding="utf-8")

    # Dual-track write: Mem0Adapter
    try:
        from kos.adapters.mem0_adapter import Mem0Adapter

        adapter = Mem0Adapter()
        if adapter.enabled:
            adapter.add_memory(text=text, user_id="kos-user", metadata={"source": str(filepath), "title": title})
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(f"Dual-write to Mem0 failed: {e}")

    # Check duplication
    dedup_check = _is_duplicate(text)
    result = {"ingested": str(filepath), "type": "text", "title": title, "chars": len(text)}
    if dedup_check:
        result["duplicate"] = True
        result["original"] = dedup_check
    else:
        _mark_ingested(text, result)
    return result


def ingest_url(url: str) -> dict:  # type: ignore[type-arg]
    """Fetch URL content and save as note."""
    try:
        import subprocess as sp

        # Try curl for simplicity
        r = sp.run(["curl", "-sL", "--max-time", "15", url], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            return {"error": f"Failed to fetch: {url}", "detail": r.stderr[:200]}

        html = r.stdout
        # Extract title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else urlparse(url).netloc

        # Simple text extraction: strip HTML tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()[:10000]

        return ingest_text(text, title)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def ingest_file(filepath: str) -> dict:  # type: ignore[type-arg]
    """Copy a file to KOS inbox and extract text if possible."""
    src = Path(filepath).expanduser()
    if not src.exists():
        return {"error": f"File not found: {filepath}"}

    dst = INBOX / src.name
    # Avoid overwrite
    if dst.exists():
        dst = INBOX / f"{src.stem}_{int(time.time())}{src.suffix}"

    import shutil

    shutil.copy2(str(src), str(dst))

    # Try to extract text
    text = ""
    suffix = src.suffix.lower()
    try:
        if suffix in (".md", ".txt", ".markdown"):
            text = src.read_text(encoding="utf-8")[:8000]
        elif suffix == ".docx":
            from docx import Document

            doc = Document(str(src))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:8000]
        elif suffix == ".pdf":
            import fitz  # type: ignore[import-untyped]

            doc = fitz.open(str(src))
            text = "\n".join(page.get_text() for page in doc)[:8000]  # type: ignore[reportArgumentType]
            doc.close()
    except Exception:  # noqa: BLE001
        text = f"[{suffix} file: {src.name}]"

    return {
        "ingested": str(dst),
        "type": suffix,
        "original": str(src),
        "title": src.name,
        "text_preview": text[:500],
    }


def analyze_ingest(item: dict[str, Any]) -> dict[str, Any]:
    """Post-ingest analysis: classify, tag, find related, suggest entities."""
    text = item.get("text_preview", "")
    title = item.get("title", "")

    if not text or len(text) < 20:
        return {"depth": "minimal", "reason": "content too short"}

    analysis: dict[str, Any] = {
        "depth": "full",
        "suggested_tags": [],
        "related_docs": [],
        "suggested_domain": "obsidian",
    }

    # 1. Domain classification via manifest strategies
    get_workspace_manifest()
    zone_kw = {
        "gongwen": ["通知", "报告", "制度", "卫健委", "医院", "医疗", "卫生", "考核", "绩效"],
        "guozhuan": ["国转中心", "数字化", "平台", "高校", "转化", "政策", "借调"],
        "obsidian": ["知识库", "AI", "Agent", "Skills", "写作", "学习", "笔记"],
    }
    scores: dict[str, int] = {}
    for zone, kws in zone_kw.items():
        scores[zone] = sum(1 for kw in kws if kw in text[:500] or kw in title)
    best_zone = max(scores, key=lambda k: scores[k]) if max(scores.values()) > 0 else "obsidian"
    analysis["suggested_domain"] = best_zone

    # 2. Extract topic keywords
    topic_patterns = {
        "数字化": ["数字化", "平台", "系统", "信息化"],
        "医疗健康": ["医疗", "健康", "医院", "病历", "患者", "妇幼"],
        "政策制度": ["制度", "规定", "通知", "政策", "法规", "考核"],
        "AI技术": ["AI", "模型", "Agent", "Skills", "LLM", "GPT"],
        "项目管理": ["项目", "进度", "方案", "汇报", "里程碑"],
    }
    for topic, kws in topic_patterns.items():
        if any(kw in text for kw in kws):
            analysis["suggested_tags"].append(topic)

    # 3. Find related documents
    try:
        db_path = get_artifact_path("retrievalDatabase")
        if db_path.exists():  # type: ignore[attr-defined]
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            # Search by title keywords
            for kw in title.split()[:3]:
                if len(kw) < 2:
                    continue
                try:
                    rows = conn.execute(
                        "SELECT title, zone FROM documents_fts WHERE documents_fts MATCH ? LIMIT 3", (kw,)
                    ).fetchall()
                    for r in rows:
                        if r["title"] not in [d["title"] for d in analysis["related_docs"]]:
                            analysis["related_docs"].append({"title": r["title"], "zone": r["zone"]})
                except sqlite3.OperationalError:
                    continue
                if len(analysis["related_docs"]) >= 3:
                    break
            conn.close()
    except Exception:  # noqa: BLE001
        pass

    return analysis


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: kos ingest <text|url|filepath> [...]")
        print("  kos ingest '今天开会讨论了数字化平台方案'")
        print("  kos ingest https://example.com/article")
        print("  kos ingest ~/Downloads/report.pdf")
        return

    results = []
    for arg in sys.argv[1:]:
        if is_url(arg):
            r = ingest_url(arg)
        elif is_file(arg):
            r = ingest_file(arg)
        else:
            r = ingest_text(arg)
        results.append(r)
        # After individual ingestion, run analysis
    if len(results) == 1 and results[0].get("text_preview"):
        analyze_result = analyze_ingest(results[0])
        results[0]["analysis"] = analyze_result

    print(json.dumps({"ingested": len(results), "items": results}, ensure_ascii=False, indent=2))

    # Reindex inbox
    print("  ⏳ Indexing...", file=sys.stderr)
    import subprocess as sp

    sp.run(
        [sys.executable, str(SCRIPT_DIR / "_legacy" / "kos-indexer.py"), "index", "--incremental"], capture_output=True
    )
    print("  ✅ Done", file=sys.stderr)


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
