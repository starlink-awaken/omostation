---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分 (1762→1244L, 13→12 god-module)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P104
- **Extends**: ADR-0093 + ADR-0094-97 (omo_lint 4 步路径完整兑现) + ADR-0097 负面登记的 13 god-module
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0093 P100-P103 4 步路径完整闭环 (omo_lint.py 1269→544L, -57%)。**ADR-0097 负面登记明确 P104+ 候选**: 13 god-module 待拆 (10 TS + 3 Python)。

**P104 调研**: 13 god-module 列表中 **Python 文件 3 个**:
1. **omo_governance_surfaces.py** (1762L, 962L excess) — P102 surfaces 子模块的 SSOT, 8 巨型函数
2. omo_ingress_task_lifecycle.py (1530L, 730L excess) — task lifecycle 核心
3. ecos/.../domain_manager.py (1914L, 1114L excess) — ecos governance domain

**P104 决策**: 拆 **omo_governance_surfaces.py** 的 2 个 **纯数据 snapshot 函数** (505L):
- `_mutation_surface_registry_snapshot` (L626-910, 284L): 28 governance mutation surface
- `_worker_internal_write_profiles_snapshot` (L919-1140, 221L): 14 worker internal write profile

**特性**: 2 函数都是 `return [{...}, {...}, ...]` literal dict lists, **零外部依赖**, 4 个内部 call site 都 `snapshot()` 无参调用。

## Decision

### D1: omo_governance_surfaces_snapshots.py 子模块创建 (P104 R3 实施)

**实际区段**: line 626-1150 (525L 含空白)

**拆出内容** (2 个纯数据 snapshot):
- **`_mutation_surface_registry_snapshot()`** (L626-910, 284L): 28 surface registry dict
- **`_worker_internal_write_profiles_snapshot()`** (L919-1140, 221L): 14 worker profile dict

**模块依赖**: 零 (纯 stdlib types hint)

**拆分策略** (P88/P100/P101/P102/P103 模式复用):
1. 创建 `omo_governance_surfaces_snapshots.py` (553L 头部 + 函数体)
2. omo_governance_surfaces.py 删除 line 626-1150 (525L)
3. 在 omo_governance_surfaces.py 添加 re-export:
   ```python
   from .omo_governance_surfaces_snapshots import (  # noqa: E402, F401
       _mutation_surface_registry_snapshot,
       _worker_internal_write_profiles_snapshot,
   )
   ```

### D2: 收口统计

| 指标 | P103 末 | P104 末 | 变化 |
|------|---------|---------|------|
| `omo_governance_surfaces.py` | 1762L | **1244L** | **-518L (-29%)** |
| `omo_governance_surfaces_snapshots.py` | (新) | 553L | +553L |
| **god-module errors (>1500L)** | **13** | **12** | **-1 (Python 3→2)** |
| Total excess | 24252L | **23290L** | **-962L** |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 57 | **58** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D3: 13 god-module 列表更新 (P104 后)

| # | 文件 | 类型 | 行数 | excess |
|:-:|:-----|:----:|:----:|:------:|
| 1 | gbrain/src/commands/doctor.ts | TS | 4825L | 4025L |
| 2 | gbrain/src/core/postgres-engine.ts | TS | 4514L | 3714L |
| 3 | gbrain/src/core/pglite-engine.ts | TS | 4509L | 3709L |
| 4 | gbrain/src/core/migrate.ts | TS | 4333L | 3533L |
| 5 | gbrain/src/core/ai/gateway.ts | TS | 2895L | 2095L |
| 6 | ecos/.../domain_manager.py | Python | 1914L | 1114L |
| ~~7~~ | ~~omo_governance_surfaces.py~~ | ~~Python~~ | ~~1762L~~ | ~~P104 ✓ 清零~~ |
| 8 | gbrain/src/commands/serve-http.ts | TS | 1756L | 956L |
| 9 | gbrain/src/cli.ts | TS | 1735L | 935L |
| 10 | gbrain/src/core/cycle.ts | TS | 1707L | 907L |
| 11 | gbrain/src/commands/sync.ts | TS | 1609L | 809L |
| 12 | gbrain/src/core/engine.ts | TS | 1563L | 763L |
| 13 | omo_ingress_task_lifecycle.py | Python | 1530L | 730L |

