---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0102: P108 omo_governance_surfaces 8 子模块化 (556→443L, 黄金值 400-500L 首次达成)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P108
- **Extends**: ADR-0101 (P107 <600L ideal 首次达成)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0101 P107 末 omo_governance_surfaces.py **556L** (<600L ideal 首次达成).
ADR-0101 D6 列出 P108 候选:
- `_check_internal_write_profile_registry` (65L) - 独立可拆
- `_check_c2g_omo_boundary` (50L) - 独立可拆
- 合计 153L → ~443L, **逼近黄金值 400-500L**

**P108 决策**: 拆 2 check function, 达成 omo_governance_surfaces.py 黄金值.

## Decision

### D1: 2 子模块创建 (P108 R3 实施)

**实际区段**:
- `_check_c2g_omo_boundary`: L104-154 (51L) → `omo_governance_surfaces_c2g_boundary.py` (91L)
- `_check_internal_write_profile_registry`: L222-325 (104L) → `omo_governance_surfaces_internal_write_profiles.py` (142L)
- 总新文件 233L

**omo_governance_surfaces.py 收口**: 556L → 443L (**-113L, -20%**)

### D2: P108 关键技术 (ast import + cross-sibling)

**关键技术 1**: `omo_governance_surfaces_c2g_boundary.py` 需要 `ast` import (P108 R3 首次暴露):
```python
import ast  # 用于 ast.parse + ast.walk 解析 c2g .py 文件检测散弹 import
```
原因: `_check_c2g_omo_boundary` 通过 AST 分析 c2g 项目内 .py 文件, 检查是否绕过 facade 直接 import omo.

**关键技术 2**: `omo_governance_surfaces_internal_write_profiles.py` 复用 P107 cross-sibling import 范式:
```python
from omo.omo_governance_surfaces_snapshots import (
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)
```

### D3: 收口统计

| 指标 | P107 末 | P108 末 | 变化 |
|------|---------|---------|------|
| `omo_governance_surfaces.py` | 556L | **443L** | **-113L (-20%)** |
| `omo_governance_surfaces_c2g_boundary.py` | (新) | 91L | +91L |
| `omo_governance_surfaces_internal_write_profiles.py` | (新) | 142L | +142L |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 0 | 0 | ✓ |
| god-module ideal (<600L) | 0 (556L) | 0 (443L) | ✓ (深化) |
| **黄金值 (400-500L)** | — | **0 (443L)** | **首次达成** |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 61 | **62** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D4: omo_governance_surfaces 子模块群最终结构 (P104-P108)

| 模块 | 起始阶段 | 行数 | 业务 |
|:----|:--------|:----:|:----|
| `omo_governance_surfaces.py` | (原) | **443L** | main + build_report + 5 has_*_gate + 6 helpers |
| `omo_governance_surfaces_snapshots.py` | P104 | 553L | 2 snapshot + 2 category_count helper |
| `omo_governance_surfaces_ingress.py` | P105 | 270L | _check_ingress_registry + _resolve_ingress_task_carrier |
| `omo_governance_surfaces_task_policy.py` | P106 | 132L | _check_task_policy_registry |
| `omo_governance_surfaces_ingress_artifacts.py` | P106 | 223L | _check_ingress_artifacts + INGRESS_ARTIFACT_RULES |
| `omo_governance_surfaces_state_plane.py` | P107 | 175L | _check_state_plane_asset_registry + 3 常量 |
| `omo_governance_surfaces_mutation_surface.py` | P107 | 154L | _check_mutation_surface_registry (cross-sibling) |
| `omo_governance_surfaces_c2g_boundary.py` | P108 | **91L** | _check_c2g_omo_boundary (ast 解析) |
| `omo_governance_surfaces_internal_write_profiles.py` | P108 | **142L** | _check_internal_write_profile_registry (cross-sibling) |
| (合计) | | **2183L** | (vs 原 1762L, +421L 拆分元数据) |

### D5: P104-P108 累计量化

| 阶段 | omo_governance_surfaces.py | 阈值 | 累计 |
|:----:|:--------------------------:|:----:|:----:|
| P103 末 | 1762L | 1 error | — |
| P104 | 1244L | 0 error 1 warn | -518L |
| P105 | 1022L | 0 error 1 warn | -740L |
| P106 | 763L | 0 warn | -999L |
| P107 | 556L | <600L ideal | -1206L |
| **P108** | **443L** | **黄金值 400-500L** | **-1319L (-75%)** |

### D6: omo_governance_surfaces.py 剩余业务 (P109+ 候选)

剩余函数:
- `build_governance_surfaces_report` (172L) - 顶层 report, 调用所有 check
- `resolve_governance_workspace_root` (24L) - 路径解析 helper
- main() + 5 has_*_gate helpers + 6 misc helpers
- 总 5 helpers + main ≈ 247L

