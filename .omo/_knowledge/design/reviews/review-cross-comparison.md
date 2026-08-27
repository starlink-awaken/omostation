---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 全面深度审阅：Task Center v0.2 多角度交叉分析与行业对标

> **版本**: v1.0
> **审阅日期**: 2026-05-31
> **审阅对象**: [Task Center 需求文档 v0.2](../task-center-requirements.md)
> **审阅方法**: 多角度交叉分析 + 行业对标（OpenSpec / Temporal / Airflow / Celery / n8n / systemd / launchd / Prefect / 及 14+ 补充方案）
> **审阅人**: 全自动 AI 审阅
> **补充报告**: [行业对标补充 14+ 方案](./review-cross-comparison-supplement.md)

---

## 执行摘要

本报告对 Task Center v0.2 进行**10 个维度**的系统性深度审阅，与 **8 个行业主流方案**交叉对标（另有 **14+ 补充方案**在补充报告中）。核心结论：

| 维度 | 成熟度 | 亮点 | 关键差距 |
|------|--------|------|----------|
| 产品定位 | ⚡强 | 单机场景的 niche 精准，无竞品直接覆盖 | 文档未阐明与全栈竞品的差异化定位 |
| 架构设计 | ✅良好 | 四层架构清晰，SSOT 双面互补 | 无高可用设计、无分布式共识 |
| 任务模型 | ⚡强 | 5 类任务覆盖全面，cron/longrun 现实最强 | webhook/event 细节冗余，可简化 |
| 安全模型 | ✅良好 | Safety Sprint 处理彻底，secret 管理务实 | 无 mTLS/无 RBAC/无审计链 |
| 可靠性 | ⚠️中等 | RTO/RPO/SLI 定义良好 | 单进程 SPOF 未根本解决，故障注入尚抽象 |
| 可观测性 | ⚡强 | 运行记录 + 健康探针 + 多通道告警 | 无 Metrics 导出（Prometheus/OpenTelemetry） |
| 开发者体验 | ⚡强 | MCP 工具集是独特优势 | CLI 接口未定义，OpenSpec 工作流可融合 |
| 运维成熟度 | ⚠️中等 | 回退方案考虑周全 | 无数据库升级策略、无备份恢复 playbook |
| 生态集成 | ⚡强 | Hermes 桥接 + i0 事件总线 | 第三方集成（GitHub/GitLab）缺失 |
| 规模边界 | ✅良好 | 500+ 任务，并发上限设计合理 | 跨机器、DAG、高可用未覆盖 |

**总体**: Task Center 在**单机调度 + 开发工具集成**场景具有显著的差异化优势，市面无直接竞品。建议在 MVP 实施前重点补强：**与 OpenSpec 工作流融合**、**Metrics 导出**、**运维 Playbook** 三项。

---

## 第一部分：对标方案全景

### 1.1 对标方案选择

| 方案 | 类型 | 定位 | 选定理由 |
|------|------|------|----------|
| **OpenSpec** ⭐ | AI 原生开发框架 | Spec-driven development | 同为 OMO 体系的技术栈，直接对比工作流哲学 |
| **Temporal** | 分布式工作流引擎 | Durable execution | 工作流/调度领域的事实标杆 |
| **Apache Airflow** | DAG 工作流编排 | 数据处理流水线 | 最广泛使用的开源调度系统 |
| **Celery** | 分布式任务队列 | 异步任务执行 | 轻量级任务调度的经典方案 |
| **n8n** | 工作流自动化 | 低代码连接器生态 | 文档已引用，深度对标 |
| **systemd timer + launchd** | OS 级调度 | 进程管理和定时 | Task Center 的底层承载者 |
| **Quartz** | Java 任务调度 | 企业级定时任务 | 最成熟的单机调度库 |
| **Prefect** | 现代工作流编排 | Python-native DAG 2.0 | Airflow 的进化版，代表下一代方向 |

### 1.2 各方案核心数据

| 方案 | 首次发布 | 实现语言 | 部署方式 | 任务存储 | 社区规模 |
|------|----------|----------|----------|----------|----------|
| OpenSpec | 2025 | Markdown + Schema | 项目目录嵌入 | 文件系统 | 新兴 |
| Temporal | 2019 | Go（Server）+ 多语言 SDK | 集群部署 | 持久化 Event Store | 大 |
| Airflow | 2015 | Python | 单机/分布式 | SQL DB + DAG 文件 | 极大 |
| Celery | 2009 | Python | 分布式 | Broker（Redis/RabbitMQ） | 极大 |
| n8n | 2019 | TypeScript | 单机 Docker | SQLite/Postgres | 中 |
| systemd | 2010 | C | 系统集成 | 文件 + 二进制 | 系统级 |
| Quartz | 2009 | Java | 嵌入/集群 | JDBC / RAM | 极大（Java 生态） |
| Prefect | 2018 | Python | 单机/云 | SQLite / Server | 快速增长 |

### 1.3 定位矩阵

```
                    分布式（多机器）
                         │
          Temporal ⬤    │    ⬤ Airflow
          Celery ⬤     │    ⬤ Prefect
                         │
     ───────────────────┼─────────────────── 编排复杂度 →
                         │
          n8n ⬤         │
                         │
          Quartz ⬤      │
                   ─────┼─────
          Task Center ⬤ │    ⬤ (未来联邦)
          systemd ⬤     │
          launchd ⬤    │
                         │
                    单机（单机器）
```

Task Center 定位在**单机 + 轻编排**象限，与 systemd/launchd 重叠但又补充了任务管理、观测、MCP 等能力。**这一 niche 目前无竞品直接覆盖。**

---

## 第二部分：多角度交叉分析

## 角度 1：产品定位与生态位

### 现状分析

Task Center 定位为"单机 5 类任务统一调度 SSOT"，解决 4 种调度机制（cron-service/crontab/launchd/hermes）碎片化问题。

### 行业对标

