---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0100: P106 omo_governance_surfaces 4 子模块化 (1022→763L, <800L warn 清零, P104 re-export 修复)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P106
- **Extends**: ADR-0099 (P105 ingress-check, 1244→1022L)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0099 P105 末 omo_governance_surfaces.py **1022L**, 仍 > 800L warn 阈值.

**P106 调研**: 剩余大函数 6 个, ADR-0099 D5 列出 2 个 P106 候选:
- `_check_ingress_artifacts` (L487-632, 145L) - 独立可拆
- `_check_task_policy_registry` (L308-399, 91L) - 独立可拆

**业务**: 2 个 check function 都校验 `.yaml` registry 文件结构, 但语义独立 (artifact vs task-policy).

**P106 决策**: 拆 2 个独立子模块 (236L) + 修 P104 漏掉的 re-export.

## Decision

### D1: 2 子模块创建 (P106 R3 实施)

**实际区段**:
- `_check_task_policy_registry`: L308-399 (92L) → `omo_governance_surfaces_task_policy.py` (132L)
- `_check_ingress_artifacts`: L487-632 (146L) → `omo_governance_surfaces_ingress_artifacts.py` (223L)
- **额外搬迁**: `INGRESS_ARTIFACT_RULES` 常量 (L60-100, 41L) 跟随 ingress-artifacts 拆 (否则 NameError)
- **INGRESS_ARTIFACT_RULES 搬运**: 从 omo_governance_surfaces.py:60 → ingress_artifacts.py module-level

**omo_governance_surfaces.py 收口**: 1022L → 763L (**-259L, -25%**)

### D2: P104 re-export 修复 (P106 R3 关键发现)

**问题**: P104 Python 脚本声称 "添加 re-export block (2 符号)", 但实际未生效。
omo_governance_surfaces_snapshots.py 创建后, P104 应该 re-export:
- `_mutation_surface_registry_snapshot`
- `_worker_internal_write_profiles_snapshot`
- 但**漏掉 2 个 helper**:
  - `_mutation_surface_category_counts`
  - `_worker_profile_subtype_counts`

**故障现象**:
- P104 末验证 `python3 -m omo.omo_lint mutation-surfaces` **未跑** (仅跑 `lint yaml-bypass` 等)
- P106 R3 验证时 `mutation-surfaces` 报 NameError: `_mutation_surface_category_counts` not defined
- P106 R3 同时跑全套 lint 才暴露

**修复** (P106 R3 内联):
```python
from .omo_governance_surfaces_snapshots import (  # noqa: E402, F401
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)
```

### D3: 收口统计

| 指标 | P105 末 | P106 末 | 变化 |
|------|---------|---------|------|
| `omo_governance_surfaces.py` | 1022L | **763L** | **-259L (-25%)** |
| `omo_governance_surfaces_task_policy.py` | (新) | 132L | +132L |
| `omo_governance_surfaces_ingress_artifacts.py` | (新) | 223L | +223L (含 INGRESS_ARTIFACT_RULES 41L) |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 1 (1022L) | **0 (763L)** | **warn 阈值清零** |
| **god-module ideal (<600L)** | — | — | 未达 (763L), 但接近 |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 59 | **60** | +1 (本 ADR, milestone 整数) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D4: omo_governance_surfaces 子模块群最终结构 (P104-P106)

| 模块 | 起始阶段 | 行数 | 业务 |
|:----|:--------|:----|:----|
| `omo_governance_surfaces.py` | (原) | **763L** | main 入口 + build_governance_surfaces_report + 5 has_*_gate helpers + 3 check 函数 |
| `omo_governance_surfaces_snapshots.py` | P104 | 553L | 2 snapshot + 2 category_count helper (纯数据) |
| `omo_governance_surfaces_ingress.py` | P105 | 270L | _check_ingress_registry + _resolve_ingress_task_carrier |
| `omo_governance_surfaces_task_policy.py` | P106 | 132L | _check_task_policy_registry |
| `omo_governance_surfaces_ingress_artifacts.py` | P106 | 223L | _check_ingress_artifacts + INGRESS_ARTIFACT_RULES |
| (合计) | | **1941L** | (vs 原 1762L, +179L 拆分元数据) |

### D5: P104-P106 累计量化

| 阶段 | 拆解 | omo_governance_surfaces.py | 累计减幅 |
|:----:|:----|:--------------------------:|:--------:|
| P103 末 | (P104 起点) | 1762L | — |
| P104 | snapshots (505L) | 1244L | -518L (-29%) |
| P105 | ingress-check (228L) | 1022L | -740L (-42%) |
| **P106** | **task-policy + ingress-artifacts (238L + 41L 常量)** | **763L** | **-999L (-57%)** |

