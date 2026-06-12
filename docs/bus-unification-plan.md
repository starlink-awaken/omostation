# Bus Unification Plan

> Date: 2026-06-12
> Status: Phase A.0 (R57)
> Phase B 触发: 5 硬条件 (见 ADR-0008)

## 目标
在 agora/bus/ 子包里建 1 个统一接口, 让新代码用 `from agora.bus import publish/subscribe/schedule` 替代选 8 套机制。

## 架构图

```
┌────────────────────────────────────┐
│ agora/bus/__init__.py (facade)     │  ← 1 行 import, 业务用
│   publish(envelope)                │
│   subscribe(pattern, fn)            │
│   schedule(expr, fn)               │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│ agora/bus/router.py                │  ← 路由 envelope.backend → backend
│  RouteConfig(backend="eventbus")   │
└──────────────┬─────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│ eventbus.py │  │ (其他 7 个  │  ← Phase A.0 只 1 个
│  (Phase A.0)│  │  Phase A.1) │
└──────┬──────┘  └─────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ dlq.py (失败兜底)                  │
│  ~/.runtime/bus_dlq.db             │
│  SQLite WAL + 50MB GC              │
└────────────────────────────────────┘
```

## 决策表 (选 backend)

| 场景 | backend | 为什么 |
|------|---------|--------|
| 跨进程事件 | `eventbus` | 唯一跨进程总线 |
| 进程内 awaitable | `asyncio` (A.1) | 低延迟, 不用落盘 |
| 推客户端 | `sse` (A.1) | 单向 push |
| 双向通信 | `ws` (A.1) | full-duplex |
| Task 状态 | `realtime` (A.1) | 复用 version 逻辑 |
| Agent 通信 | `messagebus` (A.1) | 保持 req/resp |
| 定时任务 | `croniter` (A.1) | cron expr 强 |

## 红线 (6 项)
1. ❌ bus adapter 自身不重试 (透传, 避免重试乘法)
2. ❌ 单 backend 单文件 < 500 行
3. ❌ bus/ 子包总行数 < 3000 (R57 末)
4. ❌ 改 audit_subscriber 的 import 不改 API 调用
5. ❌ omo/metaos/runtime 代码 R57 不动
6. ❌ Phase A 不拆仓

## 风险表
| 风险 | 缓解 |
|------|------|
| God module (5000+ 行) | 5 文件拆分 + 500 行硬上限 |
| DLQ SPOF | WAL + busy_timeout + 50MB GC |
| 重试乘法 | RETRY-OWNERSHIP.md 写明 |
| API 演化失控 | A.0 末冻结 6 月 |
