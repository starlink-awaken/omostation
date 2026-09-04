---
id: ADR-0252
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last_updated: 2026-07-28
related:
  - 0242-metaos-registry-drift-gate-extension.md
  - docs/proposals/2026-07-25-metaos-governance-optimization-plan.md
  - 0240-mof-d1d4-decisions-aaaa-phase1.md
supersedes: []
amends: []
---

# ADR-0252: metaos Phase 1/2 前提 D1-D4 决策 (A/A/B/A)

## Context

metaos 治理批 Phase 0 已完成（PR #520 · ADR-0242 · 260 passed · §J1 漂移门扩展）。
Phase 1/2 启动前 workorder §F 要求人类拍板 D1-D4（卡 `needs-human-metaos-phase12-d1-d4`）。

**2026-07-28** 人类批准推荐项 **A / A / B / A**（会话决策落地 worktree `decision-inbox-land-20260728`）。

## Decision

| # | 议题 | 决定 | 含义 |
|---|------|------|------|
| **O-D1** | metaos CLI 定位 | **A 正名为 cockpit 稳定契约** | 有 cockpit 消费实证则保留；与 MOF D1（删无消费者 CLI）按消费定去留，不矛盾 |
| **O-D2** | PID 控制器 | **A 标 experimental 降级** | 无消费者宣称一律降级（S2）；不补实现 |
| **O-D3** | agentkit | **B 降级 reference implementation** | 与 P84 协作主轴资源竞争；v0.2 强制门控可延后单独立项 |
| **O-D4** | admit 门禁 | **A 转 blocking + 2 周观察期** | informational≈无门禁；观察期收集误拦数据后再全量 blocking |

## 红线（不可议 / 另立 ADR）

- **不加回** metaos 独立 MCP 入口（ADR-0181）
- PID 激活 / 真 codegen 式能力扩张 **另立 ADR**
- 为无消费者宣称补实现违反 S2（一律降级不补）
- Phase 1/2 deliverable 须走 agent-workflow；计入治理配额 ≤40%（ADR-0249），不得挤占 P84 协作主轴

## Phase 1/2 启动授权

签核后允许按 `docs/proposals/2026-07-25-metaos-governance-optimization-plan.md` 启动 Phase 1/2，
每批独立 PR。本 ADR **不**一次性实施全部 deliverable。

## Status

**ACCEPTED**（2026-07-28，人类批准 A/A/B/A）。
决策卡 `needs-human-metaos-phase12-d1-d4` **关闭**。
