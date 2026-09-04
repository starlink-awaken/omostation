---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-19
type: ephemeral
---
# BET 执行路线图 2026H2 — 剩余 23 项推进计划

> **维护规则**
> owner: governance-team
> trigger: 任一 BET 状态变更 / 新窗口开启
> method: 人工维护, 各 BET 认领时反向引用本文
> upstream: `.omo/_truth/registry/bet-ledger`（`docs/plans/3y-bet-ledger.yaml`）
> created_at: 2026-08-18

**剩余 bet 总览**：1 in_progress（T1-07 在跑）+ 1 blocked（Y1Q2-T1-19）+ 16 candidate = **17 项待推进**（Tier 1 三网关 + IntentModel 已收口）。

---

## 优先级矩阵（按价值/成本）

### Tier 1 — 决策门（3 天级，纯分析写作，零代码）

| BET | 窗口 | 性质 | 落地动作 |
|-----|------|------|---------|
| **BET-Y2Q4-T1-01** | Y2Q4 | 年度门 + 愿景证伪 | 读愿景文档 → 列出 3 条可证伪命题 → 给出判定 → 写 ADR |
| **BET-Y3H2-T1-02** | Y3H2 | 三年终局门 | 读三条验收标准 → 逐项判定 → 写终局报告 |
| **BET-Y3H2-T1-01** | Y3H2 | 对外扩展决策 | 三年数据汇总 → 明确"服务他人/不服务" → 写 ADR |

**判定**：这三件事决定 Y2/Y3 方向，必须先做。每项产出 = 1 份 ADR / 终局报告。

### Tier 2 — 快速落地（1 周级，有代码改动）

| BET | 窗口 | 落地动作 |
|-----|------|---------|
| **BET-Y2Q1-T3-02** | Y2Q1 | 意图模型接 goals/tasks：读现有 SceneWatcher → 接 omo state goals → 回答"现在最重要的是哪件" |
| **BET-Y3H1-T6-01** | Y3H1 | 表面积不反弹审计：扫全仓新增文件 → 对比 Y2 减法清单 → 标反弹项 |

### Tier 3 — 多周执行（2-4 周，架构级）

| BET | 窗口 | 依赖 |
|-----|------|------|
| BET-Y1Q1-T1-05 | Y1Q1 | 仓库拓扑改造（← T1-07 量产的前置） |
| BET-Y1Q3-T1-07 | Y1Q3 | clone 迁移量产（← T1-05 之后） |
| BET-Y2Q1-T3-01 | Y2Q1 | 世界模型 world_snapshot |
| BET-Y2Q1-T3-03 | Y2Q1 | Agent 心智模型决策 |
| BET-Y2Q2-T7-01 | Y2Q2 | 知识入库升 assisted |
| BET-Y2Q2-T7-02 | Y2Q2 | 中试/政策申报场景 |
| BET-Y2Q2-T8-01 | Y2Q2 | /inbox 每日习惯化 |
| BET-Y2Q3-T3-01 | Y2Q3 | 跨场景校准迁移 |
| BET-Y2Q3-T3-02 | Y2Q3 | 漂移监控与自动降级 |
| BET-Y2Q3-T6-01 | Y2Q3 | 减法第二轮维持 |
| BET-Y2Q4-T2-01 | Y2Q4 | 感知面第三/四根管子 |
| BET-Y3H1-T3-01 | Y3H1 | 新场景冷启动 < 2 周 |
| BET-Y3H1-T7-01 | Y3H1 | 中试/政策申报升 assisted |
| BET-Y3H1-T5-01 | Y3H1 | 编排模板化 |

---

## 执行状态

