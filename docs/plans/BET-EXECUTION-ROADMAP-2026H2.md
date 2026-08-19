---
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-08-19
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
| BET-Y2Q1-T3-01 | 🔶 in_progress | world_snapshot delta_from_previous |
| BET-Y2Q1-T3-03 | 待认领 | — |
| BET-Y2Q2-T7-01 | 待认领 | — |
| 其余 13 项 | candidate | — |

---

## 关联

- [BET-Y1Q1-T1-05A 口](../reports/2026-08-14-shared-runtime-coordination-gap.md)
- [ADR-0415 能力对齐](../decisions/0415-reject-agt-integration-adopt-capability-parity.md)