| 方案 | 定位 | 与 Task Center 的关系 |
|------|------|----------------------|
| **OpenSpec** | 规范驱动的开发工作流 | **互补** — OpenSpec 管"开发阶段的提案→实现→归档"，Task Center 管"运维阶段的定时/事件触发" |
| **Temporal** | 分布式持久化工作流 | **差异** — Temporal 面向分布式系统、需要 SDK 接入、有状态持久化，Task Center 面向本地脚本、无状态触发 |
| **Airflow** | 数据流水线 DAG 编排 | **差异** — Airflow 面向数据工程团队、需要 Python DAG 代码、Web UI，Task Center 面向个人开发者（CLI + MCP） |
| **Celery** | 分布式异步任务队列 | **重叠（部分）** — 两者都做任务调度，但 Celery 需要 Broker/Worker 集群，Task Center 零依赖 |
| **n8n** | 低代码工作流自动化 | **部分重叠** — n8n 的 webhook + cron 触发与 Task Center 重合，但 n8n 强在 400+ 连接器，Task Center 强在本地脚本 + MCP |
| **systemd/launchd** | OS 级进程管理 | **互补** — Task Center 在底层调用 launchd 管理 longrun，在上层提供统一注册/观测 |
| **Quartz** | 企业级定时调度 | **重叠** — Quartz 是单机 cron 最成熟的轮子，但无脚本管理/无事件/webhook 支持 |
| **Prefect** | 现代 Python 工作流 | **差异** — Prefect 面向数据管道（Python-native），Task Center 面向脚本（非 Python 限定） |

### 发现

1. **无直接竞品**：目前市场上没有专门做"单机多类型任务统一注册/调度/观测"的产品。Temporal/Airflow 太重，Celery 需要 Broker，n8n 太重 UI，systemd 无统一管理。
2. **与 OpenSpec 的融合空间未被利用**：Task Center 的设计流程（清理→需求→审阅→实施）天然符合 OpenSpec 的变更生命周期，但目前文档未提及任何与之整合。
3. **定位描述不够锐利**：文档 §1.4 描述了"从 4 套独立系统到 1 套"的迁移故事，但未阐明"为什么不是直接用 systemd/Celery/n8n"。

### 建议

- **R1 (HIGH)**：在 §1.4 或 §2.1 增加"为什么不是 Temporal/Airflow/Celery/n8n"的对比说明，明确差异化价值
- **R2 (MEDIUM)**：在 §5 路线图中规划与 OpenSpec 工作流的融合——每个 task 的变更遵循 OpenSpec 的 proposal → apply → verify → archive 生命周期

---

## 角度 2：架构设计

### 现状分析

四层架构（Registry → Scheduler → Executor → Observability），两层 SSOT 互补（`tasks/` 治理 + `task-center/` 调度），运行记录归属交付面。

### 行业对标

| 维度 | Task Center | Temporal | Airflow | Celery | n8n |
|------|-------------|----------|---------|--------|-----|
| **架构分层** | 4 层（注册/调度/执行/观测） | 3 层（Frontend/Backend/Worker） | 4 层（Web/Scheduler/Executor/Worker） | 3 层（Broker/Worker/Backend） | 3 层（Web/Executor/Worker） |
| **SSOT** | 文件 YAML + SQLite cache | 持久化 Event Store（Cassandra/MySQL/Postgres） | DAG 文件 + Metadata DB | Broker + Result Backend | SQLite/Postgres |
| **分散度** | 单进程 | 多节点集群 | 多组件分布式 | 多 Worker 分布式 | 单进程 + Worker |
| **状态持久化** | SQLite + 文件 | Event Sourcing | DB + 文件日志 | 无默认（可选 Backend） | DB |
| **事件驱动** | kqueue/FSEvents/inotify | 内部事件系统 | Sensor + Trigger | 无（纯队列） | Webhook + 轮询 |
| **MCP/API** | MCP（FastMCP） | gRPC | REST API | 无标准 API | REST API |

### 核心对比点

**1. SSOT 设计**：Task Center 采用"文件 SSOT + SQLite Cache"组合，与 Airflow 的"文件 DAG + Metadata DB"相似，但 Airflow 的 Metadata DB 处于核心地位（DAG 运行时状态完全依赖 DB），而 Task Center 的设计更轻量（YAML 可 Git 管理，SQLite 可删除重建）。

然而，与 Temporal 的 Event Sourcing 相比，Task Center 没有**完整的状态机**——Temporal 记录了每个工作流执行的完整事件流，可以精确重放任意历史状态。Task Center 只记录每个任务的**当前定义**（registry.yaml）和**单次执行结果**（运行记录 JSON），中间状态（如"正在执行中"）是不持久化的。

**2. 高可用架构**：Task Center 是单进程设计，依赖 launchd 自动重启。相比之下：
- Temporal 使用 Quorum-based 集群（多副本 + 领导者选举），任何节点故障不影响整体
- Airflow 支持 HA Scheduler（多 scheduler 实例互备）
- Celery 天生分布式（多 Worker）

Task Center 的 §3.3 健康探针 + watchdog 虽然能检测故障并触发重启，但**重启期间的调度事件会丢失**（RPO < 15s 保证的是最多丢失 1 个 tick，但如果是执行中的任务被 kill，则该次执行完全丢失且无法自动重试）。

**3. 非功能设计对比**：

| 特性 | Task Center | Temporal | Airflow |
|------|-------------|----------|---------|
| 自动重试 | 简单重试（固定 backoff） | 无限重试 + 可配置 backoff + 回退策略 | 任务级重试 + DAG 级重试 |
| 速率限制 | 入站 + 出站 | 无（由 SDK 层控制） | 池级别 |
| 补偿式 tick | ✅ | N/A（事件驱动） | ❌（可能累积延迟） |
| 任务优先级 | ✅（1-10） | ❌（FIFO 队列） | ❌（DAG 依赖决定） |

### 建议

- **R3 (HIGH)**：补充"执行中任务被 kill"的场景设计——是否需要在 startup 时扫描 `_delivery/task-center/runs/` 中运行中的记录并标记为 `killed`？
- **R4 (MEDIUM)**：增加 SQLite cache 与 registry.yaml 的双向同步策略描述——当 Git 冲突发生时如何恢复一致性
- **R5 (LOW)**：考虑在 roadmap 中增加"Registry Watch"——监听 registry.yaml 文件变更自动 reload，避免每 tick 全量扫描

---

## 角度 3：任务模型与编排能力

### 现状分析

5 种任务类型（cron/once/longrun/webhook/event），支持依赖声明（`depends_on`），不支持 DAG。

