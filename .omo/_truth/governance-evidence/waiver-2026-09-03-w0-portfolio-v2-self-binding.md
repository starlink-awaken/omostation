---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-04
last-reviewed: 2026-09-04
value_indicator_policy: false
title: W0 Portfolio/BET v2 self-binding amendment evidence
type: doc
---

# W0 Portfolio/BET v2 Self-Binding Amendment

## Principal authorization (session)

> 更稳一点吧，继续

Interpreted as continuing the safer Portfolio Wave order:

1. finish T1-04 self-binding amendment;
2. then T1-07;
3. then T1-06.

Earlier same-session principal authorization already released Wave A1 gates and
authorized sequential Portfolio Wave advance after T1-04/T1-05 delivery.

## Scope (exact)

1. `docs/plans/3y-bet-ledger.yaml`
   - add top-level `vision` / `objectives` / `campaigns` / `milestones`
     (W0 vocabulary only: `OBJ-TRUST`, `OBJ-HOLDABILITY`,
     `KR-TRUST-CHAIN-COVERAGE`, `KR-HOLDABILITY-ORPHAN-BETS`,
     `CMP-W0-PORTFOLIO-TRUTH`, four `MS-W0-*`);
   - set `meta.schema_version: bet-portfolio/v2`;
   - for the eight W0 BETs only: replace
     `portfolio_binding.schema_state: bootstrap_unenforced` with `enforced`
     and add approved `milestone_refs`;
   - update parent T1-03 `note` to record enforcement activation.
2. this waiver evidence file.

## Hard non-goals (unchanged)

- No status / depends_on / human_gate / accepted_specifications changes
  (except the T1-03 note text above).
- No completion_evidence / value_evidence / overall_state changes.
- No W1–W6 BETs, no implementation code beyond prior Wave A1 validators,
  no projections, no Cockpit product delivery, no canary execution.

## Verification required before merge

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python bin/plan/bet-ledger.py portfolio lint --strict
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml --with pytest python -m pytest tests/test_bet_portfolio_contract.py tests/test_bet_portfolio_graph.py -q
python3 - <<'PY'
# protected-field equality for non-W0 BETs + W0 status/deps/bindings axes
PY
```

## Workflow binding

- bet: `BET-Y1Q4-T1-03`
- run: `20260904T103842Z-governance-state-mutation-c5c0053c`
- worktree: `ws-bet-y1q4-t1-03-self-binding`
- claimed paths: ledger + this waiver

## Residual

Enforcement activates Portfolio v2 reference checks for BETs that already carry
`portfolio_binding`. Legacy BETs without `portfolio_binding` remain
grandfathered. Child implementation (T1-07/T1-06/…) still requires its own
fresh workflow, claims, and human_gate where still true.
