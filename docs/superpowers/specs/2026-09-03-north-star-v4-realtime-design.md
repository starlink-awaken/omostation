---
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 北极星价值度量看板 V4 与认知杠杆率实时投影
bet_id: BET-Y1Q3-T10-121
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-03
last-reviewed: 2026-09-03
---

# 北极星价值度量看板 V4 与认知杠杆率实时投影

## Intent

在 `bin/bc-os/north_star_meter_v3.py` 3 轴复合制价值证明基础上, 扩展为 v4:
1. **实时投影模式 (`--realtime`)**: 增量统计当日 0:00 至今的信号 (与 v3 的 30d window 并存)
2. **认知杠杆率**: 第四轴 (D-axis 升级) — 用 evidence-recorded 事件 / 原始事件数, 衡量主人认知活动的代理倍增率
3. **Cockpit UI 入口**: `projects/cockpit/src/cockpit/commands/north_star.py` 提供 CLI 子命令, 输出 v4 实时数据
4. **月度/季度报告**: `--report monthly|quarterly` 输出 Markdown 报告, 增量写入 `.omo/_knowledge/reports/`

## Contract

- `bin/bc-os/north_star_meter_v4.py`: 新增. 复用 v3 compute_axes() 与 A/B/C 轴逻辑, 扩展 D 轴 + realtime 投影
- `projects/cockpit/src/cockpit/commands/north_star.py`: 新增. `cockpit north-star realtime|monthly|quarterly` 子命令
- `bin/_registry/scripts/governance/north-star-meter-v4.yaml`: 注册 v4 工具
- `tests/test_north_star_v4.py`: 5 个单元测试 (realtime window, D-axis ratio, monthly aggregation, cockpit command, idempotent report)
- `docs/reports/2026-09-03-north-star-v4-validation.md`: 验证报告 (实时数据样例)
- `.omo/_knowledge/retros/BET-Y1Q3-T10-121.md`: 复盘 (4 lessons)

## Non-goals

- 不捏造无实际交互佐证的虚假时间数据
- 不重构 v3 的 A/B/C 计算逻辑 (向后兼容)
- 不新增信号源 (使用 v3 已有 5 类 JSONL)

## Risks

- **R1 重复计数**: realtime 与 30d 窗口可能对同一事件重复计算. 解决: realtime 用 `event_id` 去重, v3 30d 按时间窗口不重叠
- **R2 D 轴信号稀疏**: 早期 days 0 可能无 evidence. 解决: D-axis 标 `N/A` 不计入 composite
- **R3 月度报告路径冲突**: 多次运行覆盖. 解决: 报告文件名带 hash 后缀, append-only 写入

## Circuit Breaker

- 数据写入冲突 → 原子 append-only 机制保证幂等 (file lock + monotonic counter)

## Verify

- `python3 bin/bc-os/north_star_meter_v4.py --realtime` 期望 exit 0 + 4 轴得分输出
- `python3 bin/bc-os/north_star_meter_v4.py --report monthly` 期望生成 Markdown 报告
- `python3 -m cockpit.cli north-star realtime` 期望输出实时数据 JSON
- `make gac-local-gate` 期望全绿
- `python3 -m pytest tests/test_north_star_v4.py -v` 期望 5 测试全过