**P105+ 候选**:
- **P105-A**: omo_ingress_task_lifecycle.py 拆解 (1530L)
- **P105-B**: ecos domain_manager.py 拆解 (1914L)
- **P105-C**: TS AST 工具 (ts-morph) 搭建, 启动 10 个 TS god-module 拆解

### D4: submodule commit 模式 (P88/P100-P103 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_governance_surfaces_snapshots.py + 修改 omo_governance_surfaces.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

**omo_governance_surfaces.py 当前 working tree**: **1244L** ✅ (<1500L god-module 阈值清零)
**omo_governance_surfaces_snapshots.py 当前 working tree**: 553L ✅

## Consequences

**正面**:
- **ADR-0097 负面登记首项闭环**: 13 → 12 god-module, Python 3 → 2
- **omo_governance_surfaces.py 不再 god-module**: 1244L < 1500L, P102 surfaces 子模块的 SSOT 解除风险
- **P100-P104 模式持续复用**: re-export + 头注释, 工具链稳定
- **数据函数识别范式**: 2 个 505L pure-data snapshot 函数暴露"代码即数据"反模式, 未来 P105+ 看到类似结构可识别
- **snapshot 调用零变更**: 4 个 call sites 无需改 (L1157 / L1223 / L1636)

**负面**:
- omo submodule working tree 仍未 commit (P88-P104 同模式), 6+ 个新文件待审批
- 553L 拆分元数据 vs 525L 原函数 = +28L (5% overhead), header + re-export
- 12 god-module 仍有 10 个 TS (待 ts-morph 工具搭建)

**关联**:
- ADR-0097 → ADR-0098: P103 收口 + P104 推进 13 god-module 列表首项
- P102 → P104: 拆 thin wrapper (P102) → 拆 SSOT 核心 (P104) 的逆向深化路径
- P100-P104 累计: 5 阶段 god-module 治理, 13 → 12 god-module errors, -962L excess

## Validation

```bash
# P104 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_governance_surfaces.py').read()); ast.parse(open('projects/omo/src/omo/omo_governance_surfaces_snapshots.py').read())"
# 期望: 静默 OK

# P104 R3 验证 2: snapshot 数据完整
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces_snapshots import _mutation_surface_registry_snapshot, _worker_internal_write_profiles_snapshot
m = _mutation_surface_registry_snapshot()
w = _worker_internal_write_profiles_snapshot()
print(f'mutation_surfaces={len(m)}, worker_profiles={len(w)}')
"
# 期望: mutation_surfaces=28, worker_profiles=14

# P104 R3 验证 3: 行数统计
wc -l projects/omo/src/omo/omo_governance_surfaces.py projects/omo/src/omo/omo_governance_surfaces_snapshots.py
# 期望: 1244L + 553L, omo_governance_surfaces.py 较 P103 末 -518L

# P104 R3 验证 4: re-export 向后兼容
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_governance_surfaces import _mutation_surface_registry_snapshot, _worker_internal_write_profiles_snapshot, build_governance_surfaces_report
print('✅ re-export OK')
"
# 期望: ✅ re-export OK

# P104 R5: god-module list 减少
PYTHONPATH=projects/omo/src python3 bin/ssot/god-module-13-error-list.py 2>&1 | grep -E "Error|excess"
# 期望: Error: 12, Total excess: 23290L

# P104 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P104 R6: mof-version
bin/mof-version record "P104: omo_governance_surfaces snapshots 子模块拆分 (1762→1244L, 13→12 god-module)"
# 期望: v0.0.92 → v0.0.93
```

## References

- P85-P103: 见 ADR-0093-97 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094: P100 omo_lint schemas 子模块拆分
- ADR-0095: P101 omo_lint yaml-bypass 子模块拆分 (顺序校正)
- ADR-0096: P102 omo_lint surfaces 子模块拆分 (<600L ideal)
- ADR-0097: P103 omo_lint mutation-ledger 子模块拆分 (4 步完整兑现)
- **ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分 (13→12 god-module, 本 ADR)**

---

*最后更新: 2026-06-25 · P104 omo_governance_surfaces snapshots 子模块拆分收口 (13→12 god-module, -962L excess, P105 推进 omo_ingress_task_lifecycle)*
