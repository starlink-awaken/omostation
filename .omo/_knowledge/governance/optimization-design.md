# 治理优化方案设计

> 告警通知 + Web 仪表板 + 历史分析

---

## 一、治理告警通知

### 1.1 需求分析

**场景**：
- X1-X4 检查失败时自动通知
- 债务健康度下降时告警
- SLA 超时时升级

**用户**：
- 开发者：代码提交时收到 pre-commit 警告
- 架构师：每周收到治理报告
- 管理者：月度治理概览

### 1.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    治理告警系统                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [触发源] ──→ [告警引擎] ──→ [路由] ──→ [通知渠道]          │
│     │           │           │           │                   │
│     │           │           │           │                   │
│  X1-X4检查    AlertEngine  Router    - Log                │
│  债务审计                   │        - Webhook             │
│  SLA超时                    │        - Email               │
│                            │        - MCP通知              │
│                            │                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 数据结构

```python
# governance/alert.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AlertSeverity(Enum):
    """告警严重程度"""
    CRITICAL = "critical"  # 立即通知
    HIGH = "high"          # 1小时内通知
    MEDIUM = "medium"      # 汇总通知
    LOW = "low"            # 仅记录


class AlertChannel(Enum):
    """通知渠道"""
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    MCP = "mcp"


@dataclass
class GovernanceAlert:
    """治理告警"""
    alert_id: str
    severity: AlertSeverity
    dimension: str  # X1/X2/X3/X4
    check_id: str
    message: str
    timestamp: datetime
    channels: list[AlertChannel]
    metadata: dict | None = None


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    dimension: str
    condition: str  # "fail", "warn_count > 3", "sla_violated"
    severity: AlertSeverity
    channels: list[AlertChannel]
    enabled: bool = True
```

### 1.4 告警规则配置

```yaml
# .omo/_truth/registry/governance-alerts.yaml

rules:
  # X1 审计链
  - id: x1-fail
    dimension: X1
    condition: "status == 'fail'"
    severity: critical
    channels: [log, webhook]
    
  # X2 抗熵
  - id: x2-debt-weight-low
    dimension: X2
    condition: "debt_weight < 0.7"
    severity: high
    channels: [log, webhook]
    
  - id: x2-debt-health-low
    dimension: X2
    condition: "debt_health < 70"
    severity: high
    channels: [log, webhook]
    
  # X3 价值栈
  - id: x3-critical-debt
    dimension: X3
    condition: "critical_count > 0"
    severity: high
    channels: [log, webhook]
    
  # X4 一致性
  - id: x4-ci-missing
    dimension: X4
    condition: "ci_count < 5"
    severity: medium
    channels: [log]
    
  - id: x4-githooks-missing
    dimension: X4
    condition: "missing_githooks > 0"
    severity: medium
    channels: [log]

# 通知渠道配置
channels:
  log:
    enabled: true
    path: "/tmp/governance-alerts.log"
    
  webhook:
    enabled: false
    url: ""
    timeout: 10
    
  email:
    enabled: false
    smtp_host: ""
    recipients: []
```

### 1.5 告警引擎实现

