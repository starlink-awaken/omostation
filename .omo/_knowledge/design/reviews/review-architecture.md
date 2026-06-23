---
plane: knowledge
type: review
status: draft
freshness: 2026-05-31
maintainer: auto
---
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# 架构评审报告：Task Center 需求文档 v0.1

> **审阅范围**: SSOT 四平面一致性 · 治理/调度边界 · 模块关系 · 可扩展性 · arcnode 映射 · 遗漏矛盾
> **审阅日期**: 2026-05-31
> **审阅对象**: `_knowledge/design/task-center-requirements.md`
> **审阅人**: general-purpose-14 (架构评审 Agent)

---

## 摘要

Task Center 需求文档整体方向正确——统一 5 类任务、收敛 4 套独立调度系统、建立调度 SSOT——与 SSOT 四平面架构基本对齐。但存在 **3 个 CRITICAL 问题**（四平面划界模糊、hermes 桥接层断裂风险延续、缺少 secret 管理体系）、**5 个 HIGH 问题**（互引空悬/SQLite cache 漂移/并发配置碎片/交付字段歧义/federated 路径缺失）以及若干 MEDIUM/LOW 建议。**有条件批准**——修复 CRITICAL + HIGH 问题后可进入实施。

---

## 1. CRITICAL 发现问题

### C1 — `instances/` 事实面/交付面归属混淆

| 字段 | 值 |
|------|-----|
| **问题描述** | §3.1 将 `instances/`（单次运行快照）置于 `_truth/task-center/`（事实面），同时将 `runs/`（运行记录）置于 `_delivery/task-center/`（交付面）。这两个实体实质上是相同数据的两个投影——实例快照是"运行的确切参数"，运行记录是"运行的结果证据"。在四平面模型中，事实面存放不可变的 SSOT（registry.yaml），交付面存放可验证的执行证据。instances 与 runs 之间的边界不清晰，会导致同一执行事件在两个平面中不一致。 |
| **影响范围** | 架构设计 | 
| **严重级别** | **CRITICAL** |
| **建议修复** | 删除 `_truth/task-center/instances/` 目录。将所有运行时数据归入 `_delivery/task-center/runs/` 一体管理。registry.yaml 只保留"期望状态"（应该执行什么），交付面只保留"实际状态"（执行了什么）。如需运行前参数快照，将其作为 run 记录的一个字段。 |

---

### C2 — Hermes 桥接层断裂风险原样延续

| 字段 | 值 |
|------|-----|
| **问题描述** | §4.6 明确保留 hermes symlink 桥接作为 decoupling layer：registry.yaml 中 script 值相对于 `~/.hermes/scripts/`，新任务注册时自动创建 symlink。这正是历史上造成 179 条断裂的直接原因——5 个项目归档后，所有 symlink 变成 dead link。Task Center 没有解决"项目归档时自动清理对应调度条目"的根本问题。保留同一桥接层 = 保留同一断裂模式。 |
| **影响范围** | 可靠性、可观测性 |
| **严重级别** | **CRITICAL** |
| **建议修复** | 方案 A（推荐）：registry.yaml 中 script 使用实体路径（绝对路径或 `~/Workspace/projects/...`），去掉 hermes 中间层。将 hermes 桥接降级为可选兼容层，不作为核心依赖。方案 B：如果必须保留 hermes 桥接，必须增加"自动断裂防护"——项目被归档时自动 deactivate 所有相关 task + 提升 `_knowledge/management/` 中的断裂检测脚本为常驻守护，SLA < 60s 发现断裂。 |

---

### C3 — Secret 管理体系完全缺失

| 字段 | 值 |
|-----|-----|
| **问题描述** | §4.1.4 webhook 要求 HMAC secret 存储在 `_secret/`，但 `_secret/` 在任何平面中均无定义——不存在于 `_truth/INDEX.md`、`DOC-ARCH.md` 或 `state/system.yaml` 中。文档也未说明秘密的创建、轮换、审计机制。四平面中没有"秘密管理"平面，这是一个基础架构缺口。 |
| **影响范围** | 安全架构 |
| **严重级别** | **CRITICAL** |
| **建议修复** | 必须在实施前确定 secret 管理方案：(1) 如果 secret 数量少（< 10），将其纳入 `_control/state/secrets.yaml` 并 git-crypt/git-secret 加密；(2) 如果数量多，建立独立的 secrets 规范目录 `_truth/secrets/`（引用加密存储）。registry.yaml 的 webhook 配置中只存 `secret_ref` 指针而非明文。提示：当前 `~/.cron-service/config.yaml` 模式可复用但需要纳入四平面索引。 |

