# Unified Bus API — Scout Report

Read-only investigation of existing infrastructure in omostation. Goal: identify what to REUSE / EXTEND / REFERENCE for the new `projects/agora/src/agora/bus/` subpackage wrapping 6 async/event/cron/pubsub mechanisms.

---

## A. Existing Unified / Abstraction Layers

Strong evidence that **someone already built exactly this kind of wrapper** — `unified_protocol_adapter.py` is the closest prior art, and `redis_message_queue.py` is a textbook "drop-in replacement" pattern.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/unified_protocol_adapter.py` (100+ lines inspected)
  - **Summary**: Wraps 4 protocols (MCP / HTTP / WebSocket / A2A) behind a single `UnifiedProtocolAdapter` class with `ProtocolType` enum, version negotiation (`ProtocolVersion` semver with `RUNTIME_COMPATIBILITY` map), middleware chain, and schema validators. Migrated from SharedBrain D_Gateway.
  - **Recommendation**: **EXTEND this** as the structural template — the new Bus API has the same shape (multiple backends, versioned protocol, schema-validated envelopes, registry of handlers). Lines 1-100 cover the pattern fully.
  - Pattern: `register_handler(protocol_type, name, fn)` → `_handlers: dict[ProtocolType, dict[str, Callable]]`

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/redis_message_queue.py` (lines 1-80)
  - **Summary**: A `RedisMessageQueue` class designed as a **drop-in replacement** for an existing SQLite queue. Checks `is_available` and lets caller fall back. Connection with 3-attempt exponential backoff retry. Has full formal Organ metadata header.
  - **Recommendation**: **REUSE this pattern verbatim** — the Bus API should expose the same `is_available` / `connect_with_backoff` interface for each backend (Redis, SQLite, asyncio.Queue, in-memory, file FIFO, cron tick). Lines 20-80 show the contract.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/realtime.py` (lines 1-80)
  - **Summary**: WebSocket-based realtime sync (T164/T165). Uses `TaskSync` class with subscribers dict + SQLite `task_events` table (event_id autoincrement, task_id, event_type, payload, **version INTEGER**) + snapshot table. Optimistic concurrency via version increments.
  - **Recommendation**: **REUSE the `version INTEGER` snapshot pattern** for event evolution. This is the codebase's existing answer to "how do we version a stream."

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/sse.py` (lines 1-80)
  - **Summary**: `SSEManager` wrapping asyncio.Queue per client, broadcast + send_event. Each `SSEClient` is `{id, queue: asyncio.Queue}`. Clean broadcaster with no external deps.
  - **Recommendation**: **REUSE as one of the 6 backends** (SSE = one of the wrapper targets). The bus can wrap an `SSEManager` and add a `BusBackend` adapter.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/core/scheduler.py` (lines 1-80)
  - **Summary**: In-memory `Scheduler` with `ScheduledTask` dataclass (id, callback, interval, cron_expr, enabled, last_run, next_run). Simple, no DB.
  - **Recommendation**: **REUSE as the in-process scheduling backend** (one of the 6 targets). Pattern: `add_task(ScheduledTask)` then `start()` / `stop()`.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/adapters/node_adapter.py` (4.1K)
  - **Summary**: External node adapter (SSRF-fixed). Demonstrates the "thin adapter for a specific protocol" idiom.
  - **Recommendation**: **REFERENCE for style** — this is how a single backend should be packaged as an adapter.

- `/Users/xiamingxing/Workspace/projects/runtime/src/runtime/executor/message_bus.py` (10.2K) and `task_scheduler.py` (5.8K)
  - **Summary**: Found in `build/lib/...` (compiled artifacts) but the same classes exist in `executor/`. Executor has its own `message_bus` and `task_scheduler` — duplicates of bus/scheduler concerns.
  - **Recommendation**: **AVOID this pattern** — the runtime/executor has its OWN message_bus that doesn't talk to agora's EventBus. The new Bus API should explicitly NOT extend this; instead, it should be the SSOT that runtime eventually migrates to.

---

## B. Existing Event Schemas & Version Handling

