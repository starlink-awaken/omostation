---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0062: P68 告警抑制时间窗 + 告警历史趋势报告

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P68
- **Extends**: ADR-0061 (P67 告警阈值参数化 + 级别)
- **Superseded by**: (无)

## Context and Problem Statement

P67 告警级别 P0/P1/P2/P3 实施后, P68 调研发现 2 项可深化:

1. **无抑制机制**: 同级别告警在 1h 内多次触发会多次 omo event emit (噪音)
2. **无历史趋势**: alert-notifications.jsonl 累积但无分析工具, 难以看跨 7d 频率

## Decision

### D1: 告警抑制时间窗 (P68 R1)

**修改**: `bin/alert-aggregator.py` 加 `is_suppressed()` + `--suppression-minutes N`

**逻辑**:
```python
def is_suppressed(level, suppression_minutes) -> bool:
    # 读 alert-notifications.jsonl 最近 50 条
    # 找同级别 + ts 在 suppression_minutes 内
    if found: return True
    return False

def emit_notification():
    level = agg.get("level")
    if is_suppressed(level, 60):
        return 2  # 抑制标记
    # 写 jsonl + omo event emit
    return 1
```

**参数**:
- `--suppression-minutes N` (默认 60, 工业实践)

**返回码**:
- 0: P3 不触发
- 1: 正常触发
- 2: 抑制

**实测**: 6 个 low_mean 连续 2 次 → 第 2 次 exit=2, 抑制

### D2: 告警历史趋势报告 (P68 R2)

**新工具**: `bin/alert-history.py` (130 行)

**功能**:
- 读 alert-notifications.jsonl 最近 N 天
- 按天统计 + 按级别 + 按类型
- 高峰日检测 (P0+P1 >= 3)
- 双格式 (text/json)

**实测**: 3 个 P1 跨 5 天 → 3 天显示

## Consequences

### Positive

- **告警噪音抑制**: 1h 内同级别只通知 1 次
- **历史趋势可见**: 7d 频率 + 高峰日
- **返回码细化**: 0/1/2 三态 (健康/触发/抑制)

### Negative

- **suppression_minutes=60 是经验值**: 实际可能需调整
- **alert-history 简化版**: suppression_rate=0 (P66/P67 jsonl 无抑制标记)

### Neutral

- **不触动 mof-drift**: 8 维度持续
- **不增 linter 维度**: 沿用 P58 独立 bin 工具

## Compliance

### 验证指标

| 指标 | P67 末 | **P68 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.56 | **v0.0.57** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 9 | **10** | +1 (alert-history) |
| 告警返回码 | 0/1 | **0/1/2** (三态) | +1 |
| 告警抑制 | 无 | **60min 同级别** | +1 |
| ADR 数量 | 21 | **22** | +1 (0062) |

### 关联 ADR

- **ADR-0061**: P67 告警阈值参数化 (P68 直接扩展)
- **ADR-0060**: P66 alert-aggregator --notify
- **ADR-0059**: P65 cockpit-readiness + alert-aggregator

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 抑制避免 alert storm
- `CR-GOV-CLOSED-LOOP-01` — alert 写入即 commit

## Notes

本 ADR 记录 P68 升级:
- **告警抑制**: 工业级噪音防御, 三态返回码
- **历史趋势**: 7d 频率 + 高峰日, 便于治理评估

后续 P69+ 候选:
- 告警聚合抑制标记写入 jsonl (精确统计 suppression_rate)
- alert-history 加趋势图 (ASCII 柱状)
- 告警级别 P0 触发短信/邮件 (P0 需即时响应)
- readiness 快照持久化
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8
- management/ 142 拆 3 类
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P68 · omostation 治理方法论持续深化*