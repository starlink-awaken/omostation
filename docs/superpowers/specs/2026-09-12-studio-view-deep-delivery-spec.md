---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
title: Studio 机理工坊与知识记忆中枢深度交付 (升级)
bet_id: BET-Y1Q4-T8-24C
implementation_authorized: true
value_indicator_policy: false
---

# Studio 机理工坊与知识记忆中枢深度交付 — 设计规格

## 1. 目标

在 cockpit-ui 的 Studio 工作台交付四大能力, 全部消费 24A 已收敛的
`/api/v1/observatory/*` 数据面 (11 operations), 不建平行数据源:

1. 六大记忆通道状态墙 (episodic/semantic/procedural/prospective/emotional/identity)
2. 意图路由仿真器 (纯前端状态机, 消费 ontology)
3. ReactFlow 42 技能 + 25 工作流拓扑网 (点击下钻 entity/lineage)
4. 302 BOS 服务网格 (在线只读检索; Dry-run 置灰待执行面接入)
5. 46 份受管文档双版本 Diff 阅读器 (跨 generation)

## 2. 架构

- 新增 `src/views/StudioView.tsx` — 页面骨架, 四个 Tab 区块
- 新增 `src/components/studio/` 组件目录:
  - MemoryChannelWall.tsx — 记忆通道状态墙 (消费 search/entity)
  - IntentRouterSim.tsx — 意图路由仿真器 (消费 ontology)
  - SkillTopologyGraph.tsx — ReactFlow 拓扑网 (消费 lineage/neighbors)
  - BosServiceGrid.tsx — BOS 服务网格 (消费 manifest/search)
  - DocumentDiffReader.tsx — 双版本 Diff 阅读器 (消费 changes + entity)
- 路由: routes.tsx 注册 Studio 页

## 3. 状态

消费 24B 六面正交 Store 的 knowledgePlaneStore, 不新建平行状态。

## 4. done_when 验收

| # | 验收 |
|---|---|
| 1 | 六通道状态墙渲染 6 tier 卡片, 点击切换过滤 |
| 2 | ReactFlow 渲染 42 技能/25 工作流节点 + 边, 点击节点弹出 entity 下钻 |
| 3 | 302 BOS 网格按域分组, 搜索过滤生效; Dry-run 按钮置灰 |
| 4 | 双 generation 文档 Diff 左右分屏渲染, 行级增删标色 |

## 5. 非目标

- 不实现 Dry-run 实际执行 (等 24D Operations 执行面)
- 不改 43191 (退役属 24E)
- 不做移动端适配

## 6. verify

- `cd projects/cockpit-ui && bun test src/views/StudioView.test.tsx` → exit 0
- `cd projects/cockpit-ui && bun run typecheck && bun run build` → exit 0
