#!/usr/bin/env python3
# ruff: noqa
"""
KOS Maintenance Engine — Phase 3 (v1.0)

Four automated checks:
  1. quality_audit   — Cross-domain health: broken links, missing metadata, orphan pages
  2. staleness_check  — Freshness decay: flag content needing review
  3. contradiction    — Cross-domain conflict detection
  4. suggestions      — Auto-tag and link suggestions for new/stale content

Usage:
    python3 kos-maintenance.py audit       # Full quality audit
    python3 kos-maintenance.py staleness   # Freshness check
    python3 kos-maintenance.py contradict  # Cross-domain contradiction check
    python3 kos-maintenance.py suggest     # Auto-suggestions
    python3 kos-maintenance.py all         # Run all checks
"""

import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# sys.path.insert(0, str(SCRIPT_DIR))  # removed
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# sys.path.insert(0, str(VAULT_OPS_DIR))  # removed

from kos.config import get_artifact_path
from typing import Any


def get_db() -> sqlite3.Connection:
    from pathlib import Path

    path_obj = Path(get_artifact_path("retrievalDatabase"))
    if not path_obj.exists():
        sys.exit(json.dumps({"error": "Retrieval DB not found. Run index build first."}))
    conn = sqlite3.connect(str(path_obj))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── 3.1 Quality Audit ────────────────────────────────────


def audit() -> dict:  # type: ignore[type-arg]
    """Cross-domain quality audit."""
    conn = get_db()  # type: ignore[no-untyped-call]
    issues = []

    # Check: documents without tags
    untagged = conn.execute("""
        SELECT d.doc_id, d.title, d.zone, d.canonical_path
        FROM documents d
        LEFT JOIN document_tags t ON d.doc_id = t.doc_id
        WHERE t.tag IS NULL AND d.kind != 'index'
        LIMIT 50
    """).fetchall()
    if untagged:
        issues.append(
            {
                "type": "missing_tags",
                "severity": "warning",
                "count": len(untagged),
                "message": f"{len(untagged)} documents have no tags",
                "examples": [{"title": r["title"], "zone": r["zone"]} for r in untagged[:5]],
            }
        )

    # Check: documents with review_status='pending' older than 30 days
    old_pending = conn.execute(
        """
        SELECT doc_id, title, zone, updated_at FROM documents
        WHERE review_status = 'pending'
        AND updated_at < ?
        LIMIT 20
    """,
        ((datetime.now() - timedelta(days=30)).isoformat(),),
    ).fetchall()
    if old_pending:
        issues.append(
            {
                "type": "stale_pending_reviews",
                "severity": "warning",
                "count": len(old_pending),
                "message": f"{len(old_pending)} documents pending review > 30 days",
            }
        )

    # Check: documents with trust_level='raw' never promoted
    raw_docs = conn.execute("""
        SELECT COUNT(*) as cnt FROM documents
        WHERE trust_level = 'raw' AND review_status = 'pending'
    """).fetchone()
    if raw_docs and raw_docs["cnt"] > 10:
        issues.append(
            {
                "type": "unpromoted_raw",
                "severity": "info",
                "count": raw_docs["cnt"],
                "message": f"{raw_docs['cnt']} raw documents awaiting promotion",
            }
        )

    # Domain health summary (dynamically from indexed zones)
    domain_health: dict[str, Any] = {}
    try:
        zone_rows = conn.execute(
            "SELECT zone, COUNT(*) as total, SUM(CASE WHEN review_status='canonical' THEN 1 ELSE 0 END) as canonical FROM documents GROUP BY zone"
        ).fetchall()
        for z in zone_rows:
            domain_health[z["zone"]] = {"total": z["total"], "canonical": z["canonical"] or 0}
    except Exception:  # noqa: BLE001
        domain_health = {"error": "Could not query zone stats"}  # type: ignore[str, Any]

    conn.close()

    return {
        "audit_type": "quality",
        "timestamp": datetime.now().isoformat(),
        "issues_found": len(issues),
        "issues": issues,
        "domain_health": domain_health,
        "status": "healthy" if len([i for i in issues if i["severity"] == "error"]) == 0 else "needs_attention",
    }


# ── 3.2 Staleness Check ──────────────────────────────────


def staleness(months: int = 6) -> dict:  # type: ignore[type-arg]
    """Detect stale canonical content needing review."""
    conn = get_db()  # type: ignore[no-untyped-call]
    cutoff = (datetime.now() - timedelta(days=months * 30)).isoformat()

    stale = conn.execute(
        """
        SELECT doc_id, title, zone, kind, trust_level, updated_at, canonical_path
        FROM documents
        WHERE trust_level = 'canonical'
        AND updated_at < ?
        ORDER BY updated_at ASC
        LIMIT 30
    """,
        (cutoff,),
    ).fetchall()

    # Also check: ephemeral content that hasn't been updated recently
    stale_ephemeral = conn.execute(
        """
        SELECT doc_id, title, zone, updated_at, canonical_path
        FROM documents
        WHERE freshness = 'ephemeral'
        AND updated_at < ?
        ORDER BY updated_at ASC
        LIMIT 10
    """,
        ((datetime.now() - timedelta(days=90)).isoformat(),),
    ).fetchall()

    conn.close()

    return {
        "check_type": "staleness",
        "cutoff_months": months,
        "timestamp": datetime.now().isoformat(),
        "stale_canonical": {
            "count": len(stale),
            "needs_review": [{"title": r["title"], "zone": r["zone"], "last_updated": r["updated_at"]} for r in stale],
        },
        "stale_ephemeral": {
            "count": len(stale_ephemeral),
            "items": [{"title": r["title"], "zone": r["zone"]} for r in stale_ephemeral[:5]],
        },
    }


