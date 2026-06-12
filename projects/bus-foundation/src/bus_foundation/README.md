# bus-foundation — 统一接口层 (Phase B, R66)

> Split out of `agora/bus/` in R66 as part of the Phase B bus-unification plan.
> agora-independent — no `import agora` in this package.

## 公共 API

```python
from bus_foundation import publish, subscribe, schedule
from bus_foundation.envelope import BusEnvelope, EventType

# 1. 发布事件
envelope = BusEnvelope(
    type=EventType.PIPELINE_COMPLETED,
    source="my_service",
    payload={"task_id": "t-123", "result": "ok"},
)
publish(envelope)  # → 走 router → 选 backend → 失败入 DLQ

# 2. 订阅事件
@subscribe(pattern="pipeline:*")
def on_pipeline_event(envelope: BusEnvelope) -> None:
    print(f"received {envelope.type}: {envelope.payload}")

# 3. 调度任务
@schedule(expr="every 5m")
def heartbeat() -> None:
    print("alive")
```

## backend 选型表 (0.1.0)

| 场景 | backend | 状态 | File |
|------|---------|------|------|
| 进程内 pub/sub (default) | `eventbus` | 0.1.0 | `backends/eventbus.py` |
| asyncio await 消费者 | `asyncio` | 0.1.0 | `backends/asyncio.py` |
| 定时任务 (cron) | `croniter` | 0.1.0 | `backends/croniter.py` |
| Agent 通信 (req/resp) | `messagebus` | 0.1.0 | `backends/messagebus.py` |
| SSE 风格 fan-out | `sse` | 0.1.0 | `backends/sse.py` |

> **agora 专属后端**: 持久化 `EventBusBackend`(包装 `agora.core.event_bus` +
> `agora-events.json`)、以及全局 `sse_manager` 后端**继续保留**在 `agora.bus.backends`。
> 消费者如需 agora 增强特性,直接 `from agora.bus.backends import ...`。

## 红线
- 单文件 < 500 行
- backend 自身不重试 (透传, 详见 `RETRY-OWNERSHIP.md`)
- 改 producer import 不改 API 调用方式

## 公共 API 冻结
0.1.0 末冻结 6 个月, 任何破坏性变更必须走 ADR。