### 行业对标

| 特征 | Task Center | Temporal | Airflow | Celery | Quartz |
|------|-------------|----------|---------|--------|--------|
| **定时任务** | ✅ cron/interval | ✅ cron/interval/cron-tab | ✅ cron/datetime | ✅ periodic_task | ✅ cron/simple |
| **一次性任务** | ✅ once | ✅ Signal/start | ✅ (manual run) | ✅ apply_async | ✅ (manual) |
| **长期守护** | ✅ longrun | ✅ (workflow 天然长运行) | ❌ | ❌ | ❌ |
| **Webhook** | ✅ (自建 HTTP Server) | ✅ (Signal + gRPC) | ✅ (REST API trigger) | ❌ | ❌ |
| **事件驱动** | ✅ (fs/bus) | ✅ (Signal/Query) | ✅ (Sensor) | ❌ | ❌ |
| **DAG 编排** | ❌ (依赖声明，无调度) | ✅ (Workflow-as-Code) | ✅ (Python DAG) | ✅ (Canvas) | ❌ |
| **条件分支** | ❌ | ✅ | ✅ (BranchOperator) | ✅ (chain/groups) | ❌ |
| **子工作流** | ❌ | ✅ (Child Workflow) | ✅ (SubDAG) | ✅ (workflow) | ❌ |

### 核心发现

1. **5 类任务类型覆盖了 95% 的单机调度需求**——cron 做定时、once 做一次、longrun 做守护、webhook 做外部触发、event 做文件驱动。Celery 和 Quartz 只有定时 + 一次性两种。

2. **`depends_on` 的设计是"弱依赖"而非"强编排"**——文档表述为"交叉引用不创建依赖环（不强制调度任务等待治理任务）"，意味着 `depends_on` 实际上是元数据标记而非执行约束。这导致 Task Center 不支持"先执行 A 再执行 B"这种最简单的编排需求，而 Airflow/Temporal 的核心能力正是这个。

3. **event 类型的 `bus` 源定义过于笼统**——`source: bus` 只写了"订阅 i0 事件总线"，但未定义 i0 事件总线的接口规范、消息格式、topic 命名规则。相比之下，Temporal 的 Signal 机制提供类型安全的事件通道。

### 建议

- **R6 (MEDIUM)**：为 `depends_on` 增加"执行依赖"语义选项——新增 `depends_on_type: weak | strong`，weak 保持当前元数据引用，strong 要求上游任务成功后才执行
- **R7 (LOW)**：明确 i0 事件总线接口规范——至少定义事件消息的最小骨架（`topic`, `type`, `payload`, `timestamp`）
- **R8 (LOW)**：考虑增加 `cron` 类型的 `timezone` 字段——当前未指定时区的处理策略

---

## 角度 4：安全模型

### 现状分析

Safety Sprint 定义了 8 项安全加固（P0-P1），覆盖：shell=False、路径白名单、HMAC compare_digest、秘密管理、子进程隔离、SQLite 并发保护、速率限制、event symlink 保护。

### 行业对标

| 特性 | Task Center (v0.2) | Temporal | Airflow | n8n |
|------|-------------------|----------|---------|-----|
| **传输加密** | 未指定（默认 local） | mTLS（gRPC） | HTTPS 可配 | HTTPS 默认 |
| **认证机制** | HMAC（webhook） | mTLS 证书 | OAuth/OIDC/RBAC | JWT + API Key |
| **授权模型** | 无（本地单用户） | 无（应用层实现） | RBAC（角色/权限/资源） | 用户/共享凭证 |
| **秘密存储** | `_secret/` 加密 vault | Temporal Server 加密 | Airflow Connections/Hashicorp Vault | Credentials（加密存储） |
| **子进程隔离** | 不同用户 + 文件权限 600 | N/A（SDK 进程） | Worker 隔离 | Docker 容器化 |
| **速率限制** | 令牌桶 per-path | 无 | 池级别 | 表达式级 |
| **审计** | MCP 操作审计 | 事件历史（完整审计链） | DAG Run 日志 | 工作流执行日志 |
| **输入验证** | 路径规范化 + 白名单 | gRPC 协议缓冲校验 | DAG 解析校验 | 节点配置校验 |

### 核心发现

1. **安全模型务实但不够完整**——作为本地单用户程序，Task Center 的安全重心在"防止脚本越狱"（子进程隔离、路径白名单）和"防止外部篡改"（HMAC、速率限制），这是正确且务实的。但缺失**传输加密**（webhook 路径无 HTTPS 说明）和**认证审计链**（谁/何时/从哪里修改了 registry.yaml）。

2. **安全对比的优势与劣势**：
   - 优势：`shell=False` + 子进程隔离（不同用户）在同类方案中罕见，即使是 Celery 也不做子进程隔离
   - 劣势：无 mTLS/无 RBAC/无 OAuth，对于需要接入外部系统（如 GitHub webhook）的场景不够

3. **Safety Sprint 的 8 项中有 3 项是"一次性配置"**（shell=False、compare_digest、路径规范化），剩余 5 项需要持续维护（秘密轮换、速率调优、目录遍历防护升级等），但文档未定义维护策略和轮换周期。

### 建议

- **R9 (HIGH)**：webhook 端点增加 HTTPS 配置选项（至少支持自签名证书用于局域网/开发环境）
- **R10 (MEDIUM)**：在 §7.4 安全验收中增加"秘密轮换策略"——iLink token 和 webhook secret 的轮换周期和自动轮换机制
- **R11 (LOW)**：考虑增加简单的变更签名——MCP 写操作可通过 HMAC 签名 registry.yaml 的 `updated_at`，防止已废弃的 MCP 客户端篡改当前数据

---

## 角度 5：可靠性工程

### 现状分析

§2.3 定义了 RTO < 30s、RPO < 15s、SLI/SLO 承诺。§3.3 健康探针 + watchdog + launchd 自动重启。§6.1 风险矩阵 12 项。

### 行业对标