**13 god-module list 更新**:
- `omo_governance_surfaces.py` 从 error list 移除 (P104) 后, 持续减重, 不再列入 error (>1500L)
- warn list 也清零 (P106)
- 当前 error list 仍 12 (10 TS + 2 Python: domain_manager + omo_ingress_task_lifecycle)

### D6: omo_governance_surfaces.py 剩余业务 (P107+ 候选)

剩余函数:
- `build_governance_surfaces_report` (172L) - 顶层 report, 依赖 4-5 个 check
- `_check_state_plane_asset_registry` (86L)
- `_check_mutation_surface_registry` (85L)
- `_check_internal_write_profile_registry` (65L)
- `_check_c2g_omo_boundary` (50L)
- `resolve_governance_workspace_root` (24L)
- main() + 5 has_*_gate helpers + 6 misc helpers

**P107+ 候选**: 拆 `_check_state_plane_asset_registry` (86L) + `_check_mutation_surface_registry` (85L) = 171L → ~592L <600L ideal

### D7: P104 re-export 修复的教训

**教训**: 
1. P104 验证**不充分** — 仅跑了 lint yaml-bypass, 未跑 mutation-surfaces (受影响函数)
2. Python 脚本 `re_export` 变量**未正确插入**到输出文件, 但 commit message 声称成功
3. **新规则**: 每个 P 阶段必须跑**全套 surfaces lints** (6 个) 验证, 不能只挑一两个

**已建立**: P106 R3 跑全套 6+lint 验证, 暴露 P104 漏的 re-export.

## Consequences

**正面**:
- **warn 阈值清零**: omo_governance_surfaces.py 763L < 800L, 13 god-module list 仍 12 但本文件不再 warn
- **累计 -57% 行数**: 1762 → 763L, 与 omo_lint 减幅 (-57%) 持平
- **4 子模块架构清晰**: snapshots/ingress/task-policy/ingress-artifacts 各司其职
- **P104 re-export 修复**: 4 个 snapshot helper 全部 re-export, 工具链稳定
- **ADR-0100 milestone**: 第 60 个 ADR, 100 阶段累计整数

**负面**:
- **P104 commit message 错误**: 声称"4 call sites 零变更"但实际 3 个 call site 失败 (NameError)
- **inline _load_yaml 重复**: P105+P106 共 3 处 inline (ingress + task_policy + ingress_artifacts), 共 12L 重复
- **omo submodule working tree 仍未 commit**: P88-P106 同模式, 9+ 个新文件待审批

**关联**:
- ADR-0099 → ADR-0100: P105 ingress-check → P106 2 子模块 + warn 阈值清零
- P104-P106: omo_governance_surfaces 持续 god-module 减重 3 阶段
- **教训**: P107+ 验证规范 = 跑全套 6+lint, 不能挑一两个

## Validation

```bash
# P106 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_governance_surfaces.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_task_policy.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_ingress_artifacts.py').read())"
# 期望: 静默 OK

# P106 R3 验证 2: 全套 6 surfaces lints (新增规范)
for cmd in ingress-registry mutation-surfaces internal-write-profiles state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint $cmd 2>&1 | head -1
done
# 期望: 6 行 ✅

# P106 R3 验证 3: re-exports 等价
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces_task_policy import _check_task_policy_registry
from omo.omo_governance_surfaces_ingress_artifacts import _check_ingress_artifacts
from omo.omo_governance_surfaces_snapshots import _mutation_surface_registry_snapshot
from omo.omo_governance_surfaces import _check_task_policy_registry as tp_orig, _check_ingress_artifacts as ia_orig, _mutation_surface_registry_snapshot as ss_orig
assert _check_task_policy_registry is tp_orig
assert _check_ingress_artifacts is ia_orig
assert _mutation_surface_registry_snapshot is ss_orig
print('✅ all re-exports OK')
"
# 期望: ✅ all re-exports OK

# P106 R3 验证 4: 行数统计
wc -l projects/omo/src/omo/omo_governance_surfaces.py
# 期望: 763L, 较 P105 末 -259L

# P106 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P106 R6: mof-version
bin/mof-version record "P106: omo_governance_surfaces 4 子模块化 (1022→763L, <800L warn 清零, P104 re-export 修复)"
# 期望: v0.0.94 → v0.0.95
```

## References

- P85-P105: 见 ADR-0093-99 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分 (13→12 god-module)
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- **ADR-0100: P106 omo_governance_surfaces 4 子模块化 (warn 阈值清零, P104 re-export 修复, 本 ADR, 第 60 ADR)**

---

*最后更新: 2026-06-25 · P106 omo_governance_surfaces 4 子模块化收口 (warn 阈值清零, P104 re-export 修复, 累计 -57% 行数)*
