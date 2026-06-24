---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0060: P66 alert-aggregator --notify 主动通知 (omo event emit aggregated)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P66
- **Extends**: ADR-0059 (P65 cockpit-readiness + alert-aggregator)
- **Superseded by**: (无)

## Context and Problem Statement

P65 alert-aggregator 实施后, P66 调研发现 1 项可深化 + 1 项需调整:

1. **alert-aggregator 无主动通知**: P65 只输出报告, 需手动跑, 不形成事件
2. **cockpit 子命令化需 dispatcher 重构**: P65 试做子命令时发现 cockpit 主入口有 dispatcher 拦截, 需重写 dispatcher 模式, 超 P66 范围, **沿用 P65 wrapper 形式**

## Decision

### D1: alert-aggregator --notify 主动通知 (P66 R2)

**修改**: `bin/alert-aggregator.py` 加 `--notify` 选项 + `emit_notification()` 函数

**触发逻辑**:
```python
should_notify = (
    bool(agg.get("storm_warnings"))       # 告警风暴
    or agg.get("total_alerts", 0) >= 5    # 总告警 >= 5
)

if should_notify:
    # 1. 写 .omo/_log/alert-notifications.jsonl (历史)
    # 2. omo event emit governance_alert_aggregated (事件总线)
    # 3. 返回 1 (cron 触发告警)
```

**实测**:
- 健康时: 0 告警, exit=0
- 模拟 5 次同小时: 触发通知 + jsonl 写入 ✅
- omo 不可用时: 静默失败 (沿用 P61 模式)

### D2: cockpit wrapper 形式保留 (调整)

**原因**: cockpit 主入口 dispatcher 会拦截未注册子命令, 强加为 readiness 子命令需要 dispatcher 重构 (超 P66 范围).

**保留方案**: `bin/cockpit-readiness.py` wrapper (P65) 继续作为 cockpit 集成入口.

**P67+ 候选**: cockpit dispatcher 重构 (沿用 add_*_subparser 模式), readiness 升级为子命令.

## Consequences

### Positive

- **告警事件化**: alert-aggregator 触发时 omo event emit, 事件总线可消费
- **持久化双轨**: jsonl (历史) + event emit (实时)
- **wrapper 仍可用**: P65 wrapper 继续工作, 不破坏 P65 行为

### Negative

- **--notify 触发条件 hardcoded**: storm 或 >= 5, 不灵活
- **cockpit dispatcher 重构未做**: 完整集成需 P67+ 评估

### Neutral

- **不增 linter 维度**: 沿用 P58/P62/P64/P65 独立 bin 工具
- **mof-drift 不变**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P65 末 | **P66 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.54 | **v0.0.55** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 9 | **9** | 持平 |
| 告警事件化 | 报告 | **报告 + event emit** | +1 |
| ADR 数量 | 19 | **20** | +1 (0060) |

### 关联 ADR

- **ADR-0059**: P65 cockpit-readiness + alert-aggregator (P66 直接扩展)
- **ADR-0058**: P64 dashboard-readiness-summary + --alert
- **ADR-0060**: 本 ADR (P66 实施)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 告警聚合补强 (避免 alert storm)
- `CR-GOV-CLOSED-LOOP-01` — 强制闭环纪律, alert 写入即 commit

## Notes

本 ADR 记录 P66 调整:
- **alert-aggregator --notify**: 从"报告"升级为"事件", omo event emit 实时分发
- **cockpit wrapper 保留**: dispatcher 重构超 P66 范围, 沿用 P65 wrapper
- **20 个 ADR**: P50-P66 完整治理链

后续 P67+ 候选:
- cockpit dispatcher 重构 + readiness 升级子命令
- 告警聚合阈值参数化 (--threshold N)
- 告警聚合主动通知级别 (P0/P1/P2)
- dashboard 卡片实际 UI 渲染
- readiness 快照持久化 (git LFS / 独立存储)
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8
- management/ 142 拆 3 类
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P66 · omostation 治理方法论持续深化*