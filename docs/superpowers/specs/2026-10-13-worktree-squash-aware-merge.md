---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-251 specification
bet_id: BET-Y2Q4-T10-251
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-13
---
# Spec: worktree-hygiene-audit squash 合并感知 (BET-Y2Q4-T10-251 / TASK-152D15B1)

schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-13
type: specification

## 0. 背景与问题

`bin/gac/worktree-hygiene-audit.py::_is_merged_to_origin_main` 以
`git merge-base --is-ancestor HEAD origin/main` 判定 worktree 分支是否已合并。
本仓 PR 统一 **squash 合并**：分支原提交永远不会成为 origin/main 的祖先，
于是经 squash 落地的 worktree 只能落入 `active`/`stale_*` 桶，
`--auto-clean` 形同虚设（2026-10-04 实证：PR #4627 squash 合并后其 worktree
`w-simplify` 仍被判 active）。

## 1. 目标行为

`_is_merged_to_origin_main` 在 merge-base 判定失败后，追加 squash 感知探测：

- **(a) tree 等价**：分支相对其 merge-base 的变更路径集，与 origin/main 上
  某 commit（限定于 merge-base 之后的 squash 候选）对比 tree/patch-id 等价
  （`git diff --quiet <merge-base> <branch>` 与
  `git diff --quiet <merge-base> <origin/main-candidate>` 结果一致，或
  `git cherry` patch-id 等价）。
- **(b) PR 状态兜底**：`gh pr view --json state` 该分支 PR 为 MERGED，且
  本地分支无超出 PR head 的新提交（`git rev-list --count <pr-head>..<branch> == 0`）。

## 2. 铁律（fail-safe）

- **判不清一律视为未合并**——延续现有语义，宁可漏清理不可误删除。
- 子仓判定（PR #4649 落地的 `_unmerged_submodules`）不受本变更影响，
  仍需每个子仓合进自己 origin/main。
- gh 不可用（网络/未认证）时 (b) 路径静默失败返回 False，不抛错、不降级整体判定。

## 3. 验收判据

1. 单测：构造 squash 场景 fixture（分支 + origin/main 上的等价 squash commit）
   → 判 merged；分支有超出 PR head 的提交 → 判 unmerged。
2. 单测：patch-id 不等价（squash 后 main 又改）→ 判 unmerged。
3. 真仓回归：`tests/` 下 hygiene 相关既有测试全绿；`--auto-clean` 对一个
   已 squash 合并的真实 worktree（若存在）给出 safe_to_remove。
4. gh 不可用路径：mock gh 缺失 → 判定回退保守。

## 4. 非目标

- 不改 janitor / gac-worktree.sh 的子仓闸（#4649 已覆盖）。
- 不引入「清理历史 squash worktree」的迁移脚本（只修判定，清理交给日常 cron）。
