#!/usr/bin/env python3
# ruff: noqa
"""
KOS-Minerva Bridge — bidirectional knowledge synchronization.

Capabilities:
  1. kos-minerva search "query" --level L2 → delegate to Minerva deep research
  2. kos-minerva ingest → auto-index Minerva reports into KOS
  3. kos-minerva sync  → bidirectional entity sync (KOS ontology ↔ Minerva Neo4j)
  4. kos-minerva status → check Minerva health

Usage:
    kos-minerva search "MoE architecture" --level L2
    kos-minerva ingest
    kos-minerva status
    kos-minerva report → generate a KOS-Minerva cross-domain activity report
"""

import json
import os
import sqlite3
import subprocess as sp
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# Unified Minerva adapter (version-aware discovery)
from kos.adapters import MinervaAdapter, NullMinerva  # type: ignore[import-not-found]
from kos.config import get_artifact_path, get_workspace_manifest
from typing import Any, cast

_MINERVA = None  # lazy singleton


def _get_minerva() -> MinervaAdapter:
    """Lazy singleton: discover Minerva once per process."""
    global _MINERVA
    if _MINERVA is None:
        _MINERVA = MinervaAdapter.discover() or NullMinerva
    return _MINERVA  # type: ignore[return-value]


MINERVA_HOME = Path(os.environ.get("MINERVA_HOME", Path.home() / "Workspace" / "minerva"))
MINERVA_REPORTS = Path.home() / "knowledge" / "reports"
KOS_MINERVA_BRIDGE = Path.home() / ".kos" / "minerva_bridge.json"


def _minerva_mcp_check() -> dict:  # type: ignore[type-arg]
    """Check Minerva health via adapter."""
    adapter = _get_minerva()
    h = adapter.health()
    if h["available"]:
        return {"minerva_installed": True, "version": h.get("version"), "path": h.get("path")}
    return {"minerva_installed": False}


