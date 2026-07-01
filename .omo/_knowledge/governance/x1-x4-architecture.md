---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# X1-X4 治理框架架构模式

> eCOS v6 跨层治理体系 · L0 抽象 · 体系化设计

---

## 一、架构概览

### 1.1 设计原则

```
┌─────────────────────────────────────────────────────────────┐
│                    X1-X4 治理框架                            │
├─────────────────────────────────────────────────────────────┤
│  L0 抽象层  │ 治理原语 · 检查器模式 · 事件总线              │
├─────────────────────────────────────────────────────────────┤
│  L1 运行时  │ 检查器执行 · 状态管理 · 告警                  │
├─────────────────────────────────────────────────────────────┤
│  L2 引擎面  │ 治理策略 · 优先级 · SLA                       │
├─────────────────────────────────────────────────────────────┤
│  L3 入口层  │ CLI · Web · MCP                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心抽象

| 抽象 | 说明 | 实现位置 |
|------|------|----------|
| GovernanceCheck | 治理检查器基类 | ecos/l0/governance/ |
| CheckResult | 检查结果数据结构 | ecos/l0/governance/ |
| GovernanceEvent | 治理事件 | ecos/l0/governance/ |
| GovernancePolicy | 治理策略 | ecos/l0/governance/ |

---

## 二、L0 抽象层设计

### 2.1 治理原语 (Governance Primitives)

```python
# ecos/l0/governance/primitives.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class CheckSeverity(Enum):
    """检查严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckStatus(Enum):
    """检查状态"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    """检查结果"""
    check_id: str
    dimension: str  # X1/X2/X3/X4
    status: CheckStatus
    message: str
    severity: CheckSeverity = CheckSeverity.MEDIUM
    timestamp: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class GovernanceEvent:
    """治理事件"""
    event_type: str  # check_started / check_passed / check_failed / alert_triggered
    dimension: str
    check_id: str
    result: Optional[CheckResult] = None
    timestamp: Optional[datetime] = None


class GovernanceCheck(ABC):
    """治理检查器基类"""
    
    def __init__(self, check_id: str, dimension: str):
        self.check_id = check_id
        self.dimension = dimension
    
    @abstractmethod
    def execute(self) -> CheckResult:
        """执行检查"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取检查描述"""
        pass
```

### 2.2 检查器模式 (Checker Pattern)

```python
# ecos/l0/governance/checkers.py

from .primitives import GovernanceCheck, CheckResult, CheckStatus, CheckSeverity


class X1AuditChainChecker(GovernanceCheck):
    """X1 审计链检查器"""
    
    def __init__(self):
        super().__init__("x1-audit-chain", "X1")
    
    def execute(self) -> CheckResult:
        # 检查债务审计
        # 检查 pre-commit hook
        # 检查审计报告
        pass
    
    def get_description(self) -> str:
        return "检查操作是否安全：债务审计 + 操作审计"


class X2StalenessChecker(GovernanceCheck):
    """X2 抗熵检查器"""
    
    def __init__(self):
        super().__init__("x2-staleness", "X2")
    
    def execute(self) -> CheckResult:
        # 检查 debt_weight
        # 检查 debt_health
        # 检查健康度趋势
        pass
    
    def get_description(self) -> str:
        return "检查数据是否新鲜：债务新鲜度 + 健康度趋势"


class X3ValueChecker(GovernanceCheck):
    """X3 价值栈检查器"""
    
    def __init__(self):
        super().__init__("x3-value", "X3")
    
    def execute(self) -> CheckResult:
        # 检查债务优先级
        # 检查 SLA 达成
        # 检查 ROI
        pass
    
    def get_description(self) -> str:
        return "检查投入是否合理：债务优先级 + SLA 达成"


class X4ConsistencyChecker(GovernanceCheck):
    """X4 一致性检查器"""
    
    def __init__(self):
        super().__init__("x4-consistency", "X4")
    
    def execute(self) -> CheckResult:
        # 检查 CI 工作流
        # 检查 pre-commit 配置
        # 检查文档一致性
        pass
    
    def get_description(self) -> str:
        return "检查规则是否被遵守：CI + pre-commit + 文档"
```

### 2.3 事件总线 (Event Bus)

```python
# ecos/l0/governance/event_bus.py

from typing import Callable, List
from .primitives import GovernanceEvent


class GovernanceEventBus:
    """治理事件总线"""
    
    def __init__(self):
        self._handlers: dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def publish(self, event: GovernanceEvent):
        """发布事件"""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
    
    def emit_check_started(self, check_id: str, dimension: str):
        """发射检查开始事件"""
        self.publish(GovernanceEvent(
            event_type="check_started",
            dimension=dimension,
            check_id=check_id
        ))
    
    def emit_check_completed(self, check_id: str, dimension: str, result):
        """发射检查完成事件"""
        self.publish(GovernanceEvent(
            event_type="check_completed",
            dimension=dimension,
            check_id=check_id,
            result=result
        ))
```

---

## 三、L1 运行时层

### 3.1 检查器执行器

```python
# runtime/governance/executor.py

