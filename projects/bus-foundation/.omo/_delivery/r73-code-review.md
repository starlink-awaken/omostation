# R73 Code Review — 3 new backends

> Date: 2026-06-13
> Reviewer: 老王
> Files: `backends/ws.py` (95 LOC), `backends/realtime.py` (75 LOC),
>         `backends/persistent_bus.py` (182 LOC)

## WebSocketBackend (`ws.py`)

### Strengths

- **Clean pattern-match reuse** (ws.py:89-94): `_match()` is identical
  to asyncio / croniter / sse patterns. Consistent with existing backends.
- **Queue-full handling is graceful** (ws.py:51-53): `Queue.put_nowait`
  catches QueueFull and logs a warning with client_id + event_id. This
  is the right policy for pubsub (drop on overload, log loudly, don't
  crash the publisher).
- **Drain task is bounded** (ws.py:77-83): `_drain()` properly wraps
  callback in try/except so a single subscriber error doesn't kill
  the loop. Continues serving other subscribers.

### Issues

- **[MEDIUM] `_drain` task leak on unsubscribe** (ws.py:77-83)
  - When `unsubscribe()` is called, the `_drain()` task continues to
    run, blocked on `queue.get()`. Eventually queue stays empty and
    the task is stuck forever (no `asyncio.CancelledError` propagation).
  - Memory leak proportional to number of unsubscribe calls.
  - Fix: store task reference in `self._clients[client_id]` tuple;
    `unsubscribe()` calls `task.cancel()`.

- **[LOW] `is_available()` is dishonest** (ws.py:40-45)
  - Returns True even when no event loop is running, with a comment
    saying "usable but subscribers must use create_task". If the caller
    doesn't know to use create_task, the subscribe silently fails.
  - This matches asyncio.py:31-34 — same pattern, so it's
    consistency over correctness. But it should be documented in the
    `name` docstring at the top of the class.
  - Fix: docstring note. Or: have subscribe() return a warning
    when called without a running loop (already done, but the
    return value is the sub_id, not a warning).

- **[LOW] `connect()` is public but should be `subscribe()`-internal**
  (ws.py:56-61)
  - The Protocol contract is `subscribe()`. Exposing `connect()` as
    public adds a second API that callers might use instead. This
    fragments the Protocol.
  - This is also a recurrent issue across other backends (croniter
    exposes `add_cron_job`, messagebus is internal-only). Not a
    regression, but a pattern.
  - Fix: rename to `_connect` (private) or document the public surface
    explicitly.

## RealtimeBackend (`realtime.py`)

### Strengths

- **Version increment is monotonic and thread-safe** (realtime.py:47-50)
  - Under lock, increments _versions, captures version, then
    snapshots subscribers OUTSIDE the lock. This avoids holding the
    lock during callback execution (which would block new subscribers
    during slow callbacks).
- **Snapshot of subscribers under lock is the right pattern**
  (realtime.py:50)
  - `subs = list(self._subscribers.get(task_id, []))` — no iterator
    aliasing, no deadlock risk.
- **`defaultdict(int)` for version counter** (realtime.py:37) is the
  right choice for first-publish-is-version-1 semantics.

### Issues

- **[HIGH] `unsubscribe()` is broken** (realtime.py:65-69)
  - Returns `False` always. The comment says "caller should know"
    but the Protocol requires unsubscribe to be truthful. A caller
    that does `if backend.unsubscribe(sub_id): ...` will always hit
    the failure branch.
  - Fix: maintain a `sub_id -> task_id` reverse index. On
    subscribe, do `self._sub_to_task[sub_id] = pattern`. On
    unsubscribe, do `self._subscribers[pattern].remove(callback)`
    and `del self._sub_to_task[sub_id]`.
  - **This is the only HIGH issue in the 3 new backends.**

- **[MEDIUM] Subscribe by `pattern` is misleading** (realtime.py:58-63)
  - The signature says `subscribe(pattern, callback)` but in realtime,
    pattern IS the task_id (no wildcards). The `_match()` function
    from other backends is NOT used here. This is an API contract
    break.
  - Other backends: `pattern` is matched against event_type with
    wildcards. Here: `pattern` is the key into a dict. Different
    semantics.
  - Fix: rename the parameter to `task_id` in this class. Or: have
    a generic `subscribe(event_type_pattern, callback)` signature
    that filters by `_versions[task_id]` bumping, even if the pattern
    doesn't match. The latter is the right call.

- **[LOW] `defaultdict(int)` for `_subscribers`** (realtime.py:38)
  - Creates a key for every subscribed task_id, even when unsubscribed
    and forgotten. Memory leak.
  - Fix: use a regular dict + explicit add/remove.

- **[LOW] `get_version` returns 0 for unseen task_id** (realtime.py:71-73)
  - This is actually the right default (defaultdict(int) does the
    same), but a caller might confuse "0 means unseen" with "0 means
    version 0". Document explicitly.