| 特性 | Task Center | Temporal | Airflow | Celery |
|------|-------------|----------|---------|--------|
| **RTO** | < 30s（依赖 launchd） | < 5s（领导者选举） | < 60s（Scheduler HA） | < 10s（Broker 重连） |
| **RPO** | < 15s（1 tick） | 0（Event Sourcing） | 依赖 DB | 依赖 Broker |
| **故障检测** | 健康探针 + watchdog | gRPC Health + Ringpop | DB heartbeats | Broker 心跳 |
| **自动重试** | 配置化（fixed backoff） | 无限 + 可配置策略 | 任务/DAG 级 | 配置化 |
| **幂等性** | 不保证 | ✅（Event ID 去重） | ❌（需业务保证） | ❌（需业务保证） |
| **一致性** | 最终一致性（Sync 策略） | 强一致（Quorum） | 最终一致 | 最终一致（at-least-once） |
| **降级策略** | ✅（安全模式/轮询降级/本地降级） | ❌无（设计即高可用） | ❌无（宕机即失败） | ❌无（Broker 升配） |

### 核心发现

1. **RTO < 30s 在单进程架构下合理但脆弱**——launchd 重启 cron-service 通常 < 5s，但重启后需要重建 SQLite cache、扫描 registry.yaml、恢复 tick 循环，如果 registry.yaml 较大（500+ 任务）或 SQLite 损坏需要重建，30s 可能不够。

2. **没有 "exactly-once" 语义保证**——文档在 §2.3 只提到可靠性 **99.9% 按计划触发**，但未说明是 at-least-once 还是 at-most-once。断点续跑会导致重复触发（at-least-once），健康探针 crash 也可能跳过 tick（at-most-once）。这与 Temporal 的 exactly-once 执行有本质差距。

3. **故障注入测试（§7.6）是亮点但抽象**——7 项故障注入测试覆盖了 kill -9、DB truncate、50 并发、网络断开、磁盘满、时钟回拨、SQLite 损坏。但其中 "kill -9 → launchd 在 < 10s 内重启并恢复调度" 缺乏具体的验证标准——如何定义"恢复调度"？第一个 tick 就触发漏掉的任务才算恢复？还是只恢复 tick 循环就行？

### 建议

- **R12 (HIGH)**：在 §2.3 或 §3.3 中明确 at-least-once / at-most-once 的语义承诺——推荐 at-least-once 加幂等脚本（业务端保证）作为默认
- **R13 (MEDIUM)**：增加恢复时间预算——500 任务时 registry.yaml 加载预算 2s、SQLite 重建预算 5s、首次 tick 恢复预算 10s，确保 RTO < 30s
- **R14 (MEDIUM)**：§7.6 "kill -9" 验收标准细化——定义"恢复调度"的标准：首次 tick 必须检查 pending 任务并触发

---

## 角度 6：可观测性与告警

### 现状分析

§4.5.1 原子写入运行记录（含 SLI 指标）、§4.5.2 健康指标、§4.5.3 多通道告警（iLink + 本地）、健康探针。

### 行业对标

| 特性 | Task Center | Temporal | Airflow | n8n |
|------|-------------|----------|---------|-----|
| **运行记录** | 文件 JSON + 原子写入 | Event Store（完整事件流） | DB 存储 | DB 存储 |
| **健康仪表板** | 健康探针 heartbeat | Web UI + 命令行 | Web UI（DAG 视图、甘特图） | Web UI 执行历史 |
| **告警通道** | iLink + 本地通知 | PagerDuty/Slack（社区） | Email/Slack/PagerDuty（丰富插件） | Email/Webhook |
| **SLI/SLO** | ✅（schedule_sli_ms） | ❌（不关注调度延迟） | ❌（不关注调度延迟） | ❌（不关注） |
| **Metrics 导出** | ❌未定义 | ✅ Prometheus | ✅ StatsD/Prometheus | ✅ Prometheus |
| **日志聚合** | 运行记录 JSON | Server 日志 | Task Log + S3/GCS | 执行日志 |
| **分布式追踪** | ❌ | ✅ OpenTelemetry | ❌ | ❌ |
| **审计日志** | MCP 审计 | 事件历史（完整） | DAG 版本 + 操作日志 | 工作流快照 |

### 核心发现

1. **SLI 指标（schedule_sli_ms）是差异化亮点**——Temporal、Airflow、n8n 都没有"调度延迟"的概念，因为它们在架构上就是事件驱动的（Temporal 的 Event Sourcing、Airflow 的 Scheduler 扫描 DAG、n8n 的 Node 链）。而 Task Center 基于 tick 扫描，调度延迟是一个自然要测量的指标。

2. **缺少 Metrics 导出是最大差距**——当前运行记录是"写文件"的 Push 模式，没有 Prometheus 暴露端点。这意味着运维人员无法用 Grafana 搭建实时仪表板，无法与现有的监控基础设施集成。Airflow 和 Temporal 都有成熟的 Metrics 集成。

3. **告警通道不够丰富**——只有 iLink（微信）和本地通知。对比 Airflow 的 Email/Slack/PagerDuty 集成，Task Center 的告警可达性有限。虽然文档说"告警从 Wave 3 升级为 MVP 必备"，但只定义了两种通道。

### 建议

- **R15 (HIGH)**：在 MVP 中增加 Prometheus Metrics 导出端点（或者至少支持 OpenTelemetry），关键指标：`task_center_sli_ms`、`task_center_active_tasks`、`task_center_runs_total`、`task_center_errors_total`
- **R16 (MEDIUM)**：告警通道增加 Webhook（可将告警转发到任一支持 Webhook 的系统）作为通用扩展点
- **R17 (LOW)**：考虑在 `_delivery/task-center/runs/` 中增加一个 `latest.json` 软链接指向最新运行记录，方便外部监控工具快速读取

---

## 角度 7：开发者体验

### 现状分析

MCP 工具集 11 个工具（CRUD + 执行 + 状态 + 健康检查），返回格式 `{ok: bool, data/error: ...}`，MCP over STDIO（FastMCP）。

### 行业对标

