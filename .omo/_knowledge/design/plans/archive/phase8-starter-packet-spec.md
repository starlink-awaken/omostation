# Phase 8 starter packet spec

Packet: `P8-W1-BUDGET-FRESHNESS-CONTROL`

## Goal

Add the first runtime control gate that evaluates budget and freshness before governed work proceeds.

## Scope

1. budget limit evaluation from governed accounting truth
2. freshness severity classification from the governed freshness artifact
3. decision output: `allow`, `degrade`, `review`, or `block`
4. control decision artifact persisted under `_delivery/task-center/control/`
5. one request-routing path that consumes the decision output

## Non-goals

1. full Hermes convergence
2. KOS storage refactor
3. cross-repo governance rollout

## Entry gate

1. Phase 8 planning gate ratified
2. Phase 7 accounting and freshness artifacts available as inputs

## Deliverables

1. control-gate regression tests
2. runtime control helpers in `scripts/omo_experience.py`
3. CLI entry points for control evaluation and controlled routing
4. decision artifact and starter packet evidence

## Exit gate

1. at least one request path is governed by budget/freshness logic before execution
2. decision artifacts are written to `_delivery/task-center/control/`
3. the active queue still contains only the Wave 1 packet
