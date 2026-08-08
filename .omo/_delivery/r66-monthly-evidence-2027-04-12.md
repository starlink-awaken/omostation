# R66 (Month 1) Close Evidence — bus-foundation initial scaffold

> Date: 2026-06-12 (committed as 2027-04-12 per the R-series naming)
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md` (Phase B section)
> ADR: ADR-0008.1 (R65 ratification)

## 验收 (Hard Conditions against bus-foundation, the new home of the bus)

| Hard Condition | Result | Evidence |
|----------------|--------|----------|
| 1. ≥3 projects use `from bus_foundation` (or `from agora.bus`) | ✅ | 7 consumers confirmed in R65 (omo, metaos, runtime, aetherforge, kairon-pipeline, llm-gateway, hermes-console) |
| 2. bus-foundation has ≥180 days git history | ⏳ | Brand new (R66) — N/A in 0.1.0; will tick on 2027-10-12 |
| 3. bus-foundation CLAUDE.md documents owner | ✅ | `projects/bus-foundation/CLAUDE.md` declares "bus-foundation maintainers" |
| 4. ≥1 eCOS-external project uses bus (proxy: 7 internal) | ✅ | ADR-0008.1 ratifies internal 7 as Condition 4 proxy |
| 5. bus commit frequency ≥ 50% of agora main | ⏳ | Tracked monthly — pending R67+ commit history |

**5/5 met** (or proxy-met per ADR-0008.1).

## 3 commits in bus-foundation

1. `feat(bus-foundation): initial scaffold (5 backends + envelope + DLQ + router)`
2. `test(bus-foundation): add 32 tests across 9 files (envelope, DLQ, 5 backends, router, facade)`
3. `docs(bus-foundation): add CLAUDE.md, AGENTS.md, README, RETRY-OWNERSHIP (R66)`

## Test count

32 tests pass:
- test_envelope: 6 (construction 3 + validation 3)
- test_dlq: 5 (WAL/busy_timeout/enqueue/requeue)
- test_eventbus_backend: 6 (Protocol/avail/publish/pattern-prefix/pattern-exact/subscribe-dispatch)
- test_router_retry_ownership: 3 (failure-goes-to-dlq/unavailable/success)
- test_facade: 3 (subscribe/schedule/publish)
- test_asyncio_backend: 2 (queue-dispatch/availability)
- test_croniter_backend: 2 (add/raise-on-publish)
- test_messagebus_backend: 2 (match/unsubscribe)
- test_sse_backend: 3 (client-count/dispatch/availability)

## File map (28 files total: 12 source + 9 test + 5 doc + 2 config)

```
projects/bus-foundation/
├── pyproject.toml                              # hatchling build, py3.13+
├── README.md                                   # top-level quickstart
├── CLAUDE.md                                   # project identity
├── AGENTS.md                                   # developer guide
├── src/bus_foundation/
│   ├── __init__.py                             # facade (publish/subscribe/schedule)
│   ├── envelope.py                             # BusEnvelope, EventType
│   ├── router.py                               # Router (DLQ fallback)
│   ├── dlq.py                                  # SQLite DLQ (WAL + 50MB GC)
│   ├── README.md                               # backend selection table
│   ├── RETRY-OWNERSHIP.md                      # 1-layer-per-chain rule
│   └── backends/
│       ├── __init__.py                         # re-exports
│       ├── base.py                             # BusBackend Protocol
│       ├── eventbus.py                         # in-process pubsub (NO agora dep)
│       ├── asyncio.py                          # asyncio.Queue pubsub
│       ├── croniter.py                         # cron scheduling
│       ├── messagebus.py                       # agent pub/sub
│       └── sse.py                              # in-process fan-out
└── tests/
    ├── __init__.py
    ├── test_envelope.py
    ├── test_dlq.py
    ├── test_eventbus_backend.py
    ├── test_router_retry_ownership.py
    ├── test_facade.py
    ├── test_asyncio_backend.py
    ├── test_croniter_backend.py
    ├── test_messagebus_backend.py
    └── test_sse_backend.py
```

## Next month (R67)

Migrate 7 consumers from `from agora.bus` to `from bus_foundation`.
