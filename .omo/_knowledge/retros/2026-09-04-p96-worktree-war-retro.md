---
schema_version: retro/v1
bet_ref: N/A (周期级复盘)
title: P96 共享 worktree 战役复盘 — 12 案时间线与机制化路线
status: active
owner: governance-team
last-reviewed: 2026-09-04
type: ssot
---

# P96 复盘：共享 worktree 战役（累计 12 案）

## 时间线（按发现序）

| # | 案件 | 现象 | 抢救手段 |
|---|------|------|---------|
| 1 | rebase 落错分支 | rebase 输出指向他人分支名 | 确认 ref 后重放 |
| 2 | 本地分支 ref 被覆盖 | gitlink 修复 commit 从分支脱落 | reflog 找回对象 |
| 3 | 远端分支被劫持强推 | PR head 被覆写为空 diff | 重放 + force-with-lease |
| 4 | Edit 工具静默失效 | 报告成功但文件未变 | 改用 python 直写 + git diff 验证 |
| 5 | rebase 吞 commit | T1-02 commit 被 squash 进他人 commit | 内容验证（对象在即可） |
| 6 | 3-way merge 静默吞行 | value_indicator_policy 一行蒸发 | 行为级验证（lint）发现 |
| 7 | rebase 完 HEAD 停错 ref | 修复 commits 落在 main 而非工作分支 | branch -f 重指 |
| 8 | 死循环 | 对不存在文件重复 find ×10+ | 用户点破即停 |
| 9 | staged 劫持（第 12 案） | 我 staged 的 gitlink 被并行 agent 的 commit 吞走 | 从 origin/main 重放干净分支 |
| 10 | 子仓 detached HEAD commit | doc-index 修复 commit 不在任何分支 | 建分支 + ff push（P97 之源） |
| 11 | 临时分支被借 commit | tmp-pick 上挂了并行 agent 的报告 commit | 不动它，开新分支隔离 |
| 12 | gitmodules 残留注册 | cockpit-ui untrack 后 .gitmodules 死条目 → PASW FAIL | 移除注册对齐 untrack 决策 |

## 根因

**共享 worktree（多 agent 并发读写同一 HEAD/index/refs）零仲裁。**
git 的 index 和 HEAD 是单用户设计的，N 个并发 agent 写 = 必然竞态。
每案都靠 reflog/orphan-recovery 人工抢救，无一机制防复发。

## 已落地机制（2026-09-04 起）

| 机制 | 位置 | 覆盖案件 |
|------|------|---------|
| post-checkout orphan-recovery tag | .git/hooks（既有） | 2/5/7/9/11 |
| submodule-reachability-gate（PASW, CI） | bin/ssot/ | 10（延迟发现） |
| pre-commit submodule-guard fast-forward 校验 | .git/hooks（既有） | 部分 10 |
| **pre-commit gitlink 可达性前置**（本次新增） | bin/git-hooks/pre-commit | 10 提前到 commit 时拦 |
| **post-checkout checkout-log 追溯**（本次新增） | bin/git-hooks/post-checkout | 1/7/9/11 可追责 |

## 待落地（按优先级）

1. agent 级分支前缀注册（agent checkout 前必须 `git checkout -b agent/<id>/…`，
   hook 校验分支名前缀）——根治 1/7/9/11
2. 每 agent 独立 worktree（git worktree add per-agent）——根治一切，但成本高
3. index 写锁（.omo/locks/staging.lock，pre-commit 检测并发 staged 劫持）——根治 9

## 铁律（写给所有 agent，含未来的自己）

1. **子仓操作前先 `git checkout -b`，绝不 detached HEAD 裸干**
2. commit 后必须 `git show HEAD --stat` 验证内容（防静默失效）
3. 大 YAML rebase 后必须跑行为级验证（lint），光看无冲突标记不算数
4. 发现重复动作立即停（死循环税）
