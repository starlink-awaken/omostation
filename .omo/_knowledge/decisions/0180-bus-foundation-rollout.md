# ADR-0180 — bus-foundation 全面落地 (P7x-bus-foundation-rollout)

**Date**: 2026-07-09
**Round**: R-Integration (R80+)
**Status**: ACCEPTED
**Supersedes**: partial coverage of bus-foundation in R0–R97

## Context

Prior to this ADR, bus-foundation was a 0.3.0-quality library with 320+ tests
and 9 working backends, but its integration into the omostation consumer
projects was a **"declaration without execution"** pattern (P71 class A):

| Project | Declared bus-foundation? | Had production call sites? |
|---------|-------------------------|----------------------------|
| agora | ✅ | ✅ (22 files, R0–R97) |
| omo | ✅ | ❌ (only `bus_demo_omo_producer.py` demo file) |
| metaos | ✅ | ❌ (`metaos_bus_adapter.py` was a dead adapter) |
| kairon-pipeline | ✅ | ❌ (`bus_adapter.py` had no call sites) |
| aetherforge | ✅ | partial (`_compat.py` only, hatcher used old `EventBus`) |
| runtime | ✅ | ❌ (legacy SSE consumer, not the bus) |
| cockpit | ✅ | ✅ (5 sites in `api_omos.py`) |
| l4-kernel | ✅ | ✅ (1 site in `signals.py`) |

Round 0-4 of this rollout closed the gap end-to-end.

## Decision

### 1. Entry-point contract

bus-foundation 3-plane facade is the **only** recommended entry point for new code:

- `bus_foundation.facade.event.publish / subscribe` — pub/sub, fan-out
- `bus_foundation.facade.control.submit_task / schedule_callback / ack / nack` — ack/nack/DLQ
- `bus_foundation.facade.data.emit / outbox_emit` — high-throughput, fire-and-forget

The top-level `bus_foundation.publish / subscribe / schedule` are now
marked `.. deprecated::` and slated for removal in 1.0.0. The pre-existing
`agora.bus` shim remains for back-compat (R69).

### 2. Topic SSOT

All canonical topic strings live in `bus_foundation.topics` (R0):

- `PIPELINE_COMPLETED`, `DEBT_CREATED`, `SWARM_WORKER_HATCHED`, `METAOS_NODE_*`, etc.
- Wildcard patterns use `:*` (e.g. `PATTERN_PIPELINE_ALL = "pipeline:*"`)
  because the bus pattern matcher is **string-prefix**, not glob.

Test coverage: `tests/test_topics.py` enforces the lowercase-colon
hierarchy and uniqueness.

### 3. Per-round integration work

| Round | Project | Change | Verification |
|-------|---------|--------|--------------|
| 0 | bus-foundation | 6 internal bugs fixed, topics.py SSOT added, ws_v2.py lazy imports | 340 tests pass |
| 1 | omo | `omo_daemon.run_once` now publishes `omo:audit:{completed,failed}` | `test_omo_daemon_publish_e2e.py` (3 tests) |
| 2 | metaos | `workflow._publish_event / _publish_human_approval_event` prefer bus-foundation with HTTP fallback behind `METAOS_LEGACY_AGORA_HTTP=1` | `test_workflow_bus_publish_e2e.py` (5 tests) |
| 2 | kairon-pipeline | `do_default` and `downstream_trigger` emit 4 bus topics on each action | `tests/test_bus_adapter.py` (6 tests) |
| 3 | aetherforge | `_events._emit_hatcher_event` now delegates to `_compat._bus_publish` (single bus path). Fixed pre-existing `EventType.INFO` AttributeError in `_compat.py` | `test_hatcher_events_bus_e2e.py` (4 tests) |
| 4 | runtime | `cron_service.scheduler._bus_emit_cron_fired` after every job run | `test_cron_bus_emit_e2e.py` (4 tests) |
| 4 | cockpit | was already wired (5 publish sites in `api_omos.py`); verified via dormant-adapter detector | n/a (no code change) |

