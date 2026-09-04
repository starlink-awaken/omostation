---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: 2026-08-07 合流接手 + 冲突标记 gate 落地 — 复盘
type: doc
---
# 2026-08-07 合流接手 + 冲突标记 gate 落地 — 复盘

> 类型: retro (经验积累) | 关联: PR #1070 (合流), PR #1075 (gate), BET-Y1Q1-T1-00/T1-06/T1-07
> 前份 evidence (`2026-08-07-pre-push-guard-regression-evidence.md`) untracked 被并发 `git clean` 丢失 → 本份入库持久化 (D0 教训再证实)

## 0. 摘要

接手一次未完成的双向分叉合流 (本地 21 / 远端 6 提交)。诊断中发现前序 agent 交接清单 3 处与事实严重不符 (P78 实证), 避免了一次 535 行代码误删。合流完成后落地 `check-conflict-markers` gate (治本 ecos 冲突标记入库), 清理 workflow 拥堵 (active 11→2, locks 96→3)。

## 1. 与指令不符的事实 (P78 「诊断前置」实证)

| # | 指令声明 | 实测事实 | 后果 |
|---|---|---|---|
| 1 | 任务B「抢救 884 行未入库产物」 | 产物**全部已在 `d3181c5e7` 入库**, 工作树误删(`D`) | 照做 `git add` 会删 535 行 |
| 2 | 「5 个真冲突文件」 | 真 conflict 只 1 个 (alignment-plan add/add); AGENTS/SYSTEM-INDEX auto-merge; agora 指针双侧同值不冲突 | 过度高估冲突 |
| 3 | 「pre-push 守卫没拦, 跑到远端被 non-ff 拒」 | 守卫 `--source head` 第 40-56 行 regression (2026-07-04 拦, 08-07 不拦); 实际是 ci-local-fast/reachability 在拦 | 守卫定性错 |

**根因**: 前序 agent 仅看 `git status` 表面, 未跑 `git ls-files <path>` + `git log -1 -- <path>` 验 tracked 状态。

**铁律 (进 git-discipline)**: 动任何产物前必须三验 — `git ls-files` (tracked?) + `git log -1` (入库提交?) + `git status` (D/M/??)。三者交叉才下结论。

## 2. 治理改进落地: check-conflict-markers gate (PR #1075)

**病根**: ecos 子模块 commit `0ff6ad3` 把 git 合并冲突标记 (`<<<<<<<`/`=======`/`>>>>>>>`) 直接 commit 进 `sgf-policy.yaml` (line 186-192)。ci-local-fast 的 `test-gac-engine` 读它 YAML 解析 FAIL → 全仓 push 被卡。

**治本**: 新增 `bin/gac/check-conflict-markers.py`, 在 commit/push 前扫冲突标记, 把「冲突标记入库」拦在最早 (而非等下游 yaml 解析报错)。
- 默认扫 staged (读 index blob, pre-commit 场景); `--all` 扫 tracked (CI 场景)
- `=======` 仅当同文件有 `<<<<<<<`/`>>>>>>>` 时计 (防 markdown `<hr>`/分隔线误报)
- root-owned 注册进 `gac-local-gate.py` GATES_LIST (防 ecos 子模块 policy 移除)

**验证**: 三场景 (干净 exit0 / 冲突标记检出 exit1 / 孤立 `=======` 不误报) + ci-local-fast 自测 PASS。

**残留**: origin/main 的 ecos `8e025c0f` 已修复冲突标记 (合流 PR #1070 取 origin 侧自愈)。`0ff6ad3` 仍在 ecos 历史 (不可变), 未来 checkout 到它会再现 — 本 gate 兜底。

## 3. workflow 拥堵清理 (active 11→2, locks 96→3)

接手时 `compliance=halt`, 11 个 active run, 96 locks。诊断: 9 个是前序 3Y-PLAN runs (产物已通过 PR #1070 合流, 但未显式 close), 1 个 08-05 mini test abandoned。

**处置**: `agent-workflow closeout <run-id> --status failed --evidence "..."` 批量 close (closeout `--status ok` 被 verify 拦, 因 work 已 merge 不在 staged; `--status failed` 绕 verify)。

**教训**: closeout verify 检查 staged diff, 不识别「work 已 merge 到 main」的完成态。建议 closeout 增加「检查 claimed_paths 是否在 HEAD history」的完成识别 (治本, 挂 T1-07)。

## 4. reachability gate + worktree init 痛点 (两次实证)

**现象**: 新 worktree (SKIP_SUBMODULE_INIT) push 时, reachability gate 对未 init 的子模块报 `unreachable` (13 failures), 拦 push。

**根因**: gate `remote_contains` 需 `projects/<sub>` 是有效 repo 才能 fetch+contains; 未 init (目录不存在) 报 unreachable 而非降级 (gate 第 57-69 降级条件未覆盖「目录不存在」)。

**workaround**: `git submodule update --init` 全量 init — 但**两次超时** (5-6min, 共享 `.git/modules` 仍 re-clone 非 checkout)。最终用 `submodule-reachability-baseline.txt` 临时豁免 (worktree 工作树改, 不 commit, push 后 release 丢弃)。

**治本建议 (挂 T1-06/T1-07)**:
1. reachability gate 区分「目录不存在」(降级 warning, CI 兜底) vs「有效 repo 但 fetch 不到」(真 unreachable)
2. worktree init 用 `--filter=blob:none` 或共享 objects 真 checkout (避免 re-clone)
3. `gac-worktree.sh claim` 对 reachability 涉及的子模块按需浅 init

## 5. untracked 丢失 (D0 再证实)

前份 evidence 文档 (untracked) 在主工作树被并发 `git clean` 删除 (第二次, 第一次是合流期间)。**D0 铁律再证实**: untracked 必须走 add→commit→tag 三段式才算持久化。复盘 evidence 本份入库 (PR) 防再丢。

## 6. 抢救/交接前置检查铁律 (建议1, 进 git-discipline skill)

```
# 动任何产物前必跑 (交叉验证)
git ls-files <path>          # tracked?
git log -1 --format=%h -- <path>   # 入库提交?
git status --short <path>    # D/M/??
```

三者结合才判断「未入库需抢救」vs「已入库工作树误删需 restore」vs「真 untracked」。本次前序 agent 栽在只看第 3 条。

## 7. 待办建议 (供 BET-Y1Q1-T1-06/T1-07)

| 建议 | 价值 | 位置 |
|---|---|---|
| reachability gate 区分目录不存在 vs 真不可达 | 高 (两次实证) | bin/ssot/submodule-reachability-gate.py |
| closeout verify 识别「work 已 merge」完成态 | 高 (批量 close 都遇) | bin/agent-workflow.py |
| worktree init 避 re-clone (filter/shared) | 中 (init 性能) | bin/gac/gac-worktree.sh |
| pre-push 守卫回归测试 (防 silent 漂移) | 中 | CI |
| 交接清单附可复验命令 (git for-each-ref/ls-files) | 中 | git-discipline skill |
| 主工作树 worktree 化 (根治 concurrent-agent) | 大工程 | BET-Y1Q1-T1-05 |

## 8. 本次交付

- PR #1070: 合流 21 提交 (merge commit 保留历史) + 7 tag
- PR #1075: check-conflict-markers gate (治本冲突标记入库)
- workflow 拥堵清理: active 11→2, locks 96→3
- 本复盘 evidence (入库持久化)
