# Changelog — bus-foundation

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2027-04-12 (R66 initial release)

### Added (R66-R67: Phase B setup)

- Standalone repo split from `agora/bus/` (per ADR-0008)
- `BusEnvelope` (Pydantic-lite wire format)
- `match_pattern` shared helper (R74 dedup; extracted early)
- 5 backends (initial set, all from `agora/bus/`):
  - `EventBusBackend` — in-process pub/sub
  - `AsyncioBackend` — in-process pub/sub via `asyncio.Queue`
  - `CroniterBackend` — cron-style scheduling
  - `MessageBusBackend` — agent-to-agent pub/sub with req/resp correlation
  - `SSEBackend` — in-process fan-out for HTTP/SSE layer
- 28 tests (initial release baseline)
- Cross-repo smoke test for Phase B GO gate
- `OWNERS.md`, `GOVERNANCE.md`, monthly 5-hard-conditions check script
- Public API frozen for 6 months from 2026-06-12

### Changed (R73-R75: feature + simplify + style)

- **R73** — Added 3 new backends:
  - `WebSocketBackend` — full-duplex fanout for browser clients
  - `RealtimeBackend` — versioned per-task event stream
  - `PersistentBusBackend` — SQLite-backed durable pub/sub
- **R73** — R73 code review + 3 fixes (HIGH unsubscribe, MEDIUM drain leak, MEDIUM `__init__.py` exports)
- **R74** — 4 of 5 LOW review fixes applied:
  - `time.monotonic()` for TTL
  - `match_pattern` helper extracted; 1 backend pilot
  - 2 docstring clarifications
- **R74 simplify** — 5 backends delegate to `match_pattern` (dedup 6 copies, -15 net LOC)
- **R75** — `ruff --fix` collections.abc (UP035) + import sort (I001); 17+2 auto-fixes
- **R75** — `GOVERNANCE.md` + `CLAUDE.md` updated to reflect R73/R74/R75 state
- **R75** — Phase C decision (R72 Path C: Defer) documented in `GOVERNANCE.md`

### Verified invariants (R75)

- **Single file < 500 LOC**: max 130 (persistent bus.py)
- **Zero `from agora` imports** in `src/bus_foundation/`: 0 (cross-repo purity)
- **No retry at backend** (per RETRY-OWNERSHIP.md): 0
- **56 tests, 100% pass** (R75)
- **ruff**: 0 errors (after R75 auto-fix)

## Backlog (deferred to normal feature work)

- **R75-LOW-1**: PersistentBusBackend.publish() runs `_cleanup_subs`
  on every publish. For high-subscriber counts (>100) this is O(N)
  per event. Switch to a separate reaper thread or rate-limited cleanup.
- **R75-LOW-2**: WebSocketBackend and PersistentBusBackend publish()
  are O(N) over subscribers. For >1000 subscribers, add a trie or
  sharded dispatch table.
- **R75-ADR-0003**: Document the "no L0 promotion" decision formally
  as an ADR (so the next maintainer doesn't have to read the
  18-month history to understand why).
- **R75-rerun**: Re-verify 0 ruff warnings after the auto-fix batch.

## References

- Architecture analysis: `.omo/_delivery/async-event-cron-architecture-2026-06-12.md`
- Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md`
- ADR-0008 (Phase B trigger): `../agora/docs/ADR-0008-bus-foundation-strategy.md`
- ADR-0008.1 (Phase B Condition 4 proxy): `../agora/docs/ADR-0008.1-condition-4-amendment.md`
- 14-month retrospective: `.omo/_delivery/r72-final-retrospective-2027-09-12.md`
- R73 code review: `.omo/_delivery/r73-code-review.md`
- R74 evidence: `.omo/_delivery/r74-monthly-evidence-2026-06-13.md`
- Path C decision: `.omo/_delivery/r71-phase-c-recommendation-memo.md`
