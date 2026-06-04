# Phase 5 Task Center 着陆模型

> **类型**: 冻结记录（Wave 0 交付物）
> **日期**: 2026-05-31
> **状态**: 已冻结
> **负责人**: codebuddy
> **关联任务**: `P5-W0-LANDING-MODEL-FREEZE`
> **源文档**:
> - [Phase 5 程序架构](./phase5-program-architecture.md)
> - [Task Center 需求文档](./task-center-requirements.md)
> - [Phase 5 Wave 0 任务规范](../../plans/archive/phase5-wave0-task-specs.md)

---

## 1. 冻结声明

以下表格显式定义 Task Center 在四平面架构中的 landing 位置。**此声明在 Wave 0 冻结，Wave 1+ 的变更必须通过 proposal 流程修改本文件。**

**核心原则**: Task Center 是 plane-native domain——registry 只存在于 `_truth/`，运行记录只存在于 `_delivery/`。任何平面不得持有另一平面的数据副本。

## 2. 平面所有权表

### 2.1 Truth 平面 `_truth/task-center/`

存储调度任务的**定义级**数据——这是唯一事实源（SSOT）。

| 资源 | 用途 | 格式 | 写入者 |
|------|------|------|--------|
| `INDEX.md` | 调度 SSOT 入口，说明目录用途与所有权规则 | Markdown | 人工（初始化）+ MCP 工具 |
| `registry.yaml` | 任务注册表，包含 5 种任务类型的完整定义 | YAML | MCP task_create/task_update/task_delete |
| `triggers/cron/` | cron 触发器定义 | YAML（每文件一任务） | MCP 工具或 registry sync |
| `triggers/event/` | 事件触发器定义 | YAML（每文件一任务） | MCP 工具或 registry sync |
| `triggers/webhook/` | Webhook 触发器定义 | YAML（每文件一任务） | MCP 工具或 registry sync |

**约束**:
- registry.yaml **禁止**包含 `secret`/`token`/`password` 明文字段，仅使用 `secret_ref` 引用受管秘密存储
- `trigger/` 下的文件是 registry.yaml 的拆分视图，**不是**独立 SSOT——registry.yaml 始终是权威来源
- 运行时缓存（SQLite `cron.db`）不在 truth 平面，属于交付平面的 cache 机制

### 2.2 Delivery 平面 `_delivery/task-center/`

存储调度任务的**运行态**数据——执行证据和观测记录。

| 资源 | 用途 | 格式 | 写入者 |
|------|------|------|--------|
| `INDEX.md` | 运行记录入口 | Markdown | 人工（初始化） |
| `runs/{task_id}/{timestamp}.json` | 单次执行运行记录 | JSON | scheduler executor |
| `alerts/{task_id}/{timestamp}.json` | 告警事件持久化 | JSON | scheduler alert 模块 |
| `audit/{timestamp}-{operation}.json` | 变更审计日志 | JSON | MCP 工具调用中继 |
| `heartbeat.json` | scheduler 健康探针（最新 tick 时间戳） | JSON | scheduler tick loop |

**约束**:
- `runs/` 必须使用原子写入（tmp → fsync → rename），写入后不可变
- `heartbeat.json` 仅保留最新状态，不做历史——历史健康数据在 `runs/` 中
- 告警文件在创建后不可变，不做原地修改
- 运行记录、告警、审计的保留和归档策略由 housekeeping cron job 管理

### 2.3 Control 平面 `_control/`

| 资源 | 用途 | 数据来源 |
|------|------|----------|
| `state/system.yaml#task_center` | 健康摘要（活跃/断裂/错误计数） | scheduler tick loop 写入 |
| `state/system.yaml#divergence_flags` | 断裂检测标志 | scheduler 断裂检测模块 |

Control 平面仅保留**状态摘要**，不包含任何 registry 或运行记录数据的副本。

### 2.4 Knowledge 平面 `_knowledge/`

| 资源 | 用途 | 数据来源 |
|------|------|----------|
| `design/task-center-requirements.md` | 架构设计文档 | 人工 |
| `design/phase5-task-center-landing-model.md` | **本文件**——着陆模型 | 人工 |
| `management/scheduling-cleanup-*.md` | 清理记录、迁移审计 | 人工 |

Knowledge 平面仅保留设计和决策记录，不包含任何 registry 或运行记录数据。

## 3. 边界规则