Event/version handling is **ad-hoc and inconsistent** across the codebase. There is no SSOT envelope schema.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/core/event_bus.py` (lines 1-279, full file read)
  - **Summary**: The canonical event envelope: `{id, time, source, type, trace_id, payload}`. Event types are string namespaces like `"index:done"`, `"pipeline:started"`, `"omo:log_sync"` — colon-separated category:verb. No version field on the envelope itself. No schema. Persistence: JSON file `agora-events.json`, FIFO ring of 1000 (keep last 500). Pattern matching: exact / prefix / catch-all.
  - **Recommendation**: **EXTEND this as the envelope contract**. Add an optional `schema_version: int = 1` field and a `BusEnvelope` Pydantic model. Lines 112-131 (`publish` method) define the wire format. Lines 104-110 (`_match`) define routing.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/audit_subscriber.py` (lines 60-138)
  - **Summary**: Defines the **event_type → actor/resource/action/risk classification** mapping (registry/route/event/pipeline/proxy/index/error/security). This is the de-facto "event type registry" — 8 namespace prefixes with risk levels.
  - **Recommendation**: **REUSE the classification map** in `projects/agora/src/agora/bus/schemas.py`. The new bus should ship with this same map so audit hook integration is trivial. Lines 109-128 are the table.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/realtime.py` `task_events` schema (lines 27-50)
  - **Summary**: Has `version INTEGER` per event row, plus a snapshot table for optimistic concurrency. This is the only place in the codebase that actually versions events.
  - **Recommendation**: **REFERENCE for the version-evolution pattern**. Don't reinvent.

- `/Users/xiamingxing/Workspace/projects/runtime/src/runtime/executor/io_schemas.py` (1.4K)
  - **Summary**: Empty/small file — runtime has IO schemas but not event schemas. Contains the function signatures for what the executor reads/writes.
  - **Recommendation**: **REFERENCE for style only** — does not currently model events.

- `/Users/xiamingxing/Workspace/projects/kairon/packages/kairon-pipeline/src/kairon/pipeline/io_schemas.py`
  - **Summary**: Pipeline IO schemas (input/output shapes for pipeline steps).
  - **Recommendation**: Not event-related; ignore for this purpose.

- **GAP IDENTIFIED**: No Pydantic event model exists. No JSON Schema for events. No version-prefix-in-event-type ("v1.index.done"). This is an **opportunity to introduce** in the new bus package.

---

## C. Existing DLQ / Retry / Persistence Patterns

Three independent DLQ implementations exist, each in a different style. They do **not** share a library — the new bus should consolidate.

- `/Users/xiamingxing/Workspace/projects/runtime/src/runtime/bus_consumer.py` (186 lines, full file read)
  - **Summary**: Polls agora's `/api/events/stream` SSE endpoint, persists every event to a local SQLite DB. DLQ table schema: `(event_id PRIMARY KEY, dispatch_id, content, retries INTEGER DEFAULT 0, status TEXT DEFAULT 'PENDING')`. States: `PENDING → ACKED` or `PENDING → DLQ` after 3 retries. Tracks `last_seen_id` in a `state` table for resume-on-crash. `dlq` rows in DLQ status are parked; only PENDING ones are retried (the `retry_dlq()` function is a stub).
  - **Recommendation**: **REUSE the DLQ table schema and state machine** as-is. Lines 44-52 (DLQ DDL), 99-124 (state transitions), 105/117 (retries >= 3 → DLQ). This is the closest thing to a working DLQ in omostation.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/audit_subscriber.py` (lines 60-89)
  - **Summary**: SQLite `audit_log` table with `INSERT OR IGNORE` for idempotency. Three indexes (timestamp, event_type, actor). WAL mode not explicit.
  - **Recommendation**: **REUSE the `INSERT OR IGNORE` idempotency pattern**. The bus should make every event write idempotent.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/redis_message_queue.py` (lines 20-80)
  - **Summary**: 3-attempt exponential backoff connection retry with `OSError, ValueError` as retryable. Uses `decode_responses=True` for clean strings.
  - **Recommendation**: **REUSE the backoff constants** (3 attempts, base 500ms, max 10s) — see `agora/retry.py` for the canonical implementation.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/retry.py` (lines 1-80)
  - **Summary**: Canonical retry module. `RetryConfig(max_retries, base_delay_ms, max_delay_ms, retryable_statuses)`, `with_retry(provider, fn, on_retry, config)` async helper. Exponential backoff with jitter (0.75-1.25).
  - **Recommendation**: **REUSE this directly** — do not write a new retry. The bus should call `with_retry(...)` for each backend publish. Default `retryable_statuses = {429, 500, 502, 503, 504}`.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/redis_message_queue.py` `is_available` pattern (lines 60-80)
  - **Summary**: Queue declares its own availability; caller falls back if `is_available == False`.
  - **Recommendation**: **REUSE as the bus-backend contract**. Each backend in the new bus should expose `is_available() -> bool` and let `Bus` try backends in order.

- `/Users/xiamingxing/Workspace/projects/runtime/src/runtime/cron_service/db.py` (lines 1-60)
  - **Summary**: SQLite with WAL mode (`PRAGMA journal_mode=WAL`), `busy_timeout=5000`, thread-local connections. Has `jobs` table with full lifecycle columns.
  - **Recommendation**: **REUSE the WAL + busy_timeout pragmas** for any SQLite-backed bus queue. Lines 22-28 are the pragma block.

- `/Users/xiamingxing/Workspace/projects/runtime/src/runtime/cron_service/scheduler.py` (lines 1-80)
  - **Summary**: croniter-based scheduler supporting standard cron, `every 5m` shorthand, and step forms. Falls through multiple parsers (`_parse_cron_expr`, `_parse_every_expr`, `_parse_step_cron_interval`).
  - **Recommendation**: **REFERENCE for cron-expression parsing**. The bus can route "cron-like" events to this scheduler as one of its 6 backends.

---

## D. Existing Test Patterns for Pubsub

The agora test suite is the canonical example. Follow its style.

- `/Users/xiamingxing/Workspace/projects/agora/tests/test_event_bus.py` (inspected 100 lines)
  - **Summary**: Pure unit tests, no network, no pytest-asyncio needed. Uses `tempfile.mkdtemp()` for isolated storage per test via `_new_bus()` helper. Class-grouped test classes: `TestEventBusPublish`, `TestEventBusSubscribe`, `TestEventBusLog`, `TestEventBusMatch`. Each test method is short and asserts on observable behavior.
  - **Recommendation**: **REFERENCE for style** — copy this class grouping + `tempfile.mkdtemp()` pattern. Lines 1-100 show the entire style.

- `/Users/xiamingxing/Workspace/projects/agora/tests/conftest.py` (inspected 50 lines)
  - **Summary**: Defines `FakeToolCatalog` mock with the same interface as the real `ToolCatalog` (get_tool, update_status, list_tools, etc.). Subprocess degradation for stdio in test mode.
  - **Recommendation**: **REUSE the FakeXxx mock pattern**. For the new bus, write `FakeRedisBackend`, `FakeSSEBackend`, etc. that match the public interface of real backends.

- `/Users/xiamingxing/Workspace/projects/agora/tests/test_pipeline_eventbus_integration.py` (file confirmed)
  - **Summary**: Integration test that exercises the EventBus end-to-end with the pipeline. (Not opened in detail; file exists at this path.)
  - **Recommendation**: **REFERENCE for the integration-test pattern** — should write an equivalent `test_bus_integration.py` that publishes through the unified API and verifies delivery via each backend.

- `/Users/xiamingxing/Workspace/projects/agora/tests/test_audit_subscriber.py` (file confirmed)
  - **Summary**: Tests the audit subscriber that hooks into the EventBus. (Not opened in detail.)
  - **Recommendation**: **REFERENCE** — a hook-based test pattern for backends that subscribe to the bus.

- `/Users/xiamingxing/Workspace/projects/agora/tests/conftest.py` also notes `@pytest.mark.network` for network tests
  - **Recommendation**: **REUSE the marker** — any test that touches real Redis/Postgres/etc. should carry `@pytest.mark.network`. Default is offline + tmpdir.

- **GAP IDENTIFIED**: No existing test exercises a backend with a real "drop-in replacement" pattern (i.e., switching backends at runtime and verifying the same behavior). The new bus needs this kind of **backend-swappability test**.

---

## E. Existing Governance / CLAUDE.md Patterns for Sub-Packages

Agora's documentation is well-structured and modular. Follow its conventions.

- `/Users/xiamingxing/Workspace/projects/agora/CLAUDE.md` (full file read)
  - **Summary**: Top-level operational guide. Section "文件职责" maps each top-level file → 职责 → 风险. Includes a "已知技术债务" section (1: server/mcp.py God Module, 2: _ok/_error duplication, 3: ecos/omo 依赖无静态 import, 4: 缺少 mypy). Has a "安全检查清单" (SSRF, hmac, env-only secrets, no eval/pickle).
  - **Recommendation**: **REUSE this exact structure** for the new bus subpackage's own CLAUDE.md. Lines 1-80 of the file show the format.

- `/Users/xiamingxing/Workspace/projects/agora/AGENTS.md` (full file read)
  - **Summary**: Developer-focused quick-start. Has a 七层内部架构 table, Key Files table (file + 行数 + 说明), Testing section, Security section, Gotchas section (5 numbered items), and BOS Services section.
  - **Recommendation**: **REUSE the table-of-files format** for the new bus AGENTS.md. Each backend adapter file should be listed with size and purpose.

- `/Users/xiamingxing/Workspace/projects/runtime/CLAUDE.md` (full file read)
  - **Summary**: Runtime's CLAUDE.md includes a **subsystem architecture ASCII diagram** (Matrix / Scheduler / KEI / Cron / Executor / MCP / Event Bus / Tools), 健康监控节奏 flow, KEI 沙箱安全模型, 快速命令 section, GPTCHAS section (7 known gotchas), and a `make test` / `make fmt` command catalog.
  - **Recommendation**: **REFERENCE the ASCII architecture diagram pattern** — the new bus should include one showing its 6 backends and their relationship.

- `/Users/xiamingxing/Workspace/projects/agora/src/agora/redis_message_queue.py` lines 1-20 (Organ metadata header)
  - **Summary**: Files in agora use a structured header with `Type: Organ / Status: Experimental / Layer: L4-Gateway / Summary / Authority`. Also a formal 数学 notation block: `内涵 ≝ {Redis, Message, Queue}`.
  - **Recommendation**: **REUSE the Organ metadata header** verbatim for each new bus backend file. This is the codebase's existing convention for "this is a registered organ."

- `/Users/xiamingxing/Workspace/projects/agora/AGENTS.md` mentions `docs/god-module-split-plan.md`
  - **Summary**: ADRs/plan docs live in `docs/` of each project.
  - **Recommendation**: **PLACE the bus design as** `projects/agora/docs/bus-unification-plan.md` (mirroring this precedent) and reference it from `agora/CLAUDE.md` and `agora/AGENTS.md`.

- **No formal `ADR-XXXX.md` files found** in agora or kairon (search returned no results in `docs/ADR*` paths). The codebase uses inline plans and CLAUDE.md instead of a numbered ADR system.
  - **Recommendation**: Do not invent an ADR system. Use the CLAUDE.md "已知技术债务" section pattern + a single design doc in `docs/`.

- **GAP IDENTIFIED**: No existing subpackage has a "this is the bus API" governance doc. The new bus will set the precedent.

---

## Summary of Reuse Plan

| Component | Source | Action |
|-----------|--------|--------|
| Registry / handler dispatch pattern | `unified_protocol_adapter.py` | **EXTEND** as structural template |
| Drop-in replacement + `is_available` | `redis_message_queue.py` | **REUSE** as backend contract |
| Event envelope (id, time, source, type, trace_id, payload) | `core/event_bus.py` | **EXTEND** with optional `schema_version` |
| Event-type classification map | `audit_subscriber.py` lines 109-128 | **REUSE** in `bus/schemas.py` |
| DLQ table schema + state machine | `runtime/bus_consumer.py` lines 44-52, 99-124 | **REUSE** as DLQ backend |
| Exponential backoff with jitter | `agora/retry.py` | **REUSE** directly via `with_retry` |
| SQLite WAL + busy_timeout pragmas | `runtime/cron_service/db.py` lines 22-28 | **REUSE** in SQLite backend |
| SSE manager | `agora/sse.py` | **REUSE** as one of 6 backends |
| In-memory scheduler | `agora/core/scheduler.py` | **REUSE** as one of 6 backends |
| Optimistic versioned events | `agora/realtime.py` | **REFERENCE** for version evolution |
| Test style (class grouping + tempfile + FakeXxx) | `agora/tests/test_event_bus.py` + `conftest.py` | **REUSE** test patterns |
| Organ metadata header | `redis_message_queue.py` lines 1-20 | **REUSE** for new files |
| CLAUDE.md structure (file table + debt section) | `agora/CLAUDE.md` | **REUSE** structure |
| AGENTS.md structure (architecture + key files) | `agora/AGENTS.md` | **REUSE** structure |
| ASCII architecture diagram | `runtime/CLAUDE.md` | **REFERENCE** for bus diagram |
| `runtime/executor/message_bus.py` | (executor-local bus) | **AVOID** extending; flag as future migration target |

## Identified Gaps to Fill

1. No Pydantic event envelope model — bus should introduce one
2. No `schema_version` field on events — bus should add it (default 1)
3. No central DLQ library — bus should consolidate the 3 existing DLQ patterns
4. No backend-swappability test — bus needs one
5. No `docs/bus-unification-plan.md` design doc yet — create it

## Recommendation on Subpackage Structure

```
projects/agora/src/agora/bus/
├── __init__.py            # Bus facade, re-exports
├── envelope.py            # BusEnvelope (Pydantic) — extends EventBus dict
├── schemas.py             # EventType enum + classification map (from audit_subscriber)
├── backends/
│   ├── base.py            # BusBackend Protocol (is_available, publish, subscribe)
│   ├── sse.py             # wraps agora.sse.SSEManager
│   ├── scheduler.py       # wraps agora.core.scheduler.Scheduler
│   ├── realtime.py        # wraps agora.realtime.TaskSync
│   ├── sqlite_dlq.py      # new SQLite DLQ (DLQ schema from bus_consumer.py)
│   ├── redis.py           # wraps agora.redis_message_queue.RedisMessageQueue
│   └── cron.py            # wraps runtime.cron_service.scheduler
├── router.py              # routes envelope to one-or-more backends by event_type
├── retry.py               # re-export agora.retry.with_retry
└── facade.py              # Bus.publish(envelope) — single entry point
```
