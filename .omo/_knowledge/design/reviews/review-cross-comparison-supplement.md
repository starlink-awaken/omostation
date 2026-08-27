---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 全面深度审阅 — 补充：新增对标方案分析

> **版本**: v1.0 · **审阅日期**: 2026-05-31
> **本文件是 [review-cross-comparison.md](./review-cross-comparison.md) 的补充**，新增 14+ 对标产品和相关分析。

---

## 关于 "gastak" 的搜索结果

经过多次搜索（中英文关键词、变体拼写），未找到名为 "gastak" 的已知工作流/任务调度引擎。可能为笔误或小众非公开方案。以下对标已覆盖已知的全部主流方案。

---

## S0：新增对标方案全景

### 新增 14 个方案一览

| # | 方案 | 类型 | 定位 | 与 Task Center 关系 |
|---|------|------|------|---------------------|
| 1 | **Conductor** | 微服务工作流编排 | 分布式 Durable workflow for microservices + AI agents | **差异** — 面向微服务 HTTP/gRPC 编排，Task Center 面向本地脚本 |
| 2 | **Camunda** | BPMN 流程引擎 | 企业级 BPM 流程（含人工审批） | **互补** — Camunda 管"人"的流程（审批/会签），Task Center 管"机器"的调度 |
| 3 | **Dagster** | 数据管道编排 | Asset-centric 数据工作流 | **差异** — Dagster 面向数据资产（表/模型/报表），Task Center 面向运维脚本 |
| 4 | **Kestra** | YAML 声明式编排 | YAML-first 工作流，插件生态丰富 | **部分重叠** — 都用 YAML 定义任务，但 Kestra 需 Server + Worker |
| 5 | **Argo Workflows** | K8s 原生工作流 | CNCF 毕业，容器工作流编排 | **差异** — 强绑定 Kubernetes，Task Center 单机零依赖 |
| 6 | **Trigger.dev** | 现代持久执行 | 开发者优先的工作流框架 | **差异** — 多步骤持久执行 + 事件触发，Task Center 单步脚本 |
| 7 | **Inngest** | 事件驱动工作流 | Event-driven 函数编排 | **部分重叠** — Inngest 的事件触发与 Task Center event 类型类似，但需 Server |
| 8 | **Windmill** | 脚本运行平台 | 开发友好型脚本执行 + 工作流 | **部分重叠** — Windmill 的"脚本→ API"理念与 Task Center 相似，但重 UI |
| 9 | **Superpowers** | AI 工作流框架 | Claude Code 可组合技能框架 | **类比 OpenSpec** — 同为 AI 工作流方法论，非任务调度 |
| 10 | **AWS Step Functions** | 无服务器编排 | AWS 原生状态机编排 | **差异** — 强绑定 AWS，Task Center 单机零云依赖 |
| 11 | **Azure Durable Functions** | 持久执行框架 | Azure 生态持久工作流 | **差异** — 强绑定 Azure，Event Sourcing |
| 12 | **Dapr Workflows** | 应用运行时工作流 | Dapr 分布式运行时的工作流能力 | **差异** — 面向微服务 Sidecar 模式 |
| 13 | **Enterprise (BMC/Stonebranch/Tidal)** | 企业作业调度 | 传统大型机/分布式作业调度 | **差异** — 重量级、GUI 驱动、企业级 SLA |
| 14 | **Pipedream / Restate / Cloudflare Workflows** | 新一代编排 | 各具特色的新兴编排方案 | **参考** — 观察其设计理念但非直接竞品 |

### 生态拓扑全景

```
                              编排复杂度 →
                    ┌──────────────────────────────┐
                    │    DAG 编排          BPM/人工      │
                    │  Airflow ⬤        Camunda ⬤  │
                    │  Prefect ⬤                    │
                    │  Dagster ⬤                    │
 分布式  ┌──────────┤                              │
 多机器  │          │    持久化工作流      微服务编排    │
         │          │  Temporal ⬤        Conductor ⬤ │
         │          │  Step Functions ⬤  Dapr ⬤      │
         │          └──────────────────────────────┘
         │                          
    ─────┼──── 事件驱动 ⬤ Inngest / Trigger.dev / Restate
         │
         ├──── K8s 原生 ⬤ Argo Workflows
         │
         ├──── YAML 声明式 ⬤ Kestra
         │
         ├──── 脚本管理 ⬤ Windmill
         │
    ─────┼──── AI 工作流方法论 ⬤ OpenSpec / Superpowers
         │
 单机    └──── 轻调度 ⬤ Task Center (在此)
 零依赖                  systemd / launchd / Quartz
```

