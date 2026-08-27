---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: strategy-observability-v1.md
deprecated-since: 2026-06-23

---

# eCOS 全系统可观测性战略方案 (v1.0)

> 2026-06-06 | 战略级方案
> 目标：将日志/事件/监控/Dashboard 统一到 OMO 治理体系中，不建独立可观测性系统
> 历史可观测性战略方案 / reference only。本文记录当时的整合思路，不是当前日志/事件/指标/状态链路的实时实现真相 SSOT。
> 当前事实请回看 `/.omo/standards/omo-governance-surfaces.md`、`/.omo/state/system.yaml`、当前 observability/runtime/omo 证据。

---

## 一、战略原则

### 1.1 核心主张

> **不建独立的可观测性系统。将可观测性数据直接纳入 OMO 治理的数据流。**
>
> 日志 → OMO evidence 链
> 事件 → OMO state 自动更新
> 监控 → OMO refresh 自动化
> Dashboard → OMO CLI + 静态 HTML

### 1.2 为什么

| 方案 | 代价 | 收益 |
|------|------|------|
| 搭建 Prometheus + Grafana | 新基础设施、新学习曲线 | 好看的图，但不进治理决策 |
| 整合到 OMO 治理 | 已有系统、扩展即可 | 可观测数据直接驱动治理决策 |
| 两者都做 | 双倍维护 | 治理决策仍在 OMO 里 |

**选型**: 整合到 OMO 治理。Grafana 的图好看但不会帮我们判断是否该 close 一个 debt。OMO 的 state 变化才会。

### 1.3 数据分类

```
观测数据 = 4 类，各有不同生命周期和消费方式:

┌──────────────┬──────────────┬─────────────────┬──────────────┐
│   日志 (Log)  │   事件 (Event)│   指标 (Metric)  │   状态 (State)│
├──────────────┼──────────────┼─────────────────┼──────────────┤
│ 不可变记录    │ 可消费信号    │ 可聚合数值       │ 当前快照      │
│ JSONL 文件    │ 总线发布/订阅 │ _STATS / counters│ YAML 文件     │
│ 15K+ 行已累积 │ bus_consumer  │ LLM token 计数   │ system.yaml   │
│ TTL: 永久保留  │ TTL: 处理后丢弃│ TTL: 按周期重置  │ TTL: 覆盖更新  │
└──────┬───────┴──────┬───────┴───────┬─────────┴──────┬───────┘
       │              │               │                │
       ▼              ▼               ▼                ▼
  omo evidence    omo state        omo cost         omo state
  add --stdin     refresh          report            show
```

---

## 二、架构设计

### 2.1 数据流

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  服务层      │     │  OMO 治理层       │     │  展示层       │
│             │     │                  │     │              │
│ agent-      │────▶│  KEI audit hook  │────▶│  CLI:        │
│ runtime     │     │  → record_audit  │     │  omo kei     │
│             │     │  → kei_audit.jsonl│     │  dashboard   │
│ agora       │────▶│                  │     │              │
│ (event_bus) │     │  EventBus →      │────▶│  CLI:        │
│             │     │  state refresh   │     │  omo state   │
│ runtime     │────▶│                  │     │  show        │
│ schedul er  │     │  health scan →   │────▶│              │
│             │     │  _freshness →    │     │  CLI:        │
│ llm-gateway │────▶│  system_health   │     │  omo state   │
│             │     │  .yaml            │     │  health      │
│ kairon 各包 │────▶│                  │────▶│              │
│ (MCP tools) │     │  _STATS →         │     │  CLI:        │
│             │     │  cost tracking    │     │  omo cost    │
└─────────────┘     │                  │     └──────────────┘
                    │  .omo/_delivery/ │     ┌──────────────┐
                    │  governance-     │────▶│  Web:        │
                    │  report          │     │  dash.html   │
                    └──────────────────┘     │  (静态)      │
                                             └──────────────┘