### 4. Cross-project e2e

`bus-foundation/tests/test_e2e_cross_project.py` (7 tests) covers the
omo↔agora, kairon↔omo, metaos↔cockpit, aetherforge↔omo, runtime↔cockpit
flows in-process through the Router + DLQ. All 7 pass.

### 5. P74 governance gate

`bin/bus-usage-report.py` scans every consumer's `src/` and counts
production call sites on the bus-foundation facade. Exit code 0 iff
every declared consumer has at least one call site. Current state:

```
[ACTIVE] agora      1+ call site(s)
[ACTIVE] cockpit    5 call site(s)
[ACTIVE] l4-kernel  1 call site(s)
[ACTIVE] metaos    15 call site(s)
[ACTIVE] omo        4 call site(s)
[ACTIVE] runtime    3 call site(s)
[ACTIVE] aetherforge 3 call site(s)
[ACTIVE] kairon     1 call site(s)  (in kairon-pipeline sub-package)
```

This is the operational guard against the P71 class-A trap re-emerging.

The gate is wired into `gac-local-gate.py` as `bus-usage-report` (non-strict,
~2.5s on real workspace). A second gate, `bin/bus-e2e-harness.py`, runs
real cross-process ZMQ e2e (ci_only=True) and is also registered.

## Consequences

### Positive

- **All 8 consumers are now active** on the bus-foundation backbone.
- **3-plane facade** + **topics.py SSOT** eliminate the "string typo"
  and "wrong entry point" classes of bugs.
- **Lazy optional-dep imports** (zmq/redis/ws) make `import bus_foundation`
  safe in any environment.
- **Dormant-adapter detector** turns the P71 trap into a hard gate
  (exit code 1) that future PRs can break.

### Negative / Caveats

- **5 cross-project flows verified only in-process**. Real
  cross-process (Redis/ZMQ/WS) verification is `bin/bus-e2e-harness.py`
  (Round 5 follow-up, requires `pip install bus-foundation[zmq]`).
- **l4-kernel has only 1 call site** (`signals.py`) — minimum
  threshold met but thin. l4-kernel's bus usage is mostly passive
  (subscribing) which is harder to grep.
- **aetherforge hatcher events now go through bus-foundation but
  omo's `omo_mesh_event_handler.py` was already subscribing to
  `swarm:worker:*` not `swarm:hatcher:*`** — the omo-side pattern
  needs alignment if we want omo to react to hatcher lifecycle.

## Implementation Notes

- **Lazy zmq import**: `zmq.py` uses `_require_zmq()` so `import bus_foundation`
  works without `pyzmq` installed. Same pattern in `backends/__init__.py`
  for `redis`/`ws`/`zmq` via PEP 562 module-level `__getattr__`.
- **HTTP fallback in metaos** is gated by `METAOS_LEGACY_AGORA_HTTP=1`
  so operators can roll back without code change.

## Tests / Verification

- bus-foundation: 340 unit tests + 7 cross-project e2e + 7 topics tests + 8 harness = 362
- omo: 750 (including 3 new e2e)
- metaos: 235 (including 5 new e2e)
- kairon-pipeline: 46 (6 bus_adapter)
- aetherforge: 18 swarm e2e (4 new + 14 existing)
- runtime: 4 new e2e
- cockpit: pre-existing (5 publish sites in api_omos.py)
- bin/tests/test_bus-usage-report.py: 6/6 pass
- bin/tests/test_bus-e2e-harness.py: 4/4 pass

## Open Questions / Future work

1. Migrate `runtime_bus_adapter` from deprecated `@bus_foundation.schedule`
   to `@bus_foundation.facade.control.schedule_callback`.
2. omo `omo_mesh_event_handler.py` should subscribe to `swarm:hatcher:*`
   in addition to `swarm:worker:*` to react to hatcher lifecycle.
3. l4-kernel: surface more bus events (currently 1 publish in `signals.py`).
4. Promote bus-usage-report coverage to a CI badge / dashboard.
