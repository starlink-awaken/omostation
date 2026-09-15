#!/usr/bin/env python3
# ruff: noqa
"""
KOS Vector Index Local Builder — 使用本地 sentence-transformers 构建向量索引

优势:
- 无 API 延迟，本地推理
- 支持多进程并行
- 断点续传

Usage:
    python kos_index_local.py           # Build all docs
    python kos_index_local.py --batch 500  # Build 500 docs per batch
    python kos_index_local.py --status     # Check status
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from kos.config import get_artifact_path

# Configuration
BATCH_SIZE = 64  # texts per encode call


def load_embedder():
    """Load sentence-transformers embedder."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts, model):
    """Embed texts using local model."""
    return model.encode(texts, show_progress_bar=False, batch_size=32).tolist()


def build_index(db_path, docs, model, batch_docs=500):
    """Build vector index for documents using local model."""
    import re

    def chunk_text(text, chunk_size=1024, overlap=128):
        if len(text) <= chunk_size:
            return [text] if text.strip() else []
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i : i + chunk_size]
            if chunk.strip():
                if len(chunk) < 50 and chunks:
                    chunks[-1] += chunk
                else:
                    chunks.append(chunk)
        return chunks

    # Prepare texts
    all_texts = []
    all_meta = []

    for d in docs[:batch_docs]:
        text = f"{d['title'] or ''}\n{d['body'] or ''}"
        chunks = chunk_text(text)
        if not chunks:
            chunks = [d["title"] or ""]
        for idx, chunk in enumerate(chunks):
            all_texts.append(chunk[:2000])
            all_meta.append(
                {
                    "doc_id": d["doc_id"],
                    "title": d["title"],
                    "zone": d["zone"],
                    "kind": d["kind"],
                    "canonical_path": d["canonical_path"],
                    "chunk_idx": idx,
                }
            )

    if not all_texts:
        return 0

    # Embed locally
    print(f"  Embedding {len(all_texts)} chunks locally...")
    sys.stdout.flush()
    embeddings = embed_texts(all_texts, model)

    # Store in LanceDB
    import lancedb

    lancedb_dir = Path(db_path).parent / "vectors"
    db = lancedb.connect(str(lancedb_dir))

    table_data = []
    for i, meta in enumerate(all_meta):
        if i < len(embeddings) and embeddings[i]:
            table_data.append({"vector": embeddings[i], **meta})

    if table_data:
        try:
            if "kos_documents" in db.list_tables():  # type: ignore[reportOperatorIssue]
                tbl = db.open_table("kos_documents")
                tbl.add(table_data)
            else:
                db.create_table("kos_documents", table_data)
        except Exception as e:
            print(f"  Warning: {e}, trying add...")
            tbl = db.open_table("kos_documents")
            tbl.add(table_data)

    return len(table_data)


def main():
    parser = argparse.ArgumentParser(description="KOS Vector Index Local Builder")
    parser.add_argument("--batch", type=int, default=500, help="Documents per batch")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches (0=unlimited)")
    parser.add_argument("--status", action="store_true", help="Check index status")
    args = parser.parse_args()

    db_path = get_artifact_path("retrievalDatabase")

    if args.status:
        from kos.semantic import status

        print(f"Index status: {status()}")
        return

    # Load model
    print("Loading embedding model...")
    model = load_embedder()
    print("Model loaded.")

    # Clear existing index for fresh build
    import lancedb

    lancedb_dir = Path(db_path).parent / "vectors"
    db = lancedb.connect(str(lancedb_dir))
    try:
        db.drop_table("kos_documents")
        print("Cleared existing index.")
    except:
        pass

    # Clear progress tracking (fresh start)
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS _index_progress")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _index_progress (
            doc_id TEXT PRIMARY KEY,
            indexed_at TEXT NOT NULL
        )
    """)
    processed = set()

    # Get pending docs
    conn.row_factory = sqlite3.Row
    all_docs = conn.execute(
        "SELECT doc_id, title, body, zone, kind, canonical_path FROM documents ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    pending = [d for d in all_docs if d["doc_id"] not in processed]
    print(f"Total: {len(all_docs)} docs, Processed: {len(processed)}, Pending: {len(pending)}")
    sys.stdout.flush()

    if not pending:
        print("All documents indexed!")
        return

    batch_size = args.batch
    total_indexed = 0
    batch_num = 0
    t_start = time.time()

    while pending:
        if args.max_batches > 0 and batch_num >= args.max_batches:
            break

        batch_num += 1
        docs_this_batch = pending[:batch_size]
        pending = pending[batch_size:]

        print(f"Batch {batch_num}: {len(docs_this_batch)} docs...")
        sys.stdout.flush()

        t0 = time.time()
        indexed = build_index(db_path, docs_this_batch, model, batch_size)
        elapsed = time.time() - t0

        # Mark as indexed
        conn = sqlite3.connect(db_path)
        now = time.strftime("%Y%m%d%H%M%S")
        for d in docs_this_batch:
            conn.execute(
                "INSERT OR REPLACE INTO _index_progress (doc_id, indexed_at) VALUES (?, ?)", (d["doc_id"], now)
            )
        conn.commit()
        conn.close()

        total_indexed += indexed
        docs_done = batch_num * batch_size
        elapsed_total = time.time() - t_start
        rate = docs_done / elapsed_total if elapsed_total > 0 else 0
        eta = len(pending) / rate if rate > 0 else 0

        print(
            f"  Done: {indexed} chunks in {elapsed:.1f}s | Total: {total_indexed} | Rate: {rate:.0f} docs/min | ETA: {eta / 60:.0f}min"
        )
        sys.stdout.flush()

    print(f"\nComplete! Total indexed: {total_indexed} chunks in {(time.time() - t_start) / 60:.1f}min")


if __name__ == "__main__":
    main()