| 特性 | Task Center | Temporal | Airflow | n8n |
|------|-------------|----------|---------|-----|
| **API 风格** | MCP（FastMCP） | gRPC + tctl CLI | REST API + Airflow CLI | REST API + n8n CLI |
| **CLI 工具** | ❌（依赖 MCP Client） | `tctl`（功能完整） | `airflow` 命令丰富 | `n8n` CLI 覆盖所有功能 |
| **SDK/客户端** | ❌（MCP 自动生成） | 9+ 语言 SDK | Python Client | Node.js + REST |
| **本地开发** | ✅（MCP over STDIO） | ❌（需要 Server） | ❌（需要 Scheduler） | ❌（需要 Node） |
| **代码配置** | ✅（YAML registry） | ✅（代码定义 Workflow） | ✅（Python DAG） | ✅（可视化 + JSON） |
| **Schema 验证** | ✅（约束列表） | ✅（protobuf） | ✅（DAG 解析器） | ❌（运行时验证） |
| **热重载** | ❌（每 tick 扫描） | ✅（代码变更自动感知） | ✅（DAG 文件自动加载） | ✅（UI 修改即时生效） |

### 核心发现

1. **MCP 工具集是独特优势**——在 AI 原生开发时代，MCP 协议让 AI 编程助手可以直接 CRUD 任务。Temporal/Airflow/n8n 都没有 MCP 支持。这使 Task Center 天然适合 AI 驱动的运维场景。

2. **缺失 CLI 工具**——MCP 工具集对 AI 友好，但对人类 CLI 操作不便。`task_create` 等操作需要在 MCP Client（如 Claude Desktop）中完成，无法在终端直接执行。对比 Airflow 的 `airflow dags trigger` 和 Temporal 的 `tctl workflow start`，Task Center 缺少一个通用的 CLI 包装器。

3. **与 OpenSpec 工作流的融合点被忽略**——OpenSpec 的 `proposal → spec → design → tasks → apply → verify → archive` 生命周期与 Task Center 的 `task_create → task_run → 运行记录 → 告警` 存在天然映射：

```
OpenSpec      →   Task Center
─────────────────────────────────
proposal.md   →   创建 task 的动机说明（暂未定义）
spec.md       →   任务的输入/输出/验收标准（暂未定义）
design.md     →   任务的实现方案说明（暂未定义）
tasks.md      →   task 注册到 registry.yaml
apply         →   MCP task_create / task_run
verify        →   MCP task_check / 运行记录验证
archive       →   task_delete（保留运行记录归档）
```

### 建议

- **R18 (HIGH)**：补充 CLI 接口——至少提供 `omo task-center <subcommand>` 的命令行入口，映射所有 MCP 工具功能。允许在终端直接执行 `omo task-center run wf-001`
- **R19 (MEDIUM)**：在 §4.3 MCP 工具集中增加 `task_diff` 工具——对比 registry.yaml 的两个版本（Git diff 的包装），方便审阅变更
- **R20 (LOW)**：考虑在文档中增加"Task Center × OpenSpec 融合工作流"章节——将 task 的创建、测试、上线、废弃映射到 OpenSpec 的变更生命周期

---

## 角度 8：运维成熟度

### 现状分析

§6.2 回退方案（7 个场景）、§5.2.1 文件清单（8 个文件）、§5.2.2 修改清单（6 个文件）、§5.1 三阶段迁移路线。

### 行业对标

| 特性 | Task Center | Temporal | Airflow | Celery |
|------|-------------|----------|---------|--------|
| **部署复杂度** | 低（单进程 + launchd） | 高（集群 + DB + ES） | 中（Scheduler + Worker + DB） | 低（Worker + Broker） |
| **升级策略** | ❌未定义 | Rolling upgrade + 版本兼容 | Blue-green DB migration | 逐步升级 Worker |
| **备份恢复** | ❌未定义 | Server 备份（DB dump） | Metadata DB + DAG 文件 | Broker 消息持久化 |
| **数据迁移** | ✅渐进式（3 阶段） | ✅（版本兼容） | ❌（主要版本不兼容） | ❌（兼容性依赖） |
| **容量规划** | ❌未定义 | ✅（文档指导） | ✅（Scheduler 和 Worker 分离） | ✅（Worker 可水平扩展） |
| **Service Level** | ✅SLI/SLO 定义 | ✅（Temporal Cloud SLA） | ❌（社区不承诺 SLA） | ❌（社区不承诺 SLA） |

### 核心发现

1. **升级策略完全空白**——当 `registry.yaml` schema 从 version 1 升级到 version 2 时，旧的 cron-service 如何处理？SQLite cache schema 升级策略是什么？文档只在附录 C 引用了 [arcnode schema]，但未说明升级时的向下兼容策略。

2. **备份恢复未定义**——如果 `_truth/task-center/` 目录误删除或 Git 损坏，恢复过程是什么？SQLite cache 可以通过重新 sync 重建（R2 缓解），但运行记录（`_delivery/task-center/runs/`）丢失后不可恢复。

3. **运维 Playbook 缺失**——没有"常见运维操作"的文档：如何优雅停止 cron-service、如何回滚 registry.yaml、如何诊断 tick 滞后、如何手动触发 housekeeping。

### 建议

- **R21 (HIGH)**：在 §5.2.1 或新增 §8 操作指南中补充：
  - 升级策略：registry.yaml schema 版本兼容（主要版本不兼容时，cron-service 拒绝启动并提示迁移）
  - 备份恢复：每日自动备份 `registry.yaml` 和 `_delivery/task-center/runs/` 到 `.omo/backups/`
  - 运维 Playbook：至少覆盖"重启服务"、"回滚任务"、"手动触发 tick"、"查看运行状态"四个场景

- **R22 (MEDIUM)**：定义 `_truth/task-center/runs-backup/` 目录（或复用现有备份机制），每日自动打包运行记录，保留 90 天

---

## 角度 9：生态与集成能力

### 现状分析

Hermes 桥接（文件级解耦）、i0 事件总线（bus event）、iLink 微信（投递通道）。

### 行业对标

