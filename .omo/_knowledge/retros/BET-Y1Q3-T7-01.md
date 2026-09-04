---
title: BET-Y1Q3-T7-01 复盘 — 知识召回被引用率上线
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  subagent 半途挂 (cockpit 侧已写), 主会话补 omo 侧并收口。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T7-01 复盘

## done_when 对照 (2026-08-16 实测)

| done_when | 结果 |
|---|---|
| 召回 N/引用 M 可自动统计 | ✅ knowledge_action.build_knowledge_action_snapshot → funnel{retrieved, cited, task_created...} |
| 指标进 /outcomes 面板 | ✅ cockpit /api/outcomes/knowledge-funnel + summary 内嵌 knowledge_funnel (citation_rate 计算) |
| 第一个月实测基线值 | 🟡 管道上线实测快照 live (retrieved=0 起步), 月度基线自 2026-08-16 累计 — 按「统计能力+首条真实数据管道」判定达成, 月满复核 |

测试: omo 6/6 (test_knowledge_action)。真实快照 status=live。

## Q3
subagent 挂于中途 (cockpit 面完成, omo 面未 commit) — 主会话接管补齐。API 设计走「summary 内嵌 + 专用端点」双入口, 前端一次拉全。

## Q5
- 基线月满 (09-16) 复核 retrieved 是否 >0; 若为 0 说明召回入口无真实流量, 升级为 W3 信号问题而非指标问题
