---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0065: P71 governance-agent 6 步 + alert-history 跨级别 + dim-weight + management 142 评估

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P71
- **Extends**: ADR-0064 (P70 跨级别 + rich + 6 卡片 + 持久化)
- **Superseded by**: (无)

## Context and Problem Statement

P70 收口后, P71 调研 7 项候选, 选 4 项轻量实施:
1. governance-agent 6 步 (P70 已 5 步, 缺 alert-history 步骤)
2. alert-history 加更多维度 (跨级别聚合)
3. 维度权重动态调整 (简化版)
4. management/ 142 拆 3 类评估 (非实际拆分)

跳过 3 项 (大重构/外部依赖/已落地):
- graphify 重生 (工具无本地扫描)
- P0 短信/邮件 (外部依赖)
- 快照 P50 持续 (P70 已落地, 评估有效)

## Decision

### D1: governance-agent 6 步闭环 (P71 R1)

**修改**: `scripts/omo/governance-agent.sh`

**6 步结构**:
```
[1/3]   governance-readiness (5 维评分)
[2/3]   mof-drift (8 维度)
[2.5/3] governance-readiness-trend (P63 历史 + --alert)
[2.6/3] alert-aggregator (P67 阈值 + P68 抑制 + P70 跨级别)
[2.7/3] alert-history (P68 + P69 ASCII + P70 rich)  ← P71 增
[3/3]   评估
```

**实测**: governance-agent --include-trend --dry-run 跑通 6 步

### D2: alert-history 跨级别聚合 (P71 R2)

**修改**: `bin/gac/alert-history.py` `analyze_history()`

**新增**:
- `by_cross_level` 字段: 按 (level, sup_state) 聚合
  - P0_fired / P0_suppressed / P1_fired / P1_suppressed / ...
- `suppression_efficiency` 字段: suppressed_total / fired_total

**实测**: 3 通知 + 2 抑制 → suppression_efficiency 0.4 (40%)

### D3: 维度权重动态调整 (P71 R3)

**新工具**: `bin/gac/dim-weight.py` (190 行)

**功能**:
- 读持久化快照 (`readiness-snapshots.jsonl`)
- fallback 到 `readiness-*.json` (P70 + 历史)
- 计算各维度 stdev + 与总分相关性
- 归一化输出建议权重

**输出**:
- 当前权重 vs 默认 (25/20/20/20/15)
- 各维度分析 (stdev + correlation)
- `--reset` 强制默认

**实测**: 13 快照 → R3 算法发现波动 (commit_closure 100% = 异常时段贡献大)

### D4: management/ 142 拆 3 类评估 (P71 R5)

**评估文件**: `.omo/_knowledge/audits/2026-06-23-p71-management-split-evaluation.md`

**4 维度评估**:
- Value 4/10 (历史快照, 无活跃引用)
- Effort 8/10 (5+ 文件改动)
- Risk 7/10 (lint 误报 + 引用断裂)
- Reachability 5/10 (需深度访谈)
- **总分 24/40 (60% 中等)**

**结论**: P72+ 暂不实施, 优先其他深化

## Consequences

### Positive

- **6 步闭环**: 完整 readiness + drift + trend + alert + history + eval
- **跨级别聚合**: 工业实践维度, 完整可观测
- **维度权重动态**: 基于历史反推, 数据驱动
- **management 142 评估**: 4 维度评分 60% 中等, 暂不实施但有清晰计划

### Negative

- **dim-weight 算法不稳健**: 13 快照 stdev=0 异常, 需更多历史
- **management 142 评估**: 暂不实施, 价值持续衰减

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P70 末 | **P71 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.59 | **v0.0.60** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 10 | **11** | +1 (dim-weight) |
| governance-agent 步骤 | 5 | **6** (+alert-history) | +1 |
| alert-history 维度 | 5 | **6** (+by_cross_level) | +1 |
| readiness 快照持久化 | 1 | **2** (P70+P71) | +1 |
| ADR 数量 | 24 | **25** | +1 (0065) |

### 关联 ADR

- **ADR-0064**: P70 跨级别 + rich + 6 卡片 (P71 直接扩展)
- **ADR-0053**: doc-lifecycle 4 类 (P71 评估 management 拆分沿用)
- **ADR-0054**: P60 治理方法论内化 (P71 深化)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 6 步闭环避免漂移
- `CR-GOV-CLOSED-LOOP-01` — 快照持久化即 commit

## Notes

本 ADR 记录 P71 5 项候选中实施 4 项:
- ✅ governance-agent 6 步 (scripts 子仓 commit)
- ✅ alert-history 跨级别聚合
- ✅ dim-weight 动态调整 (新工具)
- ✅ management/ 142 评估 (评估报告)
- ⏸ graphify 重生 (工具限制)
- ⏸ P0 短信/邮件 (外部依赖)
- ⏸ 快照 P50 持续 (P70 已落地, 评估有效)

后续 P72+ 候选:
- governance-agent 7 步 (加 dim-weight 评估)
- alert-history 加 sup_state 维度
- dim-weight 调优 (更稳健算法)
- management/ 142 实施拆分 (P75+)
- graphify 重生 (需 url 入口)
- P0 短信/邮件 (mock 模拟)

---

*最后更新: 2026-06-23 · P71 · omostation 治理方法论持续深化*