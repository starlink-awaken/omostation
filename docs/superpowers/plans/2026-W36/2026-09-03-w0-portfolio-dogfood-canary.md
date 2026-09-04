---
lifecycle: entry
owner: governance-team
last_updated: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-09 Portfolio Dogfood Canary Implementation Plan

**Goal:** Prove one value-exempt mechanism BET traverses the complete Portfolio
chain at an immutable tree and that every required corruption fails closed.

**Files:**

- Create: `tests/test_bet_portfolio_canary.py`
- Create: `docs/reports/2026-09-03-w0-portfolio-v2-dogfood-canary.md`
- Modify later under separate completion authority only:
  `docs/plans/3y-bet-ledger.yaml` and W0 retros

**Authorization gate:** implementation/canary execution requires a distinct
T1-09 authorization. This plan does not authorize a production run or any
completion transition.

### Task 1: Build isolated positive fixture

- [ ] T1-09 selects one already accepted, value-exempt W0 child mechanism BET
  only after that child has its own implementation authorization and real
  workflow receipt. Execute the selected child workflow in an independent
  canary clone at an immutable commit. Do not create a production BET, accepted
  binding, or Ledger object. Fixture helpers may corrupt copies for negative
  cases but cannot replace the real workflow start/verify/closeout chain.
- [ ] Assert the positive chain produces one immutable source digest and
  `value_indicator_policy=false`, `value=NOT_PROVEN` throughout.
- [ ] Run RED exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_canary.py -q
```

### Task 2: Build the complete negative matrix

- [ ] Parameterize mutations removing Objective/KR binding, coverage, Spec
  digest, WorkPacket identity, run binding, verification evidence, completion
  derivation, retro, projection digest, and human Vision verdict.
- [ ] Assert each mutation returns its typed failure and none changes the
  original fixture bytes.

### Task 3: Closeout prerequisites

- [ ] Compare CLI and Cockpit projection digests at the same immutable tree.
- [ ] Assert parent close is rejected while any child/Milestone is incomplete.
- [ ] Run GREEN exactly after the child workflow receipt exists:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_canary.py -q
uv run --with pyyaml python bin/plan/bet-ledger.py lint
```

Expected: one real immutable workflow chain passes; every listed negative case
fails typed; value stays `NOT_PROVEN`.
- [ ] Publish the report with exact tree, real workflow receipt, test matrix,
  required PR checks and
  clone receipts; it is engineering evidence, never personal value proof.

### Rollback

Remove only canary fixtures/report. Do not delete durable governance evidence,
alter W1-W6, or promote any value indicator.
