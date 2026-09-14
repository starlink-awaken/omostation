# Pitch: L0 协议层抽象统一的调度触发器与分布式锁接口

## 1. 现状与痛点 (Context & Problem)
系统经历多次演进后，并发、定时任务、后台常驻任务以及多进程安全锁等机制散落在各处，形成了严重的架构碎片：
1. **定时触发器分裂**：GitHub Actions, crontab, runtime cron_service, bus_foundation croniter backend。
2. **并发控制分裂**：l4_kernel 的单机文件锁 `fcntl`，gbrain 的 Bun Worker Threshold 控制，gbrain 基于 `gbrain_cycle_locks` 的行级 TTL 分布式锁。
3. **工作流耦合**：MetaOS 与底层执行环境的事件循环强耦合（缺少统一的节点上卷规范）。

目前系统处于 `code_freeze: true` 阶段。但这些底层碎片如果不在未来的 Refactoring 周期中收敛，将成为制约“多智能体大规模并行”与“全链路观测”的技术债。

## 2. 第一性原理抽象 (Essence & Proposal)
无需（也不可能）在代码实现层将 TS 与 Python 生态强行融为一体，我们只需要在 **ecos L0 协议层（MOF）** 进行“治理语义”的收拢：

### 2.1 触发器注册表 (Trigger Registry)
- 在 L0 建立唯一的 `cron_registry.yaml`。
- 将 `GitHub Action`、`本地 crontab` 等均降级为无状态的 **Runner**，通过注册表进行统一的调度意图声明。

### 2.2 分布式锁服务抽象 (BOS Lock Protocol)
- 借由现有的 Agora BOS，暴露 `bos://capability/lock` 服务接口。
- 所有需长时间执行、具备互斥资源占用的任务（无论来自 gbrain 还是 omo worker），都必须请求 BOS 获取锁协议。底层可用 `gbrain_cycle_locks` 或 `fcntl` 来支撑，但对上层透明。

### 2.3 状态机事件上卷 
- 推进 MetaOS 工作流与底层彻底解耦，统一采用 `bus_foundation` 抛出 `NODE_COMPLETED` 等标准化事件进行状态转移。

## 3. 验收标准与下一步 (Acceptance & Next Steps)
- 此提案目前处于 **Sandbox Draft** 状态，并在 `omo task` 的 `planned` 队列中建立卡片。
- 解冻后（code freeze lifted），此重构将作为优先目标推进。
