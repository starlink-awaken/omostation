---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-25
related:
  - 0238-mof-m4-phase0-registry-self-governance.md
  - docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md
supersedes: []
amends: []
---

# ADR-0240: MOF/M4 D1-D4 决策 (A/A/A/A) — Phase 1 启动

## Context

MOF/M4 治理优化方案 (`docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md`) §6 列 4 决策点.
ADR-0238 完成 Phase 0 守自止血. STRAT-P81 Round2 W2 (人类 2026-07-25 拍板 A/A/A/A) 启动 Phase 1.

## Decision (人类 2026-07-25 拍板 A/A/A/A)

**D1 model-driven CLI 处置 → A 删除**: cockpit 已是唯一人类入口 (ARCHITECTURE §3 单入口).
删除 model-driven 独立 CLI (`cli.py:220` 弃用警告), cockpit adapter 已是消费面.

**D2 MCP 面 → A 冻结**: 当前无 agent 侧消费实证. agora 目录标 `status: frozen`,
M1 节点声明真实 2 工具面 (非 28). 全量接通留待真实路由需求 (B 选项, +1 周).

**D3 M2 真源方向 → A YAML 为 SSOT + Python 生成**: ecos `m2/*.yaml` 唯一 SSOT,
model-driven `m2_lifecycle.py` 改为从 YAML 生成 (生成器入 ecos 工具链, 生成物头标
DO NOT edit + 溯源指针, 与 mof-bridge-sync 同范式). 25 Python-only schema 分批迁移
(每批 ≤8 独立 PR).

**D4 codegen → A 降级声明为模板投影**: `tool_generate` 改名/降级声明 (名义 codegen,
实际 YAML/JSON 模板输出). 真 codegen 管线无当前需求方, 单独立项.

## Phase 1 启动 (分批)

- **P1-1 M2 单真源 (D3)**: 25 schema 分批迁移 (每批 ≤8 独立 PR), 生成物保持相同模块路径/符号名
- **P1-2 值级 strict (D3 延伸)**: mof-validate state_machine 转移合法性阈值→strict
- **P1-3 工具层并轨**: `bin/mof/` vs `ecos/ssot/tools/mof-*` 边界 (ecos=模型面/bin=workspace wrapper)
- **P1-4 CLI 删除 (D1)**: 删 model-driven/cli.py, cockpit adapter 引用测试全绿

## 红线

- 不碰 `LifecycleStage` 8 阶段枚举 (ADR-0146)
- 不改 `m3.yaml` 字段语义 (P52)
- D2 冻结 = 声明降级, 不实装接通 (接通须新 ADR + 真实路由需求)

## Status

**ACCEPTED** for MOF/M4 Phase 1 启动 (2026-07-25, 人类拍板 A/A/A/A). Phase 1 分批实施,
每批独立 PR 独立验证. 决策卡 `needs-human-mof-m4-d1-d4-decisions` 可关闭.