```python
# governance/alert_engine.py

from .alert import GovernanceAlert, AlertRule, AlertSeverity, AlertChannel
from .registry import GovernanceRegistry


class AlertEngine:
    """告警引擎"""
    
    def __init__(self, rules_path: str | Path):
        self.rules = self._load_rules(rules_path)
        self.handlers: dict[AlertChannel, Callable] = {}
    
    def register_handler(self, channel: AlertChannel, handler: Callable):
        """注册通知处理器"""
        self.handlers[channel] = handler
    
    def evaluate(self, check_results: list[CheckResult]) -> list[GovernanceAlert]:
        """评估检查结果，生成告警"""
        alerts = []
        for result in check_results:
            for rule in self.rules:
                if self._match_rule(rule, result):
                    alert = self._create_alert(rule, result)
                    alerts.append(alert)
        return alerts
    
    def process(self, alerts: list[GovernanceAlert]):
        """处理告警"""
        for alert in alerts:
            for channel in alert.channels:
                handler = self.handlers.get(channel)
                if handler:
                    handler(alert)
    
    def _match_rule(self, rule: AlertRule, result: CheckResult) -> bool:
        """匹配规则"""
        if rule.dimension != result.dimension:
            return False
        # 简化匹配逻辑
        if rule.condition == "fail" and result.status == CheckStatus.FAIL:
            return True
        return False
    
    def _create_alert(self, rule: AlertRule, result: CheckResult) -> GovernanceAlert:
        """创建告警"""
        return GovernanceAlert(
            alert_id=f"alert-{rule.rule_id}-{result.check_id}",
            severity=rule.severity,
            dimension=result.dimension,
            check_id=result.check_id,
            message=result.message,
            timestamp=datetime.now(timezone.utc),
            channels=rule.channels,
        )
```

### 1.6 实施计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | 告警规则配置 + Log 通知 | 1 天 |
| Phase 2 | Webhook 通知 (Discord/Slack) | 2 天 |
| Phase 3 | Email 通知 | 1 天 |
| Phase 4 | MCP 通知 (Agent) | 1 天 |

---

## 二、治理 Web 仪表板

### 2.1 需求分析

**场景**：
- 实时查看治理状态
- 历史趋势图表
- 项目对比视图

**用户**：
- 开发者：快速查看项目健康度
- 架构师：分析治理趋势
- 管理者：月度汇报

### 2.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    治理 Web 仪表板                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [数据源] ──→ [API] ──→ [前端] ──→ [用户]                  │
│     │           │           │           │                   │
│     │           │           │           │                   │
│  governance   FastAPI    React/Vue    Browser              │
│  -data.json   endpoints  Dashboard                        │
│  system.yaml                                               │
│  health-trend.md                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 API 设计

```python
# governance/web/api.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Governance Dashboard API")


@app.get("/api/governance/health")
async def get_health():
    """获取治理健康度"""
    return {
        "health_score": 82.0,
        "debt_weight": 1.0,
        "debt_health": 100.0,
    }


@app.get("/api/governance/check/{dimension}")
async def get_check_results(dimension: str):
    """获取指定维度的检查结果"""
    registry = GovernanceRegistry()
    registry.load()
    results = registry.run_dimension(dimension, REPO_ROOT)
    return {"dimension": dimension, "results": [r.to_dict() for r in results]}


@app.get("/api/governance/trend")
async def get_trend(days: int = 30):
    """获取趋势数据"""
    trend_path = REPO_ROOT / ".omo" / "_control" / "debt-dashboard" / "health-trend.md"
    # 解析趋势数据
    return {"days": days, "trend": [...]}


@app.get("/api/governance/projects")
async def get_projects():
    """获取项目状态"""
    projects = ["kairon", "gbrain", "metaos", "agora", "cockpit", "ecos", "omo", "runtime"]
    result = []
    for proj in projects:
        proj_dir = REPO_ROOT / "projects" / proj
        result.append({
            "name": proj,
            "status": "healthy" if (proj_dir / ".githooks").exists() else "warning",
        })
    return {"projects": result}


@app.get("/api/governance/leaderboard")
async def get_leaderboard():
    """获取排行榜"""
    # 复用 leaderboard 逻辑
    return {"leaderboard": [...]}
```

### 2.4 前端设计

**页面结构**：

```
/dashboard
├── /overview          总览页
├── /checks            检查结果页
├── /trend             趋势图页
├── /projects          项目对比页
└── /settings          设置页
```

**总览页组件**：

