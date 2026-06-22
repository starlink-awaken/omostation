"""Workflow Backend Adapters — bridge each orchestration system to workflow backend interface

每个 backend adapter 暴露 `execute(m1_node, params) -> dict` 函数，
将目标编排系统的 API 适配为统一的 workflow backend 接口。

设计原则:
- 可选依赖：所有 import 都包裹在 try/except 中，缺失时抛 ImportError
- 优雅降级：调用方（backend_registry）在 ImportError 时自动 fallback 到 default
- 轻量包装：不做深拷贝，不做过度校验——依赖上游系统自身的校验
"""

from __future__ import annotations
