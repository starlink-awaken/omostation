---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-05 Coverage Graph and Critical Path Implementation Plan

**Goal:** Derive deterministic coverage and critical-path reports from Ledger
truth without creating a graph store or changing any BET.

**Files:**

- Create: `bin/plan/portfolio_graph.py`
- Modify: `bin/plan/bet-ledger.py`
- Create: `tests/test_bet_portfolio_graph.py`

**Authorization gate:** do not create or edit these files until a distinct
T1-05 implementation authorization is recorded.

### Task 1: RED fixtures for graph invariants

- [ ] Add fixtures for missing dependency, cycle, uncovered required KR,
  failed leaf without replacement, valid replacement, duplicate coverage
  without an explicit redundancy rationale, and parent ownership.
- [ ] Assert typed errors `DEPENDENCY_REF_MISSING`, `DEPENDENCY_CYCLE`, and
  `REQUIRED_KR_UNCOVERED`; assert duplicate coverage without rationale fails
  typed, assert an intentional duplicate carrying a non-empty rationale passes,
  and assert `parent_bet` never changes topological order.
- [ ] Run RED exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_graph.py -q
```

Expected: failures for the missing graph module and the typed invariants.

### Task 2: Implement pure graph construction

- [ ] Implement `build_graph(ledger)` returning immutable nodes plus exactly
  `depends_on` and `covers` edge collections.
- [ ] Implement `validate_coverage(graph)` and
  `critical_path(graph, now)` with stable sorting by depth, target window, ID.
- [ ] Define the report schema exactly as:

```python
{
    "ready_bets": [str],
    "blocked_descendant_count": int,
    "unresolved_kr_coverage": [str],
    "writer_lane_conflicts": [dict],
    "evidence": [{"id": str, "age_seconds": int | None, "status": "fresh" | "stale" | "unavailable"}],
}
```
- [ ] Do not use done-count percentages, auto-create replacements, or write
  back graph results.

### Task 3: Expose deterministic read-only CLI

- [ ] Add `bet-ledger.py portfolio coverage --json` and `critical-path --json`
  branches that serialize canonical sorted JSON.
- [ ] Add positive and negative assertions for every report field, including a
  stale/unavailable evidence fixture and a writer-lane collision fixture.
- [ ] Run GREEN exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_graph.py -q
uv run --with pyyaml python bin/plan/bet-ledger.py portfolio coverage --json
uv run --with pyyaml python bin/plan/bet-ledger.py portfolio critical-path --json
uv run --with pyyaml python bin/plan/bet-ledger.py lint
```

Expected: all tests pass; repeated JSON bytes match; no `progress` field.

### Rollback

Delete only the new graph query/CLI/test path. Ledger source data and existing
dependencies remain untouched.
