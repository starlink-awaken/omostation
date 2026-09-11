---
schema_version: specification/v1
spec_version: 1.0.0
title: Persistent Queue — ledger-backed durable queue for omo.sovereignty
bet_id: BET-Y1Q4-T10-147
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---

# Persistent Queue — ledger-backed durable queue

## 1. Problem

`projects/omo/src/omo/sovereignty` already has two ledger-backed, persistent
primitives that mirror the "Role/Queue/Receipt" trio named in the OMO Agent
OS goal: `roles.py` (Role, via `SovereigntyService`) and
`principal_authority.py` (`PrincipalAuthorityReceipt`). Both write exclusively
through `LedgerBroker.append` and reconstruct all state by replaying
`LedgerBroker.read()`; nothing lives only in memory.

The only `Queue`-named primitive found in this repository
(`projects/ecos/src/ecos/l1/runtime::MessageQueue`) is a plain in-process
Python list: priority-sorted, TTL-aware, but gone on process restart. There is
no persistent Queue analogous to Role/Receipt.

## 2. Goal

Add `PersistentQueue` to `omo.sovereignty`, following the exact architecture
already established by `SovereigntyService`: one write path
(`LedgerBroker.append`), full reconstruction by replay
(`LedgerBroker.read(producer=...)`), no second storage.

This spec does not touch `ecos::MessageQueue` — that stays as-is for callers
that only need an in-process, ephemeral priority queue.

## 3. Non-goals

- No external message-queue middleware (Redis, RabbitMQ, etc.) — this reuses
  the existing SQLite-backed `LedgerBroker` already vendored in this repo.
- No cross-process pub/sub or blocking consumer semantics — `dequeue()` is a
  synchronous pop; callers that need blocking/streaming build that on top.
- No migration of existing `MessageQueue` call sites in this BET; that is a
  separate follow-up once `PersistentQueue` exists and is proven.

## 4. Design

### 4.1 Event schema

Two event types, producer `omo-persistent-queue`, space `persistent-queue`:

```text
PersistentQueue.ItemEnqueued.v1
  queue_id: str        # the queue's principal_id in the envelope
  item_id: str          # "qitem:<uuid4>"
  item: JSON-serializable value (the payload the caller queued)
  priority: int          # higher dequeues first; ties broken by enqueue order
  enqueued_at: str (ISO-8601, set by the broker's occurred_at default)

PersistentQueue.ItemDequeued.v1
  queue_id: str
  item_id: str          # references the ItemEnqueued.item_id being consumed
```

`idempotency_key` for `ItemEnqueued` is the `item_id` itself (caller may
retry an enqueue call safely by reusing the same generated id — though in
practice each call mints a fresh uuid, so retries are naturally new items;
the key exists to make a literal duplicate call collide rather than double
insert). `idempotency_key` for `ItemDequeued` is `f"{item_id}|dequeue"` — an
item can only be dequeued once; a second dequeue attempt against the same
item raises `DuplicateEventError` from the broker, surfaced as
`QueueError("ITEM_ALREADY_DEQUEUED")`.

### 4.2 Replay / reconstruction

`_pending_items(queue_id)` reads every `PersistentQueue.*` row for this
producer, filters to rows whose payload `queue_id` matches, and computes:

```text
enqueued: {item_id: payload}  (insertion order preserved)
dequeued: {item_id}
pending = [ (item_id, payload) for item_id in enqueued if item_id not in dequeued ]
pending.sort(key=lambda pair: -pair[1]["priority"])   # stable: ties keep insertion order
```

This mirrors `SovereigntyService._replay`'s pattern: read once, decode
strictly, raise a typed error (`QueueReplayError`) on a malformed row instead
of silently skipping it.

### 4.3 Public API

```python
class PersistentQueue:
    def __init__(self, broker: LedgerBroker, queue_id: str): ...

    @classmethod
    def open(cls, db_path: str | Path, queue_id: str) -> PersistentQueue: ...

    def enqueue(self, item: Any, *, priority: int = 0) -> str:
        """Append an ItemEnqueued event; returns the new item_id."""

    def dequeue(self) -> tuple[str, Any] | None:
        """Pop the highest-priority pending item (FIFO within a priority).
        Returns (item_id, item) or None if the queue is empty. Appends
        exactly one ItemDequeued event on success."""

    def peek(self) -> tuple[str, Any] | None:
        """Same ordering as dequeue() but does not mutate state."""

    def pending_count(self) -> int:
        """len(pending) without materializing items."""
```

### 4.4 Durability property (the acceptance test)

Writing, killing the process (`kill -9`, no graceful shutdown), and
reopening `PersistentQueue.open(db_path, queue_id)` against the same
`db_path` must reconstruct the exact same pending set — because state is
never held anywhere except the SQLite-backed event log, which already fsyncs
per the `LedgerBroker` WAL contract. No queue-specific durability code is
needed beyond "don't cache state across calls, always compute from
`_pending_items`" — which is also why `PersistentQueue` holds no queue state
as instance attributes beyond `queue_id` and the broker handle.

## 5. Acceptance

- [ ] `enqueue`/`dequeue`/`peek`/`pending_count` implemented per §4.3.
- [ ] Priority ordering verified: three items enqueued priority 1, 5, 3 dequeue
  in order 5, 3, 1.
- [ ] FIFO tie-break verified: two items same priority dequeue in enqueue order.
- [ ] Double-dequeue of the same `item_id` raises `QueueError`.
- [ ] Malformed row (payload missing `item_id`) raises `QueueReplayError`,
  not silently skipped.
- [ ] Kill/reopen durability test: enqueue 3, dequeue 1, close broker
  (simulating a hard kill — no explicit flush call), reopen a fresh
  `PersistentQueue.open()` against the same file, confirm exactly the 2
  remaining items are pending in the correct order.
- [ ] Two independent `queue_id`s in the same DB file never leak items into
  each other's `_pending_items()`.