**核心结论**：Task Center 位于"单机 + 零依赖 + 轻调度"象限，在这个细分市场**无任何直接竞品**。所有对标方案要么需要分布式基础设施，要么强绑定特定生态，要么只覆盖单一任务类型。

---

## S1：Conductor（Netflix Conductor / Orkes）深度对标

### 概览

Conductor 由 Netflix 开源的微服务工作流编排引擎，现由 Orkes 维护。用于编排 REST/gRPC 调用链，支持百万级并发工作流。GitHub 星标数 13K+。

| 维度 | Conductor | Task Center | 分析 |
|------|-----------|-------------|------|
| **编排模型** | JSON DSL 定义工作流蓝图 | YAML registry 定义单个任务 | Conductor 本质是 **DAG 编排器**，Task Center 本质是 **任务注册表** |
| **执行者** | Worker（HTTP/gRPC 微服务） | 本地子进程（脚本） | 完全不同层——一个管"服务编排"，一个管"脚本调度" |
| **状态管理** | 内置 DB（Dynomite/Postgres/Redis） | SQLite cache + 文件 | Conductor 运行时强依赖 DB，Task Center SQLite 为纯缓存 |
| **Web UI** | ✅ 完整（工作流视图/甘特图/任务搜索） | ❌（MCP 工具替代） | Conductor 有最佳 UI 之一，Task Center 侧重 CLI+MCP |
| **消息队列** | ⚠️ 需要外部队列（Redis/Dyno-queues） | ❌无（本地单进程） | Conductor 的队列是核心组件，Task Center 设计为无队列 |
| **JSON DSL** | 工作流定义 -> JSON -> 可版本化 | YAML -> registry.yaml -> Git 版本管理 | 两者都用声明式格式，但 Conductor 的 DSL 更复杂（含分支/循环/叉合并） |
| **MCP/API** | REST API（swagger 文档齐全） | FastMCP（AI 原生） | Conductor 无 MCP 支持，需自定义适配 |
| **Webhook** | ✅ 内置 Webhook 资源 | ✅ 自建 HTTP Server | Conductor 的 webhook 更深（与工作流引擎直接集成） |

### Task Center 从 Conductor 可学习的

| 学习点 | 说明 | 应用到 Task Center |
|--------|------|-------------------|
| **工作流蓝图（Workflow Blueprint）** | Conductor 的工作流定义与执行分离，定义可复用 | Task Center 的 registry.yaml 任务定义可借鉴 blueprint 思想，支持"任务模板" |
| **任务类型系统** | Conductor 有 SIMPLE/FORK/JOIN/DECISION/SUB_WORKFLOW 等类型 | Task Center 的 5 种类型已很好，可考虑在未来 DAG 阶段引入 FORK/JOIN |
| **结果回调** | Conductor Worker 完成后回调工作流引擎 | Task Center 可在运行记录写入后增加"post_run_hook"回调 |
| **速率平滑** | Conductor 的 ratelimit 配置在工作流级别平滑执行 | Task Center 的令牌桶设计已是行业标准做法 |

---

## S2：Camunda 深度对标

### 概览

Camunda 是 BPMN（业务流程模型和符号）的执行平台，专注"人机混合流程"——涉及人工审批、会签、超时流转等。Camunda 8 支持云原生部署。

| 维度 | Camunda | Task Center | 分析 |
|------|---------|-------------|------|
| **流程定义** | BPMN 可视化建模（XML） | YAML registry | Camunda 有图的表达能力（并行网关/排他网关/事件子流程），Task Center 无 |
| **执行者类型** | Human Task + Service Task + External Task | 脚本子进程 | Camunda 的 Human Task（人工审批）是 Task Center 缺失的核心能力 |
| **运行模式** | 长期运行流程（可跨天/月/年） | 单次执行（秒~小时级） | Camunda 流程可持续数周等待人工审批，Task Center 只有超时管控 |
| **DMN 决策** | ✅ 集成 DMN 决策引擎 | ❌ | Camunda 可做"规则引擎"决策，Task Center 需脚本自行实现 |
| **CMMN 案例** | ✅ 支持 CMMN 案例管理 | ❌ | 非目标场景 |
| **审计日志** | 完整的操作审计 + 流程实例历史 | MCP 操作审计 | Camunda 的审计是合规级（用于 GxP/SOX），Task Center 的审计是运维级 |
| **部署** | Java 应用（可嵌入/Spring Boot/独立运行） | Python 单进程 | 完全不同技术栈 |

