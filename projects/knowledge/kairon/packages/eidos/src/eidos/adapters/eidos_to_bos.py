"""eidos_to_bos.py — Reverse adapter: kairon → SharedBrain D-Memory.

Writes kairon knowledge pipeline results back to SharedBrain's memory stores
via Agora MCP (when available) or direct file access (fallback).

Usage:
    adapter = EidosToBosAdapter()
    adapter.knowledge_cards_to_bos_memory(cards, target="minerva")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from os import environ as os_environ
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

# SharedBrain D-Memory paths (for direct file fallback)
SHAREDBRAIN_DATA_DIR = Path(
    os_environ.get(
        "SHAREDBRAIN_DATA",
        str(Path.home() / "Workspace" / "projects" / "SharedBrain" / "data"),
    )
)
AGORA_MCP_ENDPOINT = os_environ.get(
    "AGORA_MCP_ENDPOINT", f"http://localhost:{os_environ.get('AGORA_MCP_HTTP_PORT', '7422')}"
)

BOS_TARGETS = {
    "minerva": "mcp://sharedbrain/memory/minerva",
    "research": "mcp://sharedbrain/memory/research",
    "knowledge": "mcp://sharedbrain/memory/knowledge_graph",
}


@dataclass
class KnowledgeCard:
    id: str
    title: str
    content: str
    source: str
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance_chain: list[dict[str, Any]] = field(default_factory=list)

    def to_bos_entity(self) -> dict[str, Any]:
        return {
            "type": "knowledge_card",
            "id": self.id,
            "attributes": {
                "title": self.title,
                "content": self.content,
                "source": self.source,
                "tags": self.tags,
                "confidence": self.confidence,
            },
            "metadata": self.metadata,
            "provenance": self.provenance_chain,
        }


@dataclass
class DerivationResult:
    task_id: str
    query: str
    derived_facts: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    derivation_chain: list[str] = field(default_factory=list)


class EidosToBosAdapter:
    def __init__(self, mcp_endpoint: str = AGORA_MCP_ENDPOINT) -> None:
        self.mcp_endpoint = mcp_endpoint
        self._agora_available = self._check_agora()

    def knowledge_cards_to_bos_memory(
        self, cards: list[KnowledgeCard], target: str = "minerva"
    ) -> list[dict[str, Any]]:
        if not cards:
            return []
        entities = [card.to_bos_entity() for card in cards]
        if self._agora_available:
            return self._write_via_agora(entities, target)
        else:
            return self._write_via_files(entities, target)

    def derivation_result_to_bos_loop(
        self,
        task_id: str,
        result: DerivationResult,
    ) -> dict[str, Any]:
        payload = {
            "task_id": task_id,
            "type": "derivation_result",
            "query": result.query,
            "facts": result.derived_facts,
            "confidence": result.confidence,
            "chain": result.derivation_chain,
        }
        if self._agora_available:
            return self._mcp_call("mcp://sharedbrain/task/complete", {"task_id": task_id, "result": payload})
        else:
            return self._write_jsonl(payload, "derivation_results.jsonl")

    def index_to_bos_factgraph(
        self,
        index_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not index_entries:
            return []
        if self._agora_available:
            return self._write_via_agora(index_entries, "knowledge")
        else:
            return self._write_via_files(index_entries, "knowledge")

    def _check_agora(self) -> bool:
        try:
            req = Request(f"{self.mcp_endpoint}/health", method="GET")
            resp = urlopen(req, timeout=2)
            return cast("bool", resp.status == 200)
        except Exception:
            _log.warning("Agora MCP not reachable — using file fallback")
            return False

    def _mcp_call(self, tool_uri: str, args: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.mcp_endpoint}/call"
        payload = json.dumps({"tool": tool_uri, "args": args}).encode()
        req = Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            resp = urlopen(req, timeout=10)
            return {"status": resp.status, "body": resp.read().decode()[:500]}
        except Exception as e:
            _log.error(f"MCP call failed: {e}")
            return {"status": 0, "error": str(e)}

    def _write_via_agora(self, entities: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
        bos_target = BOS_TARGETS.get(target, BOS_TARGETS["knowledge"])
        result = self._mcp_call(bos_target, {"entities": entities})
        return [result]

    def _get_store_path(self, target: str) -> Path:
        store_map = {
            "minerva": SHAREDBRAIN_DATA_DIR / "memory" / "minerva",
            "research": SHAREDBRAIN_DATA_DIR / "memory" / "research",
            "knowledge": SHAREDBRAIN_DATA_DIR / "knowledge_graph",
        }
        path = store_map.get(target, store_map["knowledge"])
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_via_files(self, entities: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
        store_path = self._get_store_path(target)
        results = []
        for entity in entities:
            file_path = store_path / f"{entity['id']}.json"
            file_path.write_text(json.dumps(entity, indent=2, ensure_ascii=False))
            results.append({"file": str(file_path), "entity_id": entity["id"]})
        _log.info(f"Wrote {len(entities)} entities to {store_path}")
        return results

    def _write_jsonl(self, record: dict[str, Any], filename: str) -> dict[str, Any]:
        """B-1 P0: 改用 AppendOnlyLog + fcntl_lock (跨进程并发安全).

        旧版裸 `open(file_path, "a")` 存在丢行风险, 跨 kairon + eidos 多进程
        并发时可能产生交错半行. AppendOnlyLog 提供 fcntl.flock 跨进程锁.
        """
        from kairon_utils import AppendOnlyLog, fcntl_lock

        file_path = SHAREDBRAIN_DATA_DIR / filename
        log = AppendOnlyLog(file_path, lock=fcntl_lock(file_path.with_suffix(".lock")))
        log.append(record)
        return {"file": str(file_path), "record_id": record.get("task_id", "")}
