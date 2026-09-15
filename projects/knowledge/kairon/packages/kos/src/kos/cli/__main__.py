#!/usr/bin/env python3
# ruff: noqa
"""
KOS CLI — Knowledge Operating System Command Line Interface (v2.0)

    Usage:
        kos search "query" [--domains gongwen,obsidian] [--limit 10] [--format table|md|json]
        kos ingest <path> [--dry-run] [--verbose]
        kos get <kos_id>
        kos status [--domain <name>] [--format table|json]
        kos domains

    Examples:
        kos search "绩效考核" --domains gongwen
        kos search "平台" --kind note --zone guozhuan --limit 5
        kos ingest ~/Documents/notes --dry-run
        kos status --format table
        kos domains
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from kos.meta_types import FILTERABLE_META_TYPES_HELP  # type: ignore[import-not-found]

SCRIPT_DIR = Path(__file__).resolve().parent
get_workspace_manifest = None  # type: ignore[no-redef]
get_artifact_path = None  # type: ignore[no-redef]
get_vault_ops_dir = None  # type: ignore[no-redef]
try:
    from kos.config import (  # type: ignore[import-not-found, no-redef, assignment]
        get_artifact_path,
        get_vault_ops_dir,
        get_workspace_manifest,
    )
except ImportError:
    try:
        from config import (  # type: ignore[import-not-found, no-redef]
            get_artifact_path,
            get_vault_ops_dir,
            get_workspace_manifest,
        )  # type: ignore[import-not-found, no-redef]
    except ImportError:
        KOS_READY = False
    else:
        KOS_READY = True
else:
    KOS_READY = True

if callable(get_vault_ops_dir):
    VAULT_OPS_DIR = get_vault_ops_dir()
else:
    VAULT_OPS_DIR = Path(os.environ.get("KOS_HOME", str(Path.home() / ".kos")))


def _workspace_manifest() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if callable(get_workspace_manifest):
        manifest = get_workspace_manifest()
        return manifest if isinstance(manifest, dict) else {}
    return {}


def _artifact_path(name: str) -> str | None:  # type: ignore[no-untyped-def]
    if callable(get_artifact_path):
        path = get_artifact_path(name)
        return path if path else None  # type: ignore[reportReturnType]
    return None


# ── Terminal colors (impl 抽到 colors.py, wave 8) ─────────
_is_tty = sys.stdout.isatty()
from kos.cli.colors import *  # noqa: F403  # BOLD/DIM/CYAN/GREEN/YELLOW/RED/MAG


def _get_minerva() -> Any:
    global _MINERVA
    if _MINERVA is None:  # type: ignore[reportUnboundVariable]
        _MINERVA = MinervaAdapter.discover() or NullMinerva  # type: ignore[reportUndefinedVariable]
    return _MINERVA


# ── Output formatters ───────────────────────────────────


def _format_domains_table(data: dict):  # type: ignore[no-untyped-def, type-arg]
    """Human-readable domain list."""
    domains = data.get("domains", [])
    if not domains:
        print(RED("No domains registered."))  # type: ignore[no-untyped-call]
        return
    print(BOLD(f"\n{'Domain':<16} {'Zone':<16} {'Scope':<10} {'Indexable':<10} {'Governance'}"))  # type: ignore[no-untyped-call]
    print(DIM("-" * 80))  # type: ignore[no-untyped-call]
    for d in domains:
        idx = GREEN("✓") if d.get("indexable") else DIM("✗")  # type: ignore[no-untyped-call]
        print(
            f" {CYAN(d['domain']):<15} {d['zone']:<16} {d.get('scope', '-'):<10} {idx:<10} {d.get('governance', '-')}"  # type: ignore[no-untyped-call]
        )
    print(DIM("-" * 80))  # type: ignore[no-untyped-call]
    print(f" {len(domains)} domains\n")


def _format_status_table(data: dict):  # type: ignore[no-untyped-def, type-arg]
    """Human-readable system status."""
    if data is None:
        print("KOS status unavailable — database not found or KOS_HOME not set.")
        print("Set KOS_HOME or run 'kos index' first.")
        return
    db = data.get("retrieval_db", {})
    if db is None:
        db = {}
    domains = data.get("domains", [])

    print(BOLD("\n╔══ KOS System Status ══╗"))  # type: ignore[no-untyped-call]
    print(f" ║ Documents indexed:  {db.get('indexed_documents', 0):>6}        ║")
    print(f" ║ Domains registered: {len(domains):>6}        ║")
    print(BOLD(" ╚" + "═" * 26 + "╝"))  # type: ignore[no-untyped-call]

    if domains:
        print(BOLD(f"\n  {'Domain':<16} {'Zone':<16} {'Documents':>10}"))  # type: ignore[no-untyped-call]
        print(DIM("  " + "-" * 44))  # type: ignore[no-untyped-call]
    for d in domains:
        zone_id = d.get("zone", d.get("domain"))
        if zone_id and db.get("by_zone"):
            count = db.get("by_zone", {}).get(zone_id, 0)
        else:
            count = 0
        print(f"  {CYAN(d['domain']):<15} {zone_id:<16} {count:>10}")  # type: ignore[no-untyped-call]
    print()


def _format_search_table(data: dict):  # type: ignore[no-untyped-def, type-arg]
    """Human-readable search results grouped by zone."""
    q = data.get("query", "")
    results = data.get("results", [])
    count = data.get("count", 0)

    print(BOLD(f"\n🔍  {q}"))  # type: ignore[no-untyped-call]
    print(DIM(f"    {count} results") + "\n")  # type: ignore[no-untyped-call]

    # Group by zone
    by_zone: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_zone.setdefault(r["zone"], []).append(r)

    zone_labels = {
        "workspace": "📂 Workspace 项目代码",
        "docs-cockpit": "🔴 驾驶舱",
        "docs-learning": "🟡 学习进化",
        "docs-work": "💼 工作文档",
        "docs-work-weijian": "🏥 卫健委",
        "docs-work-guozhuan": "🔄 国转中心",
        "docs-personal": "🟢 个人",
        "docs-creative": "🎨 创意创作",
        "docs-public": "🌐 公共",
        "docs-family": "🏠 家庭生活",
        "docs-obsidian-vault": "📝 Obsidian Vault",
        "docs-opc": "⚙️ OPC",
        "config-ai": "⚙️ ~/.ai 配置",
        "config-agents": "🤖 ~/.agents 配置",
        "config-icloud-sharedconf": "☁️ SharedConf",
        "engine-minerva": "🔬 Minerva 引擎",
        "engine-knowledge-engine": "🧠 Knowledge 引擎",
        "engine-l4-kernel": "🧬 L4 Kernel",
        "tools-bin": "🧰 ~/bin",
        "tools-toolbox": "🧰 ~/ToolBox",
        "workspace-spaces": "🌌 Spaces",
        "workspace-runtime": "⏱️ Runtime Data",
        "omo": "📋 OMO 治理层",
        "gongwen": "📂 公文",
        "guozhuan": "📂 国转中心",
        "obsidian": "📂 Obsidian",
        "wpsnote": "📂 WPS Note",
        "family": "📂 家庭共享",
    }

    for zone_id, docs in by_zone.items():
        label = zone_labels.get(zone_id, f"📂 {zone_id}")
        print(BOLD(f"  {label}  ·  {len(docs)} results"))  # type: ignore[no-untyped-call]
        for d in docs:
            title = d.get("title", "Untitled")[:60]
            path = d.get("canonical_path", "")
            # Clean up the path display
            if "::" in path:
                short_path = "::".join(path.split("::")[1:])
            else:
                short_path = path
            if len(short_path) > 55:
                short_path = "…" + short_path[-54:]
            snippet = d.get("snippet", "").replace("<b>", BOLD("")).replace("</b>", "")  # type: ignore[no-untyped-call]
            print(f"    {CYAN(title)}")  # type: ignore[no-untyped-call]
            print(f"    {DIM(short_path)}")  # type: ignore[no-untyped-call]
            if snippet.strip():
                print(f"    {DIM(snippet[:120])}")  # type: ignore[no-untyped-call]
        print()

    footer_parts = [f"{count} results"]
    if len(by_zone) > 1:
        footer_parts.insert(0, f"{len(by_zone)} domains")
    print(DIM("  ──  " + " · ".join(footer_parts) + "  ──\n"))  # type: ignore[no-untyped-call]


def _format_search_md(data: dict):  # type: ignore[no-untyped-def, type-arg]
    """Markdown-formatted search results for export."""
    q = data.get("query", "")
    results = data.get("results", [])
    count = data.get("count", 0)
    lines = [f"# KOS Search: {q}", f"*{count} results*", ""]
    for i, doc in enumerate(results, 1):
        lines.append(f"## {i}. {doc['title']}")
        lines.append(f"**Zone:** {doc['zone']} | **Kind:** {doc.get('kind', '')}")
        lines.append(f"`{doc.get('canonical_path', '')}`")
        snippet = doc.get("snippet", "").replace("<b>", "**").replace("</b>", "**")
        if snippet.strip():
            lines.append(f"> {snippet.strip()}")
        lines.append("")
    print("\n".join(lines))


# ── Commands ────────────────────────────────────────────


def cmd_domains(limit=0, pipeline_output=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if not KOS_READY:
        return {"error": "KOS not available (workspace_config not found)"}
    manifest = _workspace_manifest()  # type: ignore[no-untyped-call]
    domains = manifest.get("domains", {})
    zones = manifest.get("zones", {})
    result = []
    for domain_id, domain_info in domains.items():
        zone_id = domain_info.get("zoneId", domain_id)
        zone = zones.get(zone_id, {})
        result.append(
            {
                "domain": domain_id,
                "label": domain_info.get("description", zone.get("label", "")),
                "zone": zone_id,
                "scope": zone.get("scope", "internal"),
                "indexable": zone.get("indexable", False),
                "governance": zone.get("governance", zone.get("defaultWritePolicy", "")),
            }
        )
    if limit and limit > 0:
        result = result[:limit]
    output = {"domains": result, "count": len(result)}
    if pipeline_output:
        Path(pipeline_output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"Output → {pipeline_output}")
    return output


def cmd_status(domain=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    result = {"domains": cmd_domains()["domains"], "retrieval_db": None}  # type: ignore[no-untyped-call]
    try:
        db_path = _artifact_path("retrievalDatabase")
        if db_path and os.path.exists(str(db_path)):
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone").fetchall()
            result["retrieval_db"] = {
                "path": str(db_path),
                "indexed_documents": count,
                "by_zone": {z["zone"]: z["cnt"] for z in zones},
            }
            conn.close()
    except Exception:
        result["retrieval_db"] = {"status": "not available"}
    if domain:
        result["domains"] = [d for d in result["domains"] if d["domain"] == domain]
    return result


def _tokenize_search_query(query: str) -> str:
    """Prepare a raw query string for FTS5 MATCH.

    - Quoted phrases ("..." or '...') are tokenized with jieba and wrapped as
      FTS5 phrase queries (e.g. "夏明星" -> "夏 明星") so they match the
      tokenized indexed tokens in the correct order.
    - Unquoted segments are tokenized with jieba and joined with OR for better
      Chinese recall, unless they already contain explicit OR/AND operators.
    """
    import re

    def _jieba_tokens(text: str) -> list[str]:
        try:
            import jieba  # type: ignore[import-untyped]

            return [t.strip() for t in jieba.cut(text) if t.strip()]
        except ImportError:
            return [t.strip() for t in text.split() if t.strip()]

    # Split on quoted segments while keeping the delimiters.
    segments = re.split(r"""(["'][^"']*["'])""", query)
    parts: list[str] = []

    for segment in segments:
        if not segment or not segment.strip():
            continue
        segment = segment.strip()

        # Quoted phrase -> tokenize and wrap as FTS5 phrase query.
        if (
            (segment.startswith('"') and segment.endswith('"')) or (segment.startswith("'") and segment.endswith("'"))
        ) and len(segment) > 1:
            inner = segment[1:-1].strip()
            tokens = _jieba_tokens(inner)
            if tokens:
                parts.append('"' + " ".join(tokens) + '"')
            continue

        # Already contains boolean operators -> preserve as-is.
        if " OR " in segment or " AND " in segment:
            parts.append(segment)
            continue

        tokens = _jieba_tokens(segment)
        if len(tokens) > 1:
            parts.append(" OR ".join(tokens))
        elif tokens:
            parts.append(tokens[0])

    return " ".join(parts)


def cmd_search(  # type: ignore[no-untyped-def]
    query,
    domains=None,
    limit=10,
    include_templates=False,
    kind=None,
    zone=None,
    status=None,
    meta_type=None,
    pipeline_output=None,
) -> dict[str, Any]:
    """Cross-domain full-text search with optional metadata filters."""
    if not query or not query.strip():
        print("搜索查询不能为空。用法: kos search '<关键词>'")
        print("例如: kos search '信息化'")
        return {"error": "empty query"}
    if hasattr(pipeline_output, "__fspath__"):
        pipeline_output = str(pipeline_output)
    if pipeline_output:
        result = {"query": query, "type": kind or "", "limit": limit, "results": [], "pipeline": True}
        Path(pipeline_output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Output → {pipeline_output}")
        return result
    try:
        query = _tokenize_search_query(query)
        db_path = _artifact_path("retrievalDatabase")
        if not db_path or not os.path.exists(str(db_path)):
            return {"error": "Retrieval database not found. Run 'kos index' first.", "results": []}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        params = [query]
        extra_where = []

        # Zone/domain filter
        if domains:
            domain_list = [d.strip() for d in domains.split(",")]
            placeholders = ",".join(["?" for _ in domain_list])
            extra_where.append(f"d.zone IN ({placeholders})")
            params.extend(domain_list)
        if zone:
            extra_where.append("d.zone = ?")
            params.append(zone)

        # Kind filter
        if kind:
            extra_where.append("d.kind = ?")
            params.append(kind)

        # Status filter
        if status:
            extra_where.append("d.status = ?")
            params.append(status)

        # Meta type filter
        if meta_type:
            extra_where.append("json_extract(d.metadata_json, '$.meta_type') = ?")
            params.append(meta_type)

        # Template exclusion
        if not include_templates:
            manifest = _workspace_manifest()  # type: ignore[no-untyped-call]
            search_excludes = manifest.get("indexing", {}).get("searchDefaultExclude", [])
            for p in search_excludes:
                extra_where.append(f"d.canonical_path NOT LIKE '%{p}%'")

        where_clause = " AND " + " AND ".join(extra_where) if extra_where else ""
        # Fetch extra results so deduplication still leaves enough matches.
        fetch_limit = max(limit * 3, limit)
        params.append(fetch_limit)  # type: ignore[reportArgumentType]

        # Relevance boosting: CARDS, author-linked, and entity-linked documents rank higher.
        sql = f"""
            WITH scored AS (
                SELECT d.doc_id, d.title, d.kind, d.zone, d.status,
                       d.canonical_path, d.trust_level, d.updated_at,
                       snippet(documents_fts, 1, '<b>', '</b>', '...', 80) AS snippet,
                       f.rank AS fts_rank,
                       CASE WHEN d.canonical_path LIKE '%CARDS/%' THEN 5.0 ELSE 0.0 END AS cards_boost,
                       CASE
                           WHEN d.body LIKE '%author: 夏明星%'
                                OR d.body LIKE '%author_alias: xiamingxing%'
                                OR d.metadata_json LIKE '%夏明星%'
                                OR d.metadata_json LIKE '%xiamingxing%'
                           THEN 10.0 ELSE 0.0
                       END AS author_boost,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM kos_entity_docs ed WHERE ed.doc_id = d.doc_id
                       ) THEN 3.0 ELSE 0.0 END AS entity_boost,
                       CASE
                           WHEN d.updated_at >= date('now', '-7 days') THEN 2.0
                           WHEN d.updated_at >= date('now', '-30 days') THEN 1.0
                           ELSE 0.0
                       END AS freshness_boost
                FROM documents_fts f
                JOIN documents d ON f.doc_id = d.doc_id
                WHERE documents_fts MATCH ? {where_clause}
            )
            SELECT doc_id, title, kind, zone, status, canonical_path,
                   trust_level, updated_at, snippet
            FROM scored
            ORDER BY (fts_rank - cards_boost - author_boost - entity_boost - freshness_boost) ASC, updated_at DESC
            LIMIT ?
        """

        rows = conn.execute(sql, params).fetchall()
        results = [dict(r) for r in rows]
        conn.close()
        results = _deduplicate_search_results(results)[:limit]
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "results": []}


def _zone_priority(zone: str) -> int:
    """Return a numeric priority for a zone; higher values rank first."""
    if zone.startswith("docs-"):
        return 100
    if zone.startswith("engine-"):
        return 80
    if zone.startswith("config-"):
        return 60
    if zone.startswith("tools-"):
        return 40
    if zone == "workspace":
        return 20
    return 0


def _deduplicate_search_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate search results by logical document key.

    CARDS-style files (IDEA-, DEBT-, TASK-, DEL-, RES- prefixes) are
    deduplicated by their unique filename, since the same card may be indexed
    from both docs-cockpit and project workspace zones. Non-CARDS documents
    are kept as-is.
    """
    _cards_id_pattern = re.compile(r"^(IDEA|DEBT|TASK|DEL|RES)-\d{4}-\d{2}-\d{2}-\d+\.md$")
    seen: dict[str, dict[str, Any]] = {}
    for r in results:
        canonical = r.get("canonical_path", "")
        filename = canonical.rsplit("/", 1)[-1] if "/" in canonical else canonical
        if "CARDS/" in canonical or _cards_id_pattern.match(filename):
            key = filename
        else:
            key = canonical
        existing = seen.get(key)
        if existing is None:
            seen[key] = r
            continue
        # Prefer higher-priority zone, then newer updated_at.
        if _zone_priority(r.get("zone", "")) > _zone_priority(existing.get("zone", "")):
            seen[key] = r
        elif r.get("updated_at", "") > existing.get("updated_at", ""):
            seen[key] = r
    return list(seen.values())


