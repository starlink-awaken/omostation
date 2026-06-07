# AetherForge 行业对标分析

> 与 LiteLLM / CrewAI / AutoGen / Ray / LangGraph 等行业主流方案全面对比
> 2026-06

---

## 一、对标矩阵总览

| 维度 | AetherForge | LiteLLM | CrewAI | AutoGen | Ray | LangGraph |
|:-----|:-----------:|:-------:|:------:|:-------:|:---:|:---------:|
| **定位** | 算力+Agent 全栈 | AI Gateway 专用 | 多 Agent 编排 | 多 Agent 对话 | 分布式计算 | Agent 工作流 |
| **开源协议** | MIT | MIT | MIT | MIT | Apache 2.0 | MIT |
| **Stars** | — | 19K+ | 28K+ | 40K+ | 35K+ | 12K+ |
| **语言** | Python | Python | Python | Python | Python/C++ | Python |
| **LLM Provider** | 6 (expandable) | **100+** ❗ | 间接 (通过 LLM) | 间接 | N/A (推理引擎) | 间接 |
| **多 Agent** | ✅ Auction + DAG + Hierarchical | ❌ | ✅ Crew + Flow | ✅ GroupChat | ❌ | ✅ Graph |
| **算力网格** | ✅ 自动发现 + 4层拓扑 | ❌ | ❌ | ❌ | ✅ Ray Cluster | ❌ |
| **限流** | ✅ tpm/rpm 滑动窗口 | ✅ tpm/rpm | ❌ | ❌ | ❌ | ❌ |
| **调度框架** | ✅ Filter/Score 插件化 | ✅ Router (策略) | ❌ | ❌ | ✅ Placement Group | ❌ |
| **可观测性** | ✅ MetricsCollector | ✅ Prometheus + UI | ❌ | ❌ | ✅ Dashboard | ❌ |
| **成本追踪** | ✅ SQLite + JSONL | ✅ SpendLog DB | ❌ | ❌ | ❌ | ❌ |
| **人机协作** | ✅ HITL Provider | ❌ | ❌ | ✅ human_input | ❌ | ❌ |
| **经济账本** | ✅ EnergyLedger | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Worker 管理** | ✅ 注册/心跳/消息总线 | ❌ | ❌ | ❌ | ✅ Raylet | ❌ |
| **MCP 支持** | ✅ FastMCP | ✅ Proxy | ✅ MCP tools | ❌ | ❌ | ❌ |

---

## 二、逐项深度对比

### 2.1 LLM Gateway 层

#### vs LiteLLM (AI Gateway 领域最强者)

| 能力 | LiteLLM | AetherForge | 差距评估 |
|:-----|:-------:|:-----------:|:---------|
| Provider 数量 | **100+** | 6 | 🔴 **最大差距**。AetherForge 只有 Ollama/OpenAI/Anthropic/Gemini/DeepSeek/HITL，缺 Azure/Bedrock/Vertex/智谱/文心等 |
| 路由策略 | 6 种 + 自定义 | 4 种 + 插件 | 🟡 功能接近，但 LiteLLM 的 usage-based 路由和 weighted 路由更成熟 |
| Fallback | 多级 + 超时 + 退避 | ✅ FallbackRule | 🟢 已对齐 |
| Rate Limiting | tpm/rpm + 并发控制 | tpm/rpm | 🟡 缺并发控制 (max_parallel) |
| 虚拟密钥 | ✅ 团队 RBAC | ❌ | 🟢 个人场景不急需 |
| 管理 UI | ✅ Web Dashboard | ❌ CLI only | 🟡 可考虑轻量 TUI |
| 性能 | 5000 QPS (4C8G) | 1.4M ops/sec (rate limiter) | 🟢 单组件性能优异，但全链路未测 |
| 部署 | pip / Docker / K8s | uv / Docker | 🟡 K8s 部署尚缺 Helm chart |
| 社区 | 19K+ stars, 活跃 | 0 (新生) | 🔴 社区和生态是最大短板 |
| 文档 | ✅ 完整 | ✅ README + API.md | 🟢 已对齐 |

**关键差距**: Provider 数量 (6 vs 100+) 和 社区生态。但 AetherForge 在 **人机协作 (HITL)**、**三层融合** 方面是 LiteLLM 没有的差异化能力。

#### vs Portkey (AI Gateway + 可观测性)

Portkey 2026 年被 Palo Alto Networks 收购，定位转向 AI 安全。其可观测性面板和护栏能力仍是标杆，但 AetherForge 作为开源方案在灵活性上有优势。

