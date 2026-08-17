"""时效性管理 — 从 D_KnowledgeIntegration 提取并适配到 kos。

知识时效性检查和管理，支持可配置的 TTL 规则：
- news: 24h
- technical: 7d
- concept: 30d
- fact: 永不过期
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eidos.memory_graph import MemoryGraph  # type: ignore[reportMissingImports]

_log = logging.getLogger(__name__)


# ── 本地数据模型 ──────────────────────────────────────────────


@dataclass
class KnowledgeTriple:
    """知识三元组"""

    subject: str
    predicate: str
    obj: str
    metadata: dict[str, Any]

    def to_tuple(self) -> tuple[str, str, str, dict[str, Any]]:
        return (self.subject, self.predicate, self.obj, self.metadata)


# ── 主类 ─────────────────────────────────────────────────────


class FreshnessManager:
    """知识时效性管理器。

    默认时效性规则：
    - 新闻类: 24小时
    - 技术文档: 7天
    - 概念定义: 30天
    - 历史事实: 永不过期
    """

    # 默认时效性规则（小时）
    DEFAULT_TTL_HOURS = {
        "news": 24,
        "technical": 168,
        "concept": 720,
        "fact": None,
        "default": 168,
    }

    def __init__(self, memory_graph: MemoryGraph, custom_ttl_rules: dict[str, int | None] | None = None) -> None:
        self._fg = memory_graph
        self._ttl_rules = self.DEFAULT_TTL_HOURS.copy()
        if custom_ttl_rules:
            self._ttl_rules.update(custom_ttl_rules)

        self._stats = {
            "checks": 0,
            "fresh": 0,
            "stale": 0,
            "errors": 0,
        }

    def is_fresh(self, subject: str, category: str = "default") -> bool:
        self._stats["checks"] += 1

        try:
            ttl = self._ttl_rules.get(category, self._ttl_rules["default"])

            if ttl is None:
                self._stats["fresh"] += 1
                return True

            results = self._fg.recursive_query(subject, max_depth=1)
            if not results:
                self._stats["stale"] += 1
                return False

            latest_ts = None
            for row in results:
                ts_str = row.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if latest_ts is None or ts > latest_ts:
                            latest_ts = ts
                    except (ValueError, TypeError):
                        continue

            if latest_ts is None:
                self._stats["fresh"] += 1
                return True

            now = datetime.now(UTC)
            age_hours = (now - latest_ts).total_seconds() / 3600

            is_fresh = age_hours < ttl
            if is_fresh:
                self._stats["fresh"] += 1
            else:
                self._stats["stale"] += 1

            return is_fresh

        except (OSError, ValueError, KeyError, RuntimeError) as e:
            self._stats["errors"] += 1
            _log.error(f"Freshness check failed for {subject}: {e}")
            return True

    def filter_by_time_window(self, triples: list[KnowledgeTriple], hours: int) -> list[KnowledgeTriple]:
        if not triples:
            return []

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        filtered = []
        for triple in triples:
            ts_str = triple.metadata.get("timestamp", "")
            if not ts_str:
                filtered.append(triple)
                continue

            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    filtered.append(triple)
            except (ValueError, TypeError):
                filtered.append(triple)

        return filtered

    def get_freshness_stats(self) -> dict[str, Any]:
        total = self._stats["checks"]
        return {
            "total_checks": total,
            "fresh": self._stats["fresh"],
            "stale": self._stats["stale"],
            "errors": self._stats["errors"],
            "freshness_rate": self._stats["fresh"] / max(total, 1),
            "ttl_rules": {k: v if v is not None else "infinite" for k, v in self._ttl_rules.items()},
        }

    def get_stale_knowledge(self, category: str | None = None, limit: int = 100) -> list[str]:
        stale_subjects = []

        try:
            results = self._fg.query("*", "*", "*")
            if not results:
                return []

            subjects = set()
            for row in results:
                subjects.add(row.get("subject", ""))

            for subject in subjects:
                is_fresh = self.is_fresh(subject, category or "default")
                if not is_fresh:
                    stale_subjects.append(subject)
                    if len(stale_subjects) >= limit:
                        break

        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.error(f"Failed to get stale knowledge: {e}")

        return stale_subjects
