---
schema: retro/v1
bet_id: BET-Y1Q4-T6-23
title: "Resident Daemon & CellPool Integration — Retrospective"
date: 2026-09-11
status: draft
---

# BET-Y1Q4-T6-23 Retrospective

## 1. What Went Well

- CellPool (`cell_pool.py`) already had a complete implementation with auto-scaling, episode dispatch, and fault transfer — integration was primarily a routing problem.
- The existing `CellCoordinator` interface (`start_episode`, `handoff`, `complete`, `fail`) was clean and easy to integrate with.
- All 11 new tests pass; all 22 existing AGE-v2 tests remain green.

## 2. What Could Be Improved

- The `execute.py` cellpool backend currently uses `asyncio.run()` which creates a new event loop per call. For high-frequency dispatch, a shared event loop would be more efficient.
- The `_cell_run` method currently simulates execution (records to context). Production integration with pi-worker-adapter or multica backend is deferred.

## 3. Root Cause Analysis (5-Why)

**Why was CellPool not integrated with execute.py before?**
→ Because execute.py only supported pi and multica backends; the cellpool routing path didn't exist.

**Why did it take a BET to wire them?**
→ Because CellPool was built as a standalone module without a clear consumer; the integration point was not prioritized.

## 4. Lessons Learned

- When building standalone modules (like CellPool), define the integration contract (interface + routing) at design time, not after.
- The `backend` dispatch pattern in `_execute()` is extensible — adding a new backend is a 5-line change.

## 5. Action Items

- [ ] Production integration: wire `_cell_run` to actual pi-worker-adapter or multica dispatch
- [ ] Shared event loop: refactor `asyncio.run()` to use a persistent loop for high-frequency dispatch
- [ ] Metrics: emit CellPool utilization metrics to the daemon's monitoring pipeline
