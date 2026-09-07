---
schema_version: specification/v1
title: 跨生命周期记忆衰减与冲突消除引擎
bet_id: BET-Y2Q1-T6-01
spec_version: "1.0.0"
status: accepted
created: 2026-09-07
---

# 跨生命周期记忆衰减与冲突消除引擎

> BET: BET-Y2Q1-T6-01 | Track: T6-EVOLUTION | Appetite: 2 days

## Goal

建立 MOS 记忆全生命周期管理：基于时间戳与权威更新动态衰减旧版规章制度（如《旧暂行办法》被《新实施细则》废止），自动消除记忆图谱中的语义冲突与陈旧过时事实。

## Non-Goals

- 不物理抹除历史档案，保留全量历史快照可审计
- 不修改现有 MOS schema 格式

## Design

### DecayManager (`projects/knowledge/kairon/src/kairon/graph/decay_manager.py`)

核心衰减引擎，负责：
1. **时间衰减评分** — 基于创建时间和最后更新时间计算 score，越旧越低
2. **权威覆盖检测** — 当同一实体存在多个事实版本时，标记旧版为 `deprecated`
3. **冲突消除** — 检测语义冲突三元组（A→B 与 A→¬B），自动标记冲突方并保留更新者
4. **幂等重放** — 无副作用，可反复调用

衰减评分公式:
```
score = base_score × recency_factor
recency_factor = max(0.1, 1.0 - (days_since_update / half_life_days))
```

默认 `half_life_days = 180`（6 个月）。

### CLI 验证 (`bin/ssot/m0_feedback.py --check-decay`)

在现有 `m0_feedback.py` 基础上新增 `--check-decay` 子命令：
- 扫描 MOS 中的事实条目
- 调用 DecayManager 计算衰减评分
- 输出衰减报告：deprecated 条目列表、冲突条目列表、建议动作
- 验证退出码：0=正常报告，1=存在严重冲突（幻觉事实）

### Write Surfaces

| 文件 | 动作 |
|------|------|
| `projects/knowledge/kairon/src/kairon/graph/decay_manager.py` | 新建 |
| `projects/knowledge/kairon/tests/test_decay_manager.py` | 新建 |
| `bin/ssot/m0_feedback.py` | 修改（新增 `--check-decay`） |
| `.omo/_knowledge/retros/BET-Y2Q1-T6-01.md` | closeout 时新建 |

### Verification

- `uv run pytest projects/knowledge/kairon/tests/test_decay_manager.py -q` → exit 0
- `uv run python -m bin.ssot.m0_feedback --check-decay` → exit 0
- `make gac-local-gate` → exit 0

## Changelog

- 2026-09-07: initial spec created (BET-Y2Q1-T6-01)
