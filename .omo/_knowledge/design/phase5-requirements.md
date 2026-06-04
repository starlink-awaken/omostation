# Phase 5 需求文档：OMO 级流程治理

> **版本**: v0.1 (草案)
> **修订日期**: 2026-05-31
> **状态**: 初稿 — 待审阅
> **前置依赖**: [Task Center 需求 v0.2](./task-center-requirements.md)（已审阅待审批）| [四阶段演进路线图 v1.1](../../plans/evolution-roadmap-4phases.md)（Phase 1-4 已定义）
> **对标依据**: [行业交叉对标 28 方案](./reviews/review-cross-comparison.md) | [扩展对标 14+ 方案](./reviews/review-cross-comparison-supplement.md)
> **关联标准**: [SSOT 7 域 schema](../../standards/ssot-7-domain-schema.md) | [四平面 DOC-ARCH.md](../../DOC-ARCH.md) | [操作分级](../../standards/operation-levels.md)
>
> **最新规划收敛**: 本文保留为战略需求底稿；当前执行口径以下列文档为准：
> - [phase5-program-architecture.md](./phase5-program-architecture.md)
> - [phase5-program-plan.md](../../plans/archive/phase5-program-plan.md)
> - [phase5-entry-gate-checklist.md](../../plans/archive/phase5-entry-gate-checklist.md)

---

## 目录

