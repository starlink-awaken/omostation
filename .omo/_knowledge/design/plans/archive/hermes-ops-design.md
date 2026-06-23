---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# OPS-01 — 统一运维中心方案设计

> 日期: 2026-05-28 | 服务代号: hermes-ops
> 目标: 替代碎片化运维脚本，提供统一的可接入 MCP 服务

---

## 一、设计原则

```
1. 自成一服 — 本身是一个 MCP 服务，通过 stdio/SSE 暴露工具
2. 零侵入 — 已有服务不需要改动代码，通过配置接入
3. MCP 协议 — 所有能力通过 MCP tools 暴露，Agora 可路由
4. Forge 集成 — 自动注册到工具库
5. 日志统一 — 所有服务日志收敛到统一格式
```

---

## 二、架构概览

```
                  ┌─────────────┐
                  │  Forge      │ ← 工具注册
                  └──────┬──────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│                 hermes-ops (MCP Server)                  │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Logger   │  │ Monitor  │  │ Events   │  │ Reports │ │
│  │ 统一日志  │  │ 健康检查  │  │ 事件总线  │  │ 报告生成 │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                          │
│  Tools (MCP):                                            │
│    ops.log(level, source, message)                       │
│    ops.health(service?)                                  │
│    ops.event(type, payload)                              │
│    ops.report(type, period)                              │
│    ops.status()                                          │
│    ops.alert(severity, message)                          │
└──────────┬──────────────────────────────────────────────┘
           │
    ┌──────┴──────┬──────────┬──────────┐
    │             │          │          │
┌───▼───┐  ┌─────▼────┐ ┌───▼───┐ ┌───▼───┐
│agent- │  │Agora     │ │KOS    │ │Shared │
│mesh   │  │          │ │       │ │Brain  │
│:3000  │  │:7430     │ │:7420  │ │:7420  │
└───────┘  └──────────┘ └───────┘ └───────┘
```

---

## 三、技术选型

