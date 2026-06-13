# Architecture — bus-foundation

> R77 model. Documents what the code is, why it is shaped this way,
> and what the explicit non-goals are.

## Mission

bus-foundation is the **shared event/transport layer** for omostation.
It exposes a single public API (`publish`, `subscribe`, `schedule`,
`BusEnvelope`, `EventType`) and dispatches to one of **8 backends**
selected by consumer choice.

## C4 Model (Level 1-2)

```
┌────────────────────────────────────────────────────────────────────┐
│  omostation monorepo (10 sub-projects, 7 of which use bus)        │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  bus-foundation (this repo)                                  │ │
│  │                                                              │ │
│  │  ┌─────────────┐  ┌──────────┐  ┌───────────────────────────┐ │ │
│  │  │   facade    │→ │  router  │→ │ 8 backends (5 + 3 R73)   │ │ │
│  │  │ publish     │  │ backend  │  │ eventbus / asyncio /     │ │ │
│  │  │ subscribe   │  │ dispatch │  │ croniter / messagebus /│ │ │
│  │  │ schedule    │  │ + DLQ    │  │ sse / ws / realtime /   │ │ │
│  │  │             │  │ fallback │  │ persistent_bus          │ │ │
│  │  └─────────────┘  └──────────┘  └───────────────────────────┘ │ │
│  │           │                       │                           │ │
│  │           └───── BusEnvelope ──── (envelope.py, 75 LOC)     │ │
│  │                                                              │ │
│  │  Optional: cross-process pub/sub via the SQLite file itself   │ │
│  │  (other processes poll get_recent())                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  agora.bus (now backward-compat shim)                         │ │
│  │  re-exports bus_foundation for the 7 consumers that          │ │
│  │  already used `from agora.bus import ...`. The premium         │ │
│  │  backends (persistent EventBusBackend + global sse_manager)    │ │
│  │  STAY in agora, not in bus-foundation.                        │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Component model

### facade (src/bus_foundation/__init__.py, 120 LOC)

Public API entry point. Three functions:

- `publish(envelope: BusEnvelope) -> str`
- `subscribe(pattern: str) -> Callable` (decorator)
- `schedule(expr: str) -> Callable` (decorator; routes to croniter)

Plus `BusEnvelope` and `EventType` re-exports.

**No state** beyond the default Router and the per-backend singletons
in `_backends`.

### Router (src/bus_foundation/router.py, 55 LOC)

Dispatches to one backend by `envelope.backend` (default: `eventbus`).
On failure, writes to DLQ and returns the envelope id (does not
raise). **The router is the single point of retry ownership** — no
backend retries internally; the router + DLQ are the only failure
path.

### Envelope (src/bus_foundation/envelope.py, 75 LOC)

The wire format. Fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | str | auto-generated | `evt_<epoch>_<6 hex>` |
| `time` | str | auto-generated | ISO 8601 UTC, `Z` suffix |
| `type` | str | yes | `category:verb` (e.g. `pipeline:completed`) |
| `source` | str | yes | emitting component |
| `schema_version` | int | default 1 | bump on breaking wire change |
| `trace_id` | str? | optional | distributed trace correlation |
| `payload` | dict | default {} | caller-defined, JSON-serializable |

Plus `EventType` enum (3 canonical types; custom types are allowed
as plain strings).

### DLQ (src/bus_foundation/dlq.py, 135 LOC)

SQLite dead-letter queue. WAL mode + busy_timeout=5000. 50MB rolling
GC. Schema:

```sql
CREATE TABLE dlq (
    event_id TEXT PRIMARY KEY,
    backend TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    error TEXT,
    retries INTEGER DEFAULT 0,
    status TEXT DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

States: `PENDING` → (requeue) → `PENDING with retries++` → (retries
≥ 3) → `DLQ` (parked).

### pattern_match helper (src/bus_foundation/backends/pattern_match.py, 30 LOC)

**R74 dedup.** Single source of truth for pattern matching. All 6
pattern-using backends delegate to `match_pattern(pattern, event_type)`.

Pattern syntax:
- `"*"` — catch-all
- `"foo:*"` — prefix
- `"foo:bar"` — exact

NOT supported: regex, multi-wildcard (`foo:*:bar`).

### 8 Backends

| Backend | LOC | Pattern | Process boundary | Persistence | Use case |
|---------|-----|---------|------------------|-------------|----------|
| `eventbus` | 80 | yes | in-process | none | default; tests; simple cases |
| `asyncio` | 90 | yes | in-process | none | async/await consumers |
| `croniter` | 125 | N/A (scheduling) | in-process | none | scheduled jobs |
| `messagebus` | 50 | yes | in-process | none | agent-to-agent req/resp |
| `sse` | 85 | yes | in-process | none | HTTP/SSE layer bridge |
| `ws` (R73) | 120 | yes | in-process (stub for real ws) | none | browser clients (real transport deferred) |
| `realtime` (R73) | 90 | N/A (task_id as key) | in-process | none | versioned task events |
| `persistent_bus` (R73) | 180 | yes | cross-process via SQLite | yes | durable pub/sub; low-throughput |

All backends implement the `BusBackend` Protocol (4 methods:
`is_available`, `publish`, `subscribe`, `unsubscribe`).

## Design decisions (with rationale)

### D1. One repo, 8 backends, single facade

**Why**: 7 eCOS-internal projects all need pub/sub/cron-style
operations. The variance between "I want fire-and-forget" and
"I want durable" is a backend choice, not a package choice. One
repo with a small dispatch surface is simpler than N packages.

**Alternatives considered**:
- N separate packages (one per backend) — abandoned R70: too
  much coordination cost for 7 projects
- 2 packages (core + extensions) — abandoned R70: extra import
  boilerplate with no real win

### D2. Zero `from agora` imports

**Why**: bus-foundation must be consumable by projects that don't
use agora (e.g., a future external user). agora.bus stays as a
backward-compat shim that re-exports bus_foundation.

**Enforcement**: CI grep (`grep -r "from agora" src/bus_foundation/`
must return 0).

### D3. Public API frozen for 6 months (R66 + R72)

**Why**: 7 eCOS-internal consumers need API stability to integrate.
L0 promotion is a one-way ratchet (ADR-0003) so the public API
freezes 6 months by default, then re-evaluates.

**Frozen since 2026-06-12**. Expires 2026-12-12. (No new breaking
changes planned before then.)

### D4. No retry at backend (RETRY-OWNERSHIP.md)

**Why**: If multiple layers retry, a single failure causes 9 attempts
(3 × 3 × 1). One layer retries, others pass through. The bus
adapter is **not** the retry layer — the router is.

**Enforcement**: Code review rejects `for attempt in range(3)` in
backends. `with_retry` is only called in router (or not at all —
router is the single decision point).

### D5. SQLite over Redis/Kafka for cross-process pubsub

**Why**: zero external dependencies. bus-foundation must be
installable in any Python project with a single `pip install`.
Redis would add an external dep; Kafka would add an operation
burden. SQLite gives us durable, cross-process, zero-dep pubsub
for the low-throughput use cases (audit logs, task notifications).

**Acknowledged limitation**: not for high-throughput production
pub/sub. Documented in `PersistentBusBackend` docstring.

## Anti-patterns (explicit "don't do this")

### A1. Don't add `from agora` imports to bus-foundation

Why: breaks D2. CI grep catches this.

### A2. Don't add retry loops inside backends

Why: violates D4. Code review catches this. The router + DLQ are
the only failure-handling path.

### A3. Don't introduce new dependencies

Why: violates the "zero external deps" principle. If you need a
new dep, file an ADR explaining why bus-foundation must grow.

### A4. Don't add L0-style commitment claims to docstrings

Why: per ADR-0003, L0 promotion is declined. Any "this is a
protocol" framing would contradict that decision. Document at
the level "this is a library" — not higher.

### A5. Don't break pattern_match signature without an ADR

Why: 6 backends + 4 test files depend on it. Changing the signature
is a cross-cutting breaking change.

### A6. Don't pre-emptively add a backend for a hypothetical consumer

Why: each backend is ~80-180 LOC of code + tests. Premature
backends are over-engineering. R75-R76 backlog shows the right
order: backlog ticket first, then build.

## Anti-patterns that are documented but **not yet implemented**

These are aspirational TODOs that are **explicitly out of scope**
for 0.1.x:

- **Trie-based dispatch** (R75-LOW-2 deferred): would enable
  O(1) publish with N>100 subscribers. Current state: O(N)
  scan is fine for typical N<100.
- **Real `websockets` transport** (ws.py docstring): currently the
  in-process queue + hook shim. Real ws transport would need
  `websockets` dep + a real socket loop.
- **Pydantic for Envelope**: currently a simple class. Pydantic
  would give validation but adds 1MB to the dep tree.

## Cross-repo consistency

bus-foundation is one of three "shared" packages in omostation:

| Package | Layer | Repo | Maintainer |
|---------|-------|------|------------|
| bus-foundation | L0 (proto candidate, declined) | `projects/bus-foundation/` | 夏 |
| aetherforge-gateway | L0 | `projects/aetherforge/packages/gateway/` | aetherforge team |
| kos (knowledge ontology) | L1 | `projects/kairon/packages/kos/` | kairon team |

bus-foundation interacts with `agora.bus` (backward-compat shim)
and `metaos` (workflow emits bus events). Neither `agora.bus` nor
`metaos` are required to import bus-foundation directly; they can
go through `agora.bus` if they need the shim.

## Where the bus-foundation decisions live

| Decision | Where documented | Owner |
|----------|------------------|-------|
| API frozen 6 months | `CLAUDE.md` | R66 implicit |
| Zero `from agora` | `CLAUDE.md`, this file | R66 |
| No L0 promotion | `docs/ADR-0003-no-l0-promotion.md` | R76 |
| Phase B trigger | `../agora/docs/ADR-0008-bus-foundation-strategy.md` | R57 |
| Phase B Condition 4 proxy | `../agora/docs/ADR-0008.1-condition-4-amendment.md` | R65 |
| Phase C trigger reality | `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md` | R70 |
| Rate-limit cleanup | `src/bus_foundation/backends/persistent bus.py` docstring | R76 |
| Pattern match | `src/bus_foundation/backends/pattern_match.py` docstring | R74 |

## References

- `CLAUDE.md` — owner-facing quickstart
- `AGENTS.md` — developer-facing quickstart (file list, test list, gotchas)
- `GOVERNANCE.md` — process and decision log
- `CHANGELOG.md` — version history
- `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`
- `docs/ADR-0003-no-l0-promotion.md`
- `.omo/_delivery/r72-final-retrospective-2027-09-12.md` (14-month retrospective)
- `.omo/_delivery/r75-final-close-2026-06-13.md` (19-month retrospective)