1. [背景与定位](#1-背景与定位)
2. [目标与设计原则](#2-目标与设计原则)
3. [目标一：Durable Execution — 持久化执行](#3-目标一durable-execution--持久化执行)
4. [目标二：Governance Pipeline — 治理流水线](#4-目标二governance-pipeline--治理流水线)
5. [目标三：Script Auto-Discovery — 脚本自动发现](#5-目标三script-auto-discovery--脚本自动发现)
6. [目标四：Task Templates — 任务模板系统](#6-目标四task-templates--任务模板系统)
7. [目标五：Skill Federation — 技能声明化与 AI 调度融合](#7-目标五skill-federation--技能声明化与-ai-调度融合)
8. [架构演进](#8-架构演进)
9. [实施路线图](#9-实施路线图)
10. [风险与回退](#10-风险与回退)
11. [验收检查清单](#11-验收检查清单)
12. [附录 A: 术语表](#附录-a-术语表)
13. [附录 B: 对标方案索引](#附录-b-对标方案索引)
14. [附录 C: 变更日志](#附录-c-变更日志)

---

## 1. 背景与定位

### 1.1 Phase 1-4 回顾

| Phase | 主题 | 完成时间 | 核心交付 | 治理成熟度 |
|:-----:|------|:--------:|----------|:----------:|
| 1 | 基础设施补完 | 2026-06 (规划) | 4 核心系统就位、Agora 100+ MCP、LiteLLM 路由 | L0 — 各自为战 |
| 2 | 知识能力深化 | 2026-07 (规划) | 知识库深化、授权框架 RBAC、外部 Worker 协作 | L1 — 基本连通 |
| 3 | 自我进化闭环 | 2026-09 (规划) | KOS 推荐、MinerU 解析、nuwa-skill 执行 | L2 — 半自动 |
| 4 | 自主运行 | 2026-10+ (规划) | Worker Ops 生产化、高自主运行 | L2+ — 生产就绪 |
| **5** | **流程治理** | **2026-11+** | **见本文档** | **L3 — 可治理** |

Phase 1-4 的核心叙事是"让系统能跑起来"——基础设施、知识、协作、自主。但 2026-05-31 的 28 方案行业对标揭示了一个关键差距：

> **OMO 能"做事"，但还不能"管做事"。**

具体表现为：

| 差距 | 当前表现 | 对标方案的反例 |
|------|----------|----------------|
| 无持久化执行 | 进程 crash 后中间状态全丢 | Temporal 的 Event Sourcing / Inngest 的步级 checkpoint |
| 无治理流程 | 所有操作直接执行，无提案/审核/验证 | Camunda 的 BPMN / OpenSpec 的 7 阶段生命周期 |
| 手动注册脚本 | 每个脚本需手工写 registry.yaml | Windmill 的目录扫描自动注册 |
| 任务定义重复 | N 个相似任务写 N 次 YAML | Conductor 的工作流蓝图 / Kestra 的 YAML 模板 |
| 技能与调度分离 | AI 技能（kairon agents）和 Task Center 任务无关联 | Superpowers 的技能框架 / OpenSpec 的 prol→archive |

### 1.2 核心命题

**Phase 5 的核心命题**: 将 OMO 从"工具集合"进化成"可治理的系统"。

```
Phase 1-4 追求:    能做事（capability）
Phase 5 追求:      能管做事（governance）
                                       ↗
Phase 4 目标态:    生产就绪但无治理     → Phase 5: 治理就绪
                                       ↘
                   行业对标 28 方案      → Durable Execution + Governance + Auto-Discovery + Templates + Skill Federation
```

### 1.3 对标学习的 5 个核心洞察

| # | 洞察 | 对标来源 | 对 OMO 的启示 |
|---|------|----------|---------------|
| I1 | **步级状态持久化是趋势** | Temporal, Inngest, Trigger.dev, Restate | 进程重启后能从断点继续，而非从头重跑 |
| I2 | **人机混合流程是治理基石** | Camunda, OpenSpec | 重大变更需要"提案→审批→执行→验证" |
| I3 | **脚本自动注册消除心智负担** | Windmill | 脚本头 frontmatter 声明+目录扫描=零配置注册 |
| I4 | **模板化消除重复定义** | Conductor, Kestra, n8n | 写一次蓝图，Instance N 次 |
| I5 | **AI 技能与调度引擎应同源** | Superpowers, OpenSpec | 技能既是 AI 提示词，也是调度任务定义 |

---

## 2. 目标与设计原则

### 2.1 五个核心目标

```
Phase 5 五个目标
═══════════════════════════════════════════════════

 目标一   Durable Execution         持久化执行
          ───────────────────────────────────────
          步级状态持久化 → 进程崩溃可恢复 → 断点续跑
          
 目标二   Governance Pipeline       治理流水线
          ───────────────────────────────────────
          Proposal → Approval → Execute → Verify
          
 目标三   Script Auto-Discovery     脚本自动发现
          ───────────────────────────────────────
          脚本 frontmatter + 目录扫描 → 自动注册
          
 目标四   Task Templates            任务模板系统
          ───────────────────────────────────────
          写一次蓝图 → 多次实例化 → 参数覆盖
          
 目标五   Skill Federation          技能声明化与调度融合
          ───────────────────────────────────────
          AI 技能描述 = 任务定义 → 自然语言驱动调度
```

### 2.2 设计原则

| # | 原则 | 说明 | 对标依据 |
|---|------|------|----------|
| P1 | **增量演进，不重写** | 所有 change 在现有架构上增量加入，不破坏 Phase 4 交付物 | 所有成功方案都走增量演进 |
| P2 | **轻量优先** | 单机可运行，零外部依赖。不引入 Kafka/RabbitMQ/etc | 当前 OMO 最核心优势，需保持 |
| P3 | **后向兼容** | Phase 5 引入的 schema 变更必须兼容 Phase 4 的数据格式 | Temporal 的版本兼容策略 |
| P4 | **声明式配置** | 治理规则、自动发现、模板定义都用 YAML frontmatter | Windmill/Conductor/Kestra 的成功经验 |
| P5 | **渐进采用** | 用户可选择是否启用 Phase 5 的治理功能，不强制 | OpenSpec 的渐进式引入方式 |
| P6 | **可观测原生** | 所有治理流水线的状态、审批延迟、模板使用率默认可观测 | Task Center 已有的可观测内置模式 |

### 2.3 范围

#### in scope

- 步级 checkpoint 持久化（单机 SQLite + 文件 JSON）
- 治理流水线: proposal → approval → execution → verification
- 脚本 frontmatter 规范 + 目录扫描自动注册
- 任务模板 Blueprint 定义 + 实例化
- 技能声明 frontmatter + AI 调度融合
- 跨目标的数据一致性（trace_id 贯穿所有目标）

#### out of scope（当前版本）

- 分布式 Event Store（Temporal 模式，需要时进 Phase 6）
- 人工审批的 Web UI（保持 MCP + CLI）
- 任务市场 / 模板市场共享
- BPMN 可视化建模（保留 Camunda 作为 future 集成选项）
- 企业级合规认证（SOX/GxP）

---

## 3. 目标一：Durable Execution — 持久化执行

### 3.1 问题陈述

当前 Task Center 的执行模型是"单步执行、结果写入"：

```
触发 → 启动子进程 → 等待完成 → 写入运行记录 JSON → 完成
                                           ↑
                                   进程 crash，中间状态全丢
```

当任务执行过程中 `cron-service` 进程被 kill（或 `kill -9`）时：

- 正在运行的子进程变成孤儿进程
- 所有"执行中"状态丢失
- 重启后无法判断哪些任务需要 resume
- 耗时长的多步骤任务（如"先检查文件再处理再发通知"）完全不可恢复

**对标参考**: Temporal 的 Event Sourcing、Inngest/Trigger.dev 的步级 checkpoint 都解决了这个问题。它们的共同模式是将一次执行拆为多个 step，每个 step 完成后持久化中间结果。

### 3.2 需求详述

#### 3.2.1 步级 Checkpoint 机制

在 Task Center 的运行记录中引入 `steps` 数组：

```json
{
  "run_id": "run-6bb3cce7",
  "task_id": "wf-001",
  "status": "running",
  "steps": [
    {
      "id": "step-01",
      "name": "check-file",
      "status": "completed",
      "started_at": "2026-11-01T10:00:00Z",
      "completed_at": "2026-11-01T10:00:03Z",
      "output": {"file_exists": true, "file_size": 2048}
    },
    {
      "id": "step-02",
      "name": "process-data",
      "status": "running",
      "started_at": "2026-11-01T10:00:03Z",
      "output": null
    }
  ],
  "checkpoint_path": "_delivery/task-center/checkpoints/run-6bb3cce7/"
}
```

#### 3.2.2 Checkpoint 存储

| 项 | 规格 |
|----|------|
| **存储位置** | `_delivery/task-center/checkpoints/{run_id}/` |
| **文件格式** | 每 step 一个 JSON 文件 `step-{id}.json` |
| **写入策略** | 原子写入（写入临时文件 → rename） |
| **清理策略** | 运行完成 7 天后自动 housekeeping |
| **容量** | 假设每个 step ~1KB，100 个并发运行 × 10 step = ~1MB，可接受 |

#### 3.2.3 恢复流程

```
进程 crash
     │
     ▼
cron-service 重启
     │
     ▼
启动时扫描 _delivery/task-center/checkpoints/
     │
     ▼
发现 status=running 的运行记录
     │
     ├── 有 checkpoint → 从最后一个 completed step 继续
     │                   （跳过已完成的步骤，从第一个非 completed step 重试）
     │
     └── 无 checkpoint → 标记为 "killed"（参考 R3 建议）
```

#### 3.2.4 脚本接口

为了支持步级执行，脚本需要暴露 `--step` 参数：

```bash
# 传统模式（无持久化）
./scripts/kos-index.sh

# 步级模式（支持 checkpoint）
./scripts/kos-index.sh --step check-file   # 执行 step-01
./scripts/kos-index.sh --step process-data # 执行 step-02
./scripts/kos-index.sh --step notify       # 执行 step-03
```

或者通过脚本的 stdout 输出 step 标记：

```bash
# 脚本自动输出 step 信息
echo "::step::check-file  # 自动记录 step-01 checkpoint
# ... 处理逻辑 ...
echo "::step::process-data  # 自动记录 step-02 checkpoint
```

#### 3.2.5 任务定义中的步级配置

在 `registry.yaml` 的任务定义中增加可选字段：

```yaml
- id: wf-001
  type: cron
  name: "KOS 每日索引"
  script: "scripts/kos-index.sh"
  schedule: "0 6 * * *"
  # Phase 5 新增
  durable:
    enabled: true
    steps:
      - id: check-file
        name: "检查数据文件是否存在"
      - id: process-data
        name: "执行索引处理"
      - id: notify
        name: "发送处理结果通知"
    resume_strategy: skip_completed  # skip_completed | restart_step | restart_all
```

### 3.3 验收标准

| # | 验收条件 | 测试方法 |
|---|----------|----------|
| DC-1 | 步级 checkpoint 在每一步完成后原子写入 | 检查 `_delivery/.../checkpoints/` 目录 |
| DC-2 | 进程 crash 后重启能扫描 checkpoint 并恢复运行 | kill -9 cron-service → 重启 → 检查运行记录状态 |
| DC-3 | `skip_completed` 策略下跳过已完成的 step | 检查脚本是否被以正确的 `--step` 参数调用 |
| DC-4 | checkpoint 在运行完成 7 天后自动清理 | `housekeeping` 运行后检查目录 |
| DC-5 | 每运行记录最多 20 step 限制（防止无限增长） | 超限时任务标记为 `too_many_steps` |
| DC-6 | 运行记录 JSON 中 `steps` 数组存在且 Schema 有效 | JSON Schema 校验 |

---

## 4. 目标二：Governance Pipeline — 治理流水线

### 4.1 问题陈述

当前 OMO 的所有操作都是"直接执行"的：

| 操作 | 当前方式 | 风险 |
|------|----------|------|
| 修改 registry.yaml | 直接编辑并 commit | 无审查、无回滚确认 |
| 执行任务 | MCP `task_run` 直接启动 | 无环境门禁、无审批 |
| 切换 Phase | 手动改 `goals/current.yaml` | 无 Proposal/无影响评估 |
| 部署脚本 | 直接写入 `_truth/scripts/` | 无版本门禁、无 Compatibility 检查 |

**对标参考**:
- **OpenSpec** 定义了 7 阶段生命周期（proposal → spec → design → tasks → apply → verify → archive）
- **Camunda** 的 BPMN 提供了人工审批 + 自动执行的混合流程

Phase 5 的目标不是照搬 OpenSpec 的 7 阶段，而是为 OMO 制定**轻量级治理流水线**——在"直接执行"和"企业级 BPMN"之间找到平衡点。

### 4.2 需求详述

#### 4.2.1 治理级别

不同类型的操作需要不同级别的治理：

| 治理级别 | 适用场景 | 流程 | 审批人 | 参考对标 |
|:--------:|----------|------|--------|----------|
| L0 — 无治理 | 日常脚本执行、查看状态 | 直接执行 | 无 | Task Center 当前模式 |
| L1 — 记录治理 | 修改非关键任务、修改模板 | 自动记录变更日志 | 无（日志可追溯） | Airflow DAG 版本记录 |
| L2 — 提案治理 | 新增/删除任务、修改关键配置 | Proposal → Apply | 自我确认 | OpenSpec proposal |
| L3 — 审批治理 | Phase 变更、修改秘密、修改安全配置 | Proposal → Approval → Execute | 人工（CTO/自我） | Camunda Human Task |

#### 4.2.2 Proposal 文件规范

在 `_truth/task-center/` 新增 `proposals/` 目录：

```yaml
# _truth/task-center/proposals/p-001.yaml
---
id: p-001
title: "新增 KOS 夜间增量索引任务"
status: approved             # draft | proposed | approved | rejected | executed | archived
level: L2                    # L0 | L1 | L2 | L3
author: "AI Agent"
created_at: "2026-11-01T10:00:00Z"
updated_at: "2026-11-01T10:30:00Z"

# L2+ 需要
rationale: "当前全量索引在 500K+ 文档时耗时 > 30min，需增量索引降低延迟"

# L2+ 需要
impact:
  risk: low                  # low | medium | high | critical
  rollback: "删除 task 条目并恢复旧配置"
  affected_tasks: ["wf-001"]
  affects_sla: false

# L3 需要
approval:
  required: false
  approved_by: null
  approved_at: null
  comments: ""

# 执行结果
execution:
  applied_at: "2026-11-01T10:30:00Z"
  applied_by: "cron-service (auto)"
  result: success            # success | failed | rolled_back
  rollback_at: null
```

#### 4.2.3 治理流程集成

治理流水线与 Task Center 的交互流程：

```
开发者/Agent                          Task Center                      治理流水线
───────────                          ───────────                      ──────────
     │                                     │                              │
     │  MCP task_propose                    │                              │
     │────────────────────────────────────►│                              │
     │                                     │  写入 proposals/p-001.yaml    │
     │                                     │─────────────────────────────►│
     │                                     │                              │
     │                                     │         level=L2             │
     │                                     │   ┌────────────────────┐    │
     │                                     │   │ 自动验证 → 批准     │    │
     │                                     │   └────────────────────┘    │
     │                                     │                              │
     │                                     │  proposals/p-001 → approved │
     │                                     │◄─────────────────────────────│
     │                                     │                              │
     │  MCP task_apply p-001               │                              │
     │────────────────────────────────────►│                              │
     │                                     │ 校验 proposal → 执行变更     │
     │                                     │                              │
     │  ← ok, 变更已应用                   │                              │
```

对于 L3（需要人工审批）的操作：

```
开发者/Agent                          Task Center                      人类
───────────                          ───────────                      ────
     │                                     │                              │
     │  MCP task_propose                    │                              │
     │────────────────────────────────────►│                              │
     │                                     │  写入 proposals/             │
     │                                     │  发通知: "请审批 p-002"      │
     │                                     │─────────────────────────────►│
     │                                     │                              │
     │                                     │◄──── MCP task_approve ───────│
     │                                     │  p-002                       │
     │                                     │                              │
     │  ← wait for approval                │                              │
```

#### 4.2.4 MCP 工具扩展

新增 4 个 MCP 工具：

| 工具 | 功能 | 权限 |
|------|------|------|
| `task_propose` | 创建/更新 proposal | 所有用户 |
| `task_approve` | 批准/拒绝 proposal | L3 操作需要 |
| `task_apply` | 执行已批准的 proposal | 仅当 proposal 状态为 approved |
| `task_proposal_list` | 列出所有 proposal（可过滤状态） | 所有用户 |

### 4.3 验收标准

| # | 验收条件 | 测试方法 |
|---|----------|----------|
| GP-1 | L0 操作直接执行，不经过治理流水线 | 执行日常任务检查 proposal 目录无新增 |
| GP-2 | L2 操作必须经过 proposal → 自动批准 → apply | 修改 registry.yaml 后 check proposal |
| GP-3 | L3 操作在审批前不会被执行 | 创建 L3 proposal → 尝试 apply → 拒绝 |
| GP-4 | proposal 状态流转合法: draft→proposed→approved→executed | 非法状态转换被拒绝 |
| GP-5 | 治理流水线所有操作写入审计日志 | 检查 MCP 操作审计记录 |
| GP-6 | `task_apply` 在 proposal 非 approved 时返回错误 | 测试直接跳过审批 |

---

## 5. 目标三：Script Auto-Discovery — 脚本自动发现

### 5.1 问题陈述

当前 Task Center 要求每个脚本手动注册到 `registry.yaml`：

```yaml
# registry.yaml — 手动维护
- id: wf-001
  type: cron
  script: "scripts/kos-index.sh"
  schedule: "0 6 * * *"
  # ... 更多手动字段
```

当脚本数量增长到 100+ 时：
- 新增脚本后忘记注册 → 不会执行
- 删除脚本后忘记清理 registry → 任务断裂
- 每个脚本的元数据（名称、描述、参数）在 registry.yaml 和脚本注释中各写一次 → 双源不一致

**对标参考**:
- **Windmill**: 扫描目录自动发现脚本，自动生成 webhook/cron 入口
- **crontab**: 每个脚本需要手动添加一行，但至少在同一位置集中管理

### 5.2 需求详述

#### 5.2.1 脚本 Frontmatter 规范

在脚本文件头部增加 YAML frontmatter：

```bash
#!/bin/bash
# ---
# name: "KOS 每日索引"
# description: "执行 KOS 每日全量索引，生成向量嵌入"
# type: cron
# schedule: "0 6 * * *"
# tags: [kos, index, daily]
# timeout: 1800
# retry:
#   max_attempts: 3
#   backoff: "fixed"
#   interval: 60
# durable: false
# params:
#   - name: "batch_size"
#     type: integer
#     default: 100
#     description: "每批处理的文档数"
#   - name: "dry_run"
#     type: boolean
#     default: false
#     description: "预览模式，不实际写入"
# ---

# 实际的脚本逻辑
echo "Starting KOS index..."
```

支持的 frontmatter 字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `name` | string | 是 | 任务名称 |
| `description` | string | 否 | 任务描述 |
| `type` | string | 是 | 任务类型: cron/once/longrun/webhook/event |
| `schedule` | string | type=cron 时必填 | cron 表达式 |
| `tags` | string[] | 否 | 标签，用于分类和搜索 |
| `timeout` | int | 否 | 超时时间（秒），默认 300 |
| `retry` | object | 否 | 重试策略 |
| `durable` | bool | 否 | 是否启用 Durable Execution（目标一） |
| `params` | object[] | 否 | 参数声明（用于 MCP 自动生成参数校验） |

#### 5.2.2 自动发现流程

```
目录扫描机制
══════════════

扫描路径:  _truth/scripts/ (递归)
           _truth/scripts/*/ (项目级脚本目录)
           
扫描触发:
  - cron-service 启动时 (全量扫描)
  - 文件变化时 (通过 kqueue/FSEvents 监控 _truth/scripts/)
  - 手动触发: MCP task_scan_scripts

自动注册:
  1. 扫描目录
  2. 解析每个脚本的 frontmatter
  3. 与 registry.yaml 对比
     - 新增脚本 → 追加到 registry.yaml auto- 前缀段
     - 删除脚本 → 标记为 broken（不自动删除 registry 条目）
     - frontmatter 变更 → 更新 registry.yaml 字段
  
注册位置:
  registry.yaml 新增 auto: 段，与手动注册分离：
  
  ```yaml
  # 手动注册段（优先级高）
  tasks:
    - id: wf-001
      ...
  
  # 自动发现段（由扫描器维护，不要手动修改）
  auto:
    - id: auto:kos-index
      name: "KOS 每日索引"
      type: cron
      script: "scripts/kos-index.sh"
      ...
  ```
```

#### 5.2.3 冲突处理规则

| 场景 | 处理方式 |
|------|----------|
| 手动注册与自动发现 ID 冲突 | 手动注册优先，自动发现的同名任务被跳过 |
| frontmatter 语法错误 | 跳过该脚本，记录错误日志 |
| 脚本文件被删除 | registry 中的 auto 条目标记为 `broken`，不自动删除 |
| 脚本文件内容被修改（frontmatter 变更） | 自动更新 registry 中的对应 auto 条目 |

#### 5.2.4 MCP 工具扩展

| 工具 | 功能 |
|------|------|
| `task_scan_scripts` | 手动触发全量目录扫描 |
| `task_auto_registry_diff` | 显示当前 auto 注册与目录实际内容的差异 |
| `task_auto_cleanup` | 清理已标记为 broken 超过 7 天的 auto 条目 |

### 5.3 验收标准

| # | 验收条件 | 测试方法 |
|---|----------|----------|
| SA-1 | 带 frontmatter 的脚本放入 `_truth/scripts/` 后自动出现在 registry | 放置脚本 → 触发扫描 → 检查 registry.yaml |
| SA-2 | 删除脚本后 auto 条目标记为 broken | 删除 → 检查 registry.yaml |
| SA-3 | frontmatter 变更后 registry 自动更新 | 修改 schedule → 检查 registry.yaml |
| SA-4 | 语法错误的 frontmatter 不阻塞其他脚本的扫描 | 放入错误 frontmatter → 检查其他脚本是否正常注册 |
| SA-5 | 手动注册的条目不会被自动发现覆盖 | 手动注册 wf-xxx → 放置同名脚本 → 手动条目保持 |

---

## 6. 目标四：Task Templates — 任务模板系统

### 6.1 问题陈述

当前 OMO 中大量任务结构相似但参数不同：

| 模板模式 | 实例数量 | 差异点 |
|----------|:--------:|--------|
| "每 X 分钟监听文件目录" | 15+ 任务 | 监听路径不同、目标脚本不同 |
| "每日执行清理脚本" | 8+ 任务 | 清理目录不同、保留天数不同 |
| "通过 webhook 接收通知 → 触发脚本" | 5+ 任务 | webhook secret 不同、目标脚本不同 |

每个实例都需要写完整的 YAML 定义。如果定义 100 个任务，约 60% 是重复模式。

**对标参考**:
- **Conductor**: 工作流蓝图（blueprint）与执行实例分离，定义可复用
- **Kestra**: YAML 的 `!include` 和模板引用机制
- **n8n**: 工作流模板市场

### 6.2 需求详述

#### 6.2.1 Blueprint 定义

在 `_truth/task-center/` 新增 `blueprints/` 目录：

```yaml
# _truth/task-center/blueprints/bp-file-watch.yaml
---
# === 文件目录监听 模板 ===
id: bp-file-watch
name: "文件目录监听模板"
description: "监听指定目录的文件变更事件，触发对应的处理脚本"

# 必须由实例填写
required_params:
  - name: watch_dir
    type: string
    description: "监听的目录路径"
  - name: handler_script
    type: string
    description: "文件变更时执行的脚本路径"

# 可选参数（有默认值）
optional_params:
  - name: event_types
    type: string[]
    default: ["create", "modify"]
    description: "监听的事件类型"
  - name: cooldown
    type: integer
    default: 5
    description: "同一文件的冷却时间(秒)"

# 模板生成的 task 定义
task_template:
  type: event
  source: fs
  watch_path: "{{ watch_dir }}"           # 模板变量
  script: "{{ handler_script }}"
  cooldown: "{{ cooldown }}"
  timeout: 300
  retry:
    max_attempts: 2
    backoff: fixed
    interval: 5
  tags: ["auto-generated", "file-watch"]
```

#### 6.2.2 实例化

在 `registry.yaml` 中引用模板：

```yaml
tasks:
  # 传统手动注册
  - id: wf-001
    type: cron
    name: "KOS 每日索引"
    ...

  # 模板实例化（Phase 5）
  - id: kf-watch
    template: bp-file-watch
    params:
      watch_dir: "_truth/kos/data/"
      handler_script: "scripts/kos-process.sh"
      event_types: ["create"]
```

实例化后等价于展开为完整 YAML：

```yaml
  - id: kf-watch
    type: event
    source: fs
    watch_path: "_truth/kos/data/"
    script: "scripts/kos-process.sh"
    cooldown: 5
    timeout: 300
    retry:
      max_attempts: 2
      backoff: fixed
      interval: 5
    tags: ["auto-generated", "file-watch"]
```

#### 6.2.3 变量语法

| 语法 | 示例 | 说明 |
|------|------|------|
| `{{ param_name }}` | `{{ watch_dir }}` | 引用参数值 |
| `{{ param_name \| default("val") }}` |  | 带默认值 |
| `{{ param_name \| upper }}` |  | 管道转换（预留） |

#### 6.2.4 内置 Blueprint 集合

Phase 5 附带以下内置 blueprints：

| Blueprint ID | 类型 | 说明 |
|-------------|------|------|
| `bp-cron` | cron | 标准定时任务模板 |
| `bp-file-watch` | event(fs) | 文件目录监听模板 |
| `bp-webhook-receiver` | webhook | Webhook 接收器模板 |
| `bp-cleanup` | cron | 定时清理任务模板（可配置保留天数） |
| `bp-hermes-sync` | cron | Hermes 桥接同步模板 |

### 6.3 验收标准

| # | 验收条件 | 测试方法 |
|---|----------|----------|
| TT-1 | 模板实例化后的任务与手动注册的效果一致 | 对比展开后的 YAML |
| TT-2 | 缺少必填参数时实例化失败 | 注册时不提供 watch_dir → 错误 |
| TT-3 | 可选参数使用默认值 | 不提供 cooldown → 检查任务定义中的 cooldown=5 |
| TT-4 | 模板支持嵌套变量引用 | watch_path 正确展开 |
| TT-5 | 内置 5 个 blueprint 可用 | 每个实例化并验证 |
| TT-6 | 同一模板多次实例化产生独立的 task | 注册 3 个文件监听 → 检查 3 个独立任务 |

---

## 7. 目标五：Skill Federation — 技能声明化与 AI 调度融合

### 7.1 问题陈述

当前 OMO 的 AI 技能体系存在两个割裂：

```
kairon 的 Agent (Python 类)                Task Center 的任务 (YAML)
─────────────────────────────             ───────────────────────────
Agent: code-review                        task: "每日自动代码审查"
  ├── prompt: "审查 PR 代码质量"               ├── type: cron
  ├── tools: [grep, read, write]             ├── schedule: "0 8 * * *"
  └── model: gpt-4                           └── script: "scripts/code-review.sh"
                                            
两者无任何关联 → AI 技能无法被定时/事件触发
                → 调度任务不知道它调用了哪个 AI 能力
```

**对标参考**:
- **Superpowers**: 技能是 .md 文件（自然语言可读），组合成工作流
- **OpenSpec**: 文档驱动开发，从 proposal 到 archive 全生命周期覆盖
- **Task Center × OpenSpec 融合映射**（已在交叉审阅中定义）

### 7.2 需求详述

#### 7.2.1 技能声明文件

在 `_truth/skills/` 目录放置声明式技能定义：

```yaml
# _truth/skills/code-review.yaml
---
# === AI 技能声明 ===
id: skill-code-review
name: "代码审查"
version: "1.0.0"
description: "对指定 PR 或目录执行自动化代码审查"

# 技能类型
type: agent                     # agent | script | pipeline

# 触发方式（与 Task Center 调度集成）
triggers:
  - type: cron
    schedule: "0 8 * * 1-5"    # 工作日自动触发
    name: "每日自动审查"
  - type: webhook
    path: "/webhook/github-pr"  # GitHub PR webhook 触发

# 执行配置
execution:
  engine: kairon                  # agent → kairon agent
  agent_id: "code-review-agent"   # 对应的 kairon Agent
  prompt: |
    你是 OMO 代码审查助手。请对当前工作区的变更进行审查：
    1. 检查代码风格是否符合项目规范
    2. 识别潜在的安全漏洞
    3. 建议架构改进
  tools: ["grep", "read", "diff", "github"]
  model: "gpt-4"

# 输入输出
input:
  - name: "target_dir"
    type: string
    description: "审查的目标目录"
    default: "."
  - name: "pr_number"
    type: integer
    description: "GitHub PR 编号（webhook 触发时自动填充）"

output:
  type: markdown
  path: "_delivery/reviews/{run_id}/review.md"

# 调度控制（从 Task Center 继承）
timeout: 600
retry:
  max_attempts: 2
  backoff: exponential

# 标签
tags: ["ai", "code-quality", "automation"]
```

#### 7.2.2 技能到任务的自动映射

当技能声明文件被添加到 `_truth/skills/` 时，系统自动：

1. 解析技能的 `triggers` 字段
2. 为每个 trigger 自动生成一个 Task Center 任务（使用 auto-discovery 机制）
3. 注册到 registry.yaml 的 `auto:` 段

```yaml
# 自动生成的 Task Center 条目
auto:
  - id: "skill:code-review:daily"
    name: "每日自动代码审查"
    type: cron
    schedule: "0 8 * * 1-5"
    script: "kairon agent skill-code-review"
    skill_ref: "skill-code-review"
    
  - id: "skill:code-review:webhook"
    name: "GitHub PR 代码审查"
    type: webhook
    path: "/webhook/github-pr"
    script: "kairon agent skill-code-review"
    skill_ref: "skill-code-review"
```

#### 7.2.3 融合工作流

最终形态：一个技能可以触发一次完整的 OMO 跨系统工作流：

```
技能触发
  │
  ▼
调度引擎 (Task Center)
  │
  ├── 执行前检查治理流水线 (目标二)
  │     └── L2/L3 操作等待审批
  │
  ├── 持久化执行 checkpoint (目标一)
  │     └── 每一步中间状态可恢复
  │
  ├── 调用 AI Agent (kairon)
  │     └── agent 使用声明的 tools + model
  │
  └── 写入运行记录 + 交付物
        └── gp 报告到 `_delivery/reviews/`
```

#### 7.2.4 MCP 工具扩展

| 工具 | 功能 |
|------|------|
| `skill_list` | 列出所有可用技能 |
| `skill_run` | 手动触发技能执行 |
| `skill_register` | 注册技能文件到 Task Center |
| `skill_status` | 查看技能及其关联任务的运行状态 |

### 7.3 验收标准

| # | 验收条件 | 测试方法 |
|---|----------|----------|
| SF-1 | 技能文件放入 `_truth/skills/` 后自动生成 Task Center 任务 | 放置技能 → 检查 registry.yaml auto: 段 |
| SF-2 | 技能触发类型为 cron 时按 schedule 定时执行 | 等待下一个 tick → 检查运行记录 |
| SF-3 | 技能触发类型为 webhook 时按路径响应 | curl 到 webhook 路径 → 检查运行记录 |
| SF-4 | 技能执行时调用指定的 kairon agent | 检查 agent 执行日志 |
| SF-5 | 技能执行结果写入 `_delivery/` 对应目录 | 检查交付物文件 |

---

## 8. 架构演进

### 8.1 Phase 5 整体架构

```
Phase 4 架构                              Phase 5 新增
═══════════════                          ══════════════

 治理面 _truth/                          治理面 _truth/ (扩展)
 ├── task-center/                        ├── task-center/
 │   ├── registry.yaml                     │   ├── registry.yaml (扩展 auto: 段)
 │   └── ...                              │   ├── proposals/       ← 新增
 │                                        │   └── blueprints/      ← 新增
 ├── scripts/ (手动管理)                   ├── scripts/ (扩展 frontmatter)
 │   └── *.sh                             │   └── *.sh + frontmatter
 │                                        ├── skills/             ← 新增
 │                                        │   └── *.yaml (技能声明)
 │                                        └── playbook/           ← 新增(运维)
 │                                            └── *.md
 调度层 _delivery/
 ├── task-center/                         调度层 _delivery/ (扩展)
 │   ├── runs/                            ├── task-center/
 │   └── ...                              │   ├── runs/
 │                                        │   ├── checkpoints/     ← 新增
 │                                        │   └── proposals/       ← 新增
 │                                        └── skills/             ← 新增
 │                                            └── {skill_id}/
                                                └── reviews/
                                                └── outputs/
 
 MCP 工具 11 个                           MCP 工具 11+8 个
  (CRUD + 执行 + 状态)                     新增: task_propose, task_approve,
                                          task_apply, task_scan_scripts,
                                          skill_list, skill_run,
                                          skill_register, skill_status
```

### 8.2 四平面增量

| 平面 | Phase 5 新增内容 | 说明 |
|------|-----------------|------|
| **控制面** | `goals/current.yaml` 扩展治理级别字段 | 设定当前允许的最大治理级别 |
| **事实面** | `_truth/task-center/proposals/`、`_truth/task-center/blueprints/`、`_truth/skills/` | 新的 SSOT 实体 |
| **知识面** | Phase 5 架构文档、Blueprint 使用指南、技能声明指南 | 使用文档 |
| **交付面** | `_delivery/task-center/checkpoints/`、`_delivery/task-center/proposals/`、`_delivery/skills/` | 新交付物 |

### 8.3 数据流变更

```
Phase 4 数据流:
  registry.yaml → cron-service → 子进程 → 运行记录 JSON
  
Phase 5 数据流:
  skills/ → auto-discovery → registry.yaml (auto:) → cron-service
  blueprints/ → 实例化 → registry.yaml (模板展开)
  proposals/ → governance pipeline → registry.yaml 变更 / 任务执行
  durable: true → checkpoint 写入 _delivery/checkpoints/
```

### 8.4 依赖关系

```
目标一 (Durable Execution)
  └── 依赖: Task Center v0.2 的运行记录系统

目标二 (Governance Pipeline)
  └── 依赖: 目标一 (检查点用于回退)
  └── 依赖: Task Center MCP 工具集

目标三 (Auto-Discovery)
  └── 依赖: Task Center registry.yaml 扩展 (auto: 段)

目标四 (Templates)
  └── 依赖: 目标三 (模板实例化使用 auto-discovery 的注册机制)

目标五 (Skill Federation)
  └── 依赖: 目标二 (技能触发器需要治理级别判断)
  └── 依赖: 目标三 (技能自动注册使用 auto-discovery)
  └── 依赖: 目标四 (技能作为高级 template)
```

---

## 9. 实施路线图

### 9.1 总体时间线

```
2026-11                    2026-12                    2027-01
  │                          │                          │
  ├─ Wave 1 ──────────────┤  │                          │
  │  基础治理               │  │                          │
  │  (2 周)                │  │                          │
  │                        ├── Wave 2 ────────────────┤│
  │                        │  脚本生态                 ││
  │                        │  (3 周)                  ││
  │                        │                          ├── Wave 3 ─────┤
  │                        │                          │  技能融合      │
  │                        │                          │  (3 周)       │
```

### 9.2 Wave 1: 基础治理（2 周）

**目标**: Durable Execution + Governance Pipeline 可用

| 周 | 交付物 | 依赖 |
|:--:|--------|:----:|
| W1 | 步级 checkpoint 存储：`steps` 数组 Schema + checkpoint 目录 + 原子写入 | Task Center 运行记录 |
| W1 | 恢复机制：启动时扫描 checkpoint → resume | W1 checkpoint 存储完成 |
| W2 | Proposal 规范 + `proposals/` 目录 | 无 |
| W2 | MCP 工具 `task_propose` / `task_approve` / `task_apply` | W2 proposal 规范完成 |
| W2 | 治理级别 L0-L3 实现 + 状态机 | W2 MCP 工具完成 |

### 9.3 Wave 2: 脚本生态（3 周）

**目标**: Auto-Discovery + Templates 可用

| 周 | 交付物 | 依赖 |
|:--:|--------|:----:|
| W3 | 脚本 frontmatter 规范 + 解析器 | 无 |
| W3 | 目录扫描机制（启动 + 文件变更触发） | W3 解析器 |
| W3 | registry.yaml `auto:` 段写入 | W3 目录扫描 |
| W4 | Blueprint 规范 + 模板引擎 | Wave 1 完成 |
| W4 | 内置 5 个 blueprint | W4 模板引擎 |
| W4 | 模板实例化在 registry.yaml 中展开 | W4 blueprints |
| W5 | 冲突处理（手动 vs auto） | W3 auto-discovery |
| W5 | MCP 工具 `task_scan_scripts` / `task_auto_registry_diff` | W5 冲突处理 |
| W5 | 治理流水线验收 + Safety Sprint | 所有 W3-W5 完成 |

### 9.4 Wave 3: 技能融合（3 周）

**目标**: Skill Federation 可用，五个目标全部集成

| 周 | 交付物 | 依赖 |
|:--:|--------|:----:|
| W6 | Skill 声明规范 + `_truth/skills/` 目录 | Wave 2 auto-discovery |
| W6 | 技能→任务自动映射（注册到 auto: 段） | W6 规范 |
| W7 | MCP 工具 `skill_list` / `skill_register` / `skill_run` | W6 自动映射 |
| W7 | 技能执行引擎桥接（调用 kairon agent） | W7 MCP 工具 |
| W7 | 技能运行记录写入 `_delivery/skills/` | W7 执行引擎 |
| W8 | 端到端集成验收：技能 → 治理 → checkpoint → 交付物 | 所有 W6-W7 完成 |
| W8 | 完整 A 类验收（57 项） | W8 集成验收 |

### 9.5 依赖关系管理

| 外部依赖 | 说明 | 风险 |
|----------|------|:----:|
| Task Center v0.2 实现 | Phase 5 所有目标都依赖 Task Center 运行 | 🔴 如果 v0.2 未按期完成，Phase 5 整体延期 |
| kairon agent 接口 | Skill Federation 需要 kairon agent 的可编程调用 | 🟡 需提前确认 agent 的 CLI/API 接口 |
| fastmcp 版本兼容 | MCP 工具扩展依赖 fastmcp | 🟢 版本兼容性风险低 |

---

## 10. 风险与回退

### 10.1 风险评估

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|------|:----:|:----:|----------|
| RC-1 | Task Center v0.2 未按时交付，Phase 5 无基础 | 🔴高 | 🔴高 | Wave 1 前确认 v0.2 状态；如果延期，先做 frontmatter 规范（独立于 v0.2） |
| RC-2 | checkpoint 存储导致 I/O 瓶颈 (100+ 步 × 秒级写入) | 🟡中 | 🟡中 | 写入使用异步队列 + 批量 flush；设置每运行记录 20 step 上限 |
| RC-3 | Frontmatter 引入安全风险（在 shell 脚本头部解析 YAML） | 🟡中 | 🔴高 | 解析器必须在子进程外部运行；禁止在 shell 脚本中直接 eval |
| RC-4 | 治理流水线增加操作延迟 | 🟢低 | 🟡中 | L2 自动审批 < 1s，L3 人工审批由人类等待 |
| RC-5 | Blueprint 模板引擎太复杂超出当前架构 | 🟡中 | 🟡中 | Minimum Viable Template：只支持变量替换，不支持逻辑/循环 |
| RC-6 | Skill Federation 需要 kairon agent 的接口调整 | 🟡中 | 🟡中 | 先做技能自动注册（目标三扩展），agent 桥接放 Wave 3 |
| RC-7 | 五个目标之间的依赖链导致延期 | 🟡中 | 🔴高 | 每个目标独立可交付（但会丢失端到端集成）；Wave 1 不依赖 Wave 2 |

### 10.2 回退方案

| 场景 | 回退步骤 |
|------|----------|
| Wave 1 Durable Execution 性能不达标 | 回退到 Phase 4 的非持久化模式，checkpoint 作为可选项 |
| Wave 2 Auto-Discovery 出现冲突处理 BUG | 停止自动扫描，保持手动注册。自动注册段在 registry.yaml 中标记为 disabled |
| Wave 3 Skill Federation 与 kairon agent 不兼容 | 技能声明只做文档级定义（AI 可读），不做自动调度。保留手动调度 |
| 任一波次延期 > 1 周 | 裁剪范围：保留核心（Durable + Governance），推迟 Templates + Skills |

---

## 11. 验收检查清单

### 11.1 目标一: Durable Execution（6 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| D-1 | `steps` 数组 Schema 定义在 registry.yaml 中生效 | 功能 | registry.yaml 解析校验 |
| D-2 | checkpoint 在每一步完成后原子写入 | 功能 | 目录文件检查 |
| D-3 | 进程 crash 后重启能 checkpoint 恢复 | 可靠性 | kill -9 测试 |
| D-4 | `skip_completed` 恢复策略正确实现 | 功能 | 日志检查 |
| D-5 | 20 step 上限限制生效 | 安全 | 超限测试 |
| D-6 | checkpoint 7 天后自动清理 | 运维 | housekeeping 测试 |

### 11.2 目标二: Governance Pipeline（6 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| G-1 | L0 操作直接执行，无治理 | 功能 | 操作日志检查 |
| G-2 | L2 操作 proposal → auto-approve → apply | 功能 | 状态机检查 |
| G-3 | L3 操作等待人工审批 | 功能 | 审批前 apply 拒绝 |
| G-4 | proposal 状态流转合法 | 功能 | 非法状态测试 |
| G-5 | 所有治理操作写入审计日志 | 安全 | MCP 审计记录 |
| G-6 | MCP `task_approve` 在非 L3 操作时返回警告 | 功能 | L2 操作调用 approve |

### 11.3 目标三: Script Auto-Discovery（5 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| A-1 | 带 frontmatter 的脚本自动注册到 registry | 功能 | 放置→检查 |
| A-2 | 删除脚本后 auto 条目标记 broken | 功能 | 删除→检查 |
| A-3 | frontmatter 变更自动更新 registry | 功能 | 修改→检查 |
| A-4 | 手动注册不被自动覆盖 | 功能 | 同名冲突测试 |
| A-5 | 语法错误的 frontmatter 不阻塞其他脚本 | 健壮性 | 错误 frontmatter 测试 |

### 11.4 目标四: Task Templates（6 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| T-1 | 模板实例化后与手动注册效果一致 | 功能 | YAML 展开比较 |
| T-2 | 缺少必填参数报错 | 功能 | 缺少参数测试 |
| T-3 | 可选参数默认值生效 | 功能 | 不提供→默认值 |
| T-4 | 变量展开正确 | 功能 | 字符串替换检查 |
| T-5 | 内置 5 个 blueprint 可用 | 功能 | 每个实例化 |
| T-6 | 同一模板多次实例化独立 | 功能 | 多实例注册 |

### 11.5 目标五: Skill Federation（5 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| S-1 | 技能文件自动生成 Task Center 任务 | 功能 | 放置→检查 |
| S-2 | cron trigger 按 schedule 执行 | 功能 | tick 检查 |
| S-3 | webhook trigger 按路径响应 | 功能 | curl 测试 |
| S-4 | 技能调用 kairon agent | 集成 | agent 日志检查 |
| S-5 | 交付物写入 `_delivery/skills/` | 功能 | 目录检查 |

### 11.6 安全验收（Safety Sprint，5 项）

| # | 项目 | 类型 | 验收方式 |
|---|------|:----:|----------|
| SS-1 | Frontmatter 解析器在子进程外部运行（不 eval） | 安全 | 代码审查 |
| SS-2 | 治理流水线的 approve/reject 记录不可篡改 | 安全 | 文件权限检查 |
| SS-3 | Checkpoint 文件权限 600 | 安全 | 权限检查 |
| SS-4 | skill 声明中的 prompt 字段限制长度（max 4096） | 安全 | 超长测试 |
| SS-5 | 所有新 MCP 工具遵循现有返回契约 `{ok, data/error}` | 标准 | MCP 标准检查 |

---

## 附录 A: 术语表

| 术语 | 说明 |
|------|------|
| **Checkpoint** | 任务执行过程中持久化的中间状态快照 |
| **Durable Execution** | 使任务能够从进程崩溃中恢复执行的能力 |
| **Governance Level L0-L3** | 治理流水线的四级操作分级 |
| **Proposal** | 变更请求文档，描述变更原因、影响和回退方案 |
| **Frontmatter** | 脚本文件头部的 YAML 元数据声明块 |
| **Auto-Discovery** | 自动扫描目录并注册脚本任务的机制 |
| **Blueprint** | 可复用的任务模板定义 |
| **Instance** | 从 Blueprint 实例化生成的具体任务 |
| **Skill** | 声明式 AI 能力定义，包含触发方式和执行配置 |
| **Skill Federation** | 技能系统与调度系统的统一管理机制 |

## 附录 B: 对标方案索引

| 方案 | 对标维度 | 文档位置 |
|------|----------|----------|
| **Temporal** | Durable Execution (核心) | `review-cross-comparison.md` §1.1-3.1 |
| **Inngest** | 步级 Checkpoint | `review-cross-comparison-supplement.md` §S4 |
| **Trigger.dev** | 步级 Checkpoint | `review-cross-comparison-supplement.md` §S4 |
| **Camunda** | Governance Pipeline (核心) | `review-cross-comparison-supplement.md` §S2 |
| **OpenSpec** | Governance Pipeline (核心) | `review-cross-comparison.md` §3 |
| **Windmill** | Script Auto-Discovery (核心) | `review-cross-comparison-supplement.md` §S3 |
| **Conductor** | Task Templates (核心) | `review-cross-comparison-supplement.md` §S1 |
| **Kestra** | Task Templates + YAML 声明 | `review-cross-comparison-supplement.md` §S3 |
| **Superpowers** | Skill Federation (核心) | `review-cross-comparison-supplement.md` §S5 |
| **n8n** | 工作流模板 / 连接器生态 | `review-cross-comparison.md` §1.1 |

## 附录 C: 变更日志

| 版本 | 日期 | 变更 |
|:----:|:----:|------|
| v0.1 | 2026-05-31 | 初版草案。基于 28 方案行业对标提炼 5 个核心目标定义 Phase 5 |

---

> **本文件是 Phase 5 的需求规格书草案，尚未经过审阅。**
> **预期审阅方式**: 对标审阅（与 28 方案对比）+ 可行性审阅（与现有架构对比）+ 安全审阅。
> **前置依赖**: Task Center v0.2 实现完成并运行稳定后启动 Phase 5 评估。
