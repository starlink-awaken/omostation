#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Ops — 图谱生成 + 陈旧检测 + 重建.

从 ontology/engine.py 抽出 (God Module 拆 wave 5, engine.py 214->~90 纯 main orchestrator).
含 graph/_record_source_mtimes/check_stale/rebuild. main() 留 engine (orchestrator).
依赖 schema + extract/enrich (from 各自模块避免循环).
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path  # type: ignore[import-not-found]
from kos.ontology.enrich import enrich
from kos.ontology.extract import extract
from kos.ontology.schema import (  # type: ignore[no-redef]
    entity_files,
    get_db,
    init_schema,
)


def graph(entity_type: str | None = None) -> dict:
    """Generate Mermaid graph of entity relations."""
    conn = get_db()  # type: ignore[no-untyped-call]
    edges = conn.execute("SELECT source_id,predicate,target_id FROM kos_relations").fetchall()
    entities = {r["entity_id"]: dict(r) for r in conn.execute("SELECT * FROM kos_entities").fetchall()}
    conn.close()

    lines = ["```mermaid", "graph LR"]
    seen = set()
    for s, p, t in edges:
        if entity_type and entities.get(s, {}).get("entity_type") != entity_type:
            continue
        sl = entities.get(s, {}).get("label", s)
        tl = entities.get(t, {}).get("label", t)
        # Truncate long labels for readability
        sl = sl[:20] + ("…" if len(sl) > 20 else "")
        tl = tl[:20] + ("…" if len(tl) > 20 else "")
        key = (sl, tl)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'    "{sl}" -->|{p}| "{tl}"')
    lines.append("```")
    return {"graph": "\n".join(lines), "nodes": len(entities), "edges": len(edges)}


def _record_source_mtimes(conn) -> None:  # type: ignore[no-untyped-def]
    """Persist current entitySources file mtimes into kos_ontology_meta."""
    now = datetime.now().isoformat()
    meta: dict[str, Any] = {"rebuilt_at": now, "sources": {}}
    for fp in entity_files():
        p = Path(fp)
        if p.exists():
            meta["sources"][fp] = p.stat().st_mtime
    conn.execute(
        "INSERT OR REPLACE INTO kos_ontology_meta (key,value) VALUES (?,?)", ("source_mtimes", json.dumps(meta))
    )
    conn.commit()


def check_stale() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Compare entitySources file mtimes to last rebuild. Returns stale info."""
    db_path = Path(get_artifact_path("retrievalDatabase"))
    if not db_path.exists():  # type: ignore[attr-defined]
        return {"stale": True, "reason": "never_built", "changes": []}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)  # type: ignore[no-untyped-call]
    row = conn.execute("SELECT value FROM kos_ontology_meta WHERE key='source_mtimes'").fetchone()
    if not row:
        conn.close()
        return {"stale": True, "reason": "never_built", "changes": []}

    last = json.loads(row["value"])
    changes: list[dict[str, Any]] = []
    for fp in entity_files():
        p = Path(fp)
        if not p.exists():
            changes.append({"file": fp, "status": "missing"})
            continue
        last_mtime = last.get("sources", {}).get(fp)
        curr_mtime = p.stat().st_mtime
        if last_mtime is None or abs(curr_mtime - last_mtime) > 0:
            changes.append({"file": fp, "status": "modified", "last": last_mtime, "current": curr_mtime})

    conn.close()
    return {"stale": bool(changes), "changes": changes, "last_rebuilt": last.get("rebuilt_at")}


def rebuild() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """One-command rebuild: clear + extract + enrich + record mtimes."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    conn.execute("DELETE FROM kos_relations")
    conn.execute("DELETE FROM kos_entities")
    conn.execute("DELETE FROM kos_entity_docs")
    conn.commit()
    conn.close()
    r1 = extract()  # type: ignore[no-untyped-call]
    r2 = enrich()  # type: ignore[no-untyped-call]
    # Record mtimes after successful rebuild
    conn = get_db()  # type: ignore[no-untyped-call]
    _record_source_mtimes(conn)  # type: ignore[no-untyped-call]
    conn.close()
    return {"cleared": True, "extracted": r1["extracted"], "enriched": r2.get("enriched", 0)}
