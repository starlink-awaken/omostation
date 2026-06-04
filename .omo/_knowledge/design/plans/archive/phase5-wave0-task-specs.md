# Phase 5 Wave 0 task specs

> Status: execution
>
> Scope: `G5.0` only. This packet is the first execution-grade Wave 0 source and maps directly to `.omo/tasks/{active,done}/`.

---

## Goal

Make Phase 5 executable without leaking unresolved ownership decisions into runtime implementation.

## Milestone

| Field | Value |
|------|-------|
| Milestone | `G5.0 / Wave 0` |
| User-visible outcome | Phase 5 formally starts with a real active queue, worker-backed outputs, and a validation/retrospective packet |
| Exit rule | Wave 1 may only start after landing model, secrets, Hermes, proposal, and review refresh decisions are materially documented |

## Task catalog

| Task ID | Deliverable | Suggested owner | Notes |
|--------|-------------|-----------------|-------|
| `P5-W0-LANDING-MODEL-FREEZE` | `.omo/_knowledge/design/phase5-task-center-landing-model.md` | coordinator or `codebuddy` | freezes `_truth/task-center/` vs `_delivery/task-center/` ownership |
| `P5-W0-SECRETS-OWNERSHIP-DECISION` | `.omo/_knowledge/design/phase5-secrets-ownership.md` | coordinator or `reasonix` | decides `secret_ref` storage / audit / rotation |
| `P5-W0-HERMES-COMPATIBILITY-CONTRACT` | `.omo/_knowledge/design/phase5-hermes-contract.md` | `codebuddy` | writes Hermes Direction A operating contract |
| `P5-W0-PROPOSAL-MODEL-FREEZE` | `.omo/_knowledge/design/phase5-proposal-governance-model.md` | coordinator or `codebuddy` | finalizes proposal lifecycle and approval seam |
| `P5-W0-REVIEW-REFRESH-PACKET` | `.omo/_knowledge/management/phase5-review-refresh-2026-05-31.md` | `reasonix` | marks findings as absorbed / blocking / deferred |
| `P5-W0-GOAL-TASK-SEEDING` | `goals/current.yaml`, `state/system.yaml`, kickoff retrospective | coordinator | seeds Phase 5 execution packet and closes kickoff setup |

## Gate discipline

1. Only `G5.0` is execution-ready.
2. Wave 1 remains gated even if some Wave 0 docs land early.
3. Worker tasks stay L1 and must not mutate `.omo/state/system.yaml` or `.omo/goals/current.yaml`.
4. Coordinator owns review, promotion, and global-state synchronization.

## Verification packet

1. `.omo/tests/test_phase5_wave0_docs.py`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 scripts/omo_worker.py worker status`
4. `python3 scripts/sync_omo_state.py --omo-dir .omo`
5. `python3 -m pytest .omo/tests -q`