---

## 2. HIGH 发现问题

### H1 — 跨类型互引空悬风险

| 字段 | 值 |
|-----|-----|
| **问题描述** | §3.2 互引机制：治理任务通过 `task_ref` 引用调度任务，调度任务通过 `depends_on` 引用治理任务。但治理任务 ID（如 `M2.6-INTEGRATION-VERIFY`）在 Phase 变更或重构后可能被重命名、合并或归档，导致调度任务中出现 dangling `depends_on` 引用。反之，调度任务被删除后，治理任务中的 `task_ref` 也会空悬。文档未讨论空悬检测或自动清理机制。 |
| **影响范围** | 数据一致性 |
| **严重级别** | **HIGH** |
| **建议修复** | (1) 在 `task_check` MCP 工具中增加空悬引用扫描；(2) 治理任务归档时自动扫描所有调度任务的 `depends_on` 并写入 `divergence_flags`；(3) 考虑将 `depends_on` 改为软引用（仅用于文档说明而非执行阻断），降低耦合。 |

---

### H2 — registry.yaml / SQLite 双写不一致风险被低估

| 字段 | 值 |
|-----|-----|
| **问题描述** | §6.1 R2 将"registry.yaml 与 SQLite 不一致"评为影响"中"，但影响范围比描述更广：SQLite cache 是调度层（tick loop）的直接数据源，registry.yaml 是 SSOT。如果 sync 逻辑有 bug，可能出现：(1) 调度层执行了 registry.yaml 中已删除的任务（phantom run）；(2) 调度层未执行新注册的任务（missed trigger）。R2 的缓解措施"每次 tick 前校验，diff 检测"在 15s 间隔下会引入额外 I/O 开销，对 500+ 任务场景不友好。 |
| **影响范围** | 调度可靠性 |
| **严重级别** | **HIGH** |
| **建议修复** | (1) 重新评估 R2 风险等级为"高"；(2) 设计"版本号+checksum"机制：registry.yaml 加载时生成版本指纹，SQLite cache 记录源版本指纹，tick loop 先校验指纹再加载；(3) 提供紧急强制 re-sync 命令用于手工修复。 |

---

### H3 — 并发控制配置在风险矩阵中孤立定义

| 字段 | 值 |
|-----|-----|
| **问题描述** | R6 定义了"Semaphore 限制最大并发数（默认 4）"作为风险缓解措施，但该配置未出现在任何需求章节或 schema 定义中。这意味着 R6 描述的控制措施没有纳入功能设计，实施时可能被遗漏。同时，默认 4 的并发数是否合理取决于硬件（32核 vs 4核），应该可配。 |
| **影响范围** | 资源管理、可配置性 |
| **严重级别** | **HIGH** |
| **建议修复** | (1) 在 §4.2.1 全局 defaults 中增加 `max_concurrency: 4` 字段；(2) 在任务级别可选覆盖；(3) 在非功能性需求中增加并发控制指标（最大并发数、资源限制）。 |

---

### H4 — `deliver: origin` 未定义/有歧义

| 字段 | 值 |
|-----|-----|
| **问题描述** | §4.1.1 的 `deliver` 字段枚举值为 `local | origin(iLink)`。但"origin"的字面语义和"iLink（微信）"的语义相差甚远——origin 可理解为"起源/远程"，iLink 是具体的微信通知平台。§7.4 安全验收中又提到"iLink token 存储在 `~/.cron-service/config.yaml`"。整个 iLink/微信集成属于跨系统交付，但文档对此没有明确的架构描述。 |
| **影响范围** | 交付机制清晰度 |
| **严重级别** | **HIGH** |
| **建议修复** | (1) 将 `deliver` 枚举重新设计为：`local`（本地日志）、`notify`（通知推送）、`remote`（远程执行）；(2) 通知渠道（iLink/Slack/邮件）独立为 `notify_channels` 配置；(3) 将 iLink 集成移入"外部依赖"架构决策记录。 |

---

### H5 — Federated 扩展路径从架构层面缺失

