---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet: BET-Y1Q4-T8-20
title: 声明式卡片扩展 SDK 与外部业务域即插即用挂载
symptom: 旧版 Cockpit 卡片全硬编码在核心库中，外部业务域（如 family-hub、omlxc 等）无法通过声明式配置动态挂载卡片与操作面板
solution: 研发 DCE SDK v1 声明式卡片工坊与 surface-manifest/v1 规范，实现基于 Directory Glob 的自动发现加载器、Schema 校验熔断器与 USP v1 SurfaceEnvelope 动态转换，成功挂载 family-hub 业务卡片
---

# BET-Y1Q4-T8-20 复盘

## 做对了什么

1. **声明式卡片规范与加载器解耦设计**：设计并落地了 `surface-manifest/v1` 标准，在 `cockpit/surface/loader.py` 中实现了 `ExtensionManifest` 与 `CardManifest` 数据模型，将声明式卡片无缝映射至 USP v1 五大核心卡片原语（MetricGrid, DataTable, ActionPanel, LogStream, DagGraph）。
2. **生产级业务域即插即用挂载**：在 `projects/family-hub/surface.manifest.yaml` 中首发声明了家庭空间 KPI 网格、重要待办事项表格与多操作协同面板，通过自动扫描器（`scan_manifests`）实现了零侵入挂载。
3. **全端渲染集成与容错熔断**：在 Sovereign TUI 2.0（`cockpit.tui.app`）中将 `ExtensionRegistry` 动态注入 `switch_domain` 逻辑，领域卡片甲板自动拼装扩展卡片；同时内置损坏 Manifest 容错隔离（Circuit Breaker），保证外部格式错误绝不崩溃主终端。
4. **全面严谨的测试自证**：编写 `tests/test_surface_manifest.py`，覆盖字典解析、Schema 校验阻断、未知卡片拦截、文件读取、USP v1 转换、多目录扫描熔断、领域过滤及 Textual Pilot 模拟渲染，10 项测试全绿通过。

## 踩了什么坑

| 坑 | 修复 |
|---|---|
| `MetricGridCard` 内部字段为 `cells` 而非 `metrics`，导致解析器初始化报 `unexpected keyword argument` | 查阅 `cards.py` 源码，将解析转换逻辑对齐为 `MetricGridCard(cells=...)` |
| `DataTableCard` 的 `columns` 需要 `TableColumn` 强类型实例 | 在 `loader.py` 中遍历 columns 并映射为 `TableColumn` 结构 |
| `SurfaceEnvelope` 构造函数自动设置 `self.schema = self.SCHEMA`，显式传递 `schema` 导致 TypeError | 移除 `schema` 关键字入参，严格遵守 `protocol.py` 参数契约 |

## 交付自证

- 单元测试：`uv run --project projects/cockpit pytest projects/cockpit/tests/test_surface_manifest.py` (10 passed)
- 综合回归：`PYTHONPATH=src:../runtime/src python3 -m pytest tests/test_surface_manifest.py tests/test_surface_protocol.py tests/test_tui_app.py` (71 passed)
- 门禁状态：通过 `agent-workflow` 闭环校验与本地 GaC 门禁。
