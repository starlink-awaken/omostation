"""
Minerva Vault Sink — Research → L4 Vault 归档适配器

在 Minerva publish 阶段运行, 将研究结果自动写入 Vault Markdown 文件,
使研究内容可通过 KOS 搜索和人类阅读。

设计文档: @驾驶舱/_knowledge/40-design/Minerva-Vault-Sink-Adapter.md
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import yaml

from minerva.audit_store import AuditLogger
from minerva.pipeline.engine import IPipelineStage, ResearchContext

logger = structlog.get_logger(__name__)

# ── 默认配置 ──
DEFAULT_BASE_PATH = Path.home() / "Documents" / "@学习进化"
DEFAULT_RULES: dict[str, str] = {
    "ai-tech": "_storage/知识订阅/技术资讯/",
    "methodology": "_storage/灵感顿悟/",
    "industry-report": "_storage/资料库/报告/",
    # 默认: 未分类走 _storage/（用户手动整理）
}
DEFAULT_TARGET = "_storage/"

# ── ID 生成 ──


def _make_note_id(query: str) -> str:
    """Generate deterministic file slug from query."""
    prefix = hashlib.sha256(query.encode()).hexdigest()[:8]
    date = datetime.now().strftime("%Y%m%d")
    return f"minerva-{date}-{prefix}"


def _classify(ctx: ResearchContext) -> str:
    """Classify research into a vault category.

    Checks ctx.metadata for category hint; falls back to heuristic.
    """
    hint = ctx.metadata.get("category", "")
    if hint in DEFAULT_RULES:
        return DEFAULT_RULES[hint]
    # Heuristic: scan search results for domain keywords
    texts = " ".join(
        (s.get("content", "") or s.get("snippet", "") or "")[:200] for s in (ctx.search_results or [])
    ).lower()
    ai_keywords = {"llm", "transformer", "gpt", "deepseek", "agent", "mcp", "rag", "ai"}
    industry_keywords = {"政策", "医疗", "政务", "报告", "白皮书", "标准", "规范"}
    if any(k in texts for k in ai_keywords):
        return DEFAULT_RULES["ai-tech"]
    if any(k in texts for k in industry_keywords):
        return DEFAULT_RULES["industry-report"]
    return DEFAULT_TARGET


def _generate_frontmatter(note_id: str, ctx: ResearchContext) -> dict[str, Any]:
    """Generate YAML frontmatter for the vault note."""
    return {
        "title": ctx.query[:120],
        "note_id": note_id,
        "type": "research-note",
        "status": "draft",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "source": [s.get("url", "") for s in (ctx.search_results or []) if s.get("url")][:5],
        "minerva": {
            "level": ctx.level.value if hasattr(ctx.level, "value") else str(ctx.level),
            "cost": round(ctx.cost, 4),
            "sources": len(ctx.search_results),
            "entities": len(ctx.entities),
        },
        "tags": [e.get("name", e.get("type", "")) if isinstance(e, dict) else str(e) for e in (ctx.entities or [])][
            :10
        ],
    }


def _generate_body(ctx: ResearchContext) -> str:
    """Generate Markdown body from research context."""
    parts = []

    # Summary
    parts.append("## 摘要\n")
    parts.append(ctx.query[:500] + "\n")

    # Key findings (from report)
    if ctx.report:
        parts.append("\n## 研究报告\n")
        parts.append(ctx.report[:5000] + "\n")

    # Sources
    if ctx.search_results:
        parts.append("\n## 来源\n")
        for i, s in enumerate(ctx.search_results[:10], 1):
            url = s.get("url", "")
            title = s.get("title", url)[:80]
            parts.append(f"{i}. [{title}]({url})\n")

    # Metadata
    parts.append("\n---\n")
    parts.append(f"*由 Minerva Vault Sink 自动生成 · {datetime.now().isoformat()}*\n")

    return "".join(parts)


# ── Pipeline Stage ──


class VaultSinkStage(IPipelineStage):
    """Pipeline stage: write research output to Vault as Markdown.

    Skips gracefully if ctx.report is None (research produced no output).
    """

    name = "vault_sink"

    def __init__(self, base_path: str | Path | None = None) -> None:
        self._base_path = Path(base_path) if base_path else DEFAULT_BASE_PATH

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        if not ctx.report:
            logger.info("vault_sink_skip_no_report", query=ctx.query)
            return ctx

        note_id = _make_note_id(ctx.query)
        category_path = _classify(ctx)
        target_dir = self._base_path / category_path.lstrip("/")
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / f"{note_id}.md"

        # Don't overwrite existing files
        if target_path.exists():
            note_id += "_v2"
            target_path = target_dir / f"{note_id}.md"

        frontmatter = _generate_frontmatter(note_id, ctx)
        body = _generate_body(ctx)

        content = "---\n"
        content += yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        content += "---\n\n"
        content += body

        t0 = time.time()
        target_path.write_text(content, encoding="utf-8")
        duration_ms = (time.time() - t0) * 1000

        # Emit signal via l4-kernel if available
        try:
            from l4_kernel.signals import SignalBus  # type: ignore[reportMissingImports]

            bus = SignalBus()
            bus.emit("vault", "✅", f"研究归档: {ctx.query[:60]}", source="minerva.vault_sink")
        except ImportError:
            pass

        audit = AuditLogger()
        audit.log(
            actor="pipeline",
            action="vault_sink",
            resource=ctx.query[:100],
            result="success",
            detail=f"path={target_path} size={len(content)}",
            duration_ms=duration_ms,
        )

        logger.info(
            "vault_sink_written",
            path=str(target_path),
            category=category_path,
            size=len(content),
            query=ctx.query[:50],
        )

        # Store path in context metadata for downstream stages
        ctx.metadata["vault_sink_path"] = str(target_path)
        return ctx


# ── CLI Test ──
if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        from minerva.triage.router import ResearchLevel, TriageResult

        ctx = ResearchContext(
            query="MCP 协议在 Agent 工具调用中的应用",
            level=ResearchLevel.L1,
            triage=TriageResult(
                level=ResearchLevel.L1, scores={}, model_plan={}, search_plan=[], cost_estimate=0.0, reasoning="test"
            ),
        )
        ctx.report = "MCP (Model Context Protocol) 是 Anthropic 推出的开放标准协议..."
        ctx.search_results = [{"url": "https://modelcontextprotocol.io", "title": "MCP 官网"}]
        ctx.entities = [{"name": "MCP", "type": "protocol"}, {"name": "Anthropic", "type": "organization"}]

        stage = VaultSinkStage()
        result = await stage.execute(ctx)
        print(f"Written to: {result.metadata.get('vault_sink_path')}")
        print(f"Note ID: {_make_note_id(ctx.query)}")
        print(f"Category: {_classify(ctx)}")

    asyncio.run(_test())
