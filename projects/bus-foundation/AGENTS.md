# AGENTS.md — bus-foundation developer guide

> R77 update. Originally written R66. Updated after R73 (3 new backends),
> R74 (LOW fixes + simplify), R75 (ruff), R76 (0.1.1 patch).

## Quickstart

```bash
uv sync
uv run pytest -q  # 59 tests (R76)
```

## Key files (R77 truth)

| File | LOC | Purpose |
|------|-----|---------|
| `src/bus_foundation/__init__.py` | ~120 | facade — publish/subscribe/schedule |
| `src/bus_foundation/envelope.py` | ~95 | BusEnvelope wire format |
| `src/bus_foundation/router.py` | ~55 | backend dispatch + DLQ fallback |
| `src/bus_foundation/dlq.py` | ~135 | SQLite DLQ (WAL + GC) |
| `src/bus_foundation/backends/base.py` | ~40 | BusBackend Protocol |
| `src/bus_foundation/backends/pattern_match.py` | ~30 | **R74 shared helper** (6 backends delegate) |
| `src/bus_foundation/backends/eventbus.py` | ~80 | in-process pubsub (no agora dep) |
| `src/bus_foundation/backends/asyncio.py` | ~90 | asyncio.Queue pubsub |
| `src/bus_foundation/backends/croniter.py` | ~125 | cron scheduling |
| `src/bus_foundation/backends/messagebus.py` | ~50 | agent pub/sub (note: B007 in R77) |
| `src/bus_foundation/backends/sse.py` | ~85 | in-process fan-out |
| `src/bus_foundation/backends/ws.py` | ~120 | **R73** full-duplex fanout |
| `src/bus_foundation/backends/realtime.py` | ~90 | **R73** versioned task events |
| `src/bus_foundation/backends/persistent_bus.py` | ~180 | **R73** SQLite durable (note: R76 rate-limit) |

## Tests (R76 = 59 cases)

| File | Tests | Coverage |
|------|-------|----------|
| `test_envelope.py` | 3 | BusEnvelope construction + validation |
| `test_dlq.py` | 5 | DLQ persistence + GC + rate-limit |
| `test_eventbus_backend.py` | 4 | in-process pubsub |
| `test_asyncio_backend.py` | 4 | asyncio.Queue pubsub |
| `test_croniter_backend.py` | (basic) | cron scheduling |
| `test_messagebus_backend.py` | (basic) | agent pub/sub |
| `test_sse_backend.py` | (basic) | in-process fan-out |
| `test_ws_backend.py` | 4 | R73 full-duplex fanout |
| `test_realtime_backend.py` | 4 | R73 versioned task events |
| `test_persistent_bus_backend.py` | 5 | R73 SQLite durable pubsub |
| `test_persistent_bus_ratelimit.py` | 3 | **R76** rate-limit cleanup |
| `test_pattern_match.py` | 4 | **R74** shared helper |
| `test_realtime_unsubscribe.py` | 3 | **R73** unsubscribe fix |
| `test_facade.py` | (basic) | publish/subscribe/schedule facade |
| `test_router_retry_ownership.py` | (basic) | Router + DLQ fallback |
| `test_cross_repo_smoke.py` | (R66) | Phase B GO gate |

## Gotchas (R77)

- **RETRY**: bus adapter 自身不重试 (透传), 详见 `RETRY-OWNERSHIP.md`
- **DLQ**: 落 `~/.runtime/bus_dlq.db`, 50MB 滚动
- **Zero agora dependency**: `grep -r "from agora" src/bus_foundation/` must return 0
- **Pattern syntax**: `*` (all), `foo:*` (prefix), `foo:bar` (exact) — no regex
- **Use `match_pattern` helper**: never re-implement `_match()` (R74 dedup)
- **Use `collections.abc`**: `from collections.abc import Callable`, not `from typing`
- **No premium backend in core**: persistent `EventBusBackend` (writes to
  `agora-events.json`) lives in `agora.bus.backends`, NOT here
- **R76 rate-limit**: `PersistentBusBackend.publish` runs cleanup every
  100 publishes, not every one. Document if you change the constant.

## Adding a new backend

1. Create `src/bus_foundation/backends/mybackend.py` implementing the
   `BusBackend` Protocol (4 methods: `name`, `is_available`, `publish`,
   `subscribe`, `unsubscribe`).
2. Register in `src/bus_foundation/backends/__init__.py`.
3. If dispatchable by name via `envelope.backend`, register in
   `src/bus_foundation/__init__.py` `_backends` dict.
4. Add tests in `tests/test_mybackend.py` (5+ cases: protocol,
   is_available, publish, subscribe dispatch, unsubscribe).
5. **Update `src/bus_foundation/README.md` backend selection table.**
6. Run `uv run pytest -q` and verify 0 regressions.

## Release

- **Current version**: 0.1.1 (R76)
- **Public API frozen** since R66 (2026-06-12). No breaking changes
  to BusEnvelope, the public functions (publish/subscribe/schedule),
  or the BusBackend Protocol.
- **Bump version** in `pyproject.toml` for any release.
- **Breaking changes** require an ADR (see `docs/ADR-0003-no-l0-promotion.md`
  for the L0 re-opening conditions, and `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`
  for context).

## When to update this file

Update AGENTS.md when:
- Adding/removing a backend
- Adding/removing a public function in `__init__.py`
- Changing the public API contract
- Bumping the version

Do NOT update AGENTS.md for:
- Internal refactors (CHANGELOG.md is enough)
- Test additions (CHANGELOG.md is enough)
- New shared helpers (CHANGELOG.md is enough)
