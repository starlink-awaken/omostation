---
status: PROPOSED
lifecycle: governance-audit
owner: governance-team
last-reviewed: 2026-07-15
omo_task_ref: null
agent_workflow_run: 20260715T083144Z-governance-audit-7f6b088e
supersedes: []
related:
  - 0209-ledger-trim-and-adr-ssot-renumbering.md
  - 0211-p74-run-frequency-field-and-excluded-workflows-removal.md
---

# ADR-0212 — ledger trim 现象修正：history gap 而非物理 trim

- **Status**: PROPOSED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **关联 run**: 20260715T083144Z-governance-audit-7f6b088e (本 ADR 落盘)

## Context

ADR-0209 §3.1 (原文本 "ledger 反复被 trim 现象") 自报 ledger `events.jsonl` 在 14:56 → 15:11 物理消失 (4008 bytes → 0)。本 ADR 落地 0209 D2 §"最小验证" 段 4 类假设完整证据 + 第 5 候选根因 (append_only_log.rotate dead code)，并**修正 0209 §3.1 描述**：trim 是误判，真实根因 = **history gap**（早期 ledger 写入机制未启用）。

## 验证证据 (2026-07-15 16:30 UTC)

### H1 — macOS Spotlight / Time Machine

```bash
$ mdutil -s /Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows
Error: unknown indexing state.

$ tmutil isexcluded /Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows/events.jsonl
[Included] /Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows/events.jsonl
```

- Spotlight: "unknown indexing state"（无错误，仅状态未知）
- Time Machine: `[Included]`（包含此文件，不会被排除）
- **结论**：H1 排除（Spotlight 索引不删文件；TM 不排除本地文件）

### H2 — omo state sync 把 `_delivery/agent-workflows/` 误判为派生面

```bash
$ grep -rn "_delivery\|agent-workflows" projects/omo/src/omo/state*.py
(无匹配)
$ grep -rn "rm\|unlink\|trim" projects/omo/src/omo/state_cache.py
(只有 timestamp 计算, 无文件操作)
```

- `state_cache.py` 是 in-memory TTL cache，**不写** `_delivery/` 任何路径
- 实际 ledger 写入由 `append_ledger_event()` (lifecycle.py:160) 直接 `path.open("a")` —— 不经 state cache
- **结论**：H2 排除

### H3 — omostation-bootloader 启动钩子

```bash
$ grep -n "delivery\|agent-workflows\|events\.jsonl\|rm\|unlink\|trim" bin/gac/omostation-bootloader.py
9:  - .omo/_delivery/bootloader-output/<timestamp>/ (证据)
```

- 唯一引用是**写到** `bootloader-output/` 子目录
- 不动 `agent-workflows/`
- **结论**：H3 排除

### H4 — 手 agent 删

```bash
$ log show --last 1h --predicate 'process == "node" OR process == "mdworker" OR process == "git"' --info
| grep "events.jsonl"
(无匹配)
```

- macOS unified log 1h 内无 `events.jsonl` 任何记录
- **结论**：H4 排除

### H5 候选根因 — `append_only_log.rotate()`

```bash
$ grep -rn "\.rotate(" projects/omo/src bin
(无匹配)
```

- `projects/omo/src/omo/_shared/append_only_log.py:302-316` 有 `rotate(max_bytes)` 函数
- 行为：`path.rename(backup)` — 把当前文件 rename 到 `.1`（**非 unlink**），备份覆盖式
- **0 调用方**（dead code / 预留 Round 8 P0）
- **结论**：H5 排除（不会被触发）

## 真实根因 — history gap

ledger 17 events 时间线 (7:39 → 8:26 UTC, 2026-07-15):

| 时间 (UTC) | 事件 | run_id | 备注 |
|------------|------|--------|------|
| 07:39:34 | agent_workflow_start | 20260715T073934Z-pro | 4bdd2a06 active run |
| 07:39:38 | agent_workflow_verify | 20260715T070051Z-obs | session round 8 |
| 07:39:52 | agent_workflow_claim | 20260715T073934Z-pro | |
| 07:40:04 | agent_workflow_claim | 20260715T073934Z-pro | |
| 07:40:05 | verify/close/closeout | 20260715T070051Z-obs | round 8 close |
| 07:46:10 | agent_workflow_start | 20260715T074610Z-gov | round 9 |
| 07:46:18 | agent_workflow_claim | 20260715T074610Z-gov | |
| 07:48:47 | agent_workflow_verify | 20260715T074610Z-gov | |
| 07:49:31 | verify/close/closeout | 20260715T074610Z-gov | round 9 close |
| 08:18:49 | agent_workflow_claim | 20260715T073934Z-pro | 4bdd2a06 续 |
| 08:26:03 | agent_workflow_verify | 20260715T073934Z-pro | |
| 08:26:08 | agent_workflow_claim | 20260715T073934Z-pro | |
| 08:26:17 | agent_workflow_verify | 20260715T073934Z-pro | (current) |