```
┌─────────────────────────────────────────────────────────────┐
│  治理仪表板                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │ 健康度  │ │债务权重 │ │已解决   │ │待解决   │         │
│  │  82.0   │ │  1.00   │ │   9     │ │   0     │         │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  健康度趋势                                          │   │
│  │  [图表: 62.5 → 79.5 → 97.0 → 100.0]                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────┐ ┌─────────────────────┐         │
│  │  X1-X4 检查状态      │ │  项目排行榜          │         │
│  │  X1: ✅              │ │  kairon: 100/100    │         │
│  │  X2: ✅              │ │  gbrain: 70/100     │         │
│  │  X3: ✅              │ │  metaos: 100/100    │         │
│  │  X4: ✅              │ │  ...                │         │
│  └─────────────────────┘ └─────────────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.5 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 后端 | FastAPI | 与 cockpit 一致 |
| 前端 | Vue 3 + Vite | 轻量、快速 |
| 图表 | Chart.js | 简单易用 |
| 样式 | Tailwind CSS | 快速开发 |

### 2.6 实施计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | API 端点 (5 个) | 2 天 |
| Phase 2 | 总览页 + 检查页 | 3 天 |
| Phase 3 | 趋势图 + 排行榜 | 2 天 |
| Phase 4 | 集成到 cockpit | 1 天 |

---

## 三、治理历史分析

### 3.1 需求分析

**场景**：
- 追踪治理指标的长期变化
- 识别退化模式
- 预测未来趋势

**用户**：
- 架构师：分析治理演进
- 管理者：评估治理效果

### 3.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    治理历史分析系统                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [数据采集] ──→ [存储] ──→ [分析] ──→ [可视化]              │
│     │           │           │           │                   │
│     │           │           │           │                   │
│  定时检查    SQLite/JSON   分析引擎   图表/报告             │
│  检查结果    history.db    trend      dashboard             │
│                            anomaly                          │
│                            predict                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 数据结构

```python
# governance/history.py

from dataclasses import dataclass
from datetime import datetime


@dataclass
class HealthSnapshot:
    """健康度快照"""
    timestamp: datetime
    health_score: float
    debt_weight: float
    debt_health: float
    resolved_count: int
    unresolved_count: int


@dataclass
class CheckHistory:
    """检查历史"""
    timestamp: datetime
    dimension: str
    check_id: str
    status: str
    message: str
    duration_ms: int


@dataclass
class TrendAnalysis:
    """趋势分析"""
    metric: str
    current: float
    previous: float
    change: float
    trend: str  # "improving", "stable", "degrading"
```

### 3.4 存储设计

```sql
-- 治理历史数据库

-- 健康度快照表
CREATE TABLE health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    health_score REAL,
    debt_weight REAL,
    debt_health REAL,
    resolved_count INTEGER,
    unresolved_count INTEGER
);

-- 检查历史表
CREATE TABLE check_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    dimension TEXT,
    check_id TEXT,
    status TEXT,
    message TEXT,
    duration_ms INTEGER
);

-- 告警历史表
CREATE TABLE alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    alert_id TEXT,
    severity TEXT,
    dimension TEXT,
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE
);
```

### 3.5 分析功能

#### 趋势分析

```python
def analyze_trend(history: list[HealthSnapshot], metric: str) -> TrendAnalysis:
    """分析趋势"""
    if len(history) < 2:
        return TrendAnalysis(metric=metric, current=0, previous=0, change=0, trend="stable")
    
    current = getattr(history[-1], metric)
    previous = getattr(history[-2], metric)
    change = current - previous
    
    if change > 0.05:
        trend = "improving"
    elif change < -0.05:
        trend = "degrading"
    else:
        trend = "stable"
    
    return TrendAnalysis(
        metric=metric,
        current=current,
        previous=previous,
        change=change,
        trend=trend,
    )
