---
id: ADR-0238
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last_updated: 2026-07-25
related:
  - docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md
  - 0152-m4-gac-rules.md
supersedes: []
amends: []
---

# ADR-0238: MOF/M4 Phase 0 注册面守自止血 (P0-1..P0-4)

## Context

MOF/M4 治理优化方案 (`docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md`)
§2 诊断发现三类结构性漂移, 其中第一类"治理注册面自身漂移" (Q1) 最刺眼 — 治理系统
没守住自己的注册表 `mof-capabilities.yaml`:

- 工具路径全指向 `bin/mof-*` 旧路径 (实际已迁 `bin/mof/`); `mof-manage` 内部相对路径
  `parent.parent` 随迁移失效 (status 全输出 0 — P71 类 A 声明/执行鸿沟活证据)
- `model_stats` 计数 stale: m1_nodes 1177 vs 实际 1419, m2_schemas 46 vs 实际 55
- `mof-manage` commands 声明 `[status, validate, update]` 但代码只实装
  `[status, tools, constraints, integrations]` (validate/update 是幽灵命令)
- `MCPTOOL-MODEL-DRIVEN.yaml` tool_count=41 vs `mcp_server.py` 实际 `_register_tool` 28
- model-driven `CAPABILITY-MAP`/`ARCHITECTURE` 文档硬编码 24/7/12/8/15/28/210, 违反
  model-driven CLAUDE.md "不在文档复制数量" 铁律

北极星 S1 守自: 治理系统先治理自己, 把注册面纳入机器守门 (治本, 非一次性清扫).

## Decision

Phase 0 四个 deliverable (R-patch 型):

**P0-1 注册表修复** (`mof-capabilities.yaml`):
- 14 工具 path `bin/mof-*` → `bin/mof/mof-*`; usage 同步
- `model_stats`: m1_nodes 1177→1419, m2_schemas 46→55, 加 `stats_as_of` + source
  指针 (ecos CLAUDE.md: M1/M2/M3 以实际文件为准)
- `mof-manage` commands 改实际 `[status, tools, constraints, integrations]` + description
  对齐; 顺手修 mof-manage 内部 `REGISTRY_FILE` (`parent.parent` → `parents[2]`,
  与 `m4-health-score.py` 一致, DRY)
- version 2.1→2.2

**P0-2 注册表漂移门** (`bin/mof/check-mof-capabilities-drift.py`, 新增):
- rule_id `CR-X4-MOF-CAPABILITIES-DRIFT`, 三类检测: tool path 存在性 / model_stats
  vs 实际 yaml 计数 / `MCPTOOL-MODEL-DRIVEN` tool_count vs `mcp_server.py`
  `_register_tool` 数
- 函数化设计 (`check_*` 接受参数) 便于注入测试
- 接入 gac-local-gate: 注册 `diff_checks` {mof-capabilities-drift,
  mof-capabilities-drift-tests} (required: false, CI-only 守门)
- 7 注入检出测试 (path/stat/mcptool 三类 drift 检出 + 干净全绿)

**P0-3 文档数字指针化** (model-driven):
- `CAPABILITY-MAP.md` / `ARCHITECTURE.md` 硬编码数字全指针化 → "见 project-registry.yaml
  / 代码 SSOT" + as_of 2026-07-25 (model-driven CLAUDE.md "不在文档复制数量")

**P0-4 MCP 口径对齐** (ecos `MCPTOOL-MODEL-DRIVEN.yaml`):
- tool_count 41→28 (`mcp_server.py` `_register_tool` 实际计数, `rg -c` 实证)
- 加 `tool_count_verified_at` 指针, 由 P0-2 漂移门守护

## Confirmation

- `mof-manage status`: M1=1419 M2=55 M3=8 (修前全 0) ✅
- `check-mof-capabilities-drift`: 0 drift ✅
- `test_mof_capabilities_drift`: 7 passed (三类注入检出 + 干净全绿) ✅
- `agent-workflow lint`: PASS (diff_checks 注册合法) ✅
- 三闸门 G-Health delta≥0 (基线 99.83/100)

## 红线遵守

- 未碰 `LifecycleStage` 8 阶段枚举 (ADR-0146 永久封禁)
- 未改 `m3.yaml` 字段语义 (P52)
- 新 check 同步注册 `diff_checks` (goal 红线) ✅

## Status

**ACCEPTED** for MOF/M4 Phase 0 注册面守自止血 (2026-07-25). Phase 1/2 (双轨收敛 /
引擎治理边界) 待 D1-D4 决策签核后启动, 不在本 ADR 范围.
