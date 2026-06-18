# 沉淀全局触发器注册表与分布式锁机制

## 0.1 竞品与现状调研 (Research & Benchmarking)
> [强制要求] AI 必须在此处填写真实调研：

1. **系统内部是否已有现成代码/组件？**
   - 是的，目前锁机制散落在多处：`l4-kernel` (`concurrency.py`) 实现了基于 `fcntl.flock` 的本地文件锁和简单的基于 `mtime` 的乐观锁；`runtime` 中使用了 `threading.Lock`。
   - 触发器机制同样碎片化：`runtime.cron_service` 自建了基于线程池的调度；而 MetaOS 与 Agora 也有各自的事件消费挂载机制。
2. **开源界/工业界是否有成熟对标物？**
   - 工业界分布式锁通常采用 Redis (`Redlock`)、Zookeeper 或是 Etcd 等强一致性 KV 存储来实现。
   - 触发器注册表一般参考 Kubernetes 的 Declarative CronJobs，或是基于 Celery/APScheduler 封装的中心调度器。
3. **证明“为什么必须自研或二次开发”？**
   - 我们目前的系统环境 (eCOS v6) 采用 5+4+1+1 架构，强依赖文件系统（如 `.omo` 状态文件库）与 BOS URI 层，并没有引入 Redis 这样的大型中间件依赖。如果要保持系统的轻量化（SQLite / 文件基底 / 共享内存），我们需要在底层协议 (L0 ecos) 抽象一套接口规范，并在上层做具体适配。

## 0.2 关键决策对齐 (Critical Decisions)
> [强制要求] AI 必须抛出至少 3 个影响全局架构的关键选择题，并给出推荐意见。用户需在此作答。

1. **[决策点1] 分布式锁的核心存储载体选择？**
   - AI推荐: **基于 SQLite 的分布式锁与信号量。** (`ecos` 中已有 SQLite 基建抽象)。相比单纯基于文件系统的 `fcntl`（多容器或跨物理机失效），SQLite WAL 模式下的互斥事务更适合微服务解耦环境。
   - 您的选择: [等待用户输入]
2. **[决策点2] 触发器 (Trigger) 的声明方式与作用域？**
   - AI推荐: **BOS URI 为核心的声明式注册表** (`bos://capability/trigger/{name}`)。统一存储在 YAML 中（如 `.omo/registry/triggers.yaml`），让所有服务启动时声明，下沉给底层的统一调度中心。
   - 您的选择: [等待用户输入]
3. **[决策点3] 现存 `l4-kernel` 文件锁平滑迁移策略？**
   - AI推荐: **适配器模式**：在 L0 提出 `LockFacade`，在 `l4-kernel` 提供其基于文件锁的实现，同时在 `runtime` 引入基于 SQLite 的实现。未来平滑切走。
   - 您的选择: [等待用户输入]

---

## 1. 方案细化与定型 (Solution Refinement)
**What:** 
1. 在 `projects/ecos/src/ecos/` L0 层增加两个新的抽象接口集：`ecos.locks` 和 `ecos.triggers`。
2. `ecos.locks` 定义标准的 `acquire()`, `release()`, `try_lock()`，以及乐观锁 `check_and_set()` 接口。
3. `ecos.triggers` 定义 `CronTrigger`, `EventTrigger`, `HookTrigger` 的规范接口和元数据数据类。

**Why:**
消除系统中的“局部锁”与“局部 Cron”，使得全工作区不论是哪个层级，并发争抢与任务唤醒都能被集中审计 (Audit) 与跟踪，这对于 MetaOS 状态机和 L4 的沙箱安全极其重要。

## 2. 可行性与必要性审查 (Feasibility & Necessity)
必要性极大。系统目前的并发问题在 `pre-commit` OOM 与日志冲突时已有暴露。如果不下沉抽象，一旦部署分布式组件，必然产生脑裂与脏写问题。开发量适中，仅为接口抽象与局部组件迁移，ROI 高。

## 3. 架构审查 (Architecture Review)
放在 `L0 ecos` 协议层最合理，所有其他层都依赖于 `ecos`。锁的管理本身是基础设施，通过 BOS 域 `bos://governance/locks` 及 `bos://capability/triggers` 进行抽象，符合系统原有的 5 域治理架构。不会引入反向依赖。

## 4. 治理审查 (Governance Review)
完全符合 X1-X4 约束。我们不动底层的业务流转，只是统一基础组件规范，不会带来 OMO Debt。平滑演进策略确保在老代码未迁移前系统仍能工作。

## 5. 红队分析 (Red Team Analysis - Devil's Advocate)
1. **死锁引发全局卡死**：如果新的锁服务设计错误或超时机制失效，可能导致所有消费者线程组集体卡住。需强制带 Timeout。
2. **触发器雪崩**：中心化的触发器如果在一秒内唤醒上千个并发任务，会导致 `runtime` OOM，需增加背压 (Backpressure)。
3. **SQLite Write 被独占锁死**：如果用 SQLite 实现锁，某进程意外 Crash 后未释放，需要提供定期的 Lock Heartbeat 检测。

## 6. 用户视角审查 (User Perspective)
对开发者来说将变得异常简单。以前需要自己管理 `fcntl.flock` 或线程池，现在只需通过 `ecos.locks.Lock("lock_name")` 以及配置 YAML 即可完成并发控制和触发器定义。

## 7. 质量保障 (Quality Assurance)
### 7.1 测试计划 (Test Plan)
- [X1-X4 Governance] 必须在代码实现前完成治理与架构依赖的白盒分析。
### 7.2 验收证据 (Evidence Required)
- X1-X4 治理合规自证
- 单测覆盖率

---

## 🎯 任务拆解 (GSD Action Items)
- [ ] 任务1: 在 `ecos/src/ecos/concurrency/` 中定义 L0 分布式锁的基础 Interface 和异常类 (`LockAcquireError` 等)。
- [ ] 任务2: 在 `ecos/src/ecos/triggers/` 中定义全局触发器声明标准 (`TriggerSchema` Pydantic models)。
- [ ] 任务3: 将 `l4-kernel` 中的 `fcntl` 锁提取为 `ecos` 分布式锁的一个具体实现类，并重构 `l4_kernel.concurrency` 以实现向下适配。