| 特性 | Task Center | Airflow | n8n | Temporal |
|------|-------------|---------|-----|----------|
| **连接器生态** | ❌Hermes 文件桥接（自制） | ✅100+ Provider (AWS/GCP/Azure/DB) | ✅400+ 节点（SaaS/DB/API） | ❌无（需 SDK 接入） |
| **CICD 集成** | ❌ | ✅GitSync + DAG 版本控制 | ✅Docker + 版本控制 | ✅GitOps（SDK 项目） |
| **代码仓库** | ✅Git 原生（YAML 在仓库内） | ✅DAG 文件在仓库 | ❌（DB 内，不支持 Git） | ❌（SDK 项目在仓库，Server 外） |
| **监控集成** | ❌无 Metrics | ✅Prometheus/StatsD/Sentry | ✅Prometheus/Datadog | ✅Prometheus/OpenTelemetry |
| **通知通道** | iLink + 本地通知 | Email/Slack/PagerDuty/JIRA | 100+ 通知节点 | PagerDuty/Slack（社区） |
| **自愈能力** | ❌（检测断裂但不自愈） | ❌（检测失败但不自愈） | ✅（Execution 重试） | ✅（Workflow 自动恢复） |
| **外部触发** | webhook + event | REST API + Sensor | Webhook + 定时 | Signal + Query |

### 核心发现

1. **集成生态严重空缺**——对比 Airflow 的 100+ Provider 和 n8n 的 400+ 连接器，Task Center 的集成仅限于"本地脚本 + 文件监听 + 微信通知"。虽然这与"单机本地调度"的定位一致，但至少应支持几个关键的外部集成：**GitHub/GitLab webhook**（CI/CD 触发）、**Slack 通知**（替代 iLink）、**文件上传到 S3**（结果投递扩展）。

2. **Hermes 桥接是一个"自制连接器"**——虽然 Hermes 桥接有效解决了项目间脚本共享的问题，但它在实质上是一个**文件目录级别的集成机制**，而非真正的连接器平台。每个新集成都需要编写新的 Hermes 桥接脚本，难以标准化。

3. **自愈能力缺失**——检测到任务断裂后（如 `script` 文件被删除），Task Center 只会标记为 `broken` 状态，不会自动尝试从其他位置寻找替代脚本或回退到上一个版本。对比 Airflow 的 SLA 监控和 Temporal 的自动恢复，这是一个可优化的方向。

### 建议

- **R23 (MEDIUM)**：在 §4.1.4 webhook 中增加 `GitHub/GitLab push event` 作为默认示例配置，降低 CI/CD 集成的门槛
- **R24 (LOW)**：考虑在 Wave 3 增加"Slack 通知通道"作为除 iLink 外的生产力工具集成
- **R25 (LOW)**：Hermes 桥接防断裂机制（§4.6）增加"自愈"选项——当检测到断裂时，自动从 Git 恢复脚本文件（如果项目仍在仓库中）

---

## 角度 10：规模边界与演进路线

### 现状分析

§2.3 目标：500+ 任务注册。§5.1 三阶段：阶段 1（清理完成）→ 阶段 2（MVP，Wave 2~3）→ 阶段 3（联邦，Phase ∞）。

### 行业对标

| 维度 | Task Center | Temporal | Airflow | n8n |
|------|-------------|----------|---------|-----|
| **最大任务数** | 500+ | 百万级 | 万级 | 千级 |
| **最大并发** | 4（Semaphore）+ 100（队列） | 数十万 | 取决于 Worker 数 | 取决于 Docker 资源 |
| **跨机器** | ❌（Phase 3 规划） | ✅天生 | ✅天生 | ✅集群模式 |
| **容量扩展** | 垂直扩展（单机资源） | 水平扩展 + 分片 | 水平扩展（Worker） | 水平扩展（Docker） |
| **DB 瓶颈** | SQLite（单写） | Cassandra/MySQL/Postgres | Postgres/MySQL | SQLite/Postgres |
| **事件吞吐** | kqueue 上限 ~1000 fd | 取决于 Event Store | 取决于 Sensor | 取决于 Node.js 事件循环 |

### 核心发现

1. **500+ 任务在单机 SQLite + 文件系统上是合理且保守的**——SQLite 可轻松处理数万行记录，文件系统（registry.yaml）加载 500 个 YAML 任务 < 100ms。真正瓶颈是并发执行（4 个 Semaphore slot）和事件监听（kqueue fd 上限），但文档已做限制。

2. **联邦路线过于模糊**——Phase 3（2027+）的描述只有标题级内容（"联邦调度"、"任务 DAG"、"自助注册门户"、"健康看板"、"智能告警"）。对比 Temporal 的分布式架构设计，Task Center 的联邦路线缺乏具体设计。

3. **MVP 阶段负载过重**——Wave 2~3（2026-06~08）需要完成：registry.yaml schema + cron-service 改造 + MCP 工具集 + 事件触发器 + 健康仪表板 + 迁移 2 条存活任务 + Safety Sprint（4-6 天）。对于个人开发者 + AI 协作，这个范围可能过于激进。

### 建议

- **R26 (MEDIUM)**：在 §5.1 路线图中增加 MVP 的阶段性里程碑——分为 MVP-A（注册层 + 调度层 + cron 执行，2 周）和 MVP-B（事件 + webhook + 观测，2 周）
- **R27 (LOW)**：明确 500+ 任务的软上限——超过 500 时，推荐使用 SQLite cache 替代全量 YAML 扫描；超过 1000 时，考虑将 `_delivery/task-center/runs/` 切换为时间分区目录结构
- **R28 (LOW)**：在 §5.3 联邦路线中增加一个设计原则——"联邦按需，不超前设计"

---

## 第三部分：与 OpenSpec 的深度对标

### 3.1 设计哲学对比

| 哲学维度 | OpenSpec | Task Center | 对标分析 |
|----------|----------|-------------|----------|
| **规范形式** | Markdown + Schema | YAML + 约束列表 | OpenSpec 的 Schema 更正式（JSON Schema），Task Center 通过表格约束更轻量 |
| **变更生命周期** | 提案→规约→设计→任务→应用→验证→归档 | 创建→执行→记录→告警→删除 | 两者生命周期有 3 个阶段对应，但 Task Center 缺"提案"和"验证"阶段 |
| **迭代模式** | 流动迭代（可随时修改任何阶段产物） | 版本化迭代（registry.yaml 通过 Git 版本化） | OpenSpec 更灵活，Task Center 更严谨（Git commit 作为变更边界） |
| **AI 友好度** | 20+ AI 助手支持，Slash 命令控制 | MCP 协议（标准工具接口） | 两者都是 AI-native，但 OpenSpec 面向"开发工作流"，Task Center 面向"运维工作流" |
| **存量项目** | 可逐步引入（新增 openspec/ 目录） | 可直接迁移（已有 cron-job 可录入 registry.yaml） | 两者都支持渐进式采用 |

