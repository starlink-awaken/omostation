---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-17
title: 统一表面协议 (USP v1) 与通用交互卡片元语模型规范
symptom: 终端渲染与后端业务逻辑强耦合，各视图缺少统一抽象契约
solution: 实现纯净 USP v1 协议（SurfaceEnvelope）与 5 大交互卡片元语（MetricGrid, DataTable, LogStream, DagGraph, ActionPanel）
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-17 复盘

## 做对了什么

1. **协议层纯净性设计**：严格将 `SurfaceEnvelope`、`SurfaceDomain`、`CardType`、`RefreshMode` 设计为无副作用的数据模型，彻底解耦底层 BOS/Agora 数据源与终端展示层。
2. **卡片元语完整覆盖**：实现了 `MetricGridCard`（KPI 网格）、`DataTableCard`（数据表格）、`LogStreamCard`（事件流）、`DagGraphCard`（DAG 拓扑图）、`ActionPanelCard`（交互操作面板）5 大核心交互元语，均支持完整的 `.to_dict()` 与 `.from_dict()` 序列化/反序列化。
3. **单测覆盖与质量验证**：在 `projects/cockpit/tests/test_surface_protocol.py` 实现 52 项单元测试，包括协议纯净性、枚举词汇表、TTL 机制、卡片双向转换与全链路 round-trip 验证，全部通过（52 passed in 0.18s）。

## 踩了什么坑

| 坑 | 修复 |
|---|---|
| 枚举跨模块导入时的 identity 比对 (`is`) 偶发失效 | 在协议与测试中统一采用数值比对 (`==`) 与 `StrEnum` 标准基类 |
| 多泳道变更混合提交导致 `change-lane-check` 阻断 | 遵循变更泳道隔离原则，将 governance_state、submodule_pointer 和 docs_data 拆分为纯净提交 |
| 并发 PR 引入的 ADR 编号断层 (0450→0460) | 及时重命名修正为 0451 并挂号到 INDEX.md，维护 ADR 编号连续性 |

## 交付自证

- 测试覆盖：`PYTHONPATH=src:../runtime/src python3 -m pytest tests/test_surface_protocol.py` (52 passed in 0.18s)
- 门禁状态：`make gac-local-gate` 56 项全绿通过。
