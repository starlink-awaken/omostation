# Portfolio v2 Ledger Truth Restore

## Finding
`BET-Y1Q4-T1-03`..`T1-09` and `BET-Y1Q4-T8-05` were added in #3004 / authorized in #3007,
then wiped from first-parent main by #2993 (`94aa91fa6`, dual-node failover) which landed
a stale ledger base. Specs/plans/waiver remained on tip; only BET rows disappeared
(288 → ~280).

## Action
Restored the eight BET blocks from the portfolio-v2-governance attempt tree
(`w0-t1-04-script-registry-amendment`, T1-04 binding pinned to tip Spec 1.0.1 digest
`c8bc7fa1…` matching #3007). `meta.total_bets` left unchanged (drift repair is a
separately claimed T1-04 step).

## Next
Wave A1 T1-04: register `bin/plan/portfolio_contract.py` then re-land #3009 validator.
