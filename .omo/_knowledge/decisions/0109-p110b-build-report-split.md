---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0109: P110-B omo_governance_surfaces build_report 子模块化 (443→276L, <300L ideal)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P110-B
- **Extends**: ADR-0098-102 + ADR-0108 (P110-A 跨 submodule 模式)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0108 P110-A 收官 (ecos domain_manager 1914→1406L)。下一候选 P110-B:
- **P110-B 候选**: omo_governance_surfaces.build_governance_surfaces_report (172L)
- 是 omo_governance_surfaces.py 当前最大单函数 (跨 7 check + 8 gate 调用的顶层 aggregator)

**P110-B 调研**:
- 函数位置: L245-417 (172L, 全是顶层 report aggregator)
- 调用: 3 个 cross-sibling check funcs (state_plane / mutation_surface / internal_write_profiles)
- 8 个 has_*_gate 调用
- 业务独立: 顶层 report 编排, 无循环依赖

**P110-B 决策**: 拆 `build_governance_surfaces_report` 到 `omo_governance_surfaces_report.py` 子模块, omo_governance_surfaces.py 443→~270L (<300L ideal).

## Decision

### D1: 子模块创建 (P110-B R3 实施)

| 子模块 | 行数 | 业务 |
|:------|:----:|:-----|
| `omo_governance_surfaces_report.py` | 254L (含 82L header) | 1 顶层 report 函数 (172L) |

**omo_governance_surfaces.py 收口**: 443L → **276L** (-167L, -38%)
- 拆 172L + re-export block +6L = 178L
- 实际 -167L 是因为 re-export 较小 (1 函数)

### D2: Cross-Sibling Imports 范式 (P107 应用)

**子模块导入 8 个 siblings**:
```python
# snapshots: pure data, no further dependencies
from omo.omo_governance_surfaces_snapshots import (
    _mutation_surface_category_counts, _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot, _worker_profile_subtype_counts,
)
# 5 sibling check funcs
from omo.omo_governance_surfaces_ingress import _check_ingress_registry, _resolve_ingress_task_carrier
from omo.omo_governance_surfaces_ingress_artifacts import _check_ingress_artifacts
from omo.omo_governance_surfaces_mutation_surface import _check_mutation_surface_registry
from omo.omo_governance_surfaces_internal_write_profiles import _check_internal_write_profile_registry
from omo.omo_governance_surfaces_state_plane import _check_state_plane_asset_registry
from omo.omo_governance_surfaces_c2g_boundary import _check_c2g_omo_boundary
```

**无 circular 风险** (P107 范式: child → siblings, siblings 互不依赖)

**Inline `_load_yaml` 4L** (P105 范式: 避免 child → parent circular)

### D3: 收口统计

| 指标 | P110-A 末 | P110-B 末 | 变化 |
|:-----|:----------|:----------|:-----:|
| `omo_governance_surfaces.py` | 443L | **276L** | **-167L (-38%)** |
| `omo_governance_surfaces_report.py` | (新) | 254L | +254L |
| god-module warn (>800L) | 0 (本文件) | **0** | ✓ |
| **god-module ideal (<600L)** | 0 | **1 (276L < 600L ideal)** | **新 ideal 达成** |
| 工具数 | 47 | 47 | 不变 |
| ADR 数 | 68 | **69** | +1 (本 ADR) |
| mof-version | v0.0.103 | v0.0.104 | +1 |

### D4: 验证结果 (3 测试用例)

| # | 测试 | 结果 |
|:-:|:-----|:-----|
| 1 | 2 文件 parse OK | ✅ |
| 2 | build_governance_surfaces_report re-export 等价 | ✅ same fn object (from omo.omo_governance_surfaces_report) |
| 3 | 6 surface lints 全过 | ✅ |

### D5: P110-B 累计量化 (omo_governance_surfaces)

| 阶段 | 行数 | 累计 |
|:-----|:----:|:----:|
| P104 末 | 1762L | — |
| P104-P108 累计 | 443L | -75% |
| **P110-B** | **276L** | **-84%** |
| 阈值 | <600L ideal ✓ | **首次达成** |

