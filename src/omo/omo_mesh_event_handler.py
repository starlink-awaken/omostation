"""omo_mesh_event_handler.py — R3 Mesh→OMO 自适应闭环

订阅 bus-foundation 总线上的 Mesh 节点状态变更事件：
  - 「mesh:node:status_changed」 由 compute_mesh.pool.ComputePool 发布
  - 「swarm:worker:hatched / terminated」 由 swarm_engine._compat 发布

收到事件后，通过 OMO 治理路径（omo_audit / omo_state）将最新状态
安全写回 M1 元模型 YAML，遵循 SSOT 铁律：
  - 不直接进行 raw file write。
  - 所有落盘操作必须通过 _safe_write_back() 走 omo_audit 校验门。

使用方法（在 OMO daemon 或启动脚本中调用一次）：
    from omo.omo_mesh_event_handler import register_mesh_event_handlers
    register_mesh_event_handlers()
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from .omo_io import write_yaml_atomic
from .omo_shared import load_yaml

logger = logging.getLogger("omo.mesh_event_handler")

# M1 compute engine YAML 目录
_M1_COMPUTE_ENGINE_DIR = Path(
    "~/Workspace/projects/ecos/src/ecos/ssot/mof/m1/compute_engine"
).expanduser()

# 事件处理全局锁（防止并发竞态写）
_write_lock = threading.Lock()

# 延迟写入缓冲区：node_id → 最新待写状态（防止状态抖动）
_pending_writes: dict[str, dict[str, Any]] = {}
_pending_timer: threading.Timer | None = None
_DEBOUNCE_SECONDS = 3.0  # 状态变更防抖：3s 内无新事件才写盘


# ─────────────────────────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────────────────────────


def register_mesh_event_handlers() -> None:
    """订阅所有 mesh / swarm 事件并注册处理器。

    此函数是幂等的，可重复调用。
    """
    try:
        from bus_foundation import subscribe  # type: ignore[import]
    except ImportError:
        logger.warning(
            "bus-foundation not available; mesh event handlers NOT registered. "
            "Install bus-foundation to enable R3 adaptive feedback loop."
        )
        return

    @subscribe("mesh:node:status_changed")
    def _on_node_status_changed(envelope: Any) -> None:
        payload = getattr(envelope, "payload", {})
        node_id = payload.get("node_id", "")
        new_status = payload.get("status", "")
        if node_id and new_status:
            _schedule_write(node_id, {"status": new_status, "last_seen": time.time()})

    @subscribe("swarm:worker:hatched")
    def _on_worker_hatched(envelope: Any) -> None:
        payload = getattr(envelope, "payload", {})
        worker_id = payload.get("worker_id", "")
        if worker_id:
            _schedule_write(
                f"swarm-{worker_id}",
                {
                    "status": "ACTIVE",
                    "task_type": payload.get("task_type", ""),
                    "pid": payload.get("pid", 0),
                    "hatched_at": time.time(),
                },
            )

    @subscribe("swarm:worker:terminated")
    def _on_worker_terminated(envelope: Any) -> None:
        payload = getattr(envelope, "payload", {})
        worker_id = payload.get("worker_id", "")
        if worker_id:
            _schedule_write(
                f"swarm-{worker_id}",
                {
                    "status": "TERMINATED",
                    "reason": payload.get("reason", ""),
                    "eu_consumed": payload.get("eu_consumed", 0.0),
                    "terminated_at": time.time(),
                },
            )

    logger.info(
        "Mesh event handlers registered (topics: mesh:node:status_changed, swarm:worker:*)"
    )


# ─────────────────────────────────────────────────────────────────
# 内部实现
# ─────────────────────────────────────────────────────────────────


def _schedule_write(node_id: str, new_fields: dict[str, Any]) -> None:
    """防抖写入调度：合并短时间内的多次状态更新后再落盘。"""
    global _pending_timer

    with _write_lock:
        # 合并待写字段（后来覆盖先来）
        _pending_writes.setdefault(node_id, {}).update(new_fields)

        # 取消旧计时器，重新计时
        if _pending_timer is not None:
            _pending_timer.cancel()

        _pending_timer = threading.Timer(_DEBOUNCE_SECONDS, _flush_pending_writes)
        _pending_timer.daemon = True
        _pending_timer.start()


def _flush_pending_writes() -> None:
    """将缓冲区中所有待写状态落盘（经 OMO 治理校验）。"""
    with _write_lock:
        to_write = dict(_pending_writes)
        _pending_writes.clear()

    for node_id, fields in to_write.items():
        try:
            _safe_write_back(node_id, fields)
        except Exception as exc:
            logger.error("Mesh state write-back failed for node=%s: %s", node_id, exc)


def _safe_write_back(node_id: str, fields: dict[str, Any]) -> None:
    """通过 OMO 治理层将节点状态安全写回 M1 YAML。

    写入策略（优先级降序）：
    1. 尝试调用 omo_audit.record_compute_node_state()（若已实现）
    2. 直接追加写 .omo/state/mesh_node_states.yaml（中间 SSOT 暂存区）
       并在下次 omo sync 时由 omo_audit_sync 拉取落盘。

    绝对禁止：直接修改 M1 compute_engine/*.yaml（需经审计门）。
    """
    logger.info("Mesh write-back: node=%s fields=%s", node_id, list(fields.keys()))

    # ── 方案 1：走 omo_audit 正式审计路径 ──
    try:
        from omo.omo_audit import record_compute_node_state  # type: ignore[import]

        record_compute_node_state(node_id=node_id, **fields)
        logger.debug("omo_audit.record_compute_node_state OK for node=%s", node_id)
        return
    except (ImportError, AttributeError):
        pass  # omo_audit 暂未实现该接口，降级到方案 2

    # ── 方案 2：写入 .omo/state/mesh_node_states.yaml 暂存区 ──
    _write_to_omo_state(node_id, fields)


def _write_to_omo_state(node_id: str, fields: dict[str, Any]) -> None:
    """将节点状态写入 .omo/state/mesh_node_states.yaml 暂存区。

    omo_audit_sync 会周期性地将此文件的状态同步到 M1 YAML。
    """
    state_path = Path("~/Workspace/.omo/state/mesh_node_states.yaml").expanduser()

    try:
        if state_path.exists():
            current = load_yaml(state_path)
        else:
            current = {}

        nodes: dict = current.setdefault("nodes", {})
        node_entry: dict = nodes.setdefault(node_id, {})
        node_entry.update(fields)
        node_entry["updated_at"] = time.time()
        current["schema_version"] = current.get("schema_version", 1)
        current["last_updated"] = time.time()

        state_path.parent.mkdir(parents=True, exist_ok=True)
        write_yaml_atomic(state_path, current)

        logger.info(
            "Mesh state written to .omo/state/mesh_node_states.yaml: node=%s status=%s",
            node_id,
            fields.get("status", "?"),
        )
    except Exception as exc:
        logger.error("Failed to write mesh state to .omo staging: %s", exc)
