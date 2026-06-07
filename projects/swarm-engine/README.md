# swarm-engine — 群体智能引擎

> 多智能体任务编排框架 — 拍卖/竞价/DAG/生命周期/经济账本
> 原 `engine_core`，从 SharedBrain D_Execution 提取

## 核心能力

| 模块 | 功能 |
|:----|------|
| **auctioneer/bidder** | 市场化任务分配 — 多 Agent 竞价争夺任务 |
| **dag.py** | 任务依赖图编排 |
| **lifecycle_manager** | 全生命周期管理 (状态机/治理/持久化/看门狗) |
| **economy_seed** | EnergyLedger — 经济账本/资源核算 |
| **conflict_resolution** | CRDT 冲突解决 (LWW/ORSet/VectorClock) |
| **semantic_orchestrator** | 语义编排/意图分类/路由 |
| **worker_dispatcher** | Worker 分发/执行/监控 |
| **event_bus** | 事件总线/消息代理 |

## 来源

从 SharedBrain D_Execution 提取，原 `llm-gateway-kernel` 中的 `engine_core` 模块。
