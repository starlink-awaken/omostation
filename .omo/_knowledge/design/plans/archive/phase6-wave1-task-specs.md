# Phase 6 Wave 1 task specs

> Status: execution
>
> Scope: `G6.1` only. This packet is the first Phase 6 execution-grade source and maps directly to `.omo/tasks/{active,done}/`.

---

## Goal

Seed exactly one execution-ready packet for the durable + governance runtime core, and keep all later Phase 6 work gated.

## Milestone

| Field | Value |
|------|-------|
| Milestone | `G6.1 / Wave 1` |
| User-visible outcome | Phase 6 starts with one governed runtime-core packet, not a multi-wave active queue |
| Exit rule | `G6.2` may only start after a Wave 1 closeout with explicit GO |

## Task catalog

| Task ID | Deliverable | Suggested owner | Notes |
|--------|-------------|-----------------|-------|
| `P6-G1-DURABLE-GOVERNANCE-CORE` | `scripts/omo_worker.py`, `scripts/sync_omo_state.py`, runtime/governance closeout artifacts | coordinator | single seeded packet owning the full Wave 1 runtime-core implementation |

## Gate discipline

1. Only `P6-G1-DURABLE-GOVERNANCE-CORE` may exist in `.omo/tasks/active/` at Phase 6 start.
2. `G6.2` and `G6.3` remain gated in planning docs only.
3. Coordinator owns `goals/current.yaml` and `state/system.yaml` updates; worker implementation stays inside the packet boundary.

## Verification packet

1. `.omo/tests/test_phase6_ratification_docs.py`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`
4. `python3 -m pytest .omo/tests -q`
5. `python3 scripts/omo_worker.py worker status`

