---
schema_version: specification/v1
spec_version: 1.0.0
title: 常驻自愈派发按 objective 折叠重复建档
bet_id: BET-Y2Q4-T10-345
status: accepted
lifecycle: contract
last-reviewed: 2026-11-10
---

# 常驻自愈派发按 objective 折叠重复建档

## 1. 缺陷与实测

`projects/omo/src/omo/resident/dispatch.py::dispatch_task` 每次调用无条件做三件事：新建
`TSK-<epoch>-<uid6>` 封套、落一份 TaskObject JSON、落一张 Action Desk 卡片，然后（`auto_worktree=True`
时）调 `prepare_isolated_worktree()`。没有任何按目标去重的分支。

巡检与大屏 triage 是**周期性重报同一条件**的生产者：

- `omo/resident/patrol.py::probe_projection_lease` → `interact.py::triage_component_failure`
  （`auto_dispatch` 默认 True）→ `dispatch_task`
- `interact.py:1492` 的 HTTP `POST /resident/triage` 同链路
- 定时自愈（`HEAL_*` 系列 objective 由 cron 侧固定字符串产生）

实测主仓已提交的 `.omo/_truth/task-center/dispatches/`（2026-11-10，33 份 JSON）：

| 重复度 | objective |
|---|---|
| 10 份 | `自治自愈 [HEAL_BRANCH_CLAIMS_ARCHIVE]: 将超期已完成的分支认领文件归档至 .omo/tasks/archive` |
| 6 份 | `自愈修复: dashboard_projection · 根因初判: dashboard_projection 运行态…` |
| 5 份 | `自愈修复: projects/omo/tests · 根因初判: …代码逻辑或…` |
| 4 份 | `自治自愈 [HEAL_TEMP_RESIDUE]` / `[HEAL_STRAY_TEST_SCRIPTS]`（两种措辞各 4 份） |

那 10 份 `HEAL_BRANCH_CLAIMS_ARCHIVE` 的时间戳是 2026-10-22 至 2026-10-27 的每天 18:30 与 19:00 两个节拍，
`status` 全部 `worktree_missing` —— 即同一条件每节拍新建一档，且从未真正执行成功。

## 2. 判据：只能按 objective 的新鲜度，不能按状态

去重需要一个「这条还没了结」的判据。平面里没有：

- `task-object-v1` 协议（`projects/runtime/protocols/task-object-v1.md`）**未定义状态枚举**，
  只有字段表；`L0-registry.yaml` 里 TaskObject 条目 `status: partial`。
- `dispatch.py` 自身只写 `pending_isolation` / `worktree_ready` / `worktree_failed` 三值。
- 已提交 33 份的实际状态分布是 `ready_for_review`(12) / `worktree_ready`(11) / `worktree_missing`(10)，
  其中 `ready_for_review` 由 `omo/resident/worker.py:78,183` 写入；`worktree_missing` **没有任何代码写入方**
  （全库检索只命中 `ADR-0466` 的诚实失败措辞与 `bin/gac/check-test-host-hygiene.py:58` 的注释），
  它是执行侧按 ADR-0466 手写进记录的。
- 结论：没有任何写入方会把任务标成「已了结」，按状态去重等于永不放行；判据只能是 objective 归一化文本 +
  新鲜度窗口。

## 3. 方案

`dispatch_task` 在造封套之前先查一次既有档案：

- 键：`" ".join(objective.split())`（归一化空白，字节级同文即同键）。
- 窗口：`OMO_DISPATCH_DEDUPE_TTL_S`，默认 `259200`（3 天）。取 `created_at`（无时区按 UTC 解释）与窗口比较；
  解析失败、非 JSON、缺 `created_at` 的记录一律不参与判定（不误吞新派发）。
- 命中：返回既有 `task_id` / `session_id` / `target_agent`，`worktree.path` 用既有记录里的值、
  `worktree.ok` 只在该路径**真的存在**时为 True，`message` 点名折叠；`card_registered=False`、
  `deduplicated=True`、`existing_status` 带上既有状态供调用方显示。不新建文件、不新建卡片、不 claim worktree。
- 未命中：行为与今天完全一致（含 `dry_run` 语义）。

**不做读改写**：命中时不去更新既有 JSON 的计数或时间戳。这些记录会被执行侧按 ADR-0466 手写状态值，
read-modify-write 会与手写撞车，收益（保留“仍在复发”信号）不值这个风险。因此重复派发折叠后仍按窗口
产生新档，残余增长是有界非零；把该面彻底止住需要裁掉「运行态派单 JSON 是否该进 git」这条 trackedness
分叉——BET-Y2Q4-T10-289 已把它登记为未裁分叉，改 `.gitignore` 或摘库须 principal 另行授权，不在本轮。

## 4. 消费面

`dispatch_task` 返回字典的四个键被 `interact.py:501` 直接下标读取（`task_id` / `target_agent` /
`session_id` / `worktree.message`），`interact.py:1043` 走 `.get()`；去重分支必须同样提供这四个键，
否则折叠会把 triage 接口打成 KeyError。其余 `dispatch_task` 同名符号
（`omo.omo_worker_dispatch.dispatch_task`、`bin/ssot/agent-federation.py:322`）签名不同、不受影响。

## 5. 验收

见台账 `BET-Y2Q4-T10-345` 的 `done_when` / `verify`：正例（同 objective 两次调用只留一档）、
反例（不同 objective 各自建档、窗口外允许再建档）、消费面四键不缺失、`dry_run` 既有契约不放宽、
`test_resident_worker.py` 与 `test_resident_dispatch.py` 零回归。
