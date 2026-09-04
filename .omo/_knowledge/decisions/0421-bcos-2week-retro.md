---
id: ADR-0421

title: "ADR-0421: BCOS 2 周落地复盘 (W1 执行+知识, W2 治理+进化)"
status: archived
lifecycle: spec
type: retrospective
owner: governance-team
date: 2026-08-19
last_updated: 2026-08-20
tags: [bcos, retrospective, 2-week]
supersedes: []
related:
  - ADR-0419 (BCOS 业务落地计划)
  - .omo/_knowledge/decisions/0420-bcos-evolution-engine.md
---

# BCOS 2 周落地复盘

## 北极星结果

```
consumed_journeys_per_week: 18 (W1≥5 ✅, W2≥20 ⏳ 18/20)
journey_completion_rate: 100% (W1≥65% ✅, W2≥85% ✅)
calibration_score: 50%
```

**总评**: W1 全达标, W2 接近达标 (90%)

## W1 完成清单 (执行+知识闭环)

| 任务 | 产出 | 验证 |
|------|------|------|
| W1-D1 inbox_folder信号触发 | knowledge-shadow-runner | 6 samples 积累 |
| W1-D2 signal_router | 4 路由规则 (doc/meeting/research/code) | 5 tests |
| W1-D3 端到端集成 | inbox → router → scene → ingest | 5 e2e tests |
| W1-D4 knowledge_quality接入 | score_knowledge 在 runner 中 | 9 tests |
| W1-D5 meeting接入 | scene active | router 路由 |
| W1-D6 research接入 | scene active | router 路由 |
| W1-D7 北极星验收 | NorthStarMeter | 18 consumed, 100% |

## W2 完成清单 (治理+进化闭环)

| 任务 | 产出 | 验证 |
|------|------|------|
| W2-D1/D2/D3 EvolutionEngine | 完整四阶段 (observe+propose+A/B+rollback) | 7 tests |
| W2-D4/D5 场景升迁 | 4 路由优化提案 + apply 批准 | 灰度 rollout |
| W2-D6 periodic-reporting | (部分) | — |
| W2-D7 复盘 | 本 ADR | — |

## 关键学习

1. **端到端信号流**: inbox_folder → signal_router → shadow_runner → knowledge_quality → MOSBeliefManager ✅
2. **北极星 = 双指标**: consumed_journeys + completion_rate 互补, 更全面
3. **路由规则**: 4 个 keyword 模式覆盖 90% 信号, 未来可接入 LLM
4. **进化引擎**: observe→propose→evaluate→approve 闭环可行, A/B 测试框架就绪
5. **场景升迁自动化**: calibration + samples 阈值自动触发提案, 减少人工

## 遗留项

| 项 | 优先级 | 后续动作 |
|-----|--------|---------|
| consumed_journeys 18/20 (差 2) | 中 | W3 补充 2 个真实消费事件 |
| 路由优化提案灰度验证 | 高 | W3 验证 scored 信号是否正常 |
| LLM 接入智能路由 | 中 | Month 2 (L3 决策引擎) |
| periodic-reporting 自动化 | 中 | W3 |

## 关键决策回顾

| 决策 | 选择 | 验证 |
|------|------|------|
| 北极星双指标 | ✅ | 18 + 100% 有效 |
| 2 周节奏 | ✅ | W1 W2 都落地 |
| L1→L2 优先 | ✅ | 规则+评分已用 |
| 进化引擎完整四阶段 | ✅ | 7 tests PASS |

## 后续 4 周路线图

- **W3**: consumed_journeys → 20, 路由优化灰度验证
- **W4**: L3 决策引擎 (MentalModel) 接入
- **W5-W6**: L4 学习引擎 (calibration 自进化)
- **W7-W8**: 智能路由 (LLM 接入)