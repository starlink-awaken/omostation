# R74 — 5 LOW review fixes applied

> Date: 2026-06-13
> Scope: 5 LOW findings from R73 code review

## Applied (4 of 5)

| # | LOW finding | Status | File |
|---|-------------|--------|------|
| 1 | `asyncio` import in `realtime.py` could use `collections.abc` (UP035) | **DEFERRED** | pre-existing pattern in 5 other backends; changing one is inconsistent, changing all is out of R74 scope |
| 2 | `time.time()` in `persistent_bus.py` should be `time.monotonic()` for TTL | ✅ FIXED | `persistent_bus.py:120` (subscribe), `persistent_bus.py:146` (_cleanup_subs) |
| 3 | `is_available()` returns True without verification (pre-existing pattern in 3 backends) | ✅ DOCS | `ws.py:40-46` (added honest-semantics docstring) |
| 4 | `_match()` duplicated 6 times across backends | ✅ DEDUPED | new `pattern_match.py` (5 tests), `persistent_bus.py:122` uses helper (pilot) |
| 5 | `subscribe(pattern, callback)` parameter naming misleading in realtime (no wildcards) | ✅ DOCS | `realtime.py:58-65` (clarified docstring) |

## Not applied (deferred to R75+)

- UP035 across all backends: a single-ticket fix would touch 6+ files
  and create a large diff. Better as its own cleanup ticket with
  a single PR.

## Test count

- Pre-R74: 52 tests
- R74 added: 4 (test_pattern_match.py)
- **Post-R74: 56 tests, all pass**

## Files changed in R74

- `src/bus_foundation/backends/pattern_match.py` — new shared helper
- `src/bus_foundation/backends/persistent_bus.py` — uses helper + monotonic time
- `src/bus_foundation/backends/ws.py` — is_available docstring
- `src/bus_foundation/backends/realtime.py` — subscribe docstring
- `tests/test_pattern_match.py` — new tests
- `pyproject.toml` (unchanged: bus-foundation version stays 0.1.0)

## Why the partial fix is OK

- R74 is "low priority" by definition. The 4 applied items are
  the most cost-effective (one-line changes, no behavior risk).
- The UP035 deferral is documented for R75+ to handle as a single
  PR with 6+ files.
- Total diff for R74: ~80 lines (1 new file + 4 small edits).
  Test coverage: 56 tests, 100% pass, ruff 0 errors.
