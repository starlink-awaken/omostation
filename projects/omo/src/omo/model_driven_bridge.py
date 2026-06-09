"""model_driven → AppendOnlyLog 桥接 (Round 5 P2).

把 model_driven 的 PipelineTracker 事件流接入 .omo/_knowledge/pipeline-events.jsonl.
由 AppendOnlyLog 统一物理写盘, 事件按 ts 排序可查, 失败不影响主流程.

用法:
    from omo.model_driven_bridge import make_pipeline_tracker_with_log
    tracker = make_pipeline_tracker_with_log(entity_id="my-domain")
    # 后续 t.start_phase(...) 自动写一行到 pipeline-events.jsonl

设计:
  - 不直接 import model_driven (避免硬耦合)
  - 提供 factory 函数, consumer 显式 wire on_event
  - 失败时 try/except 兜底, 业务不受影响
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog

_WORKSPACE = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
)
DEFAULT_PIPELINE_LOG_PATH = _WORKSPACE / ".omo" / "_knowledge" / "pipeline-events.jsonl"


def make_pipeline_event_logger(
    log_path: Path = DEFAULT_PIPELINE_LOG_PATH,
) -> AppendOnlyLog:
    """返回一个写 pipeline 事件到 .jsonl 的 AppendOnlyLog 实例."""
    return AppendOnlyLog(log_path)


def wire_pipeline_tracker(
    tracker: Any,
    log_path: Path = DEFAULT_PIPELINE_LOG_PATH,
) -> Any:
    """给一个 PipelineTracker 实例挂上事件钩子, 写 log_path.

    Args:
        tracker: 已有 PipelineTracker 实例 (没设 on_event).
        log_path: 落点 .jsonl (默认 .omo/_knowledge/pipeline-events.jsonl).

    Returns:
        同一个 tracker, 已注入 on_event 钩子. 链式调用友好.
    """
    log = make_pipeline_event_logger(log_path)

    def on_event(event: dict[str, Any]) -> None:
        try:
            log.append(event)
        except Exception:
            pass  # 落盘失败不影响主流程 (AppendOnlyLog 自身已 fsync)

    # 直接挂到 _on_event (避免改 tracker API 假设)
    tracker._on_event = on_event
    return tracker


def make_pipeline_tracker_with_log(
    entity_id: str,
    entity_type: str = "",
    log_path: Path = DEFAULT_PIPELINE_LOG_PATH,
) -> Any:
    """Factory: 一步创建带 on_event 的 PipelineTracker.

    Returns:
        model_driven.lifecycle.pipeline.PipelineTracker 实例.
    """
    from model_driven.lifecycle.pipeline import PipelineTracker

    log = AppendOnlyLog(log_path)

    def on_event(event: dict[str, Any]) -> None:
        try:
            log.append(event)
        except Exception:
            pass

    return PipelineTracker(
        entity_id=entity_id,
        entity_type=entity_type,
        on_event=on_event,
    )


__all__ = (
    "DEFAULT_PIPELINE_LOG_PATH",
    "make_pipeline_event_logger",
    "wire_pipeline_tracker",
    "make_pipeline_tracker_with_log",
)
