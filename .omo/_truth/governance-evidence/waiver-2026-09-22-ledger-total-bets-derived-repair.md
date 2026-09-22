---
schema_version: governance-waiver/v1
created: '2026-09-22'
bet_id: unbound
run_id: 20260922T040308Z-project-doc-change-0fac185b
scope: governance-data-single-field-repair
---

# ledger meta.total_bets 派生修复 unbound-start waiver

`bin/plan/portfolio_contract.py` 将 full-Ledger strict mode 有意推迟到
"separately authorized `meta.total_bets` repair"（compat 模式下
`META_TOTAL_BETS_DRIFT` 仅 typed warning: declared=439 actual=443）。
该修复不对应任何台账 BET，故按仓内先例（#4176 draft-spec bootstrap）
使用一次性 `AGCP_REQUIREMENT_ITERATION_GATE=0` 前缀完成 unbound
workflow start `20260922T040308Z-project-doc-change-0fac185b`。

Write surface 严格限定为两个路径：

- `docs/plans/3y-bet-ledger.yaml` — 仅 `meta.total_bets` 一个字段
  439 → 443（= len(bets) 派生值；分支点实测 442，PR 推进期间 main 新增
  BET-Y2Q2-T10-155，rebase 后按最新 immutable tree 重新派生为 443；
  yaml.safe_load 复验；无其他键改动）
- `.omo/_truth/governance-evidence/waiver-2026-09-22-ledger-total-bets-derived-repair.md`（本文件）

本 waiver 不授权：ledger 任何其他键的修改、strict mode 启用、
W0 self-binding、runtime mutation、Claims Authority 激活、branch
protection 修改、value evidence。Claim、verify、compliance、Git、CI
与 closeout 全部走默认门禁。

验证：`bet-ledger.py lint` exit 0；portfolio lint strict 下
`META_TOTAL_BETS_DRIFT` 消失；`gac-local-gate --scope run` ok=True。
