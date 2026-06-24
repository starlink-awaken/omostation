---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0058: P64 dashboard 数据源 + 异常自动告警 (--alert mode)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P64
- **Extends**: ADR-0057 (P63 readiness 历史快照 + trend)
- **Superseded by**: (无)

## Context and Problem Statement

P63 readiness 历史快照 + trend 报告实施后, P64 调研发现 2 项可深化:

1. **无 dashboard 数据源**: cockpit dashboard / 第三方工具需结构化 JSON, 但 trend 报告只输出 text
2. **无自动告警**: readiness 异常 (low_mean / high_volatility / sudden_drop) 只在报告中显示, 需手动监控

## Decision

### D1: dashboard-readiness-summary 工具 (P64 R1)

**新工具**: `bin/dashboard-readiness-summary.py` (175 行)

**输出**: 结构化 JSON 含 4 类卡片
```json
{
  "generated_at": "2026-06-24T06:12:27Z",
  "workspace_root": "/Users/xiamingxing/Workspace",
  "summary_card": {
    "score": 96, "grade": "A+ L4 稳态治理", "phase": "P60+",
    "trend": "stable", "snapshot_count": 10,
    "last_update": "2026-06-24T05:58:26Z", "alerts": []
  },
  "dimensions_card": { "frontmatter": {...}, "drift_low": {...}, ... },
  "alerts_card": [...],
  "history_card": [...],
  "stats": { "count": 10, "mean": 95.9, "median": 96, ... }
}
```

**双格式支持**:
- `--format json` (默认, 适合机器消费)
- `--format text` (人类可读卡片)

**输出目标**:
- `--output file.json` 写文件
- 默认 stdout

**实测**: 10 快照, score=96, alerts=[], stable

### D2: --alert 自动告警 (P64 R2)

**修改**: `bin/governance-readiness-trend.py` 加 `--alert` 选项

**逻辑**:
```python
# 异常检测 (沿用 analyze_trend)
# alert 类型:
# - low_mean: mean < 90 (high severity)
# - high_volatility: stdev > 3 (medium severity)
# - sudden_drop: 单次下降 > 5 (high severity)

# --alert 模式触发:
# 1. 写 .omo/_log/readiness-alerts.jsonl (历史)
# 2. 调 omo event emit governance_readiness_alert (事件总线)
# 3. 返回非 0 exit code (cron 触发告警)
```

**实测**: 健康时 mean=95.9, 无告警, exit=0

## Consequences

### Positive

- **dashboard 数据源就绪**: cockpit dashboard 可直接消费 4 类卡片数据
- **异常自动告警**: 自治代理 --include-trend + --alert 可形成闭环
- **JSON 标准化**: 时间戳 / workspace_root / 4 卡片让消费方解析简单

### Negative

- **--alert 触发 omo event 依赖 omo CLI**: 不存在时静默 (P64 沿用 P61 模式)
- **dashboard 卡片未实际渲染**: 仅数据源, 实际 dashboard UI 留 P65+

### Neutral

- **不增 linter 维度**: 沿用 P58/P62 独立 bin 工具
- **快照保留策略不变**: 30 快照自动清理

## Compliance

### 验证指标

| 指标 | P63 末 | **P64 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.52 | **v0.0.53** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 6 | **7** | +1 (dashboard summary) |
| 自治代理 flags | 3 | **3+1** | +1 (--alert) |
| readiness 快照 | 6 | **10** | +4 (P64 测试) |
| ADR 数量 | 17 | **18** | +1 (0058) |

### 关联 ADR

- **ADR-0057**: P63 readiness 历史快照 + trend + agent flags (P64 直接扩展)
- **ADR-0056**: P62 readiness 5 档 + mof-drift v7
- **ADR-0055**: P61 readiness 修复 + mof-drift v6

### 关联 L0 规则

- `X1-AUD-COMMIT-LOOP` — readiness-alerts.jsonl 写入即 commit 闭环
- `X2-FRESH-COMMIT-FATIGUE` — 自治代理 cron 触发自动告警
- `CR-GOV-CLOSED-LOOP-01` — alert 写入 + event emit 强制闭环

## Notes

本 ADR 记录 P64 dashboard 数据源 + 异常自动告警:
- **dashboard 4 卡片**: summary / dimensions / alerts / history
- **--alert 自动告警**: omo event emit + jsonl 持久化 + 非 0 exit
- **闭环**: 自治代理 + --include-trend + --alert 形成完整事件链路

后续 P65+ 候选:
- dashboard 卡片实际 UI 渲染 (cockpit integration)
- 告警聚合 (避免 alert storm)
- readiness 快照持久化 (git LFS / 独立存储)
- 维度权重动态调整
- governance-readiness-trend 集成 mof-drift v8 (统一 trend 报告)
- management/ 142 拆 3 类 (大重构)
- graphify 重生覆盖 1190 M1 节点

---

*最后更新: 2026-06-23 · P64 · omostation 治理方法论持续深化*