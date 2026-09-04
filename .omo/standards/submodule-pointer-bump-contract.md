---
schema_version: standard/v1
standard: submodule-pointer-bump-contract
created: 2026-08-30
last_updated: 2026-08-30
owner: governance-team
origin_bets: BET-Y1Q3-T4-04 / BET-Y1Q3-T4-05 (指针污染事故 ×2 的根治)
review_before: 2026-11-28
---

# 子模块指针 Bump 契约（强约束）

## 背景

2026-08-29 两次指针污染事故：并行 agent 在 root bump `projects/{cockpit,agora}`
指针时使用了 **squash merge 前的分支头**，squash 后该 commit 从子仓 main 消失，
root main 的 gitlink 指向不可达对象，阻塞全仓 PR 半天。

## 契约

1. **bump 唯一合法来源**: `git -C projects/<sub> rev-parse origin/main`（fetch 后）。
   禁止使用本地分支头、PR head、任何非 `origin/main` 的 sha。
2. **bump 前自检**（三条全过才允许 commit）:
   - `git -C projects/<sub> merge-base --is-ancestor <旧指针> <新指针>`（后代性）
   - `git -C projects/<sub> cat-file -e <新指针>^{commit}`（对象存在）
   - 新指针的 commit message 应与子仓 origin/main 头一致
3. **可达性修复必须 true merge**: squash merge 无法恢复 ancestry（重写历史）。
   `--no-ff` 真 merge 是唯一正解；禁 merge commit 的仓库走豁免登记
   （gate-known-debt + principal 知情）。
4. **root PR 前必跑**: `python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main`

## 动态化

本契约带 `review_before`（2026-11-28），过期未复审自动进入 ADR-0431 减法候选。
若后续 GitHub/子仓策略变化（如 agora 仓开放 merge commit），本契约第 3 条应复审修订。
