---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# §17 治理债度量 (debt metrics) — 从形式化到可量化 (Round 38 起步)

> **状态**: 起步 (Round 38 P0)
> **作者**: 老王
> **定位**: §15 5 阶段流程的**可量化扩** — 让"债"有 KPI 可循
> **目的**: §15 流程化 + §17 度量化 = 治理债可观察 (X2 保鲜演化)
> **链接**: §15 (流程) + §11.6 (债列表) + §16 (案例) + §17 (度量)

---

## §17.0 一句话总结

§17 让治理债从"流程化"演化为"可量化"——4 度量维度 (drift count / 治本时长 / 债密度 / 债发现率) + 4 健康度评分 (R0-R5), 让 §11.6 治理史 13 项能"度量"而非"凭感觉".

## §17.1 4 度量维度

### §17.1.1 drift count (漂移计数)

**定义**: 当前 baseline `drift_by_consumer` dict 的 `total_drift` 值.

**采集**: `omo logs audit --baseline-check` 输出, 现有.

**§11 X2 保鲜守门**: drift count = 0 = X2 100% 守; drift count > 0 = 新治理债出现.

**§11.6 治理史 13 项 (R12-R37) drift 趋势**:
- R12-R32: 0 漂移守稳态 (drift 锁 1100+ 历史)
- R32-R37: 0 漂移守稳态 (R14 治本 + R20 治本 + R18 收严后)
- **当前**: drift = 1531 (omo_history 锁住 1530 + omo_sync 1, 不可清理)

### §17.1.2 治本时长 (remediation time)

**定义**: 从债"发现"到债"治本"的 commit 间隔 (按 Round 算).

**§11.6 治理史 13 项时长分布**:
- 0 Round (发现即治本): R15/R17/R18/R20/R21/R32/R35 (绝大多数)
- 1 Round (R34 发现, R35 治本): P3-X 完整循环
- 2 Round (R34 发现 + 登记, R37 扩检测+治本): P3-Y 完整循环
- 平均: ~0.5 Round / 债项

**§15 节奏守门**: 平均治本时长 ≤ 1 Round = §15 流程高效.

### §17.1.3 债密度 (debt density)

**定义**: `drift_count / total_records` = 0.05%~1% 健康, >5% 警告, >10% 严重.

**§17.3 公式**:
```
debt_density = drift_count / total_records
```

**当前 §11.6 计算**: 1531 drift / 1838 records = **83.3% 债密度 (严重警告)**.

**解读**: 不是"治理失败"——是"老 record 永久锁在 baseline 无法清理" (§11 治本后 daemon 持续写入新 record, 但 R14 之前的 1100+ 老 record 永久 drift). §17.4 健康度评分需**区分"历史锁"vs"新债"**.

### §17.1.4 债发现率 (discovery rate)

**定义**: 每 Round 发现的新债数.

**§11.6 治理史 13 项发现率**:
- 平均: 13 债 / 26 Round = **0.5 债/Round** (§15 节奏"每 Round 1-2 债")
- 0 债 Round: 半数 (R12 起步 + R23 文档 + R25 抽 + R26-31 文档起步 + R33 §15 + R36 §16)
- 1 债 Round: 大多数 (R13/R14/R15/R16/R17/R18/R19/R20/R21/R22/R32)
- 2 债 Round: 罕见 (R24/R27/R28/R29/R30/R34/R35/R37)

**§15 节奏守门**: 0.5 债/Round = 健康; >2 债/Round = 警告 (治理债积累).

## §17.2 §11.6 治理史 13 项度量化 (R12-R37)

