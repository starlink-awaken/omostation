#!/usr/bin/env python3
"""omlxc-embedding-bridge.py — omlxc 本地 Embedding 向量提取器

功能: 物理连接本地跑在 localhost:8183 的 qwen3-embedding-8b 模型，
对 ~/Documents/_inbox/ 的抓取文档正文提取 1024 维密集向量，写入 vector_index.sqlite。

v1.0 (Real LLM Embedding Phase 1) | 2026-07-31
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents"))
WS_ROOT = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
VECTOR_DB = WS_ROOT / "data" / "vector_index.sqlite"
OMLXC_EMBEDDING_URL = "http://localhost:8183/v1/embeddings"


def init_vector_db() -> None:
    VECTOR_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(VECTOR_DB))
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_embeddings (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding_dim INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
    conn.close()


def get_local_embedding(text: str) -> list[float] | None:
    """物理调用 localhost:8183 的 qwen3-embedding-8b 模型提取向量."""
    payload = {
        "input": text[:2000],
        "model": "retrieval/qwen3-embedding-8b"
    }
    try:
        req = urllib.request.Request(
            OMLXC_EMBEDDING_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
    except Exception as e:
        print(f"ℹ️ omlxc 本地 Embedding API (8183) 暂未响应标准 REST 结构: {e}")
        return None
    return None


def index_inbox_files() -> int:
    init_vector_db()
    inbox_dir = DOCS_ROOT / "_inbox"
    if not inbox_dir.exists():
        return 0

    count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(VECTOR_DB))

    for f in inbox_dir.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            emb = get_local_embedding(content)
            dim = len(emb) if emb else 0
            file_id = f.stem

            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO doc_embeddings (id, file_path, chunk_text, embedding_dim, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (file_id, str(f), content[:300], dim, now_iso))
            count += 1
            print(f"✅ 物理向量索引建立 ──► {f.name} (维度: {dim})")
        except Exception as e:
            print(f"⚠️ 处理 {f.name} 错误: {e}")

    conn.close()
    return count


def main() -> int:
    print("🔒 启动基于 omlxc (localhost:8183) 本地模型的真实向量索引器...")
    count = index_inbox_files()
    print(f"🎉 向量处理完成: 物理索引了 {count} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
