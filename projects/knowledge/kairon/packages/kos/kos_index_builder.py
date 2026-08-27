#!/usr/bin/env python3
# ruff: noqa
"""
KOS Vector Index Batch Builder — 分批构建向量索引

Usage:
    python kos_index_builder.py           # Build all remaining docs
    python kos_index_builder.py --batch 500  # Build 500 docs per batch
    python kos_index_builder.py --status     # Check index status
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from kos.config import get_artifact_path


def get_pending_docs(db_path, batch_size):
    """Get documents not yet indexed in LanceDB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Track processed docs in a local table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _index_progress (
            doc_id TEXT PRIMARY KEY,
            indexed_at TEXT NOT NULL
        )
    """)

    # Get doc_ids already processed
    processed = {r[0] for r in conn.execute("SELECT doc_id FROM _index_progress").fetchall()}

    # Get all documents from SQLite
    all_docs = conn.execute(
        "SELECT doc_id, title, body, zone, kind, canonical_path FROM documents ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    # Filter out already indexed
    pending = [d for d in all_docs if d["doc_id"] not in processed]
    return pending, processed


def mark_indexed(db_path, doc_ids):
    """Mark documents as indexed."""
    conn = sqlite3.connect(db_path)
    now = time.strftime("%Y%m%d%H%M%S")
    for doc_id in doc_ids:
        conn.execute("INSERT OR REPLACE INTO _index_progress (doc_id, indexed_at) VALUES (?, ?)", (doc_id, now))
    conn.commit()
    conn.close()


def build_batch(docs, batch_size=500):
    """Build vector index for a batch of documents."""
    from kos.semantic import _embed_texts, _chunk_text

    all_texts = []
    all_meta = []

    for d in docs[:batch_size]:
        text = f"{d['title'] or ''}\n{d['body'] or ''}"
        chunks = _chunk_text(text)
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

    # Embed in batches of 32
    BATCH_SIZE = 32
    all_embeddings = []
    for i in range(0, len(all_texts), BATCH_SIZE):
        batch = all_texts[i : i + BATCH_SIZE]
        vecs = _embed_texts(batch)
        all_embeddings.extend(vecs)

    # Store in LanceDB
    import lancedb

    db_path = Path(get_artifact_path("retrievalDatabase"))
    lancedb_dir = db_path.parent / "vectors"
    db = lancedb.connect(str(lancedb_dir))

    table_data = []
    for i, meta in enumerate(all_meta):
        if i < len(all_embeddings) and all_embeddings[i]:
            table_data.append({"vector": all_embeddings[i], **meta})

    if table_data:
        if "kos_documents" in db.table_names():
            tbl = db.open_table("kos_documents")
            tbl.add(table_data)
        else:
            db.create_table("kos_documents", table_data)

    return len(table_data)


def main():
    parser = argparse.ArgumentParser(description="KOS Vector Index Batch Builder")
    parser.add_argument("--batch", type=int, default=500, help="Documents per batch")
    parser.add_argument("--status", action="store_true", help="Check index status")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches (0=unlimited)")
    args = parser.parse_args()

    db_path = get_artifact_path("retrievalDatabase")

    if args.status:
        from kos.semantic import status

        print(f"Index status: {status()}")
        return

    batch_size = args.batch
    total_indexed = 0
    batch_num = 0

    while True:
        if args.max_batches > 0 and batch_num >= args.max_batches:
            break

        pending, processed = get_pending_docs(db_path, batch_size)
        if not pending:
            print("All documents indexed!")
            break

        batch_num += 1
        docs_this_batch = pending[:batch_size]
        print(
            f"Batch {batch_num}: indexing {len(docs_this_batch)} docs ({len(pending)} pending, {len(processed)} done)..."
        )
        sys.stdout.flush()

        t0 = time.time()
        indexed = build_batch(docs_this_batch, batch_size)
        elapsed = time.time() - t0

        # Mark as indexed
        mark_indexed(db_path, [d["doc_id"] for d in docs_this_batch])

        total_indexed += indexed
        print(f"  Indexed {indexed} chunks in {elapsed:.1f}s (total: {total_indexed})")
        sys.stdout.flush()

        # Small delay to avoid overloading
        time.sleep(0.5)

    print(f"\nDone! Total indexed: {total_indexed} chunks")


if __name__ == "__main__":
    main()
