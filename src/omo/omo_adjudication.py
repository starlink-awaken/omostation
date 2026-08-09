"""omo_adjudication.py — AdjudicationRecorded 事件与裁决存储 (BET-Y1Q1-T4-01).

结果面: 系统第一次能记录"人类接受了什么、改了什么".
守 ADR-0372: 决策日志入 bos://memory/mos/*.
关联: decision_outcome.decision_id (do-NNNN).

存储: .omo/_delivery/outcomes/adjudications.jsonl (append-only).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import AppendOnlyLog, fcntl_lock
from .omo_paths import DELIVERY_DIR

import yaml

VERDICT_CONFIDENCE_DELTA: dict[str, float] = {
    "accepted": +0.05,
    "modified": -0.05,
    "rejected": -0.20,
}

OUTCOMES_DIR = DELIVERY_DIR / "outcomes"
ADJUDICATIONS_LOG = OUTCOMES_DIR / "adjudications.jsonl"
ADJUDICATION_SCHEMA = "adjudication/v1"
VALID_VERDICTS = frozenset({"accepted", "modified", "rejected"})


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _log() -> AppendOnlyLog:
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    return AppendOnlyLog(
        path=ADJUDICATIONS_LOG,
        lock=fcntl_lock(ADJUDICATIONS_LOG.with_suffix(".lock")),
    )


@dataclass
class AdjudicationRecord:
    """人类裁决记录 — 关联回 decision_outcome.decision_id."""

    id: str
    decision_id: str
    verdict: str
    adjudicated_at: str = field(default_factory=_utc_now)
    edit_diff: str = ""
    time_spent_seconds: float = 0.0
    adjudicator: str = ""
    notes: str = ""
    schema_version: str = ADJUDICATION_SCHEMA


class AdjudicationStore:
    """裁决存储 — append-only JSONL + 查询 + 闭环信念修正."""

    def __init__(
        self,
        log: AppendOnlyLog | None = None,
        mos_manager: Any | None = None,
    ) -> None:
        self._log = log or _log()
        self._mos_manager = mos_manager
        self._counter: int | None = None

    def _next_id(self) -> str:
        records = self._log.read_all()
        n = len(records) + 1
        return f"adj-{n:04d}"

    def record(
        self,
        *,
        decision_id: str,
        verdict: str,
        edit_diff: str = "",
        time_spent_seconds: float = 0.0,
        adjudicator: str = "",
        notes: str = "",
    ) -> str:
        """记录一条裁决, 返回 adjudication id.

        Args:
            decision_id: 关联的 decision_outcome.id (do-NNNN).
            verdict: accepted | modified | rejected.
            edit_diff: 人类修改的 diff (modified 时建议填).
            time_spent_seconds: 审阅耗时.
            adjudicator: 裁决人标识.
            notes: 自由文本备注.
        """
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}"
            )
        adj_id = self._next_id()
        record = AdjudicationRecord(
            id=adj_id,
            decision_id=decision_id,
            verdict=verdict,
            edit_diff=edit_diff,
            time_spent_seconds=time_spent_seconds,
            adjudicator=adjudicator,
            notes=notes,
        )
        self._log.append(asdict(record), sort_keys=True)
        self._apply_belief_feedback(decision_id, verdict)
        self._update_capability_calibration(decision_id, verdict)
        return adj_id

    def _apply_belief_feedback(self, decision_id: str, verdict: str) -> None:
        """闭环: 裁决 → 信念置信度修正 (best-effort, 不抛异常)."""
        if self._mos_manager is None:
            return
        try:
            outcome = self._mos_manager.get_decision_outcome(decision_id)
            if outcome is None:
                return
            topic = outcome.get("decision_type", "")
            belief = self._mos_manager.find_belief_by_topic(topic)
            if belief is None:
                return
            delta = VERDICT_CONFIDENCE_DELTA.get(verdict, 0.0)
            if delta != 0.0:
                self._mos_manager.update_belief_confidence(
                    belief["id"],
                    delta,
                    reason=f"adjudication:{verdict} decision={decision_id}",
                )
        except Exception:
            pass

    def _update_capability_calibration(self, decision_id: str, verdict: str) -> None:
        """闭环: 裁决 → capability_calibration 自动更新 (BET-Y1Q2-T4-01).

        公式: calibration = accepted_as_is / invocations (per capability).
        """
        if self._mos_manager is None:
            return
        try:
            outcome = self._mos_manager.get_decision_outcome(decision_id)
            if outcome is None:
                return
            capability = outcome.get("decision_type", "unknown")

            records = self._log.read_all()
            total = 0
            accepted = 0
            for r in records:
                rid = r.get("decision_id", "")
                if not rid:
                    continue
                rel = self._mos_manager.get_decision_outcome(rid)
                if rel and rel.get("decision_type") == capability:
                    total += 1
                    if r.get("verdict") == "accepted":
                        accepted += 1

            if total == 0:
                return
            calibration = accepted / total
            self._mos_manager.record_capability_calibration(
                capability_ref=capability,
                success_rate=round(calibration, 4),
                sample_size=total,
                last_run_id=decision_id,
            )

            OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
            summary_file = OUTCOMES_DIR / "capability_calibration_summary.yaml"
            existing: dict = {}
            if summary_file.exists():
                with open(summary_file, encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            existing[capability] = {
                "calibration": round(calibration, 4),
                "accepted": accepted,
                "total": total,
                "updated_at": _utc_now(),
            }
            with open(summary_file, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)

            self._check_autonomy_ladder(capability, verdict)
        except Exception:
            pass

    def _check_autonomy_ladder(self, capability: str, verdict: str) -> None:
        """闭环: 裁决 → 自主性阶梯升降级检查 (BET-Y1Q4-T3-01)."""
        try:
            from .omo_autonomy_level import AutonomyLadder

            ladder = AutonomyLadder()
            ladder.record_adjudication(capability, verdict)
        except Exception:
            pass

    def query(
        self,
        *,
        decision_id: str | None = None,
        verdict: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询裁决记录."""
        records = self._log.read_all()
        if decision_id:
            records = [r for r in records if r.get("decision_id") == decision_id]
        if verdict:
            records = [r for r in records if r.get("verdict") == verdict]
        return records[-limit:]

    def stats(self) -> dict[str, int]:
        """裁决统计 — 按 verdict 计数."""
        records = self._log.read_all()
        counts: dict[str, int] = {"total": len(records)}
        for v in sorted(VALID_VERDICTS):
            counts[v] = sum(1 for r in records if r.get("verdict") == v)
        return counts


__all__ = [
    "ADJUDICATIONS_LOG",
    "ADJUDICATION_SCHEMA",
    "OUTCOMES_DIR",
    "VALID_VERDICTS",
    "VERDICT_CONFIDENCE_DELTA",
    "AdjudicationRecord",
    "AdjudicationStore",
]
