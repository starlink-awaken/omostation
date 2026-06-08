# L4 Kernel · 分布式多Agent协作架构

**2026-06-08 · 长期战略 · 多机多节点多Agent**

---

## 一、当前覆盖面评估

### 1.1 已覆盖

```
✅ 单机单用户 · 21域 · 全层连接
✅ 单Agent会话 (cockpit context + OMO Phase 注入)
✅ 单域操作 (KEMS六面读写 + Schema校验)
✅ 跨域场景 (12个场景, 单机串联)
✅ 定时任务 (runtime cron, 单机调度)
✅ 信号闭环 (SignalBus, 单机域间通信)
✅ OMO 治理 (Phase/Task/Debt, 单机)
```

### 1.2 未覆盖

```
❌ 多机器 L4 数据同步 (不同机器的 ~/Documents/@*/)
❌ 多节点协同执行 (多个 runtime cron 节点)
❌ 多Agent并行操作同一域 (并发冲突)
❌ Agent间通信与协商 (无 Agent-to-Agent 协议)
❌ 分布式任务分配 (谁执行哪个场景)
❌ 跨机器信号路由 (机器A的信号 → 机器B的域)
❌ 联邦域管理 (多个机器的域注册表合并)
❌ 分布式一致性 (多机器修改同一域的同一文件)
```

---

## 二、分布式架构设计

### 2.1 核心模型

```
┌─────────────────────────────────────────────────────────────────┐
│                    L4 联邦层 (新增)                               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Node A     │  │  Node B     │  │  Node C     │              │
│  │  (主力机)    │  │  (工作机)    │  │  (移动端)    │              │
│  │             │  │             │  │             │              │
│  │ l4-kernel   │  │ l4-kernel   │  │ l4-kernel   │              │
│  │ DomainReg.  │  │ DomainReg.  │  │ DomainReg.  │              │
│  │ 12域(本地)   │  │ 5域(本地)    │  │ 3域(本地)    │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          │                                      │
│              ┌───────────▼───────────┐                          │
│              │   L4 Federation Hub   │  ← 新增组件              │
│              │                       │                          │
│              │  联邦域注册表          │                          │
│              │  跨节点信号路由         │                          │
│              │  分布式任务调度         │                          │
│              │  一致性协议            │                          │
│              └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 节点角色

| 角色 | 职责 | 典型节点 |
|------|------|---------|
| **Primary** | 域主节点, 持有域数据 | 主力机 (Mac) |
| **Replica** | 域副本节点, 同步数据 | 工作机 (Linux) |
| **Observer** | 只读观察节点 | 移动端 (Obsidian) |
| **Coordinator** | 任务调度协调者 | runtime cron 节点 |
| **Worker** | 执行任务的Agent | 任何有 l4-kernel 的节点 |

### 2.3 域分布策略

```
主力机 (Primary):
  @驾驶舱 (cockpit)    ← Primary
  @学习进化 (vault)     ← Primary
  @个人 (personal)      ← Primary
  @家庭生活 (family)     ← Primary
  @公共 (shared)        ← Primary

工作机 (Replica):
  @学习进化 (vault)     ← Replica (同步自 Primary)
  @卫健委 (work-weijian) ← Primary
  @国转中心 (work-guozhuan) ← Primary

移动端 (Observer):
  @学习进化 (vault)     ← Observer (Obsidian, 只读)
```

---

## 三、新增组件设计

### 3.1 FederationHub — 联邦中枢

```python
# l4_kernel/federation.py (新增)

class FederationHub:
    """L4 联邦中枢 — 多节点域管理。
    
    职责:
    1. 联邦域注册表 (合并所有节点的域)
    2. 跨节点信号路由
    3. 域数据同步策略
    4. 节点健康监控
    """
    
    def __init__(self, node_id: str, registry: DomainRegistry):
        self.node_id = node_id
        self.registry = registry
        self.peers: dict[str, PeerNode] = {}
    
    # ── 节点管理 ──
    def register_peer(self, peer: PeerNode) -> None:
        """注册对等节点。"""
    
    def discover_peers(self) -> list[PeerNode]:
        """发现网络中的其他节点。"""
    
    # ── 域同步 ──
    def get_federated_domains(self) -> dict[str, FederatedDomain]:
        """获取联邦域视图 (合并所有节点的域)。"""
    
    def sync_domain(self, domain_id: str, strategy: SyncStrategy) -> dict:
        """同步域数据。
        
        strategy:
        - PUSH: 主节点推送变更到副本
        - PULL: 副本拉取主节点数据
        - MERGE: 双向合并 (CRDT)
        """
    
    # ── 信号路由 ──
    def route_signal(self, signal: Signal, target_nodes: list[str]) -> None:
        """跨节点路由信号。"""
    
    # ── 任务调度 ──
    def assign_task(self, task: Task, strategy: TaskStrategy) -> str:
        """分配任务到最优节点。
        
        strategy:
        - AFFINITY: 分配到域主节点
        - LOAD_BALANCE: 负载均衡
        - CAPABILITY: 按能力分配
        """
```

### 3.2 PeerNode — 对等节点

```python
@dataclass
class PeerNode:
    node_id: str
    hostname: str
    role: str  # "primary" | "replica" | "observer" | "coordinator"
    domains: list[str]  # 该节点管理的域
    l4_kernel_version: str
    health_endpoint: str  # http://host:7455/health
    last_seen: datetime