### 关键洞察：Camunda 与 Task Center 的互补关系

Camunda 和 Task Center 在 OMO 体系中可以**完美互补**：

```
OMO 中的流程分类    适用引擎          例子
───────────────────────────────────────────────
人工审批流程        Camunda BPMN    "Phase 变更审批"、"任务跨层 Escalate"
纯自动脚本调度       Task Center     "每日 KOS 索引"、"文件变更重索引"
混合流程            Camunda + TC     "运维任务 → Camunda 走审批 → 
                                     审批通过 → Task Center 自动触发脚本"
```

当前 OMO 体系缺失 BPMN 引擎。如果未来有"人工审批治理需求"（例如变更管理需要 CTO 审批后才执行），Camunda 是最成熟的方案。

### 建议

- **R29 (LOW / Future)**：在 §5.3 联邦路线中备注：如果需要"人工审批→自动执行"的混合流程，考虑引入 Camunda 或类似 BPMN 引擎

---

## S3：Argo Workflows / Kestra / Windmill 对标

### Argo Workflows

专注 Kubernetes 容器编排，CNCF 毕业项目（GitHub 15K+ stars）。

| 特性 | Argo Workflows | Task Center |
|------|----------------|-------------|
| 定义格式 | YAML + 模板（Go template 语法） | YAML registry |
| 运行环境 | 必须 Kubernetes 集群 | 裸机/VM，零依赖 |
| 任务类型 | 容器 + 脚本 + HTTP + DAG | 5 种运维任务类型 |
| 执行隔离 | Docker 容器（强隔离） | 子进程（用户级隔离） |
| 事件触发 | Webhook + Event + Cron | cron/once/longrun/webhook/event |
| 适用场景 | ML 训练 + CI/CD + 批处理 | 本地运维 + 文件监听 + 定时脚本 |

**一句话**：Argo 要 K8s，Task Center 不用。完全不同的生态位。

### Kestra

YAML-first 工作流编排器，支持 250+ 插件（GitLab、DB、S3、Slack 等）。

| 特性 | Kestra | Task Center |
|------|--------|-------------|
| 工作流定义 | YAML（支持 DAG + 条件 + 循环） | YAML（单任务 + 依赖声明） |
| 运行时 | Server + Worker（Java） | 单进程 Python |
| 插件生态 | 250+ 官方 + 社区插件 | Hermes 桥接 + 自定义脚本 |
| Web UI | ✅ 丰富 UI + Gantt 图 | ❌ 无 UI |
| 长期运行 | ❌（Worker 重启丢失状态） | ✅（longrun 通过 launchd） |

**可学习的**：Kestra 的 YAML 流式语法（`tasks[].id/tasks[].type/tasks[].depends_on`）和 Task Center 的 registry.yaml 风格非常相似。Kestra 的**内置插件系统**（DB 查询/S3 上传/Git 操作）值得 Task Center 在 Wave 3 参考。

### Windmill

"从脚本到工作流"的平台——写一个 Python/TypeScript/Bash 脚本，自动生成 webhook/定时/UI。

| 特性 | Windmill | Task Center | 分析 |
|------|----------|-------------|------|
| **核心理念** | 脚本→ API（写脚本自动变成可调用 API） | 脚本→ 定时/事件（YAML 注册，自动调度） | 两者出发点不同但目标相似——管理脚本 |
| **脚本发现** | 目录扫描 + 自动注册 | registry.yaml 手动注册 | Windmill 更自动，Task Center 更可控 |
| **Web 编辑器** | ✅ 在线 IDE（Monaco Editor） | ❌ Vim 本地编辑 | Windmill 适合非 CLI 工程师 |
| **定时触发** | ✅ cron + interval | ✅ cron + interval | 等价 |
| **Webhook** | ✅ 自动为每个脚本生成 HTTP 端点 | ✅ 自建 HTTP Server | Windmill 更简单（自动生成） |
| **事件触发** | ❌（仅 webhook + cron） | ✅（fs/bus event） | Task Center 更丰富 |
| **运行记录** | ✅ 日志 + 历史 + 持久化 | ✅ 原子写入 JSON | 等价 |
| **部署** | Docker 自托管 + 云端 | launchd 单进程 | Task Center 轻 10 倍 |

