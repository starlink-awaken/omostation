# 深度架构分析：多Agent协作 · 第一性原理 · 控制面设计

> 日期: 2026-05-29 | 版本: v1.1 | 审计: agent-architecture-audit-redteam.md
> 主题: Agent协作集成 · 本体Agent选型 · 第一性原理优化 · 分层控制面 · Agent-as-Kernel
> 修订: v1.1 — 增加安全机制(操作分级/Agent沙箱/死锁检测/检查点)、NATS推迟、AI-Scientist-v2仅取BFTS、控制器滞回、跨层反馈、全局熵度量
> 本文档是历史架构分析输入，保留当时的多 Agent 协作设想、组件分工与控制面设计，不是当前 Agent 实现状态、工具计数或当前入口拓扑 SSOT。
> 当前事实请以 `/.omo/PROJECTS.yaml`、`AGENTS.md`、`docs/PANORAMA.md` 和当前代码为准。

---

## 目录

1. [多Agent协作架构](#一多agent协作架构)
2. [本体Agent工具对比与选型](#二本体agent工具对比与选型)
3. [第一性原理架构升级](#三第一性原理架构升级)
4. [分层控制面/管理面设计](#四分层控制面管理面设计)
5. [Agent-as-Kernel模式](#五agent-as-kernel模式)
6. [实施路线建议](#六实施路线建议)

---

## 一、多Agent协作架构

### 1.1 现状分析

```
当前 agent 分布:
┌─────────────────────────────────────────────┐
│ agentmesh: 30+ Agent类型 (TS)              │  ← 有Agent框架，无统一协作
│ SharedBrain: D-Execution 编排器 (Python)    │  ← 器官级编排，不跨项目
│ gstack: 53 编排脚本 (TS)                   │  ← 脚本级编排，无Agent
│ gbrain: 74 MCP tools (TS)                  │  ← 工具集，无Agent编排
│ kairon: 各包独立工具 (Python)               │  ← 管线式，非Agent式
└─────────────────────────────────────────────┘

痛点:
❌ Agent之间无直接通信通道
❌ 没有统一的任务派发机制
❌ 没有Agent能力发现机制
❌ 没有跨Agent的消息总线
❌ 专业Agent（如DeepCode用于编码）无法接入
```

### 1.2 协作架构设计

```
                   ┌──────────────────────────────┐
                   │   Agent Control Plane (ACP)   │
                   │                              │
                   │  ┌──────────┐ ┌───────────┐  │
                   │  │ Agent    │ │ Task       │  │
                   │  │ Registry │ │ Dispatcher │  │
                   │  └──────────┘ └───────────┘  │
                   │  ┌──────────┐ ┌───────────┐  │
                   │  │ Event    │ │ Result     │  │
                   │  │ Bus      │ │ Aggregator │  │
                   │  └──────────┘ └───────────┘  │
                   │  ┌──────────┐ ┌───────────┐  │
                   │  │ State    │ │ Policy     │  │
                   │  │ Manager  │ │ Engine     │  │
                   │  └──────────┘ └───────────┘  │
                   └──────────┬───────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼────┐  ┌───────▼──────┐  ┌─────▼──────────┐
    │ agentmesh    │  │ SharedBrain  │  │ External Agents │
    │ 30+ Agents   │  │ D-Execution  │  │ DeepCode, etc.  │
    └──────────────┘  └──────────────┘  └────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Agora (MCP)     │
                    │   统一通信协议      │
                    └───────────────────┘
```

### 1.3 核心组件

**Agent Registry** — 谁有什么能力？
```
registry:
  agentmesh/research_agent:
    capabilities: [deep_research, web_search, paper_writing]
    protocols: [MCP, REST]
    endpoint: mcp://agentmesh:3000

  sharedbrain/execution_agent:
    capabilities: [task_orchestration, organ_lifecycle]
    protocols: [MCP, BOS-URI]
    endpoint: mcp://sharedbrain:7421

  external/deepcode_agent:
    capabilities: [multi_file_coding, architecture_analysis]
    protocols: [MCP]
    endpoint: mcp://external:9000
```

**Task Dispatcher** — 谁最适合做这个任务？
```
Task: "分析 kairon 架构并生成优化方案"
  → Decompose into subtasks:
    1. analyze existing code → dispatch to deepcode_agent (coding)
    2. research architecture patterns → dispatch to agentmesh/research_agent
    3. generate optimization plan → dispatch to agentmesh/planning_agent
  → Aggregate results → Return to caller
```

**Event Bus** — Agent之间如何通信？

三选一方案：

| 方案 | 实现 | 优点 | 缺点 | 推荐 |
|------|------|------|------|:---:|
| **Agora MCP 原生** | 扩展现有 Agora，增加 PubSub 模式 | 零新依赖，架构一致 | 不是真正的消息队列 | ⭐⭐⭐ |
| **Redis PubSub** | 部署 Redis，Agent 订阅频道 | 成熟方案，支持集群 | 新增外部依赖 | ⭐⭐⭐⭐ |
| **NATS** | 部署 NATS Server | 专为微服务设计，轻量 | 新增外部依赖，需学习 | ⭐⭐⭐⭐⭐ |

**推荐**: **Phase 2 先用 Agora MCP 原生 PubSub（零新依赖）。** Phase 3 评估是否需要升级到 NATS。不要过早优化。Agora MCP 足以处理 100+ tools 的事件通信，NATS 的额外复杂度（部署/运维/学习）当前阶段不值。

> ⚠️ 审计修正: 原推荐 NATS，红队审计发现引入新依赖的风险大于收益。改为渐进式：先用 Agora，不够再升级。

### 1.4 安全机制 (审计新增)

**操作分级 (Operation Levels)** — 防止 LLM 幻觉导致灾难：

| 级别 | 类型 | 示例 | Agent 自主? |
|:----:|------|------|:----------:|
| **L0** | 读操作 | 查询、搜索、状态检查 | ✅ 完全自主 |
| **L1** | 低风险写 | 创建索引、记录日志 | ✅ 自主但审计 |
| **L2** | 高风险写 | 修改配置、更新 Schema | ❌ 需人类确认 |
| **L3** | 破坏性操作 | 删除数据、重启服务、修改护栏 | ❌ 人类确认 + 24h 冷静期 |

**Agent 沙箱 (Agent Sandbox)** — 新 Agent 或新版本必须先沙箱测试：

```
新 Agent 加入流程:
1. Agent 注册到 Registry (status: sandbox)
2. 隔离环境运行 7 天 (沙箱: 无外网, 只读数据, 操作记录)
3. 自动评估: 异常操作? 权限越界? 资源消耗?
4. 人类审查沙箱报告 → 通过 → status: active
5. 不通过 → 退回修改
```

**死锁检测 (Deadlock Detection)** — 防止两个 Agent 互相等待：

```
检测机制:
- 每个 Agent 操作有超时 (默认 5min)
- Deadlock Monitor Agent 分析 Agent 依赖图
- 检测到循环等待 → 终止低优先级 Agent 的操作 → 通知人类
- 终止的 Agent 从检查点恢复
```

### 1.4 协作模式

```
模式1: 任务分派 (Task Dispatch)
  User → ACP Dispatcher → Agent(最佳) → 执行 → Result Aggregator → User

模式2: Agent协作 (Agent Collaboration)
  Agent A 发现需要编码能力 → 查询 Registry → 找到 Agent B(DeepCode)
  → ACP Event Bus: A 发布 "code_review_request" → B 订阅并响应

模式3: 管线编排 (Pipeline)
  ACP Dispatcher → Agent A (research) → Event → Agent B (derive) → Event → Agent C (index)

模式4: 共识决策 (Consensus)
  3+ Agents 对同一问题给出答案 → ACP Result Aggregator 投票 → 置信度输出
```

---

## 二、本体Agent工具对比与选型

### 2.1 候选Agent系统对比

| 系统 | 类型 | 语言 | 许可证 | 核心能力 | 与omostation适配度 |
|------|------|:---:|:-----:|------|:---:|
| **agentmesh** | Agent运行时 | TS | MIT | 30+ Agent类型, MCP网关 | ⭐⭐⭐⭐⭐ (已有) |
| **OpenManus** | 通用Agent | Python | MIT | 多工具集成, 浏览器 | ⭐⭐⭐ (通用型, 无特色) |
| **DeepCode** | 编码Agent | Python | MIT | 多文件协作编码 | ⭐⭐⭐⭐ (编码特化) |
| **AI-Scientist-v2** | 研究Agent | Python | Apache | 自主科研(假设→实验→论文) | ⭐⭐⭐⭐ (研究特化) |
| **pi-acp** | Agent协议 | — | MIT | Agent通信协议(ACP) | ⭐⭐⭐⭐⭐ (协议, 可直接集成) |
| **CrewAI** | 编排框架 | Python | MIT | Role-based agents | ⭐⭐⭐ (外部框架, 重复) |
| **AutoGen** | 编排框架 | Python | MIT | 微软多Agent框架 | ⭐⭐⭐ (外部框架, 重复) |
| **LangGraph** | 编排框架 | Python | MIT | 图状态机, Agent DAG | ⭐⭐⭐ (外部框架, 重复) |
| **Agency-Agents** | Agent模式 | TS | MIT | Agency pattern | ⭐⭐⭐ (参考模式) |
| **Multica** | 协作框架 | — | MIT | 多Agent协作 | ⭐⭐⭐ (参考模式) |

### 2.2 选型结论

**不引入新的Agent框架**（CrewAI/AutoGen/LangGraph）——它们与agentmesh定位重叠。

**集成三个外部Agent系统作为专业能力补充**：

```
omostation Agent 生态:

┌─────────────────────────────────────────────────┐
│            agentmesh (主Agent运行时)              │
│  30+ Agent类型, MCP网关, LLM路由, 任务编排        │
│  角色: 通用Agent平台 + 编排中枢                   │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼────┐ ┌─────▼──────┐ ┌──▼──────────────────┐
│ DeepCode   │ │ AI-Scientist│ │ SharedBrain D-Exec  │
│ 编码特化   │ │ 研究特化    │ │ 合规+免疫+自愈       │
│ MCP接入    │ │ MCP接入    │ │ BOS-URI + MCP       │
└────────────┘ └────────────┘ └─────────────────────┘
        │            │            │
        └────────────┼────────────┘
                     │
          ┌──────────▼──────────┐
          │  pi-acp 协议层      │
          │  Agent通信协议标准   │
          │  (可选的未来方向)    │
          └─────────────────────┘
```

### 2.3 集成方式

每个外部Agent系统通过 **MCP Server + Agent Registry** 接入：

```python
# agentmesh注册DeepCode为专业Agent
registry.register({
    "agent_id": "deepcode",
    "type": "external",
    "capabilities": ["multi_file_coding", "architecture_analysis", "refactoring"],
    "mcp_endpoint": "mcp://deepcode:9000",
    "protocol": "MCP",
    "priority": 2,  # 编码任务优先路由到DeepCode
})

# ACP Dispatcher when receiving a coding task:
# 1. Query registry: "which agent handles coding?"
# 2. Match: deepcode (priority 2) vs agentmesh/coding_agent (priority 1)
# 3. Dispatch to deepcode
```

---

## 三、第一性原理架构升级

### 3.1 控制论视角：反馈闭环设计

**当前问题**: minerva→KOS→gbrain 是单向管道。没有反馈。

```
当前: minerva → KOS(index) → gbrain(memory)
      研究     → 索引        → 存储
      (无反馈)

升级: minerva ←── KOS(index) ──→ gbrain(memory)
      研究        ↕ 反馈          ↕ 反馈
      
      反馈回路:
      1. KOS检测: 某领域知识质量下降 → 通知minerva重新研究
      2. gbrain检测: 某记忆从未被访问 → 降低压缩优先级
      3. minerva研究结果质量差 → KOS降低该来源的信任分
```

**控制律 (Control Law)**:
```
if KOS.domain_quality(domain) < threshold:
    minerva.re_research(domain, depth=+1)
    trust_layer.adjust(domain.source, delta=-0.1)
```

### 3.2 系统论视角：熵管理

**Ashby必需多样性定律**: 控制器的多样性必须匹配被控系统的多样性。

| 被控系统 | 当前控制器 | 多样性匹配？ |
|---------|-----------|:----------:|
| 100+ MCP tools | 4角色RBAC | ❌ 100:4 不匹配 |
| 30 kairon 包 | 无包级控制器 | ❌ 0个控制器 |
| 7 SSOT 域 | 1个SSOT | 🟡 1:7 勉强 |
| 41 Phase 2 任务 | 1个人类 | ❌ 41:1 不匹配 |

**解决**: 
- 工具级RBAC (Phase 2) → 解决MCP tools多样性
- 分层控制器 (Agent-as-Kernel) → 解决包级管理
- KOS辅助决策 (Phase 3) → 解决人类瓶颈

### 3.3 信息论视角：知识熵管理

**香农熵**: 系统知识的不确定性。

```
当前知识熵状态:
  KOS index: 10165→700 → 熵爆炸 (知识丢失)
  gbrain memory: 无压缩 → 熵持续增长
  SharedBrain organs: 4 delegated → 托管熵

目标:
  1. TokenJuicer: 降低输入token的冗余度 (压缩信息)
  2. Memory Tree: 分层压缩历史记忆 (管理时间熵)
  3. trust-layer: 标记信息可靠性 (管理信源熵)
  4. KOS health monitor: 检测知识熵增长 (提前预警)
```

**信息通道容量**:
```
Agora MCP: 当前承载 ~33 tools
  饱和点: ~100 tools (串行路由)
  瓶颈: 每个MCP调用 5-50ms
  解: 并行路由 + 本地缓存 + 批处理
```

### 3.4 图灵机视角：可计算性边界

**系统能计算什么？能做多少步？**

```
当前: minerva 研究 → 有界搜索 (L0-L4)
      没有: 实验 → 验证 → 修正循环

AI-Scientist-v2: 假设 → 实验(train) → 评估 → 修正 → 论文
              可计算但需GPU

omostation: 
  不需要做ML实验 (非核心场景)
  需要: 假设 → 证据搜索 → 逻辑验证 → 修正 → 输出
         (类似科学方法, 但不训练模型)
        
  minerva + BFTS树搜索 = 实现了"假设→搜索→验证→修正"的图灵完备性
```

### 3.5 贝叶斯视角：信念更新

**每个Agent决策应该是贝叶斯更新**:

```python
class BayesianAgent:
    def decide(self, observation, prior_belief):
        # P(hypothesis | evidence) ∝ P(evidence | hypothesis) × P(hypothesis)
        likelihood = self.evaluate_evidence(observation)
        posterior = normalize(likelihood * prior_belief)
        self.belief = posterior  # 更新信念
        return self.act(posterior)

# 系统级贝叶斯:
# 每个Knowledge Card有一组信念:
#   P(correct) = trust_score
#   P(relevant) = relevance_score
#   新证据到达 → 贝叶斯更新 → 新信任度
```

**trust-layer (Phase 2) 就是对贝叶斯先验的系统化实现**。

---

## 四、分层控制面/管理面设计

### 4.1 为什么需要分层控制面

当前每层是包的集合，无统一管理：

```
L2层: kronos, minerva, sophia, ontoderive, ssot, codeanalyze, eu-pricing, token-juicer...
      → 8个包, 各自独立MCP server, 无统一健康检查, 无统一资源管理
      → 如果minerva超载，kronos不会自动降速
      → 包之间版本不一致时，无人检测
```

### 4.2 层控制器设计

```
                    ┌──────────────────┐
                    │  System Controller│  ← 跨层协调
                    │  (meta-control)   │
                    └──┬───┬───┬───┬───┘
                       │   │   │   │
       ┌───────────────┘   │   │   └───────────────┐
       ▼                   ▼   ▼                   ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ L1 Controller│ │ L2 Controller│ │ L3 Controller│ │ L4 Controller│
│ 契约控制面   │ │ 能力控制面   │ │ 协作控制面   │ │ 元控制面     │
│              │ │              │ │              │ │              │
│ Schema健康   │ │ Pipeline健康 │ │ Agent协调    │ │ 系统内省     │
│ 数据质量     │ │ 能力编排     │ │ 协作策略     │ │ 进化治理     │
│ 版本兼容性   │ │ 资源分配     │ │ Agent发现    │ │ 目标对齐     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

### 4.3 各层控制器职责

| 层级 | 控制器 | 监控 | 控制 | 对外接口 |
|------|--------|------|------|---------|
| **L1** | SchemaController | Schema版本, 数据校验通过率 | 拒绝不符合Schema的数据 | `l1.schema.validate(entity)` |
| **L2** | CapabilityController | Pipeline延迟, 吞吐, 错误率 | 动态调整并行度, 降级策略 | `l2.pipeline.status(flow)` |
| **L3** | CollaborationController | Agent负载, 任务队列长度 | 任务路由, Agent负载均衡 | `l3.agent.dispatch(task)` |
| **L4** | MetaController | 系统健康评分, 演进指标 | 全局资源分配, 进化触发 | `l4.system.health()` |
| **I0** | MeshController | MCP延迟, 注册状态 | 路由策略, 熔断恢复 | `i0.mesh.health()` |

### 4.4 控制器的实现形态

**控制器本身是 Agent（不是纯代码）**:

```python
class L2CapabilityController(Agent):
    """L2层控制面Agent"""
    
    tools = [
        "ecos_pipeline_health",     # 监控pipeline
        "forge_model_garden",       # 模型资源
        "ops_health",              # 服务健康
    ]
    
    async def control_loop(self):
        while True:
            # 1. 感知层状态
            health = await self.tool("ecos_pipeline_health")
            
            # 2. 推理是否需要调整
            if health.minerva_latency > health.baseline * 2:
                decision = await self.reason("""
                    minerva延迟高于基线2倍。
                    可能原因: LLM API慢 / 下游服务阻塞 / CPU不足。
                    建议: 先检查LLM API, 然后检查kronos是否占满资源。
                """)
                
            # 3. 执行调整(或推荐给人类)
            if decision.confidence > 0.9:
                await self.act(decision)
            else:
                await self.recommend_to_human(decision)
            
            await asyncio.sleep(30)  # 30秒检查一次
    
    # Communication interface:
    # MCP tool: "l2_controller_status"
    # MCP tool: "l2_controller_adjust"
```

---

## 五、Agent-as-Kernel 模式

### 5.1 从"代码+LLM"到"Agent为内核"

```
传统模式 (当前):
  ┌──────────────────────┐
  │   minerva 研究模块    │
  │                      │
  │  ~3000行Python代码    │
  │  内嵌LLM调用          │
  │  固定管道             │
  │  无自主决策           │
  └──────────────────────┘

Agent-as-Kernel模式 (升级后):
  ┌──────────────────────────────────────┐
  │        Minerva Research Agent        │
  │                                      │
  │  ┌────────┐  ┌──────┐  ┌─────────┐  │
  │  │ Brain  │  │Memory│  │  State   │  │
  │  │ (LLM)  │  │(Pers) │  │(Short)  │  │
  │  └────┬───┘  └──┬───┘  └────┬────┘  │
  │       │         │           │        │
  │  ┌────▼─────────▼───────────▼────┐   │
  │  │        Tool Belt              │   │
  │  │  ┌──────┐ ┌──────┐ ┌──────┐  │   │
  │  │  │search│ │derive│ │write │  │   │
  │  │  │(MCP) │ │(MCP) │ │(MCP) │  │   │
  │  │  └──────┘ └──────┘ └──────┘  │   │
  │  └──────────────────────────────┘   │
  │                                      │
  │  Communication: MCP via Agora        │
  │  Identity: agent-runtime provider   │
  │  Memory: gbrain (persistent)         │
  │  Budget: eu-pricing (cost tracking) │
  └──────────────────────────────────────┘
```

### 5.2 Agent核心接口

```python
class KernelAgent:
    """Agent-as-Kernel 抽象基类"""
    
    # ── 内核组件 ──
    brain: LLM            # 推理引擎 (opena_router via agentmesh)
    memory: MemoryTree    # 持久记忆 (gbrain + memU)
    state: AgentState     # 短期状态 (会话上下文)
    identity: AgentIdentity # A1身份 (identity_bridge)
    
    # ── 工具带 ──
    tools: list[MCPTool]  # 可调用的MCP工具
    
    # ── 通信 ──
    comm: MCPClient       # MCP协议通信 (via Agora)
    
    # ── 控制 ──
    budget: EUBudget      # EU配额 (eu-pricing)
    
    # ── 核心方法 ──
    async def perceive(self, observation) -> Perception
    async def reason(self, perception, goal) -> Plan
    async def act(self, plan) -> ActionResult
    async def learn(self, action_result) -> None
    async def communicate(self, target_agent, message) -> Response
```

### 5.3 哪些模块适合升级为Agent-as-Kernel

| 模块 | 当前形态 | 适合升级? | Agent类型 |
|------|---------|:--------:|---------|
| **minerva** | 管线代码 | ✅✅✅ | Research Agent |
| **kronos** | 抓取管道 | ✅ | Ingestion Agent |
| **ontoderive** | 推导引擎 | ✅✅ | Derivation Agent |
| **KOS** | 索引系统 | ✅✅✅ | Knowledge OS Agent |
| **forge** | 工具治理 | ✅✅ | Governance Agent |
| **iris** | 连接器集合 | ✅ | Integration Agent |
| **agent-runtime** | Agent管理 | ✅✅✅ | Meta Agent (管理其他Agent) |
| **ecos** | 监控 | ✅ | Monitoring Agent |
| **cron-service** | 定时器 | ❌ | 纯基础设施，无需Agent |
| **eidos** | Schema验证 | ❌ | 纯验证，无需Agent |
| **ssot** | 事实源 | ❌ | 纯数据，无需Agent |

### 5.4 Agent通信模式

```
Agent间通信走 MCP 协议:

# Agent A (minerva) 需要 Agent B (DeepCode) 分析代码
response = await self.comm.call(
    target="deepcode/analyze",
    message={
        "type": "code_analysis_request",
        "files": ["kairon/packages/minerva/src/..."],
        "goal": "Identify performance bottlenecks"
    }
)

# Agent间的对话通过 Agora 的 MCP dispatch
# Agent注册通过 agent-registry
# Agent发现通过 L3 Collaboration Controller
```

---

## 六、实施路线建议

### 6.1 优先级

```
Phase 2 内 (优先级排序):
1. Agent Registry + ACP Dispatcher (基础协作) — 2周
2. L2层控制器原型 (能力控制面) — 1周
3. DeepCode集成 (编码Agent示范) — 1周
4. Agent-as-Kernel: minerva升级 (研究Agent示范) — 2周

Phase 3 (进阶):
5. 全层控制器 (L1/L3/L4/I0)
6. Event Bus (NATS)
7. 其余模块Agent-as-Kernel升级
8. pi-acp协议集成
```

### 6.2 新包建议

| 包名 | 层 | 功能 |
|------|:--:|------|
| **acp-core** | I0 | Agent Control Plane: Registry + Dispatcher + Event Bus |
| **layer-controllers** | L4 | 分层控制器实现 (L1-L4 Controller Agents) |
| **agent-kernel** | L1 | Agent基类 (KernelAgent + 核心接口) |
| **deepcode-bridge** | L3 | DeepCode MCP桥接适配器 |
| **pi-acp-bridge** | I0 | pi-acp协议兼容层 (可选) |

### 6.3 不建议现在做的事

- ❌ 全模块升级Agent-as-Kernel (工作量大，先做minerva示范)
- ❌ 引入NATS (先看Agora MCP原生方案够不够用)
- ❌ pi-acp协议 (行业标准未定型，观望)
- ❌ 完全替代现有管线式代码 (Agent和管线可以共存)

---

> **核心洞察**: omostation 不需要变成另一个Agent框架——它已经有一个（agentmesh）。它需要的是 **Agent Control Plane**——让已有的和未来的Agent能够互相发现、通信、协作。然后逐步将核心模块从"代码+LLM"升级为"Agent内核+代码工具"，让Agent成为模块的控制面。L1-L4各层的控制器Agent就是这个升级的第一批产物。
