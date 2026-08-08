# agora.bus — 统一接口层 (Phase A.0)

## 公共 API

```python
from agora.bus import publish, subscribe, schedule
from agora.bus.envelope import BusEnvelope, EventType

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


# 3. 调度任务 (Phase A.1)
@schedule(expr="every 5m")
def heartbeat() -> None:
    print("alive")
```

## backend 选型表

> R62 status: 5 backends actually exist on disk (asyncio / croniter / eventbus /
> messagebus / sse). The ws / realtime / cron_daemon entries below are
> **planned** backends; they are tracked here for visibility but have not
> landed. Do not mark a project as using one of these without a corresponding
> file in `bus/backends/`.

| 场景 | backend | Status | File |
|------|---------|--------|------|
| 跨进程事件 (default) | `eventbus` | A.0 ✅ | `backends/eventbus.py` |
| 进程内 await | `asyncio` | A.1 ✅ | `backends/asyncio.py` |
| 推客户端 (SSE 单向) | `sse` | R60 ✅ | `backends/sse.py` |
| Agent 通信 (req/resp) | `messagebus` | A.1 ✅ | `backends/messagebus.py` |
| 定时任务 | `croniter` | A.1 ✅ | `backends/croniter.py` |
| WebSocket 双向 | `ws` | planned | — |
| Task 状态同步 | `realtime` | planned | — |
| omo 旧 daemon 兼容 | `cron_daemon` | planned | — |

## 红线
- 单文件 < 500 行
- backend 自身不重试 (透传, 详见 RETRY-OWNERSHIP.md)
- 改 producer import 不改 API 调用方式