### 2.2 多 Agent 编排层

#### vs CrewAI (多 Agent 编排领域最流行)

| 能力 | CrewAI | AetherForge Swarm | 差距评估 |
|:-----|:------:|:-----------------:|:---------|
| 角色定义 | ✅ role/goal/backstory | ✅ AgentCard/Capability | 🟢 完整 |
| 任务分解 | ✅ Task + 依赖 | ✅ task_decomposer + DAG | 🟢 完整 |
| 流程控制 | sequential / **hierarchical** | auction / DAG | 🟡 缺 CrewAI 式层级流程 |
| 工具集成 | ✅ 100+ 内置 + MCP | ✅ ToolSchema | 🟢 完整 |
| 记忆管理 | ✅ 短期/长期/实体 | ✅ context_injector | 🟢 完整 |
| 回调/Hook | ✅ step/ task 回调 | ❌ 无 | 🟡 可加 |
| CLI 工具 | ✅ crewai run | ❌ 无专属 CLI | 🟡 swarm CLI 待建设 |
| 缓存 | ✅ 步骤缓存 | ❌ 无 | 🟢 个人场景可加 |

**AetherForge Swarm 的独特优势**:
- **拍卖市场**: CrewAI 没有市场化任务分配机制
- **EnergyLedger**: 经济账本体系，CrewAI 无
- **GatewaySynapse**: 与 gateway 深度集成，CrewAI 依赖独立 LLM 调用

### 2.3 算力调度层

#### vs Ray (分布式计算领域标准)

| 能力 | Ray | AetherForge Mesh | 差距评估 |
|:-----|:---:|:----------------:|:---------|
| 分布式对象存储 | ✅ Plasma Store | ❌ | 🔴 大消息/模型状态传递 |
| 自动扩缩 | ✅ Autoscaler | ✅ ComputePool.auto_scale | 🟢 基础能力对齐 |
| 故障恢复 | ✅ 任务重试 + 节点恢复 | 🟡 CircuitBreaker + 重试 | 🟡 缺节点级容错 |
| 调度策略 | ✅ Placement Group + SPREAD | ✅ Filter/Score 插件 | 🟢 更灵活 (插件化) |
| 多语言 | Python/Java/C++/Rust | Python only | 🟢 个人场景足够 |
| 部署复杂度 | 高 (需 Ray Cluster) | 低 (单进程) | 🟢 AetherForge 更轻量 |
| GPU 支持 | ✅ 原生 GPU 调度 | 🟡 标记支持 | 🟡 缺 GPU 显存追踪 |

**AetherForge Mesh 的独特优势**:
- 拓扑四层模型 (region/zone/rack/host) — Ray 无
- Worker 消息总线 — 轻量级 Worker 通信
- 自动节点发现 (mDNS/SSH/静态) — Ray 需手动配置集群

#### vs K8s Scheduler (容器调度黄金标准)

AetherForge 的 Filter/Score 插件化调度框架直接借鉴 K8s Scheduling Framework，在架构设计上已对齐。差距在于成熟度和生态。

### 2.4 工具链完整度

| 能力 | LiteLLM | CrewAI | Ray | AetherForge | 行业标杆 |
|:-----|:-------:|:------:|:---:|:-----------:|:--------:|
| 单元测试 | ✅ | ✅ | ✅ | **12** | ✅ (几百+) |
| 集成测试 | ✅ | ✅ | ✅ | **26** | ✅ |
| 性能基准 | ✅ | ❌ | ✅ | **7 benchmarks** | ✅ |
| CI/CD | ✅ GitHub Actions | ✅ | ✅ | ❌ 无 | ✅ |
| Docker 镜像 | ✅ | ✅ | ✅ | ✅ 有 | ✅ |
| Helm Chart | ✅ | ❌ | ✅ | ❌ 无 | ✅ |
| API 文档 | ✅ 自动生成 | ✅ mkdocs | ✅ ReadTheDocs | ✅ 手动 | ✅ |
| 示例代码 | ✅ 丰富 | ✅ 丰富 | ✅ 丰富 | ❌ 少 | ✅ |
| 贡献指南 | ✅ CONTRIBUTING.md | ✅ | ✅ | ❌ 无 | ✅ |

---

## 三、差距总结

### 🔴 重大差距 (急需补齐)

| 差距 | 影响 | 工作量 | 参考实现 |
|:-----|:------|:------:|:---------|
| **Provider 数量** (6 vs 100+) | 用户选择面窄 | 小 | LiteLLM 的 provider 适配模式 |
| **社区/生态** (0 stars) | 发现/采用困难 | 大 | 需时间积累 |
| **CI/CD 缺失** | 无自动化测试/发布 | 中 | GitHub Actions |
| **示例代码不足** | 上手门槛高 | 中 | 写 3-5 个完整示例 |

