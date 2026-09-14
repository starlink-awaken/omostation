#!/usr/bin/env python3
# ruff: noqa
"""
KOS LLM Entity Extractor — 利用本地 LLM 从文档中自动抽取实体和关系。

使用 omlx 网关 (qwopus3.6-27b-coder-mlx-8bit) 进行实体抽取，
支持批量处理、增量抽取、置信度评分。

Usage:
    from kos.ontology.llm_extractor import LLMEntityExtractor

    extractor = LLMEntityExtractor()

    # 从单篇文档抽取
    result = extractor.extract_from_document("文档内容...")

    # 批量抽取
    results = extractor.extract_batch([doc1, doc2, doc3])

    # 从已索引文档抽取
    stats = extractor.extract_from_index(limit=10)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class LLMEntityExtractor:
    """LLM 辅助实体抽取器。

    通过本地 omlx 网关调用 LLM，从文档中自动提取实体和关系。
    """

    # omlx 网关配置
    OMLX_URL = os.environ.get("LLM_GATEWAY_URL", "http://100.96.126.35:4000")
    OMLX_API_KEY = "123456"
    DEFAULT_MODEL = "qwopus3.6-27b-coder-mlx-8bit"

    def __init__(self, model: str | None = None, omlx_url: str | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.omlx_url = omlx_url or self.OMLX_URL

    # ── 核心 API ────────────────────────────────────────────

    def extract_from_document(
        self,
        doc_text: str,
        existing_entities: list[dict] | None = None,
    ) -> dict[str, Any]:
        """从单篇文档中抽取实体和关系。

        Args:
            doc_text: 文档文本内容。
            existing_entities: 已有实体列表 (用于去重)。

        Returns:
            {"entities": [...], "relations": [...]}
        """
        prompt = self._build_extraction_prompt(doc_text, existing_entities)
        response = self._call_llm(prompt)
        return self._parse_response(response)

    def extract_batch(
        self,
        docs: list[dict[str, str]],
        batch_size: int = 3,
    ) -> list[dict[str, Any]]:
        """批量抽取文档中的实体和关系。

        Args:
            docs: 文档列表 [{"doc_id": "...", "text": "..."}]
            batch_size: 每次批量处理的文档数。

        Returns:
            抽取结果列表。
        """
        results = []
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            batch_text = self._combine_docs(batch)
            prompt = self._build_batch_extraction_prompt(batch_text, len(batch))
            response = self._call_llm(prompt)
            parsed = self._parse_response(response)
            results.append(parsed)
        return results

    def extract_from_index(
        self,
        limit: int = 10,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """从已索引文档中抽取实体和关系。

        Args:
            limit: 最多处理的文档数。
            domain: 域过滤。

        Returns:
            抽取统计和结果。
        """
        conn = get_connection(get_artifact_path("retrievalDatabase"))

        # 获取文档
        where = ""
        params: list[Any] = []
        if domain:
            where = "WHERE zone = ?"
            params.append(domain)

        docs = conn.execute(
            f"""SELECT doc_id, title, body, zone, canonical_path
                FROM documents {where}
                ORDER BY updated_at DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        conn.close()

        if not docs:
            return {"extracted": 0, "message": "No documents found"}

        # 抽取
        all_entities: list[dict] = []
        all_relations: list[dict] = []
        processed = 0

        for doc in docs:
            text = f"{doc['title'] or ''}\n{doc['body'] or ''}"[:3000]
            if not text.strip():
                continue

            result = self.extract_from_document(text)
            entities = result.get("entities", [])
            relations = result.get("relations", [])

            # 添加来源信息
            for e in entities:
                e["source_doc_id"] = doc["doc_id"]
                e["source_zone"] = doc["zone"]
            for r in relations:
                r["source_doc_id"] = doc["doc_id"]

            all_entities.extend(entities)
            all_relations.extend(relations)
            processed += 1

        return {
            "processed": processed,
            "entities": all_entities,
            "relations": all_relations,
            "entity_count": len(all_entities),
            "relation_count": len(all_relations),
        }

    # ── Prompt 构建 ─────────────────────────────────────────

    def _build_extraction_prompt(
        self,
        text: str,
        existing_entities: list[dict] | None = None,
    ) -> str:
        """构建实体抽取 prompt。"""
        existing_str = ""
        if existing_entities:
            existing_str = "\n\n已有实体（请复用而非新建）:\n"
            for e in existing_entities[:20]:
                existing_str += f"- {e.get('label', '')} ({e.get('type', '')})\n"

        return f"""从以下文档中抽取关键实体和关系。

文档内容:
{text[:3000]}

{existing_str}

请输出 JSON 格式:
{{
  "entities": [
    {{"label": "实体名称", "type": "Person|Organization|Project|Concept|Regulation|Event|Role|Document", "description": "简短描述(50字内)"}}
  ],
  "relations": [
    {{"source": "实体A", "predicate": "works_on|manages|related_to|member_of|reports_to|conforms_to|depends_on|derived_from|described_in|coordinates", "target": "实体B", "confidence": 0.8}}
  ]
}}

规则:
1. 只抽取明确的实体，不要推测
2. type 只能是: Person, Organization, Project, Concept, Regulation, Event, Role, Document
3. predicate 只能是: works_on, manages, related_to, member_of, reports_to, conforms_to, depends_on, derived_from, described_in, coordinates
4. confidence 范围 0.1-1.0
5. 只输出 JSON，不要解释"""

    def _build_batch_extraction_prompt(self, combined_text: str, doc_count: int) -> str:
        """构建批量抽取 prompt。"""
        return f"""从以下 {doc_count} 篇文档中分别抽取关键实体和关系。

{combined_text[:4000]}

为每篇文档输出 JSON 格式:
{{
  "doc_index": 0,
  "entities": [
    {{"label": "实体名称", "type": "Person|Organization|Project|Concept|Regulation|Event|Role|Document", "description": "简短描述"}}
  ],
  "relations": [
    {{"source": "实体A", "predicate": "works_on|manages|related_to|member_of|reports_to|conforms_to|depends_on|derived_from|described_in|coordinates", "target": "实体B"}}
  ]
}}

以 JSON 数组输出，不要解释。"""

    def _combine_docs(self, docs: list[dict[str, str]]) -> str:
        """合并多篇文档为一个文本。"""
        parts = []
        for i, doc in enumerate(docs):
            text = doc.get("text", "")[:1000]
            parts.append(f"--- 文档 {i + 1} ---\n{text}")
        return "\n\n".join(parts)

    # ── LLM 调用 ────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """调用 omlx 网关。"""
        import urllib.request
        import urllib.error

        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个严谨的知识工程师，擅长从文档中抽取结构化实体和关系。只输出 JSON，不要解释。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 2000,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.omlx_url}/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.OMLX_API_KEY}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        except (urllib.error.URLError, Exception) as e:
            return ""

        return ""

    # ── 响应解析 ────────────────────────────────────────────

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析 LLM 响应。"""
        if not response:
            return {"entities": [], "relations": []}

        # 尝试提取 JSON
        json_str = self._extract_json(response)
        if not json_str:
            return {"entities": [], "relations": []}

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {"entities": [], "relations": []}

        # 标准化输出
        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and e.get("label"):
                entities.append(
                    {
                        "label": str(e["label"]).strip(),
                        "type": str(e.get("type", "Concept")).strip(),
                        "description": str(e.get("description", ""))[:200],
                    }
                )

        relations = []
        for r in data.get("relations", []):
            if isinstance(r, dict) and r.get("source") and r.get("target"):
                relations.append(
                    {
                        "source": str(r["source"]).strip(),
                        "predicate": str(r.get("predicate", "related_to")).strip(),
                        "target": str(r["target"]).strip(),
                        "confidence": float(r.get("confidence", 0.5)),
                    }
                )

        return {"entities": entities, "relations": relations}

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON 部分。"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("{") or text.startswith("["):
            # 找到匹配的闭合括号
            depth = 0
            start = 0
            for i, c in enumerate(text):
                if c in "{[":
                    if depth == 0:
                        start = i
                    depth += 1
                elif c in "}]":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
            return text[start:]

        # 尝试从 markdown 代码块中提取
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            return match.group(1).strip()

        return ""


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS LLM Entity Extractor")
    parser.add_argument(
        "action",
        choices=["extract", "batch", "test"],
        default="test",
        nargs="?",
        help="Action: extract/batch/test",
    )
    parser.add_argument("--text", help="Text to extract from")
    parser.add_argument("--limit", type=int, default=5, help="Max documents for batch")
    parser.add_argument("--model", help="LLM model name")
    args = parser.parse_args()

    extractor = LLMEntityExtractor(model=args.model)

    if args.action == "extract":
        if not args.text:
            print("Error: --text required")
            return
        result = extractor.extract_from_document(args.text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "batch":
        result = extractor.extract_from_index(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Test: check if omlx is available
        test_prompt = 'Hello, respond with just: {"status": "ok"}'
        response = extractor._call_llm(test_prompt)
        if response:
            print(json.dumps({"status": "available", "response": response[:200]}, ensure_ascii=False))
        else:
            print(json.dumps({"status": "unavailable", "message": "omlx gateway not running"}))


if __name__ == "__main__":
    main()
