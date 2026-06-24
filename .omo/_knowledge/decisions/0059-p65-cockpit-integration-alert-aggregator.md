---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0059: P65 cockpit 集成 + 告警聚合 (避免 alert storm)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P65
- **Extends**: ADR-0058 (P64 dashboard 数据源 + --alert)
- **Superseded by**: (无)

## Context and Problem Statement

P64 dashboard-readiness-summary + --alert 实施后, P65 调研发现 2 项可深化:

1. **cockpit 未集成 dashboard**: 4 卡片数据源已就绪, 但 cockpit CLI 不能直接消费
2. **无告警聚合**: P64 --alert 每次异常都触发, 无聚合抑制 (alert storm 风险)

## Decision

### D1: cockpit-readiness wrapper 工具 (P65 R1)

**注**: 原本设计为 cockpit 子命令 (P65 R1 初次实现), 但 cockpit cli.py 有 pre-existing ruff 错误 (P65 范围外), 改在根仓 `bin/cockpit-readiness.py` 提供独立 wrapper.

**新工具**: `bin/cockpit-readiness.py` (60 行)

**功能**:
- 委派到 `bin/dashboard-readiness-summary.py` (P64 工具)
- 自动发现 workspace 根 (向上 5 层查找 .omo/)
- 双格式 (--format json/text)
- --output 写文件
- 60s timeout + 错误处理

**P66+ 候选**: cockpit cli.py pre-existing ruff 错误修复后, 升级为 cockpit 子命令

**实测**: 10 快照, score=96, alerts=[], stable (JSON 格式完整)

### D2: 告警聚合工具 (P65 R2)

**新工具**: `bin/alert-aggregator.py` (130 行)

**功能**:
- 读 `.omo/_log/readiness-alerts.jsonl` (P64 --alert 写入)
- 时间窗口过滤 (默认 24h)
- 按类型分组 (low_mean / high_volatility / sudden_drop)
- 按小时分桶
- **告警风暴检测**: 同 1h 内同类型 > 3 次 → 抑制报告
- 双格式 (json/text)
- --output 写文件

**实测**:
- 健康时: 0 告警, 无风暴
- 模拟 5 次同小时: 检测到告警风暴

## Consequences

### Positive

- **cockpit 可消费 dashboard**: 4 卡片 JSON 完整输出
- **告警风暴防御**: 同小时 > 3 次抑制, 避免监控疲劳
- **告警历史可追溯**: jsonl 持久化 + 按时间窗口聚合

### Negative

- **wrapper 是过渡方案**: 完整集成需 cockpit cli.py ruff 修复 (P66+)
- **告警聚合无主动通知**: 只输出报告, 需手动跑

### Neutral

- **不增 linter 维度**: 沿用 P58/P62/P64 独立 bin 工具
- **不触动 mof-drift**: 8 维度不变

## Compliance

### 验证指标

| 指标 | P64 末 | **P65 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.53 | **v0.0.54** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 7 | **9** | +2 (cockpit-readiness + alert-aggregator) |
| readiness 快照 | 10 | **10** | 持平 |
| ADR 数量 | 18 | **19** | +1 (0059) |

### 关联 ADR

- **ADR-0058**: P64 dashboard-readiness-summary + --alert (P65 直接扩展)
- **ADR-0057**: P63 readiness 历史快照 + trend
- **ADR-0054**: P60 治理方法论内化 (6 层落地)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 告警风暴检测补强
- `CR-GOV-CLOSED-LOOP-01` — cockpit-readiness wrapper 委派保持闭环

## Notes

本 ADR 记录 P65 集成 + 告警聚合:
- **cockpit wrapper**: 过渡方案, 完整集成需 P66+ 修复 cli.py
- **告警聚合**: 防御 alert storm, 24h 窗口 + 同小时 > 3 抑制
- **2 新 bin 工具**: cockpit-readiness + alert-aggregator

后续 P66+ 候选:
- cockpit cli.py pre-existing ruff 错误修复 → 升级 readiness 为子命令
- dashboard 卡片实际 UI 渲染 (cockpit dashboard integration)
- 告警聚合主动通知 (omo event emit aggregated)
- readiness 快照持久化 (git LFS / 独立存储)
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8
- management/ 142 拆 3 类
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P65 · omostation 治理方法论持续深化*