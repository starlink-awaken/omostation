---
title: Historical completion receipt digest audit
date: 2026-08-29
status: verified
type: ephemeral
---

# 历史 completion receipt digest 审计

## Scope

本次审计处理 12 个非 T1-12 BET：T6-14、T10-01、T10-02、T10-03、T10-04、
T10-05、T10-06、T10-07、T10-08、T10-09、T10-10、T10-12。

## Findings and repair

- 20 个错误 receipt 都指向仍存在的根仓文件，但旧 sha256 来自主线文件
  后续变更前的快照。
- 统一重算后，将 20 个 digest 更新为当前解析文件的实际 sha256；所有
  `receipt://` 路径、轴状态、人工 attestation 和历史 BET verdict 保持不变。
- 由 digest 错误推导出的 `OVERALL_STATE_MISMATCH` 随验证恢复，不做独立状态改写。

## Verification

`python3 bin/plan/bet-ledger.py lint` 当前只报告 T1-12 的 `workflow` 与
`write_surfaces` 缺失；本报告范围内的 12 个 BET 不再产生 digest 或 overall
state 错误。

## Boundary

本次只做 ledger receipt re-attestation，不修改业务代码、运行态、宿主机、
T1-12 principal-bound evidence 或人类验收结论。
