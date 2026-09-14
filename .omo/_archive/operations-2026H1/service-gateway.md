---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-29
type: ephemeral
status: archived
---
# Service Gateway (ops 控制面)

> 统一运维控制面 — 管理 omostation 所有服务

## 快速开始

```bash
# 查看服务状态
make ops
# 或
cockpit ops status

# 系统概览
cockpit ops summary

# 启动所有服务
cockpit ops up

# 停止所有服务
cockpit ops down

# 查看依赖图
cockpit ops deps
```

## 命令参考

### 核心命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `ops status` | 全量服务状态 | `cockpit ops status --json` |
| `ops summary` | 系统概览 | `cockpit ops summary` |
| `ops up` | 启动服务 | `cockpit ops up` |
| `ops up <service>` | 启动指定服务 | `cockpit ops up resident.orchestrator` |
| `ops down` | 停止服务 | `cockpit ops down` |
| `ops down <service>` | 停止指定服务 | `cockpit ops down resident.orchestrator` |
| `ops deps` | 依赖图 | `cockpit ops deps` |
| `ops deps <service>` | 指定服务依赖 | `cockpit ops deps mcp.kos` |
| `ops logs` | 日志查看 | `cockpit logs -n 100` |
| `ops deploy` | 部署信息 | `cockpit ops deploy` |

### 高级命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `ops discover` | 自动发现服务 | `cockpit ops discover --update` |
| `ops validate` | 配置校验 | `cockpit ops validate` |
| `ops generate` | 生成部署配置 | `cockpit ops generate --format docker-compose -o docker-compose.yml` |

## 服务类型

### 按调度器分类

| 类型 | 说明 | 数量 |
|------|------|------|
| `launchd` | macOS 守护进程 | 29 |
| `cron` | 定时任务 | 30 |
| `manual` | 手动触发 | 195 |
| `docker` | Docker 容器 | 7 |
| `gha` | GitHub Actions | 2 |

### 按域分类

| 域 | 说明 | 数量 |
|------|------|------|
| BOS URI | 能力路由服务 | 236 |
| MCP Server | MCP 协议服务 | 16 |
| CLI 入口 | 命令行入口 | 15 |
| Resident | 常驻 Agent | 9 |
| GaC | 治理门禁 | 17 |
| Docker | 容器服务 | 7 |

## 健康检查

### 检查类型

| 类型 | 说明 | 覆盖 |
|------|------|------|
| HTTP | HTTP 端点探测 | 24 |
| TCP | TCP 端口探测 | 0 (自动) |
| Docker | 容器状态检查 | 6 |
| PID | 进程存活检查 | 动态 |
| File | 文件存在/新鲜度 | 294 |

### 健康状态

| 状态 | 说明 |
|------|------|
| `healthy` | 服务正常运行 |
| `stale` | 服务超时未更新 |
| `missing` | 服务未找到 |
| `unreachable` | 服务不可达 |
| `unhealthy` | 服务异常 |
| `disabled` | 服务已禁用 |

## 依赖图 (DAG)

服务依赖图使用 Kahn 算法进行拓扑排序，确保启动顺序正确：

```
Layer 1: 独立服务 (无依赖)
  ├── cli.* (6)
  ├── mcp.agora (1)
  ├── cron.* (17)
  ├── docker.* (7)
  └── launchd.* (6)

Layer 2: 依赖 Layer 1
  ├── mcp.* → mcp.agora (15)
  ├── cli.* → mcp.* (9)
  └── resident.* → resident.orchestrator (5)

Layer 3: 依赖 Layer 2
  ├── bos.* → mcp.* (236)
  └── resident.promote → resident.sediment (1)

Layer 4: 依赖 Layer 3
  └── cron.proposal_to_adr → resident.promote (1)
```

## 进程管理

### PID 文件

每个服务的 PID 存储在 `runtime/pids/<service>.pid`：

```bash
# 查看 PID
cat runtime/pids/resident.orchestrator.pid

# 检查进程存活
kill -0 $(cat runtime/pids/resident.orchestrator.pid)
```

### 日志文件