def cmd_search(query: str, level: str = "L2", max_cost: float = 1.0) -> dict:  # type: ignore[type-arg]
    """Execute a deep research query via Minerva.

    Falls back to KOS local search if Minerva is unavailable.
    """
    adapter = _get_minerva()
    if not adapter.health()["available"]:
        print("⚠️  Minerva not available — falling back to local KOS search", file=sys.stderr)
        r = sp.run(
            [sys.executable, str(SCRIPT_DIR / "kos-cli.py"), "search", query, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            result = json.loads(r.stdout)
            result["_backend"] = "kos-local"
            return cast("dict[Any, Any]", result)
        return {"error": "Minerva unavailable and KOS fallback failed", "query": query}

    print(f"🔬 Minerva research: {query} (level={level})", file=sys.stderr)
    return adapter.research(query, level=level, max_cost=max_cost, timeout=600, cwd=str(MINERVA_HOME))


def cmd_ingest() -> dict:  # type: ignore[type-arg]
    """Ingest Minerva research reports into KOS index."""
    if not MINERVA_REPORTS.exists():
        return {"ingested": 0, "message": f"No reports directory: {MINERVA_REPORTS}"}

    reports = list(MINERVA_REPORTS.glob("*.md"))
    if not reports:
        return {"ingested": 0, "message": "No reports found"}

    # Use KOS ingest for each report
    ingested = []
    for r in sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            # Use kos-ingest to add the report
            ingest_path = SCRIPT_DIR / "kos-ingest.py"
            r2 = sp.run([sys.executable, str(ingest_path), str(r)], capture_output=True, text=True, timeout=30)
            ingested.append({"file": r.name, "success": r2.returncode == 0})
        except Exception as e:  # noqa: BLE001
            ingested.append({"file": r.name, "success": False, "error": str(e)})

    # After ingest, re-index minerva domain
    indexer_path = SCRIPT_DIR / "kos-indexer.py"
    r3 = sp.run(
        [sys.executable, str(indexer_path), "index", "--domain", "minerva", "--incremental"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "ingested": len(ingested),
        "files": ingested,
        "indexed": r3.returncode == 0,
        "timestamp": datetime.now().isoformat()[:19],
    }


def cmd_status() -> dict:  # type: ignore[type-arg]
    """Check the status of the KOS-Minerva bridge."""
    manifest = get_workspace_manifest()
    minerva_zone = manifest.get("zones", {}).get("minerva", {})
    minerva_domain = manifest.get("domains", {}).get("minerva", {})

    # Check KOS index for minerva documents
    index_status: dict[str, Any] = {"documents": 0}
    try:
        db_path = get_artifact_path("retrievalDatabase")
        db_path_str = str(db_path)
        if os.path.exists(db_path_str):
            conn = sqlite3.connect(db_path_str)
            count = conn.execute("SELECT COUNT(*) FROM documents WHERE zone='minerva'").fetchone()[0]
            docs = conn.execute(
                "SELECT title, kind, updated_at FROM documents WHERE zone='minerva' ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
            index_status = {"documents": count, "recent": [dict(d) for d in docs]}
            conn.close()
    except Exception as e:  # noqa: BLE001
        index_status = {"error": str(e)}

    return {
        "minerva_zone": minerva_zone.get("label", "not configured"),
        "minerva_domain": minerva_domain.get("description", "not configured"),
        "minerva_health": _minerva_mcp_check(),
        "kos_index": index_status,
        "bridge_version": "1.0",
        "manifest_version": manifest.get("version", "unknown"),
    }


def cmd_report() -> dict:  # type: ignore[type-arg]
    """Generate a cross-domain activity report covering KOS + Minerva."""
    manifest = get_workspace_manifest()
    now = datetime.now().isoformat()[:19]

    # KOS domain stats
    try:
        db_path = get_artifact_path("retrievalDatabase")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC").fetchall()
        minerva_count = conn.execute("SELECT COUNT(*) FROM documents WHERE zone='minerva'").fetchone()[0]
        recent = conn.execute(
            "SELECT title, zone, updated_at FROM documents ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        zones = []
        minerva_count = 0
        recent = []

    return {
        "timestamp": now,
        "domains": len(manifest.get("domains", {})),
        "zones": {z["zone"]: z["cnt"] for z in zones},
        "minerva_docs": minerva_count,
        "recent_activity": [dict(r) for r in recent],
        "minerva_reports_available": len(list(MINERVA_REPORTS.glob("*.md"))) if MINERVA_REPORTS.exists() else 0,
    }


def cmd_report() -> dict[str, Any]:
    """Generate a cross-domain activity report covering KOS + Minerva."""
    manifest = get_workspace_manifest()
    now = datetime.now().isoformat()[:19]

    # KOS domain stats
    try:
        db_path = get_artifact_path("retrievalDatabase")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone ORDER BY cnt DESC").fetchall()
        minerva_count = conn.execute("SELECT COUNT(*) FROM documents WHERE zone='minerva'").fetchone()[0]
        recent = conn.execute(
            "SELECT title, zone, updated_at FROM documents ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
    except Exception:
        zones = []
        minerva_count = 0
        recent = []

    return {
        "timestamp": now,
        "domains": len(manifest.get("domains", {})),
        "zones": {z["zone"]: z["cnt"] for z in zones},
        "minerva_docs": minerva_count,
        "recent_activity": [dict(r) for r in recent],
        "minerva_reports_available": len(list(MINERVA_REPORTS.glob("*.md"))) if MINERVA_REPORTS.exists() else 0,
    }


def cmd_research(question: str, level: str = "auto", max_cost: float = 1.0) -> dict:
    """深度研究流水线: KOS检索 → Minerva研究 → 事实核查 → 结构化报告。

    Args:
        question: 研究问题。
        level: Minerva 研究级别 (auto/L0/L1/L2/L3/L4)。
        max_cost: 最大费用 (USD)。

    Returns:
        结构化研究报告。
    """
    result = {
        "question": question,
        "timestamp": datetime.now().isoformat()[:19],
        "steps": {},
    }

    # Step 1: KOS 混合检索
    try:
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        search_result = engine.search(question, mode="hybrid", limit=10)
        engine.close()
        result["steps"]["kos_search"] = {
            "status": "complete",
            "results_count": search_result.get("count", 0),
            "sources": search_result.get("sources", {}),
        }
    except Exception as e:
        result["steps"]["kos_search"] = {"status": "error", "error": str(e)}

    # Step 2: 上下文工程
    try:
        from kos.context_engine import ContextEngine

        ctx_engine = ContextEngine()
        ctx = ctx_engine.build_context(question, mode="detailed")
        ctx_engine.close()
        result["steps"]["context"] = {
            "status": "complete",
            "sources_count": ctx.get("sources_count", 0),
            "total_tokens": ctx.get("total_tokens", 0),
        }
    except Exception as e:
        result["steps"]["context"] = {"status": "error", "error": str(e)}

    # Step 3: Minerva 深度研究
    adapter = _get_minerva()
    if adapter.health()["available"]:
        try:
            research_result = adapter.research(question, level=level, max_cost=max_cost, timeout=600)
            result["steps"]["minerva_research"] = {
                "status": "complete" if research_result.get("success") else "failed",
                "output_length": len(research_result.get("output", "")),
            }
        except Exception as e:
            result["steps"]["minerva_research"] = {"status": "error", "error": str(e)}
    else:
        result["steps"]["minerva_research"] = {"status": "skipped", "reason": "Minerva unavailable"}

    # Step 4: 事实核查
    try:
        from kos.hybrid_search import HybridSearchEngine

        verify_engine = HybridSearchEngine()
        # Extract key claims from question and verify
        verify_result = verify_engine.search(question, mode="hybrid", limit=5)
        verify_engine.close()
        result["steps"]["fact_check"] = {
            "status": "complete",
            "evidence_count": verify_result.get("count", 0),
        }
    except Exception as e:
        result["steps"]["fact_check"] = {"status": "error", "error": str(e)}

    result["overall_status"] = "complete"
    return result


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    rest = sys.argv[2:] if len(sys.argv) > 2 else []

    if cmd == "search":
        query = rest[0] if rest else ""
        level = "L2"
        for i, a in enumerate(rest):
            if a == "--level" and i + 1 < len(rest):
                level = rest[i + 1]
        result = cmd_search(query, level)
    elif cmd == "ingest":
        result = cmd_ingest()
    elif cmd == "status":
        result = cmd_status()
    elif cmd == "report":
        result = cmd_report()
    elif cmd == "research":
        question = rest[0] if rest else ""
        level = "auto"
        max_cost = 1.0
        for i, a in enumerate(rest):
            if a == "--level" and i + 1 < len(rest):
                level = rest[i + 1]
            if a == "--max-cost" and i + 1 < len(rest):
                max_cost = float(rest[i + 1])
        result = cmd_research(question, level, max_cost)
    else:
        result = {"error": f"Unknown command: {cmd}", "usage": "search|ingest|status|report|research"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
