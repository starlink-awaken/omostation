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

| 场景 | backend | Phase |
|------|---------|-------|
| 跨进程事件 | `eventbus` | A.0 ✅ |
| 进程内 await | `asyncio` | A.1 |
| 推客户端 (单向) | `sse` | A.1 |
| 双向通信 | `ws` | A.1 |
| Task 状态同步 | `realtime` | A.1 |
| Agent 通信 (req/resp) | `messagebus` | A.1 |
| 定时任务 | `croniter` | A.1 |
| omo 旧 daemon (deprecating) | `cron_daemon` | A.1 |

## 红线
- 单文件 < 500 行
- backend 自身不重试 (透传, 详见 RETRY-OWNERSHIP.md)
- 改 producer import 不改 API 调用方式
