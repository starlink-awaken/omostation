# Task Center 需求文档

> **版本**: v0.2.1 (收敛修订版)
> **修订日期**: 2026-05-31
> **状态**: 已审阅 — 待审批
> **审阅报告**:
> - [架构审阅](./reviews/review-architecture.md) — 3 CRITICAL, 5 HIGH
> - [安全红队审阅](./reviews/review-security-redteam.md) — 3 CRITICAL, 5 HIGH
> - [运维可靠性审阅](./reviews/review-ops-reliability.md) — 3 CRITICAL, 4 HIGH
> - **三路审阅结论已吸收到当前约束；剩余架构取舍以本版正文为准**
> **关联文档**: [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) | [四平面架构 DOC-ARCH.md](../../DOC-ARCH.md) | [治理任务规范](../../tasks/README.md) | [arcnode schema](https://github.com/xiamingxing/arcnode) | [scheduling-cleanup-2026-05-31.md](../management/scheduling-cleanup-2026-05-31.md)
> 本文档是历史阶段的需求与设计输入，保留当时的调度断裂审计、Task Center 目标、架构约束与路线图，不是当前调度状态、当前 registry 真相或当前执行许可 SSOT。
> 当前执行与状态以 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/tasks/active/` 以及当前 owner-plane 实体为准。

---

## 目录

1. [背景与问题陈述](#1-背景与问题陈述)
2. [目标与范围](#2-目标与范围)
3. [架构设计](#3-架构设计)
4. [详细需求](#4-详细需求)
5. [实施路线图](#5-实施路线图)
6. [风险与回退](#6-风险与回退)
7. [验收检查清单](#7-验收检查清单)
8. [附录 A: 变更日志](#附录-a-变更日志)
9. [附录 B: 术语表](#附录-b-术语表)
10. [附录 C: 参考文档](#附录-c-参考文档)

---

## 1. 背景与问题陈述

### 1.1 当前状态

2026-05-31 的调度基础设施审计发现以下断裂状况：

| 组件 | 状态 | 断裂数量 | 根因 |
|------|------|----------|------|
| hermes 桥接 symlink | 全部断裂 | 179 条 | 5 个项目被归档，scripts/ 目录被删除 |
| cron-service cron.db | 全部失效 | 20 job | 所有 job 指向断裂的 symlink |
| 系统 crontab | 部分断裂 | 4/6 条断裂 | 脚本文件被删除 |
| launchd 服务 | 停止 | 2 个已归档 | plist 引用不存在的脚本 |

### 1.2 历史教训

1. **无自动清理机制** — 项目迭代从未触发 symlink/调度条目的自动清理，断裂引用持续累积
2. **无统一管理入口** — cron-service、crontab、launchd、hermes 桥接分散管理，无单一视图
3. **无健康监测** — 断裂发生后无告警，直到人工审计才发现
4. **硬编码泛滥** — 项目路径、分类、计数在审计脚本中硬编码
5. **桥接层无 SSOT** — `~/.hermes/scripts/` 成为事实 SSOT 但无版本/治理

### 1.3 核心矛盾

| 问题 | 描述 |
|------|------|
| 调度碎片化 | 4 种调度机制（cron-service/crontab/launchd/hermes）互不感知 |
| 任务无分类 | cron/长期守护/一次性/事件驱动 四种任务混用同一机制 |
| 存活性不可观测 | 无法回答"当前哪些任务活着、哪些已死" |
| 治理与调度混淆 | `.omo/tasks/` 的 14 字段审批流不适合运维级调度，但被混用 |

### 1.4 为什么需要 Task Center

建立 **Task Center** 的核心目标是收敛 5 类任务至统一调度 SSOT，解决上述所有问题。

```
当前:   cron-service + crontab + launchd + hermes (4 套独立系统)
未来:   Task Center 调度 SSOT → 统一调度引擎 → 统一观测
```

---

## 2. 目标与范围

### 2.1 设计原则

| 编号 | 原则 | 说明 |
|------|------|------|
| P1 | SSOT 优先 | 调度中心的事实存储在 `_truth/task-center/registry.yaml`，非 SQLite |
| P2 | 不重复造轮子 | 复用 cron-service 的 scheduler/executor 模块，改造而非重写 |
| P3 | 渐进式迁移 | 先下线断裂任务 → MVP 收敛 5 类任务 → 联邦扩展 |
| P4 | 可观测内置 | 所有任务运行记录、健康状态、告警默认开启 |
| P5 | 与治理解耦 | 调度任务与治理任务（`tasks/`）边界清晰，通过 task_ref 双向引用 |
| P6 | 最少意外 | launchd 长期守护、crontab 存活条目保留到迁移就绪 |

### 2.2 范围

#### in scope

- 5 类任务的 schema 定义：cron / once / longrun / webhook / event
- `registry.yaml` 任务注册表格式
- 调度引擎的改造规格（基于 cron-service）
- MCP 工具集（CRUD + 执行 + 状态）
- 健康观测与告警
- 迁移路线：断裂清理 → MVP → 联邦扩展

#### out of scope（当前版本）

- 任务 DAG 编排（依赖图执行）
- 跨机器联邦调度
- 任务市场/模板库
- 付费/配额计量

### 2.3 非功能性需求

| 维度 | 目标 | 衡量方式 |
|------|------|----------|
| 调度精度 | ±15s（cron）/ 准实时（event） | 从触发到执行 |
| 可靠性 | 99.9% 任务按计划触发 | 缺失触发次数 / 总触发次数 |
| 可观测 | 每次运行记录 + 健康仪表板 | 运行记录完整性 |
| 扩展性 | 支持 500+ 任务注册 | registry.yaml 加载耗时 < 2s |
| 安全性 | 子进程隔离 + 权限白名单 | 无 RCE / 无权限逃逸 |

#### 灾难恢复承诺 (SRE)

| 指标 | 目标 | 衡量方式 |
|------|------|----------|
| RTO（恢复时间目标） | < 30s | cron-service 崩溃到恢复调度 |
| RPO（恢复点目标） | < 15s（1 tick 间隔） | 最多丢失 1 个 tick 的事件 |
| SLI（调度延迟指标） | 99.9% 在 ±15s 内 | `实际触发时间 - 计划触发时间` 每分钟产出 |
| SLO（调度精度承诺） | 99.9% tick 延迟 ≤ 15s | 按月滚动计算 |

---

## 3. 架构设计

### 3.1 在 SSOT 四平面中的定位

Task Center 在四平面架构中的位置：

```
控制面 _control/                   事实面 _truth/
  state/system.yaml                  tasks/ (治理 SSOT)
  goals/current.yaml                 task-center/ (调度 SSOT)  ← NEW
                                       ├── registry.yaml
                                       ├── triggers/
                                     PROJECTS.yaml
                                     workers/registry.yaml

知识面 _knowledge/                  交付面 _delivery/
  design/                            workers/runs/
    task-center-requirements.md  ← 本文件    task-center/ (运行记录)  ← NEW
  management/
    scheduling-cleanup-*.md
```

> **落位约束**：Task Center 是少数允许直接落在 owner plane 下的 **plane-native domain**。`registry.yaml / triggers/` 只在 `_truth/task-center/`；`runs/alerts/audit/heartbeat` 只在 `_delivery/task-center/`。控制面和知识面只保留状态、设计和引用，不再复制 registry 或运行记录。

### 3.2 两层 SSOT 互补

| 维度 | 治理任务 `tasks/` | 调度任务 `task-center/` |
|------|------------------|------------------------|
| 用途 | Phase 目标分解、人类协作审批 | 运维脚本自动执行、定时/事件触发 |
| 数量级 | 几十个（Phase 级） | 几十~几百个（每日运行） |
| 生命周期 | Phase 跨度（周~月） | 持续运行（天~年） |
| 审批要求 | review→done 流转 | 自治执行，失败告警 |
| 触发方式 | 人工认领 | cron / interval / event / webhook |
| 格式 | YAML 14 字段 + Git | registry.yaml 注册表 + SQLite cache |

**互引机制**：
- 治理任务通过 `task_ref: "task-center#wf-001"` 引用调度任务
- 调度任务通过 `depends_on: ["M2.6-INTEGRATION-VERIFY"]` 引用治理任务
- 交叉引用不创建依赖环（不强制调度任务等待治理任务）

### 3.3 核心组件四层架构

```
┌─────────────────────────────────────────────────────────┐
│                   观测层 Observability                   │
│  健康仪表板 · 运行记录 · 告警通知 · 断裂检测             │
├─────────────────────────────────────────────────────────┤
│                   执行层 Executor                        │
│  Runner Pool · 超时/重试 · 结果收集 · 投递分发           │
├─────────────────────────────────────────────────────────┤
│                   调度层 Scheduler                       │
│  Tick Loop · cron/interval/event/webhook · 任务图        │
├─────────────────────────────────────────────────────────┤
│                   注册层 Registry                        │
│  registry.yaml · 任务定义 · 触发器定义 · 依赖声明        │
│           ↑                                        ↑    │
│      _truth/task-center/                       SQLite    │
│       (SSOT, Git)                            (Cache)     │
└─────────────────────────────────────────────────────────┘
```

#### 注册层 (Registry Layer)

- **SSOT**: `_truth/task-center/registry.yaml` — 唯一真相源
- **Cache**: `~/.cron-service/cron.db` — 运行时快速查询，通过 `omo task-center sync` 同步
- **触发器**: `_truth/task-center/triggers/cron/`, `triggers/event/`, `triggers/webhook/`

> **设计说明**：`_truth/` 下无 `instances/` 目录——单次运行记录属于交付面 `_delivery/task-center/runs/`。实例快照（如"当前正在运行哪些任务"）由 SQLite cache 实时查询提供，不持久化到事实面。事实面仅存**定义级**数据（registry.yaml + triggers），**运行态**数据归属交付面。

#### 调度层 (Scheduler Layer)

- 基于 cron-service 现有 `CronScheduler` 改造
- `Tick Loop` 默认 15s，扫描 registry.yaml cache 计算到期
- **补偿式 tick**：使用 `next_tick_time = start + interval` 固定间隔，避免漂移累积
- **健康探针**：每个 tick 写入 `_delivery/task-center/heartbeat.json`，滞后超过 30s 触发告警
- **进程内 watchdog**：tick loop 使用 `signal.SIGALRM` 或 `threading.Timer` 自监视，超时未完成主动 crash（fail-fast），利用 launchd 重启
- 新增 `event` 类型：通过 kqueue + FSEvents 原生监听（带 symlink 保护 + watch 上限）
- 新增 `webhook` 类型：HTTP POST → 注册回调 → 触发任务
- `longrun` 类型：通过 launchd/systemd 包装，Task Center 仅注册+健康检查

#### 执行层 (Executor Layer)

- 复用 cron-service 现有 `executor.execute()`，强制 `shell=False`（列表参数调用）
- 新增：任务级超时配置、自动重试（可配）、并发控制（Semaphore + 队列上限 100）
- **优先级队列**：支持 `priority` 字段（1-10），高优先级任务插队
- **分类 Semaphore**：cron/longrun 共享 4，event 独立 2，webhook 独立 2
- 子进程隔离：文件权限 600，子进程以不同（更低权限）用户执行
- 输出：stdout + stderr + exit code + duration（写入前脱敏）
- 结果投递：local log + iLink 微信（可选），投递失败自动降级 local

#### 观测层 (Observability Layer)

- 运行记录：每次执行原子写入 `_delivery/task-center/runs/`，自带 SLI 指标
- 健康指标：`failed_since`, `last_success`, `consecutive_failures`
- 断裂检测：定期扫描 registry.yaml 中的 script 路径可达性（执行时重新校验）
- 告警（MVP 必备）：多通道（iLink + 本地通知）、告警持久化、告警抑制
- 变更审计：每个 MCP 写操作写入 `_delivery/task-center/audit/`

### 3.4 与 Workers 框架的关系

| 区别 | Task Center | Workers 框架 |
|------|-------------|-------------|
| 执行者 | 本地子进程 (subprocess) | Agent (LLM) |
| 用途 | 可预测的重复性脚本 | 需要推理的复杂任务 |
| 触发 | cron/event/webhook | 治理任务 dispatch |
| 存储 | `_delivery/task-center/runs/` | `_delivery/workers/runs/` |
| 职责分离 | 不做人类审批 | 做 L0-L3 权限审批 |

两者正交：一个 task 可以同时是 Task Center 的 cron job + Workers 框架的治理任务。

---

## 4. 详细需求

### 4.1 五种任务类型

#### 4.1.1 `cron` — 定时重复

最常用的类型，周期性执行脚本。

```yaml
- id: wf-001
  type: cron
  name: "KOS 每日索引"
  description: "每天凌晨 2 点重建知识索引"
  schedule: "0 2 * * *"           # cron 表达式
  script: kos-index.sh            # 相对于 ~/.hermes/scripts/
  workdir: ~/Workspace
  timeout: 300                    # 5 分钟
  deliver: local                  # local | notify
  notify_on: [error, timeout]     # 仅在失败时通知
  retry:
    max_attempts: 2
    backoff: "fixed_30s"
  enabled: true
  tags: [kos, knowledge, core]
```

#### 4.1.2 `once` — 一次性

手动触发或脚本驱动的临时任务。

```yaml
- id: migrate-v2-schema
  type: once
  name: "Schema v2 迁移"
  description: "一次性数据库迁移脚本"
  script: upgrade-schema-v2.py
  timeout: 600
  deliver: local
  notify_on: [always]             # 不管成功失败都通知
  enabled: true                   # 创建时默认启用，执行后自动禁用
  tags: [migration, db]
```

执行后自动置 `enabled: false`，保留运行记录。

#### 4.1.3 `longrun` — 长期守护

由 launchd/systemd 管理的守护进程，Task Center 负责注册 + 健康检查。

```yaml
- id: bos-daemon
  type: longrun
  name: "BOS 守护进程"
  description: "SharedBrain BOS 后台服务"
  manager: launchd                # launchd | systemd | supervisor
  plist: com.sharedbrain.bos      # launchd 的 plist 标签
  program: /usr/local/bin/bos-daemon
  health_check:
    type: pid                     # pid | http | tcp | script
    port: 7453
    interval: 60
    timeout: 5
  enabled: true
  tags: [sharedbrain, core, daemon]
```

Task Center 不做 launchd 的 work——launchd 本身是最成熟的进程管理器。Task Center 仅做：
- 注册/更新/卸载操作
- 定期健康检查（HTTP/TCP/PID 文件）
- 状态同步到 registry.yaml

#### 4.1.4 `webhook` — 外部触发

通过 HTTP POST 从外部触发任务。

```yaml
- id: github-ci-webhook
  type: webhook
  name: "GitHub CI 触发部署"
  description: "PR merged 后触发部署流水线"
  script: deploy.sh
  webhook:
    path: /hooks/deploy            # 相对于 webhook 基础路径
    method: POST
    secret_ref: "webhook/github-ci" # HMAC secret 引用
    timeout: 10                    # 请求处理超时
  workdir: ~/Workspace
  deliver: local
  enabled: true
  tags: [ci, deploy]
```

安全性要求：
- 每个 webhook 必须配置 HMAC secret（存储在 `_secret/` 而非 registry.yaml 明文）
- HMAC 签名验证必须使用 `hmac.compare_digest()`，禁止 `==`/`!=` 字符串比较（防时序侧信道攻击）
- 请求 IP 白名单可选，`Host` header 必须与注册的 webhook path 匹配（防 SSRF）
- 请求体大小限制：在 `Content-Length` 解析后**立即**拒绝超限请求（`413 Payload Too Large`），不超过 1MB
- 速率限制：per-path 计数器，使用**令牌桶算法**（允许 5 次突发，长期平均 10 次/分钟），持久化到 SQLite（防止重启丢失）。被限流返回 `429 Too Many Requests` + `Retry-After` header
- 区分注册超时（5s）和执行超时（沿用任务级 timeout，默认 120s）
- 未认证请求（无有效 HMAC）也计入速率限制计数

#### 4.1.5 `event` — 事件驱动

监听文件系统事件或内部消息。

```yaml
- id: file-change-reindex
  type: event
  name: "文件变更触发重新索引"
  description: "知识库文件变更后自动重建索引"
  script: reindex.py
  event:
    source: fs                     # fs | bus
    watch: ~/Workspace/data/knowledge/
    patterns: ["*.md", "*.json"]   # glob 模式
    debounce: 30                   # 去抖 30 秒
  timeout: 120
  deliver: local
  enabled: true
  tags: [knowledge, index]
```

**事件源**：
- `fs`：基于 kqueue / FSEvents（macOS）、inotify（Linux）
- `bus`：订阅 i0 事件总线的内部消息
- `interval`：轮询检查（回退方案）

**事件安全要求**：
- 监听器层必须跳过 symlink 目标（应用层过滤），防止 symlink 遍历攻击
- 全局 watch 数量上限：最多 10 个目录、1000 个文件
- 启动时检查可用 inotify/kqueue 资源，接近上限时拒绝注册新 event 任务
- `max_depth` 参数控制递归深度（默认 3 级）
- 检测到 kqueue fd 耗尽或 FSEvents 错误时**自动降级**到 interval 轮询（polling interval 默认 60s）

### 4.2 registry.yaml 规范

#### 4.2.1 顶层结构

```yaml
version: 1
updated_at: "2026-05-31T00:00:00Z"
status: active                     # active | paused | deprecated

# 全局设置
defaults:
  timeout: 120
  deliver: local
  notify_channels: [ilink]
  notify_on: [error]
  max_concurrency: 4
  queue_limit: 100

# 任务列表
tasks:
  # ... 任务定义 ...
```

#### 4.2.2 任务字段清单

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 全局唯一标识 |
| `type` | enum | ✅ | cron/once/longrun/webhook/event |
| `name` | string | ✅ | 人类可读名称 |
| `description` | string | | 详细描述 |
| `schedule` | string | cron | cron 表达式 |
| `script` | string | cron/once/webhook/event | 脚本路径（相对 `~/.hermes/scripts/`），禁止目录遍历 |
| `workdir` | string | | 工作目录 |
| `timeout` | int | | 超时秒数，默认 120 |
| `deliver` | enum | | local/notify，默认 local |
| `notify_channels` | string[] | | 通知通道，默认继承全局配置 |
| `notify_on` | enum[] | | always/error/timeout/success |
| `retry` | object | | `max_attempts`, `backoff` |
| `enabled` | bool | | 是否启用，默认 true |
| `tags` | string[] | | 标签，用于分类和过滤 |
| `depends_on` | string[] | | 依赖的任务 ID |
| `priority` | int | | 优先级 1-10，默认 5 (越高越优先) |
| `redact_patterns` | string[] | | 日志脱敏正则列表，匹配内容替换为 `***REDACTED***` |
| `manager` | enum | longrun | launchd/systemd/supervisor |
| `plist` | string | longrun | launchd 标签 |
| `program` | string | longrun | 守护进程路径 |
| `health_check` | object | longrun | `type`, `port`, `interval`, `timeout` |
| `webhook` | object | webhook | `path`, `method`, `secret_ref`, `timeout` |
| `event` | object | event | `source`, `watch`, `patterns`, `debounce` |

#### 4.2.3 registry.yaml 约束

- `id` 必须匹配 `^[a-z0-9][a-z0-9_-]{2,63}$`
- `script` 值必须在 `~/.hermes/scripts/` 中存在引用（创建时校验 + 每次执行前重新校验）
- `script` 路径执行前必须做规范化（`os.path.realpath`）+ 前缀检查（必须落在 `~/.hermes/scripts/` 内）
- `schedule` 必须是有效 cron 表达式或 `every Xm` 格式
- 同一 `id` 不可重复注册
- `secret`/`token`/`password` 字段**禁止**出现在 registry.yaml 中，应引用 `_secret/`

### 4.3 MCP 工具集

基于现有 cron-service 的 `mcp_server.py` 扩展：

| 工具 | 参数 | 说明 |
|------|------|------|
| `task_list` | `type?`, `enabled?`, `tags?` | 列出任务，支持过滤 |
| `task_get` | `id` | 获取任务详情（含运行统计） |
| `task_create` | `type`, `name`, `script?`, `schedule?`, ... | 创建任务，自动校验 |
| `task_update` | `id`, `...` | 更新任务字段 |
| `task_delete` | `id` | 删除任务 |
| `task_run` | `id` | 立即触发一次执行 |
| `task_pause` | `id` | 暂停任务（不删除） |
| `task_resume` | `id` | 恢复暂停的任务 |
| `task_status` | 无 | 全局状态：总数/活跃/断裂/错误 |
| `task_check` | 无 | 全量健康检查：断裂检测 + 项目比对 |

返回格式统一为 `{ok: bool, data/error: ...}`。

**MCP 工具安全要求**：
- 错误响应区分用户可见错误和内部错误：用户返回归一化路径（`~` 代替 `/Users/xxx/`）+ 通用错误描述，完整 stack trace 写入 stderr/logging 系统
- `task_create`/`task_update` 写入 script 前做路径规范化 + 白名单检查（`os.path.realpath` 确认在 `~/.hermes/scripts/` 内）
- `task_create`/`task_update` 建议使用乐观锁：写入前读取 registry.yaml 的 `updated_at`，冲突时拒绝写入要求重试
- 禁用 `shell=True`，始终使用列表参数调用 subprocess（`subprocess.Popen([script_path], shell=False)`）
- input/output 日志中匹配 `token=`/`secret=`/`password=`/`api_key` 模式的替换为 `***REDACTED***`

### 4.4 事件系统需求

#### 4.4.1 文件事件 (fs)

| 需求 | 优先级 | 说明 |
|------|--------|------|
| kqueue 监听 | P0 | macOS 原生方案 |
| FSEvents 监听 | P0 | macOS 补充方案（更丰富的元信息）|
| inotify 监听 | P1 | Linux 方案 |
| 去抖合并 | P0 | 批量修改时不重复触发 |
| 递归监听 | P0 | 子目录变更也触发 |
| glob 模式过滤 | P0 | 只关注特定文件类型 |

#### 4.4.2 内部消息事件 (bus)

| 需求 | 优先级 | 说明 |
|------|--------|------|
| 订阅 i0 事件 | P1 | 与现有事件总线集成 |
| 消息过滤 | P1 | 按 topic/type 过滤 |
| 去重 | P1 | 幂等性保证 |

### 4.5 观测与告警

#### 4.5.1 运行记录

每次任务执行完成后，写入：
- `_delivery/task-center/runs/{task_id}/{timestamp}.json`

**原子写入策略**：
1. 写入临时文件 `{timestamp}.json.tmp`
2. 执行 `os.fsync()` 确保数据落盘
3. `os.rename()` 原子重命名为 `{timestamp}.json`
4. 启动时扫描并清理残留 `.tmp` 文件
5. 抽象为 `RunRecorder` 类，统一原子写入 + 重试 + 完整性校验

**保留与归档策略**：
- 在线保留最近 7 天的完整运行记录
- 近 30 天保留摘要（仅 `status/duration/exit_code`）
- 30 天以上归档为压缩文件（`.tar.gz`）
- 内置 `task-center-housekeeping` cron job 每日执行清理

**配额告警**：
- `_delivery/task-center/runs/` 文件数超过 10,000 时触发告警
- 磁盘使用率超过 80% 时触发告警

```json
{
  "task_id": "wf-001",
  "run_id": "run_abc123",
  "started_at": "2026-05-31T02:00:01Z",
  "finished_at": "2026-05-31T02:00:05Z",
  "duration_ms": 4230,
  "status": "ok",
  "exit_code": 0,
  "output_snippet": "...",      # 已脱敏（token/secret/password 替换为 ***REDACTED***）
  "error_snippet": "",
  "delivery_status": "delivered",
  "schedule_sli_ms": 3200       # SLI：实际触发 - 计划触发，单位 ms
}
```

#### 4.5.2 健康指标

`task_status` MCP 工具返回：

```json
{
  "total": 42,
  "active": 35,
  "paused": 3,
  "broken": 2,
  "error": 2,
  "never_run": 0,
  "last_check": "2026-05-31T12:00:00Z"
}
```

**断裂定义**：script 引用的目标文件不存在。
**错误定义**：连续 3 次运行失败（可配置 `max_consecutive_failures`）。

#### 4.5.3 告警（MVP 必备）

- **多通道降级**：iLink 微信为主通道 + 本地通知（`terminal-notifier`/macOS 通知）为保底通道
- **连续失败告警**：连续失败 N 次（可配置 `max_consecutive_failures`，默认 3）→ iLink + 本地通知
- **告警持久化**：告警事件写入 `_delivery/task-center/alerts/`（原子写入），每次告警记录：时间、任务 ID、失败原因、通知通道、送达状态
- **告警抑制**：同一任务连续失败仅首次 + 每 1 小时重复通知一次，避免告警轰炸
- **断裂检测**：写入 `.omo/state/system.yaml#divergence_flags`
- **任务雪崩保护**：单任务 1 分钟内最多触发 4 次（硬限制，可配置 `max_trigger_rate`）
- **SLI 持续采集**：每个运行记录自动产出 `schedule_sli_ms` 指标（实际触发时间 - 计划触发时间），每分钟聚合输出一个统计点
- **健康探针**：每个 tick 写入 `_delivery/task-center/heartbeat.json`，观测层独立监控该文件的更新时间戳，滞后超过 2 个 tick 间隔（30s+）则触发告警

### 4.6 与 Hermes 桥接的关系

暂时保留 hermes 桥接作为**兼容层**，而不是新的核心 SSOT：
- registry.yaml 中的 `script` 值相对于 `~/.hermes/scripts/`
- `~/.hermes/scripts/` 中的实体文件直接执行（非 symlink）
- 桥接同步脚本 `script-bridge-sync.py` 纳入 Task Center 辅助工具
- 新任务注册时自动创建 hermes symlink

**防断裂机制**：
- 启动和每 tick 时检测 `~/.hermes/scripts/` 中 symlink 的断裂状态
- 断裂检测与任务 `enabled` 状态联动：断裂任务自动标记为 `broken` 而非 `active`
- 提供 `task_repair` 工具：断裂的 hermes symlink 可手动/自动重建（从项目 scripts/ 目录重新关联）
- 定期清理（GC）：当 registry.yaml 中删除了某任务，自动清理对应的 hermes symlink

---

## 5. 实施路线图

### 5.1 三阶段迁移

```
阶段 1 (Wave 1 后·Wave 2 前)    阶段 2 (Wave 2~3)             阶段 3 (Phase ∞)
     2026-06                         2026-06~08                    2027+
─────────                          ─────────                       ─────
  ✅ 紧急止损（已完成）               🔧 Task Center MVP             🌐 联邦任务中心
  • 清理 179 断裂 symlink            • 创建调度 SSOT                • 联邦调度
  • 清理 cron.db 废弃 job            • registry.yaml schema         • 事件总线集成
  • 清理 crontab 断裂条目            • cron-service 改造            • 任务 DAG
  • 卸载废弃 launchd                 • MCP 工具集                   • 自助注册门户
  • 记录清理结果                     • 事件触发器 MVP               • 健康看板
                                      • 健康仪表板                   • 智能告警
                                      • 迁移 2 条存活任务
```

### 5.2 阶段 2 (MVP) 交付物

#### 5.2.1 需要建设的文件

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `_truth/task-center/INDEX.md` | 调度 SSOT 入口 | P0 |
| `_truth/task-center/registry.yaml` | 任务注册表 | P0 |
| `_truth/task-center/triggers/cron/` | cron 触发器目录 | P1 |
| `_truth/task-center/triggers/event/` | 事件触发器目录 | P1 |
| `_delivery/task-center/INDEX.md` | 运行记录入口 | P0 |
| `_delivery/task-center/alerts/` | 告警事件记录 | P0 |
| `_delivery/task-center/audit/` | 变更审计日志 | P1 |
| `_knowledge/design/INDEX.md` 编目 | 设计文档索引 | P0 |

#### 5.2.1a 安全加固子阶段（Safety Sprint）

在 MVP 功能开发前或并行执行（预计 4-6 天），必须完成以下安全加固：

| 优先级 | 加固项 | 关联发现 | 预估 |
|--------|--------|----------|------|
| P0 | 子进程强制 `shell=False` + 路径白名单 | C-1 | 0.5 天 |
| P0 | 定义 `_secret/` 目录规范（加密存储 + 运行时解密 + 权限 600） | C-2/C-3 | 2 天 |
| P0 | HMAC 比较使用 `hmac.compare_digest` | C-3 | 0.5 天 |
| P0 | 执行时重新校验 script 路径 | H-2 | 0.5 天 |
| P1 | SQLite WAL + busy_timeout + 单点写入代理 | H-1 | 2 天 |
| P1 | Webhook 速率限制（令牌桶 + per-path + 持久化） | H-3 | 1 天 |
| P1 | 子进程隔离（sandbox-exec / systemd 约束） | H-5 | 2 天 |
| P1 | 事件监听 symlink 保护 + 资源限制 | H-4 | 1 天 |

#### 5.2.2 需要修改的文件

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| `_truth/INDEX.md` | 增加 task-center 注册 | P0 |
| `state/system.yaml` | 增加 task_center 健康指标 | P0 |
| cron-service scheduler.py | registry.yaml → SQLite sync | P0 |
| cron-service mcp_server.py | 扩展 MCP 工具集 | P0 |
| `scheduled-tasks-audit.py` | 支持新架构 | P1 |
| `workers/registry.yaml` | 增加 task-center worker（可选） | P2 |

#### 5.2.3 存量迁移

| 来源 | 任务 | 迁移方式 |
|------|------|----------|
| crontab x2-backup-brain | 注册为 cron 任务 | 手动移入 registry.yaml |
| crontab omo-state-sync | 注册为 cron 任务 | 手动移入 registry.yaml |

### 5.3 阶段 2 不包含的内容

- 联邦跨机器调度
- 任务 DAG 执行器
- 事件总线深度集成（i0 订阅）

### 5.4 凭据管理与 n8n 参考

n8n 在企业级工作流自动化中的设计值得参考，但不直接采用：
- **升级为 Wave 2 必做项**：凭据管理（credential management）从"可参考"升级为 Wave 2 必做项，至少覆盖 iLink token、webhook secret 两类凭据的加密存储 + 访问审计
- **可学习的**：可视化 DAG、执行日志回溯
- **不采用的**：Node.js 运行时绑定、拖拽式编辑器、内置 400+ connector

---

## 6. 风险与回退

### 6.1 风险矩阵

| ID | 风险 | 概率 | 影响 | 缓解措施 |
|----|------|------|------|----------|
| R1 | cron-service 单进程崩溃 | 中 | 高 | 进程管理（launchd），自动重启 + 健康探针自恢复 |
| R2 | registry.yaml 与 SQLite 不一致 | 中 | 高 | registry version/checksum 指纹校验 + force-resync 命令 |
| R3 | event 监听消耗过多资源 | 低 | 中 | 去抖合并，限制监听路径数，自动降级轮询 |
| R4 | webhook 端点被恶意调用 | 低 | 高 | HMAC 签名 + IP 白名单 + 速率限制 + 请求体预检 |
| R5 | 迁移期间遗漏任务 | 中 | 中 | 阶段性审计报告对比 |
| R6 | 并发执行导致资源耗尽 | 低 | 高 | Semaphore 限制最大并发数（默认 4），队列上限 100 |
| R7 | 长期守护健康检查误报 | 中 | 低 | 可配置检查间隔、容忍连续失败次数 |
| R8 | 多人同时修改 registry.yaml | 低 | 中 | MCP 单点写入 + `updated_at` 乐观锁 + 审计日志 |
| R9 | 磁盘满导致写入失败 | 低 | 高 | 启动时检查剩余空间 < 1GB 进入安全模式，只执行存量任务不写记录 |
| R10 | NTP 时钟回拨导致调度混乱 | 低 | 中 | 使用 `time.monotonic()` 计算 tick 间隔，跳变超过 2 个 tick 跳过该 tick |
| R11 | iLink 网络不可达导致告警丢失 | 中 | 中 | 多通道告警（iLink + 本地通知），投递队列持久化本地 |
| R12 | 子进程篡改 registry.yaml | 低 | 高 | 文件权限 600，子进程以不同（更低权限）用户执行 |

### 6.2 回退方案

| 场景 | 回退动作 |
|------|----------|
| MVP 导致现有任务中断 | 回滚 registry.yaml 到上一版，恢复 cron.db 备份，回滚后执行全量安全验证 + 断裂检测 |
| 事件监听引入性能问题 | 禁用所有 event 类型任务，回退到 interval 轮询 |
| MCP 工具导致数据损坏 | 停止 MCP 进程，通过 HTTP API 手动修复 |
| 迁移遗漏 | 审计脚本每日对比 registry.yaml 与 crontab/launchd |
| 磁盘满 | 进入安全模式：只执行存量任务，不写入运行记录（缓冲到内存，空间恢复后写入），不接收新 webhook |
| iLink 不可达 | 投递自动降级为 `deliver: local`，本地保存结果，网络恢复后重试投递（最多 3 次）。投递队列持久化到本地 SQLite |

---

## 7. 验收检查清单

### 7.1 架构验收

- [ ] `_truth/task-center/` 目录创建，包含 INDEX.md 和 registry.yaml
- [ ] 5 种任务类型的 registry.yaml schema 定义完成
- [ ] `_truth/INDEX.md` 增加 task-center SSOT 注册条目
- [ ] `_knowledge/design/INDEX.md` 增加本文件编目
- [ ] 运行记录采用原子写入（tmp + rename + fsync）
- [ ] 补偿式 tick 实现（`next_tick_time = start + interval` 固定间隔）
- [ ] 待执行队列上限（默认 100），超过上限跳过低优先级任务并告警

### 7.2 功能验收

- [ ] `task_create` 创建 cron 任务并自动调度
- [ ] `task_list` 列出所有任务，支持 type/tag/enabled 过滤
- [ ] `task_run` 立即执行任务并返回结果
- [ ] `task_pause` / `task_resume` 暂停/恢复任务
- [ ] `task_check` 全量健康检查（断裂检测）
- [ ] event 类型：文件变更 → 自动触发脚本
- [ ] webhook 类型：HTTP POST → 触发脚本 + HMAC 验证

### 7.3 性能验收

- [ ] 100 个 cron 任务同步耗时 < 2s
- [ ] 连续 tick 不累积延迟
- [ ] 事件去抖 30s 生效
- [ ] webhook 请求处理 < 1s（纯注册）
- [ ] registry.yaml 加载 < 500ms

### 7.4 安全验收

- [ ] webhook HMAC 签名验证生效，使用 `hmac.compare_digest()`
- [ ] 子进程执行使用 `shell=False`（列表参数调用），路径白名单校验
- [ ] 子进程隔离：文件权限 600，子进程以单独（更低权限）用户执行
- [ ] iLink token 存储在 `~/.cron-service/config.yaml` 非 registry.yaml，配置文件权限 600
- [ ] webhook secret 存储在 `_secret/` 加密 vault 中，禁止出现在 registry.yaml
- [ ] 最大并发数默认 4，队列上限 100
- [ ] 文件事件监听不追踪隐藏文件，跳过 symlink 目标
- [ ] 事件监听全局 watch 数量上限（10 目录 / 1000 文件）
- [ ] `script` 路径执行前规范化 + 前缀检查（必须落在 `~/.hermes/scripts/` 内）
- [ ] 运行记录日志脱敏（`token=`/`secret=`/`password=` 替换为 `***REDACTED***`）
- [ ] MCP 错误响应不暴露内部路径和 stack trace
- [ ] webhook 速率限制 per-path 持久化，被限流返回 `429` + `Retry-After`
- [ ] 目录遍历防护验证（`../` 路径被拒绝）
- [ ] SQLite 并发写压测：多进程同时写入无 `SQLITE_BUSY` 错误
- [ ] registry.yaml 中无 `secret`/`token`/`password` 字段

### 7.5 迁移验收

- [ ] x2-backup-brain 从 crontab 迁移到 registry.yaml
- [ ] omo-state-sync 从 crontab 迁移到 registry.yaml
- [ ] 迁移后原 crontab 条目删除
- [ ] 运行 3 次确认定时触发正常

### 7.6 可靠性验收（故障注入测试）

- [ ] `kill -9 cron-service` 进程 → launchd 在 < 10s 内重启并恢复调度
- [ ] `truncate cron.db` → 自动从 registry.yaml 重建 cache
- [ ] 构造 50 个同时到期 cron 任务 → 验证 tick 不累积、无 OOM
- [ ] 网络断开 iLink → 投递自动降级为 `deliver: local`，网络恢复后重试
- [ ] 填充磁盘至 95% → 进入安全模式，不写运行记录
- [ ] 系统时钟回拨 10s → 调度不重复触发
- [ ] SQLite 损坏 → 自动切换到 fallback cache，后台重建 primary

### 7.7 秘密管理验收

- [ ] `_secret/` 目录定义完成：加密存储（age/sops 加密 YAML），运行时解密到内存
- [ ] iLink token 非明文存储在 `~/.cron-service/config.yaml`，文件权限 600
- [ ] webhook secret 通过 `secrets.token_hex(32)` 生成，存储在 `_secret/`
- [ ] registry.yaml 不包含任何明文 secret/token/password 字段
- [ ] 所有秘密引用通过 `secret_ref` 字段指向 `_secret/`

---

## 附录 A: 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v0.2.1 | 2026-05-31 | **收敛修订：补齐当前 `.omo` 四平面约束与剩余语义冲突** |
| | | • 顶部状态描述改为“审阅结论已吸收，最终约束以正文为准” |
| | | • 明确 Task Center 属于 plane-native domain，避免与导航壳模型冲突 (§3.1) |
| | | • webhook 示例改为 `secret_ref`，去除与“registry 不存秘密”相冲突的明文字段 (§4.1.4) |
| | | • `deliver` 语义收敛为 `local | notify`，并新增 `notify_channels` / `max_concurrency` / `queue_limit` 默认项 (§4.2.1-4.2.2) |
| | | • 将 hermes 定位为兼容层而非核心 SSOT，弱化桥接层回潮 (§4.6) |
| | | • 更新 R2 / R8 风险缓解，改为 version/checksum + force-resync / optimistic locking (§6.1) |
| v0.2 | 2026-05-31 | **基于三路审阅（架构/安全红队/运维）全面修订** |
| | | • 新增 RTO (<30s)、RPO (<15s)、SLI/SLO 定义 (§2.3) |
| | | • 修复 instances/ vs runs/ SSOT 混淆，明确运行记录仅属交付面 (§3.1) |
| | | • webhook 安全加固：HMAC `compare_digest`、SSRF 防护、令牌桶限流、双超时 (§4.1.4) |
| | | • event 安全加固：symlink 跳过、watch 上限、自动降级轮询 (§4.1.5) |
| | | • 新增 `priority`、`redact_patterns` 字段 (§4.2.2) |
| | | • script 路径约束：执行时重新校验 + 规范化 + 前缀检查 (§4.2.3) |
| | | • MCP 安全要求：shell=False、乐观锁、错误脱敏 (§4.3) |
| | | • 运行记录原子写入 + 保留/归档策略 + SLI 指标 (§4.5.1) |
| | | • 告警从 Wave 3 升级为 MVP 必备：多通道、持久化、抑制、健康探针 (§4.5.3) |
| | | • hermes 桥接防断裂机制：自动标记 broken + task_repair + GC (§4.6) |
| | | • 新增安全加固子阶段 Safety Sprint（4-6 天）(§5.2.1a) |
| | | • 凭据管理升级为 Wave 2 必做项 (§5.4) |
| | | • 风险矩阵扩展至 R12：磁盘满/时钟回拨/iLink 不可达/子进程篡改 (§6.1) |
| | | • 回退方案补充：安全验证 + 磁盘满安全模式 + iLink 投递降级 (§6.2) |
| | | • 安全验收从 5 项扩展至 15 项 (§7.4) |
| | | • 新增可靠性验收（7 项故障注入测试）(§7.6) |
| | | • 新增秘密管理验收 (5 项) (§7.7) |
| v0.1 | 2026-05-31 | 初始草案 — 完整 PRD 含 7 章节 |

## 附录 B: 术语表

| 术语 | 定义 |
|------|------|
| SSOT | Single Source of Truth，单一事实来源 |
| registry.yaml | 调度任务注册表，Task Center 的 SSOT |
| hermes 桥接 | `~/.hermes/scripts/` 中的 symlink 层，解耦调度与项目 |
| tick | scheduler 的周期扫描（默认 15s） |
| 断裂 | script 引用的目标文件不存在 |
| 告警阈值 | `max_consecutive_failures`，默认 3 次 |

## 附录 C: 参考文档

- [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) — 整体架构蓝图
- [DOC-ARCH.md](../../DOC-ARCH.md) — 四平面架构文档
- [scheduling-cleanup-2026-05-31.md](../management/scheduling-cleanup-2026-05-31.md) — 清理记录
- [tasks/README.md](../../tasks/README.md) — 治理任务规范
- [workers/registry.yaml](../../workers/registry.yaml) — Worker 注册表
- [INDEX.md](../../INDEX.md) — OMO 主导航索引