每个服务的日志存储在 `runtime/logs/<service>.log`：

```bash
# 查看日志
tail -f runtime/logs/resident.orchestrator.log

# 查看最后 100 行
cockpit ops logs resident.orchestrator -n 100
```

## 配置

### services.yaml

服务清单 SSOT 位于 `.omo/_truth/registry/services.yaml`：

```yaml
services:
  - id: resident.orchestrator
    enabled: true
    scheduler: launchd
    trigger: interval
    interval_sec: 30
    label: com.l4.resident.orchestrator
    program:
      interpreter: stable-python3
      entrypoint: bin/ssot/resident-orchestrator-daemon.py
    resilience:
      keepalive: crashed
      throttle_interval: 30
    liveness:
      signal: .omo/_knowledge/omo-events.jsonl
      event_kind: resident_tick
      max_stale_hours: 1
    depends_on: [omo.sync_daemon]
    outputs:
      stdout: runtime/logs/resident-orchestrator-stdout.log
      stderr: runtime/logs/resident-orchestrator-stderr.log
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `id` | 服务唯一标识 |
| `enabled` | 是否启用 |
| `scheduler` | 调度器类型 (launchd/cron/manual/docker/gha) |
| `trigger` | 触发方式 (interval/schedule/on_demand/compose) |
| `interval_sec` | 间隔秒数 (interval 触发) |
| `schedule` | Cron 表达式 (schedule 触发) |
| `label` | 服务标签 (launchd/docker) |
| `program` | 程序入口 (interpreter/entrypoint/args) |
| `resilience` | 弹性策略 (keepalive/throttle_interval) |
| `liveness` | 健康检查 (signal/endpoint/max_stale_hours) |
| `depends_on` | 依赖服务列表 |
| `ports` | 监听端口列表 |
| `outputs` | 日志输出路径 |

## 部署配置生成

### Docker Compose

```bash
cockpit ops generate --format docker-compose -o docker-compose.yml
```

### Systemd

```bash
cockpit ops generate --format systemd -o omostation.service
```

### Launchd

```bash
cockpit ops generate --format launchd -o com.omostation.plist
```

## 自动发现

扫描运行中的服务并自动注册：

```bash
# 仅发现
cockpit ops discover

# 发现并更新 services.yaml
cockpit ops discover --update
```

## 配置校验

检查服务配置是否正确：

```bash
# 校验所有服务
cockpit ops validate

# 校验指定服务
cockpit ops validate resident.orchestrator
```

## 故障排查

### 服务无法启动

1. 检查配置：`cockpit ops validate <service>`
2. 检查日志：`cockpit ops logs <service>`
3. 检查依赖：`cockpit ops deps <service>`

### 健康检查失败

1. 检查端口：`lsof -i :<port>`
2. 检查进程：`ps aux | grep <entrypoint>`
3. 检查日志：`tail -f runtime/logs/<service>.log`

### 依赖冲突

1. 查看依赖图：`cockpit ops deps`
2. 检查端口冲突：`cockpit ops validate`

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Service Gateway                          │
│                     `cockpit ops`                            │
├─────────────────────────────────────────────────────────────┤
│  Commands: status | up | down | deps | summary | discover   │
│            validate | generate | logs | deploy                │
├─────────────────────────────────────────────────────────────┤
│  Core:                                                       │
│  ├── DAG Engine (Kahn's algorithm)                           │
│  ├── Process Manager (PID + subprocess)                      │
│  ├── Health Checker (HTTP/TCP/Docker/PID/File)              │
│  └── Auto Discovery (lsof + pgrep)                          │
├─────────────────────────────────────────────────────────────┤
│  SSOT: .omo/_truth/registry/services.yaml                    │
│  ├── 336 services registered                                 │
│  ├── 100% health check coverage                              │
│  └── 84% dependency coverage                                 │
└─────────────────────────────────────────────────────────────┘
```

## 参见

- [服务清单 SSOT](../.omo/_truth/registry/services.yaml)
- [端口注册表](../protocols/port-registry.yaml)
- [运维指南](ops-gateway.md)