```

### 2.2 与 5+3+1 的映射

| 架构层 | 可观测性角色 | 实现方式 |
|--------|-------------|---------|
| **L0 协议** | 协议调用日志 | MCP tool `record_audit` (已有) |
| **L1 运行时** | 服务健康 + freshness | `scheduler.py` → `system_health.yaml` (已有) |
| **L2 OMO 治理** | 债务趋势 + 治理报告 | `omo-debt report-trend` → `_delivery/` (已有) |
| **L2 kairon 引擎** | LLM Token 用量 | `_STATS` → JSONL (缺口) |
| **X1 审计** | KEI 审计链闭环 | 15K 行 → 告警阈值 (缺口: 告警未接) |
| **X2 抗熵** | 服务 freshness 自动恢复 | autoheal + stale detection (已有) |
| **X3 价值栈** | 成本追踪 | — (未实现) |
| **I0 集成织层** | 事件总线 | Agora EventBus (代码存在, 零消费) |

### 2.3 数据保留策略

| 数据类型 | 保留期 | 存储方式 | 清理策略 |
|---------|--------|---------|---------|
| KEI 审计 (JSONL) | 永久 | `~/.runtime/data/` | 归档到 `_archive/` |
| 执行日志 (JSONL) | 90 天 | `agent-runtime/` | 按日期轮转 |
| TaskObject 信封 | 30 天 | `~/.runtime/` | 自动清理 |
| 健康快照 (YAML) | 永久(覆写) | `state/system_health.yaml` | 每次刷新覆写 |
| 治理报告 (MD) | 永久 | `_delivery/` | 归档到 `_archive/` |

---

## 三、实施路线

### Wave 1: 观测层基础设施 (1-2 天)

**目标**: 将所有已有的观测数据纳入 CLI 可查询范围

```
输出:
  omo log search --since 2026-06-01 --level error    # 搜索 KEI 审计日志
  omo log tail --file kei_audit --lines 10            # 实时 tail
  omo event list                                      # Agora 事件总线状态
  omo event subscribe --type service_down             # 订阅事件
  omo metric show                                     # _STATS 计数器
```

实施方式: 在 `omo_observability.py` 模块中封装，直接读 JSONL 文件。

### Wave 2: 事件驱动状态更新 (2-3 天)

**目标**: 事件自动触发 OMO 状态更新，无需手动运行 `omo state refresh`

```
流程:
  service failure → Agora EventBus → bus_consumer → omo state refresh
  debt due        → Cron → omo-debt dispatch       → review queue update
  health change   → scheduler → system_health.yaml  → health_score update
```

实施方式: 
- Agora EventBus 的 `publish_event` 调用 `omo state refresh` 子进程
- `scheduler.py` 的状态变化写入 `state/system_health.yaml` 后通知 OMO
- 债务到期由 Cron 自动触发

### Wave 3: 告警闭环 (2-3 天)

**目标**: 从"日志只写不读"到"异常自动通知"

```
阈值:
  KEI 阻断率 > 10/小时 → WeChat 通知
  服务不可达 > 5分钟   → WeChat 通知  
  债务到期未处理       → 每日摘要推送
  LLM Token 日消耗 > 阈值 → 成本告警

通知通道 (优先级):
  P0: WeChat (通过 Hermes send_message)
  P1: 本地通知 (macOS Notification Center)
  P2: 日志 (始终)
```

实施方式: 
- `scheduler.py` 的状态变化触发 `scripts/notify-alerts.sh`
- `notify-alerts.sh` 配置 WeChat webhook
- 增加 `omo alert list` / `omo alert ack` 命令

### Wave 4: 统一 Web Dashboard (3-5 天)

**目标**: CLI 仪表板内容搬到浏览器

```
架构:
  omo dashboard --serve :9090
  └── 单页 HTML + SSE
       ├── 系统状态 (Phase/Health)
       ├── 服务健康 (12 服务状态卡片)
       ├── 债务仪表盘 (open/resolved 趋势图)
       ├── KEI 审计 (阻断率/执行量)
       └── 事件流 (最近 50 条事件)
```

实施方式: 不引入框架。纯静态 HTML + JavaScript SSE。数据来源: `omo state show --json` + `omo kei dashboard --json`。

---

## 四、成本估算

| Wave | 工作量 | 新文件 | 主要变更 |
|------|--------|--------|---------|
| W1 观测层 | 1-2 天 | 2 个 | omo_observability.py + omo_event.py |
| W2 事件驱动 | 2-3 天 | 3 个 | bus_consumer 改造 + scheduler 通知 + cron 触发 |
| W3 告警闭环 | 2-3 天 | 2 个 | notify-alerts.sh 配置 + omo_alert.py |
| W4 Web Dashboard | 3-5 天 | 2 个 | dashboard.html + dashboard_server.py 改造 |
| **合计** | **8-13 天** | **9 个** | |

---

## 五、与现有系统对比

| 需求 | 当前最好的方案 | Wave 1 后 | Wave 4 后 |
|------|--------------|----------|----------|
| 查 KEI 审计 | 手动 cat JSONL | `omo log search --level error` | Web 趋势图 |
| 看服务健康 | `omo state health` | `omo state health` | Web 状态卡片 |
| 知债务趋势 | `omo-debt report-trend` | `omo-debt report-trend` | Web 趋势图 |
| 查 LLM 成本 | ❌ 无 | ❌ 无 | `omo cost estimate` |
| 服务挂了通知 | ❌ 无 | WeChat (如果配了 webhook) | WeChat + Dashboard 红点 |
| 跨系统排查 | ❌ 无 | `omo log search` | 一站式 Web |