**P109 候选**: 拆 `build_governance_surfaces_report` (172L) → ~271L, 接近 <300L
- 风险: build_report 跨多 check 调用, 拆完等于 thin wrapper (类似 P102)
- 收益: omo_governance_surfaces.py 进入 <300L 区间

### D7: 8 子模块架构成熟度

P104-P108 5 阶段 god-module 治理形成完整子模块架构:

| 维度 | 状态 |
|:-----|:-----|
| 错误阈值 (>1500L) | ✓ 清零 |
| 警告阈值 (>800L) | ✓ 清零 |
| 理想阈值 (<600L) | ✓ 清零 (556L) |
| **黄金值 (400-500L)** | **✓ 清零 (443L)** |
| 子模块数 | 8 (snapshots/ingress/task_policy/ingress_artifacts/state_plane/mutation_surface/c2g_boundary/internal_write_profiles) |
| 单一职责 | ✓ 每模块 1-2 函数 + 0-1 常量 |
| Cross-sibling import 范式 | ✓ 2 处应用 (mutation_surface + internal_write_profiles → snapshots) |
| Inline helper 范式 | ✓ 4 处应用 (ingress/task_policy/ingress_artifacts/state_plane → parent _load_yaml) |

## Consequences

**正面**:
- **黄金值 400-500L 首次达成**: omo_governance_surfaces.py 443L, 5 阶段 god-module 治理完整闭环
- **累计 -75% 行数**: 1762 → 443L, 超过 omo_lint 减幅 (-57%)
- **8 子模块架构完整**: 所有 _check_* 业务函数独立, omo_governance_surfaces.py 仅保留 main + report + helpers
- **3 个 cross-cutting import 范式确立**: P105 inline helper (parent) + P107 cross-sibling + P108 ast import
- **全套 6 lint 通过**: P106 新规范持续, P108 ast 解析边界 lint 也工作

**负面**:
- **inline `_load_yaml` 5 处重复**: P105+P106+P107+P108 共 5 处 (20L 重复)
- **拆分元数据 +421L overhead**: 9 文件 vs 原 1 文件, 物理拆分代价
- **omo submodule working tree 仍未 commit**: P88-P108 同模式, 13+ 个新文件待审批
- **`build_governance_surfaces_report` 172L 留 main**: 顶层 report 难拆, P109+ 候选

**关联**:
- ADR-0101 → ADR-0102: P107 <600L ideal → P108 黄金值 400-500L
- P104-P108: omo_governance_surfaces 5 阶段 god-module 治理完整闭环
- P108 创新: ast import (c2g 边界 AST 解析) + 复用 P107 cross-sibling (internal_write_profiles)

## Validation

```bash
# P108 R3 验证 1: 模块解析 (9 modules)
python3 -c "
import ast
import glob
for f in sorted(glob.glob('projects/omo/src/omo/omo_governance_surfaces*.py')):
    ast.parse(open(f).read())
    print(f'✅ {f}')
"

# P108 R3 验证 2: 全套 6 surfaces lints
for cmd in ingress-registry mutation-surfaces internal-write-profiles state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint $cmd 2>&1 | head -1
done
# 期望: 6 行 ✅

# P108 R3 验证 3: 8 re-exports 等价
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces import (
    _check_state_plane_asset_registry,
    _check_mutation_surface_registry,
    _check_ingress_registry,
    _check_ingress_artifacts,
    _check_task_policy_registry,
    _check_c2g_omo_boundary,
    _check_internal_write_profile_registry,
    _mutation_surface_registry_snapshot,
)
print('✅ all 8 re-exports OK')
"

# P108 R3 验证 4: 行数统计
wc -l projects/omo/src/omo/omo_governance_surfaces.py
# 期望: 443L, 较 P107 末 -113L

# P108 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P108 R6: mof-version
bin/mof-version record "P108: omo_governance_surfaces 8 子模块化 (556→443L, 黄金值 400-500L 首次达成)"
# 期望: v0.0.96 → v0.0.97
```

## References

- P85-P107: 见 ADR-0093-101 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- ADR-0100: P106 omo_governance_surfaces 4 子模块化 (warn 阈值清零, P104 re-export 修复)
- ADR-0101: P107 omo_governance_surfaces 6 子模块化 (<600L ideal 首次达成, cross-sibling import 范式)
- **ADR-0102: P108 omo_governance_surfaces 8 子模块化 (黄金值 400-500L 首次达成, 本 ADR)**

---

*最后更新: 2026-06-25 · P108 omo_governance_surfaces 8 子模块化收口 (黄金值 400-500L 首次达成, 累计 -75% 行数, 5 阶段 god-module 治理完整闭环)*
