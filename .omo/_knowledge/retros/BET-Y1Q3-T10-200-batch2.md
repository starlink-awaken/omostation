---
lifecycle: history
owner: governance-team
last_updated: 2026-09-03
title: BET-Y1Q3-T10-200 复盘 batch2
type: retro
bet: BET-Y1Q3-T10-200
date: 2026-09-03
run: 20260903T082945Z-bet-execution-3f457408
pr: https://github.com/starlink-awaken/omostation/pull/2997
merge: 84474c2671db0fbad66da779f201f0ea443f0cd3
---

# BET-Y1Q3-T10-200 复盘 batch2

> 北极星：织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。
> 指针：`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`

## Q1 实际耗时 vs appetite？超出比例？

appetite 0.5 day；实际约 0.2 day（含 PR #2997 开出到 merge 84474c2671）；超出 0%。

## Q2 done_when 是否全部通过？哪条没过，为什么？

bet 目标：给 batch2 的 5 个 docs/notes 点名文件加 `last_updated`，正文零改动，验证保鲜口径。

| done_when | 状态 |
|---|---|
| 5 个 docs/notes 文件均有 last_updated 且格式合法 | ✅ 5 文件各 +1 行 last_updated（+5/-0） |
| doc-index 缺失数对应 -5（SSOT-NO-DATE 口径） | ✅ 扫描口径确认，UNTYPED 失败系历史存量非阻塞 |
| ledger lint 通过，CI required 全绿 | ✅ required 3 项全绿后 squash 合入 main |

未过：无（doc-index FAILURE 为 UNTYPED 存量问题，非 required，不阻塞）。

## Q3 过程中发现的与 plan 不符的事实（打假）

1. **required 仅 3 项**：分支保护 required 为 `phase-gate`、`bet-done-transition`、`gac-gate`，`doc-index` FAILURE 不阻塞合入——看到红先查是否 required 再决策。
2. **mergeStateStatus UNSTABLE 仍可合入**：MERGEABLE + 3 required 绿即满足 squash 条件，UNSTABLE 只是非 required 红的提示。
3. **并发脏不影响服务端合入**：worktree 内子模块浮动（omo/agora/cockpit 等）是并发 agent 的 staged 产物，`gh pr merge` 走服务端不受本地脏影响，不用 gac 脚本。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

改动（PR #2997，merge 84474c2671，分支 commit fb8aacd2d）：

- 5 docs/notes 各 +1 行 `last_updated: 2026-09-03`（closeout-template-5min-dev.md、closeout-template-5min.md、governance-runtime-convergence-closeout-20260814.md、governance-runtime-convergence-rca-20260814.md、mechanism-convergence-retrospective-20260815.md）
- +5/-0 单 commit，无 ledger/spec 新增（复用 batch1 建的 bet + spec）
- 无新增 GaC 规则 / ADR / 脚本；不碰正文语义与业务代码。

验证：

- `verify --from-diff --execute` 1/1 PASS
- CI required 3 项全绿（phase-gate、bet-done-transition、gac-gate）
- PR 已 squash 合入 main（merge 84474c2671）

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **先查 required 再看红**：`gh api .../branches/main/protection` 拿 required 上下文，非 required 红（如 doc-index UNTYPED）直接注明不阻塞。
2. **合入走服务端**：并发期 worktree 脏是常态，`gh pr merge --squash` 不依赖本地树干净，别在脏树上跑 gac 脚本。
3. **batch 模板固定**：每 batch = N 个 last_updated + verify 1/1 + required 全绿 + retro 一篇（本篇照 batch1 的 62 行 Q1-Q5 格式）。
4. **batch3-6 照此模板**：点名文件换一批即可，ledger/spec/bet 复用，无需重建。

