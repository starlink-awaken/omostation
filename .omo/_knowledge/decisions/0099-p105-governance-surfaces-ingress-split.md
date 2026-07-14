---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (1244→1022L)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P105
- **Extends**: ADR-0098 (P104 snapshots 子模块拆分, 13→12 god-module)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0098 P104 末 omo_governance_surfaces.py **1244L** (1762→1244, -518L). 仍 > 800L warn 阈值, 接近但未触发 god-module error (>1500L).

**P105 调研**: god-module 列表中 Python 剩 2 个:
- omo_ingress_task_lifecycle.py (1530L, 730L excess) — 15 函数, 内部工具高度耦合, 拆风险大
- ecos/.../domain_manager.py (1914L, 1114L excess) — ecos submodule, 跨 submodule 治理节奏

**P105 决策**: 不拆 omo_ingress_task_lifecycle.py 和 domain_manager.py (高风险), 继续 omo_governance_surfaces.py 内部 god-module 减重。

**P105 候选**: `_check_ingress_registry` (L809-1013, 204L, 最大单函数) + 内部依赖 `_resolve_ingress_task_carrier` (L785-808, 23L) = 228L.

**业务**: ingress registry.yaml 校验 (4 类: goal/task/debt/capability), 内部 task_carrier 路径回落。

## Decision

### D1: omo_governance_surfaces_ingress.py 子模块创建 (P105 R3 实施)

**实际区段**: line 785-1013 (229L 含空白)

**拆出内容** (2 个函数):
- **`_resolve_ingress_task_carrier`** (L785-808, 23L): 解析 task carrier yaml 路径 (7 candidates)
- **`_check_ingress_registry`** (L809-1013, 204L): 校验 ingress registry.yaml
  - registry 结构 (goal/task/debt/capability ids)
  - 反向映射 (artifact_ref ↔ registry entry)
  - 落盘一致性 (registry → 真实 artifact 文件)
  - task_carrier 路径回落

**模块依赖**: `Path` (stdlib) + `yaml` (via inline `_load_yaml` helper, 见 D2)

### D2: Circular Import 修复 (P105 关键技术决策)

**问题**: `_check_ingress_registry` 内部使用 `_load_yaml` (3L helper in omo_governance_surfaces.py:103-106).
直接 `from .omo_governance_surfaces import _load_yaml` 会触发循环:
- `omo_governance_surfaces_ingress` 导入 `_load_yaml` →
- `omo_governance_surfaces` 导入 `_check_ingress_registry` (P105 re-export) →
- `omo_governance_surfaces_ingress` 正在初始化中 → **ImportError**

**修复方案**: 在 ingress 子模块 inline `_load_yaml` 4-line helper:
```python
from omo.omo_shared import load_yaml_required

def _load_yaml(path):
    """Inline helper (P105): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)
```

**权衡**: 重复 4L helper, 但消除循环依赖。vs. P88-P104 模式 re-export import 不同（这次是 child → parent 内部 helper）。

**替代方案评估**:
- 方案 A (采用): inline 4L helper, 0 风险, 0 调用方变更
- 方案 B: 把 `_load_yaml` 移到 `omo_shared.py` (更高层 SSOT), 需改动 omo_governance_surfaces.py
- 方案 C: 用 `import yaml` 直接读 + `try/except`, 需更复杂 fallback

**决策**: 方案 A, 最小变更。

### D3: 收口统计

| 指标 | P104 末 | P105 末 | 变化 |
|------|---------|---------|------|
| `omo_governance_surfaces.py` | 1244L | **1022L** | **-222L (-18%)** |
| `omo_governance_surfaces_ingress.py` | (新) | 265L | +265L |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 1 (1244L) | **1 (1022L)** | 仍 warn, 但接近 ideal |
| **理想值 (<1000L)** | — | **未达成 (1022L)** | -222L 减幅大但未触线 |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 58 | **59** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D4: 13 god-module 列表 (P105 后)

| # | 文件 | 类型 | 行数 | excess | 状态 |
|:-:|:-----|:----:|:----:|:------:|:----:|
| 1 | gbrain/src/commands/doctor.ts | TS | 4825L | 4025L | 待 P107+ |
| 2 | gbrain/src/core/postgres-engine.ts | TS | 4514L | 3714L | 待 P107+ |
| 3 | gbrain/src/core/pglite-engine.ts | TS | 4509L | 3709L | 待 P107+ |
| 4 | gbrain/src/core/migrate.ts | TS | 4333L | 3533L | 待 P107+ |
| 5 | gbrain/src/core/ai/gateway.ts | TS | 2895L | 2095L | 待 P107+ |
| 6 | ecos/.../domain_manager.py | Python | 1914L | 1114L | 待 P106+ (ecos 治理) |
| ~~7~~ | ~~omo_governance_surfaces.py~~ | ~~Python~~ | ~~1762L~~ | ~~P104 ✓ 清零~~ | **1022L (持续减重)** |
| 8 | gbrain/src/commands/serve-http.ts | TS | 1756L | 956L | 待 P107+ |
| 9 | gbrain/src/cli.ts | TS | 1735L | 935L | 待 P107+ |
| 10 | gbrain/src/core/cycle.ts | TS | 1707L | 907L | 待 P107+ |
| 11 | gbrain/src/commands/sync.ts | TS | 1609L | 809L | 待 P107+ |
| 12 | gbrain/src/core/engine.ts | TS | 1563L | 763L | 待 P107+ |
| 13 | omo_ingress_task_lifecycle.py | Python | 1530L | 730L | 待 P106+ (omo 内部治理, 高风险) |

