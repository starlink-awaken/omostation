---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0064: P70 跨级别抑制 + rich 颜色 + dashboard 6 卡片 + 快照持久化 + mof-drift v8 趋势集成

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P70
- **Extends**: ADR-0063 (P69 抑制标记精确 + ASCII 趋势图)
- **Superseded by**: (无)

## Context and Problem Statement

P69 收口后, P70 调研发现 5 项可深化（用户列举 9 项候选, 选 5 项轻量高价值）:

1. **同级别抑制不够细**: P0→P1 应抑制（高级别已通知），P0→P3 应抑制（同理），P1→P0 不抑制（紧急程度更高必须通知）
2. **ASCII 颜色单调**: 终端无法区分 P0/P1/P2/P3 严重度
3. **dashboard 4 卡片不包含告警**: 数据源缺 alert_history_card
4. **快照 30 rotation 限制历史可追溯**: 30 快照会被清理, 长期数据丢失
5. **mof-drift 维度与 readiness 趋势无集成**: governance-readiness-trend 只看 readiness, 不显示 mof-drift

## Decision

### D1: 跨级别抑制 (P70 R1)

**修改**: `bin/alert-aggregator.py` `is_suppressed()` + `LEVEL_RANK`

**抑制规则 (P70 升级)**:
```python
LEVEL_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# 高→低 (rec_rank <= current_rank): 抑制
# 低→高 (rec_rank > current_rank): 不抑制
if rec_rank > current_rank:
    continue  # 跳过
```

**实测**:
- P0 已通知 + 6 low_mean 触发 P1: P1 抑制 ✅
- P1 已通知 + 13 low_mean 触发 P0: P0 不抑制 ✅

### D2: rich 库颜色 (P70 R2)

**修改**: `bin/alert-history.py`

**新增**: rich Console/Table/Panel + 级别颜色
```python
level_color = {"P0": "bold red", "P1": "red", "P2": "yellow", "P3": "green"}

# Panel: 标题 + 摘要
# Table: 按级别 / 按天 (富文本柱状)
# fallback: ImportError → 纯文本
```

**实测**: 5 通知 + 5 抑制 → rich Panel + Table + 颜色渲染

### D3: dashboard 6 卡片 (P70 R2)

**修改**: `bin/dashboard-readiness-summary.py`

**新增**: `alerts_card` 字段 + `load_alerts_card()` 函数
- 读 alert-notifications.jsonl + alert-suppressions.jsonl (24h 窗口)
- 通知/抑制数 + 抑制率 + 按级别统计

**实测**: 0 通知 0 抑制 0% 抑制率, 健康状态

### D4: 快照持久化 (P70 R3)

**修改**: `bin/governance-readiness.py` `write_readiness_snapshot()`

**新增**: `readiness-snapshots.jsonl` 累加
- 不受 30 快照 rotation 限制
- 长期可追溯, 跨 7d+ 历史保留

**实测**: 写入 1 行 JSON, 持续累加

### D5: mof-drift v8 趋势集成 (P70 R4)

**修改**: `bin/governance-readiness-trend.py`

**新增**: 跑 mof-drift 并显示维度数
```python
drift_output = subprocess.run(["bin/mof-drift"], ...)
m = re.search(r"Total:\s*(\d+)\s+drifts", drift_output.stdout)
print(f"📊 mof-drift: {drift_count} 维度 (P62 v7 + P70 v8 趋势集成)")
```

**实测**: 4 LOW 维度, 12 快照 mean=96.1 stable

## Consequences

### Positive

- **跨级别抑制**: P0 抑制低级别, 但低级别不抑制高级别 (紧急度优先)
- **rich 颜色**: 终端一眼区分 P0/P1/P2/P3
- **dashboard 6 卡片**: 含告警数据, dashboard 端直接消费
- **快照持久化**: 长期历史可追溯, 跨 7d+ 不丢
- **mof-drift v8 趋势集成**: 一份报告含 readiness + drift 趋势

### Negative

- **graphify 重生未做**: 0.8.46 工具需 url 入口, 无本地扫描模式
- **management/ 142 拆 3 类未做**: 大重构, 需深度访谈
- **P0 短信/邮件未做**: 需外部 SMS/email 依赖
- **维度权重动态调整未做**: 大算法变更

### Neutral

- **不增 linter 维度**: 沿用 P58/P62 独立 bin 工具
- **mof-drift 8 维度不变**: P70 仅集成显示

## Compliance

### 验证指标

| 指标 | P69 末 | **P70 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.58 | **v0.0.59** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 10 | **10** | 持平 |
| dashboard 卡片 | 5 | **6** (+alerts_card) | +1 |
| 告警抑制规则 | 同级别 | **跨级别 (P0→P1 ✅, P1→P0 ❌)** | +1 |
| 快照持久化 | rotation 30 | **+ jsonl 累加** | +1 |
| mof-drift 趋势集成 | 无 | **trend 报告含 drift** | +1 |
| ADR 数量 | 23 | **24** | +1 (0064) |

### 关联 ADR

- **ADR-0063**: P69 抑制标记精确 + ASCII 趋势图 (P70 直接扩展)
- **ADR-0062**: P68 告警抑制 + 历史趋势
- **ADR-0061**: P67 告警阈值参数化

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 跨级别抑制避免噪音
- `CR-GOV-CLOSED-LOOP-01` — 持久化快照即 commit

## Notes

本 ADR 记录 P70 五项深化:
- **跨级别抑制**: 工业实践, 紧急优先
- **rich 颜色**: 终端友好
- **dashboard 6 卡片**: 完整可消费
- **快照持久化**: 长期可追溯
- **mof-drift v8 集成**: 统一趋势报告

后续 P71+ 候选:
- graphify 重生 (需 url 入口或子工具改造)
- 维度权重动态调整 (大算法)
- management/ 142 拆 3 类 (大重构)
- P0 短信/邮件 (外部依赖)
- alert-history 加更多维度 (跨级别聚合)
- governance-agent 6 步 (加 alert-history)
- 快照 P50 (P70 持久化, 历史可追溯)

---

*最后更新: 2026-06-23 · P70 · omostation 治理方法论持续深化*