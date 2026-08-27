---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 治理优化能力收敛映射
#
> 定义告警、仪表板、历史分析能力在 L0-L3 和 X1-X4 中的位置

---

## 一、能力收敛架构

```
┌─────────────────────────────────────────────────────────────┐
│                    治理优化能力收敛                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L3 入口层                                                  │
│  ├── cockpit CLI: governance check/status/sla/leaderboard   │
│  ├── cockpit MCP: governance_check/status/sla/leaderboard   │
│  └── cockpit Web: 治理仪表板 (新增)                          │
│                                                             │
│  L2 引擎面                                                  │
│  └── omo: 债务管理 + SLA 追踪                                │
│                                                             │
│  L1 运行时                                                  │
│  └── runtime: Cron 调度 + 告警执行                           │
│                                                             │
│  L0 协议层                                                  │
│  ├── governance/primitives.py: 原语定义                      │
│  ├── governance/checkers.py: X1-X4 检查器                   │
│  ├── governance/alert.py: 告警原语 (新增)                    │
│  ├── governance/dashboard.py: 仪表板原语 (新增)              │
│  └── governance/history.py: 历史分析原语 (新增)              │
│                                                             │
│  X 轴 (跨层)                                                │
│  ├── X1 审计链: 检查器执行 → 告警触发                        │
│  ├── X2 抗熵: 历史记录 → 趋势分析 → 预测                    │
│  ├── X3 价值栈: SLA 追踪 → 成本归因                         │
│  └── X4 一致性: 告警路由 → 通知分发 → 规则验证               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、能力收敛映射表

| 能力 | L0 原语 | L1 执行 | L2 引擎 | L3 入口 | X 维度 |
|------|---------|---------|---------|---------|--------|
| **告警通知** | alert.py | runtime/cron | omo/alerts | cockpit MCP | X4 |
| **Web 仪表板** | dashboard.py | - | - | cockpit Web | - |
| **历史分析** | history.py | runtime/cron | omo/history | cockpit CLI | X2 |

---

## 三、详细映射

### 3.1 告警通知

```
L0: governance/optimization.py (GovernanceAlert, AlertRule, AlertHandler)
    │
    ├── X4 一致性: 告警规则定义 + 路由逻辑
    │
    L1: runtime/cron/governance-alert.sh (定时检查)
    │
    L2: omo/alerts/ (告警存储 + 查询)
    │
    L3: cockpit MCP (governance_alerts 工具)
```

**收敛决策**:
- 原语定义 → **L0** (ecos/l0/governance/optimization.py)
- 规则配置 → **X4** (.omo/_truth/registry/governance-alerts.yaml)
- 执行调度 → **L1** (runtime cron)
- 告警存储 → **L2** (omo/alerts)
- 用户接口 → **L3** (cockpit MCP)

### 3.2 Web 仪表板

```
L0: governance/optimization.py (DashboardMetric, DashboardData, DashboardProvider)
    │
    L3: cockpit Web (FastAPI + Vue 3)
    ├── API: /api/governance/*
    └── Frontend: /dashboard/*
```

**收敛决策**:
- 原语定义 → **L0** (ecos/l0/governance/optimization.py)
- API + 前端 → **L3** (cockpit Web)

### 3.3 历史分析

```
L0: governance/optimization.py (HealthSnapshot, TrendAnalysis, Prediction, HistoryAnalyzer)
    │
    ├── X2 抗熵: 数据采集 + 趋势检测
    │
    L1: runtime/cron/governance-history.sh (定时采集)
    │
    L2: omo/history/ (SQLite 存储 + 分析引擎)
    │
    L3: cockpit CLI (governance history 命令)
```

**收敛决策**:
- 原语定义 → **L0** (ecos/l0/governance/optimization.py)
- 数据采集 → **X2** (抗熵检测)
- 存储分析 → **L2** (omo/history)
- 用户接口 → **L3** (cockpit CLI)

---

## 四、L0 原语清单

### 4.1 governance/optimization.py

```python
# 告警原语
AlertSeverity      # 告警严重程度
AlertChannel       # 通知渠道
GovernanceAlert    # 告警数据结构
AlertRule          # 告警规则
AlertHandler       # 处理器基类

# 仪表板原语
DashboardMetric    # 仪表板指标
DashboardData      # 仪表板数据
DashboardProvider  # 数据提供者基类

# 历史分析原语
HealthSnapshot     # 健康度快照
TrendAnalysis      # 趋势分析结果
Prediction         # 预测结果
HistoryAnalyzer    # 分析器基类
```

---

## 五、文件结构

```
ecos/src/ecos/l0/governance/
├── __init__.py
├── primitives.py      # X1-X4 检查原语
├── checkers.py        # X1-X4 检查器
├── event_bus.py       # 事件总线
├── registry.py        # 注册表
└── optimization.py    # 优化原语 (新增)

omo/_truth/registry/
├── governance-checks.yaml     # 检查器注册
├── governance-alerts.yaml     # 告警规则 (新增)
└── governance-dashboard.yaml  # 仪表板配置 (新增)

omo/_control/
├── governance-data.json       # 治理数据
├── governance-history.db      # 历史数据 (新增)
└── debt-dashboard/
    ├── current.yaml
    └── health-trend.md
```

---

## 六、实施顺序

| 阶段 | 内容 | 位置 |
|------|------|------|
| 1 | L0 原语定义 | ecos/l0/governance/optimization.py |
| 2 | 告警规则配置 | .omo/_truth/registry/governance-alerts.yaml |
| 3 | 告警引擎实现 | ecos/l0/governance/alert_engine.py |
| 4 | 历史存储实现 | ecos/l0/governance/history_store.py |
| 5 | 仪表板 API | cockpit/scripts/cockpit_mcp.py |
| 6 | Web 前端 | cockpit/web/ |

---

*文档版本: 1.0*
*创建日期: 2026-06-12*
