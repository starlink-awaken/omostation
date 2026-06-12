# Retry Ownership Rule (R57+, R66 split)

## 核心规则
**每条事件链路只有 1 层做重试, 其他层透传。**

## 链路分层 (从 producer 到 consumer)

| 层 | 组件 | 是否重试 | 重试参数 |
|----|------|---------|---------|
| L1 | producer 代码 | ❌ | - |
| L2 | `bus_foundation.publish` | ❌ (透传) | - |
| L3 | `bus_foundation.backends.*` | ❌ (透传) | - |
| L4 | **底层 transport 自身** (agora EventBus / croniter) | ✅ | 由 transport 决定 |
| L5 | **subscriber 端点** | ✅ | 由 subscriber 决定 |

## 为什么这样分
- L4 是 transport 边界, 重试可解网络抖动
- L5 是 subscriber 边界, 重试可解端点下线
- L2/L3 透传: 避免重试乘法 (1 个失败 = 9 次重试)

## 监控
- 看板: `~/.runtime/bus_dlq.db` SQLite + `bus_foundation_dlq` table
- 失败入 DLQ 不抛 (避免事件丢失)

## 违规检测
- producer 写 `for attempt in range(3): ...` → lint 警告
- backend adapter 写 `with_retry(...)` → code review 拒绝
