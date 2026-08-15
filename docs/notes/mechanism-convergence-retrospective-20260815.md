---
title: "机制收敛复盘（2026-08-15）"
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-15
---

# 机制收敛复盘（2026-08-15）

## 结论

本批只收敛已经发生的机制事实，不把“能力存在”写成“已获得工程结果”。
T1-05A 仍在 shadow 窗口，T1-18 只完成 accept leg，T7 仍缺周期样本；
T1-19 和 A2A 都不得因为本次收敛而提前推进。

## 已核实的收敛

### T1-05A：shadow 有实证，但窗口未结束

- 共享 SQLite WAL 协调层、claim/fencing/heartbeat 和 shadow 观测面已接通。
- 专用部署 clone 已留下 live runtime attestation；备份路径在发现 cron 指向漂移后完成人工恢复和 integrity 验证。
- SSOT 仍是 `BET-Y1Q1-T1-05A` 及其 retro。七天 shadow 窗口从
  `2026-08-14T12:56:00Z` 开始，只能在窗口跑满且 human gate 确认后置 done。

### T1-18：人工批准 accept leg 已实证

- 真实 approval-wait canary 在同一受管 terminal 完成 collect 与独立 verify，
  `WorkflowVerified` 时间为 `2026-08-15T02:34:47Z`。
- 变更面只有
  `docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md`；独立验证回执为
  `sha256:df8dd2245e47ab409e41646408bc0eb522f3ec905e10b0bf4d62001d900bc49c`。
- reject + compensation rollback leg 尚未执行，因此 `BET-Y1Q2-T1-18` 保持
  `candidate`，不得声称整条闭环已完成。

### affected-hash 假门禁收敛为可复算 receipt

旧 claim 门禁只校验 `affected_hash` 非空，dummy 值也能通过，没有把
changed project、affected project、layer contract 和被认领路径绑定起来。现在改为
`affected-graph-receipt/v1`：生成器和 OMO 均复算 canonical hash、layer-contract digest
和受影响图，未知项目 fail closed。

独立红队又补了三个绑定漏洞：

1. 拒绝模糊宽路径 `projects`，防止 workspace-root receipt 冒充所有子项目。
2. receipt ref 必须是 workspace 内 canonical repo-relative regular file，拒绝绝对路径、
   traversal、symlink 和外部文件，运行台账不再持久化本机绝对路径。
3. 任何非空 surface claim 都要求 `workspace-root`；生成器只能在 workspace
   内原子、排他地发布新 receipt，不覆盖既有 evidence。

### PR #1498：done 不再仅看台账字面

PR #1498 已合并独立 done 抽样审计：10 个样本中 2 个 false done，
1 个因漂移无法验证，6 个缺 retro，只有 7/10 可按现有证据判为诚实。
这个结果是快照审计，不应被改写成对整个台账的成熟度背书。
集成门同时发现并修复了跨提交的 capability registry 生成文档漂移。

## SSOT 边界

- 状态、依赖和 done_when 以 `docs/plans/3y-bet-ledger.yaml` 为准。
- T1-05A 运行结论以共享 coordination store 的 status/attestation 与
  `.omo/_knowledge/retros/BET-Y1Q1-T1-05A.md` 为准；文档不反向生成运行真相。
- workflow claim 以 OMO 重算验证的 receipt 为准；root 生成器只生成候选证据。
- T1-18 的 accept 回执只证明已完成的 leg，不修改 BET 状态，也不替代
  reject/rollback 证据。

## 运行态快照与未完成项

本轮收口时的运行态观察为 **0 条 personal accepted** 和
**0 条 engineering decision outcome**。这两个数字是当时快照，不是长期常量；
后续判定必须回到权威运行事件与 memory-os 投影。所以 T7 的“每周至少 20 条”
尚未验证，不得用 scene lifecycle 已是 shadow 来代替 outcome 产出。

未完成项是：T1-05A shadow 窗口跑满与 human gate；T1-18 reject/rollback；
T7 真实周期样本；依赖 T1-18 的 T1-19；以及不在本轮目标中的 A2A。
在这些边界没有新证据前，**不推进下一轮**。
