---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# Governance Meta-Roadmap (ADR-0384)

> Published with ADR-0384. Strategy: from "more mechanisms" to "meta-meta governance" — measure and govern the governance system itself.

## Why this roadmap

10 convergence rounds shipped a fully covered plane: 136 rules, 98 surfaces, 41/41 gate, healthcheck green, all 10 initiatives closed. Strategic analysis identified three frictions:

1. **Manual rebase cycle** eats 30-60% of round time
2. **Mechanism count is growing** but no signal on which gates actually catch problems
3. **Healthcheck is over-instrumented** for the steady state

This roadmap publishes the multi-milestone plan for the next phase of governance work.

## Milestones

| M | Round | Scope | Status |
|---|-------|-------|--------|
| **M1** | ADR-0384 | A1 `make rebase-regen` automation, A3 doc-ssot cleanup, B1 `bin/_archive/2026-08-conv3/gate-effectiveness.py` meta-meta tool | ✅ shipped |
| **M2** | 0385+ | A2 cron pruner; B2 SSOT healthcheck auto-report | planned |
| **M3** | later | C1 drift history → concurrent hot-spot prediction (use 10 rounds of drift data) | planned |
| **M4** | later | C2 convergence proposal generator (semi-automated ADR draft from drift patterns) | planned |
| **M5** | later | C3 governance value report (quarterly executive summary: caught N problems, saved M hours) | planned |

## Direction (B-series / C-series)

### Phase A — friction automation (M1-M2)

- **A1 `make rebase-regen`** (M1): 7-step idempotent pipeline (M1 sync + docs + ruff + mof). 60s vs 15-30min manual.
- **A2 cron pruner** (M2): schedule `prune-ci-runs.py` weekly — prevent 40000-run cap stall recurring.

### Phase B — measure the mechanism (M1-M2)

- **B1 `gate-effectiveness.py`** (M1): empirical score from `governance-history.jsonl`. Output: ACTIVE / MODERATE / WEAK / RETIRE / NEW verdicts. Currently `agora health` and `ruff lint` are the only ACTIVE gates (94 + 91 fires / 506-508 runs).
- **B2 SSOT healthcheck** (M2): each SSOT file (ci-surfaces / governance-checks / roadmap) auto-reports last-consumed time and drift count. Detect dead SSOTs.

### Phase C — guide the next round (M3-M5)

- **C1 hot-spot prediction** (M3): 10 rounds of drift data → predict which files / agents will collide next round.
- **C2 ADR draft generator** (M4): given a drift pattern, output a draft ADR with verification plan. Human review → accept / reject / amend.
- **C3 value report** (M5): quarterly metrics: drift-fires caught, time saved, mechanisms retired. Make governance budget-discussable.

## Current state (M1 baseline)

From `gate-effectiveness.py` (M1 ship):

```
check               verdict   n     fires  rate    score  last_fired
agora health        ACTIVE    506   94     18.6%   0.64   2026-06-13
ruff lint           ACTIVE    508   91     17.9%   0.61   2026-07-31
task consistency    MODERATE  508   55     10.8%   0.33   2026-06-13
doc lifecycle       WEAK      151   13      8.6%   0.30   2026-06-23
debt integrity      WEAK      508   31      6.1%   0.19   2026-07-31
adr links           WEAK      508   27      5.3%   0.18   2026-07-27
test coverage       WEAK      508   23      4.5%   0.14   2026-07-31
```

**Interpretation**: 2/7 gates are doing real work; 5/7 are weak (still firing, but low signal). Strategic direction: B-series to prune the bottom of this list before adding new mechanisms.

## Maintenance

- Run `gate-effectiveness.py` weekly (or per round) to track gate effectiveness trend.
- Run `make rebase-regen` post-rebase as a one-shot.
- ADR-0384 marks the pivot: from "convergence" to "meta-meta convergence".