| 字段 | 值 |
|-----|-----|
| **问题描述** | 阶段 3（2027+）宣称"联邦任务中心"，但文档中没有对 federated 场景的架构约束进行任何前瞻设计。具体缺失：(1) 跨机器 registry.yaml 同步机制——是 Git-pull 轮询还是事件推送？(2) 分布式锁或乐观并发控制？(3) task ID 命名空间如何管理？（一台机器的 wf-001 与另一台机器的 wf-001 如何区分？）(4) 跨机器的 webhook 路由。这些在 MVP 阶段的 schema 和 ID 设计中就应当预留扩展位。 |
| **影响范围** | 架构可扩展性 |
| **严重级别** | **HIGH** |
| **建议修复** | (1) 假设 federated 模式为每个节点添加 `node_id` 前缀——立即将 task ID 约束从 `^[a-z0-9][a-z0-9_-]{2,63}$` 改为 `^[a-z0-9-][a-z0-9_-]{2,63}$` 以允许 hostname 前缀；(2) 在设计文档中增加"Federated 架构备忘"一节，记录已知约束和预留扩展位；(3) 评估 registry.yaml 在 federated 模式下是否还适合作为 SSOT（可能是每个节点一个 registry.yaml + 全局聚合层）。 |

---

## 3. MEDIUM 建议

### M1 — 事件文件监听与项目目录耦合

| 字段 | 值 |
|-----|-----|
| **问题描述** | event 类型 fs 监听硬编码路径 `~/Workspace/data/knowledge/`。项目目录将来可能重组，硬编码路径是历史教训 §1.2 第 4 条提到的问题。 |
| **影响范围** | 可维护性 |
| **严重级别** | **MEDIUM** |
| **建议修复** | event 配置中的 `watch` 路径应支持环境变量展开（如 `$WORKSPACE/data/knowledge/`）或相对 workspace root 的路径。 |

---

### M2 — once 类型缺少延迟执行能力

| 字段 | 值 |
|-----|-----|
| **问题描述** | `once` 类型只有"创建即启用，执行后禁用"的语义。如果需要在特定时间执行（如"3 小时后备份"），没有 `run_at` 或 `delay_seconds` 字段。|
| **影响范围** | 功能可用性 |
| **严重级别** | **MEDIUM** |
| **建议修复** | 为 once 类型增加可选字段 `run_at: "2026-06-01T14:00:00Z"` 或 `delay_seconds: 3600`，实现计时执行。 |

---

### M3 — 运行记录缺少触发源标识

| 字段 | 值 |
|-----|-----|
| **问题描述** | §4.5.1 运行记录格式没有 `triggered_by` 字段。同一任务可能被 cron tick、task_run MCP、webhook 三种方式触发，缺少触发源会影响审计和问题排查。 |
| **影响范围** | 可观测性/审计 |
| **严重级别** | **MEDIUM** |
| **建议修复** | 运行记录增加 `trigger: cron | manual | webhook | event` 字段。 |

---

### M4 — 告警策略无法按任务定制

| 字段 | 值 |
|-----|-----|
| **问题描述** | §4.5.3 告警机制使用全局 `max_consecutive_failures` 默认 3 次。但不同任务的通知需求不同——core 索引任务失败应立即告警，辅助任务可以容忍多次失败。当前 schema 没有每个任务的告警策略配置。 |
| **影响范围** | 告警灵活性 |
| **严重级别** | **MEDIUM** |
| **建议修复** | 在任务 schema 中增加 `alert` 对象字段：`alert: { max_consecutive_failures: 3, notify_channels: ["ilink"], cooldown_minutes: 60 }`，覆盖全局默认值。 |

---

### M5 — Workers 框架运行记录路径未对齐

| 字段 | 值 |
|-----|-----|
| **问题描述** | §3.4 中 Task Center 运行记录在 `_delivery/task-center/runs/`，Workers 框架运行记录在 `_delivery/workers/runs/`。两者共享同一平面但路径不同，缺少共享的 INDEX 入口。对于运维人员来说，"查所有运行记录"需要知道去两个目录。 |
| **影响范围** | 运维体验 |
| **严重级别** | **MEDIUM** |
| **建议修复** | 在 `_delivery/INDEX.md` 中增加"运行记录聚合"章节，列出 `task-center/runs/` 和 `workers/runs/` 作为子入口；或考虑 `_delivery/runs/task-center/` 和 `_delivery/runs/workers/` 统一前缀。 |

---

## 4. LOW / 建议

### L1 — once 创建即启用的用户意图没说透

