---
lifecycle: stable
owner: governance-team
last_updated: 2026-08-24
title: North Star v3 — 复合制价值证明设计
type: doc
---

# North Star v3 — 复合制价值证明设计

> **定位**: project-strategy-v1 §5.2 落地 — 主人每月可证的时间节省 (小时) 的可测量版本
> **回答的问题**: "omostation 到底为主人省了多少时间?" — 从「能精确测量 142 条 GaC 规则遵守度, 无法测量系统为主人省下的时间」(2026-08-22) 转向可证
> **D4 混合数据源策略**: 自动信号 + 关键节点轻量人工确认
> **关联**: docs/architecture/project-strategy-v1.md §5.2, D4, D5, D7

---

## 0. 一句话总结

3 轴复合 (D5 混合制, 时间账本为锚):
- **A 时间账本 (主, 70%)**: 系统自动化事件数 × 估时/事件 → 月可证时间节省
- **B 决策吞吐 (30%)**: 决策收件箱条目数 + cadence (0/低/中/高)
- **C 项目推进力 (佐证, 0%)**: BET done rate (无成本导出, 不计入 composite)

---

## 1. 3 轴详解

### 1.1 A 轴 (时间账本, 70%)

| 信号源 | 估时/事件 | 30 天实测 |
|--------|----------|----------|
| compass_radar_run | 5 min | 45 |
| drift_sweep_run | 8 min | 0 (无独立 history) |
| signal_poll | 1 min | 1322 |
| agent_tick | 2 min | 218 |
| maturity_scorecard_run | 4 min | 0 (无 history) |
| document_review_sample | 12 min | 0 (scene 卡未激活) |
| knowledge_curation | 3 min | 0 |
| staleness_check | 2 min | 0 |

**当前实测**: 1983 min ≈ 33h / 30d ≈ 1.1h/天
**Score 公式**: `min(100, 100 * total_minutes / 1800)` (参考: 60min/day × 30day = 1800)
**当前 Score**: 100/100 (信号轮询 + agent tick 大量累积)

### 1.2 B 轴 (决策吞吐, 30%)

| 信号源 | 数据 |
|--------|------|
| `notepads/delegation-guardrails/decisions.md` 中 `## [YYYY-MM-DD]` 标题数 |

**当前实测**: 2 条 / 30d ≈ 2.0 条/月
**Cadence**: low (1-3 条/月)
**Score 公式**: `min(100, 10 * decisions_per_month)` (10 条/月 = 100)
**当前 Score**: 20/100 ← 瓶颈

### 1.3 C 轴 (项目推进力, 0% 佐证)

无成本导出: BET done rate = 133/137 = 97.1%
不计入 composite, 仅作佐证参考.

---

## 2. 状态机

| 状态 | 触发 | 含义 |
|------|------|------|
| `unprovable` | A=0 且 B=0 | 数据缺失, 无法证明 |
| `low` | A < 30 或 B < 20 | 价值低, 需重审 |
| `partial` | A < 60 或 B < 50 | 部分证明, 改进中 |
| `provable` | A ≥ 60 且 B ≥ 50 | 价值闭环闭合 |

**当前状态**: partial (A=100, B=20, composite=76)

---

## 3. v3 vs v2 演进

| 维度 | v2 (旧) | v3 (新) |
|------|--------|--------|
| 触发器 | 需要 principal_id (manual) | 自动从 telemetry 算 |
| 范围 | 单人 episode 价值 | 系统综合价值 |
| 数据源 | PersonalEpisodeService | health.jsonl + autoloop-trace + agent-tick + decisions.md |
| 输出 | unprovable (主) / partial | partial → provable 渐进 |
| 可证度 | 低 (需要证据) | 高 (自动计算) |

v3 不替代 v2 — v2 仍是单事件可追溯的 SSOT. v3 是宏观可证版本.

---

## 4. 治本路径

要让 v3 到达 `provable` 状态:
- **B 轴 ≥ 50**: 决策收件箱 cadence 升至 ≥ 5/月
  - 短期: cockpit decide 工具 (V3-01) 落地, 把零散决策结构化入库
  - 中期: weekly-review 集成, 每周主人对 decision-inbox 一键 confirm
- **A 轴 ≥ 60 持续**: 系统自动化稳定运转
  - 已有 100, 关键在「不被一次崩溃拖到 0」
  - 对应 rot-defense 6 层

---

## 5. 落地工具

- `bin/bc-os/north_star_meter_v3.py`: 主工具 (本设计落地)
- `bin/gac/strategy-check.py`: 9 维战略矩阵 — 维度 5 引用 v3 status
- (未来) `cockpit decide` 子命令: 主动产出 B 轴事件

---

## 6. 数据流

```
health.jsonl          (compass_radar history)
autoloop-trace.jsonl  (agent_tick)
agent-tick-daemon.jsonl (signal_poll / 5 类 resident daemon)
.notepads/delegation-guardrails/decisions.md (主人决策)
            ↓
    north_star_meter_v3.compute_axes(30d)
            ↓
    {status, composite, axes.A, axes.B, axes.C}
            ↓
    strategy-check.py 维度 5 → YELLOW / RED
            ↓
    weekly-review card (YELLOW → provable 节奏)
```

---

## 7. 验证

- 11 新测试 (单测 + 集成 + CLI)
- 实测: A=100, B=20, composite=76, status=partial
- 与 v2 对比: v2 unprovable (单点) → v3 partial (综合可证)

---

## 8. 反模式

- **主人主观感知代替可证**: 不可量化即不可证
- **单点测量**: 价值是多面的, 单一 score 掩盖关键瓶颈
- **估时表硬编码**: 当前是经验值, 未来需用真实时数据校准 (A-axis calibration cycle)

---

## 9. 决策记录

| 编号 | 决策 | 结论 |
|------|------|------|
| V1 | 锚点 | **A 时间账本为主 (70%)**, B 决策吞吐辅 (30%), C 仅佐证 |
| V2 | 数据源 | **自动从 telemetry** (health.jsonl + autoloop-trace + decisions.md), 不需主事件输入 |
| V3 | 估时表 | **经验值起步**, 写明 "可校准" — 后续用真实回填 (D5 防腐) |
| V4 | 状态机 | 4 级 (unprovable / low / partial / provable), 不二值化 |
| V5 | 与 v2 关系 | **共存**, v3 宏观 + v2 单点可追溯 |