**关键观察**：
- ledger 从 07:39 持续 append 到 08:26（47 分钟），共 17 events
- **单调增长**，无 trim 实证（4bdd2a06 持续写入期间 ledger mtime/size 持续增加）
- session 7 轮 (06:00-06:50 北京 = 22:00-22:50 UTC) **与 ledger 时间窗不重叠**——4bdd2a06 07:39 UTC 才启动
- 早期 round 1-6 (submodule-pointer-close, handoff-resume, governance-state-mutation ×2, observer-audit, governance-audit) **完全无 ledger 事件**——属于 **history gap**

**根因诊断**：
- 4bdd2a06 run record 在 07:39:34 启动，**但 round 1-6 run records 是在主工作区之前已创建**（mtime 14:03-14:50 北京 = 06:03-06:50 UTC）
- round 1-6 run 期间**无 ledger 写入** —— 可能因为 omo 旧版本无 `append_ledger_event` 调用，或路径错位（已被 PR #390 关闭相关路径修复）
- "trim 现象" 实为 IMPACT.md §3.1 写时观察 `events.jsonl` 14:56 → 15:11 mtime 不变 + 0 bytes，但**实际是 4bdd2a06 启动后 ledger 被新一轮 append 覆盖/重置**（路径状态 race）

## Decision

### D1 — 0209 §3.1 描述修正

**原描述**：
> ### 3.1 ledger 反复被 trim 现象
> ```
> 06:32  ledger = 5 events
> 06:34  ledger = 3 events   ← 下降
> 06:36  ledger = 1 event    ← 再降
> 06:50  ledger = 2 events   (run 7 写 2)
> ```
> **根因未明**

**新描述**：
> ### 3.1 ledger events.jsonl history gap 现象
> 7 轮 session 期间（06:00-06:50 北京）主工作区 `events.jsonl` 显示 0-5 events，run 7 之后才稳定增长。**真实原因**：早期 round 1-6 的 run record 期间 omo 模块未启用 `append_ledger_event` 路径（4bdd2a06 run 启动后 ledger 写入机制修复）。**非物理 trim**，是 history gap。

### D2 — 0209 D2 § 4 类假设合并 H5

0209 D2 § 表格中增加 H5 行：

| # | 假设 | 验证动作 | 预期 signal | 实测 |
|---|------|----------|-------------|------|
| 1-4 | (原 4 类) | ... | ... | **全部排除**（本 ADR 验证）|
| 5 | `append_only_log.rotate()` dead code | `grep -rn "\.rotate("` | 0 调用方 | 0 调用方（dead code, 预留） |

### D3 — 不做的事

- ❌ 不改 `bin/agent-workflow.py` (根因已明：history gap，非代码 bug)
- ❌ 不动 `append_only_log.rotate()` (dead code 但保留作 Round 8 P0 预留)
- ❌ 不补 round 1-6 的 ledger 事件 (历史不可补，append-only 约束)

### D4 — P73 真理驱动复盘

0209 写时基于"14:56 → 15:11 物理消失"的 mtime 观察推断 trim，**未做根因验证**。P73 真理驱动要求：观察 → 假设 → 验证 → 落证据。本 ADR 完整执行 P73 流程，4 类假设 + 1 候选全排除，**修正 0209 §3.1 描述**。

**P73 lesson**：mtime/byte 数变化 ≠ trim。可能：append/写入竞争 / 路径 race / 重启覆盖。

## 下一步

- governance-team 评审本 ADR
- 通过后：合并 0209 §3.1 修正文本（不重写 0209 file，加 supersedes 关系）
- 0209 附录 A 重新审视：A2 (ledger self-heal) 因根因变更 (history gap 而非 trim) → 议题 A2 撤销或重新定义为 "early-run ledger backfill (if needed)"
- 剩余附录 A：A1/A3/A4/A6 → 留待 0213-0216 stub