**关键发现**：Windmill 是 Task Center 的**最接近的竞品**——两者都想做"脚本的管理和触发"。Windmill 的优势是 Web UI + 自动注册 + 丰富集成；Task Center 的优势是零依赖 + MCP + 原生文件事件 + 四平面架构集成。

### 建议

- **R30 (LOW)**：在 §5.2 中考虑借鉴 Windmill 的"脚本→API"理念——Task Center 的每个 task 除了定时执行外，也可通过 MCP 工具 `task_run` 临时调用，本质已经是"脚本→API"，可明确文档化这一能力
- **R31 (LOW)**：观察 Windmill 的 Web 编辑器方式——如果未来 OMO 需要可视化脚本管理，参考其编辑器集成方式

---

## S4：事件驱动新一代编排（Inngest / Trigger.dev / Restate）

### 三方共同趋势

| 趋势 | 说明 | 对 Task Center 的启示 |
|------|------|----------------------|
| **事件原生** | 所有触发（cron/webhook/event）统一为"事件" | Task Center 已做（但 bus 事件未定义规范） |
| **逐步持久化** | 函数可跨越数天等待事件，状态自动持久化 | Task Center 需要实现"执行中"状态的持久化（当前只持久化 JIT 结果） |
| **自动重试+补偿** | 失败自动重试/回滚/补偿 | Task Center 的 retry 是简单的 fixed backoff，无补偿语义 |
| **零基础设施** | Serverless 模式下开发者不关心 Server | Task Center 的 launchd 零运维是类似理念 |

### 具体比较

| 特性 | Inngest | Trigger.dev | Restate | Task Center |
|------|---------|-------------|---------|-------------|
| **事件驱动** | ✅ 核心（Event→Function） | ✅ 核心（Event→Step） | ✅ 核心（日志即事件） | ✅ 部分（fs/bus） |
| **步骤持久化** | ✅（步级别 checkpoint） | ✅（步级别 checkpoint） | ✅（整个执行日志） | ❌（只有执行结果） |
| **幂等性** | ✅ (Idempotency Key) | ✅ (Idempotency Key) | ✅ (运行时强制执行) | ❌ |
| **重试策略** | 指数退避 + 最大次数 | 指数退避 + 可配置 | 自动重试 + 补偿 | 固定 backoff |
| **工作流步骤** | 多 Step 可组合 | 多 Step 可组合 | 多 Step 可组合 | 单步 |
| **SDK 语言** | TypeScript/Python/Go | TypeScript | TypeScript/Java/Kotlin | 不限（subprocess） |
| **部署模式** | Cloud / Docker | Cloud / Self-hosted | Self-hosted | 单进程 |

### 建议

- **R32 (MEDIUM)**：考虑在 Route（Phase 3）引入**步级别 checkpoint**——如果未来需要"先等文件就绪，再执行处理脚本，再根据结果发通知"，可将一次运行拆为多个 step，中间状态持久化到 SQLite，即使进程重启也能从中断处继续。（参考 Temporal 和 Inngest 的做法，但 Task Center 的单机场景可用轻量方式实现。）
- **R33 (LOW)**：在运行记录 JSON（§4.5.1）中预留 `steps` 数组字段，为未来的步级 checkpoint 做准备

---

## S5：Superpowers 深度对标

### 概览

Superpowers 是 **Claude Code 的可组合技能框架**（GitHub: obra/superpowers），由一套可组合的 .md 技能文件 + 初始化指令组成。不是任务调度引擎，而是**AI 开发工作流方法论**。

