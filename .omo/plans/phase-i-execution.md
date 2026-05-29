# Phase I — 集成织物层实施详细方案

> 遵循 MECH-02 / MECH-05 | 2026-05-28 | 总工时: 5h

---

## TL;DR

```
实施 4+1+3+I 架构的最后一步：把 I0 层从文档定义变成代码锁死的制度。

3 Wave · 6 个任务 · ~5h · 全部可并行
```

## Wave 分解

### Wave I1: I0 正式化 (2h, 3 任务并行)

| # | 任务 | 内容 | 角色 | 工时 |
|:--:|------|------|:----:|:----:|
| 1 | **Forge sync 迁移** | `sync-agora.sh` → `agora/adapters/` | P8 | 30min |
| 2 | **KOS→hermes-ops MCP** | HTTP 硬编码 → MCP 事件推送 | P8 | 1h |
| 3 | **arcnode I0 验证脚本** | I0-1 MCP强制 / I0-2 无业务逻辑 / I0-3 总线优先 | P8 | 30min |

### Wave I2: Agora 事件总线 (2h, 2 任务串行)

| # | 任务 | 内容 | 角色 | 工时 |
|:--:|------|------|:----:|:----:|
| 4 | **Agora 总线适配** | Agora 事件订阅 → hermes-ops events 转发 | P8 | 1h |
| 5 | **全量集成测试** | I0 层连通性验证 (test-11) | P8 | 1h |

### Wave I3: 文档封版 (1h, 1 任务)

| # | 任务 | 内容 | 角色 | 工时 |
|:--:|------|------|:----:|:----:|
| 6 | **架构宪法迭代** | 4+1+3+I 定稿锁版 | P9 | 1h |

---

## 任务详细定义（Task Prompt 六要素）

---

### 1. Forge sync 迁移

| 要素 | 内容 |
|------|------|
| **目标** | Forge 的 sync-agora.sh 从 Forge 源码目录迁移到 Agora 的适配器目录，消除项目跨两层的问题 |
| **范围** | Forge/ → agora/adapters/forge-sync/ | 复制 sync 脚本 | 更新路径引用 | **不删** 原 Forge 文件（保留兼容 symlink） |
| **验收** | `ls agora/adapters/forge-sync/sync-agora.sh` 存在 | `agora/adapters/forge-sync/` 有 README 描述角色 |
| **依赖** | 无（可立即启动） |
| **输出** | `agora/adapters/forge-sync/sync-agora.sh` |
| **角色** | P8 (Shell) |

---

### 2. KOS→hermes-ops MCP 事件

| 要素 | 内容 |
|------|------|
| **目标** | KOS 中所有对 hermes-ops 的 HTTP 硬编码调用（pattern_learner/push_engine 中的 urllib.request）改为 MCP 事件推送 |
| **范围** | kos/kos/pattern_learner.py + push_engine.py | 替换 HTTP JSON-RPC → MCP 调用 | **不改变** 业务逻辑 |
| **验收** | `grep -n "9800\|localhost" pattern_learner.py push_engine.py` 无 HTTP 硬编码 | KOS 测试通过 |
| **依赖** | 无（可并行） |
| **输出** | pattern_learner.py + push_engine.py 修改 |
| **角色** | P8 (Python) |

---

### 3. arcnode I0 验证脚本

| 要素 | 内容 |
|------|------|
| **目标** | 在 arcnode 验证脚本中新增 I0-1/I0-2/I0-3 三条约束 |
| **范围** | ~/.hermes/scripts/validate-I0-1-mcp / validate-I0-2-logic / validate-I0-3-bus |
| **验收** | `arcnode validate --constraint I0-1` exit 0 | 三条脚本均可执行 |
| **依赖** | 无（可并行） |
| **输出** | 3 个验证脚本 |
| **角色** | P8 (Python) |

---

### 4. Agora 事件总线适配

| 要素 | 内容 |
|------|------|
| **目标** | Agora 状态变更（服务注册/注销/降级进入/退出）自动通过 hermes-ops 的事件总线广播，而非直接 HTTP 调用 |
| **范围** | Agora/src/agora/router.py + service_cache.py | 在关键状态切换点添加 ops_event 调用 | **不改变** 核心路由逻辑 |
| **验收** | Agora 降级进入时自动触发 ops_event("AGORA_DEGRADE_ENTERED") | Agora 测试通过 |
| **依赖** | 无（可立即） |
| **输出** | router.py + service_cache.py 修改 |
| **角色** | P8 (Python) |

---

### 5. 全量集成测试

| 要素 | 内容 |
|------|------|
| **目标** | 创建 test-11-i0-integration 验证 I0 层连通性 |
| **范围** | tests/integration/test-11-i0-integration.sh | 验证: Agora MCP 可路由 / hermes-ops 事件可接收 / Forge sync 可触发 / KOS MCP 可调用 |
| **验收** | `bash tests/integration/test-11-i0-integration.sh` exit 0 |
| **依赖** | 任务 1-4 全部完成 |
| **输出** | test-11-i0-integration.sh |
| **角色** | P8 (Shell) |

---

### 6. 架构宪法定稿

| 要素 | 内容 |
|------|------|
| **目标** | 4+1+3+I 架构正式纳入宪法文档，所有文档一致 |
| **范围** | constraints.md / interface_contract.md / MECH-02 / MECH-05 / AGENTS.md / LAYER-INDEX.md |
| **验收** | 所有文档中 4+1+3+I 层定义一致 | I0 约束已注册 |
| **依赖** | 任务 1-3 完成 |
| **输出** | 全量文档迭代 |
| **角色** | P9 (架构师) |

---

## 执行波次

```
Wave I1 (并行 3 任务, ~2h):
  ┌── 1. Forge sync 迁移  (30min)
  ├── 2. KOS→MCP 事件     (1h)
  └── 3. arcnode I0验证    (30min)

Wave I2 (串行, ~2h):
  ├── 4. Agora 总线适配   (1h)
  └── 5. 全量集成测试     (1h)     ← 依赖 4

Wave I3 (独立, ~1h):
  └── 6. 架构宪法定稿     (1h)     ← 依赖 1-3
```

要开始执行吗？
