---
type: ephemeral
status: archived
---

# BET-Y1Q4-T5-03 复盘（batch 1：spec 绑定 + resident A2A 委托闭环）

## Q1 实际耗时 vs appetite？超出比例？
Appetite 2 days。本 batch 为单会话交付：spec 新建 + ledger 绑定 +
agora 侧 resident-orchestrator 卡片与 `resident.*` 本地派发 + 8 个新测试。
未超 appetite；剩余 budget 留给 batch 2（长时后台任务语义/真实 resident
端到端演练 + candidate→done transition）。

## Q2 done_when 是否全部通过？
batch 1 覆盖 ledger done_when 中的子集：
1. `list_agent_cards` 含完整 resident-orchestrator 卡片元数据及 Capabilities —
   通过（well-known 规范卡：3 skills 后台分析/深度巡检/对账 + 6 capabilities；
   registry 若未来注册同名 service 则实时合并优先）。
2. `a2a_send_task` 提交 resident 任务返回有效 task_id 与状态跟踪 — 通过
  （`resident.status` / `resident.roles` 本地短路派发；deferred→submitted→
   可 query/cancel，immediate→completed 携 result；未知 `resident.*` 直接
   fail-closed 不建 task）。
3. A2A 委托与结果拉取闭环测试 — 通过
  （`tests/test_resident_a2a.py` 8/8；回归 `test_a2a_smoke` + registry +
   replay-protection 92/92；ruff clean）。
4. circuit_breaker（幂等 ID + 超时隔离 + fail-closed）— 通过
   （`idempotency_key` 重复提交返回同一 task 不重复执行；`timeout_s`
   超时仅标 failed；异常不挂起主进程）。

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. **A2A 任务原语早已存在**：`a2a_send_task/get/list/cancel` 与
   `list/get_agent_cards` 已在 `tools_governance.py` 落地并有 smoke 覆盖；
   本 bet 的真实增量是 resident 可发现性 + `resident.*` 可派发性，
   不是从零建 A2A。
2. **运行时 TaskManager 来自 metaos 子模块**（`metaos.a2a.task_manager`，
   admission extra），不是 `agora/task_manager.py`（那是另一套网关内模型）；
   governance 的 `create_task("", tool_name, …)` 签名只在 metaos 实现上成立。
3. **`gac-worktree.sh claim` 曾超时并清空几乎全部子模块工作树**
   （agora/metaos/ecos/cockpit 等全 D staged）：逐个
   `git reset --hard HEAD` 恢复；root 侧 `projects/cockpit` gitlink 漂移
   （5bda8fa vs 登记 68432c2）为 worktree 创建时既有状态，本 batch 未碰。
4. **`bet-ledger.py spec-init` 是 yaml 全量 dump**：首次绑定造成 143 行
   reflow churn，已回滚改外科手术式文本编辑（diff 14 行：status→in_progress +
   accepted_specifications + completion_evidence）。
5. **`in_progress` 强制要求 completion_evidence 矩阵**：首个 in_progress BET
   会独触发 lint ERROR；本 batch 以诚实矩阵
   （engineering IN_PROGRESS / operational+value NOT_PROVEN →
   overall evaluating）过门，VERIFIED/PROVEN 留给 done transition。
6. **claim/start 交织三坑**：start 的 actor 取 `--actor`/`$USER` 而非
   `--profile`（holder 本人需显式传 `--actor engineering-agent`）；
   `claim --path` 需先跑 affected-graph 并传 `--affected-hash` receipt 路径；
   claim-bet 广播落主 checkout 共享区，worktree 间互相可见。

## Q4 净增减
- spec：+1（docs/superpowers/specs/2026-09-11-t5-03-resident-a2a-delegation-spec.md）
- 台账：T5-03 candidate→in_progress + accepted_specifications（1 条）+
  completion_evidence（evaluating 诚实矩阵）
- agora 代码：tools_resident.py（规范卡 builder + impl 抽取 + RESIDENT_A2A_TOOLMAP）+
  tools_governance.py（resident 本地派发/幂等/超时 + 卡片接线 + bos 域映射）
- agora 测试：tests/test_resident_a2a.py（8/8，--extra admission 下运行；
  缺 metaos 时按既有 importorskip 惯例跳过）
- 分支：agora `agent/engineering-agent/t5-03-resident-a2a`；
  root `agent/governance-agent/t5-03-a2a`（PR 不 merge，batch 2 继续）

## Q5 下一个 agent 需要知道什么？
1. ledger 编辑禁止 yaml 全量 dump，只能定点 edit；改后跑 `bet-ledger.py lint`。
2. agora 测试必须带 `--extra admission` 跑（否则 metaos 缺席整模块 skip，
   包括既有 test_a2a_smoke）。
3. batch 2 事项：真实 resident 长时任务语义（working 状态推进/产物拉取）、
   外部瞬态 Agent 端到端演练、completion_evidence 升级到 VERIFIED/PROVEN +
   candidate→done transition。
4. run-id：20260911T071722Z-bet-execution-65455711；path claim 覆盖 4 个
   write_surfaces；receipt 在 `.omo/evidence/<run-id>/`（untracked，不入库）。