from ecos.l0.governance import GovernanceCheck, CheckResult, GovernanceEventBus


class GovernanceExecutor:
    """治理检查执行器"""
    
    def __init__(self, event_bus: GovernanceEventBus):
        self.event_bus = event_bus
        self.checkers: list[GovernanceCheck] = []
    
    def register_checker(self, checker: GovernanceCheck):
        """注册检查器"""
        self.checkers.append(checker)
    
    def run_all(self) -> list[CheckResult]:
        """运行所有检查"""
        results = []
        for checker in self.checkers:
            self.event_bus.emit_check_started(checker.check_id, checker.dimension)
            result = checker.execute()
            self.event_bus.emit_check_completed(checker.check_id, checker.dimension, result)
            results.append(result)
        return results
    
    def run_dimension(self, dimension: str) -> list[CheckResult]:
        """运行指定维度检查"""
        return [c.execute() for c in self.checkers if c.dimension == dimension]
```

### 3.2 状态管理

```python
# runtime/governance/state.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ecos.l0.governance import CheckResult, CheckStatus


@dataclass
class GovernanceState:
    """治理状态"""
    dimension: str
    last_check: Optional[datetime] = None
    last_status: Optional[CheckStatus] = None
    check_count: int = 0
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    
    def update(self, result: CheckResult):
        """更新状态"""
        self.last_check = result.timestamp
        self.last_status = result.status
        self.check_count += 1
        if result.status == CheckStatus.PASS:
            self.pass_count += 1
        elif result.status == CheckStatus.WARN:
            self.warn_count += 1
        elif result.status == CheckStatus.FAIL:
            self.fail_count += 1
    
    @property
    def pass_rate(self) -> float:
        """通过率"""
        return self.pass_count / self.check_count if self.check_count > 0 else 0
```

---

## 四、L2 引擎面层

### 4.1 治理策略

```python
# governance/policy.py

from dataclasses import dataclass
from typing import Optional
from ecos.l0.governance import CheckSeverity


@dataclass
class GovernancePolicy:
    """治理策略"""
    dimension: str
    max_warn_before_fail: int = 3
    max_fail_before_alert: int = 1
    sla_response_hours: Optional[int] = None
    sla_resolution_hours: Optional[int] = None
    
    # 债务相关
    debt_weight_threshold: float = 0.9
    debt_health_threshold: float = 90.0
    resolved_rate_threshold: float = 0.9


# 预定义策略
X1_POLICY = GovernancePolicy(
    dimension="X1",
    sla_response_hours=1,
    sla_resolution_hours=24,
    max_warn_before_fail=2,
)

X2_POLICY = GovernancePolicy(
    dimension="X2",
    debt_weight_threshold=0.9,
    debt_health_threshold=90.0,
)

X3_POLICY = GovernancePolicy(
    dimension="X3",
    sla_response_hours=24,
    sla_resolution_hours=168,  # 7 days
)

X4_POLICY = GovernancePolicy(
    dimension="X4",
    max_warn_before_fail=3,
    max_fail_before_alert=1,
)
```

### 4.2 SLA 管理

```python
# governance/sla.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from ecos.l0.governance import CheckSeverity


@dataclass
class SLATarget:
    """SLA 目标"""
    severity: CheckSeverity
    response_hours: int
    resolution_hours: int


# SLA 标准
SLA_TARGETS = {
    CheckSeverity.CRITICAL: SLATarget(CheckSeverity.CRITICAL, 1, 24),
    CheckSeverity.HIGH: SLATarget(CheckSeverity.HIGH, 24, 168),
    CheckSeverity.MEDIUM: SLATarget(CheckSeverity.MEDIUM, 168, 720),
    CheckSeverity.LOW: SLATarget(CheckSeverity.LOW, 720, 2160),
}


class SLAManager:
    """SLA 管理器"""
    
    def __init__(self):
        self.targets = SLA_TARGETS
    
    def check_sla(self, severity: CheckSeverity, created_at: datetime) -> dict:
        """检查 SLA 达成情况"""
        target = self.targets.get(severity)
        if not target:
            return {"status": "unknown"}
        
        now = datetime.now()
        elapsed = (now - created_at).total_seconds() / 3600
        
        response_ok = elapsed <= target.response_hours
        resolution_ok = elapsed <= target.resolution_hours
        
        return {
            "severity": severity.value,
            "elapsed_hours": round(elapsed, 1),
            "response_target": target.response_hours,
            "resolution_target": target.resolution_hours,
            "response_ok": response_ok,
            "resolution_ok": resolution_ok,
            "status": "ok" if response_ok and resolution_ok else "violated",
        }
```

---

## 五、L3 入口层

### 5.1 CLI 接口

```bash
# X1-X4 治理框架 CLI

# 运行所有检查
governance check --all

# 运行指定维度
governance check --dimension X1
governance check --dimension X2
governance check --dimension X3
governance check --dimension X4

# 查看状态
governance status
governance status --dimension X1

# 查看 SLA
governance sla
governance sla --severity critical

