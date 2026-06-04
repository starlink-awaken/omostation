# Phase 8 program plan

> Status: active
>
> Theme: convert visibility into controlled operations

## Objective

Phase 8 upgrades the runtime from “can observe accounting and freshness” to “can decide what is allowed to execute before work starts.”

## Wave structure

### G8.1 / Wave 1 — budget and freshness control plane

Goal: turn existing cost and freshness artifacts into a governed pre-execution decision path.

Scope:

1. budget threshold evaluation
2. freshness severity classification
3. allow / degrade / review / block decision surface
4. at least one governed request-routing path

Packet:

- `P8-W1-BUDGET-FRESHNESS-CONTROL`

### G8.2 / Wave 2 — Hermes and storage convergence

Goal: close the highest-value runtime trust seams that remain after the new control path exists.

Scope:

1. Hermes 179-chain impact closure
2. scheduler/bridge convergence
3. KOS storage abstraction seam

### G8.3 / Wave 3 — cross-repo governance and blocked-surface ratification

Goal: propagate the control posture outside the local repo.

Scope:

1. cross-repo AGENTS/governance sync
2. blocked connector re-ratification
3. shared control/freshness/accounting language

## Sequencing rule

1. ratification seeds **Wave 1 only**
2. Wave 2 stays gated until Wave 1 closeout records a GO
3. Wave 3 stays gated until Wave 2 closeout records a GO
4. active queue never contains more than one execution-ready packet

## Success metrics

1. one governed journey is actually gated before execution
2. budget overrun can trigger a non-allow outcome
3. stale freshness can trigger a non-allow or degraded outcome
4. deeper debt remains explicit and scheduled instead of silently skipped

## Verification baseline

1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`
