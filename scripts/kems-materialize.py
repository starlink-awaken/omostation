#!/usr/bin/env python3
"""Materialize redacted source metadata and evidence into the KEMS graph store.

The Kairon package is loaded from an explicitly configured workspace path so
this runtime adapter does not create a second graph implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

SOURCE_PATTERNS = (
    "*-auto-seeyon-oa-pending.md",
    "*-auto-netease-mailmaster.md",
    "*-auto-apple-mail.md",
    "*-auto-iphone-sms.md",
)


def _load_graph_types():
    root = Path(os.environ.get("BOS_KAIRon_ROOT", "")).expanduser()
    if not root:
        root = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace")) / "projects" / "kairon"
    package_src = root / "packages" / "kos" / "src"
    if not package_src.is_dir():
        raise RuntimeError(f"Kairon KOS source is unavailable: {package_src}")
    sys.path.insert(0, str(package_src))
    try:
        from kos.kems import DocumentVersion, EvidenceSpan, GraphEntity, GraphStore
    except ImportError as exc:
        raise RuntimeError("Kairon KEMS graph store is unavailable") from exc
    return DocumentVersion, EvidenceSpan, GraphEntity, GraphStore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(docs_root: Path) -> list[Path]:
    inbox = docs_root / "_inbox"
    return sorted({path for pattern in SOURCE_PATTERNS for path in inbox.glob(pattern) if path.is_file()})


def materialize(docs_root: Path, graph_db: Path, run_id: str) -> dict[str, object]:
    DocumentVersion, EvidenceSpan, GraphEntity, GraphStore = _load_graph_types()
    files = source_files(docs_root)
    if not files:
        raise RuntimeError("no source documents available for KEMS materialization")
    store = GraphStore(graph_db)
    now = datetime.now(UTC).isoformat()
    entities = 0
    evidence = 0
    for path in files:
        source_sha = _sha256(path)
        version_id = source_sha
        document_id = f"source:{source_sha[:24]}"
        text = path.read_text(encoding="utf-8", errors="replace")
        sensitivity = "internal" if "seeyon" in path.name else "personal"
        store.put_document_version(
            DocumentVersion(document_id, version_id, source_sha, "official_work" if sensitivity == "internal" else "personal", text, sensitivity=sensitivity, run_id=run_id)
        )
        evidence_id = f"evidence:{source_sha[:24]}"
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), path.stem)
        store.add_evidence(EvidenceSpan(evidence_id, document_id, version_id, "line=1", first_line[:500], "kems-materialize-v1", 1.0, run_id))
        store.add_entity(GraphEntity(document_id, "source_document", path.name, document_id, version_id, evidence_id, 1.0, "pending", created_by_run=run_id))
        store.record_extraction_run(run_id=f"{run_id}:{source_sha[:16]}", scenario_id="private-source-materialization", source_sha256=source_sha, model_id="kems-materialize-v1", status="completed", evidence_refs=(evidence_id,), created_at=now)
        entities += 1
        evidence += 1
    return {"run_id": run_id, "documents": len(files), "entities": entities, "evidence": evidence, "graph_db": str(graph_db)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", type=Path, default=Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents")))
    parser.add_argument("--graph-db", type=Path, default=Path(os.environ.get("KEMS_GRAPH_DB", str(Path.home() / ".kems" / "graph.sqlite"))))
    parser.add_argument("--run-id", default=os.environ.get("BOS_MESH_RUN_ID", ""))
    args = parser.parse_args()
    if not args.run_id:
        print(json.dumps({"status": "failed", "error": "missing_run_id"}))
        return 2
    try:
        result = materialize(args.docs_root.expanduser().resolve(), args.graph_db.expanduser().resolve(), args.run_id)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps({"status": "succeeded", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
