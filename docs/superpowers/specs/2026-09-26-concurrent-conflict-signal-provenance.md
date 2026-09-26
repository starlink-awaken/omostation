---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 并发冲突信号溯源 — health 执行面 12 信号的逐个判定与根因处置
bet_id: BET-Y2Q4-T9-01
---

# BET-Y2Q4-T9-01 — 并发冲突信号溯源

## 背景

复合健康分 36/100 的主扣分项：governance 执行面 4/100，其中
`concurrent_conflicts = 12 × 权重 8 = 96` 分扣光（health.yaml 2026-09-26）。
radar 的 orphan worktree 自动 prune 已上线（N1 治本），但 12 个信号仍在 ——
每个信号的生产者是谁、真残留还是假信号，未逐个判定过。
教训约束：**禁止调权重**（预算 whack-a-mole 教训：8→15→20→50 四轮才过 CI）。

## 目标

1. 逐个溯源 12 个信号（来源 worktree/记录/首次出现/生产者代码路径），列判定表；
2. 真残留 → `gac-worktree.sh release`/归档 14 天不活跃 worktree（逐项留痕）；
3. 假信号 → 修计数根因（wt_pressure 累积逻辑）并加 hermetic 回归测试；
4. 处置后 radar 复测：concurrent_conflicts ≤ 2（余量），执行面分显著回升并留档。

## 写面

`bin/compass_radar.py`（如需修计数）、`tests/**`（回归用例）、
`docs/plans/**`（判定表）、`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。
`.omo/state/health.yaml` 由 radar 工具产出，不手工编辑。

## 验收（done_when 摘要）

1. 12 信号逐个归因表进 retro（含无法归因项的如实标注）；
2. 真残留清理逐项留痕（worktree 名 + 处置命令 + 结果）；
3. 假信号根因修复带 hermetic 回归测试（不依赖 host 运行时状态）；
4. radar `--dry-run` 复测 concurrent_conflicts ≤ 2；
5. **git diff 证明未改任何权重值**；retro 记录 before/after 执行面分。

## 红线

- 不得调 `_W_ORPHAN_WORKTREE`/`_W_ADR_RENUMBER`/`_W_CONCURRENT_CONFLICT` 任何权重；
- 不得删除他人活跃 worktree（只处置 ≥14 天不活跃或已失主的记录）；
- 计数修复不得改信号语义（仍如实报告真实冲突）。

## verify

- `python3 bin/compass_radar.py --dry-run` → concurrent_conflicts ≤ 2 且执行面分 > 60
- `uv run --with pytest python -m pytest tests/ -k concurrent -q` → 回归用例过
- `git diff origin/main..HEAD -- bin/compass_radar.py | grep -c "_W_"` → 0（权重未动）
- `make gac-local-gate` → exit 0