### 3.2 工作流生命周期的融合映射

OpenSpec 的 7 阶段工作流与 Task Center 的任务生命周期存在**天然的互补关系**：

```
OpenSpec 变更                                                        Task Center
───────────                                                        ────────────
proposal.md  ──── 为何要做？                                         task 创建前的   "提案文档"
                    ↓                                               （暂未定义）
spec.md      ──── 做成什么样？                                       task 的        "规格文档"
                    ↓                                               （暂未定义）
design.md    ──── 技术方案？                                         task 的        "设计文档"
                    ↓                                               （暂未定义）
tasks.md     ──── 具体任务                                            registry.yaml 注册
                    ↓
apply        ──── AI 编码实现                                        MCP task_create / task_run
                    ↓
verify       ──── 验证是否符合 spec                                  MCP task_check + 运行记录验证
                    ↓
archive      ──── 归档变更                                           task_delete（Y → archive）
                                                                     运行记录保留在 _delivery/
```

**融合价值**：每个 Task Center 的调度任务，其"创建目的/验收标准/技术方案"用 OpenSpec 的 `proposal.md` / `spec.md` / `design.md` 来表达，而"执行入口"用 registry.yaml 的 `script` / `schedule` 来表达。这样，一个调度任务既有**业务文档**（OpenSpec），又有**执行配置**（Task Center）。

### 3.3 互操作性的具体方案

建议在 `_truth/task-center/` 中增加可选字段 `openspec_ref`：

```yaml
- id: wf-001
  type: cron
  name: "KOS 每日索引"
  openspec_ref: "changes/kos-daily-index/proposal.md"  # ← 新增
  # ... 其余字段
```

`openspec_ref` 指向 OpenSpec 的变更目录。当执行 `task_check` 时，除了运行记录，还可以输出 OpenSpec 文档的完整性和一致性问题。

### 3.4 借鉴 OpenSpec 的设计

| 可借鉴点 | 说明 | 建议位置 |
|----------|------|----------|
| Schema 机制 | OpenSpec 使用 JSON Schema 校验文档结构，Task Center 可使用类似方式校验 registry.yaml | §4.2.3 |
| Delta 规范 | OpenSpec 的变更记录增量变化，Task Center 的 registry.yaml 也可记录增量 diff | §4.2.1 或附录 A |
| 归档机制 | OpenSpec 的 archive/ 保留历史变更，Task Center 的任务删除后可将 registry.yaml 条目移入归档 | §4.2.1 |
| 批量操作 | OpenSpec 的 bulk-archive 可以一次性归档多个变更，Task Center 可借鉴批量迁移/禁用 | §4.3 |

---

## 第四部分：发现汇总与改进优先级

### 4.1 发现汇总

| ID | 角度 | 严重度 | 标题 | 当前缺失 |
|----|------|--------|------|----------|
| R1 | 定位 | HIGH | 缺少与 Temporal/Airflow/Celery/n8n 的差异化对比 | 未说明"为什么不是 X" |
| R2 | 定位 | MEDIUM | 未规划与 OpenSpec 工作流的融合 | 同为 OMO 体系，可无损融合 |
| R3 | 架构 | HIGH | 缺少"执行中任务被 kill"的场景设计 | startup 时未标记中断的运行记录 |
| R4 | 架构 | MEDIUM | SQLite cache 与 registry.yaml 双向同步策略模糊 | Git 冲突时恢复策略不明确 |
| R5 | 架构 | LOW | 可以考虑 Registry Watch（文件变更自动 reload） | 减少每 tick 全量扫描 |
| R6 | 任务模型 | MEDIUM | `depends_on` 应增加 weak/strong 语义 | 无法表达"必须先执行 A" |
| R7 | 任务模型 | LOW | i0 事件总线接口规范未定义 | 消息骨架未定义 |
| R8 | 任务模型 | LOW | 缺少 timezone 字段 | 时区处理不明确 |
| R9 | 安全 | HIGH | webhook 无 HTTPS 配置选项 | 传输层加密缺失 |
| R10 | 安全 | MEDIUM | 未定义秘密轮换策略 | 无自动轮换机制 |
| R11 | 安全 | LOW | 未考虑 MCP 操作防重放 | 无 updated_at 签名验证 |
| R12 | 可靠性 | HIGH | 执行语义未明确(at-least-once / at-most-once) | 无 exactly-once 保证 |
| R13 | 可靠性 | MEDIUM | 恢复时间预算未定义 | 500 任务时 RTO 预算不清 |
| R14 | 可靠性 | MEDIUM | §7.6 故障注入验收标准模糊 | "恢复调度"定义不明确 |
| R15 | 可观测性 | HIGH | 缺少 Prometheus Metrics 导出 | 无法与 Grafana 集成 |
| R16 | 可观测性 | MEDIUM | 告警通道不够丰富 | 只支持 iLink + 本地 |
| R17 | 可观测性 | LOW | 无 latest.json 软链接 | 外部监控读取不便 |
| R18 | 开发者体验 | HIGH | 缺少 CLI 接口 | 依赖 MCP Client，终端操作不便 |
| R19 | 开发者体验 | MEDIUM | 缺少 task_diff（Git diff 包装） | 审阅变更需要手动 git diff |
| R20 | 开发者体验 | LOW | 未规划与 OpenSpec 工作流融合 | MCP 工具集可扩展 |
| R21 | 运维 | HIGH | 升级策略/备份恢复/Playbook 完全空白 | 关键运维操作文档缺失 |
| R22 | 运维 | MEDIUM | 运行记录未备份 | 不可恢复的丢失风险 |
| R23 | 生态 | MEDIUM | 缺少 GitHub/GitLab webhook 默认配置 | CI/CD 集成门槛高 |
| R24 | 生态 | LOW | 缺少 Slack 等生产力工具通知 | 通知通道单一 |
| R25 | 生态 | LOW | Hermes 防断裂可增加"自愈"选项 | 从 Git 恢复脚本 |
| R26 | 规模 | MEDIUM | MVP 负载过重，建议分为 MVP-A 和 MVP-B | 2 个月窗口过于紧张 |
| R27 | 规模 | LOW | 500+ 任务的规模应对细节不明确 | SQLite 切换/分区策略 |
| R28 | 规模 | LOW | 联邦路线过于模糊 | 缺乏具体设计 |