### 规则 1: 不镜像运行时快照

禁止在 truth 平面下创建 `instances/` 或等效目录。"当前正在运行哪些任务"由 SQLite cache 实时查询生成，不持久化到 `_truth/`。

**违反示例**：
- `_truth/task-center/instances/wf-001-running.json` ❌
- `_truth/task-center/status.yaml`（包含运行时状态） ❌

### 规则 2: 不镜像注册表

禁止在 delivery 平面下创建 registry 的副本或摘要。所有事实引用写入 `_truth/task-center/registry.yaml`。

**违反示例**：
- `_delivery/task-center/registry-cache.yaml` ❌
- `_delivery/task-center/task-summary.json` ❌

### 规则 3: Secret 引用替代明文

registry.yaml 中的 webhook/event 配置如果涉及密钥，仅使用 `secret_ref` 字段引用 `_secret/`。禁止在 truth 或 delivery 平面的任何文件中存储明文密钥。

**违反示例**：
- registry.yaml 中包含 `token: "xxxx"` ❌
- 运行记录中包含完整请求体密钥 ❌

### 规则 4: 治理任务与调度任务分离

- `tasks/`（治理任务）与 `_truth/task-center/`（调度任务）是两层互补 SSOT，互不替代
- 通过 `task_ref` / `depends_on` 双向引用，不创建依赖环
- 治理任务的 lifecycle（review→done）与调度任务的 lifecycle（调度执行）无关

### 规则 5: Hermes 兼容层

Hermes 只保留 **ingress + memory** 兼容价值，不再作为 Task Center 的新调度骨架：
- 现存 Hermes 脚本桥接仅作为 **legacy compatibility** 读取入口
- **禁止**为新任务继续扩张 `~/.hermes/scripts/` symlink 体系
- 新任务定义应指向 OMO/Task Center 直接拥有的脚本或受控适配路径
- Hermes 的 cron/task-definition 所有权在 Wave 1 Lane C（Hermes convergence transition）中彻底迁回 OMO / Task Center

## 4. 拒绝清单

以下操作在冻结的 landing 模型下**被拒绝**：

| 拒绝操作 | 原因 | 替代方案 |
|----------|------|----------|
| 在 truth 平面存储运行时状态 | 违反规则 1 — 不镜像运行时快照 | SQLite cache 实时查询 |
| 在 delivery 平面缓存 registry | 违反规则 2 — 不镜像注册表 | registry.yaml + force-resync |
| registry.yaml 中明文存密钥 | 违反规则 3 — secret 引用替代明文 | `secret_ref` 指向受管秘密存储 |
| 在 task-center schema 中加入 governance 字段（review/approve/phase） | 违反规则 4 — 治理与调度分离 | `tasks/` 治理任务体系 |
| 在 delivery 平面创建运行时数据之外的持久化文件 | 违反 plane-native 模型 | 确认数据属于哪个平面后再创建 |
| 为新任务继续创建 Hermes symlink | 违反规则 5 — Hermes 不再是新调度骨架 | 直接使用 OMO/Task Center 拥有的脚本路径 |

## 5. 落地状态

| 条目 | 状态 | 备注 |
|------|------|------|
| `_truth/task-center/` 目录创建 | ❌ 未创建 | Wave 1 阶段 2 MVP 建设 |
| `_delivery/task-center/` 目录创建 | ❌ 未创建 | Wave 1 阶段 2 MVP 建设 |
| 平面所有权表冻结 | ✅ 本文档 | Wave 0 冻结 |
| 边界规则写入 | ✅ 本文档 | Wave 0 冻结 |
| 拒绝清单写入 | ✅ 本文档 | Wave 0 冻结 |
| Wave 1+ 变更需 proposal | ✅ 已就位 | 关联 `P5-W0-PROPOSAL-MODEL-FREEZE` |

## 6. Wave 1+ 预留给此模型的变更空间

以下主题已知需要在 Wave 1+ 中通过 proposal 修改本文件，但不在 Wave 0 预判范围内：

- 联邦调度模式下 delivery 平面的扩展（跨机器运行记录聚合）
- 任务模板实例化后 truth 平面的模板条目管理规则
- 如果 hermes 在 Wave 1 Lane C 中完全退役，规则 5 的删除和 `~/.hermes/scripts/` 依赖的消除
- 新的触发类型（如有）在 truth 平面 trigger 目录下的扩展规则
