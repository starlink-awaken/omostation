---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0101: P107 omo_governance_surfaces 6 子模块化 (763→556L, <600L ideal 首次达成)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P107
- **Extends**: ADR-0100 (P106 warn 阈值清零)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0100 P106 末 omo_governance_surfaces.py **763L** (warn 阈值 800L 已清零).
ADR-0100 D6 列出 P107+ 候选:
- `_check_state_plane_asset_registry` (86L) + `_check_mutation_surface_registry` (85L) = 171L → ~592L

**P107 决策**: 拆 2 check function + 搬迁 3 个 module-level constants (45L).

## Decision

### D1: 2 子模块创建 (P107 R3 实施)

**实际区段**:
- `_check_state_plane_asset_registry`: L267-353 (87L) → `omo_governance_surfaces_state_plane.py` (175L 含 3 常量)
- `_check_mutation_surface_registry`: L420-532 (113L) → `omo_governance_surfaces_mutation_surface.py` (154L)
- **额外搬迁**: 3 个 module-level constants (ALLOWED_PERSISTENCE_MODES + ALLOWED_RETENTION_MODES + EXPECTED_ASSET_LIFECYCLE_BY_TYPE, 45L) 跟随 state-plane 拆

**omo_governance_surfaces.py 收口**: 763L → 556L (**-207L, -27%**)

### D2: Cross-Sibling Import 模式 (P107 关键技术决策)

**新模式**: `omo_governance_surfaces_mutation_surface.py` 直接 import 同级 sibling `omo_governance_surfaces_snapshots.py`:
```python
from omo.omo_governance_surfaces_snapshots import (
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
)
```

**理由**: `_check_mutation_surface_registry` 内部直接调用 2 个 snapshot helper (不是通过 re-export)

**与 P105 circular import 修复对比**:
- P105: child → parent internal helper 用 inline `_load_yaml` (避免 circular)
- P107: child → sibling (同 parent) 直接 import (无 circular 风险, snapshots 是 pure data leaf)

### D3: 收口统计

| 指标 | P106 末 | P107 末 | 变化 |
|------|---------|---------|------|
| `omo_governance_surfaces.py` | 763L | **556L** | **-207L (-27%)** |
| `omo_governance_surfaces_state_plane.py` | (新) | 175L | +175L (含 3 常量 45L) |
| `omo_governance_surfaces_mutation_surface.py` | (新) | 154L | +154L |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 0 | 0 | ✓ |
| **god-module ideal (<600L)** | — | **0 (556L)** | **<600L ideal 首次达成** |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 60 | **61** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D4: omo_governance_surfaces 子模块群最终结构 (P104-P107)

| 模块 | 起始阶段 | 行数 | 业务 |
|:----|:--------|:----|:----|
| `omo_governance_surfaces.py` | (原) | **556L** | main + build_report + 5 has_*_gate + c2g check + 6 misc helpers |
| `omo_governance_surfaces_snapshots.py` | P104 | 553L | 2 snapshot + 2 category_count helper |
| `omo_governance_surfaces_ingress.py` | P105 | 270L | _check_ingress_registry + _resolve_ingress_task_carrier |
| `omo_governance_surfaces_task_policy.py` | P106 | 132L | _check_task_policy_registry |
| `omo_governance_surfaces_ingress_artifacts.py` | P106 | 223L | _check_ingress_artifacts + INGRESS_ARTIFACT_RULES |
| `omo_governance_surfaces_state_plane.py` | P107 | **175L** | _check_state_plane_asset_registry + 3 常量 |
| `omo_governance_surfaces_mutation_surface.py` | P107 | **154L** | _check_mutation_surface_registry (cross-sibling import) |
| (合计) | | **2063L** | (vs 原 1762L, +301L 拆分元数据) |

### D5: P104-P107 累计量化

| 阶段 | 拆解 | omo_governance_surfaces.py | 阈值 | 累计 |
|:----:|:----|:--------------------------:|:----:|:----:|
| P103 末 | (起点) | 1762L | 1 error | — |
| P104 | snapshots (505L) | 1244L | 0 error 1 warn | -518L |
| P105 | ingress-check (228L) | 1022L | 0 error 1 warn | -740L |
| P106 | task-policy + ingress-artifacts (279L) | 763L | **0 warn** | -999L |
| **P107** | **state-plane + mutation-surface (200L + 45L)** | **556L** | **<600L ideal** | **-1206L (-68%)** |

### D6: omo_governance_surfaces.py 剩余业务 (P108+ 候选)

