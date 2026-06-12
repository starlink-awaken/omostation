# Changelog

All notable changes to bus-foundation are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-12 (R66-R69)

### Added
- **BusEnvelope** wire format (`id`, `time`, `type`, `source`, `schema_version`,
  `trace_id`, `payload`).
- **Public API facade**: `publish(env)`, `subscribe(pattern)`,
  `schedule(expr)` decorators, plus `BusEnvelope` and `EventType`.
- **5 backends**:
  - `eventbus` — in-process pubsub (NO agora dependency; premium persistent
    variant stays in `agora.bus.backends`)
  - `asyncio` — in-process pubsub via `asyncio.Queue`
  - `croniter` — cron-style scheduling
  - `messagebus` — agent pub/sub with pattern dispatch
  - `sse` — in-process fan-out (HTTP layer wires its own SSE)
- **DLQ** (SQLite, WAL + 50MB rolling GC) — `~/.runtime/bus_dlq.db`
- **Router** — single backend dispatch with DLQ fallback (no retry, per
  `RETRY-OWNERSHIP.md`)
- **32 tests** across 9 test files (envelope, DLQ, 5 backends, router, facade)
- **Zero external dependencies** beyond `pydantic` (and stdlib)

### Notes
- 6/7 consumers migrated from `agora.bus` to `bus_foundation` in R67
  (omo, metaos, runtime, aetherforge, llm-gateway, kairon-pipeline).
  hermes-console is TypeScript and uses the JSON SSE wire format, no migration needed.
- Public API is **frozen for 6 months** from 0.1.0 release. Any breaking change
  requires an ADR.

[0.1.0]: #0.1.0
