---
id: ADR-0308
title: Cockpit 首页运行态真值与分源降级契约
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../projects/cockpit-ui/src/components/HomePage.tsx
  - ../../../projects/cockpit-ui/src/components/__tests__/HomePage.truthfulness.test.tsx
---

# ADR-0308: Cockpit 首页运行态真值与分源降级契约

## 背景

Cockpit 首页是用户进入系统后的第一判断面，曾在后端接口不可用时继续展示默认健康分、示例
告警、示例任务和随机趋势。这样的 fallback 会把“没有证据”伪装成“系统运行正常”，也会让
Workflow Mesh 的 unavailable、stale 和 partial 边界无法被用户正确感知。

## 决策

1. 首页不再生成默认业务对象或随机指标。健康摘要、告警、任务、指标趋势和心智探针都必须
   来自对应真实接口；接口失败时清空本轮读数，不沿用未标记的旧值。
2. 首页和各分区统一表达 `loading`、`complete`、`partial`、`unavailable`。每个数据源拥有独立
   状态，首页总状态只描述整体可用性，不能用一个成功接口掩盖另一个失败接口。
3. `complete` 时空结果才可以显示“暂无活跃告警/任务”；其他状态只能显示“没有可展示的真实
   数据”、N/A 或明确的不可用提示。
4. 周期刷新先进入 loading 并清空旧读数；刷新失败不把上一次读数冒充当前 live 状态。后续若
   需要保留 stale 读数，必须增加带时间戳和 freshness 的显式状态，而不是恢复隐式 fallback。
5. 本 ADR 只约束 Cockpit 首页的展示真值，不改变后端数据源、Workflow Mesh 状态机或外部
   连接激活门；它为 M0 真相归一和 J1 日常工作台提供可验证的用户侧边界。

## 不变量

- 首页源码中不得存在用于运行态展示的 `DEFAULT_*` 业务数据或 `Math.random()` 趋势生成。
- 后端全部不可用时，不得出现历史示例任务 ID、示例任务标题、默认健康分或随机趋势点。
- 部分数据成功时，成功分区仍可消费真实数据，失败分区必须独立显示 unavailable，首页总提示
  必须列出失败来源。
- 只有真实接口返回成功，告警/任务空列表才可以被解释为真实的“暂无”。

## 验收

- `HomePage.truthfulness.test.tsx` 覆盖 loading、全源 unavailable 和部分成功三条路径，3/3
  通过。
- cockpit-ui 全量 Vitest：146 passed、1 skipped；生产构建通过。
- 本轮改动文件精确 ESLint 通过；全量 ESLint 的既有错误未纳入本轮范围，已在 closeout 中记录。
- 不声称后端真实业务数据、外部连接或业务场景已经激活；本轮只完成用户侧运行态真值治理。
