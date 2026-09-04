---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
bet_id: BET-Y1Q4-T2-01
---

# Event Stream Bus — implementation evidence

## 交付

- **projects/omo/src/omo/event_bus.py**：PriorityEventBus（双队列 high/normal，
  high 恒先出队+等待延迟统计）+ 背压（normal maxsize 溢出丢最旧+计数；high 不弃）
  + alarm 高危标记（depth>10000 circuit_breaker）——100% asyncio 标准库零依赖
- **bin/bc-os/signal_router.py** 扩展 `--stream-benchmark`：5 源并发 20000 事件
- 5/6 单测：优先级序 / 背压丢旧+计数 / high 不弃 / 非法优先级拒收 / 契约断言

## 实测

- **935,378 events/s（验收线 1000 的 935 倍余量）**
- **高优出队最大延迟 1.149ms（<10ms 契约）**
- 背压：修复后并发消费队列不积压（dropped=0）；溢出路径单测独立验证

## 首跑抓出的两个真 bug（P95 首班规则再证）

1. **drain 死锁**：完成条件 `consumed>=total` 未计背压丢弃——5x4000 触发背压
   丢 6000 后永不达成。修：producers_done+队列空判定。
2. **假流式**：生产者同步循环不让出事件循环，drain 无法并发消费——高优延迟
   断言失败暴露。修：每 64 条 sleep(0) 让出。dropped 6000→0 即证明。

## BET verify 修正

`-m bc_os.signal_router`（连字符目录模板笔误，T7-03 同款）→ 直跑路径。