```

### 3.3 FederatedDomain — 联邦域

```python
@dataclass
class FederatedDomain:
    domain_id: str
    primary_node: str  # 主节点 ID
    replica_nodes: list[str]  # 副本节点 ID
    observer_nodes: list[str]  # 观察节点 ID
    sync_strategy: str  # "push" | "pull" | "merge"
    last_sync: datetime
    conflict_resolution: str  # "primary_wins" | "last_write_wins" | "manual"
```

---

## 四、多Agent协作模型

### 4.1 Agent角色

```
Agent类型          职责                    通信方式
──────────────────────────────────────────────────
ResearchAgent      执行深度研究              MCP tools
GovernanceAgent    执行治理检查              定时 cron
MaintenanceAgent   执行维护任务              定时 cron
UserAgent          代表用户交互              cockpit CLI/MCP
CoordinatorAgent   协调多Agent任务            SignalBus + Task
```

### 4.2 Agent间通信

```
方式1: SignalBus (异步, 松耦合)
  Agent A: SignalBus.emit("cockpit", "ℹ️", "研究完成: {topic}")
  Agent B: SignalBus.aggregate_recent() → 发现信号 → 响应

方式2: OMO Task (显式, 紧耦合)
  Agent A: OmoBridge.create_task("需要代码审查", assignee="Agent B")
  Agent B: OmoBridge.get_my_tasks() → 执行 → update_status("done")

方式3: CARDS (目标驱动)
  Agent A: CardsPlane.scan_cards() → 发现 P0 卡片
  Agent B: 同一 CARDS 系统 → 避免重复执行

方式4: MCP 工具调用 (同步, 直接)
  Agent A → MCP: l4_health("vault")
  Agent B → 同一 MCP Server → 获取相同结果
```

### 4.3 并发冲突处理

```python
# l4_kernel/concurrency.py (新增)

class ConcurrencyManager:
    """多Agent并发操作管理。
    
    策略:
    1. 乐观锁: 读取时记录版本号, 写入时检查版本
    2. 文件锁: fcntl.flock (单机)
    3. 分布式锁: Redis/etcd (多机)
    4. CRDT: 冲突自动合并 (signals/TIMELINE)
    """
    
    def acquire_lock(self, domain_id: str, file_path: str) -> LockContext:
        """获取操作锁。"""
    
    def check_version(self, domain_id: str, file_path: str, 
                      expected_version: int) -> bool:
        """乐观锁版本检查。"""
    
    def merge_conflict(self, domain_id: str, file_path: str,
                       local: dict, remote: dict) -> dict:
        """CRDT 冲突合并。"""
```

---

## 五、多机场景扩展

### 场景 13: 跨机器域同步

```
触发: 定时 (每小时) 或 手动

Step 1 · Primary Node:
  FederationHub.sync_domain("vault", strategy=PUSH)
  └─ 计算变更 diff

Step 2 · Primary → Replica:
  └─ 推送变更到工作机

Step 3 · Replica Node:
  └─ 应用变更
  └─ 冲突检测 (如双方都修改了同一文件)
  └─ 冲突解决 (primary_wins)

Step 4 · Replica → Primary:
  └─ 确认同步完成
  └─ 发射信号: "✅ 域同步完成: vault (Primary→Replica)"

Step 5 · DASHBOARD 更新
  └─ 联邦域健康度
```

### 场景 14: 分布式任务分配

```
触发: OMO Task 创建

Step 1 · Coordinator:
  └─ 接收新 Task

Step 2 · Coordinator:
  ├─ 评估任务需求 (需要哪个域的数据? CPU密集型? IO密集型?)
  ├─ 查询各节点状态 (负载, 可用域)
  └─ 选择最优节点

Step 3 · Coordinator → Worker:
  └─ 分配任务: Task ID + 目标节点

Step 4 · Worker:
  └─ 执行任务
  └─ 更新 Task 状态

Step 5 · Coordinator:
  └─ 确认完成
  └─ DASHBOARD 更新
```

### 场景 15: 多Agent协同研究

```
触发: 复杂研究任务 (需要多Agent协作)

Step 1 · CoordinatorAgent:
  └─ 分解研究任务为子任务
  └─ 创建 OMO Tasks: 3 个子任务

Step 2 · CoordinatorAgent → WorkerAgents:
  └─ Task 1 → ResearchAgent@NodeA: "文献搜索"
  └─ Task 2 → ResearchAgent@NodeB: "数据分析"
  └─ Task 3 → ResearchAgent@NodeA: "报告撰写"

Step 3 · WorkerAgents (并行):
  └─ 各自执行子任务
  └─ 通过 SignalBus 报告进度

Step 4 · CoordinatorAgent:
  └─ 监控进度
  └─ 收集结果
  └─ 合并为最终报告

Step 5 · 归档:
  └─ vault: VaultSink 写入
  └─ cockpit: CARDS 更新
  └─ OMO: Task 全部完成
```

---

## 六、实施路线

| Phase | 内容 | 预估 |
|-------|------|------|
| **P4** | concurrency.py — 单机并发锁 | 1周 |
| **P5** | federation.py — FederationHub + PeerNode | 2周 |
| **P6** | 跨机器域同步 (场景13) | 2周 |
| **P7** | 分布式任务分配 (场景14) | 2周 |
| **P8** | 多Agent协同研究 (场景15) | 2周 |

### 当前可立即实施

**P4 · 单机并发锁** — 这是最紧急的。当前多Agent同时操作同一域时无并发保护。

```python
# concurrency.py 最小实现 (~50行)
# 使用 fcntl.flock 保护 signals.md 写入
# 使用 STATE.md 版本号实现乐观锁
```

要开始实施 P4 吗？