"""Workflow Engine — 统一工作流编排入口

架构:
  M1 YAML → loader.py (加载) → validator.py (校验) → executor.py (执行)
            └── backend_registry.py (后端路由)

Phase 1 模块化拆分:
  - loader.py: load_workflow, list_workflows, list_from_m1, _load_from_m1
  - executor.py: execute_workflow, execute_m1_workflow, _execute_step
  - backend_registry.py: register, resolve, list_backends (动态后端)
  - validator.py: validate_workflow, validate_step (X1-X4 校验桩)

向后兼容: 所有旧函数签名不变，可直接从 ecos.workflow import
"""

from __future__ import annotations

from ecos.workflow.actions import (
    get_action,
    list_actions,
    register_action,
    resolve_action,
)
from ecos.workflow.backend_registry import (
    BackendResolutionError,
    get_backend,
    list_backends,
    register,
    resolve,
)
from ecos.workflow.cache import (
    get as cache_get,
)
from ecos.workflow.cache import (
    invalidate,
    invalidate_all,
)
from ecos.workflow.cache import (
    set as cache_set,
)
from ecos.workflow.cache import (
    status as cache_status,
)
from ecos.workflow.event_listener import (
    build_trigger_registry,
    execute_matched,
    listen_forever,
    match_event,
)
from ecos.workflow.executor import (
    _execute_step,
    execute_m1_workflow,
    execute_workflow,
    test_workflow,
)
from ecos.workflow.loader import (
    _load_from_m1,
    list_from_m1,
    list_workflows,
    load_workflow,
)
from ecos.workflow.validator import (
    validate_step,
    validate_workflow,
)
from ecos.workflow.mesh_contract import (
    WorkflowRunState,
    new_workflow_event,
    new_workflow_run_id,
)
from ecos.workflow.default_mesh_sink import (
    get_default_mesh_sink,
)
from ecos.workflow.mesh_gate import (
    check_mesh_connection,
    mesh_gate_check,
    is_strict_mode,
)
from ecos.workflow.mesh_health import (
    mesh_health_snapshot,
    mesh_health_check,
)


__all__ = [
    # loader
    "load_workflow",
    "_load_from_m1",
    "list_workflows",
    "list_from_m1",
    # cache (P48 R2 增: re-export unused cache import)
    "cache_get",
    "cache_set",
    "invalidate",
    "invalidate_all",
    "cache_status",
    # executor
    "execute_workflow",
    "execute_m1_workflow",
    "test_workflow",
    "_execute_step",
    # actions (声明式注册)
    "register_action",
    "resolve_action",
    "list_actions",
    "get_action",
    # backend_registry
    "register",
    "resolve",
    "list_backends",
    "get_backend",
    "BackendResolutionError",
    # workflow mesh
    "WorkflowRunState",
    "new_workflow_run_id",
    "new_workflow_event",
    # mesh gate
    "check_mesh_connection",
    "mesh_gate_check",
    "is_strict_mode",
    # mesh health
    "mesh_health_snapshot",
    "mesh_health_check",
    # validator
    "validate_workflow",
    "validate_step",
    # event_listener
    "build_trigger_registry",
    "match_event",
    "execute_matched",
    "listen_forever",
]