def _print_json_output(tool: str, command: str, data) -> None:  # type: ignore[no-untyped-def]
    print(json.dumps({"tool": tool, "command": command, "data": data}, ensure_ascii=False, indent=2))


def cmd_search_web(query: str, limit: int = 10) -> dict:  # type: ignore[type-arg]
    """Search via Minerva's 8 web search backends."""
    adapter = _get_minerva()  # type: ignore[no-untyped-call]
    if not adapter.health()["available"]:
        return {"error": "Minerva required for web search. Install: pip install minerva", "results": []}

    result = adapter.research(query, level="L0", max_cost=0.0, timeout=60)
    if result.get("success"):
        output = result.get("output", "")
        results = []
        for line in output.split("\n"):
            if line.startswith("  ") and "http" in line:
                results.append({"title": line.strip(), "url": "", "source": "minerva-web"})
        return {"query": query, "results": results, "count": len(results), "backend": "minerva"}
    return {"error": result.get("errors", "") or result.get("error", "Minerva L0 failed"), "results": []}


def cmd_research(query: str, level: str = "auto", max_cost: float = 1.0) -> dict:  # type: ignore[type-arg]
    """Execute deep research via Minerva pipeline."""
    adapter = _get_minerva()  # type: ignore[no-untyped-call]
    if not adapter.health()["available"]:
        return {
            "error": "Minerva required for deep research. Install: pip install minerva",
            "query": query,
            "level": level,
            "backend": "minerva",
            "success": False,
        }
    result = adapter.research(query, level=level, max_cost=max_cost, timeout=600)
    return {
        "query": query,
        "level": level,
        "backend": "minerva",
        "success": result.get("success", False),
        "output": result.get("output", ""),
        "error": result.get("errors", "") or result.get("error", ""),
    }


