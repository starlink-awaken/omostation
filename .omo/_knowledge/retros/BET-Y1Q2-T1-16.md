---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-16 复盘
type: retro
---

# BET-Y1Q2-T1-16 复盘

## 交付与真实回执

本轮修复的是“能力曾交付，但未进入子仓主线”的持久化断链。OMO personal 能力经
[PR #37](https://github.com/starlink-awaken/omostation-omo/pull/37) 合并到 `main`，提交为
`2bd55bc4e7bec62506f346398e412b6092ac450e`；Cockpit personal API/CLI、feedback 修订和隐私边界经
[PR #47](https://github.com/starlink-awaken/omostation-cockpit/pull/47) 合并到 `main`，提交为
`36f92f3a405466b4372fc2a2b2e5254915db58e3`。根仓随后只更新这两个远端 `main` 精确指针。

根指针门新增 `--require-main`：feature-only SHA 即使存在且远端可达，也不能再作为发布指针；远端
查询、fetch、对象或 ancestry 失败均非零退出。根定向测试 8 条通过，索引态 19 个 gitlink 的
`source=index --require-main` 实测通过。子仓恢复后 OMO 153 条、Cockpit 97 条根集成回归通过；Cockpit
PR 平台 lint/test 均绿，独立复审额外以真实 OMO 跑了 64 条 personal 回归和隐私探测后 APPROVE。

公开入口 `cockpit workflow mesh personal --help` 已重新提供 `setup/ingest/confirm/draft/feedback/status`。
共享运行 Ledger 的只读查询仍只有一条 `SignalObserved`、一条 `Evidence.LocalDraft`，没有
`Outcome.Human`。因此本轮只恢复了可重复使用的工程能力，个人价值北极星仍为 0，不以测试、PR 或
system draft 代替本人裁决。

## Q1 实际耗时 vs appetite？

约半天，低于 2 days appetite。主要耗时不是恢复代码，而是处理当前主线兼容、两轮 Cockpit 隐私/反馈
红队、独立仓 CI 私有依赖错误，以及根仓并发前进后的二次集成。

## Q2 done_when 是否全部通过？

全部通过：

1. OMO/Cockpit 恢复提交均已进入各自 `origin/main`，不是 agent 分支或 tag-only 对象；
2. 根 gitlink 在两个子仓合并后才更新，并由 `--require-main` 验证；
3. main-ancestry 单测覆盖 feature-only 拒绝、main 祖先通过与查询失败；
4. personal CLI 可发现，PEP/never-send/feedback revision/隐私与 Ledger hash chain 定向回归通过；
5. 运行 Ledger 查询保持只读，Human Outcome 诚实为 0。

## Q3 与计划不符的事实

1. Cockpit 第一版恢复遗漏 `feedback_id` 的 CLI/HTTP 全链，导致同一 Episode 不能可靠表达
   `accept → reject → accept` 修订。最终补齐可选 `feedback_id`，同 ID 幂等、新 ID 追加并以最新裁决生效。
2. Episode projection 原先直接暴露领域 payload，可能带出 `file://`、绝对路径和 source URI。最终改为
   公开字段白名单 DTO，并用真实临时 Ledger 做负向探测。
3. Cockpit CI 最初试图 checkout 私有 OMO/Agora/Iris，默认 `GITHUB_TOKEN` 无跨仓权限，测试在产品代码
   执行前失败。最终 CI 改为不依赖兄弟私仓的公共 HTTP/CLI 边界测试；跨仓完整回归仍在根集成门执行。
4. `submodule-pointer-transaction.sh` 在独立 clone 的 19 个 detached 子模块上可通过 dry-run，却在正式
   fetch 门等待期间缺乏清晰进度；本轮保留 `submodule-reachability-gate` 的确定性结果，并补齐 Cockpit
   PASW 镜像后由 pre-commit 完成提交。后续应给长 fetch 增加进度/超时回执，不能用等待态冒充失败。
5. Orca 内建 Codex worker 启动的是交互式 TUI。实际任务在 `git add`、`git tag`、push 等步骤反复要求
   人工确认，`worker ready` 并不等于无人值守。实测
   `codex exec --approve-for-me --ephemeral --ignore-user-config --json -C <independent-clone>` 可在
   `workspace-write` 自动审批边界内零人工确认完成；`--approve-for-me` 与显式 `--sandbox` 互斥，不能同时传。
   后续应做独立 `codex-exec-worker` adapter，由外层 supervisor 提供 deadline、进程组回收和结构化 receipt；
   禁止在共享 Workspace 使用 `--dangerously-bypass-approvals-and-sandbox`。

## Q4 净增减与必要性

根仓只新增 main-ancestry 门、对应测试、冻结规范、BET/复盘和两个子模块指针，没有新增任务数据库、
Ledger DDL、Workflow Mesh 状态机、UI、信号源或外部副作用。子仓恢复复用了已经审过的 personal 模块，
新增部分仅用于当前主线兼容、feedback 修订、隐私 DTO 与独立 CI 边界。

## Q5 后续提示

下一步先让本人对现有 system draft 写入一次真实 verdict、review duration 和 estimated time saved，再连续
四周每周至少三条低敏真实事项；未满足前不扩第二信号源或自治等级。多 Agent 方向则先把 Codex 从 TUI
launcher 收口为 `codex exec` 非交互 adapter，保持 OMO/ECOS 为唯一任务与完成真相，Orca 只负责运输和
进程生命周期。
