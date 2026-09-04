---
type: ephemeral
created: 2026-09-03
---

# Gate ROI 季度治理价值报告

> 数据源: governance-history.jsonl | 事件数: 693 | 趋势窗口: 近 30 天 | 估算总节省: **65.3 小时**

## 各 Gate 价值表

| gate | verdict | total | fires | fail | rate(30d) | trend | est_hours |
|------|---------|-------|-------|------|-----------|-------|-----------|
| agora health | PRUNE | 506 | 94 | 0 | 0% | down | 23.5 |
| ruff lint | NOISY | 508 | 91 | 0 | 31% | up | 12.1 |
| debt integrity | NOISY | 508 | 31 | 0 | 69% | up | 10.3 |
| task consistency | PRUNE | 508 | 55 | 0 | 0% | down | 9.2 |
| test coverage | KEEP | 508 | 23 | 0 | 50% | up | 5.8 |
| doc lifecycle | PRUNE | 151 | 13 | 0 | 0% | down | 2.2 |
| adr links | KEEP | 508 | 27 | 0 | 25% | up | 2.2 |

## 减法建议 (下轮候选)

- **PRUNE agora health**: 30d fire 0% < 全期 19% → 衰减, 降频或合并
- **NOISY ruff lint**: 91 warn / 0 fail, 30d fire 31% → 降级 warn→info 或聚合去噪
- **NOISY debt integrity**: 31 warn / 0 fail, 30d fire 69% → 降级 warn→info 或聚合去噪
- **PRUNE task consistency**: 30d fire 0% < 全期 11% → 衰减, 降频或合并
- **PRUNE doc lifecycle**: 30d fire 0% < 全期 9% → 衰减, 降频或合并

> 注: est_hours 为经验估计 (warn/fail 人工处理分钟数), 非精确计量, 用于相对排序。