def _format_research_output(data: dict):  # type: ignore[no-untyped-def, type-arg]
    """Display deep research results."""
    q = data.get("query", "")
    level = data.get("level", "auto")
    backend = data.get("backend", "minerva")

    print(BOLD("\n🔬  KOS Deep Research"))  # type: ignore[no-untyped-call]
    print(DIM(f"    Backend: {backend}@{level}"))  # type: ignore[no-untyped-call]
    print(f"    Query: {CYAN(q)}")  # type: ignore[no-untyped-call]

    if data.get("error") and not data.get("output"):
        print(RED(f"\n  Error: {data['error']}\n"))  # type: ignore[no-untyped-call]
        return

    output = data.get("output", "")
    if output:
        print()
        # Pass through the Minerva report
        for line in output.split("\n")[:80]:  # First 80 lines, avoid flooding
            print(f"  {line}")
        if len(output.split("\n")) > 80:
            print(DIM(f"  ... ({len(output.split(chr(10)))} lines total)"))  # type: ignore[no-untyped-call]
    else:
        print(DIM("\n  (no output)\n"))  # type: ignore[no-untyped-call]

    print(DIM(f"\n  {'─' * 40}"))  # type: ignore[no-untyped-call]
    print(DIM(f"  Research complete  ·  {backend}  ·  {level}\n"))  # type: ignore[no-untyped-call]


