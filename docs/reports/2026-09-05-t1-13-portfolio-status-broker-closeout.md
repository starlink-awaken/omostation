# BET-Y1Q4-T1-13 closeout receipt

## Delivered

- Brokered mutation-surface for `.omo/_control/portfolio-status.json`
  (`portfolio-projection-control` → `bin/plan/portfolio_projection.py:apply_omo_via_broker`)
- CLI: `python3 bin/plan/portfolio_projection.py --check-broker`
- Spec: `docs/superpowers/specs/2026-09-05-portfolio-status-broker-ownership-design.md`
- Retro: `.omo/_knowledge/retros/BET-Y1Q4-T1-13.md`
- Affected-graph: `docs/reports/2026-09-05-t1-13-affected-graph.json`

## Verify

```text
$ python3 bin/plan/portfolio_projection.py --check-broker
broker_ok

$ PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml --with pytest \
    python -m pytest tests/test_bet_portfolio_projection.py -q
........                                                                 [100%]
8 passed in 0.10s

$ python3 bin/plan/portfolio_projection.py --apply-omo; echo exit:$?
PORTFOLIO_BROKER_APPLY_NOT_WIRED: ownership present but apply adapter not authorized in T1-08
exit:1
```

## Boundaries kept

- No Ledger reverse write
- No W0 Markdown rewrite
- Apply adapter intentionally unwired (circuit breaker)

## Run

`20260905T004704Z-governance-state-mutation-5b5f3bdf`