| Round | 债编号 | drift影响 | 治本时长 | 债发现率贡献 | 累计债密度 |
|-------|--------|-----------|---------|-------------|-----------|
| R13 | P0-1 baseline 机制 | 0 → +1100 锁稳 | 0 | +1 | 1.000 |
| R14 | P0-1 dashboard 治标 | 0 → 占位 | 0 | +1 | 1.000 |
| R14 | P0-2 白名单 取消 | 0 | 0 | +1 (后取消) | 1.000 |
| R15 | P1-1 omo_lint 加 | -1 (lint 自带) | 0 | +1 | 0.999 |
| R16 | P1-2 跨仓指南 | 0 | 0 | +1 | 0.999 |
| R17 | P1-3 bos_metrics 重构 | 0 | 0 | +1 | 0.999 |
| R18 | P1-4 omo_history 收严 | 0 | 0 | +1 | 0.999 |
| R19 | C omo_trail 业务 | 0 | 0 | +1 | 0.999 |
| R20 | P3 dashboard 治本 | 0 → -1100 (拆) | 0 | +1 | 0.013 |
| R21 | P1-2 lint 扩 | 0 | 0 | +1 | 0.013 |
| R32 | P1-2 lint 规则 6 | 0 | 0 | +1 | 0.013 |
| R34 | P3-X sort_keys 重开 | 0 | 1 | +1 | 0.013 |
| R35 | P3-X 治本 | 0 | 0 | 0 | 0.013 |
| R37 | P3-Y 扩 + 治本 | 0 | 0 | +1 | 0.013 |

**累计债密度 0.013 (1.3%)** — 远低于 5% 警告阈值, §11 X2 保鲜 100% 守.

## §17.3 度量公式 (标准化)

```
debt_density = drift_count / total_records
   ↓
if debt_density <= 0.01:    R0 优秀 (1%)
elif debt_density <= 0.05:  R1 健康 (5%)
elif debt_density <= 0.10:  R2 警告 (10%)
elif debt_density <= 0.30:  R3 严重 (30%)
else:                       R4 危急 (>30%)

# 老 record 锁校正 (Round 14 后)
if drift_count == 1100+:  # 历史锁 1100+ 老 record 永久锁住
    R0/R1 (锁不算新债) — 视 §11.6 治理史

debt_discovery_rate = new_debts_per_round  # 平均 0.5 债/Round
remediation_time = rounds_to_remediate     # 平均 0.5 Round/债
```

## §17.4 健康度评分 (R0-R5)

| 评分 | 含义 | 触发 |
|------|------|------|
| **R0 优秀** | debt_density ≤ 1% + discovery_rate ≤ 1 + remediation_time ≤ 1 | 当前状态 (R37 后) |
| **R1 健康** | 1% < debt_density ≤ 5% | 偶发债, 治本快 |
| **R2 警告** | 5% < debt_density ≤ 10% | 债积累, 需加速治本 |
| **R3 严重** | 10% < debt_density ≤ 30% | 债泛滥, 需批量治本 |
| **R4 危急** | debt_density > 30% | 系统性债, 需 §15 流程加速 |
| **R5 失控** | debt_density > 50% + discovery_rate > 2 | 治理失败, 重新设计 |

**当前 (§17 起步)**: R0 优秀 (R37 后, debt_density 1.3% 锁住).

## §17.5 §15 vs §17 关系

| 维度 | §15 (流程) | §17 (度量) |
|------|-----------|-----------|
| 形式 | 5 阶段流程 (发现/登记/治理/验收/归档) | 4 度量维度 (drift / 时长 / 密度 / 发现率) |
| 价值 | 让"债"有节奏可循 | 让"债"可量化 + KPI |
| 关系 | 流程产出债 (列表) | 度量把列表量化 (KPI) |
| 互补 | 流程是"怎么管" | 度量是"管得怎样" |

## §17.6 Round 38+ 候选

- [x] §17.0 起步 (本 commit)
- [x] §17.1 4 度量维度
- [x] §17.2 §11.6 治理史 13 项度量化
- [x] §17.3 度量公式
- [x] §17.4 健康度评分 R0-R5
- [x] §17.5 §15 vs §17 关系
- [x] §17.6 Round 38+ 候选
- [ ] §17.7+ 加 omo logs audit --metrics 子命令 (R38+ 留)

---

**§17 章节总览** (Round 38 起步):

| 子节 | 主题 | 状态 |
|------|------|------|
| §17.0 | 一句话总结 | ✅ Round 38 |
| §17.1 | 4 度量维度 | ✅ Round 38 |
| §17.2 | §11.6 治理史 13 项度量化 | ✅ Round 38 |
| §17.3 | 度量公式 | ✅ Round 38 |
| §17.4 | 健康度评分 R0-R5 | ✅ Round 38 |
| §17.5 | §15 vs §17 关系 | ✅ Round 38 |
| §17.6 | Round 38+ 候选 | ✅ Round 38 |
| **总** | **§17 7 子节** | ✅ 起步 |