### D6: P110-A/B 累计 (2 阶段 跨生态)

| 阶段 | 文件 | 行数变化 | 跨模块 |
|:-----|:-----|:---------|:------:|
| P100-P108 | omo_lint | 1269→544L | omo |
| P104-P108 | omo_governance_surfaces | 1762→443→**276L** | omo |
| P110 (前) | omo_ingress_task_lifecycle | 1530→614L | omo |
| **P110-A** | **ecos domain_manager** | **1914→1406L** | **ecos (跨 submodule 首例)** |
| **P110-B** | **omo_governance_surfaces** | **443→276L** | **omo** |
| **P110 累计** | | | **2 阶段** |

### D7: 13 god-module 列表更新 (P110-B 后)

omo_governance_surfaces.py 443L → 276L, 已 **<300L ideal**, **退出 god-module warn list**。

剩余 11 god-modules:
- 10 TS (gbrain) - 等 P110-D ts-morph
- 1 Python (ecos domain_manager.py 1406L, 仍 >800L warn)

## Consequences

**正面**:
- **443→276L, -38%**: 8 子模块架构完成 (P104-P108 6 + P110-B 1 = 7 + P110-A 跨模块)
- **<300L ideal 首次达成**: omo_governance_surfaces.py 是第 1 个达成 ideal 的文件 (除 doc-lifecycle)
- **P107 cross-sibling import 范式复用**: 8 个 sibling 导入, 无 circular 风险
- **P105 inline _load_yaml 范式**: 4L 重复, 避免 circular
- **build_report 单职责**: 顶层 aggregator 独立, 易单测

**负面**:
- **0 新 god-module 清零** (P110-B 是 P104-P108 收尾, 不清新 god-module)
- **inline 4L 重复** (与 7 个 P104-P108 子模块相同)
- **8 个 sibling import**: 子模块 254L 中 ~50L 是 import block, 27% overhead

**关联**:
- ADR-0098-102: omo_governance_surfaces 8 子模块化 (P104-P108)
- ADR-0103: 治理赋能三件套 (验证模板)
- ADR-0108: P110-A ecos domain_manager 跨 submodule 首例
- **ADR-0109**: P110-B omo_governance_surfaces build_report 子模块化 (本 ADR)

## Validation

```bash
# P110-B 验证 1: parse 2 文件
python3 -c "import ast
for f in ['projects/omo/src/omo/omo_governance_surfaces.py',
         'projects/omo/src/omo/omo_governance_surfaces_report.py']:
    ast.parse(open(f).read())
    print(f'✅ {f}')"

# P110-B 验证 2: re-export 等价
PYTHONPATH=projects/omo/src python3 -c "
import inspect
from omo.omo_governance_surfaces import build_governance_surfaces_report
print(f'✅ from: {inspect.getmodule(build_governance_surfaces_report).__name__}')
"

# P110-B 验证 3: 6 surface lints
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src python3 -m omo.omo_lint $cmd 2>&1 | head -1
done

# P110-B 验证 4: 行数
wc -l projects/omo/src/omo/omo_governance_surfaces.py
# 期望: 276L (从 443L, -38%)
```

## References

- P85-P110A: 见 ADR-0093-108 References 列表
- ADR-0093: P99 omo_lint 兑现路径
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- ADR-0100: P106 omo_governance_surfaces 4 子模块化
- ADR-0101: P107 omo_governance_surfaces 6 子模块化 (<600L ideal 首次达成, cross-sibling import 范式)
- ADR-0102: P108 omo_governance_surfaces 8 子模块化 (黄金值 400-500L)
- ADR-0103: P109 治理赋能三件套
- ADR-0108: P110-A ecos domain_manager 2 子模块化 (跨 submodule 治理首例)
- **ADR-0109**: P110-B omo_governance_surfaces build_report 子模块化 (本 ADR, <300L ideal)

---

*最后更新: 2026-06-25 · P110-B omo_governance_surfaces build_report 子模块化收官 (443→276L, -38%, <300L ideal 首次达成, P107 cross-sibling import 范式复用)*