### 4.2 优先级排序

#### 必须解决（MVP Blocking）

| ID | 发现 | 影响 |
|----|------|------|
| R12 | at-least-once vs at-most-once 未明确 | 影响整个可靠性设计 |
| R15 | 缺 Metrics 导出 | 运维无法监控 |
| R18 | 缺 CLI | 人类无法操作 |
| R21 | 运维 Playbook 缺失 | MVP 上线后无法运维 |
| R3 | 执行中被 kill 场景 | 数据完整性风险 |

#### 强烈建议（MVP 前解决）

| ID | 发现 |
|----|------|
| R1 | 差异化定位说明 |
| R9 | webhook HTTPS |
| R13 | 恢复时间预算 |
| R14 | 故障注入验收标准 |
| R16 | 告警通道 Webhook 扩展 |
| R19 | task_diff 工具 |
| R23 | GitHub webhook 示例 |
| R26 | MVP 分阶段 |

#### 建议（MVP 后）

| ID | 发现 |
|----|------|
| R2 | OpenSpec 工作流融合 |
| R4 | 双向 sync 策略 |
| R5 | Registry Watch |
| R6 | depends_on weak/strong |
| R7/R8 | i0 规范 / timezone |
| R10 | 秘密轮换策略 |
| R11 | MCP 操作防重放 |
| R17 | latest.json |
| R20 | OpenSpec 融合文档 |
| R22 | 运行记录备份 |
| R24/R25 | Slack / 自愈 |
| R27/R28 | 规模细节 / 联邦设计 |

---

## 结论

### 总体评分

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 产品定位 | 4.5 | Niche 精准，但差异化描述不够锐利 |
| 架构设计 | 4.0 | 四层架构清晰，单点故障和恢复设计待补强 |
| 任务模型 | 4.5 | 5 类覆盖 95% 场景，编排能力是固有边界 |
| 安全模型 | 4.0 | Safety Sprint 彻底，传输加密和秘密轮换待补 |
| 可靠性 | 3.5 | SLI/SLO 定义好，语义承诺和恢复预算不明确 |
| 可观测性 | 4.0 | 运行记录 + 健康探针好，Metrics 导出缺失 |
| 开发者体验 | 4.0 | MCP 是亮点，缺少 CLI 是硬伤 |
| 运维成熟度 | 3.0 | 升级/备份/Playbook 空白 |
| 生态集成 | 3.5 | Hermes 务实，连接器生态弱 |
| 规模边界 | 4.0 | 单机上限明确，联邦路线模糊 |

**综合评分：3.9 / 5.0**

### 关键结论

1. **Task Center 在单机调度领域没有直接竞品**——Temporal/Airflow/Celery/n8n 要么太重（需要 Broker/DB/集群），要么太轻（只有 cron，无统一管理）。Task Center 填补了这个空白，但文档未充分阐述这一点。

2. **与 OpenSpec 的融合是最"可惜"的未使用机会**——两者同属 OMO 技术栈，且设计哲学互补（OpenSpec 管开发阶段，Task Center 管运维阶段），但当前文档未定义任何互操作接口。

3. **v0.2 的 9 CRITICAL + 14 HIGH 修复非常扎实**——安全、可靠性、回退方案经过三路审阅后显著提升。当前的差距主要是**进阶功能**（Metrics、CLI、运维 Playbook）而非**基础缺陷**。

4. **建议在进入 MVP 编码前，先完成 R1/R12/R15/R18/R21 五个发现处理**——它们不影响架构设计但影响上线后的可用性和可运维性。

---

## 附录：各方案简明参考

### OpenSpec
- **GitHub**: https://github.com/Fission-AI/OpenSpec
- **Docs**: https://radebit.github.io/OpenSpec-Docs-zh/
- **核心理念**: Spec-driven development for AI coding assistants
- **工作流**: Proposal → Spec → Design → Tasks → Apply → Verify → Archive

### Temporal
- **GitHub**: https://github.com/temporalio/temporal
- **核心组件**: Frontend (gRPC) → History Service → Matching Service → Worker
- **存储**: Cassandra/MySQL/Postgres (Event Store + Visibility)
- **亮点**: Exactly-once execution, Durable Workflow, 9+ 语言 SDK

### Apache Airflow
- **官网**: https://airflow.apache.org/
- **核心组件**: Scheduler → Executor → Worker + Web UI + Metadata DB
- **文件格式**: Python DAG 文件
- **亮点**: 100+ Provider, 丰富 UI (DAG 视图/甘特图/代码视图), 活跃社区

### Celery
- **官网**: https://docs.celeryq.dev/
- **核心组件**: Broker (Redis/RabbitMQ) → Worker → Result Backend
- **亮点**: 简单、成熟、轻量、与 Python 生态集成好
- **限制**: 无 Web UI、无事件驱动、无长期守护管理

### n8n
- **官网**: https://n8n.io/
- **核心组件**: Node.js Server → Workflow Executor → 400+ 连接器节点
- **亮点**: 可视化编辑、丰富连接器（400+）、自托管
- **限制**: Node.js 运行时绑定、不适合纯脚本任务

### systemd timer / launchd
- **本质**: OS 级服务管理器 + 定时器
- **特点**: 零依赖、可靠性高、直接进程管理
- **限制**: 无统一管理/观测/告警、配置分散在各 .timer/.plist 文件中

### Quartz
- **官网**: https://www.quartz-scheduler.org/
- **核心组件**: Scheduler → ThreadPool → JobStore (RAM/JDBC)
- **亮点**: 最成熟的单机调度库、cron 表达式兼容、集群模式
- **限制**: Java 生态绑定、无 Web UI、无事件/webhook/脚本管理

### Prefect
- **官网**: https://www.prefect.io/
- **核心组件**: Python SDK + Server (SQLite/Postgres) + Agent
- **亮点**: Python-native、动态 DAG、自动重试、缓存机制
- **限制**: Python 限定、Server 组件较重

---

> **本报告未经人工验证，AI 可能遗漏某些细节。建议人工审阅后确认改进项。**
