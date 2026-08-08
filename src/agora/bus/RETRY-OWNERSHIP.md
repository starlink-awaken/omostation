# Retry Ownership Rule (R57+)

## 核心规则
**每条事件链路只有 1 层做重试, 其他层透传。**

## 链路分层 (从 producer 到 consumer)

| 层 | 组件 | 是否重试 | 重试参数 |
|----|------|---------|---------|
| L1 | producer 代码 | ❌ | - |
| L2 | `agora.bus.publish` | ❌ (透传) | - |
| L3 | `agora.bus.backends.eventbus` (HTTP callback) | ❌ (透传) | - |
| L4 | **agora EventBus 自身** | ✅ | 3x, 2^attempt (event_bus.py:170-188) |
| L5 | **subscriber HTTP 端点** | ✅ | 由 subscriber 决定 (bus_consumer 3x) |

## 为什么这样分
- L4 是 EventBus 边界, 重试可解 HTTP 网络抖动
- L5 是 subscriber 边界, 重试可解端点下线
- L2/L3 透传: 避免重试乘法 (1 个失败 = 9 次重试)

## 监控
- 写 1 个 `bus_stats()` 函数, 报告每层重试次数
- 看板: `~/.runtime/bus_dlq.db` SQLite + `bus_dlq` table

## 违规检测
- producer 写 `for attempt in range(3): ...` → lint 警告
- backend adapter 写 `with_retry(...)` → code review 拒绝