# 生成报告
governance report --format html
governance report --format json
```

### 5.2 MCP 工具

```python
# MCP 工具定义
tools = [
    {
        "name": "governance_check",
        "description": "运行 X1-X4 治理检查",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": ["X1", "X2", "X3", "X4", "all"]},
            },
        },
    },
    {
        "name": "governance_status",
        "description": "查看治理状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string"},
            },
        },
    },
    {
        "name": "governance_sla",
        "description": "查看 SLA 达成情况",
        "inputSchema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            },
        },
    },
]
```

---

## 六、数据流

```
┌─────────────────────────────────────────────────────────────┐
│                      数据流                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [触发] ──→ [执行器] ──→ [检查器] ──→ [结果] ──→ [状态]    │
│     │           │           │           │           │       │
│     │           │           │           │           │       │
│  schedule    executor    checker    result      state      │
│  manual                  (X1-X4)   (pass/warn  (metrics   │
│  event                             /fail)      /history)   │
│                                                             │
│  [结果] ──→ [事件总线] ──→ [处理器] ──→ [输出]            │
│     │           │           │           │                  │
│     │           │           │           │                  │
│  result      event_bus    handler    (alert/report/       │
│                              │        dashboard)           │
│                              │                             │
│                           (notify/log/store)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 七、缺口补全计划

### 7.1 X1 操作级审计

**缺口**: kei_sandbox, agora auth, metaos gate 的操作审计

**补全方案**:
```python
# ecos/l0/governance/checkers/x1_operation_audit.py

class X1OperationAuditChecker(GovernanceCheck):
    """X1 操作级审计检查器"""
    
    def execute(self) -> CheckResult:
        # 检查 kei_sandbox audit hook
        # 检查 agora auth 配置
        # 检查 metaos gate 规则
        pass
```

### 7.2 X2 自动修复

**缺口**: 债务自动修复机制

**补全方案**:
```python
# governance/auto_fix.py

class GovernanceAutoFix:
    """治理自动修复"""
    
    def fix_atomic_write(self, file_path: str):
        """修复非原子写入"""
        pass
    
    def fix_test_coverage(self, package_path: str):
        """修复测试覆盖"""
        pass
    
    def fix_doc_version(self, doc_path: str):
        """修复文档版本"""
        pass
```

### 7.3 X3 成本追踪

**缺口**: ROI 分析, 成本追踪

**补全方案**:
```python
# governance/cost_tracking.py

@dataclass
class CostTracking:
    """成本追踪"""
    total_investment: float = 0
    debt_resolution_cost: float = 0
    roi_score: float = 0
    cost_per_debt: float = 0
    
    def calculate_roi(self):
        """计算 ROI"""
        if self.debt_resolution_cost > 0:
            self.roi_score = self.total_investment / self.debt_resolution_cost
```

### 7.4 X4 验证链自动化

**缺口**: 全链验证自动化

**补全方案**:
```yaml
# .github/workflows/x1-x4-validation.yml

name: X1-X4 Validation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  x1-x4-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run X1-X4 checks
        run: make x1-x4-check
```

---

## 八、文件结构

```
ecos/src/ecos/l0/governance/
├── __init__.py
├── primitives.py          # 治理原语 (CheckResult, GovernanceCheck, etc.)
├── checkers.py            # X1-X4 检查器
├── event_bus.py           # 事件总线
└── policies.py            # 治理策略

runtime/governance/
├── __init__.py
├── executor.py            # 检查器执行器
├── state.py               # 状态管理
└── auto_fix.py            # 自动修复

governance/
├── policy.py              # 治理策略定义
├── sla.py                 # SLA 管理
├── cost_tracking.py       # 成本追踪
└── reporting.py           # 报告生成
```

---

## 九、与其他体系的集成

### 9.1 与债务治理体系集成

```
债务治理体系
    │
    ├── debt-audit.sh ──→ X1 审计链检查器
    │
    ├── debt_weight ────→ X2 抗熵检查器
    │
    ├── debt priority ──→ X3 价值栈检查器
    │
    └── CI/pre-commit ──→ X4 一致性检查器
```

### 9.2 与 BOS URI 集成

```
bos://omo/governance/health    ← 治理健康度
bos://omo/governance/check     ← 运行检查
bos://omo/governance/status    ← 查看状态
bos://omo/governance/sla       ← SLA 达成
```

---

## 十、实施路线图

### Phase 1: L0 抽象层 (本周)
- [ ] 创建 governance/primitives.py
- [ ] 创建 governance/checkers.py
- [ ] 创建 governance/event_bus.py
- [ ] 单元测试

### Phase 2: L1 运行时层 (下周)
- [ ] 创建 executor.py
- [ ] 创建 state.py
- [ ] 集成现有脚本

### Phase 3: L2 引擎面层 (第3周)
- [ ] 创建 policy.py
- [ ] 创建 sla.py
- [ ] 创建 cost_tracking.py

### Phase 4: L3 入口层 (第4周)
- [ ] CLI 接口
- [ ] MCP 工具
- [ ] Web 仪表板

---

*文档版本: 1.0*
*创建日期: 2026-06-12*