```

#### 异常检测

```python
def detect_anomalies(history: list[HealthSnapshot], window: int = 7) -> list:
    """检测异常"""
    anomalies = []
    if len(history) < window:
        return anomalies
    
    recent = history[-window:]
    avg_score = sum(s.health_score for s in recent) / len(recent)
    
    for snapshot in recent:
        if abs(snapshot.health_score - avg_score) > 0.2:
            anomalies.append({
                "timestamp": snapshot.timestamp,
                "score": snapshot.health_score,
                "avg": avg_score,
                "deviation": snapshot.health_score - avg_score,
            })
    
    return anomalies
```

#### 预测

```python
def predict_trend(history: list[HealthSnapshot], days: int = 7) -> list:
    """预测未来趋势"""
    if len(history) < 3:
        return []
    
    # 简单线性回归
    scores = [s.health_score for s in history]
    n = len(scores)
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    
    numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean
    
    predictions = []
    for i in range(1, days + 1):
        predicted = slope * (n + i - 1) + intercept
        predictions.append({
            "day": i,
            "predicted_score": min(max(predicted, 0), 100),
        })
    
    return predictions
```

### 3.6 报告生成

```python
def generate_history_report(history: list[HealthSnapshot]) -> str:
    """生成历史分析报告"""
    trend = analyze_trend(history, "health_score")
    anomalies = detect_anomalies(history)
    predictions = predict_trend(history)
    
    report = f"""
# 治理历史分析报告

## 趋势分析
- 当前健康度: {trend.current:.1f}
- 趋势: {trend.trend}
- 变化: {trend.change:+.1f}

## 异常检测
- 检测到 {len(anomalies)} 个异常

## 未来预测
- 7 天后预测: {predictions[-1]['predicted_score']:.1f}

## 建议
"""
    
    if trend.trend == "degrading":
        report += "- ⚠️ 健康度正在下降，建议立即检查\n"
    if anomalies:
        report += f"- 发现 {len(anomalies)} 个异常点，建议深入分析\n"
    
    return report
```

### 3.7 实施计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | 数据采集 + SQLite 存储 | 2 天 |
| Phase 2 | 趋势分析 + 异常检测 | 2 天 |
| Phase 3 | 预测功能 | 1 天 |
| Phase 4 | 报告生成 + 可视化 | 2 天 |

---

## 四、集成方案

### 4.1 系统集成

```
┌─────────────────────────────────────────────────────────────┐
│                    治理优化系统集成                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │  告警通知    │    │  Web 仪表板  │    │  历史分析    │   │
│  └─────────────┘    └─────────────┘    └─────────────┘   │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                 │
│                    ┌─────────────┐                         │
│                    │  治理注册表  │                         │
│                    └─────────────┘                         │
│                           │                                 │
│                    ┌─────────────┐                         │
│                    │  L0 治理模块 │                         │
│                    └─────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```
X1-X4 检查 → 检查结果
    │
    ├──→ 告警引擎 → 通知
    │
    ├──→ 历史存储 → 分析 → 报告
    │
    └──→ Web API → 仪表板
```

---

## 五、总实施计划

| 阶段 | 内容 | 时间 | 依赖 |
|------|------|------|------|
| Phase 1 | 告警通知 (Log + Webhook) | 3 天 | 无 |
| Phase 2 | Web 仪表板 API | 2 天 | Phase 1 |
| Phase 3 | Web 仪表板前端 | 3 天 | Phase 2 |
| Phase 4 | 历史数据采集 | 2 天 | 无 |
| Phase 5 | 趋势分析 + 预测 | 3 天 | Phase 4 |
| Phase 6 | 集成测试 + 部署 | 2 天 | Phase 3+5 |
| **总计** | | **15 天** | |

---

## 六、资源需求

| 资源 | 数量 | 说明 |
|------|------|------|
| 开发 | 15 人天 | 全栈开发 |
| 测试 | 3 人天 | 功能 + 集成测试 |
| 部署 | 2 人天 | 环境配置 + 上线 |

---

*文档版本: 1.0*
*创建日期: 2026-06-12*
