# Phase 7 starter packet spec

> Packet: `P7-W1-USER-JOURNEY-ENABLEMENT`
>
> Status: execution-ready

## Goal

Exercise the already-built tool surfaces through one coherent user journey so D2 adoption moves from "tools exist" to "tools are actually used."

## Scope

1. preload self-context for the first interaction path
2. bridge complex requests into governed task creation or task-center/task-object flow
3. mark positive confirmation as consensus evidence when appropriate
4. produce the first freshness report and connect it to D2 journey review

## Non-goals

1. implementing Wave 2 resource accounting
2. implementing Wave 3 freshness automation at full depth
3. hiding or auto-clearing `orphaned_tasks:1`

## Entry gate

1. Phase 7 planning gate ratified
2. active queue contains no second packet
3. `orphaned_tasks:1` triage path is recorded before Wave 1 closeout

## Deliverables

1. Wave 1 execution summary / closeout document
2. evidence that a real user journey traverses context, task, consensus, and freshness seams
3. updated D2 baseline judgment

## Verification

1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. targeted pytest/doc regressions for the touched surfaces
