#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Enrich — 实体文档关联 + 本地 LLM 语义丰富.

从 ontology/engine.py 抽出 (God Module 拆 wave 3, engine.py 639->~510).
含 enrich() (FTS 文档关联) + _enrich_with_local_llm() (omlx 网关语义摘要).
依赖 schema 组 (get_db/init_schema).
"""

import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from kos.ontology.schema import (  # type: ignore[no-redef]
    get_db,
    init_schema,
)

logger = structlog.get_logger(__name__)


def enrich() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Link entities to indexed documents via text search."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    entities = conn.execute("SELECT entity_id,label,aliases FROM kos_entities").fetchall()
    enriched = 0

    for e in entities:
        label = e["label"]
        aliases = json.loads(e["aliases"] or "[]")
        search_terms = [label] + [a for a in aliases if a != label]

        for term in search_terms[:3]:  # max 3 terms per entity
            # Sanitize: FTS5 doesn't like special chars, use simple word matching
            safe_term = re.sub(r'[.()（）\-*"~]', " ", term)[:60].strip()
            if len(safe_term) < 2:
                continue
            try:
                docs = conn.execute(
                    "SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ? LIMIT 10", (safe_term,)
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for d in docs:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO kos_entity_docs (entity_id,doc_id,relevance) VALUES (?,?,?)",
                        (e["entity_id"], d["doc_id"], 0.5),
                    )
                    enriched += 1
                except Exception:  # noqa: BLE001
                    logger.error("Unexpected exception caught", exc_info=True)
                    pass

    # 3. Optional local LLM semantic enrichment via omlx gateway (MBP coder model)
    llm_enriched = _enrich_with_local_llm(conn, now)
    if llm_enriched > 0:
        print(f"Successfully enriched {llm_enriched} entities using local omlx/coder model.")

    conn.commit()
    conn.close()
    return {"enriched": enriched + llm_enriched, "timestamp": now}


import os

# 推理端点: 默认 omlxc 网关 (tailscale), 可通过 LLM_GATEWAY_URL 覆盖
OMLX_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://100.96.126.35:4000")
OMLX_CHAT_URL = f"{OMLX_GATEWAY_URL}/v1/chat/completions"
OMLX_MODELS_URL = f"{OMLX_GATEWAY_URL}/v1/models"


def _enrich_with_local_llm(conn: sqlite3.Connection, now: str) -> int:
    """利用本地 omlx 推理网关 (http://localhost:4000) 自动为缺失描述的实体进行源码及文档级语义丰富化"""
    import urllib.error
    import urllib.request

    # 1. 快速探测本地 omlx 网关是否在线
    gateway_url = OMLX_CHAT_URL
    try:
        req = urllib.request.Request(
            OMLX_MODELS_URL, headers={"Authorization": "Bearer sk-omlx-admin"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status != 200:
                return 0
    except Exception:
        # 网关不在线，直接静默退出
        return 0

    # 2. 查找所有描述缺失或仅有默认占位描述的实体
    query = """
        SELECT entity_id, entity_type, label, source_file, description
        FROM kos_entities
        WHERE description IS NULL
           OR description = ''
           OR description LIKE 'Subproject in workspace%'
        LIMIT 5
    """
    targets = conn.execute(query).fetchall()
    if not targets:
        return 0

    enriched_count = 0
    for t in targets:
        eid = t["entity_id"]
        etype = t["entity_type"]
        label = t["label"]
        src_file = t["source_file"]

        context = ""
        if src_file and Path(src_file).is_file():
            try:
                with open(src_file, "r", encoding="utf-8") as f:
                    context = f.read(3000)
            except Exception:
                pass

        prompt = f"请为实体 '{label}' (类型: {etype}) 生成一段 100 字以内的专业语义摘要。\n"
        if context:
            prompt += f"以下是该实体的物理源码或配置片段，请基于它进行总结，不要有虚构内容：\n\n```\n{context}\n```\n"
        else:
            prompt += "请直接给出该实体在软件工程或治理规范中的常规定义与定位。"

        payload = {
            "model": "coder",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个严谨的产品架构师，请用中文简明扼要地总结，直接输出结果，不要有前言和废话。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            post_req = urllib.request.Request(
                gateway_url,
                data=data,
                headers={"Content-Type": "application/json", "Authorization": "Bearer sk-omlx-admin"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=12.0) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    summary = choices[0].get("message", {}).get("content", "").strip()
                    if summary:
                        conn.execute(
                            "UPDATE kos_entities SET description=?, updated_at=? WHERE entity_id=?", (summary, now, eid)
                        )
                        enriched_count += 1
        except Exception as ex:
            print(f"  ⚠️  Local LLM enrichment failed for {eid}: {ex}", file=sys.stderr)

    return enriched_count