剩余函数:
- `build_governance_surfaces_report` (172L) - 顶层 report, 跨多 check
- `_check_internal_write_profile_registry` (65L) - 独立可拆
- `_check_c2g_omo_boundary` (50L) - 独立可拆 (但 P102 cmd wrapper 已存在)
- `resolve_governance_workspace_root` (24L) - 路径解析 helper
- main() + 5 has_*_gate helpers + 6 misc helpers

**P108 候选**: 拆 `_check_internal_write_profile_registry` (65L) + `_check_c2g_omo_boundary` (50L) = 115L → ~441L (逼近黄金值 400-500L)

### D7: Cross-Sibling Import 范式 (P107 创新)

**新发现**: child → sibling 同 parent 模块 import 是安全的 (无 circular 风险), 因为:
- parent (omo_governance_surfaces) 不依赖 child 的实现细节
- sibling 是 leaf (pure data, no further dependencies)
- 与 P105 child → parent 修复范式 (inline helper) 形成对照

**vs P105 inline helper 范式**:
| 维度 | P105 inline | P107 sibling import |
|:-----|:------------|:---------------------|
| 适用 | child → parent | child → sibling |
| 风险 | circular | 极低 (sibling 是 leaf) |
| 代码重复 | 4L helper × N 处 | 0 |
| 维护性 | 差 | 好 |

**P107 决策**: state_plane 用 inline (因为只 1 函数需要 `_load_yaml`, 重复 4L 可接受);
mutation_surface 用 sibling import (依赖 2 个 snapshot helper, 适合 cross-sibling).

## Consequences

**正面**:
- **<600L ideal 首次达成**: omo_governance_surfaces.py 556L, 4 阶段 god-module 治理完整闭环
- **累计 -68% 行数**: 1762 → 556L, 接近 omo_lint 减幅 (-57%) + P107 (-57% 累计)
- **6 子模块架构完整**: snapshots/ingress/task_policy/ingress_artifacts/state_plane/mutation_surface 各司其职
- **Cross-sibling import 范式确立**: P107 创新, 未来 child → sibling 拆分可参考
- **全套 6 lint 通过**: P106 新规范有效, P107 严格验证

**负面**:
- **inline `_load_yaml` 4L 重复**: P105+P106+P107 共 4 处 inline (ingress + task_policy + ingress_artifacts + state_plane), 共 16L 重复
- **3 module-level constants 跟随搬迁**: ALLOWED_* / EXPECTED_* 等 45L 业务常量在 state_plane module 而非 main, 命名一致性需维护
- **omo submodule working tree 仍未 commit**: P88-P107 同模式, 11+ 个新文件待审批

**关联**:
- ADR-0100 → ADR-0101: P106 warn 阈值清零 → P107 <600L ideal 首次达成
- P104-P107: omo_governance_surfaces 持续 4 阶段 god-module 减重
- P107 创新: cross-sibling import 范式, 与 P105 inline 范式形成完整 child → parent/sibling 决策树

## Validation

```bash
# P107 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_governance_surfaces.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_state_plane.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_mutation_surface.py').read())"
# 期望: 静默 OK

# P107 R3 验证 2: 全套 6 surfaces lints (P106 新规范)
for cmd in ingress-registry mutation-surfaces internal-write-profiles state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint $cmd 2>&1 | head -1
done
# 期望: 6 行 ✅

# P107 R3 验证 3: re-exports 等价 (7 symbols)
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces import (
    _check_state_plane_asset_registry as sp_orig,
    _check_mutation_surface_registry as ms_orig,
    _check_ingress_registry as ir_orig,
    _check_ingress_artifacts as ia_orig,
    _check_task_policy_registry as tp_orig,
    _mutation_surface_registry_snapshot as ss_orig,
    _mutation_surface_category_counts as cc_orig,
)
print('✅ all 7 re-exports OK')
"
# 期望: ✅ all 7 re-exports OK

# P107 R3 验证 4: 行数统计
wc -l projects/omo/src/omo/omo_governance_surfaces.py
# 期望: 556L, 较 P106 末 -207L

# P107 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P107 R6: mof-version
bin/mof-version record "P107: omo_governance_surfaces 6 子模块化 (763→556L, <600L ideal 首次达成)"
# 期望: v0.0.95 → v0.0.96
```

## References

- P85-P106: 见 ADR-0093-100 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- ADR-0100: P106 omo_governance_surfaces 4 子模块化 (warn 阈值清零, P104 re-export 修复)
- **ADR-0101: P107 omo_governance_surfaces 6 子模块化 (<600L ideal 首次达成, 本 ADR)**

---

*最后更新: 2026-06-25 · P107 omo_governance_surfaces 6 子模块化收口 (<600L ideal 首次达成, 累计 -68% 行数, cross-sibling import 范式)*
