---
title: Swarm Protocol — 多twin协作标准
lifecycle: contract
owner: governance-team
last_updated: 2026-08-08
---

# Swarm Protocol — 多twin协作标准

> 标准编号: SP-001 | 状态: active | 创建: 2026-08-08
> 参考: ADR-0396 (数字生命体架构), M2: swarm.yaml

## 1. 概述

Swarm是多个数字twin的临时编组, 为共同目标协作。编组按需形成, 完成后解散。

## 2. 生命周期

```
forming → active → dissolved
```

- **forming**: 发起者提议目标+成员, 各成员Advisor评估是否加入
- **active**: 共享上下文, 任务委托, 进度同步
- **dissolved**: 目标达成或放弃, 解散, 各成员返回独立运行

## 3. 发现机制

每个twin通过Agent Registry声明自己的能力。发现方式:
- 本地namespace扫描 (同一omostation实例)
- A2A协议 (跨实例, 未来)

## 4. 通信

- 总线: Aetherforge bus_adapter
- 频道: `swarm:{swarm_id}:shared` (全员), `swarm:{swarm_id}:direct:{from}:{to}` (点对点)
- 隐私: 成员间不暴露private namespace数据, 只传任务描述+结果

## 5. 角色与分工

| 角色 | 职责 | 谁担任 |
|------|------|--------|
| Coordinator | 任务分解+进度追踪+汇总 | 发起者twin |
| Specialist | 特定能力执行 | 按能力匹配的成员twin |
| Reviewer | 质量审查+冲突仲裁 | Coordinator或指定成员 |

## 6. 冲突处理

当两个成员输出冲突时:
1. Coordinator检测冲突
2. 各成员提供reasoning
3. Reviewer裁决 (或升级到人工)
4. 记录到decision_outcome

## 7. 解散条件

- 目标达成: 所有任务completed
- 超时: deadline到达
- 放弃: 发起者主动解散
- 异常: 连续3次任务失败
