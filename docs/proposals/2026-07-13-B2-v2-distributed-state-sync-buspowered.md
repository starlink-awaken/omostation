# B2 · 分布式状态同步设计 v2（bus-foundation 驱动版）

> 状态: DRAFT v2 · 日期: 2026-07-13 · 取代 B2 v1（raw gossip 版）
> 迭代原因: ADR-0180 把 bus-foundation Omni-Bus 定为全系标准，其 ws_v2 后端已提供跨机传输——v1 的"复用 raw gossip 不引中间件"决策过时。
> 对应 Roadmap Phase 1 / M1 · 验收锚点: 2 机状态同步延迟 p99 < 100ms
> 前置纪律不变: B 代码执行(B3+)仍等 A5 确认健康探测变真。

## 1. 迭代要点（v1 → v2 变了什么）

| 维度 | v1（旧） | v2（新，本文件） | 依据 |
|------|---------|-----------------|------|
| **跨机传输** | 复用 SwarmOrchestrator raw gossip + UDP | **bus-foundation Event 平面 / `ws_v2` WebSocket 后端** | ADR-0180 标准 + ws_v2 已有压缩/心跳/版本 |
| 压缩 | 待延迟不达标再加 | **现成**（ws_v2 per-message-deflate） | R95 |
| 心跳/健康 | SwarmOrchestrator 心跳 | SwarmOrchestrator 角色/发现 + bus Control 平面健康 | 分工 |
| 冲突解决 | DeterministicConflictResolver vector_clock | **不变** | swarm_engine 现成 |
| 一致性模型 | 最终一致 + 确定性合并 | **不变** | — |
| 同步状态切片 | 节点健康/注册表 | **不变** | 低风险高价值 |

**净效果**：B 比 v1 更省——传输层从"要接 gossip 载荷 + 后加压缩"变成"直接挂 bus-foundation Event 平面标准信封"，且顺着刚立的组织标准而非逆着它。

## 2. 三件现成件组合（M1 架构）

```
┌────────────── 机器 A ──────────────┐        ┌────────────── 机器 B ──────────────┐
│ SwarmOrchestrator (master/worker)   │        │ SwarmOrchestrator (worker)          │
│  · 角色/UDP 发现/节点注册            │        │  · 心跳上报                          │
│                                     │        │                                     │
│ 节点健康/注册 KV (+_vector_clock)    │        │ 节点健康/注册 KV (+_vector_clock)    │
│        │ publish(Envelope)          │        │        ▲ subscribe                  │
│        ▼                            │        │        │                            │
│ bus-foundation Event 平面 ═══ ws_v2 WebSocket(压缩+心跳+版本) ═══════════════════▶ │
│                                     │        │        │                            │
│                                     │        │        ▼ DeterministicConflictResolver│
│                                     │        │          .vector_clock → 写本地 registry│
└─────────────────────────────────────┘        └─────────────────────────────────────┘
```

- **SwarmOrchestrator**（`agora/mcp/swarm.py`）：角色、UDP 发现、节点注册、本地心跳。**不再**用它的 raw gossip 做跨机传输。
- **bus-foundation `ws_v2`**（`bus_foundation/backends/ws_v2.py`）：跨机 WebSocket 传输，Omni-Bus Envelope 标准信封，per-message-deflate 压缩，心跳，协议版本。走 Event 平面 + `topics` SSOT。
- **DeterministicConflictResolver**（`swarm_engine/conflict_resolver.py`）：收到远端 KV → `vector_clock` 策略合并 → 写本地 registry。

## 3. 决策（v2）

- **决策 1 · 传输**：M1 用 bus-foundation Event 平面（`ws_v2` 后端）做跨机状态传播。理由：ADR-0180 组织标准、已有压缩/心跳/版本/DLQ、避免重复造 gossip。
- **决策 2 · 一致性**：不变——per-key `vector_clock` 最终一致 + 确定性合并（CRDT-lite），零新依赖。
- **决策 3 · 状态切片**：不变——M1 只同步节点健康/注册表；BOS 路由/任务/治理面留 M2+。
- **决策 4 · 拓扑**：master 订阅所有 worker 的状态 topic，worker 订阅 master 的聚合视图；2 机即 A↔B 双向。

## 4. GAP（B3/B4 真实工作，比 v1 更少）

1. **确认 ws_v2 接入 facade**：`ws_v2` 后端已存在，但需确认它被 `BusFacade` 的后端选择暴露（本轮 grep facade 未直接命中，B3 首查）。若未接，补一个 facade 后端注册（小）。
2. **topics SSOT 加两条**：`swarm.node.health`、`swarm.node.registry`（进 `bus_foundation.topics`）。
3. **状态载荷 ↔ Envelope**：把节点健康/注册 KV + `_vector_clock`/`_timestamp` 封进 Omni-Bus Envelope；收端解封 → conflict_resolver → 写本地。
4. **2 机基准台**：A/B 各起 orchestrator + bus ws 后端，一端改状态，测另一端收敛 p50/p99。
5. **故障用例**：worker 掉线 → 心跳超时 → 状态标记 + failover；bus DLQ 处理传输失败重放。

## 5. 风险 / 依赖

- **ws_v2 成熟度**：R95 已实现 serve_forever + 压缩，但 B3 需实测握手/重连稳定性（bus-foundation 刚从"声明未执行"转正，adoption 新）。
- **端口治理**：ws 默认 127.0.0.1:8765（已是 deprecated 端口之一），须走 `port-registry.yaml` 注册真实端口，勿硬编码（P77 env-var-SSOT）。
- **依赖 A3/A4**：同步的"节点健康"必须真实，否则同步的是假状态——这就是 B 等 A5 的根本原因；A3 把探测做真之后此设计才可信。
- **与并发 P7X 流协调**：bus-foundation 正由 starlink-awaken 落地中（ADR-0180），B3 启动前对齐其 facade/topics 现状，避免撞车。

## 6. 验收（M1，不变）
2 机各跑 orchestrator + bus ws；节点健康/注册经 Event 平面 + vector_clock 收敛；端到端 p99 < 100ms（可复现）；worker 掉线 15s 内标记 + failover。

## 7. 战略备注 · decl/exec 元门禁（喂给 A4/C1）
ADR-0180 揭示 bus-foundation 曾是"8 声明 / 0 调用"的第三个声明/执行鸿沟（前两:BOS resolve A1、daemon 假绿灯 A3），且各自打了点状 gate（BOS resolve gate / probe-truth / dormant-adapter gate）。**治本是一条 decl/exec 一致性元规则**（A4 的 `DECL-EXEC-CONSISTENCY` 统摄三者），而非累加点状 gate——正好落实 C1"先减后加"。建议 A4 落地时把这三个点状 gate 也纳入合并评估。

## 8. 下一步
- ADR 编号顺延：hermes+GaC 那份草案改 **ADR-0181**（0180 已占）。
- B1 立项(c2g-spec-ingress, appetite 2 周, 锁本切片) —— 待 A5 绿灯。
- B3 首动作：查 `BusFacade` 是否已暴露 ws_v2 + topics 现状（GAP #1）。