# ── Main ────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KOS CLI — Knowledge Operating System v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""快速开始:
  kos status                   查看系统状态
  kos domains                  列出所有知识域
  kos search '搜索关键词'       全文搜索
  kos onto list                查看本体实体列表

例子:
  kos search '信息化' --format table
  kos status --format json
  kos domains --limit 10
  kos onto card ROL-xia-mingxing

首次使用: kos init  # 初始化工作区
""",
    )
    parser.add_argument("--json", action="store_true", help="Force JSON output (override --format)")
    sub = parser.add_subparsers(dest="command")

    # domains
    p_domains = sub.add_parser("domains", help="List all knowledge domains")
    p_domains.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_domains.add_argument("--limit", type=int, default=0, help="Max domains (pipeline mode compat)")
    p_domains.add_argument("--pipeline-input", help=argparse.SUPPRESS)
    p_domains.add_argument("--pipeline-output", help=argparse.SUPPRESS)
    p_domains.add_argument(
        "--format", choices=["table", "json"], default="table", help="Output format (default: table)"
    )

    # list (alias for domains)
    p_list_domains = sub.add_parser("list", help="Alias of domains")
    p_list_domains.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_list_domains.add_argument("--limit", type=int, default=0, help="Max domains (pipeline mode compat)")
    p_list_domains.add_argument("--pipeline-input", help=argparse.SUPPRESS)
    p_list_domains.add_argument("--pipeline-output", help=argparse.SUPPRESS)
    p_list_domains.add_argument("--meta-type", help=f"按 MetaType 过滤 ({FILTERABLE_META_TYPES_HELP})")
    p_list_domains.add_argument(
        "--format", choices=["table", "json"], default="table", help="Output format (default: table)"
    )

    # status
    p_status = sub.add_parser("status", help="Show system status")
    p_status.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_status.add_argument("--domain", help="Filter by domain")
    p_status.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")

    # search
    p_search = sub.add_parser("search", help="Cross-domain full-text search")
    p_search.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--domains", help="Comma-separated domain filter (e.g. gongwen,obsidian)")
    p_search.add_argument("--zone", help="Single zone filter")
    p_search.add_argument("--kind", help="Filter by document kind (note, reference, index, etc.)")
    p_search.add_argument("--status", help="Filter by document status (active, draft, archived, etc.)")
    p_search.add_argument("--meta-type", help=f"按 MetaType 过滤 ({FILTERABLE_META_TYPES_HELP})")
    p_search.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_search.add_argument("--templates", action="store_true", help="Include template/reference documents")
    p_search.add_argument("--web", action="store_true", help="Search via Minerva web backends (8 engines)")
    p_search.add_argument("--semantic", action="store_true", help="Hybrid semantic search (LanceDB + FTS5)")
    p_search.add_argument(
        "--mode",
        choices=["keyword", "semantic", "graph", "hybrid"],
        default=None,
        help="Search mode: keyword/semantic/graph/hybrid (default: hybrid if --semantic, else keyword)",
    )
    p_search.add_argument(
        "--context-mode",
        choices=["concise", "balanced", "detailed"],
        default="balanced",
        help="Context mode for result compression (default: balanced)",
    )
    p_search.add_argument("--no-cache", action="store_true", help="Bypass cache")
    p_search.add_argument("--pipeline-input", help=argparse.SUPPRESS)
    p_search.add_argument("--pipeline-output", help=argparse.SUPPRESS)
    p_search.add_argument(
        "--format",
        choices=["table", "md", "json"],
        default="table",
        help="Output format: table=human-readable (default), md=Markdown export, json=raw JSON",
    )

    # research (powered by Minerva)
    p_research = sub.add_parser("research", help="Deep research via Minerva (8 engines + 4 LLMs)")
    p_research.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_research.add_argument("query", help="Research question")
    p_research.add_argument(
        "--level",
        choices=["auto", "L0", "L1", "L2", "L3", "L4"],
        default="auto",
        help="Pipeline level: L0=30s/$0, L1=3min/$0, L2=10min/~$0.30, L3=20min/~$2 (default: auto)",
    )
    p_research.add_argument("--max-cost", type=float, default=1.0, help="Max cost in USD (default: 1.0)")

    # suggest
    p_suggest = sub.add_parser("suggest", help="Search suggestions based on indexed terms")
    p_suggest.add_argument("prefix", help="Partial search term")
    p_suggest.add_argument("--limit", type=int, default=8, help="Max suggestions (default: 8)")

    # related
    p_related = sub.add_parser("related", help="Related searches based on entity co-occurrence")
    p_related.add_argument("query", help="Current search query")
    p_related.add_argument("--limit", type=int, default=6, help="Max related queries (default: 6)")

    # history
    p_history = sub.add_parser("history", help="Search history management")
    p_history.add_argument(
        "action",
        choices=["list", "add", "clear", "popular"],
        default="list",
        nargs="?",
        help="Action: list/add/clear/popular (default: list)",
    )
    p_history.add_argument("--query", help="Query to add (for 'add' action)")

    # monitor
    p_monitor = sub.add_parser("monitor", help="System monitoring and health checks")
    p_monitor.add_argument(
        "action",
        choices=["health", "quality", "performance", "full"],
        default="full",
        nargs="?",
        help="Action: health/quality/performance/full (default: full)",
    )

    # context
    p_context = sub.add_parser("context", help="Build LLM-ready context with budget control")
    p_context.add_argument("query", help="Query to build context for")
    p_context.add_argument(
        "--mode",
        default="balanced",
        choices=["concise", "balanced", "detailed"],
        help="Context mode (default: balanced)",
    )
    p_context.add_argument("--persona", help="Persona/role for context")
    p_context.add_argument("--max-tokens", type=int, help="Max token budget")
    p_context.add_argument("--prompt", action="store_true", help="Output as formatted prompt")

    # memory
    p_memory = sub.add_parser("memory", help="Memory tier management")
    p_memory.add_argument(
        "action",
        choices=["history", "popular", "stats", "clear"],
        default="stats",
        nargs="?",
        help="Action: history/popular/stats/clear (default: stats)",
    )
    p_memory.add_argument("--limit", type=int, default=10, help="Max entries")

    # evolve
    p_evolve = sub.add_parser("evolve", help="Ontology evolution: deduplicate, normalize, detect issues")
    p_evolve.add_argument(
        "action",
        choices=["evolve", "stats", "recommend"],
        default="stats",
        nargs="?",
        help="Action: evolve/stats/recommend (default: stats)",
    )

    # multimodal
    p_multimodal = sub.add_parser("multimodal", help="Process image/audio/video files into searchable content")
    p_multimodal.add_argument("path", help="File or directory to process")
    p_multimodal.add_argument("--zone", default="multimodal", help="Target knowledge zone")
    p_multimodal.add_argument("--recursive", action="store_true", help="Process directory recursively")
    p_multimodal.add_argument("--formats", action="store_true", help="Show supported formats")

    # cache
    p_cache = sub.add_parser("cache", help="Search cache management")
    p_cache.add_argument(
        "action",
        choices=["stats", "clear", "benchmark"],
        default="stats",
        nargs="?",
        help="Action: stats/clear/benchmark (default: stats)",
    )

    # ingest
    p_ingest = sub.add_parser("ingest", help="Scan a directory and index Markdown/JSON/TXT files")
    p_ingest.add_argument("path", help="Directory to scan")
    p_ingest.add_argument("--dry-run", action="store_true", help="Scan only; do not write to storage")
    p_ingest.add_argument("--verbose", action="store_true", help="Print per-file progress")
    p_ingest.add_argument("--schema", help="Eidos Schema 类型 (KnowledgeCard/Fact/OntologyNode)")
    p_ingest.add_argument("--pipeline-input", help=argparse.SUPPRESS)
    p_ingest.add_argument("--pipeline-output", help=argparse.SUPPRESS)

    p_schema = sub.add_parser("import-schema", help="导入 Eidos Schema")
    p_schema.add_argument("schema_file", help="Eidos Schema JSON 文件")

    # onto (pass-through to kos-ontology.py)
    p_onto = sub.add_parser("onto", help="Ontology: extract, card, path, graph, list, rebuild")
    p_onto_sub = p_onto.add_subparsers(dest="onto_cmd")
    p_onto_sub.add_parser("extract", help="Extract entities from source files")
    p_onto_sub.add_parser("infer", help="Infer relations from indexed docs")
    p_onto_sub.add_parser("rebuild", help="Rebuild ontology from scratch")
    p_card = p_onto_sub.add_parser("card", help="Show entity card")
    p_card.add_argument("entity_id", help="Entity ID (e.g. P:xia-mingxing)")
    p_path = p_onto_sub.add_parser("path", help="Find relation path")
    p_path.add_argument("from_id", help="Source entity")
    p_path.add_argument("to_id", help="Target entity")
    p_onto_sub.add_parser("discover", help="Discover implicit connections")
    p_graph = p_onto_sub.add_parser("graph", help="Generate Mermaid graph")
    p_graph.add_argument("--type", dest="entity_type", help="Filter by entity type")
    p_list = p_onto_sub.add_parser("list", help="List entities")
    p_list.add_argument("--type", dest="entity_type", help="Filter by entity type")
    p_list.add_argument("--pipeline-input", help=argparse.SUPPRESS)
    p_list.add_argument("--pipeline-output", help=argparse.SUPPRESS)

    args = parser.parse_args()

    json_output = bool(getattr(args, "json", False))

    # ── Route to command ──
    if args.command in ("domains", "list"):
        result = cmd_domains(limit=getattr(args, "limit", 0), pipeline_output=getattr(args, "pipeline_output", None))  # type: ignore[no-untyped-call]
        fmt = "json" if json_output else getattr(args, "format", "table")
        if json_output or fmt == "json":
            _print_json_output("kos", args.command, result)
            return
        if fmt == "table":
            _format_domains_table(result)
            return
    elif args.command == "status":
        result = cmd_status(domain=getattr(args, "domain", None))  # type: ignore[no-untyped-call]
        fmt = "json" if json_output else getattr(args, "format", "table")
        if fmt == "table":
            _format_status_table(result)
            return
    elif args.command == "search":
        if getattr(args, "web", False):
            result = cmd_search_web(args.query, limit=getattr(args, "limit", 10))
            if result.get("error"):
                print(RED(f"\n  Error: {result['error']}\n"), file=sys.stderr)
                sys.exit(1)
            _format_search_table(result)
            return

        # Determine search mode
        search_mode = getattr(args, "mode", None)
        if search_mode is None:
            if getattr(args, "semantic", False):
                search_mode = "hybrid"
            else:
                search_mode = "keyword"

        # Use HybridSearchEngine for semantic/graph/hybrid modes
        if search_mode in ("semantic", "graph", "hybrid"):
            from kos.hybrid_search import HybridSearchEngine

            engine = HybridSearchEngine()
            result = engine.search(
                args.query,
                mode=search_mode,
                limit=getattr(args, "limit", 10),
                context={"mode": getattr(args, "context_mode", "balanced")},
                use_cache=not getattr(args, "no_cache", False),
            )
            engine.close()
            if result.get("error"):
                print(RED(f"\n  Error: {result['error']}\n"), file=sys.stderr)
                sys.exit(1)
            fmt = "json" if json_output else getattr(args, "format", "table")
            if json_output or fmt == "json":
                _print_json_output("kos", "search", result)
                return
            if fmt == "table":
                _format_search_table(result)
                return
            elif fmt == "md":
                _format_search_md(result)
                return

        # Keyword-only mode: use original cmd_search
        result = cmd_search(
            args.query,
            domains=getattr(args, "domains", None),
            limit=getattr(args, "limit", 10),
            include_templates=getattr(args, "templates", False),
            kind=getattr(args, "kind", None),
            zone=getattr(args, "zone", None),
            status=getattr(args, "status", None),
            meta_type=getattr(args, "meta_type", None),
            pipeline_output=getattr(args, "pipeline_output", None),
        )
        fmt = "json" if json_output else getattr(args, "format", "table")
        if result.get("error"):
            print(RED(f"\n  Error: {result['error']}\n"), file=sys.stderr)  # type: ignore[no-untyped-call]
            sys.exit(1)
        if json_output or fmt == "json":
            _print_json_output("kos", "search", result)
            return
        if fmt == "table":
            _format_search_table(result)
            return
        elif fmt == "md":
            _format_search_md(result)
            return
    elif args.command == "research":
        result = cmd_research(
            args.query,
            level=getattr(args, "level", "auto"),
            max_cost=getattr(args, "max_cost", 1.0),
        )
        _format_research_output(result)
        if result.get("error") and not result.get("output"):
            sys.exit(1)
        return
    elif args.command == "ingest":
        from kos.commands.ingest import ingest_command  # type: ignore[import-not-found]

        result = ingest_command(args)
        if not result.get("ok", True):
            sys.exit(1)
        return
    elif args.command == "import-schema":
        from kos.commands.ingest import import_schema_command

        rc = import_schema_command(args)
        if rc not in (None, 0):
            sys.exit(rc)
        return
    elif args.command == "onto":
        from kos.ontology import engine as onto_engine

        result: Any = {}
        try:
            if args.onto_cmd == "rebuild":
                print("正在重建本体图谱...")
                result = onto_engine.rebuild()
            elif args.onto_cmd == "extract":
                print("正在从源文件提取实体...")
                result = onto_engine.extract()
            elif args.onto_cmd == "infer":
                print("正在从已索引文档中推导关系...")
                result = onto_engine.infer()
            elif args.onto_cmd == "card":
                if not getattr(args, "entity_id", None):
                    print("错误: 请指定 entity_id. 例如: kos onto card ROL-xia-mingxing")
                    sys.exit(1)
                result = onto_engine.card(args.entity_id)
            elif args.onto_cmd == "path":
                if not getattr(args, "from_id", None) or not getattr(args, "to_id", None):
                    print("错误: 请指定 from_id 和 to_id. 例如: kos onto path ID1 ID2")
                    sys.exit(1)
                result = onto_engine.find_path(args.from_id, args.to_id)
            elif args.onto_cmd == "discover":
                result = onto_engine.discover()  # type: ignore[reportAttributeAccessIssue]
            elif args.onto_cmd == "graph":
                result = onto_engine.graph(getattr(args, "entity_type", None))
            elif args.onto_cmd == "list":
                result = onto_engine.list_entities(getattr(args, "entity_type", None))
            else:
                print(f"未知本体子命令: {args.onto_cmd}")
                sys.exit(1)
        except Exception as e:
            print(f"本体操作执行失败: {type(e).__name__}: {str(e)}")
            sys.exit(1)

        # 打印输出
        if args.onto_cmd == "graph" and isinstance(result, dict) and "graph" in result:
            print(result["graph"])
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "suggest":
        from kos.search_features import SearchFeatures

        features = SearchFeatures()
        result = features.suggest(args.prefix, limit=getattr(args, "limit", 8))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "related":
        from kos.search_features import SearchFeatures

        features = SearchFeatures()
        result = features.related(args.query, limit=getattr(args, "limit", 6))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "history":
        from kos.search_features import SearchFeatures

        features = SearchFeatures()
        result = features.history(
            action=getattr(args, "action", "list"),
            query=getattr(args, "query", None),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "monitor":
        from kos.monitoring import KosMonitor

        monitor = KosMonitor()
        action = getattr(args, "action", "full")
        if action == "health":
            result = monitor.index_health()
        elif action == "quality":
            result = monitor.search_quality()
        elif action == "performance":
            result = monitor.performance_metrics()
        else:
            result = monitor.full_report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "context":
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        result = engine.build_context(
            args.query,
            mode=getattr(args, "mode", "balanced"),
            persona=getattr(args, "persona", None),
            max_tokens=getattr(args, "max_tokens", None),
        )
        if getattr(args, "prompt", False):
            print(engine._format_prompt(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        engine.close()
        return
    elif args.command == "memory":
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        action = getattr(args, "action", "stats")
        if action == "history":
            result = memory.get_history(limit=getattr(args, "limit", 10))
        elif action == "popular":
            result = memory.get_popular(limit=getattr(args, "limit", 10))
        elif action == "clear":
            result = memory.clear_history()
        else:
            result = memory.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "cache":
        from kos.cache import SearchCache

        cache = SearchCache()
        action = getattr(args, "action", "stats")
        if action == "clear":
            cache.clear_all()
            result = {"status": "cleared"}
        elif action == "benchmark":
            result = cache.benchmark()  # type: ignore[reportAttributeAccessIssue]
        else:
            result = cache.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "evolve":
        from kos.ontology.evolution import OntologyEvolution

        evo = OntologyEvolution()
        action = getattr(args, "action", "stats")
        if action == "evolve":
            result = evo.evolve()
        elif action == "recommend":
            result = evo.get_recommendations()
        else:
            result = evo.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    elif args.command == "multimodal":
        from kos.multimodal import MultimodalProcessor

        processor = MultimodalProcessor()
        if getattr(args, "formats", False):
            result = processor.supported_formats
        else:
            path = Path(args.path)
            if path.is_file():
                result = processor.process_file(path, zone=args.zone)
            elif path.is_dir():
                result = processor.process_directory(path, zone=args.zone, recursive=args.recursive)
            else:
                result = {"error": f"Path not found: {path}"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    else:
        parser.print_help()
        sys.exit(1)

    # Fallback: JSON output
    if json_output:
        _print_json_output("kos", args.command, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
