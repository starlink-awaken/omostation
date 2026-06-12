# L0 协议层 — 治理框架

> eCOS v5 最底层抽象，定义治理原语、检查器模式和事件总线

---

## 架构

```
l0/
├── ssb/           SSB 签名链 (1,737 行)
├── emergence/     涌现度量 (1,162 行)
├── governance/    治理框架 (456 行) ← 本文档
├── ssot/          SSOT 元模型 (18,197 行)
└── symphony/      交响编排 (1,087 行)
```

---

## governance 模块

### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| primitives | primitives.py | 治理原语: CheckResult, CheckSeverity, CheckStatus, GovernanceCheck, GovernanceEvent |
| checkers | checkers.py | X1-X4 检查器实现 |
| event_bus | event_bus.py | 治理事件总线 |

### X1-X4 检查器

| 检查器 | 维度 | 职责 |
|--------|------|------|
| X1AuditChainChecker | X1 审计链 | 检查操作是否安全 |
| X2StalenessChecker | X2 抗熵 | 检查数据是否新鲜 |
| X3ValueChecker | X3 价值栈 | 检查投入是否合理 |
| X4ConsistencyChecker | X4 一致性 | 检查规则是否被遵守 |

### 使用示例

```python
from pathlib import Path
from ecos.l0.governance import (
    X1AuditChainChecker,
    X2StalenessChecker,
    X3ValueChecker,
    X4ConsistencyChecker,
)

repo_root = Path("/path/to/workspace")

# 运行所有检查
checkers = [
    X1AuditChainChecker(repo_root),
    X2StalenessChecker(repo_root),
    X3ValueChecker(repo_root),
    X4ConsistencyChecker(repo_root),
]

for checker in checkers:
    result = checker.execute()
    print(f"{result.dimension}: {result.status.value} - {result.message}")
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

---

## 测试

```bash
cd projects/ecos
uv run pytest tests/test_l0/test_governance.py -v
```

---

*最后更新: 2026-06-12*