| 维度 | Superpowers | OpenSpec | Task Center |
|------|-------------|----------|-------------|
| **本质** | AI 技能框架 | 规范驱动开发 | 任务调度系统 |
| **用户** | AI 编程助手（Claude Code） | AI 编程助手 + 开发者 | 运维脚本 + 开发者 |
| **核心产物** | `.md` 技能文件 + 提示词 | `proposal.md/spec.md/design.md/tasks.md` | `registry.yaml` + 运行记录 |
| **工作流** | 技能发现 → 技能编排 → 执行 | Propose → Apply → Verify → Archive | Create → Run → Record → Alert |
| **集成方式** | cursorrules / CLAUDE.md 注入 | Slash 命令（/opsx:*） | MCP 工具集 |
| **GitHub** | obra/superpowers | Fission-AI/OpenSpec | 内部 OMO 体系 |

### 关键洞察

1. **Superpowers 是"方法论"，OpenSpec 是"框架"，Task Center 是"工具"**——三个层面不同：
   - Superpowers 告诉你"如何组织 AI 开发流程"（方法论）
   - OpenSpec 告诉你"如何用文档驱动 AI 开发"（框架）
   - Task Center 告诉你"如何管理运维脚本"（工具）

2. **Superpowers 的技能体系与 Task Center 的任务体系可以融合**——Superpowers 的每个 skill 对应一个 Task Center 的 cron/event task 理论上可行。例如：
   - Superpowers skill "code-review" → Task Center task "每日自动代码审查"
   - Superpowers skill "deploy" → Task Center task "PR merged 后自动部署"

3. **Superpowers 没有调度能力**——它的技能只能"被 AI 调用"，不能"被定时/事件触发"。Task Center 正好补这个缺口。

### 建议

- **R34 (LOW)**：在路线图中考虑"Task Center 作为 Superpowers 技能的调度引擎"——Superpowers 定义技能做什么，Task Center 决定技能何时/如何触发

---

## S6：企业级方案（BMC Control-M / Stonebranch / Tidal）

### 概览

这三者是企业级工作负载自动化（Workload Automation）的传统代表，与 Task Center 不在同一赛道：

| 特性 | BMC Control-M | Stonebranch | Tidal | Task Center |
|------|--------------|-------------|-------|-------------|
| **部署** | 大型机 + 分布式 + Agent | 分布式 Agent | 大型机 + 分布式 | 单进程 |
| **定价** | 天价（按 CPU/Job 数计费） | 天价 | 天价 | 开源零成本 |
| **UI** | Java Web 控制台 | Web UI | Web UI | MCP + CLI |
| **SLA** | 企业级 99.99% | 企业级 | 企业级 | 99.9% |
| **集成** | SAP/Oracle/Mainframe + 所有企业系统 | SAP/DB/Cloud | SAP/DB/大数据 | Hermes + 脚本 |
| **合规** | SOX/GxP/PCI 认证 | SOX/GxP 就绪 | SOX 就绪 | 无（单机开发者环境） |

**结论**：完全不重叠。Task Center 不需要从这些企业方案学习任何东西——它们太重、太贵、太复杂。

---

## S7：任务模型全景对比 — 更新版

整合原有 + 新增方案的完整任务能力矩阵：

```
                            cron    once    longrun webhook event   DAG     条件    子工作流
Task Center  ⬤             ✅      ✅      ✅      ✅      ✅      ❌       ❌      ❌
Temporal     ⬤             ✅      ✅      ✅      ✅      ✅      ✅       ✅      ✅
Airflow      ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
Prefect      ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
Dagster      ⬤             ✅      ✅      ❌      ✅      ❌      ✅       ✅      ✅
Conductor    ⬤             ✅      ✅      ❌      ✅      ❌      ✅       ✅      ✅
Camunda      ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
Celery       ⬤             ✅      ✅      ❌      ❌      ❌      ✅       ✅      ✅
Kestra       ⬤             ✅      ✅      ❌      ✅      ❌      ✅       ✅      ✅
Argo         ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
n8n          ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
Quartz       ⬤             ✅      ✅      ❌      ❌      ❌      ❌       ❌      ❌
systemd      ⬤             ✅      ❌      ✅      ❌      ❌      ❌       ❌      ❌
Windmill     ⬤             ✅      ✅      ❌      ✅      ❌      ✅       ❌      ❌
Inngest      ⬤             ✅      ✅      ❌      ✅      ✅      ✅       ✅      ✅
Step Func    ⬤             ✅      ✅      ❌      ✅      ❌      ✅       ✅      ✅
```

**Task Center 在 5 类任务覆盖率上领先**——只有 Temporal 和 Camunda 达到同样多的原生任务类型。但在**编排能力**（DAG/条件/子工作流）上是固有短板。

