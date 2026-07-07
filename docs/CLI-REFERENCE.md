# omo CLI Reference

> Auto-generated on 2026-07-07 05:56:45 UTC

## Overview

omo is the L2 governance kernel CLI for omostation. It provides commands for
health checking, linting, validation, auditing, and worker management.

## Commands

### `omo doctor`

统一健康检查入口

**Details:**

```
omo doctor — 统一健康检查入口.

聚合以下检查为一站式诊断:
1. health check — agora 服务探活
2. validate state — .omo 状态一致性
3. audit freshness — X2 freshness 巡检
```

### `omo inspect`

统一检查入口

**Details:**

```
omo inspect — 统一检查入口.

聚合以下检查为一站式审查:
1. lint schemas — schema 校验
2. validate completeness — .omo 目录完整性
3. validate references — 关键文件引用完整性
```

### `omo health`

服务探活 / 看板

**Subcommands:**

| Command | Description |
|---------|-------------|
| `check` | 探活 agora-routes.json 注册的服务端点 |
| `dashboard` | Keeper Dashboard — 读取 .omo/ 状态文件渲染运维看板 |

### `omo lint`

静态校验

**Subcommands:**

| Command | Description |
|---------|-------------|
| `schemas` | 扫 7 consumer 模块, 校验 .append() 都传 schema= |
| `yaml-bypass` | 扫 .omo/debt/items/*.yaml 拦截 status 字段越权写入 |
| `direct-omo-io` | 拦截非 broker 对 .omo / spaces 的直接文件系统改写 |
| `projection-guard` | P74: 验证 runtime-projections.yaml 声明的路径存在且可解析 |
| `stamp-policy` | P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted |
| `sensitive-governed-writes` | 拦截对 system/goals/tasks/capabilities 等敏感治理面的直接落盘 |
| `god-module` | 单文件 LOC 硬规则 (warn>600L, error>800L) |

### `omo manage`

目录管理

**Details:**

```
omo manage — .omo 目录管理工具集.

从 bin/omo-manage 迁移.

提供:
  - status: 显示 .omo 目录状态 (文件统计、关键文件检查)
  - health: 检查 .omo 目录健康度 (stale 文件、broken references)
  - tasks: 列出任务状态 (active/planned/done/blocked)
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `status` | 显示 .omo 目录状态 |
| `health` | 检查 .omo 目录健康度 |
| `tasks` | 列出任务状态 |

### `omo validate`

目录验证

**Details:**

```
omo validate — .omo 目录验证工具集.

从 bin/omo-validate 迁移.

提供:
  - completeness: 验证 .omo 目录完整性 (M1 治理节点覆盖)
  - references: 验证关键文件引用完整性
  - state: 验证状态一致性 (stale 检测)
  - all: 执行全部验证
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `completeness` | 验证 .omo 目录完整性 |
| `references` | 验证关键文件引用完整性 |
| `state` | 验证状态一致性 |
| `all` | 执行全部验证 |

### `omo audit`

X 审计

**Subcommands:**

| Command | Description |
|---------|-------------|
| `cards` | CARDS X3 value metrics (SQLite 聚合) |
| `vault` | Vault X1 audit (Markdown content hash + author tracking) |
| `freshness` | X2 freshness audit (3 条 P43 巡检规则) |

### `omo worker`

Worker 调度

**Subcommands:**

| Command | Description |
|---------|-------------|
| `task` | 任务相关命令 |
| `worker` | Worker 相关命令 |

### `omo task`

任务管理

**Details:**

```
OMO task CLI — list and create governed tasks via OMO ingress.
```

### `omo debt`

债务管理

**Details:**

```
omo_debt_cli — omo-debt CLI argparse + main() (P110 split from omo_debt.py).

P110 refactor: omo_debt.py 1085L → split off ~315L CLI 入口.
- omo_debt.py: business functions (write_dashboard / write_*_packet / helpers)
- omo_debt_cli.py: argparse setup + main() dispatcher
- omo-debt CLI 调用方不变 (入口 main() 行为一致).

P110 关联: TASK-F7114ABA (omo lint god-module 硬规则 800L, omo_debt 1085L
触发 lint-error 负债清单, 需治本拆分).
```

### `omo state`

状态管理

**Details:**

```
OMO state CLI — show system state from state/.
```

### `omo governance`

治理操作

## Common Usage

```bash
# Health check
omo doctor                  # Unified health check
omo inspect                 # Unified inspection

# Health
omo health check            # Probe agora services
omo health dashboard        # Keeper dashboard

# Lint
omo lint schemas            # Schema validation
omo lint projection-guard   # P74 projection guard
omo lint stamp-policy       # P74 stamp policy

# Manage
omo manage status           # Directory status
omo manage health           # Health check
omo manage tasks            # Task status

# Validate
omo validate all            # Full validation

# Audit
omo audit cards --json      # CARDS X3 metrics
omo audit vault --json      # Vault X1 audit
omo audit freshness --json  # X2 freshness audit

# Worker
omo worker task validate --all-planned
omo worker task promotion-readiness
```
