---
type: ephemeral
status: archived
---

# BET-Y1Q4-T2-01 Retro — Event Stream Bus

## 做对了

- 纯标准库 asyncio——non_goal 契约（无外部 MQ）零妥协达成
- benchmark 断言从第一天就是契约的一部分（不是事后补的性能测试）
- 首跑大规模（5x4000）而非舒适规模（3x1000）——两个 bug 都是规模暴露的

## 踩坑

- drain 完成条件未计背压丢弃 → 死锁（并发+丢弃的交互盲区）
- 生产者无让出 = 假流式（asyncio 的协作式调度在无 await 循环下退化为串行）
- verify 模板病第二例（-m 连字符目录）——#2788 模板系统性缺陷，建议批量修

## 下一步

- Spine subscriber 接线（T5/T8 站）
- policy_radar 源接入（producer 适配器——管线站间咬合）
