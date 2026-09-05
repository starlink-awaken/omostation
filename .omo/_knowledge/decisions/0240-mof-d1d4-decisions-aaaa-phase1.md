---
id: ADR-0240
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-28
related:
  - 0238-mof-m4-phase0-registry-self-governance.md
  - docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md
supersedes: []
amends: []
type: ssot
---

# ADR-0240: MOF/M4 D1-D4 决策 (A/A/A/A) — Phase 1 启动

## Context

MOF/M4 治理优化方案 (`docs/proposals/2026-07-25-mof-m4-governance-optimization-plan.md`) §6 列 4 决策点。
ADR-0238 完成 Phase 0 守自止血。

**落地说明 (2026-07-28)**：人类 2026-07-25 拍板 A/A/A/A；旁支 PR #513 曾起草本 ADR 但未合 main（work-not-landed）。
2026-07-28 人类**追认**同一结论，本文件正式进 main 并关闭 `needs-human-mof-m4-d1-d4-decisions`。

## Decision (人类 2026-07-25 拍板 · 2026-07-28 追认 A/A/A/A)

**D1 model-driven CLI 处置 → A 删除**：cockpit 已是唯一人类入口 (ARCHITECTURE §3 单入口)。
删除 model-driven 独立 CLI，cockpit adapter 已是消费面。

**D2 MCP 面 → A 冻结**：当前无 agent 侧消费实证。声明真实 2 工具面（非 28 全接通）。
全量接通留待真实路由需求（B 选项，+1 周）。

**D3 M2 真源方向 → A YAML 为 SSOT + Python 生成**：ecos `m2/*.yaml` 唯一 SSOT，
model-driven 侧从 YAML 生成（生成物头标 DO NOT edit + 溯源指针，与 mof-bridge-sync 同范式）。
25 Python-only schema 分批迁移（每批 ≤8 独立 PR）。

**D4 codegen → A 降级声明为模板投影**：名义 codegen 实际为 YAML/JSON 模板输出。
真 codegen 管线无当前需求方，单独立项。

## Phase 1 启动 (分批 · 不在本 ADR 一次做完)

- **P1-1 M2 单真源 (D3)**：25 schema 分批迁移
- **P1-2 值级 strict (D3 延伸)**：mof-validate state_machine 转移合法性阈值→strict
- **P1-3 工具层并轨**：`bin/mof/` vs `ecos/ssot/tools/mof-*` 边界
- **P1-4 CLI 删除 (D1)**：删 model-driven 独立 CLI，cockpit adapter 引用测试全绿

## 红线

- 不碰 `LifecycleStage` 8 阶段枚举 (ADR-0146)
- 不改 `m3.yaml` 字段语义 (P52)
- D2 冻结 = 声明降级，不实装接通（接通须新 ADR + 真实路由需求）
- Phase 1 每批独立 PR / 独立 verify，计入治理配额 ≤40% (ADR-0249)

## Status

**ACCEPTED** for MOF/M4 Phase 1 启动授权（2026-07-25 拍板 · 2026-07-28 main 追认落地）。
决策卡 `needs-human-mof-m4-d1-d4-decisions` **关闭**。
