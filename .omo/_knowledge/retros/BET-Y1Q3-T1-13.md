---
lifecycle: history
owner: governance-team
last_updated: 2026-09-04
title: BET-Y1Q3-T1-13 复盘
type: retro
bet: BET-Y1Q3-T1-13
date: 2026-09-04
run: 20260904T015823Z-bet-execution-5dfabb6f
---

# BET-Y1Q3-T1-13 复盘

> 北极星：织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。
> 指针：`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`

## Q1 实际耗时 vs appetite？超出比例？

appetite 0.25 day；实际约 0.1 day（含 worktree 搭建、子模块恢复、证据矩阵、开 PR）。超出 0%。

## Q2 done_when 是否全部通过？

| done_when | 状态 |
|---|---|
| projects/agora 子模块 index 已恢复，工作区文件全部存在 | ✅ `git submodule update --force --checkout` 恢复 agora（529 个暂存删除）、aetherforge（241）、bus-foundation（134） |
| agora/cockpit/omo commit 与父仓库 HEAD 指针一致 | ✅ `git submodule update --init` 后三者均无 `+`/`-` 前缀（agora 0bd4877 / cockpit f087095f / omo cac825fc == origin/main HEAD 记录） |
| 父仓库 `git status --short` 返回空 | ✅ 空 |

verify（`bet-ledger.py verify --execute`）：`git status --short` 空、`git submodule status` 无 `+` 前缀，D0 台账入库随本 PR，D2 表面积记账通过。

## Q3 过程中发现的与 plan 不符的事实（打假）

1. **漂移不在指针而在工作树**：origin/main（93310effb）记录的指针本身一致；漂移是 worktree 内 cockpit/omo 未初始化（`-` 前缀）+ agora/aetherforge/bus-foundation 工作树大面积暂存删除。`submodule update --init/--force --checkout` 即恢复，无需改指针。
2. **主树并发分支未碰**：主工作区存在并发分支 `chore/submodule-bump-cockpit-only-20260904`（e1206101c，cockpit f087095f / omo cac825fc），非 origin/main 内容，本 BET 以 origin/main 为基，不触碰、不 rebase。
3. **claim 需 affected 收据**：`agent-workflow.py claim` 要求 `--affected-hash` 指向工作区相对路径收据，且 changed-projects 须含 `workspace-root`（台账路径归属），收据用后即删以保工作树干净。
4. **done 需证据矩阵**：candidate→done 触发 `COMPLETION_EVIDENCE_REQUIRED` + `done_at` 门；本 repair 以 `value_indicator_policy: false` 走 delivery_accepted（engineering VERIFIED + operational PROVEN + value NOT_PROVEN），`merged_reachable_commit` 回填本 PR 提交，squash 合入后按回写惯例跟进。

## Q4 教训与固化

- 子模块 worktree 漂移优先用 `git submodule update --init --force --checkout`（受控命令），不用手写 reset。
- 主树只读：一切修改在 `ws-t1-13-closeout`（分支 `work/t1-13-closeout`）完成，主树并发工作一律不碰。
- **前次交付曾被相邻 PR 破坏**：#2988（2026-09-03）已将本 BET 置 done + 落盘 retro，但 #2993（T10-119，94aa91fa6）冲突解决时误删本条目的 completion_evidence/value_indicator_policy/retro 写面（同 PR 亦将 T10-200 done 打回 candidate，后由 #2995 修复）。本 PR 为按原语义的重新钉死，非重复交付；retro 已按当前 origin/main 指针（agora 0bd4877 / cockpit f087095f / omo cac825fc）刷新，前版 SHA（346e3fb/d5fb9a0/b907178）已过期，仅保留于 git 历史。
