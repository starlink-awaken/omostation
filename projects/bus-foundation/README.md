# bus-foundation

> Standalone Python package providing the unified bus interface for omostation.
> Split from `agora/bus/` in Phase B (R66) per ADR-0008.1.

## Why this package exists

Inside `agora`, the bus lived at `agora/bus/`. As 7 projects adopted it
(`omo`, `metaos`, `runtime`, `aetherforge`, `kairon-pipeline`, `llm-gateway`,
`hermes-console`), the dependency on agora for a generic bus primitive
became a tax. Phase B moves the bus into its own package so projects can
`pip install bus-foundation` without pulling in agora's I0 service mesh.

## Install

```bash
uv add bus-foundation
# or
pip install bus-foundation
```

## Public API

```python
from bus_foundation import publish, subscribe, schedule
from bus_foundation.envelope import BusEnvelope, EventType

env = BusEnvelope(
    type=EventType.PIPELINE_COMPLETED,
    source="my_service",
    payload={"task_id": "t-123"},
)
publish(env)

@subscribe("pipeline:*")
def on_pipeline_event(envelope: BusEnvelope) -> None:
    print(f"received {envelope.type}")

@schedule("every 5m")
def heartbeat() -> None:
    pass
```

## What's in 0.1.0

- `BusEnvelope` wire format (id, time, type, source, schema_version, trace_id, payload)
- `publish()` / `subscribe()` / `schedule()` facade
- 5 backends: `eventbus` (in-process pubsub), `asyncio`, `croniter`, `messagebus`, `sse`
- `DLQ` (SQLite WAL + 50MB GC) for failed-event capture
- 28 tests

## License

Apache-2.0
