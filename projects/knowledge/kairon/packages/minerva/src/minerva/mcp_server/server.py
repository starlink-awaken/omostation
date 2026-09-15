"""
Minerva MCP Server — Expose deep research as Model Context Protocol tools.

Implements 5 Super Tools (Dropbox Dash pattern):
- research_now: Execute research immediately
- research_schedule: Schedule recurring research
- research_watch: Watch topics for new content
- knowledge_search: Search existing knowledge base
- knowledge_ingest: Ingest new content into knowledge base

Any MCP-compatible agent (Claude Code, Codex, Cursor) can call these.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from typing import Any, cast

from fastmcp import FastMCP

from minerva.executor.executor import ExecutionMode, ResearchExecutor, ResearchTask

FORMAT_VERSION = "minerva-v1"

# --- Create MCP server ---

mcp = FastMCP(
    "Minerva Deep Research",
    mask_error_details=True,
)

# Global executor (initialized at startup via init_server()).
# Design note: singleton pattern is intentional — loading LLM/search/pipeline/KB
# at MCP connect time would add 5-10s latency to every tool call.
executor: ResearchExecutor | None = None


class DegradedExecutor:
    """Lightweight executor with only knowledge store access.

    Used when full executor (LLM+pipeline) fails to initialize. Provides
    knowledge_search and knowledge_ingest; research tools return clear errors.
    """

    def __init__(self, kb: Any) -> None:
        self.kb = kb

    async def get_status(self, task_id: str) -> None:
        return None

    async def execute_now(self, task: Any) -> None:
        raise RuntimeError("Research not available in degraded mode. Only knowledge_search and knowledge_ingest work.")

    async def schedule(self, task: Any) -> None:
        raise RuntimeError("Schedule not available in degraded mode.")

    async def watch(self, task: Any) -> None:
        raise RuntimeError("Watch not available in degraded mode.")


def _ensure_executor() -> Any:
    """Return executor or raise with clear guidance."""
    if executor is not None:
        return executor
    raise RuntimeError(
        "Minerva MCP server not initialized. Start with: minerva-mcp or configure your MCP client to launch minerva."
    )


# ── 辅助函数 ─────────────────────────────────────────
# _ok() / _error() 集中管理返回格式。
# 注意：_ok() 的 data 参数中不内建 format_version，
# 要求每个工具函数显式传递（以便 SOP 的 AST 静态检测能在工具函数体中找到字面量）。


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


def _normalize_domains(domains: str | list[str] | None) -> list[str]:
    if isinstance(domains, list):
        values = domains
    else:
        values = (domains or "").split(",")
    normalized: list[str] = []
    for value in values:
        domain = str(value).strip().lower()
        if domain and domain not in normalized:
            normalized.append(domain)
    return normalized


def _infer_domain(result: dict, requested_domains: list[str]) -> str | None:
    explicit = str(result.get("domain", "")).strip().lower()
    if explicit:
        return explicit
    haystack = " ".join(str(result.get(key, "")) for key in ("path", "title", "snippet", "source", "source_id")).lower()
    for domain in requested_domains:
        if domain in haystack:
            return domain
    match = re.search(r"(agentmesh|gbrain|kairon|minerva|kos|metaos|iris)", haystack)
    return match.group(1) if match else None


def build_cross_domain_report(query: str, results: list[dict], domains: list[str]) -> dict:
    normalized = _normalize_domains(domains)
    grouped: dict[str, list[dict]] = {domain: [] for domain in normalized}
    for result in results:
        domain = _infer_domain(result, normalized)
        if domain in grouped:
            grouped[domain].append(result)

    domain_briefs: list[dict] = []
    for domain in normalized:
        entries = grouped[domain]
        if not entries:
            domain_briefs.append(
                {
                    "domain": domain,
                    "status": "gap",
                    "result_count": 0,
                    "summary": f"No evidence found yet for {domain}.",
                    "highlights": [],
                }
            )
            continue
        highlights = [
            {
                "title": entry.get("title", ""),
                "snippet": entry.get("snippet", ""),
                "path": entry.get("path", ""),
            }
            for entry in entries[:3]
        ]
        summary_parts = [entry.get("snippet") or entry.get("title", "") for entry in entries[:2]]
        domain_briefs.append(
            {
                "domain": domain,
                "status": "covered",
                "result_count": len(entries),
                "summary": " ".join(part for part in summary_parts if part).strip(),
                "highlights": highlights,
            }
        )
    covered = [brief["domain"] for brief in domain_briefs if brief["status"] == "covered"]
    missing = [brief["domain"] for brief in domain_briefs if brief["status"] == "gap"]
    synthesis = (
        f"Query '{query}' is covered by {', '.join(covered)}."
        if covered
        else f"Query '{query}' does not yet have cross-domain coverage."
    )
    return {
        "query": query,
        "domains": normalized,
        "domain_briefs": domain_briefs,
        "synthesis": synthesis,
        "missing_domains": missing,
    }


# ============================================================
# Tool: research_now
# ============================================================


@mcp.tool()
async def research_now(
    query: str,
    level: str = "auto",
    max_cost: float = 1.0,
) -> dict:
    """Execute deep research immediately. Auto-routes to appropriate pipeline level.

    Use when: You or the user need an answer NOW.
    Levels: L0=30s/$0, L1=3min/$0, L2=10min/~$0.30, L3=20min/~$2, L4=30min+/$5-10.
    Default 'auto' classifies the query and picks the right level.

    Args:
        query: The research question to investigate
        level: Pipeline level — auto|L0|L1|L2|L3|L4 (default: auto)
        max_cost: Maximum cost in USD for this research (default: 1.0)
    """
    task = ResearchTask(
        id=str(uuid.uuid4())[:8],
        query=query,
        mode=ExecutionMode.IMMEDIATE,
        level=level,
        max_cost=max_cost,
    )

    try:
        result = await _ensure_executor().execute_now(task)
    except Exception as exc:
        return _error(str(exc))

    # 构建 Eidos KnowledgeCard 兼容数据
    try:
        from minerva.knowledge.adapters import research_result_to_card

        eidos_card = research_result_to_card(result)
    except Exception:
        eidos_card = None

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "completed",
            "task_id": result.task_id,
            "summary": result.summary,
            "report_path": result.report_path,
            "cost": result.cost,
            "completed_at": result.completed_at,
            "eidos_card": eidos_card,
        }
    )


# ============================================================
# Tool: research_schedule
# ============================================================


@mcp.tool()
async def research_schedule(
    query: str,
    cron: str,
    level: str = "auto",
    notify: str = "mcp",
) -> dict:
    """Schedule recurring research. Runs on a cron schedule.

    Use when: You want daily/weekly briefings on a topic.
    Examples: "0 8 * * *" = every day at 8am, "0 9 * * 1" = every Monday at 9am

    Args:
        query: Research question to investigate on schedule
        cron: Cron expression for execution timing
        level: Pipeline level (default: auto)
        notify: Notification method — mcp|none (default: mcp)
    """
    task = ResearchTask(
        id=str(uuid.uuid4())[:8],
        query=query,
        mode=ExecutionMode.SCHEDULED,
        level=level,
        max_cost=1.0,
        cron_expr=cron,
        notify=notify,
    )

    try:
        task_id = await _ensure_executor().schedule(task)
    except Exception as exc:
        return _error(str(exc))

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "scheduled",
            "task_id": task_id,
            "cron": cron,
            "next_run": "calculated_at_runtime",
        }
    )


# ============================================================
# Tool: research_watch
# ============================================================


@mcp.tool()
async def research_watch(
    topic: str,
    sources: str = "arxiv",
    check_interval: str = "daily",
    max_cost_per_run: float = 1.0,
) -> dict:
    """Watch a topic for new content. Automatically researches when new content appears.

    Use when: You want to track a research area and be notified of developments.

    Args:
        topic: Topic to watch (e.g., "transformer architecture", "CRISPR")
        sources: Comma-separated sources — arxiv,github_trending,techcrunch,reddit,zhihu
        check_interval: How often to check — hourly|daily|weekly (default: daily)
        max_cost_per_run: Max cost per triggered research (default: 1.0)
    """
    task = ResearchTask(
        id=str(uuid.uuid4())[:8],
        query=f"[WATCH] {topic}",
        mode=ExecutionMode.WATCH,
        level="L2",
        max_cost=max_cost_per_run,
        topic=topic,
        sources=[s.strip() for s in sources.split(",")],
        check_interval=check_interval,
    )

    try:
        task_id = await _ensure_executor().watch(task)
    except Exception as exc:
        return _error(str(exc))

    return _ok(
        {
            "format_version": FORMAT_VERSION,
            "action": "watching",
            "task_id": task_id,
            "topic": topic,
            "sources": task.sources,
            "check_interval": check_interval,
        }
    )


# ============================================================
# Tool: knowledge_search
# ============================================================


@mcp.tool()
async def knowledge_search(
    query: str,
    mode: str = "hybrid",
) -> dict:
    """Search the existing knowledge base.

    Modes:
    - hybrid: All search methods combined (RRF fused) — best for most queries
    - fulltext: Keyword search via SQLite FTS5
    - semantic: Vector similarity search via LanceDB
    - graph: Entity relationship traversal
    - timeline: Time-ordered entity/event search

    Args:
        query: What to search for
        mode: Search mode (default: hybrid)
    """
    try:
        results = await _ensure_executor().kb.search(query, mode)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "query": query,
                "mode": mode,
                "results": results[:20],  # Top 20
                "total": len(results),
            }
        )
    except Exception as exc:
        return _error(str(exc))


@mcp.tool()
async def cross_domain_research(
    query: str,
    domains: str = "agentmesh,gbrain,kairon",
    mode: str = "hybrid",
    limit: int = 8,
) -> dict:
    """Synthesize evidence across requested domains with gap visibility."""
    try:
        requested_domains = _normalize_domains(domains)
        results = await _ensure_executor().kb.search(query, mode)
        report = build_cross_domain_report(query, list(results)[: max(limit, 1)], requested_domains)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "cross_domain_research",
                "query": query,
                "mode": mode,
                "domains": report["domains"],
                "domain_briefs": report["domain_briefs"],
                "synthesis": report["synthesis"],
                "missing_domains": report["missing_domains"],
            }
        )
    except Exception as exc:
        return _error(str(exc))


# ============================================================
# Tool: minerva_bfs_search
# ============================================================


@mcp.tool()
async def minerva_bfs_search(
    query: str,
    depth: int = 3,
    max_branches: int = 5,
) -> dict:
    """Best-First Tree Search — deep iterative branching research.

    Decomposes a research question into sub-questions, explores each in
    parallel (fan-out), scores and prunes branches, and continues the
    best branches deeper. Synthesizes all results into a merged output.

    Args:
        query: Research question to investigate
        depth: Maximum exploration depth (default: 3)
        max_branches: Maximum parallel branches per level (default: 5)
    """
    try:
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.engine import SearchEngine

        # Create SearchEngine from config (lazy — errors are non-fatal)
        try:
            from minerva.config import MinervaConfig

            config = MinervaConfig.load()
            engine = SearchEngine(
                {
                    "searxng_url": config.search.searxng_url,
                    "exa_api_key": config.search.exa_api_key,
                }
            )
        except Exception:
            engine = SearchEngine()

        bfs = BFTSearch(
            search_engine=engine,
            max_depth=min(depth, 10),  # Cap depth at 10
            max_branches=min(max_branches, 20),  # Cap branches at 20
        )
        result = await bfs.search(query)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "query": query,
                "depth": depth,
                "branches_explored": result["branches_explored"],
                "depth_reached": result["depth_reached"],
                "pruned_count": result["pruned_count"],
                "synthesis": result["synthesis"],
            }
        )
    except Exception as exc:
        return _error(str(exc))


# ============================================================
# Tool: knowledge_ingest
# ============================================================


@mcp.tool()
async def knowledge_ingest(
    source: str,
    source_type: str = "auto",
) -> dict:
    """Ingest new content into the knowledge base.

    Supported types: url, pdf, markdown, code, or auto (detect from source).

    Args:
        source: URL or local file path to ingest
        source_type: Content type (default: auto)
    """
    try:
        result = await _ensure_executor().kb.ingest(source, source_type)

        # 构建 Eidos KnowledgeCard 兼容数据
        try:
            from minerva.knowledge.adapters import ingest_to_card

            eidos_card = ingest_to_card(
                source=source,
                source_type=result.get("source_type", source_type),
            )
        except Exception:
            eidos_card = None

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "ingested",
                "source": source,
                "type": source_type,
                "entities_extracted": result.get("entity_count", 0),
                "relations_found": result.get("relation_count", 0),
                "eidos_card": eidos_card,
            }
        )
    except Exception as exc:
        return _error(str(exc))


# ============================================================
# Tool: knowledge_closed_loop
# ============================================================


@mcp.tool()
async def knowledge_closed_loop(
    query: str,
    level: str = "auto",
    confirmed: bool = False,
    fresh: bool = False,
) -> dict:
    """Knowledge closed-loop: search KOS → research → save → audit.

    First searches KOS for existing research results (unless fresh=True).
    If not found, runs the minerva pipeline and saves results to KOS
    as a CONCEPT entity with zone=minerva_research.

    Args:
        query: Research question to investigate
        level: Pipeline level — auto|L0|L1|L2|L3|L4 (default: auto)
        confirmed: L2 confirmation for batch/rebuild operations
        fresh: Skip KOS cache, force fresh research
    """
    try:
        from minerva.knowledge_closed_loop import KnowledgeClosedLoop

        loop = KnowledgeClosedLoop(_ensure_executor())
        return await loop.search(
            query=query,
            level=level,
            confirmed=confirmed,
            fresh=fresh,
        )
    except Exception as exc:
        return _error(str(exc))


# ============================================================
# Server lifecycle
# ============================================================


def init_server(executor_instance: ResearchExecutor) -> None:
    """Initialize the MCP server with an executor."""
    global executor
    executor = executor_instance


def _check_llm_health() -> tuple[bool, str]:
    """Check LLM service availability at startup — local Ollama + cloud API keys.

    Returns:
        Tuple of (available: bool, message: str).
    """
    messages = []
    local_ok = False
    cloud_keys = []

    # 本地 Ollama / OpenAI 兼容检测
    try:
        from minerva.config import MinervaConfig

        config = MinervaConfig.load()
        import httpx

        resp = httpx.get(
            f"{config.llm.base_url}/models",
            timeout=5.0,
        )
        if resp.status_code == 200:
            models = resp.json()
            available = [m.get("id", "") for m in models.get("data", [])]
            pref = config.llm.models.get("agent", "")
            if available:
                msg = f"  LLM health OK: {len(available)} model(s) available"
                if pref in available:
                    msg += f" (preferred: {pref})"
                else:
                    msg += f" [WARN] preferred model '{pref}' not found among available models"
                messages.append(msg)
                local_ok = True
            else:
                messages.append("  [WARN] LLM endpoint responded but no models listed")
        else:
            messages.append(f"  [WARN] LLM health check returned HTTP {resp.status_code}")
    except Exception as e:
        err_msg = str(e)
        if "ConnectError" in type(e).__name__ or "Connection refused" in err_msg:
            messages.append(f"  [WARN] LLM {config.llm.base_url} unreachable — check Ollama is running")  # type: ignore[reportPossiblyUnboundVariable]
        else:
            messages.append(f"  [WARN] LLM health check failed: {e}")

    # 云端 API Key 检查
    cloud_providers = {
        "DeepSeek (V4 Pro / 1M ctx)": "DEEPSEEK_API_KEY",
        "GLM (128K ctx fallback)": "GLM_API_KEY",
        "LongCat (Flash backup)": "LONGCAT_API_KEY",
    }
    for provider_name, env_key in cloud_providers.items():
        if os.environ.get(env_key):
            cloud_keys.append(provider_name)
        else:
            messages.append(f"  [NOTE] {provider_name}: no {env_key} env var")

    if cloud_keys:
        messages.append(f"  Cloud LLM keys found: {', '.join(cloud_keys)}")
    else:
        messages.append("  [WARN] No cloud LLM API keys configured — L3/L4 research unavailable")

    # 总体状态
    overall = local_ok or bool(cloud_keys)
    return overall, "\n".join(messages)


def main() -> None:
    """Entry point: minerva-mcp — auto-initializes executor with graceful degradation."""
    sys.stderr.write("Minerva MCP Server starting...\n")

    # Try full executor init first (LLM + pipeline + KB + cost_guard)
    try:
        from minerva.init import create_default_executor

        executor = create_default_executor(kos_save_enabled=True)
        init_server(executor)
        sys.stderr.write("  Full executor initialized: research + search + ingest all available.\n")
    except Exception as e:
        sys.stderr.write(f"  [WARNING] Full executor init failed: {e}\n")
        sys.stderr.write("  Trying degraded mode: knowledge_search + knowledge_ingest only...\n")
        # Degraded mode: create a minimal executor with just the knowledge store
        try:
            from minerva.knowledge.store import SQLiteKnowledgeStore

            kb = SQLiteKnowledgeStore()
            init_server(cast("ResearchExecutor", DegradedExecutor(kb)))
            sys.stderr.write("  Degraded mode ready: knowledge_search + knowledge_ingest available.\n")
        except Exception as e2:
            sys.stderr.write(f"  [ERROR] Degraded init also failed: {e2}\n")
            sys.stderr.write("  No tools available.\n")
            mcp.run()
            return

    # LLM health check (non-blocking: degraded mode already handled above)
    available, msg = _check_llm_health()
    sys.stderr.write(msg + "\n")
    if not available:
        sys.stderr.write(
            "  All LLM paths unavailable: research tools will fail until a local or cloud LLM is reachable.\n"
        )
        sys.stderr.write("  Hint: start Ollama with 'ollama serve', or set DEEPSEEK_API_KEY/GLM_API_KEY env vars.\n")

    sys.stderr.write("Configure your MCP client to connect to this server.\n")
    mcp.run()


if __name__ == "__main__":
    main()