| BET | 状态 | 产出 |
|-----|------|------|
| BET-Y1Q1-T1-05A | ✅ done | coordination.sqlite3 + 测试全 PASS + cron + runbook |
| BET-Y2Q4-T1-01 | ✅ done | ADR-0416: 愿景暂未被证伪，先建度量 |
| BET-Y3H2-T1-02 | ✅ done | ADR-0417: 中期校准，S1/S2 度量缺失为最高风险 |
| BET-Y3H2-T1-01 | ✅ done | ADR-0418: 对外扩展默认不做，3 条件重开 |
| BET-Y2Q1-T3-02 | ✅ done | IntentModel + Prioritizer (src/agora/intent/), 9 tests PASS |
| BET-Y2Q3-T3-02 | ✅ done | DriftMonitor (auto-degrade) + 9 tests |
| BET-Y3H1-T3-01 | ✅ done | SceneColdStartPlanner (冷启动) + 7 tests |
| BET-Y3H1-T5-01 | ✅ done | journey template 编排 (3 specs) + 7 tests |
| BET-Y2Q3-T3-01 | ✅ done | transfer_calibration 跨场景迁移 + 6 tests |
| BET-Y2Q2-T7-01 | ✅ done | knowledge-ingest.yaml v2 (assisted 第二场景) |
| BET-Y2Q2-T7-02 | ✅ done | 5 张 v2 场景卡 (knowledge-ingest + 4 迁移) |
| BET-Y2Q2-T8-01 | ✅ done | /inbox cockpit-ui build (exit 0) |
| BET-Y2Q3-T6-01 | ✅ done | surface 审计 (exit 0) |
| BET-Y2Q4-T2-01 | ✅ done | 4 信号源场景绑定 (inbox/github/apple/netease) |
| BET-Y1Q1-T1-05 | ✅ done | D1 pilot + M1 机制 + guard 三态验证 |
| BET-Y1Q3-T1-07 | ✅ done | clone 迁移量产 (clone-lifecycle + agent-clone-onboard) |
| BCOS W1-W4 | ✅ done | 业务闭环 + 北极星双通过 (131/100%) |

## BCOS (Business Capability OS) 2 周落地 (2026-08-19~20)

| 阶段 | 产出 | 北极星 |
|------|------|--------|
| W1 执行+知识闭环 | signal_router + knowledge_capture_pipeline + 5 场景 active | 18 consumed |
| W2 治理+进化 | EvolutionEngine v1 (4 阶段) + 4 提案 apply | 18 consumed |
| W3 诚实修复 | lifecycle_changer 真实改状态 + 北极星 v2 (排除 self-data) | 10 consumed (真实) |
| W4 真实落地 | cockpit-ui 消费面板 + L3 智能路由 + Apple Mail watcher + 30 真实 journey | **131 consumed, 100% completion** |

## 关键学习

1. **从"建功能"到"跑业务"**: 基建收口后必须立刻跑真实业务流, 否则机制是空的
2. **北极星必须诚实**: 排除 self-generated 数据, 用 journey_id 追踪真实人类消费
3. **EvolutionEngine 真实改状态**: 提案 → apply → 写 scene card lifecycle (不是只存到 rollout 文件)
4. **信号源真实路径**: Apple Mail 27 mbox 验证, 真实信号流入
5. **L3 智能路由替代 regex**: 多维评分 (type/urgency/quality) 替代简单关键词匹配

## 后续路线图 (W5+)

- **W5**: 补足 8 场景真实业务 (periodic-reporting + project-supervision)
- **W6**: L4 学习引擎 (calibration 自进化)
- **W7-W8**: 智能路由 (LLM 接入)

---

## 关联

- [BET-Y1Q1-T1-05A 口](../reports/2026-08-14-shared-runtime-coordination-gap.md)
- [ADR-0415 能力对齐](../decisions/0415-reject-agt-integration-adopt-capability-parity.md)
- [ADR-0419 业务落地计划](../decisions/0419-business-workflow-implementation-plan.md)
- [ADR-0421 2 周复盘](../decisions/0421-bcos-2week-retro.md)
- [BCOS 完整方案](../../../projects/agora/Plans/cryptic-baking-newell.md)
