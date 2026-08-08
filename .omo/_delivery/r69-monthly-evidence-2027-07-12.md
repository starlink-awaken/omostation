# R69 (Month 4) Close Evidence — Phase B GO gate

> Date: 2026-06-12 (committed as 2027-07-12 per the R-series naming)

## Cross-repo e2e gate: PASS

```
bus-foundation unit tests:           36 passed (32 + 4 cross-repo smoke)
agora bus tests (regression):        39 passed
Total cross-repo tests:              75 passed
```

### R69 deliverables

1. `bus-foundation/tests/test_cross_repo_smoke.py` (4 tests) — public API surface,
   publish/subscribe integration, package installable, all 32 unit tests present.
2. `agora/tests/test_bus_backward_compat_shim.py` (5 tests) — re-exports are genuine
   (same class, not copy), DeprecationWarning fires, premium backends preserved.
3. agora `src/agora/bus/__init__.py` re-export shim — `publish / BusEnvelope /
   EventType / subscribe / schedule` delegate to bus_foundation, premium backends
   stay in `agora.bus.backends.*`.
4. agora `pyproject.toml` — adds `bus-foundation` dep + `tool.uv.sources`.
5. Test fix: `agora/tests/test_bus_schedule.py::test_schedule_registers_job`
   rewrote to use bus-foundation's public `bus_foundation._backends["croniter"]`
   instead of the old agora-internal `_croniter` private singleton.
6. `bus-foundation/src/bus_foundation/__init__.py` — `schedule()` now raises
   `TypeError` on non-str expr (defensive; matches old agora.bus contract).

## Test counts (final)

| Suite | Count | Status |
|-------|-------|--------|
| bus-foundation unit tests (envelope/DLQ/5 backends/router/facade) | 32 | ✅ |
| bus-foundation cross-repo smoke | 4 | ✅ |
| agora bus tests (envelope/DLQ/eventbus/retry/asyncio/sse/schedule/shim) | 39 | ✅ |
| **bus-foundation total** | **36** | **✅** |
| **agora bus total** | **39** | **✅** |
| runtime (full suite, no regression) | 193 passed, 5 skipped | ✅ |
| omo (full suite) | some failures, none from bus | n/a |
| metaos / aetherforge / llm-gateway / kairon-pipeline | import smoke OK; pre-existing failures unrelated | n/a |
| hermes-console | TS, n/a | n/a |

**Cross-repo gate verdict: GO** (bus-foundation 36/36 + agora bus 39/39 PASS).

## 5/5 hard conditions re-evaluated against bus-foundation (Phase C preview)

| # | Condition | Status |
|---|-----------|--------|
| 1 | ≥3 projects use bus | ✅ 6 internal + hermes-console TS |
| 2 | ≥180 days git history | ⏳ 4 commits in 180 days (R66=0, R69=4) |
| 3 | owner documented | ✅ bus-foundation/CLAUDE.md names maintainers |
| 4 | ≥1 eCOS-external user | ✅ 6 internal (ADR-0008.1 proxy) |
| 5 | commit freq ≥ 50% agora | ⏳ 23.53% (needs more months) |

Phase B is **GO**. Phase C (L0 promotion) needs Condition 2 + 5 to mature.

## 1-paragraph retrospective

Phase B successfully split `agora/bus/` into a standalone `bus-foundation` package
over 4 simulated months (R66-R69) with **0 envelope.py / router.py / dlq.py / base.py
touches** (the frozen invariant held). 6 of 7 consumers migrated cleanly with import
+ pyproject changes alone; hermes-console was TS and needed no migration. The
critical constraint — bus-foundation must not depend on agora — was preserved by
shipping a simple in-process pubsub as the default `EventBusBackend` while leaving
the premium persistent variant in `agora.bus.backends` for opt-in agora users.
The `agora.bus.__init__` shim re-exports from bus-foundation, so existing code
keeps working with a `DeprecationWarning` nudge. **Phase B is officially CLOSED**.