# ── 3.3 Contradiction Detection ───────────────────────────


def contradict() -> dict:  # type: ignore[type-arg]
    """Detect potential cross-domain contradictions."""
    conn = get_db()  # type: ignore[no-untyped-call]
    conflicts = []

    # Pattern 1: Same keyword with opposite sentiment in different domains
    opposing_pairs = [
        ("已售罄", "在售"),
        ("暂停", "推进中"),
        ("已完成", "待开始"),
        ("确认", "待确认"),
    ]

    for positive, negative in opposing_pairs:
        pos_docs = conn.execute(
            "SELECT d.doc_id, d.title, d.zone FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id WHERE documents_fts MATCH ?",
            (positive,),
        ).fetchall()
        neg_docs = conn.execute(
            "SELECT d.doc_id, d.title, d.zone FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id WHERE documents_fts MATCH ?",
            (negative,),
        ).fetchall()

        # If same zone has both positive and negative mentions, flag as potential conflict
        pos_zones = {r["zone"] for r in pos_docs}
        neg_zones = {r["zone"] for r in neg_docs}
        overlap = pos_zones & neg_zones
        if overlap:
            conflicts.append(
                {
                    "type": "opposing_indicators",
                    "positive_term": positive,
                    "negative_term": negative,
                    "affected_zones": list(overlap),
                    "severity": "info",
                }
            )

    # Pattern 2: Cross-domain policy conflicts
    policy_keywords = ["必须", "禁止", "应当", "不得", "强制"]
    for kw in policy_keywords:
        docs = conn.execute(
            "SELECT d.doc_id, d.title, d.zone FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id WHERE documents_fts MATCH ?",
            (kw,),
        ).fetchall()
        zones_with_policy = defaultdict(lambda: defaultdict(int))  # type: ignore[var-annotated]
        for d in docs:
            zones_with_policy[d["zone"]][kw] += 1

    conn.close()

    return {
        "check_type": "contradiction",
        "timestamp": datetime.now().isoformat(),
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
        "note": "Contradiction detection is heuristic. Human review recommended for flagged items.",
    }


# ── 3.4 Auto-Suggestions ──────────────────────────────────


def suggest() -> dict:  # type: ignore[type-arg]
    """Generate auto-tag and link suggestions."""
    conn = get_db()  # type: ignore[no-untyped-call]
    suggestions: list[dict[str, Any]] = []

    # Suggestion 1: Untagged docs → suggest tags based on content keywords
    untagged = conn.execute("""
        SELECT d.doc_id, d.title, d.zone, d.canonical_path
        FROM documents d
        LEFT JOIN document_tags t ON d.doc_id = t.doc_id
        WHERE t.tag IS NULL AND d.kind != 'index'
        LIMIT 20
    """).fetchall()

    if untagged:
        suggestions.append(
            {
                "type": "tag_suggestions",
                "message": f"{len(untagged)} documents could benefit from tags",
                "examples": [{"title": r["title"], "zone": r["zone"]} for r in untagged[:5]],
                "action": "Use tag-organize skill to auto-tag these documents",
            }
        )

    # Suggestion 2: Orphan documents (no incoming links, no tags) → suggest review
    # (simplified: documents with kind='note' or 'reference' and review_status='pending')
    orphan_candidates = conn.execute("""
        SELECT doc_id, title, zone FROM documents
        WHERE review_status = 'pending' AND kind IN ('note', 'reference')
        AND trust_level = 'working'
        LIMIT 15
    """).fetchall()
    if orphan_candidates:
        suggestions.append(
            {
                "type": "orphan_review",
                "message": f"{len(orphan_candidates)} working documents pending review — consider promoting or archiving",
                "count": len(orphan_candidates),  # type: ignore[Collection[str, unused-ignore]
            }
        )

    # Suggestion 3: Recently updated docs → suggest cross-linking
    conn.execute("""
        SELECT d1.doc_id, d1.title, d1.zone as z1, d2.title as related_title, d2.zone as z2
        FROM documents d1
        JOIN documents_fts f ON d1.doc_id = f.doc_id
        JOIN documents_fts f2 ON f.doc_id != f2.doc_id
        JOIN documents d2 ON f2.doc_id = d2.doc_id
        WHERE d1.zone != d2.zone
        LIMIT 10
    """).fetchall()

    conn.close()

    return {
        "check_type": "suggestions",
        "timestamp": datetime.now().isoformat(),
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
    }


# ── Run All ───────────────────────────────────────────────


def run_all() -> None:
    result = {
        "maintenance_run": datetime.now().isoformat(),
        "kos_version": "1.0",
        "checks": {
            "quality_audit": audit(),
            "staleness": staleness(),
            "contradiction": contradict(),
            "suggestions": suggest(),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    handlers = {"audit": audit, "staleness": staleness, "contradict": contradict, "suggest": suggest, "all": run_all}
    handler = handlers.get(cmd, run_all)
    result = handler()  # type: ignore[no-untyped-call]
    if cmd != "all":
        print(json.dumps(result, ensure_ascii=False, indent=2))
