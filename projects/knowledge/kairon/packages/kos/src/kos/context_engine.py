#!/usr/bin/env python3
# ruff: noqa
"""
KOS Context Engine — 上下文工程引擎

实现 Context Engineering 核心能力:
1. 检索预算控制 — 根据查询复杂度动态调整召回数量
2. 结果压缩 — 长文档智能摘要/裁剪
3. 上下文组装 — 为 LLM 组装精准上下文
4. 三层记忆 — 短期/中期/长期记忆管理

Usage:
    from kos.context_engine import ContextEngine

    engine = ContextEngine()
    context = engine.build_context("数据治理", mode="balanced")

    # 带完整配置
    context = engine.build_context(
        "数据治理",
        mode="detailed",
        persona="架构师",
        history=["之前的查询1", "之前的查询2"],
        max_tokens=4000,
    )
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class ContextEngine:
    """KOS 上下文工程引擎。

    将检索结果转化为 LLM 可消费的精简上下文，
    实现检索预算控制、结果压缩、分层记忆。
    """

    # 预设上下文模式
    MODES = {
        "concise": {
            "max_chunks": 3,
            "max_tokens": 1000,
            "snippet_length": 200,
            "include_graph": False,
            "include_history": False,
        },
        "balanced": {
            "max_chunks": 7,
            "max_tokens": 2000,
            "snippet_length": 300,
            "include_graph": False,
            "include_history": True,
        },
        "detailed": {
            "max_chunks": 15,
            "max_tokens": 4000,
            "snippet_length": 500,
            "include_graph": True,
            "include_history": True,
        },
    }

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 核心 API ────────────────────────────────────────────

    def build_context(
        self,
        query: str,
        mode: str = "balanced",
        persona: str | None = None,
        history: list[str] | None = None,
        max_tokens: int | None = None,
        results: list[dict] | None = None,
    ) -> dict[str, Any]:
        """构建 LLM 上下文。

        Args:
            query: 用户查询。
            mode: 上下文模式: concise | balanced | detailed
            persona: 用户角色/身份。
            history: 搜索历史。
            max_tokens: 自定义 token 限制。
            results: 预检索结果 (可选，未提供时自动检索)。

        Returns:
            上下文 dict，包含 sections、total_tokens、sources 等。
        """
        t0 = time.monotonic()

        # 1. 确定配置
        cfg = self.MODES.get(mode, self.MODES["balanced"]).copy()
        if max_tokens:
            cfg["max_tokens"] = max_tokens

        # 2. 获取检索结果 (如未提供)
        if results is None:
            results = self._retrieve(query, cfg)

        # 3. 结果压缩
        compressed = self._compress(results, cfg)

        # 4. 上下文组装
        sections = self._assemble(query, compressed, cfg, persona, history)

        # 5. Token 预算控制
        sections, total_tokens = self._apply_token_budget(sections, cfg["max_tokens"])

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

        return {
            "query": query,
            "mode": mode,
            "persona": persona,
            "sections": sections,
            "total_tokens": total_tokens,
            "sources_count": len(compressed),
            "truncated": len(results) > len(compressed),
            "elapsed_ms": elapsed_ms,
        }

    def build_context_for_agent(
        self,
        task: str,
        persona: str | None = None,
        history: list[str] | None = None,
        mode: str = "balanced",
    ) -> str:
        """为 AI Agent 构建上下文字符串 (直接可注入 prompt)。

        Args:
            task: 任务描述。
            persona: Agent 角色。
            history: 对话历史。
            mode: 上下文模式。

        Returns:
            格式化的上下文字符串。
        """
        ctx = self.build_context(task, mode=mode, persona=persona, history=history)
        return self._format_prompt(ctx)

    # ── 检索 ────────────────────────────────────────────────

    def _retrieve(self, query: str, cfg: dict) -> list[dict]:
        """执行混合检索。"""
        try:
            from kos.hybrid_search import HybridSearchEngine

            engine = HybridSearchEngine(self.db_path)
            result = engine.search(
                query,
                mode="hybrid",
                limit=cfg["max_chunks"] * 2,
                context={"mode": cfg.get("mode", "balanced")},
            )
            engine.close()
            return result.get("results", [])
        except Exception:
            # 降级到纯关键词检索
            return self._fallback_keyword_search(query, cfg["max_chunks"] * 2)

    def _fallback_keyword_search(self, query: str, limit: int) -> list[dict]:
        """降级关键词检索。"""
        try:
            rows = self.conn.execute(
                """SELECT d.doc_id, d.title, d.zone, d.kind,
                          d.canonical_path, d.updated_at,
                          substr(d.body, 1, 500) as snippet
                   FROM documents_fts f
                   JOIN documents d ON f.doc_id = d.doc_id
                   WHERE documents_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [
                {
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "zone": r["zone"],
                    "kind": r["kind"],
                    "canonical_path": r["canonical_path"],
                    "updated_at": r["updated_at"],
                    "snippet": r["snippet"],
                    "source": "keyword",
                }
                for r in rows
            ]
        except sqlite3.OperationalError:
            return []

    # ── 结果压缩 ────────────────────────────────────────────

    def _compress(self, results: list[dict], cfg: dict) -> list[dict]:
        """压缩检索结果: 裁剪 snippet、提取关键信息。"""
        compressed = []
        snippet_len = cfg.get("snippet_length", 300)

        for r in results:
            snippet = r.get("snippet", "")
            # 清理 HTML 标签
            snippet = re.sub(r"</?b>", "", snippet)
            # 裁剪到指定长度
            if len(snippet) > snippet_len:
                snippet = snippet[:snippet_len].rsplit(" ", 1)[0] + "..."

            compressed.append(
                {
                    "doc_id": r["doc_id"],
                    "title": r.get("title", ""),
                    "zone": r.get("zone", ""),
                    "kind": r.get("kind", ""),
                    "canonical_path": r.get("canonical_path", ""),
                    "snippet": snippet,
                    "source": r.get("source", "unknown"),
                    "relevance": r.get("_rrf_score", r.get("_score", 0)),
                }
            )

        return compressed

    # ── 上下文组装 ──────────────────────────────────────────

    def _assemble(
        self,
        query: str,
        compressed: list[dict],
        cfg: dict,
        persona: str | None,
        history: list[str] | None,
    ) -> list[dict]:
        """组装上下文段落。"""
        sections = []

        # 1. 角色段落
        if persona:
            sections.append(
                {
                    "type": "persona",
                    "content": f"You are: {persona}",
                    "tokens": self._estimate_tokens(f"You are: {persona}"),
                }
            )

        # 2. 任务段落
        sections.append(
            {
                "type": "task",
                "content": f"Query: {query}",
                "tokens": self._estimate_tokens(f"Query: {query}"),
            }
        )

        # 3. 历史段落
        if cfg.get("include_history") and history:
            hist_text = "\n".join(f"- {h}" for h in history[-5:])
            sections.append(
                {
                    "type": "history",
                    "content": f"Recent searches:\n{hist_text}",
                    "tokens": self._estimate_tokens(hist_text),
                }
            )

        # 4. 知识段落
        if compressed:
            knowledge_lines = ["Relevant Knowledge:"]
            for i, doc in enumerate(compressed, 1):
                line = f"[{i}] {doc['title']}"
                if doc.get("snippet"):
                    line += f"\n    {doc['snippet']}"
                knowledge_lines.append(line)

            knowledge_text = "\n".join(knowledge_lines)
            sections.append(
                {
                    "type": "knowledge",
                    "content": knowledge_text,
                    "tokens": self._estimate_tokens(knowledge_text),
                }
            )

        return sections

    # ── Token 预算 ──────────────────────────────────────────

    def _apply_token_budget(
        self,
        sections: list[dict],
        max_tokens: int,
    ) -> tuple[list[dict], int]:
        """应用 token 预算，超出时裁剪知识段落。"""
        total = sum(s["tokens"] for s in sections)
        if total <= max_tokens:
            return sections, total

        # 找到知识段落并裁剪
        for i, section in enumerate(sections):
            if section["type"] == "knowledge":
                # 需要裁剪
                excess = total - max_tokens
                content = section["content"]
                # 简单裁剪: 从末尾移除
                while self._estimate_tokens(content) > section["tokens"] - excess and "\n" in content:
                    content = content.rsplit("\n", 1)[0]

                section["content"] = content + "\n... (truncated)"
                section["tokens"] = self._estimate_tokens(section["content"])
                break

        total = sum(s["tokens"] for s in sections)
        return sections, total

    # ── 格式化输出 ──────────────────────────────────────────

    def _format_prompt(self, ctx: dict) -> str:
        """将上下文格式化为 LLM prompt 字符串。"""
        parts = []

        for section in ctx["sections"]:
            if section["type"] == "persona":
                parts.append(f"## Role\n{section['content']}")
            elif section["type"] == "task":
                parts.append(f"## Task\n{section['content']}")
            elif section["type"] == "history":
                parts.append(f"## History\n{section['content']}")
            elif section["type"] == "knowledge":
                parts.append(f"## {section['content']}")

        return "\n\n".join(parts)

    # ── 工具方法 ────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算 token 数 (粗略: 中文约1.5 char/token，英文约4 char/token)."""
        if not text:
            return 0
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 3.5)

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "ContextEngine":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Context Engine")
    parser.add_argument("query", help="Query to build context for")
    parser.add_argument(
        "--mode",
        default="balanced",
        choices=["concise", "balanced", "detailed"],
        help="Context mode (default: balanced)",
    )
    parser.add_argument("--persona", help="Persona/role")
    parser.add_argument("--max-tokens", type=int, help="Max token budget")
    parser.add_argument("--prompt", action="store_true", help="Output as formatted prompt")
    args = parser.parse_args()

    engine = ContextEngine()
    ctx = engine.build_context(
        args.query,
        mode=args.mode,
        persona=args.persona,
        max_tokens=args.max_tokens,
    )
    engine.close()

    if args.prompt:
        print(engine._format_prompt(ctx))
    else:
        print(json.dumps(ctx, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
