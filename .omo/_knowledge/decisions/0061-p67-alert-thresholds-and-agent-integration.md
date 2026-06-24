---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0061: P67 告警阈值参数化 (P0/P1/P2/P3) + governance-agent 集成 alert-aggregator

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P67
- **Extends**: ADR-0060 (P66 alert-aggregator --notify)
- **Superseded by**: (无)

## Context and Problem Statement

P66 alert-aggregator --notify 实施后, P67 调研发现 2 项可深化:

1. **阈值 hardcoded**: storm_threshold=3 / total_threshold=5 hardcoded, 不同环境需调整
2. **级别缺失**: 告警无 P0/P1/P2/P3 级别, 难以分级处理
3. **governance-agent 未跑 alert-aggregator**: P65 alert-aggregator 是独立工具, 未集成到 cron 代理

## Decision

### D1: alert-aggregator 阈值参数化 + 级别判定 (P67 R1)

**修改**: `bin/alert-aggregator.py`

**新参数**:
- `--storm-threshold N` (默认 3, 同 1h 内同类型触发告警)
- `--total-threshold N` (默认 5, 总告警数触发)

**级别判定** (P67 增):
```
P0 (critical): storm + total > total_threshold * 2
P1 (high):     storm + total > total_threshold
P2 (medium):   storm || total > total_threshold
P3 (low):      其余 (默认 0 告警)
```

**notify 触发**:
- P0/P1/P2 → omo event emit
- P3 → 不触发 (健康)

**实测**: 8 个 low_mean → P1 (storm + total=8 > 5)

### D2: governance-agent.sh 集成 alert-aggregator (P67 R2)

**修改**: `scripts/omo/governance-agent.sh`

**集成逻辑**:
```bash
if [ "$INCLUDE_TREND" = true ] && [ -f .omo/_log/readiness-alerts.jsonl ]; then
    # 跑 alert-aggregator
    python3 bin/alert-aggregator.py
fi
```

**触发条件**:
- --include-trend flag 开启
- readiness-alerts.jsonl 存在 (P64 --alert 写入)

**实测**: governance-agent --include-trend --dry-run 跑通, 10 快照稳定, 退出码 0

## Consequences

### Positive

- **阈值参数化**: 不同环境 (dev/staging/prod) 可调整
- **P0/P1/P2/P3 分级**: 告警按严重度排序, 便于分级处理
- **governance-agent 闭环**: cron 触发时自动跑 alert-aggregator
- **3 步完整**: readiness + drift + alert 评估

### Negative

- **--storm-threshold 3 / --total-threshold 5 默认值需调优**: 真实环境可能需不同
- **P0 极少触发**: 仅 critical 场景, 需保持低误报

### Neutral

- **不触动 mof-drift**: 8 维度持续
- **不增 linter 维度**: 沿用 P58 独立 bin 工具

## Compliance

### 验证指标

| 指标 | P66 末 | **P67 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.55 | **v0.0.56** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 告警级别 | 2 档 (storm/total) | **4 档 (P0/P1/P2/P3)** | +2 |
| 独立 bin 治理工具 | 9 | **9** | 持平 |
| governance-agent 步骤 | 4 | **5** | +1 (alert-aggregator) |
| ADR 数量 | 20 | **21** | +1 (0061) |

### 关联 ADR

- **ADR-0060**: P66 alert-aggregator --notify (P67 直接扩展)
- **ADR-0059**: P65 cockpit-readiness + alert-aggregator
- **ADR-0054**: P60 治理方法论内化 (6 层落地)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 告警分级补强 (P0 强制处理)
- `CR-GOV-CLOSED-LOOP-01` — alert 写入即 commit 闭环

## Notes

本 ADR 记录 P67 升级:
- **告警参数化**: --storm-threshold / --total-threshold 灵活调整
- **P0/P1/P2/P3 分级**: 工业级告警分级, 便于响应优先级
- **governance-agent 闭环**: 3 步 (readiness + drift + alert) 完整评估

后续 P68+ 候选:
- 告警级别 P0 触发 omo event 含 P0 标记
- 告警抑制时间窗 (避免 1h 内重复 P0)
- 告警聚合历史趋势 (跨 7d 频率)
- readiness 快照持久化 (git LFS / 独立存储)
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8
- management/ 142 拆 3 类
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P67 · omostation 治理方法论持续深化*