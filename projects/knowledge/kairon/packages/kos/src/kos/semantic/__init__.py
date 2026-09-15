#!/usr/bin/env python3
# ruff: noqa
"""
KOS Semantic Search — LanceDB vector index for cross-domain semantic retrieval.

Usage:
    kos-semantic build              # Build/rebuild vector index
    kos-semantic build --incremental # Incremental build (only new/changed docs)
    kos-semantic build --domain X   # Build for single domain
    kos-semantic search "query"     # Semantic search
    kos-semantic hybrid "query"     # Hybrid FTS5 + semantic search
    kos-semantic status             # Index stats

Embedding backends:
    - omlx:     Local omlx gateway (qwen3-embedding-8b, default)
    - st:       Sentence-transformers (all-MiniLM-L6-v2, fallback)
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path

# ── Configuration ──────────────────────────────────────

# Primary embedding backend: omlx gateway (qwen3-embedding-8b, 4096d, Chinese-optimized)
OMLX_URL = os.environ.get("OMLX_URL", "http://100.96.126.35:4000")
OMLX_API_KEY = os.environ.get("OMLX_API_KEY", "123456")
OMLX_EMBED_MODEL = os.environ.get("OMLX_EMBED_MODEL", "qwen3-embedding-8b")

# ── Model Registry ─────────────────────────────────────
# Available embedding models with auto-switching support.
# Switch model via: kos-semantic build --model <name>
# Or environment: KOS_EMBED_MODEL=<name>

EMBED_MODEL_REGISTRY = {
    # Local models (sentence-transformers)
    "all-MiniLM-L6-v2": {
        "source": "st",
        "dim": 384,
        "description": "General purpose, fast, multilingual (default fallback)",
        "chinese_quality": "medium",
        "speed": "~5ms/text",
    },
    "BAAI/bge-small-zh-v1.5": {
        "source": "st",
        "dim": 512,
        "description": "Chinese-optimized, fast, good quality (recommended)",
        "chinese_quality": "excellent",
        "speed": "~24ms/text",
    },
    "BAAI/bge-base-zh-v1.5": {
        "source": "st",
        "dim": 768,
        "description": "Chinese-optimized, balanced quality/speed",
        "chinese_quality": "excellent",
        "speed": "~50ms/text",
    },
    "BAAI/bge-large-zh-v1.5": {
        "source": "st",
        "dim": 1024,
        "description": "Chinese-optimized, highest quality, slower",
        "chinese_quality": "excellent",
        "speed": "~150ms/text",
    },
    # Remote models (omlx gateway)
    "embed": {
        "source": "omlx",
        "dim": 4096,
        "description": "Qwen3-Embedding-8B via omlx (high quality, slower)",
        "chinese_quality": "excellent",
        "speed": "~174ms/text",
    },
    "embed-bge": {
        "source": "omlx",
        "dim": 1024,
        "description": "BGE via omlx gateway",
        "chinese_quality": "excellent",
        "speed": "~50ms/text",
    },
}

# Active model selection (override with KOS_MODEL env or --model CLI)
ACTIVE_MODEL = os.environ.get("KOS_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

# Legacy fallback config (kept for backward compatibility)
ST_MODEL_NAME = ACTIVE_MODEL if EMBED_MODEL_REGISTRY.get(ACTIVE_MODEL, {}).get("source") == "st" else "all-MiniLM-L6-v2"
ST_EMBEDDING_DIM = EMBED_MODEL_REGISTRY.get(ST_MODEL_NAME, {}).get("dim", 384)

# Vector storage
VECTOR_TABLE = "kos_documents"
VECTOR_CHUNK_TABLE = "kos_chunks"  # Chunked documents
BATCH_SIZE = 128  # Optimized for larger batches
CHUNK_SIZE = 1024  # Larger chunks = fewer embeddings needed
CHUNK_OVERLAP = 128

# Lazy imports
_embedder = None
_lancedb = None
_embed_backend = None  # "omlx" | "st"

# ── Embedding Backends ─────────────────────────────────


def _get_embed_backend() -> str:
    """Detect available embedding backend."""
    global _embed_backend
    if _embed_backend is not None:
        return _embed_backend

    # Try omlx first (faster, better Chinese support)
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{OMLX_URL}/v1/models",
            headers={"Authorization": f"Bearer {OMLX_API_KEY}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                _embed_backend = "omlx"
                return "omlx"
    except Exception:
        pass

    # Fallback to sentence-transformers
    try:
        import sentence_transformers  # noqa: F401

        _embed_backend = "st"
        return "st"
    except ImportError:
        pass

    return "none"


def _get_embedder() -> Any:
    """Get sentence-transformers embedder (fallback backend)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(ST_MODEL_NAME)
    return _embedder


