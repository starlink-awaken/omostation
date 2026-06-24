---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0068: P74 事件驱动 P0 检测 + dim-weight percentile 调优 + alert-history 多维扩展

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P74
- **Extends**: ADR-0067 (P73 8 步 + P0 mock + cron --test)
- **Superseded by**: (无)

## Context and Problem Statement

P73 收口后, P74 调研 6 项候选, 实施 3 项:

1. **事件驱动 P0 检测** (替代 P73 polling 模式, omo event listener)
2. **dim-weight percentile 调优** (替代 IQR 更稳健, P75 P90-P10 range)
3. **alert-history 多维扩展** (by_level_sup_state + by_time_window + peak_hour)

跳过 3 项:
- graphify 重生 (工具限制)
- management/ 142 实施拆分 (P75+ 太早)
- P0 mock 替换真实 SMS/email (外部依赖)

## Decision

### D1: p0-event-listener 事件驱动 (P74 R1)

**新工具**: `bin/p0-event-listener.py` (95 行)

**功能**:
- 监听 `.omo/_knowledge/omo-events.jsonl` 新事件
- 检测 `kind=governance_alert_aggregated` + `level=P0`
- 自动调 `alert-mock-p0-notify --all-channels`
- `--once` 单次轮询, `--daemon` 后台守护

**vs P73 polling**:
- P73: governance-agent 步骤 2.6.5 polling 检测
- P74: 独立 listener 工具, 实时事件流处理
- 优势: 跨进程解耦, 不依赖 governance-agent 触发

**实测**: 3 个 P0 事件 → 3 通道 mock 通知 ✅

### D2: dim-weight percentile 调优 (P74 R2)

**修改**: `bin/dim-weight.py` `compute_weights()`

**算法变更**:
- 旧: IQR (interquartile range) — 13 快照 IQR=0 异常
- 新: P90-P10 range + max-min range, 更稳健

**score = correlation * (1 + P90-P10_range/100)**

**保护**:
- max_min_range > 0 才计算, 否则只用 correlation
- score < 0.01 保护为 0.01 (避免某维度权重为 0)

**实测**: commit_closure 突出 (P75 percentile > 0)

### D3: alert-history 多维扩展 (P74 R3)

**修改**: `bin/alert-history.py` `analyze_history()`

**新增 3 维度**:
- `by_level_sup_state`: 按级别拆分 fired/suppressed
  - `{"P0": {"fired": 5, "suppressed": 0}, "P1": {"fired": 1, "suppressed": 2}}`
- `by_time_window`: 1h / 6h / 24h 分桶
  - `{"1h": 0, "6h": 3, "24h": 3}`
- `peak_hour`: 24h 内最频繁的 hour (跨日聚合)

**新增工具函数**: `_within_hours(ts, hours)` — 判断 ts 在最近 N 小时内

**实测**: 4 天 P1 数据 → 3 维度完整输出

## Consequences

### Positive

- **事件驱动替代 polling**: 实时响应, 解耦 governance-agent
- **percentile 调优**: 算法对历史数据更稳健
- **多维可观测**: 按级别/时间/高峰 三个维度

### Negative

- **P0 listener 是轮询**: 真正事件驱动需 omo event 实时 API
- **percentile 仍依赖样本量**: 13 快照下结果不稳定

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P73 末 | **P74 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.62 | **v0.0.63** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 12 | **13** | +1 (p0-event-listener) |
| alert-history 维度 | 7 | **10** (+3) | +3 |
| dim-weight 算法 | IQR | **percentile** | 升级 |
| ADR 数量 | 27 | **28** | +1 (0068) |

### 关联 ADR

- **ADR-0067**: P73 8 步 + P0 mock + cron --test (P74 直接扩展)
- **ADR-0066**: P72 7 步 + sup_state + IQR + P0 mock

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 事件驱动减少轮询
- `CR-GOV-CLOSED-LOOP-01` — listener 写日志即 commit

## Notes

本 ADR 记录 P74 3 项候选实施:
- ✅ 事件驱动 P0 检测 (p0-event-listener 新工具)
- ✅ dim-weight percentile 调优
- ✅ alert-history 多维扩展 (3 新维度)
- ⏸ graphify 重生 (P74 跳过)
- ⏸ management/ 142 实施 (P75+)
- ⏸ P0 mock 替换真实 SMS (P75+)

后续 P75+ 候选:
- graphify 重生 (需 url 入口)
- management/ 142 实施拆分 (P75+ 优先)
- P0 mock 替换真实 SMS/email provider
- P0 listener 实时事件 API (替代轮询)
- dim-weight 真实数据调优 (需 30+ 快照)
- alert-history 加更多维度 (跨类型 + 高峰日 + 自动洞察)

---

*最后更新: 2026-06-23 · P74 · omostation 治理方法论持续深化*