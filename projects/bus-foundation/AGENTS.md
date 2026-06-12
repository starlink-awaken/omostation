# AGENTS.md — bus-foundation developer guide

## Quickstart

```bash
uv sync
uv run pytest -q  # 32 tests
```

## Key files

| File | LOC | Purpose |
|------|-----|---------|
| `src/bus_foundation/__init__.py` | ~90 | facade — publish/subscribe/schedule |
| `src/bus_foundation/envelope.py` | ~95 | BusEnvelope wire format |
| `src/bus_foundation/router.py` | ~55 | backend dispatch + DLQ fallback |
| `src/bus_foundation/dlq.py` | ~135 | SQLite DLQ (WAL + GC) |
| `src/bus_foundation/backends/eventbus.py` | ~80 | in-process pubsub (no agora dep) |
| `src/bus_foundation/backends/asyncio.py` | ~90 | asyncio.Queue pubsub |
| `src/bus_foundation/backends/croniter.py` | ~125 | cron scheduling |
| `src/bus_foundation/backends/messagebus.py` | ~50 | agent pub/sub |
| `src/bus_foundation/backends/sse.py` | ~85 | in-process fan-out |

## Gotchas

- **RETRY**: bus adapter 自身不重试 (透传), 详见 `src/bus_foundation/RETRY-OWNERSHIP.md`
- **DLQ**: 落 `~/.runtime/bus_dlq.db`, 50MB 滚动
- **Zero agora dependency**: `grep -r "from agora" src/bus_foundation/` must return 0
- **Pattern syntax**: `*` (all), `foo:*` (prefix), `foo:bar` (exact) — no regex
- **No premium backend in core**: persistent `EventBusBackend` (writes to
  `agora-events.json`) lives in `agora.bus.backends`, NOT here

## Adding a new backend

1. Create `src/bus_foundation/backends/mybackend.py` implementing the
   `BusBackend` Protocol (4 methods: `name`, `is_available`, `publish`,
   `subscribe`, `unsubscribe`).
2. Register in `src/bus_foundation/backends/__init__.py`.
3. Optionally register in `src/bus_foundation/__init__.py` `_backends` dict
   if you want it dispatchable by name via `envelope.backend`.
4. Add tests in `tests/test_mybackend.py` (5+ cases: protocol, is_available,
   publish, subscribe dispatch, unsubscribe).
5. Update `src/bus_foundation/README.md` backend selection table.

## Release

0.1.0 freeze 6 months. Bump version in `pyproject.toml`. Any breaking
change requires an ADR (see agora/docs/ADR-0008-bus-foundation-strategy.md).
