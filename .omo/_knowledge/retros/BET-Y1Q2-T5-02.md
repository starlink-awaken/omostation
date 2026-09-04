---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q2-T5-02 Retro: 回退边执行语义"
type: retro
---
# BET-Y1Q2-T5-02 Retro: 回退边执行语义

## 完成日期
2026-08-08

## 交付物
- `bin/ssot/journey-runner.py`: DFS backedge 检测 + 可配置 limit + OMO 事件

## 改动
1. `MAX_RETRIES = 3` → `DEFAULT_BACKEDGE_LIMIT = 3` (可被 spec 和 CLI 覆盖)
2. 新增 `_detect_backedges()`: DFS 遍历 transition graph, 找所有 backedge (from→to where to is ancestor of from)
3. 替换原来 flawed 的 next-list 启发式检测 (只检查直接邻居, 无法检测间接环)
4. 新增 `_emit_escalation_event()`: 超限时发 OMO 事件 `journey_backedge_escalated`
5. CLI: `--backedge-limit N` 参数

## 原实现问题
旧代码用 `state.next` 列表检查回退, 只能检测直接 A→B→A 环, 无法检测 A→B→C→A 间接环。
新实现用标准 DFS 回溯边检测, 覆盖所有拓扑。

## 验证
- `journey-runner.py run --journey inbox-to-decision --backedge-limit 2` 正常运行
- inbox-to-decision 有已知环 (under_review → returned_for_revision → under_review), backedge 被正确识别
