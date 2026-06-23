---
plane: knowledge
type: audit
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
freshness: 2026-05-31
maintainer: auto
note: "P55 R2: 历史 OMO convergence 审计快照 (Phase 6 时期), 当前 governance 100 A+ 已远超当时基线"
---

# OMO convergence audit

> Historical convergence audit / reference only. This audit records a 2026-05-31 convergence assessment and is not the current status/goal/index truth SSOT.
> Current runtime truth should be read from `/.omo/state/system.yaml`, `/.omo/goals/current.yaml`, `/.omo/_truth/`, and current governance checks.

## Scope

本轮审计覆盖三组输入：

1. 当前 `.omo` 四平面与 Wave 2 治理固化实现
2. `task-center-requirements.md` v0.2.x 与其三份审阅报告
3. 最新状态/目标/索引/自动化测试之间的收敛情况

## Overall judgment

`.omo` 当前是 **结构收敛、语义未完全收敛** 的状态。

- **结构层面**：四平面入口、Wave 2 gate model、worker baseline/triage 已经把此前最危险的 shadow queue / status 漂移压下来了。
- **语义层面**：如果只看文档和测试名称，系统看起来已经收口；但如果追 gate 规则、索引快照、Task Center 新设计与现有四平面约束之间的细节，仍然存在会慢慢长出“影子 SSOT”的点。

## Convergence wins

1. **四平面入口已经成型**：控制、事实、知识、交付四个入口现在可以稳定回答“状态 / 真相 / 设计 / 证据”四类问题。
2. **Wave 2 把 canonical status 与 gate facts 分开了**：`task.status` 不再被继续扩展为半流程字段，这是最重要的一条治理边界。
3. **状态同步从手工维护转向派生**：`sync_omo_state.py` 现在会重建 `next_active_tasks`、gate summary、promotion blockers、triage summary。
4. **divergence 开始有治理语义**：不再只是发现问题，而是开始区分 severity / owner / disposition。

## Corruption and drift risks

### 1. Live snapshot copied into indexes

此前根 INDEX、控制面 INDEX、truth/delivery 子索引中出现了硬编码任务数、健康分、完成数等易变数字。

这类内容会快速过期，并把“导航页”重新变成半个状态面。  
本轮已收敛为：**索引页只链向 live source，不再复制易变计数**。

### 2. Gate semantics can silently drift from the standard

Wave 2 标准要求：

- `dispatched` 需要 `dispatch_id + run_ref + assigned_to`
- `accepted` 需要证据完整、无阻断 divergence、并且有 completion summary

本轮已把 `sync_omo_state.py` 收紧到这套语义，避免“标准说一套、状态推导跑另一套”。

### 3. Task Center is ahead of the repository

Task Center 需求文档已经引入 `_truth/task-center/` 与 `_delivery/task-center/`，但当前仓库尚未正式落地这些目录与实现。

这不是坏事，但意味着 **设计包已经领先于 repo reality**。  
如果不先定义落位规则，后面最容易出现的问题就是：

- 设计文档写一套目录
- 四平面导航再写一套解释
- 实现代码又写出第三套现实

因此本轮补了一个明确规则：Task Center 属于 **plane-native domain**，允许直接落在 owner plane，但禁止在其他平面镜像复制 registry/run data。

### 4. Task Center still had unresolved semantic seams

在进入本轮之前，Task Center 文档里还存在几处“看起来已修，但实际上没完全收口”的点：

1. webhook 示例仍然使用明文 `secret`
2. `deliver` 仍然带有 `origin(iLink)` 这类歧义语义
3. 顶层默认项里没有并发/队列默认值
4. hermes 仍被表述成核心桥接，而不是兼容层
5. R2 / R8 风险缓解仍偏旧

这些点本轮已收敛到正文约束里。

### 5. Divergence remains too coarse

`orphaned_tasks:*` 目前仍是一个大 blob。  
它已经可见，但还不够可治理。真正下一步应该是把它拆成 per-task 或 registry-style artifact，而不是继续让 `state/system.yaml` 承担“大段 backlog 列表”的职责。

## Decisions landed in this round

1. **Gate semantics aligned to Wave 2 standard**
   - `dispatched` 现在要求 `dispatch_id`
   - `accepted` 不再因为 `status == done` 自动成立
   - `done` 缺少 `completion_summary` 会形成 blocker
   - `status: active` 不再作为 canonical task status 的隐形残留

2. **Indexes no longer mirror live counters**
   - 根入口、控制面、truth、delivery 索引移除了硬编码数量
   - 所有动态事实统一回到 `state/system.yaml` / `goals/current.yaml` / `tasks/*/`

3. **Four-plane rule clarified**
   - 默认保持导航壳
   - 允许单 owner plane 的 plane-native domain
   - 禁止在 INDEX 中复制 live facts

4. **Task Center requirement doc tightened**
   - webhook 示例改为 `secret_ref`
   - `deliver` 收敛为 `local | notify`
   - 新增 `notify_channels` / `max_concurrency` / `queue_limit`
   - hermes 降级为兼容层
   - R2 / R8 风险条目改为更现实的缓解路径

## Remaining priorities

### P0

1. 将 `orphaned_tasks` 从 blob 拆成结构化 registry 或逐项 flag
2. 为 `accepted` / divergence blocker 增加更强的行为测试，而不只是字符串/文档测试

### P1

1. 生成真实的 handoff index artifact，而不只是有脚本和入口
2. 扩展 worker utilization baseline，使其真正覆盖 review completion / average handoffs

### P2

1. 决定 Task Center 的 secrets 归属模型
2. 在 Task Center 进入实施前，刷新三份 v0.1 review 的“已吸收/已过期”状态，避免旧审阅报告再次变成新的腐败来源

## Summary

本轮判断不是“`.omo` 已经腐败”，而是：

**`.omo` 处在一个已经明显收敛、但很容易因为新设计包和导航层继续扩张而再次长出影子 SSOT 的窗口期。**

只要继续坚持两条铁律，系统仍会继续收敛：

1. **动态事实只在 live source 中存在**
2. **新机制只允许一个 owner plane，其他平面只做索引/状态/解释**