文档说 once 类型"创建时默认启用，执行后自动禁用"，但没有说明用户是否能显式创建后延迟启用。建议增加语义：once 类型的 `enabled: false` 等同于"定时炸弹"——只在手动 task_run 时执行，创建后不会自动触发。

### L2 — 验收清单顺序逻辑颠倒

§7.1 第一条验收项为"`_truth/task-center/` 目录创建，包含 INDEX.md 和 registry.yaml"，第二条为"5 种任务类型的 registry.yaml schema 定义完成"。逻辑上应先定义 schema → 再创建 registry.yaml → 再创建 INDEX.md。建议交换顺序。

### L3 — schedule now 字段建议

当前 `schedule` 只支持 cron 表达式和 `every Xm` 格式。建议增加 `:now` 伪值，语义为"创建后立即执行一次"（特别适合 once 类型）。实现简单但在用户体验上提供很大便利。

### L4 — longrun health_check 的 PID 检测局限

§4.1.3 中 `health_check.type: pid` 仅检测 PID 文件存在性。如果进程变成 zombie（PID 存在但实际已死），会误报为健康。建议补充进程存活探活（`kill -0 $PID`）或给出明显的准确度限制说明。

### L5 — 缺失与 arcnode meta types 的映射

请求文档 §6 明确要求审阅该映射，当前设计文档完全没有提及。建议在架构附录中增加映射关系：

| Task Center 类型 | arcnode MetaType | arcnode ConcreteType | 说明 |
|:---|:---|:---|:---|
| `cron` | PROCESSOR | `ProcessorDef` | 周期性处理器 |
| `once` | PROCESSOR | `ProcessorDef` | 一次性执行 |
| `longrun` | (*new) SERVICE* | 建议新增 | 长期运行服务 |
| `webhook` | GATEWAY | — | 入口/触发端点 |
| `event` | PROCESSOR | `ProcessorDef` | 事件驱动处理器 |

> 注: arcnode 当前枚举中没有 SERVICE 类型。longrun 本质上是"常驻服务"而非"处理节点"，如果 arcnode 要完整覆盖 Task Center，可能需要新增 SERVICE meta type。

---

## 5. 跨维度一致性检查

| 检查维度 | 结果 | 说明 |
|---------|------|------|
| ../MASTER-BLUEPRINT.md 对齐 | 🟡 松散对齐 | Phase 4 Wave 2-3 覆盖，但缺失 Task Center 在架构图中的位置标注 |
| DOC-ARCH.md 四平面对齐 | 🔴 未对齐 | `_truth/INDEX.md` 未预留 task-center 槽位；`_delivery/INDEX.md` 未索引 task-center runs |
| state/system.yaml 可嵌入 | 🟡 部分对齐 | divergence_flags 已预留，但缺少活跃任务数/错误任务数指标字段 |
| workers/registry.yaml 正交 | 🟢 对齐 | Task Center 不在 Worker 框架内 |
| 历史教训闭环 | 🔴 部分断裂 | 179 条断裂的根本原因是 hermes 桥接 + 无清理机制。Task Center 继承了 hermes 桥接但未解决清理机制 |
| 2 条存活任务迁移路径 | 🟢 清晰 | x2-backup-brain、omo-state-sync 迁移路径明确 |

---

## 6. 结论

### 有条件批准交付

**条件**（按优先级排序）：

**必须先修复（CRITICAL）**：
1. C1 — 删除 `instances/` 事实面归属，统一到交付面
2. C2 — 消除 hermes 桥接核心依赖，或增加断裂自动防护机制
3. C3 — 建立 secret 管理方案，纳入四平面索引

**修复后可进入实施（HIGH）**：
4. H1 — 增加跨类型空悬引用检测
5. H2 — 重新设计 registry.yaml/SQLite 一致性校验机制
6. H3 — 将并发控制纳入 schema 和全局 defaults
7. H4 — 重新设计 deliver 字段语义
8. H5 — 补充 Federated 架构约束和 ID 命名空间预留

**建议在 MVP 前处理（MEDIUM）**：
9. M1-M5 如上所述，涉及运维体验和功能完整性

**预计修复工作量**：C1~C3 ~2 天，H1~H5 ~3 天，M1~M5 ~2 天。总计约 **7 人天**的架构修订工作。

---

*审阅完成: 2026-05-31 · 审阅版本: v0.1 (草案)*