## PersistentBusBackend (`persistent_bus.py`)

### Strengths

- **WAL mode + busy_timeout=5000** (persistent_bus.py:71-72)
  - Reuses the proven pragmas from `dlq.py` and `cron_service/db.py`.
  - This is the correct pattern: don't reinvent.
- **GC runs on every publish, not in a separate thread** (persistent_bus.py:97-103)
  - Simple, no race conditions. The check is fast (count + 1
    SELECT + DELETE), so it's fine to do inline.
- **`OR REPLACE` on insert is correct** (persistent_bus.py:113)
  - Replaces on conflict — so duplicate event_ids are idempotent
    (good for retries).
- **`_cleanup_subs` lazy on every publish** (persistent_bus.py:148-152)
  - Per-publish cleanup keeps the subscriber dict small without
    needing a separate reaper thread.

### Issues

- **[MEDIUM] No `__init__.py` update for the 3 new backends**
  (check `src/bus_foundation/backends/__init__.py`)
  - The new backends exist but are not exported from the package
    `__init__.py`. Consumers can't `from bus_foundation.backends
    import WebSocketBackend` without explicit path.
  - This is also true for the existing 5 backends (they don't
    re-export from `__init__.py` either), so it's a pattern, not
    a regression. But it's worth fixing in a follow-up.
  - Fix: in `backends/__init__.py`, add imports for the 3 new
    backends so they're discoverable.

- **[LOW] `time.time()` is used in a `threading.Lock` block**
  (persistent_bus.py:144-147)
  - Not a real issue (no deadlock, monotonic enough for TTL), but
  - `time.monotonic()` is the right call for TTL deltas. Cosmetic.
  - Fix: replace `time.time()` with `time.monotonic()` in the
    subscriber TTL check.

- **[LOW] Subscriber callbacks are NOT re-entrant safe**
  (persistent_bus.py:127-132)
  - If a callback calls `publish()` (which re-enters the publish
    path), the lock is held during the snapshot but the loop
    iterates outside. So re-entrant publish works (it takes the
    lock again — Python's `threading.Lock` is not re-entrant but
    this code releases before iterating).
  - Actually it's fine. But documenting it would be nice.

## Cross-cutting summary

### Top 3 things to fix (in priority order)

1. **[HIGH] RealtimeBackend.unsubscribe is broken** — always returns
   False. Maintain `sub_id -> task_id` reverse index.
2. **[MEDIUM] WebSocketBackend._drain task leak on unsubscribe** —
   call `task.cancel()` from `disconnect()`. Memory leak under
   long-running + high-churn patterns.
3. **[MEDIUM] `__init__.py` doesn't export the 3 new backends** —
   add explicit imports so consumers can `from bus_foundation.
   backends import WebSocketBackend`.

### Things that are genuinely good (no fix needed)

- Pattern-match logic is identical across all 3 (and matches the
  existing 5 backends). Consistency is the right call here.
- Threading is correct: lock-then-snapshot-then-iterate is the
  canonical pattern. RealtimeBackend does this right.
- SQLite pragmas (WAL + busy_timeout) are reused correctly.
  PersistentBusBackend didn't reinvent.
- Queue-full handling in WebSocketBackend is graceful (drop + log).
- All 3 backends respect RETRY-OWNERSHIP: no internal retry.
  The router catches and writes to DLQ.
- All 3 backends correctly raise NotImplementedError where the
  Protocol expects a "not supported" (PersistentBusBackend doesn't
  have one — but it implements everything, so OK).

### Things that are stylistic / consistent-with-existing-bugs

- `is_available()` returning True without verification is a pattern
  across asyncio / ws / croniter. Consistent, but technically
  dishonest. The README says "return True if reachable and
  writable" — none of them verify. This is a pre-existing gap
  that the 3 new backends correctly inherit.
- `unsubscribe()` "returns False" in RealtimeBackend is a worse
  version of the same issue that already exists in eventbus /
  asyncio backends. Inconsistency in a bad way.
- `_match()` is duplicated 5 times now (eventbus, asyncio,
  croniter, messagebus, sse, ws, persistent — that's 7). Should
  be on the BusBackend base class. But that's a pre-existing
  design issue, not a regression in the 3 new backends.

## Verdict

**All 3 backends are production-acceptable** with the fix for
RealtimeBackend.unsubscribe being the only blocker for "ship
without a follow-up ticket." WebSocketBackend._drain and the
`__init__.py` exports are follow-up tickets, not blockers.

**Tests are good**: 13 cases total (4 + 4 + 5), all TDD-style,
all passing. Tests don't cover the unsubscribe task-leak case
(neither in the existing tests nor in the proposed fix), so a
follow-up test would be needed alongside the fix.