def _embed_texts_omlx(texts: list[str]) -> list[list[float]]:
    """Embed texts via omlx gateway."""
    import urllib.request
    import urllib.error

    payload = json.dumps(
        {
            "model": OMLX_EMBED_MODEL,
            "input": texts,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{OMLX_URL}/v1/embeddings",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OMLX_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
    except urllib.error.URLError:
        return []


def _embed_texts_st(texts: list[str]) -> list[list[float]]:
    """Embed texts via sentence-transformers."""
    embedder = _get_embedder()
    return embedder.encode(texts, show_progress_bar=False).tolist()


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using available backend."""
    backend = _get_embed_backend()

    if backend == "omlx":
        return _embed_texts_omlx(texts)
    elif backend == "st":
        return _embed_texts_st(texts)
    else:
        return []


def _get_embedding_dim() -> int:
    """Get embedding dimension based on backend."""
    backend = _get_embed_backend()
    if backend == "omlx":
        return 4096  # qwen3-embedding-8b
    return ST_EMBEDDING_DIM


# ── LanceDB ────────────────────────────────────────────


def _get_lancedb() -> Any:
    """Get LanceDB connection."""
    global _lancedb
    if _lancedb is None:
        import lancedb

        db_path = Path(get_artifact_path("retrievalDatabase"))
        lancedb_dir = db_path.parent / "vectors"
        lancedb_dir.mkdir(parents=True, exist_ok=True)
        _lancedb = lancedb.connect(str(lancedb_dir))
    return _lancedb


# ── Document Chunking ──────────────────────────────────


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks for better embedding."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i : i + chunk_size]
        if chunk.strip():
            # Merge very small last chunk with previous
            if len(chunk) < 50 and chunks:
                chunks[-1] += chunk
            else:
                chunks.append(chunk)
    return chunks


# ── Build ──────────────────────────────────────────────


def build_index(domain: str | None = None, incremental: bool = False) -> dict:
    """Build/rebuild vector index.

    Args:
        domain: Optional domain filter.
        incremental: If True, only embed new/changed documents.
    """
    t0 = time.time()

    backend = _get_embed_backend()
    if backend == "none":
        return {
            "error": "No embedding backend available. Install lancedb + sentence-transformers or start omlx gateway."
        }

    try:
        db = _get_lancedb()
    except ImportError as e:
        return {"error": f"LanceDB import failed: {e}"}

    # Get documents from SQLite
    db_path = Path(get_artifact_path("retrievalDatabase"))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    where = ""
    params: list[Any] = []
    if domain:
        where = "WHERE zone = ?"
        params.append(domain)

    docs = conn.execute(
        f"SELECT doc_id, title, body, zone, kind, canonical_path FROM documents {where}", params
    ).fetchall()
    conn.close()

    total_docs = len(docs)
    if total_docs == 0:
        return {"error": "No documents indexed. Run 'kos index' first.", "count": 0}

    # For incremental: filter out already-indexed docs
    existing_ids: set[str] = set()
    if incremental and VECTOR_TABLE in db.table_names():
        try:
            tbl = db.open_table(VECTOR_TABLE)
            # Batch fetch existing doc_ids (limit to avoid memory issues)
            existing_rows = tbl.search().select(["doc_id"]).to_list()
            existing_ids = {r["doc_id"] for r in existing_rows}
        except Exception:
            pass

    # Filter to process
    docs_to_process = [d for d in docs if d["doc_id"] not in existing_ids]
    skipped = total_docs - len(docs_to_process)

    if not docs_to_process:
        return {
            "embedded": 0,
            "skipped": skipped,
            "total": total_docs,
            "message": "No new documents to embed",
            "backend": backend,
        }

    # Prepare texts for embedding (chunked)
    all_texts: list[str] = []
    all_meta: list[dict] = []

    for d in docs_to_process:
        title = d["title"] or ""
        body = d["body"] or ""
        full_text = f"{title}\n{body}"

        chunks = _chunk_text(full_text)
        if not chunks:
            chunks = [title]  # Fallback to title only

        for chunk_idx, chunk_text in enumerate(chunks):
            all_texts.append(chunk_text[:2000])  # Cap at 2000 chars per chunk
            all_meta.append(
                {
                    "doc_id": d["doc_id"],
                    "title": title,
                    "zone": d["zone"],
                    "kind": d["kind"],
                    "canonical_path": d["canonical_path"],
                    "chunk_idx": chunk_idx,
                }
            )

    # Embed in batches
    total_chunks = len(all_texts)
    print(
        f"  Backend: {backend}  ·  Embedding {total_chunks} chunks from {len(docs_to_process)} docs...", file=sys.stderr
    )

    embeddings: list[list[float]] = []
    batch_size = BATCH_SIZE
    for i in range(0, total_chunks, batch_size):
        batch = all_texts[i : i + batch_size]
        batch_vecs = _embed_texts(batch)
        embeddings.extend(batch_vecs)
        if (i + batch_size) % 200 == 0 or i + batch_size >= total_chunks:
            print(f"    {min(i + batch_size, total_chunks)}/{total_chunks}", file=sys.stderr)

    if not embeddings:
        return {"error": "Embedding failed", "count": 0}

    # Store in LanceDB
    table_data = []
    for i, meta in enumerate(all_meta):
        if i < len(embeddings) and embeddings[i]:
            table_data.append(
                {
                    "vector": embeddings[i],
                    **meta,
                }
            )

    # Drop and recreate (or merge for incremental)
    try:
        db.drop_table(VECTOR_TABLE)
    except Exception:
        pass

    if not table_data:
        return {"error": "No valid embeddings produced", "count": 0}

    tbl = db.create_table(VECTOR_TABLE, table_data)
    count = tbl.count_rows()

    elapsed = round(time.time() - t0, 1)

    return {
        "embedded": count,
        "documents": len(docs_to_process),
        "skipped": skipped,
        "total": total_docs,
        "dimensions": len(embeddings[0]) if embeddings else 0,
        "backend": backend,
        "elapsed_seconds": elapsed,
        "incremental": incremental,
        "domain": domain or "all",
    }


# ── Search ─────────────────────────────────────────────


def semantic_search(query: str, limit: int = 10, domain: str | None = None) -> dict:
    """Semantic vector search with optional domain filter."""
    try:
        db = _get_lancedb()
    except ImportError as e:
        return {"error": f"LanceDB import failed: {e}", "results": [], "count": 0}

    if VECTOR_TABLE not in db.table_names():
        # Auto-build if missing
        build_index()

    backend = _get_embed_backend()
    if backend == "none":
        return {"error": "No embedding backend available", "results": [], "count": 0}

    # Embed query
    query_vecs = _embed_texts([query])
    if not query_vecs:
        return {"error": "Query embedding failed", "results": [], "count": 0}
    q_vec = query_vecs[0]

    # Search
    tbl = db.open_table(VECTOR_TABLE)

    if domain:
        results = tbl.search(q_vec).limit(limit * 3).to_list()
        results = [r for r in results if r.get("zone") == domain][:limit]
    else:
        results = tbl.search(q_vec).limit(limit).to_list()

    return {
        "query": query,
        "results": [
            {
                "doc_id": r["doc_id"],
                "title": r.get("title", ""),
                "zone": r.get("zone", ""),
                "kind": r.get("kind", ""),
                "canonical_path": r.get("canonical_path", ""),
                "chunk_idx": r.get("chunk_idx", 0),
                "_distance": r.get("_distance", 0),
            }
            for r in results
        ],
        "count": len(results),
        "backend": backend,
    }


def hybrid_search(query: str, limit: int = 10) -> dict:
    """Combine FTS5 + LanceDB results via RRF fusion."""
    # FTS5 results
    db_path = Path(get_artifact_path("retrievalDatabase"))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        fts_results = conn.execute(
            """SELECT d.doc_id, d.title, d.zone, d.kind, d.canonical_path
               FROM documents_fts f JOIN documents d ON f.doc_id = d.doc_id
               WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?""",
            (query, limit * 2),
        ).fetchall()
    except sqlite3.OperationalError:
        fts_results = []
    conn.close()

    # Semantic results
    sem = semantic_search(query, limit=limit * 2)
    sem_results = sem.get("results", [])

    # RRF fusion
    k = 60
    scores: dict[str, float] = {}
    docs: dict[str, Any] = {}

    for rank, r in enumerate(fts_results):
        d = dict(r)
        doc_id = d["doc_id"]
        docs[doc_id] = d
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

    for rank, r in enumerate(sem_results):
        doc_id = r["doc_id"]
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "title": r["title"],
                "zone": r["zone"],
                "kind": r["kind"],
                "canonical_path": r["canonical_path"],
            }
        scores[doc_id] = scores.get(doc_id, 0) + 1.2 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
    results = [{**docs[doc_id], "_score": round(score, 4)} for doc_id, score in ranked]

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "backend": "hybrid (FTS5 + LanceDB)",
    }


def list_models() -> dict:
    """List all available embedding models."""
    return {
        "active": ACTIVE_MODEL,
        "models": {name: {**cfg, "selected": name == ACTIVE_MODEL} for name, cfg in EMBED_MODEL_REGISTRY.items()},
    }


def status() -> dict:
    """Get vector index status."""
    try:
        db = _get_lancedb()
        tables = db.table_names()
        if VECTOR_TABLE in tables:
            tbl = db.open_table(VECTOR_TABLE)
            count = tbl.count_rows()
            backend = _get_embed_backend()
            return {
                "status": "active",
                "documents": count,
                "backend": backend,
                "dimensions": _get_embedding_dim(),
            }
        return {"status": "not_built", "documents": 0}
    except ImportError:
        return {"status": "unavailable", "error": "lancedb not installed"}


# ── Main ───────────────────────────────────────────────


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    domain = None
    limit = 10
    incremental = "--incremental" in sys.argv
    model = None
    for i, a in enumerate(sys.argv):
        if a == "--domain" and i + 1 < len(sys.argv):
            domain = sys.argv[i + 1]
        if a == "--limit" and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                pass
        if a == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]

    # Override active model if specified
    global ACTIVE_MODEL
    if model:
        if model in EMBED_MODEL_REGISTRY:
            ACTIVE_MODEL = model
        else:
            print(f"Warning: Unknown model '{model}'. Available: {list(EMBED_MODEL_REGISTRY.keys())}")

    if cmd == "build":
        result = build_index(domain=domain, incremental=incremental)
    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        result = semantic_search(query, limit=limit, domain=domain)
    elif cmd == "hybrid":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        result = hybrid_search(query, limit=limit)
    elif cmd == "status":
        result = status()
    elif cmd == "list-models":
        result = list_models()
    else:
        result = {
            "error": f"Unknown: {cmd}",
            "usage": "build|search|hybrid|status|list-models",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
