---
schema_version: governance-waiver/v1
created: '2026-09-23'
bet_id: unbound
run_id: 20260923T013303Z-project-code-change-1ef17a79
scope: guard-contract-test-sync
---

# Waiver · bet-done-gate 契约测试同步（无 bet 绑定）

## 背景

#4221（f70c38030）把 `.github/workflows/bet-done-gate.yml` 的硬失败分类从
两类 finding 扩为三类（新增 `META_TOTAL_BETS_DRIFT`），但
`tests/test_spec_binding_lint.py::test_bet_done_transition_job_has_guard_contract`
仍钉住旧的两类 grep 字面量 → main 上 scheduled Governance Check 自 2026-09-22
12:17 起持续红（1 failed, 70 passed）。

## 处置

仅同步测试断言至 #4221 已落地的契约（三族 grep 字面量 + 注释），不改生产行为。

## bet 绑定说明

台账 444 条全部 done，无在途 bet 可绑定；本事务为 main CI 红的修复性
test-lane 增量（P75 triage：真 bug-预存，选择修复而非登记 known-debt）。
经用户授权链（2026-09-22 "我给你授权，推进吧" + 常驻 PR 合并授权）以
`AGCP_REQUIREMENT_ITERATION_GATE=0` 记录性豁免启动 workflow run
20260923T013303Z-project-code-change-1ef17a79。
