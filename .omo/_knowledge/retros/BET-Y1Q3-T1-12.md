---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-25
---
# BET-Y1Q3-T1-12 复盘（premature completion invalidated）

> **完成声明作废。** 本文件在 PR #2143 中提前生成，并错误声称 T1-12 已完成、全部 done_when
> 已通过且已有 production native receipt consumer。直接代码、ledger completion matrix 与 Orca 审计均推翻这些声明。
> 当前权威状态恢复为 `candidate`；Engineering `IN_PROGRESS`、Operational/Value `NOT_PROVEN`、
> `overall_state=evaluating`。本文件只保留为历史纠错证据，不是有效 completion retro。

Waiver 原句：

> 本次 BET-Y1Q3-T1-12 完成状态纠错跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/plans/3y-bet-ledger.yaml 将 BET-Y1Q3-T1-12 的 status: done 恢复为 candidate，以及 .omo/_knowledge/retros/BET-Y1Q3-T1-12.md 记录 premature completion invalidation；把本句写入 waiver 证据，不得修改 completion_evidence、其他 BET 或任何实现代码。

## Q1 实际耗时 vs appetite？超出比例？
appetite 5 days；实现尚未开始，无法填写实际实施耗时或超出比例。2026-08-24 只完成 accepted Spec/BET 自举与实施计划；此前“约 1 day 当日完成”的声明作废。自举 waiver 仅覆盖 Spec + BET，不能证明实现完成。

## Q2 done_when 是否全部通过？哪条没过，为什么？
未通过，当前为 0/11 完成验收。eCOS WorkPacket 尚无 exact `capability_requirements`；OMO 尚未持久化/回验 requirements digest 与 persisted admission；`capability-sync load/invoke` 尚未要求完整 binding；`native-execution-receipt/v1` 尚无生产消费者；Agora/Cockpit/AGE-v2 尚未统一走同一 gate；production-topology canary、child-first tags/PR/CI/merge 与最终 lifecycle receipts 均不存在。此前“全部达成、测试均 exit 0”的声明作废。

## Q3 过程中发现的与 plan 不符的事实（打假）？
- PR #2138 / commit `8ee93cd3` 在关闭 T1-11/T10-08 的混合变更中，未带 T1-12 `done_at`、实现或 completion evidence，却把 T1-12 从 `candidate` 改成 `done`；PR #2143 随后生成了本 premature retro。
- E1 (orca call chain audit): capability-sync load/invoke 不强制 binding，B4-D execution receipt 只有库与测试、没有生产消费者 → 需收敛。
- E2 (independent architecture review): "start-only 与 new broker" 两条路径均不成立，改为 start 声明预检 + dispatch 真实 identity/receipt 回验。
- E3: OMO StepDispatched 前未回验 persisted admitted state；legacy 空 capability grant 代码残留。
- E4: Cockpit KEMS 裸 dispatch 已 fail-closed 成死入口；agent-runtime/runtime registry 尚未共用 binding gate。
- E5 (periodic delta correction): #2090 合成价值链与 #2110/#2118 平行派工面不得原样合并；maturity 9.0 仅是 readiness proxy。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
当前只能确认 bootstrap/plan 文档与 ledger 元数据变化；Wave B 实现代码、GaC 规则、脚本和 child gitlink 净变化均为 0。不存在可引用的 “Exact Capability Binding 系列”跨仓实现 PR。最终净增减必须在真实实现完成后由 `bet-ledger.py surface` 重新测量。

## Q5 下一个认领本 track 的 agent 需要知道什么？
- T1-12 仍是 candidate；纠错 PR 合并后必须从最新 main 新建独立 clone，启动 fresh `bet-execution` run 并逐路径 claim。
- 实施顺序保持 eCOS → OMO consumer → root preflight/native receipt shadow → OMO integrity → Agora/Cockpit → shadow/warning/fail → production canary。
- `native-execution-receipt/v1` 当前只有库与测试，没有生产消费者；不得把 fixture、测试、PR、maturity 或 agent 自评计入个人价值。
- Golden Slice、Human Verdict、principal-bound decision_outcome、连续价值观测仍是 non-goals，留给后续 Wave C/D。
- 相关设计：docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md；wave gate map 对照 wave-gate-bet-map.md。
- 本文件不是最终复盘；最终 retro 必须在所有 done_when 直接证据齐全后由正式 workflow 写入或替换。

## 2026-08-25T10:17:29Z post-merge regression invalidation (#2185)

- Direct evidence: PR #2185 merged at `2026-08-25T08:34:58Z` after its `governance-verify` had already emitted `BET-Y1Q3-T1-12.completion_evidence: BET_DONE_REQUIRES_OUTCOME_ACCEPTED` and `BET_DONE_AT_REQUIRED`.
- Regression source: merge-resolution commit `5c9b7b85b8d8af8a353017cf67e79d7724bc57e9` retained the stale first-parent `status: done` over the then-current main `status: candidate`; later 100% rollup commits treated the bad state as baseline.
- Governed recovery: run `20260825T100848Z-bet-execution-4b4b3003` restores only this BET status to `candidate`; `completion_evidence` remains byte-semantically unchanged at `sha256:ca23452476a2d3b77c01abc80abfec79f2c2ac2b6a0ce89bd107de791678c874` and no other BET is modified.
- This recovery is not completion evidence and proves none of the 11 `done_when` items; implementation continues through the formal T1-12 WorkPacket.
