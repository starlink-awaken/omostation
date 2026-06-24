"""omo_ingress trail 记录 (从 God Module 拆出, SRP · P60+ 第三步).

_record_trail: AppendOnlyLog 写 ingress-trail.jsonl (OmoTrailRecord schema).
被 omo_ingress + omo_ingress_doc 等复用 (拆 trail 解 doc 循环依赖).
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_io import AppendOnlyLog
from omo.omo_io_schemas import OmoTrailRecord
from omo.omo_ingress_paths import _trail_log_path, _utc_now


def _record_trail(
    omo_dir: Path,
    *,
    actor: str,
    action: str,
    target: str,
    parent_step_id: str,
) -> None:
    trail_record = OmoTrailRecord(
        ts=_utc_now(),
        actor=actor,
        action=action,
        target=target,
        status="ok",
        duration_ms=0,
        parent_step_id=parent_step_id,
    )
    AppendOnlyLog(_trail_log_path(omo_dir)).append(
        trail_record.model_dump(), schema=OmoTrailRecord, sort_keys=True
    )