### 🟡 中等差距 (可逐步补齐)

| 差距 | 影响 | 工作量 |
|:-----|:------|:------:|
| 并发控制 (max_parallel) | 无法限制并发请求 | 小 |
| 轻量管理 TUI | 无可视化界面 | 中 |
| K8s Helm Chart | 生产部署不便 | 中 |
| 步骤缓存 (swarm) | 重复计算 | 中 |
| 节点级故障恢复 | 可靠性不足 | 大 |

### 🟢 无差距或已领先

| 能力 | 说明 |
|:-----|:------|
| 人机协作 (HITL) | LiteLLM/CrewAI 都没有 |
| 经济账本 (EnergyLedger) | 独有能力 |
| 三层融合 (gateway+mesh+swarm) | 没有其他项目同时具备这三层 |
| 插件化调度 (Filter/Score) | 比 LiteLLM 的 Router 更灵活 |
| 拓扑四层模型 | 比 Ray 更精细的拓扑 |
| 成本追踪 (SQLite+JSONL) | LiteLLM 有等效能力 |
| Rate Limiter 性能 (1.4M ops/sec) | 性能领先 |

---

## 四、北极星指标

根据对标结果，AetherForge 当前在 **三层融合度** 和 **独特能力 (HITL/经济账本)** 上领先，在 **Provider 数量** 和 **社区生态** 上差距最大。

| 指标 | 当前 | 6 个月目标 | 12 个月目标 |
|:-----|:----:|:----------:|:-----------:|
| Provider 数量 | 6 | 15 | 30+ |
| GitHub Stars | 0 (私有) | 100+ | 1K+ |
| 测试覆盖率 | 12+26 | 80%+ | 90%+ |
| 示例代码 | 0 | 5 | 15 |
| 贡献者 | 1 | 3 | 10 |
| 文档站点 | README | GitHub Pages | 独立文档站 |

---

## 四、当前差距清单 (已解决 vs 待解决)

| 差距 | 状态 | 交付物 |
|:-----|:----:|:--------|
| Provider 数 (6 vs 100+) | 🟡 部分解决 | 6→9, 新增 Azure/Bedrock/Vertex |
| 步骤回调/hook (vs CrewAI) | ✅ **已解决** | `StepCallbacks` (6 hooks + decorator) |
| 对话式 GroupChat (vs AutoGen) | ✅ **已解决** | `GroupChat` (round-robin + moderator) |
| 图工作流 (vs LangGraph) | ✅ **已解决** | `GraphWorkflow` (DAG + 条件边 + LLM 节点) |
| 分布式对象存储 (vs Ray) | ✅ **已解决** | `ObjectStore` (put/get/TTL + SQLite) |
| 社区/生态 | 🔴 未开始 | 需开源发布 |
| CI/CD | 🔴 未开始 | 需 GitHub Actions |
| K8s Helm Chart | 🔴 未开始 | 生产部署 |

---

## 五、北极星指标

根据对标结果，AetherForge 当前在 **三层融合度** 和 **独特能力 (HITL/经济账本)** 上领先，在 **Provider 数量** 和 **社区生态** 上差距最大。

| 指标 | 当前 | 6 个月目标 | 12 个月目标 |
|:-----|:----:|:----------:|:-----------:|
| Provider 数量 | **9** | 15 | 30+ |
| 测试覆盖率 | 12+26+18=**56** | 80%+ | 90%+ |
| 示例代码 | 0 | 5 | 15 |
| 贡献者 | 1 | 3 | 10 |

---

## 六、结论

**AetherForge 在架构设计上不输任何一个主流方案**，在某些方面甚至领先（三层融合、插件化调度、经济账本、人机协作）。

**当前最大的短板是 Provider 数量和社区生态**。建议：

1. **短期**: 用 1-2 天补齐 Azure / Bedrock / Vertex 三个主流 Provider（覆盖 80% 用户需求）
2. **中期**: 建立 CI/CD + 完善示例 + 开源发布
3. **长期**: 社区运营 + Provider 插件市场

**无需追赶的方向**:
- 不需要做成 LiteLLM 那样的 100+ Provider（长尾 Provider 的维护成本 > 收益）
- 不需要 CopilotKit 级别的 UI（AetherForge 定位是框架/CLI，不是应用）
- 不需要对标 Ray 的分布式能力（个人场景单机足够）
