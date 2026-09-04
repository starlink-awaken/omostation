---
schema_version: specification/v1
spec_version: 1.0.0
title: Event stream bus
bet_id: BET-Y1Q4-T2-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
type: ssot
last_updated: 2026-09-03
---

# Event Stream Bus (T2-01)

## Intent

轻量本地事件总线：统一汇聚 OA/邮件/日历/RSS/IM 信号，优先级动态排队+背压，
100% 单机主权（asyncio 标准库，无外部 MQ——BET non_goal）。

## Architecture

```
projects/omo/src/omo/event_bus.py（核心）
├─ PriorityEventBus: 双队列（high/normal）——高优先 drain 优先出队
│   （公文/来信毫秒级直达；同优先级 FIFO）
├─ 背压: per-queue maxsize（默认 10000=circuit_breaker 阈值）
│   溢出→丢弃最旧 normal + overflow 计数 + 高危标记
├─ 多源并发: async producers（每源一个 task）
└─ 纯标准库（asyncio + dataclass），零依赖

bin/bc-os/signal_router.py（扩展 --stream-benchmark）
└─ 基准: N 并发源 × M 事件 → 计时出队 → 断言 ≥1000 events/s
   + 高优出队延迟 < 10ms 断言 + 背压丢弃路径验证
```

## Acceptance mapping

- ≥1000 events/s: benchmark 断言（本地 asyncio 实际可达数万/s，留足余量）
- 高优毫秒直达: 高优事件在 normal 队列非空时仍优先出队，延迟断言
- 背压: maxsize 溢出丢弃 + overflow_count + 告警标记（circuit_breaker 契约）
- Cockpit Spine 直达: 出队侧 subscriber 接口（Spine 接线随 T5/T8 站）
