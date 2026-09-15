#!/usr/bin/env python3
# ruff: noqa
"""
KOS Vector Index Fast Builder — 快速分批构建向量索引

优化:
- 大批次 (128 texts/batch) 减少 API 调用次数
- 多 worker 并行请求
- 断点续传
"""

import argparse
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from kos.config import get_artifact_path

# Configuration
EMBED_URL = "http://127.0.0.1:8183/v1/embeddings"
EMBED_MODEL = "embed"
EMBED_KEY = "sk-omlx-admin"
BATCH_SIZE = 128  # texts per API call
MAX_WORKERS = 4  # parallel API calls


def embed_batch(texts):
    """Embed a batch of texts via API."""
    payload = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
    import urllib.request

    req = urllib.request.Request(
        EMBED_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {EMBED_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]


def embed_parallel(all_texts, num_workers=MAX_WORKERS):
    """Embed texts in parallel batches."""
    batches = [all_texts[i : i + BATCH_SIZE] for i in range(0, len(all_texts), BATCH_SIZE)]
    results = [None] * len(batches)

    def process_batch(idx, batch):
        return idx, embed_batch(batch)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_batch, i, batch): i for i, batch in enumerate(batches)}
        for future in as_completed(futures):
            try:
                idx, embeddings = future.result()
                results[idx] = embeddings
            except Exception as e:
                print(f"  Error in batch {futures[future]}: {e}")
                sys.stdout.flush()

    # Flatten results
    all_embeddings = []
    for r in results:
        if r is not None:
            all_embeddings.extend(r)
    return all_embeddings


def build_index(db_path, docs, batch_docs=200):
    """Build vector index for documents."""
    from kos.semantic import _chunk_text

    # Prepare texts
    all_texts = []
    all_meta = []
    doc_ids = []

    for d in docs[:batch_docs]:
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
            doc_ids.append(d["doc_id"])

    if not all_texts:
        return 0

    # Embed in parallel
    print(f"  Embedding {len(all_texts)} chunks ({len(all_texts) // BATCH_SIZE} batches of {BATCH_SIZE})...")
    sys.stdout.flush()
    embeddings = embed_parallel(all_texts)

    # Store in LanceDB
    import lancedb

    lancedb_dir = Path(db_path).parent / "vectors"
    db = lancedb.connect(str(lancedb_dir))

    table_data = []
    for i, meta in enumerate(all_meta):
        if i < len(embeddings) and embeddings[i]:
            table_data.append({"vector": embeddings[i], **meta})

    if table_data:
        if "kos_documents" in db.list_tables():  # type: ignore[reportOperatorIssue]
            tbl = db.open_table("kos_documents")
            tbl.add(table_data)
        else:
            db.create_table("kos_documents", table_data)

    return len(table_data)


def main():
    parser = argparse.ArgumentParser(description="KOS Vector Index Fast Builder")
    parser.add_argument("--batch", type=int, default=200, help="Documents per batch")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches (0=unlimited)")
    parser.add_argument("--status", action="store_true", help="Check index status")
    args = parser.parse_args()

    db_path = get_artifact_path("retrievalDatabase")

    if args.status:
        from kos.semantic import status

        print(f"Index status: {status()}")
        return

    # Track processed docs
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _index_progress (
            doc_id TEXT PRIMARY KEY,
            indexed_at TEXT NOT NULL
        )
    """)
    processed = {r[0] for r in conn.execute("SELECT doc_id FROM _index_progress").fetchall()}

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
        indexed = build_index(db_path, docs_this_batch, batch_size)
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
