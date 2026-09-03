---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract

bet_id: BET-Y1Q3-T6-14
owner: human-principal
last-reviewed: 2026-08-24

risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# resident 常驻体系与治理接线深度复盘

## 目的

对 resident 常驻 agent 体系（五类角色/事件驱动/规则订阅/多载体执行）与治理接线
（MOF/SGF/BOS、agent-workflow 契约、gac-local-gate、PR 工作流、MCP 工具）产出一份
项目粒度的深度复盘文档，从场景/功能/用户旅程/体验/目标愿景/长期运营/运维/防腐/约束
九维度沉淀可验证结论，作为 resident 体系（BET-Y1Q3-T1-10）之后的系统性分析产物。

## 交付物

- `docs/reports/2026-08-24-resident-system-deep-review.md` — 九维度深度复盘文档
- 复盘结论必须基于本会话实测数据（水位文件、路由表、cron、MCP 工具、治理登记），
  不凭空推断

## 边界

- 只沉淀分析结论，不改动 resident 运行时行为或治理接线代码
- 不重复共享 checkout 上并发 agent 已产出的通用九维度复盘文档