### D5: P106+ 推进路径

**omo_governance_surfaces.py 剩余大函数**:
- `build_governance_surfaces_report` (172L) - 顶层 report, 依赖其他 check, 难拆
- `_check_ingress_artifacts` (145L) - 独立可拆
- `_check_task_policy_registry` (91L) - 独立可拆
- `_check_state_plane_asset_registry` (86L) - 独立可拆
- `_check_mutation_surface_registry` (85L) - 独立可拆
- `_check_internal_write_profile_registry` (65L) - 独立可拆

**P106 候选**: 拆 `_check_ingress_artifacts` (145L) + `_check_task_policy_registry` (91L) = 236L → 786L <800L warn 阈值清零

**omo_ingress_task_lifecycle.py (1530L) 拆解评估**:
- 15 函数, 7+ 内部工具 import (omo_audit / omo_io / omo_promotion_request / omo_task_schema / omo_ingress_paths / omo_ingress_registry / omo_ingress_trail)
- **风险评估**: 高 — task lifecycle 是 omostation 核心业务, 拆分需深入理解 cross-function call graph
- **建议**: P106+ 推迟, 优先 omo_governance_surfaces.py 收尾 (P106 完成即可降级 13 list 第 7 位)

### D6: submodule commit 模式 (P88/P100-P104 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_governance_surfaces_ingress.py + 修改 omo_governance_surfaces.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

## Consequences

**正面**:
- **omo_governance_surfaces.py 持续减重**: 1762 → 1244 → 1022L, -740L 累计
- **circular import 修复范式**: P105 确立 inline helper 模式, 后续 child→parent 内部 helper 拆分可参考
- **P104-P105 模式持续**: re-export (除 _load_yaml 例外) + 头注释, 工具链稳定
- **P102 surfaces 子模块的 SSOT 进一步解耦**: ingress check 独立, 未来单测可独立 mock

**负面**:
- **inline helper 4L 重复**: `_load_yaml` 在 2 处存在, 短期可接受, 长期应重构
- **warn 阈值仍 1022L > 800L**: P105 未达 ideal <1000L, P106 需继续
- **omo submodule working tree 仍未 commit** (P88-P105 同模式), 7+ 个新文件待审批

**关联**:
- ADR-0098 → ADR-0099: P104 snapshots → P105 ingress-check, omo_governance_surfaces 持续 god-module 减重
- P102 → P104 → P105: 拆 thin wrapper (P102) → 拆 SSOT snapshot 数据 (P104) → 拆 SSOT ingress check 业务 (P105)
- P105 决策推迟 omo_ingress_task_lifecycle / domain_manager 拆解, 因风险/跨 submodule 限制

## Validation

```bash
# P105 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_governance_surfaces.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_ingress.py').read())"
# 期望: 静默 OK

# P105 R3 验证 2: re-export 等价
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces_ingress import _check_ingress_registry
from omo.omo_governance_surfaces import _check_ingress_registry as orig
assert _check_ingress_registry is orig
print('✅ re-export OK')
"
# 期望: ✅ re-export OK

# P105 R3 验证 3: ingress-registry lint 功能不变
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint ingress-registry
# 期望: ✅ omo lint ingress-registry pass

# P105 R3 验证 4: 行数统计
wc -l projects/omo/src/omo/omo_governance_surfaces.py projects/omo/src/omo/omo_governance_surfaces_ingress.py
# 期望: 1022L + 265L, omo_governance_surfaces.py 较 P104 末 -222L

# P105 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P105 R6: mof-version
bin/mof-version record "P105: omo_governance_surfaces ingress-check 子模块拆分 (1244→1022L, circular import 修复)"
# 期望: v0.0.93 → v0.0.94
```

## References

- P85-P104: 见 ADR-0093-98 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分 (4 步完整兑现)
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分 (13→12 god-module)
- **ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复, 本 ADR)**

---

*最后更新: 2026-06-25 · P105 omo_governance_surfaces ingress-check 子模块拆分收口 (1244→1022L, circular import 修复范式)*
