"""ECOS 默认 Workflow Mesh Sink — 自动发现 OMO 并连接。

ECOS workflow engine 默认通过此 sink 连接到 Workflow Mesh，
不需要调用方显式传入 event_sink。

设计原则:
1. 自动发现：从当前工作目录向上查找 .omo 目录
2. 优雅降级：找不到 OMO 时静默返回，不阻断 workflow 执行
3. 幂等保证：复用 OMO WorkflowMeshStore 的原生去重
4. 错误隔离：sink 异常只会记录日志，不影响 workflow 执行结果
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("ecos.workflow.mesh")

# Late binding — 避免在 import 阶段尝试连 OMO
# 真正需要 sink 时才尝试 import
_store_instance: Any | None = None


def _find_omo_root(start_path: Path | None = None) -> Path | None:
    """从 start_path 向上查找 .omo 目录。"""
    path = start_path or Path.cwd()
    for parent in [path, *path.parents]:
        if (parent / ".omo").is_dir():
            return parent
    return None


def _get_workflow_mesh_store() -> Any | None:
    """延迟加载 WorkflowMeshStore。

    先尝试从 projects/omo 导入（开发环境），
    失败则尝试通过 uv run 调用 CLI（运行环境）。
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    omo_root = _find_omo_root()
    if not omo_root:
        logger.debug("OMO not found, mesh events will be dropped")
        return None

    try:
        import sys
        projects_path = str(omo_root / "projects" / "omo" / "src")
        if projects_path not in sys.path:
            sys.path.insert(0, projects_path)
        from omo.workflow_mesh import WorkflowMeshStore
        _store_instance = WorkflowMeshStore(omo_root / ".omo")
        logger.debug("Connected to WorkflowMeshStore at %s", omo_root / ".omo")
        return _store_instance
    except ImportError as exc:
        logger.debug("Cannot import WorkflowMeshStore: %s. Mesh events disabled.", exc)
        return None


def default_mesh_sink(event: dict[str, Any]) -> None:
    """默认 Mesh event sink — 自动发现并写入 OMO。

    如果找不到 OMO 或写入失败，静默记录日志后返回，
    不阻断 workflow 执行。
    """
    try:
        store = _get_workflow_mesh_store()
        if store is None:
            logger.debug("Mesh sink unavailable, dropping event: %s", event.get("event_type"))
            return
        store.append(event)
    except Exception as exc:
        logger.warning(
            "Failed to append mesh event %s: %s. Execution continues.",
            event.get("event_type"),
            exc,
        )


def get_default_mesh_sink() -> Callable[[dict[str, Any]], None] | None:
    """获取默认 Mesh sink callable。

    始终返回可调用对象。即使 OMO 不可用，也返回一个只记录 debug 日志的空 sink。
    """
    return default_mesh_sink
