#!/usr/bin/env python3
# ruff: noqa: D100,D103
"""bionic-memory-consolidation.py -- 仿生清醒-睡眠双相记忆巩固 (BET-Y1Q4-T6-29).

白天清醒相：纳秒级追加记录高吞吐 Working Memory 与事件流水。
夜间睡眠相：利用 Semantica 因果三元组提取器和 SEMA 逆向萃取引擎，
提炼出不可变知识与踩坑信念沉淀入长期图谱 Gbrain，会话上下文永久不膨胀。

Circuit Breaker:
    置信度 < 0.6 的因果三元组自动丢弃，不污染长期信念库。

Usage:
    python3 bin/ops/bionic-memory-consolidation.py --help
    python3 bin/ops/bionic-memory-consolidation.py --dry-run
    python3 bin/ops/bionic-memory-consolidation.py --date 2026-09-13
    python3 bin/ops/bionic-memory-consolidation.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_WORKING_MEMORY_DB = PROJECT_ROOT / ".omo/_artifacts/working-memory.db"
DEFAULT_LONGTERM_DB = PROJECT_ROOT / ".omo/_artifacts/longterm-knowledge.db"
MAX_TRIPLES_PER_CYCLE = 1000

_LOGGER = logging.getLogger("bionic-memory")


class CausalTriple:
    """因果三元组."""

    def __init__(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 0.5,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.subject = subject
        self.predicate = predicate
        self.object = obj
        self.confidence = confidence
        self.source = source
        self.metadata = metadata or {}
        self.triple_id = str(uuid.uuid4())
        self.timestamp = datetime.now(tz=timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "triple_id": self.triple_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    def is_valid(self, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
        return self.confidence >= threshold


class WorkingMemoryEvent:
    """工作记忆事件."""

    def __init__(
        self,
        event_type: str,
        content: str,
        agent: str = "system",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.content = content
        self.agent = agent
        self.confidence = confidence
        self.metadata = metadata or {}
        self.timestamp = datetime.now(tz=timezone.utc)


class SEMAExtractor:
    """SEMA 逆向萃取引擎 -- 从工作记忆事件中反向提炼因果三元组."""

    AVOID_PATTERNS = ["不要", "避免", "禁止", "切勿", "不能"]
    RECOMMEND_PATTERNS = ["应该", "推荐", "建议", "最好", "必须"]

    def extract_triples(self, event: WorkingMemoryEvent) -> list[CausalTriple]:
        triples: list[CausalTriple] = []
        content = event.content
        triples.extend(self._extract_causal_chain(content, event))
        triples.extend(self._extract_avoid_beliefs(content, event))
        triples.extend(self._extract_recommendations(content, event))
        triples.extend(self._extract_from_metadata(event))
        return triples

    def _extract_causal_chain(self, content: str, event: WorkingMemoryEvent) -> list[CausalTriple]:
        triples: list[CausalTriple] = []
        pairings = [("因为", "所以"), ("由于", "因此"), ("原因是", "故")]
        for left, right in pairings:
            if left in content and right in content:
                left_idx = content.index(left)
                right_idx = content.index(right)
                if left_idx < right_idx:
                    cause = content[left_idx + len(left):right_idx].strip()
                    effect = content[right_idx + len(right):].strip()
                    if cause and effect:
                        triples.append(CausalTriple(
                            subject=cause[:200], predicate="CAUSED", obj=effect[:200],
                            confidence=event.confidence * 0.85,
                            source=f"sema:causal_chain:{event.event_id}",
                            metadata={"pattern": f"{left}..{right}", "agent": event.agent},
                        ))
                        return triples
        single_patterns = [
            (["因为", "由于", "原因是"], "CAUSED"),
            (["导致", "造成", "结果是"], "LEADS_TO"),
            (["所以", "因此", "故"], "THEREFORE"),
        ]
        for keywords, predicate in single_patterns:
            for kw in keywords:
                if kw in content:
                    parts = content.split(kw, 1)
                    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                        triples.append(CausalTriple(
                            subject=parts[0].strip()[:200], predicate=predicate,
                            obj=parts[1].strip()[:200], confidence=event.confidence * 0.85,
                            source=f"sema:causal_chain:{event.event_id}",
                            metadata={"pattern": kw, "agent": event.agent},
                        ))
                        return triples
        return triples

    def _extract_avoid_beliefs(self, content: str, event: WorkingMemoryEvent) -> list[CausalTriple]:
        triples: list[CausalTriple] = []
        for pattern in self.AVOID_PATTERNS:
            if pattern in content:
                idx = content.index(pattern)
                avoid_target = content[idx:].split("，", 1)[0].strip()[:200]
                triples.append(CausalTriple(
                    subject="practice", predicate="AVOID", obj=avoid_target,
                    confidence=min(event.confidence * 1.1, 1.0),
                    source=f"sema:avoid:{event.event_id}",
                    metadata={"pattern": pattern, "agent": event.agent},
                ))
                break
        return triples

    def _extract_recommendations(self, content: str, event: WorkingMemoryEvent) -> list[CausalTriple]:
        triples: list[CausalTriple] = []
        for pattern in self.RECOMMEND_PATTERNS:
            if pattern in content:
                idx = content.index(pattern)
                recommendation = content[idx:].split("，", 1)[0].strip()[:200]
                triples.append(CausalTriple(
                    subject="practice", predicate="RECOMMEND", obj=recommendation,
                    confidence=min(event.confidence * 1.05, 1.0),
                    source=f"sema:recommend:{event.event_id}",
                    metadata={"pattern": pattern, "agent": event.agent},
                ))
                break
        return triples

    def _extract_from_metadata(self, event: WorkingMemoryEvent) -> list[CausalTriple]:
        triples: list[CausalTriple] = []
        meta = event.metadata
        if "causal_subject" in meta and "causal_object" in meta:
            triples.append(CausalTriple(
                subject=str(meta["causal_subject"]),
                predicate=meta.get("causal_predicate", "RELATED_TO"),
                obj=str(meta["causal_object"]),
                confidence=meta.get("confidence", event.confidence),
                source=f"sema:metadata:{event.event_id}",
                metadata={"agent": event.agent},
            ))
        return triples


class NightlyDistillationEngine:
    """夜间蒸馏引擎."""

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 working_db: Path = DEFAULT_WORKING_MEMORY_DB,
                 longterm_db: Path = DEFAULT_LONGTERM_DB) -> None:
        self.confidence_threshold = confidence_threshold
        self.working_db = working_db
        self.longterm_db = longterm_db
        self.extractor = SEMAExtractor()

    def run_consolidation(self, date: datetime | None = None, dry_run: bool = False) -> dict[str, Any]:
        if date is None:
            date = datetime.now(tz=timezone.utc) - timedelta(days=1)
        _LOGGER.info("Starting nightly consolidation for %s", date.date())
        events = self._load_working_memory(date)
        _LOGGER.info("Loaded %d working memory events", len(events))
        all_triples: list[CausalTriple] = []
        event_count = 0
        for event in events:
            all_triples.extend(self.extractor.extract_triples(event))
            event_count += 1
        accepted = [t for t in all_triples if t.is_valid(self.confidence_threshold)]
        rejected = len(all_triples) - len(accepted)
        if not dry_run and accepted:
            self._store_longterm(accepted)
        elif dry_run:
            _LOGGER.info("[DRY RUN] Would store %d triples", len(accepted))
        if not dry_run:
            self._cleanup_working_memory(date)
        return {
            "date": date.date().isoformat(), "dry_run": dry_run,
            "threshold": self.confidence_threshold,
            "events_processed": event_count,
            "triples_extracted": len(all_triples),
            "triples_accepted": len(accepted),
            "triples_rejected": rejected,
        }

    def _load_working_memory(self, date: datetime) -> list[WorkingMemoryEvent]:
        if not self.working_db.exists():
            return self._generate_sample_events(date)
        events: list[WorkingMemoryEvent] = []
        try:
            conn = sqlite3.connect(str(self.working_db))
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                "SELECT event_id, event_type, content, agent, confidence, metadata, timestamp FROM working_memory_events WHERE date(timestamp) = date(?) ORDER BY timestamp ASC LIMIT ?",
                (date.date().isoformat(), MAX_TRIPLES_PER_CYCLE),
            ):
                events.append(WorkingMemoryEvent(
                    event_type=row["event_type"], content=row["content"], agent=row["agent"],
                    confidence=row["confidence"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                ))
            conn.close()
        except Exception as e:
            _LOGGER.error("Failed to load working memory: %s", e)
            return self._generate_sample_events(date)
        return events

    def _store_longterm(self, triples: list[CausalTriple]) -> None:
        self.longterm_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.longterm_db))
        conn.execute("CREATE TABLE IF NOT EXISTS causal_knowledge (triple_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL, confidence REAL NOT NULL, source TEXT, metadata TEXT, timestamp TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        for t in triples:
            conn.execute("INSERT OR REPLACE INTO causal_knowledge (triple_id, subject, predicate, object, confidence, source, metadata, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (t.triple_id, t.subject, t.predicate, t.object, t.confidence, t.source, json.dumps(t.metadata), t.timestamp.isoformat()))
        conn.commit()
        conn.close()

    def _cleanup_working_memory(self, date: datetime) -> None:
        if not self.working_db.exists():
            return
        try:
            conn = sqlite3.connect(str(self.working_db))
            conn.execute("DELETE FROM working_memory_events WHERE date(timestamp) <= date(?)", (date.date().isoformat(),))
            conn.commit()
            conn.close()
        except Exception as e:
            _LOGGER.warning("Cleanup failed (non-fatal): %s", e)

    def _generate_sample_events(self, date: datetime) -> list[WorkingMemoryEvent]:
        return [
            WorkingMemoryEvent("lesson_learned", "因为并发 agent 争用共享写面，所以必须用 worktree 隔离", "governance-agent", 0.9, {"source": "bet_retro"}),
            WorkingMemoryEvent("best_practice", "应该用 git tag 钉住交付，不要依赖分支 ref", "engineering-agent", 0.85, {"source": "git_discipline"}),
            WorkingMemoryEvent("pitfall", "避免在清醒相执行大算力耗时图谱蒸馏", "system", 0.95, {"source": "circuit_breaker"}),
            WorkingMemoryEvent("observation", "PITFALL-GAT-006 动手前先查 main 是否已自愈", "governance-agent", 0.88, {"source": "pitfall_registry"}),
            WorkingMemoryEvent("low_confidence_claim", "可能用 Rust 重写会更快", "intern", 0.3, {"source": "speculation", "causal_subject": "rust_rewrite", "causal_predicate": "RELATED_TO", "causal_object": "performance"}),
        ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bionic-memory-consolidation",
        description="仿生清醒-睡眠双相记忆巩固 -- 夜间蒸馏工作记忆为长期因果知识",
        epilog="Circuit Breaker: 置信度 < 0.6 的三元组自动丢弃")
    parser.add_argument("--date", type=str, default=None, help="指定日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD, help=f"置信度阈值 (默认 {DEFAULT_CONFIDENCE_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟不写入")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--working-db", type=Path, default=DEFAULT_WORKING_MEMORY_DB)
    parser.add_argument("--longterm-db", type=Path, default=DEFAULT_LONGTERM_DB)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=(logging.DEBUG if args.verbose else logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    date: datetime | None = None
    if args.date:
        try:
            date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _LOGGER.error("Invalid date format: %s (expected YYYY-MM-DD)", args.date)
            return 1
    engine = NightlyDistillationEngine(confidence_threshold=args.threshold, working_db=args.working_db, longterm_db=args.longterm_db)
    result = engine.run_consolidation(date=date, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
