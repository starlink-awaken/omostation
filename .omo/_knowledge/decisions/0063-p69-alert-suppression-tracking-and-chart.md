---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0063: P69 抑制标记精确统计 + alert-history ASCII 趋势图

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P69
- **Extends**: ADR-0062 (P68 告警抑制 + 历史趋势)
- **Superseded by**: (无)

## Context and Problem Statement

P68 实施后, P69 调研发现 2 项可深化:

1. **抑制率 hardcoded 0**: alert-history 中 `suppression_rate=0` 是简化值, 无实际统计
2. **无趋势图**: 跨天统计只有表格, 缺 ASCII 柱状图可视化

## Decision

### D1: 抑制标记精确统计 (P69 R1)

**修改**: `bin/gac/alert-aggregator.py` `emit_notification()` 抑制分支

**逻辑**:
```python
if suppressed:
    # 写 alert-suppressions.jsonl (P69 新增)
    suppress_payload = {
        "timestamp": ...,
        "level": level,
        "total_alerts": agg["total_alerts"],
        "suppression_minutes": suppression_minutes,
        "prev_record_ts": prev_record["timestamp"],
        "storm_count": len(storm_warnings),
    }
    append to .omo/_log/alert-suppressions.jsonl
    return 2
```

**双 jsonl 分离**:
- `alert-notifications.jsonl`: 实际触发的通知
- `alert-suppressions.jsonl`: 抑制记录 (P69 新)

### D2: alert-history ASCII 趋势图 + 抑制率 (P69 R2)

**修改**: `bin/gac/alert-history.py`

**新增**:
- `load_suppressions()` 函数
- `analyze_history()` 接受 suppressions 参数
- `render_ascii_bar()` 函数 (40 字符柱状)
- 主函数读双 jsonl

**报告新增**:
- 抑制记录数
- 抑制率 (%)
- 按天 ASCII 柱状图

**实测**: 5 个通知 + 5 个抑制 → 50% 抑制率, 5 天柱状图

## Consequences

### Positive

- **抑制率精确**: 不再 hardcoded 0, 双 jsonl 真实统计
- **趋势可视化**: ASCII 柱状图直观, 终端友好
- **双 jsonl 分工**: notifications 实际触发, suppressions 抑制记录, 互不污染

### Negative

- **双 jsonl 维护成本**: 需保持 2 个文件同步清理
- **ASCII 图简单**: 后续可加颜色 (rich 库) 或真图 (matplotlib)

### Neutral

- **不触动 mof-drift**: 8 维度持续
- **不增 linter 维度**: 沿用 P58 独立 bin 工具

## Compliance

### 验证指标

| 指标 | P68 末 | **P69 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.57 | **v0.0.58** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 10 | **10** | 持平 |
| 告警 jsonl | 1 (notifications) | **2 (notifications + suppressions)** | +1 |
| 抑制率 | 0 (hardcoded) | **真实统计** | +1 |
| ADR 数量 | 22 | **23** | +1 (0063) |

### 关联 ADR

- **ADR-0062**: P68 告警抑制 + 历史趋势 (P69 直接扩展)
- **ADR-0061**: P67 告警阈值参数化
- **ADR-0060**: P66 alert-aggregator --notify

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 抑制精确化避免 alert storm
- `CR-GOV-CLOSED-LOOP-01` — 双 jsonl 写入即 commit

## Notes

本 ADR 记录 P69 升级:
- **双 jsonl 分工**: notifications (触发) + suppressions (抑制), 精确统计
- **ASCII 柱状图**: 终端友好可视化, 不依赖第三方库
- **抑制率真实计算**: total / (total + suppress) = 真实抑制比例

后续 P70+ 候选:
- ASCII 柱状图加颜色 (rich 库集成)
- 跨级别抑制 (P0 → P1 仍抑制, 但 P0 → P3 不抑制)
- alert-history 集成到 dashboard 卡片
- P0 触发短信/邮件
- readiness 快照持久化
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8
- management/ 142 拆 3 类
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P69 · omostation 治理方法论持续深化*