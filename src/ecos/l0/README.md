# L0 协议层 — 治理框架

> eCOS v6 最底层抽象，定义治理原语、检查器模式、事件总线、告警引擎和历史存储

---

## 架构

```
l0/
├── ssb/           SSB 签名链 (1,737 行)
├── emergence/     涌现度量 (1,162 行)
├── governance/    治理框架 (1,200+ 行) ← 本文档
├── ssot/          SSOT 元模型 (18,197 行)
└── symphony/      交响编排 (1,087 行)
```

---

## governance 模块

### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| primitives | primitives.py | 治理原语: CheckResult, GovernanceCheck, GovernanceEvent |
| checkers | checkers.py | X1-X4 检查器实现 |
| event_bus | event_bus.py | 治理事件总线 |
| registry | registry.py | 检查器注册表 |
| optimization | optimization.py | 优化原语: Alert, Dashboard, History |
| alert_engine | alert_engine.py | 告警引擎 |
| history_store | history_store.py | 历史存储 (SQLite) |

### X1-X4 检查器

| 检查器 | 维度 | 职责 |
|--------|------|------|
| X1AuditChainChecker | X1 审计链 | 检查操作是否安全 |
| X2StalenessChecker | X2 抗熵 | 检查数据是否新鲜 |
| X3ValueChecker | X3 价值栈 | 检查投入是否合理 |
| X4ConsistencyChecker | X4 一致性 | 检查规则是否被遵守 |

### 优化组件

| 组件 | 说明 |
|------|------|
| AlertEngine | 告警引擎 (规则匹配 + 通知分发) |
| SQLiteHistoryStore | 历史存储 (SQLite + 趋势分析 + 预测) |
| LogHandler | 日志告警处理器 |
| WebhookHandler | Webhook 告警处理器 |

### 使用示例

```python
from pathlib import Path
from ecos.l0.governance import (
    GovernanceRegistry,
    AlertEngine,
    SQLiteHistoryStore,
    LogHandler,
    HealthSnapshot,
)

repo_root = Path("/path/to/workspace")

# 1. 运行检查
registry = GovernanceRegistry()
registry.load()
results = registry.run_all(repo_root)

# 2. 触发告警
alert_engine = AlertEngine()
alert_engine.register_handler("log", LogHandler("/tmp/alerts.log"))
alerts = alert_engine.evaluate(results)
alert_engine.process(alerts)

# 3. 记录历史
store = SQLiteHistoryStore("/path/to/history.db")
snapshot = HealthSnapshot(
    timestamp=datetime.now(),
    health_score=82.0,
    debt_weight=1.0,
    debt_health=100.0,
    resolved_count=9,
    unresolved_count=0,
)
store.record(snapshot)

# 4. 分析趋势
trend = store.analyze_trend("health_score", days=30)
predictions = store.predict("health_score", days=7)
```

---

## SSOT 对齐

### M1 实体

- `ecos/ssot/mof/m1/governance/GOV-X1-CONSTRAINT.yaml`
- `ecos/ssot/mof/m1/governance/GOV-X2-POLICY.yaml`
- `ecos/ssot/mof/m1/governance/GOV-X3-VALUE.yaml`
- `ecos/ssot/mof/m1/governance/GOV-X4-CONSISTENCY.yaml`

### M2 Schema

- `ecos/ssot/mof/m2/governance_check.yaml`
- `ecos/ssot/mof/m2/governance_event.yaml`
- `ecos/ssot/mof/m2/governance_policy.yaml`

### 注册表

- `.omo/_truth/registry/governance-checks.yaml` — 检查器注册
- `.omo/_truth/registry/governance-alerts.yaml` — 告警规则

---

## 测试

```bash
cd projects/ecos
uv run pytest tests/test_l0/test_governance.py -v
```

---

*最后更新: 2026-06-12*