| 选择 | 理由 |
|:----:|------|
| **Python + fastmcp** | 与现有 13 个 Python 项目一致 |
| **SQLite** | 零配置持久化，与 KOS/SharedBrain 一致 |
| **stdio 传输** | 标准 MCP，Agora 可直接路由 |
| **~/.hermes/ops/** | 与其他 hermes 基础设施共存 |
| **YAML 配置** | 与项目配置风格一致 |

---

## 四、服务目录结构

```
~/.hermes/ops/
├── server.py              # MCP server 入口
├── config.yaml             # 服务配置
├── logger.py               # 统一日志模块
├── monitor.py              # 健康检查模块
├── events.py               # 事件总线模块
├── reports.py              # 报告生成模块
├── alerts.py               # 告警模块
├── db.py                   # SQLite 持久化
├── schedule.py             # 定时任务调度
├── __init__.py
├── tests/
│   └── test_ops.py
└── data/
    ├── ops.db              # SQLite 数据库
    ├── logs/               # 统一日志存储
    │   ├── 2026-05-28/
    │   │   ├── agentmesh.log
    │   │   ├── agora.log
    │   │   └── health.log
    ├── events/             # 事件存储
    └── reports/            # 报告存储
```

---

## 五、模块设计

### 5.1 Logger — 统一日志

```
格式 (JSON Lines):
  {"ts":"2026-05-28T14:30:00Z","level":"INFO","source":"agentmesh",
   "message":"Task completed","tags":["task","agent"],"duration_ms":150}

MCP Tools:
  ops.log(level, source, message, tags?)
    → 写入统一日志，返回 log_id
  ops.logs(source?, level?, since?, limit?)
    → 查询日志，返回 JSON Lines

约定:
  level: DEBUG/INFO/WARN/ERROR/CRITICAL
  source: 服务名 (agentmesh/agora/kos/shared_brain/ops 等)
  tags: 可选标签列表 (便于分类搜索)
```

### 5.2 Monitor — 健康检查

```
监控对象: ~/.hermes/ops/config.yaml 中注册的服务

每 60 秒 (可配置):
  - 对每个服务执行健康检查
  - 如果服务是 HTTP: curl /healthz
  - 如果服务是 MCP: 尝试连接获取工具列表
  - 如果服务是 CLI: 运行 --version 验证可执行

MCP Tools:
  ops.health(service?)
    → 返回所有服务的健康状态
    → 格式: {"service": "agentmesh", "status": "up", "since": "..."}
  ops.monitor_start()
    → 启动持续监控（后台线程）
  ops.monitor_stop()
    → 停止监控
  ops.metrics(service, metric?, period?)
    → 返回监控指标 (avg_response_time, uptime_percent 等)
```

### 5.3 Events — 事件总线

```
事件类型:
  SERVICE_UP / SERVICE_DOWN     → 服务启动/停止
  BACKUP_SUCCESS / BACKUP_FAIL  → 备份成功/失败
  TEST_DEGRADATION              → 测试数低于阈值
  FRESHNESS_ALERT               → 保鲜检查超期
  HEALTH_REPORT_READY           → 健康报告生成
  KEY_ROTATION_DUE              → 密钥轮换到期

MCP Tools:
  ops.event(type, payload)
    → 触发事件
    → 自动匹配告警规则
  ops.events(type?, since?, limit?)
    → 查询事件历史
  ops.event_subscribe(types?)
    → 订阅事件（SSE 流）
```

### 5.4 Reports — 报告生成

```
报告类型:
  daily    — 每日健康快照
  weekly   — 每周健康报告 (合并到 x2-health-report)
  monthly  — 月度趋势分析

MCP Tools:
  ops.report(type, period?)
    → 生成指定类型报告
    → 返回 Markdown 文本
  ops.report_schedule(type, cron_expression)
    → 注册定时报告
  ops.reports_list()
    → 列出已有报告
```

### 5.5 Alerts — 告警

```
告警规则 (在 config.yaml 中定义):
  - 条件: 备份连续失败 2 次
    动作: ops.log(ERROR) + ops.event(BACKUP_FAIL_ALERT)
  - 条件: 服务不可用 > 5 分钟
    动作: ops.log(CRITICAL) + ops.event(SERVICE_DOWN)
  - 条件: 测试低于阈值
    动作: ops.event(TEST_DEGRADATION)

MCP Tools:
  ops.alert(severity, message)
    → 触发告警
  ops.alerts(severity?, since?)
    → 查询告警历史
  ops.alert_rules()
    → 列出告警规则
```

### 5.6 Status — 全局状态

```
MCP Tools:
  ops.status()
    → 返回运维中心整体状态
    → {"services_up": 3, "services_down": 1, "last_backup": "...",
       "last_freshness": "...", "total_events_today": 42,
       "active_alerts": 0}
```

---

## 六、系统集成方式

### 已有服务接入方式

```
方式 1: MCP 调用 (推荐)
  python3 -c "
  from mcp.client import MCPClient
  client = MCPClient('hermes-ops')
  client.call('ops.log', level='INFO', source='my-service', message='hello')
  "

方式 2: HTTP POST (简化)
  curl -X POST http://localhost:9800/log \
    -d '{"level":"INFO","source":"my-service","message":"hello"}'

方式 3: Python import (直接)
  from hermes_ops import ops
  ops.log("INFO", "my-service", "hello")

方式 4: Shell (命令行)
  ops-cli log --level INFO --source my-service "hello"
```

### 健康检查集成

```
已有服务需要做的事:
  1. 实现 GET /healthz (HP-01 标准)
  2. 在 config.yaml 中注册:
     services:
       - name: "my-service"
         type: "http"
         endpoint: "http://localhost:PORT/healthz"
         interval: 60

  → 之后 ops 自动监控
```

### Forge 集成

```
自动注册到 Forge:
  forge:ops-log          — 统一日志
  forge:ops-health        — 健康检查
  forge:ops-event         — 事件总线
  forge:ops-report        — 报告生成
  forge:ops-status        — 全局状态
  forge:ops-alert         — 告警
  forge:ops-monitor-start — 启动监控
```

---

## 七、实施路线

```
Wave 1 — 基础 (~3h):
  T1: 项目骨架 (server.py + config.yaml + db.py)
  T2: Logger 模块 (ops.log + ops.logs)
  T3: Monitor 模块 (ops.health + ops.status)
  T4: 集成测试 + Forge 注册

Wave 2 — 事件 (~2h):
  T5: Events 模块 (ops.event + ops.events)
  T6: Alerts 模块 (ops.alert + 告警规则)

Wave 3 — 报告 (~2h):
  T7: Reports 模块 (ops.report + 定时调度)
  T8: 已有 x2-* 脚本迁移到 ops 服务
  T9: 运维总览页面 (dashboard update)

总工时: ~7h | Wave 1-2 可部分并行
```

---

## 八、迁移计划

### 被替换的脚本

```
当前脚本                         → 迁移到
x2-freshness-cron               → ops.schedule 定时任务
x2-backup-brain                 → ops.schedule 定时任务
x2-health-report                → ops.report(weekly)
x2-retrospect                   → ops.report(retrospective)
validate-HP-health-check        → ops.health() 
validate-TST-minimal-coverage   → ops.alert() 告警规则
```

### 保留的脚本

```
保留:
  validate-* (17约束验证)       → 保留，它们验证代码规则，不是运维
  setup-auth-keys               → 保留，一次性密钥生成
  agent-inject-budget           → 保留，平台层工具
```

---

## 九、config.yaml 示例

```yaml
server:
  name: "hermes-ops"
  version: "1.0.0"
  port: 9800
  transport: "stdio"

services:
  - name: "agentmesh-gateway"
    type: "http"
    endpoint: "http://localhost:3000/healthz"
    interval: 60
  
  - name: "agora"
    type: "http"
    endpoint: "http://localhost:7430/healthz"
    interval: 60
  
  - name: "sharedbrain-mcp"
    type: "mcp"
    command: "python3 server/mcp_server.py"
    interval: 300

schedule:
  - name: "freshness"
    cron: "0 3 * * *"
    action: "report"
    report_type: "freshness"
  
  - name: "backup"
    cron: "30 3 * * *"
    action: "script"
    script: "~/.hermes/scripts/x2-backup-brain"
  
  - name: "health-weekly"
    cron: "0 9 * * 1"
    action: "report"
    report_type: "weekly"

alerts:
  - name: "backup-fail"
    condition: "events.count(type='BACKUP_FAIL', last=7) >= 2"
    severity: "CRITICAL"
  
  - name: "service-down"
    condition: "health.status(service) == 'down' for 5m"
    severity: "CRITICAL"
  
  - name: "test-degradation"
    condition: "events.count(type='TEST_DEGRADATION', last=24h) >= 1"
    severity: "WARN"
```

---

## 十、验收标准

- [ ] `python3 ~/.hermes/ops/server.py --help` 输出帮助
- [ ] `ops.log("INFO", "test", "hello")` 成功写入数据库
- [ ] `ops.health()` 返回所有注册服务的健康状态
- [ ] `ops.event("BACKUP_SUCCESS", {"files": 43})` 触发事件
- [ ] `ops.report("daily")` 生成今日报告
- [ ] `ops.status()` 返回全局状态
- [ ] 所有工具在 Agora 中路由
- [ ] 所有工具在 Forge 中注册
- [ ] 定时任务按 crontab 执行
