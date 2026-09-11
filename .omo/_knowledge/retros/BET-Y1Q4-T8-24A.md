---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T8-24A
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
completed_at: 2026-09-12
run_id: 20260911T222043Z-bet-execution-62312684
pr: "omostation-cockpit#160 omostation#3597"
---

# BET-Y1Q4-T8-24A Retro — Observatory 统一数据面收敛与增量流式投影服务

> 日期: 2026-09-11 | 状态: engineering VERIFIED (operational/value 待 T8-24E 退役后单独证明)

## 交付

cockpit#159 (基线收敛) + cockpit#160 (context_pack/lineage/ontology 3 operation
+ rag_engine/ontology_model 收敛 + trace_lineage 175L + 3 文档随迁) +
cockpit#162 (测试鲁棒性) + 主仓 #3597 (gitlink bump 8fd2290 → 312d829)。

## 验收实测 (与 43191 live 观测站对账)

| done_when | 结果 |
|---|---|
| #1 observatory 模块 + 42 技能/6 记忆/302 BOS 采集 | ✅ 模块 11 文件; 采集面与 43191 同源 current.json |
| #2 /api/v1/observatory 路由 + generation 锁 | ✅ snapshot/query/stream + GENERATION_MISMATCH 409 |
| #3 SSE 100ms 增量广播 | ✅ /stream?once=true connected 事件 + generation_id 实测 |
| #4 旧 web/api_*.py 废除或重定向 | ⏳ defer → T8-24E (52 个 API 各有 cockpit-ui 消费方, 需前端消费方清单后按面废除; 数据面保真已由本 BET 证明, 退役动作属 24E 终验) |

## 保真度矩阵 (43191 live 对账, 跳过时间戳字段)

manifest / summary / ontology / lineage / context_pack / search / entity /
neighbors / brief / controls — 10 操作语义对齐。

- `summary` data 层 SHA-256 一致
- `lineage` (BET-Y1Q4-T10-125): 29 nodes / 40 edges / 3 层 lineage_by_depth
- `context_pack`: markdown_pack 1249B + related_knowledge 3 条
- `context_pack.lineage_by_depth` int/str 键差为 JSON 序列化表象, 归一后全等

## 测试

tests/test_observatory_unified.py 6 → 13 passed
(新增: op 注册白名单 / lineage 子图 / 缺实体真值 False / ontology 导出 +
axioms_live / context_pack 合成 / 43191 在线保真对账 / 键型契约)
src/cockpit/tests 全套 1522 passed。

## SSE 端到端

GET /api/v1/observatory/stream?once=true →
`event: connected, data: {"generation_id": "initial", ...}` (200, text/event-stream)。

## 剩余 (非本 BET)

1. 旧 API 废除清单 → T8-24E (依赖 cockpit-ui 消费方分析)
2. 43191 (PID 77125) 平稳退役 → T8-24E
3. operational/value 轴: daemon 面与价值面证据待 24E 终验后单独证明
