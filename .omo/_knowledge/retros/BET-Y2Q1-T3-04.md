---
schema_version: retro/v1
bet_id: BET-Y2Q1-T3-04
run_id: 20260905T104915Z-bet-execution-70e05129
session: t304-20260905t104533z
completed: 2026-09-05T19:15:00+08:00
pr: https://github.com/starlink-awaken/omostation/pull/3211
---

# BET-Y2Q1-T3-04 Retrospective

## What was delivered

- **TreeContextIndex** (`projects/omlxc/src/omlxc/dataplane/tree_context.py`):
  - Heading-level hierarchical document parsing
  - Lightweight bag-of-words embedding (no ML dependency, deterministic)
  - Semantic query with entity-overlap boosting
  - Contradiction detection (entity-overlap + low cosine similarity = conflict signal)
  - Full unit test suite (22 tests)

- **PagedKVCache** (added to `projects/omlxc/src/omlxc/dataplane/paged_kv.py`):
  - Fixed-memory-budget LRU cache (default 16GB)
  - Priority-aware eviction (lower priority evicted first)
  - 4KB block alignment for allocation efficiency
  - Full unit test suite (19 tests)

## Verification

- `uv run pytest projects/omlxc/tests/unit/test_tree_context.py` — 22/22 GREEN
- `uv run pytest projects/omlxc/tests/unit/test_paged_kv_cache.py` — 19/19 GREEN
- `uv run pytest projects/omlxc/tests/unit/` — 946 passed, 0 failed
- `make gac-local-gate` — PASS (57 checks, ALL GREEN)
- PR: https://github.com/starlink-awaken/omostation/pull/3211

## Lessons learned

1. **4KB block alignment needs test budget headroom** — tests using tiny budgets (4KB) failed because each entry aligned to a full 4KB block. Use `PagedKVCache.BLOCK_SIZE` multiplier for test budgets.
2. **PASW subtree vs submodule divergence** — when modifying code in `.subtrees/omlxc`, the main worktree's `projects/omlxc` submodule is a separate git repo. Must `git fetch` + `git checkout <merge-commit>` in the submodule to sync.
3. **Submodule guard fast-forward** — pointer changes must be fast-forward relative to previous staged SHA. The merge commit satisfies this because it has the previous staged SHA as a parent.

## Follow-up work

- BET-Y2Q1-T6-01 (memory decay engine) is now unblocked by this delivery
- TreeContextIndex could benefit from real embedding models (e.g., sentence-transformers) for higher accuracy
- PagedKVCache could integrate with omlxc's existing VRAM budget estimator for dynamic budget sizing