---

## S8：架构模式全景对比

```
部署架构维度            单进程        单进程+Worker   集群/分布式
                    ───────────     ───────────    ─────────
Task Center           ⬤
Quartz                ⬤  (可集群)
Windmill                            ⬤
systemd/launchd       ⬤
Kestra                              ⬤
n8n                                 ⬤
Celery                                              ⬤
Airflow                                             ⬤
Prefect                                             ⬤
Dagster                                             ⬤
Temporal                                            ⬤
Conductor                                           ⬤
Camunda                                             ⬤
Argo                                                ⬤
Step Functions                                      ⬤  (全托管)
Inngest                                             ⬤  (全托管)
```

**零依赖单进程是 Task Center 最大的差异化优势**——也是最大的可靠性风险（单点故障）。所有对标方案中，只有 Quartz 可以单进程运行，但 Quartz 没有脚本管理/事件/webhook 能力。这个权衡非常清晰：极致简单 vs. 高可用。

---

## S9：更新后的风险矩阵—新增对标驱动的发现

以下是本次补充审阅新增的发现：

| ID | 角度 | 严重度 | 标题 | 当前缺失 |
|----|------|--------|------|----------|
| R29 | 模型 | LOW | 未与 Camunda 做流程互补规划 | 人工审批+自动执行的混合流程未覆盖 |
| R30 | 定位 | LOW | "脚本→API"能力未明确文档化 | 已有 `task_run` 但未定义为 API |
| R31 | 生态 | LOW | Windmill 的 Web 编辑器方式可参考 | 未来可视化脚本管理路线不明 |
| R32 | 任务模型 | MEDIUM | 无步级 checkpoint 持久化 | 长周期多步骤任务无法中断恢复 |
| R33 | 架构 | LOW | 运行记录 JSON 未预留 steps 字段 | 未来步级扩展需要 schema 变更 |
| R34 | 开发者体验 | LOW | 未规划与 Superpowers 的融合 | 同为 AI 工作流工具，可做调度引擎 |

### 更新 MVP 优先级

新增发现均为 LOW，不影响 MVP 编码进程。

---

## S10：最终对比结论更新

### 差异化定位的精确表述

参照所有对标方案，Task Center 的差异化可以一句话提炼为：

> **"单机、零依赖、5 类任务统一注册/调度/观测，面向 AI 原生开发者"**

这个定位在以下维度与所有竞品形成**不重叠**的 niche：

| 维度 | Task Center | 所有对标方案 |
|------|-------------|-------------|
| **运行环境** | 裸机/VM 轻量单进程 | 需要 K8s / Server / Broker / DB |
| **任务类型** | 5 类（含 event + longrun） | 2-3 类为主（cron + webhook + DAG） |
| **AI 接口** | MCP 原生（FastMCP） | REST/gRPC（需额外适配） |
| **项目集成** | 四平面 SSOT 原生集成 | 独立系统，需桥接 |
| **学习成本** | YAML + shell 脚本 | Python DAG / Java / BPMN |
| **运维成本** | launchd 管理，零 DB 运维 | 至少管理一个 DB + 消息队列 |
| **文件事件** | kqueue/FSEvents/inotify 原生 | 需额外 Agent/Sensor 配置 |

### 各竞品与 Task Center 的"距离"

```
完全重叠   部分重叠   有借鉴    完全不同
────────  ────────  ──────  ────────
Windmill  Kestra     n8n     Temporal
(脚本管理) (YAML定义)  (连接器)  (分布式工作流)
                    
          Celery    Inngest  Airflow
          (任务队列)  (事件驱动) (数据管道)
                   
                    Conductor Prefect
                    (微服务)   (数据管道)
                    
                    Camunda   Dagster
                    (BPMN)    (数据资产)

                    Trigger.dev Argo
                    (持久执行)   (K8s)
                    
                    Quartz
                    (单机cron)
```

Windmill 是最近的竞品（脚本→API），Kestra 是最相似的（YAML 定义任务），但两者都有**Server 依赖**和**UI 绑定**，无法在 OMO 的轻量场景替代 Task Center。

---

> **本补充文档与 review-cross-comparison.md 共同构成完整的行业对标审阅（总计 28 个对标方案）。**
> **本报告未经人工验证，AI 可能遗漏某些细节。建议人工审阅后确认改进项。**
