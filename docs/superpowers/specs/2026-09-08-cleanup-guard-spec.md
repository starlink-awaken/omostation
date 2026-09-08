---
schema_version: specification/v1
spec_version: 1.0.0
title: 清理器引用保护
bet_id: BET-Y1Q4-T10-140
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-08
---


# 清理器引用保护 (T10-140)

## 根因

T10-139 交付期间观测 7 次并行 reset/prune 吃掉未推 commit（含刀落 commit
后的案例）。三个清理器（prune-zombie-worktrees / branch-ttl-gate /
gac-branch-prune）的删除判定只有 dirty-skip / open-PR（部分）两维，
**未推 commit 与活跃工作面无保护**。

## 设计

**共享 guard**（`lib/cleanup-guard.py`，DRY——三清理器同一实现）：

```
protect_reason(branch) -> None | "unpushed" | "open-pr" | "bet-claimed (<id>)"
```

1. **unpushed**: `git log origin/<b>..branch` 有输出 → 保护；远端无同名分支
   → 整条分支都是未推 → 保护
2. **open-pr**: `gh pr list --head <b>` 有 open → 保护；查询失败宽容放行
   （防防御层成单点）
3. **bet-claimed**（T10-139 广播联动）: 活跃认领的 bet_id 出现在分支名 →
   保护。双形态匹配：全 id（`BET-Y1Q4-T10-139`）或尾段短 id（`t10-139`，
   真实命名惯例 `work/t10-139-xxx`）；短 id 带边界匹配（`-t10-139-`）防
   相邻编号误伤（T10-13 ≠ T10-139）

**接入点**（三清理器删除动作前）：
- `branch-ttl-gate.py`: 主仓 enforce 删除前全查（替换原 open-PR 单查）
- `prune-zombie-worktrees.py`: enforce 时 worktree 照删（目录清理）但受保护
  分支保留（`git branch -D` 跳过）
- `gac-branch-prune.sh`: work 段 + agent 段删除前经 `python3 lib/cleanup-guard.py
  check` CLI 查询（exit code 契约：0=可删 1=保护）

**失败语义**: guard 自身故障（import/执行异常）→ 宽容放行 + 警告
（防御层不成为清理流程新单点；与 T10-139 guard 同哲学）。

## 数据源现实修正

立项时 done_when 写"活跃 run 分支"，勘察发现 run 文件无 branch 字段
（无数据源）→ 修正为"活跃认领 BET 分支"（T10-139 广播现成数据源）。
retro 记录此修正。

## 非目标

- 不改 gac-worktree 生命周期语义（claim/submit/merge/release 不动）
- 不给 run 记录加 branch 字段（超范围，未来 BET）
- guard 不做强制——只跳过并警告，人工仍可显式删除
