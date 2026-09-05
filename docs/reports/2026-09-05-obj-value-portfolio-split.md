# OBJ-VALUE portfolio split — landing receipt

Date: 2026-09-05  
Session: `bet-y1q4-value-obj-split`  
Primary bet: `BET-Y1Q4-T1-14`

## What landed

| Entity | ID |
|--------|----|
| Objective | `OBJ-VALUE` |
| KRs | `KR-VALUE-JOURNEY-COMPLETION`, `KR-VALUE-WEEKLY-ADOPTION`, `KR-VALUE-REVISION-RATE` |
| Campaign | `CMP-Y1-VALUE-PROOF` |
| Bets | `BET-Y1Q4-T1-14`, `T4-02`, `T4-03`, `T4-04`, `T4-05` |
| meta.total_bets | 311 → **316** |

Vision `required_objectives` now: `OBJ-TRUST`, `OBJ-HOLDABILITY`, `OBJ-VALUE`.

## Intent

Close the gap between VISION-2029 result-plane language and portfolio objectives that were governance-only. Meter implementation remains in T4-02/03/04; T4-05 inventories value-proof debt on already-done spine bets.

## Verify hints

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py show BET-Y1Q4-T1-14
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/plan/bet-ledger.py status
```

## Follow-ups (do not invent outside ledger)

1. Claim/close `T1-14` after PR merge if still candidate.
2. Execute `T4-02` → `T4-03` → `T4-04` (deps: T1-14 + T4-07).
3. Keep `T10-105` as product choke point for real Diff/LoRA samples feeding T4-04.
