---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0057: P63 readiness 历史快照 + trend 报告 + agent 增强 (--dry-run/--snapshot-only/--include-trend)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P63
- **Extends**: ADR-0055/0056 (P61-P62 治理深化)
- **Superseded by**: (无)

## Context and Problem Statement

P62 收口后, P63 调研发现 3 项可深化:

1. **readiness 无历史快照**: 每次跑只输出当前, 无快照累积, 趋势不可见
2. **drift LOW 趋势有, readiness 趋势无**: mof-drift v6 (P61) 已加 governance_score_history, 但 readiness 评分历史未跟踪
3. **governance-agent.sh 单一模式**: cron 触发固定, 缺 dry-run / snapshot-only / trend 集成选项

## Decision

### D1: readiness 历史快照 (P63 R1)

**修改**: `bin/gac/governance-readiness.py` 末尾加 `write_readiness_snapshot()` 函数

**快照格式** (`.omo/_log/readiness-YYYYMMDD-HHMM.json`):
```json
{
  "timestamp": "2026-06-24T05:39:49Z",
  "score": 96,
  "grade": "A+ L4 稳态治理",
  "phase": "P60+",
  "dimensions": {
    "frontmatter": {"score": 25, "metric": 703, "coverage": 0.977, "max": 25},
    "drift_low": {"score": 18, "metric": 4, "max": 20},
    "commit_closure": {"score": 18, "metric": 17, "max": 20},
    "adr_index": {"score": 20, "metric": 0, "max": 20},
    "governance_score": {"score": 15, "metric": 100.0, "max": 15}
  },
  "thresholds": {"A+_L4_stable": 90, "A_L3_mature": 80, ...}
}
```

**保留策略**: 最多 30 个快照, 自动清理旧文件 (避免目录膨胀)

**实测**: 6 个快照 (4 + snapshot-only × 2)

### D2: governance-readiness-trend 报告 (P63 R2)

**新工具**: `bin/gac/governance-readiness-trend.py`

**功能**:
- 加载最近 30 个快照
- 统计: mean / median / min / max / stdev
- 趋势判定: declining / improving / stable / insufficient_data
- 异常检测: 单次下降 > 5 分 (sudden_drop)
- 维度趋势: 5 维各自完成度
- L0 规则关联: < 90 告警 / stdev > 3 波动

**实测**:
```
📊 快照数: 6
📊 评分统计: mean=96.0 median=96 min=96 max=96 stdev=0.00
📊 趋势: stable
```

### D3: governance-agent.sh 增强 (P63 R3)

**新选项**:
- `--dry-run`: 不写日志, 不告警, 输出到 stdout
- `--snapshot-only`: 只跑 readiness + 写快照, 跳过 drift
- `--include-trend`: 跑 readiness + drift + trend (3 步 → 4 步)
- `--help`: 显示用法

**优势**:
- 调试: dry-run 不污染 .omo/_log
- 监控: snapshot-only 频繁跑 (每 5min) 不影响 drift
- 报告: include-trend 给完整评估 (含趋势)

**实测**:
- `--dry-run` ✅ 96/100 + LOW=1
- `--snapshot-only` ✅ 6 快照
- `--include-trend` ✅ 含 trend 输出

## Consequences

### Positive

- **readiness 历史可见**: 6 快照, mean=96, 趋势 stable, 异常检测就绪
- **trend 工具可用**: governance-readiness-trend.py 让治理评估有"前世今生"
- **agent 多模式**: 3 新 flag 让 cron / 调试 / 报告分离

### Negative

- **快照保留 30 限制**: 长期可能丢失历史 (待 P64+ 评估持久化)
- **dry-run 与正常输出重复**: 步骤 1 跑 2 次 (输出 + 捕获), 效率 50% 损失

### Neutral

- **不触动 mof-drift**: 8 维度不变
- **不增 linter 维度**: 沿用 P58 独立 bin 工具模式

## Compliance

### 验证指标

| 指标 | P62 末 | **P63 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.51 | **v0.0.52** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| mof-drift 维度 | 8 | **8** | 持平 |
| governance readiness | 96/100 | **96/100** | 持平 (稳态) |
| 独立 bin 治理工具 | 4 | **6** | +2 (readiness snapshot + trend) |
| 自治代理 flags | 0 | **3** | +3 (--dry-run/--snapshot-only/--include-trend) |
| readiness 快照 | 0 | **6** | 新增 (P63 R1) |
| ADR 数量 | 16 | **17** | +1 (0057) |

### 关联 ADR

- **ADR-0056**: P62 readiness 5 档 + mof-drift v7 (P63 直接扩展)
- **ADR-0055**: P61 readiness 修复 + mof-drift v6
- **ADR-0054**: P60 治理方法论内化 (6 层落地)

### 关联 L0 规则

- `CR-GOV-CLOSED-LOOP-01` (强制闭环) — readiness-trend 异常检测
- `X2-FRESH-DOC-LIFECYCLE` (7 天) — 快照保留 30 个 = ~7d×4 次/天

## Notes

本 ADR 记录 P63 三项深化:
- **readiness 历史化**: 快照 + 趋势 + 异常检测形成完整时间序列
- **agent 多模式**: dry-run / snapshot-only / include-trend 三种使用场景
- **trending-ready**: trend 工具为 P64+ dashboard 卡片实时显示奠定基础

后续 P64+ 候选:
- readiness 快照持久化 (git LFS 或独立数据存储)
- dashboard 卡片实时显示 readiness + trend
- 异常自动告警 (stdev > 3 触发 signal)
- 维度权重动态调整 (基于历史相关性)
- governance-readiness-trend 集成 mof-drift v8 (统一 trend 报告)

---

*最后更新: 2026-06-23 · P63 · omostation 治理方法论持续深化*