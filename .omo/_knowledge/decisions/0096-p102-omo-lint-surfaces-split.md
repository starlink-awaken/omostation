---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0096: P102 omo_lint surfaces 子模块拆分 (731→594L, <600L ideal 达成)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P102
- **Extends**: ADR-0093 (P99 兑现路径) + ADR-0094 (P100) + ADR-0095 (P101 yaml-bypass)
- **Superseded by**: (无)

## Context and Problem Statement

P101 末 omo submodule working tree 状态:
- `src/omo/omo_lint.py`: **731L** (P100: 800L → P101: 731L, -69L)
- `projects/omo/src/omo/omo_lint_schemas.py`: 519L (P100 创建)
- `projects/omo/src/omo/omo_lint_yaml_bypass.py`: 102L (P101 创建)
- `projects/omo/src/omo/omo_lint_doc.py`: 304L (P88 创建, 未 commit)
- **god-module error (>1500L)**: 0 ✓
- **god-module warn (>800L)**: 0 ✓

P102 调研 1 个候选区段:
- **surfaces 区段** (L366-L513, 148L): 6 个 governance-surface thin wrapper
  - 所有 6 个 cmd 都从 `omo.omo_governance_surfaces` 导入核心 check 函数
  - 业务: ingress registry / mutation surfaces / internal write profiles / state plane assets / c2g-omo boundary / ingress artifacts
  - 拆解性质: thin wrapper 移位, 收益次于 yaml-bypass (P101 已校正顺序)

**P102 决策**: 拆 **surfaces (148L)**, 兑现 ADR-0095 校正后路径的第 3 步。

## Decision

### D1: omo_lint_surfaces.py 子模块创建 (P102 R3 实施)

**实际区段**: line 366-513 (148L 含空白行)

**拆出内容** (6 个 governance-surface cmd thin wrapper):
- **`cmd_lint_ingress_registry`** (L366-391, 26L): ingress registry 结构 + 反向映射 + 落盘一致性
- **`cmd_lint_mutation_surfaces`** (L393-415, 23L): mutation surface truth registry vs broker
- **`cmd_lint_internal_write_profiles`** (L417-439, 23L): worker internal write profile registry
- **`cmd_lint_state_plane_assets`** (L441-464, 24L): .omo 顶层资产持久化与保留语义
- **`cmd_lint_c2g_omo_boundary`** (L466-485, 20L): c2g 接入 omo 边界 (facade-only)
- **`cmd_lint_ingress_artifacts`** (L487-512, 26L): ingress registry 指向 artifact 文件存在

**模块依赖**: `Path` (stdlib) + `omo.omo_governance_surfaces` (内部 SSOT, 已是 P88-89 沉淀的核心 check 函数集中地)

**拆分策略** (P100/P101 模式复用):
1. 创建 `omo_lint_surfaces.py` (179L 头部 + 函数体)
2. omo_lint.py 删除 line 366-513 (148L)
3. 在 omo_lint.py yaml-bypass re-export 后添加:
   ```python
   from .omo_lint_surfaces import (  # noqa: E402, F401
       cmd_lint_c2g_omo_boundary,
       cmd_lint_ingress_artifacts,
       cmd_lint_ingress_registry,
       cmd_lint_internal_write_profiles,
       cmd_lint_mutation_surfaces,
       cmd_lint_state_plane_assets,
   )
   ```

### D2: 收口统计

| 指标 | P101 末 | P102 末 | 变化 |
|------|---------|---------|------|
| `omo_lint.py` | 731L | **594L** | **-137L (-19%)** |
| `omo_lint_surfaces.py` | (新) | 179L | +179L |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 0 | 0 | ✓ |
| **god-module ideal (<600L)** | — | **0 (594L < 600L)** | **ideal 阈值首次达成** |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 55 | **56** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

**god-module 兑现进度 (ADR-0093 P100-P103 4 步, P101 校正顺序后)**:
- ✅ P100: schemas 拆 (-469L), 0 error 达成
- ✅ P101: yaml-bypass 拆 (-69L), 0 warn 达成
- ✅ **P102: surfaces 拆 (-137L), <600L ideal 首次达成** ← 净 594L
- 🔲 P103: mutation-ledger 拆 (57L) → 537L, <600L ideal 进一步巩固

**omo_lint 子模块群当前结构 (P88/P100/P101/P102)**:
| 模块 | 起始阶段 | 行数 | 业务 |
|:----|:--------|:----|:----|
| `omo_lint.py` | (原) | 594L | main() 入口 + 3 task-policy + sensitive/direct helpers |
| `omo_lint_doc.py` | P88 | 304L | doc-lifecycle (4 类 + 死链 + frontmatter) |
| `omo_lint_schemas.py` | P100 | 519L | 7 schema check + cmd_lint_schemas |
| `omo_lint_yaml_bypass.py` | P101 | 102L | yaml-bypass 越权检测 |
| `omo_lint_surfaces.py` | P102 | 179L | 6 governance-surface cmd |
| (合计) | | **1698L** | (vs 原 1269L, +429L 拆分元数据) |

### D3: P100-P102 累计量化

**累计 god-module 闭环**:
- P99 末: 1269L, 1 error
- P102 末: 594L, 0 error, 0 warn, **<600L ideal**
- **累计 -675L (-53%)**

**累计子模块数**: 0 → 4 (doc/schemas/yaml-bypass/surfaces), 平均 425L/模块

**累计 ADR 数**: 53 → **56** (+3)

### D4: submodule commit 模式 (P88/P100/P101 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_lint_surfaces.py + 修改 omo_lint.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

**omo_lint.py 当前 working tree**: **594L** ✅ (<600L ideal)
**omo_lint_surfaces.py 当前 working tree**: 179L ✅

## Consequences

**正面**:
- **3 阶段连续闭环**: P100 error 0 → P101 warn 0 → P102 ideal 0
- **累计 -53% 行数**: omo_lint.py 从 1269L 缩到 594L, 减半以上
- **4 子模块架构清晰**: doc/schemas/yaml-bypass/surfaces 各司其职
- **业务边界清楚**: 6 个 governance-surface cmd 集中到 omo_lint_surfaces.py, 未来 P103+ 拆分互不干扰
- **P100/P101 模式复用**: re-export + 头注释, 工具链稳定

**负面**:
- omo submodule working tree 仍未 commit (P88/P100/P101 同模式), 4 个新文件 + 1 修改文件待审批
- 1698L 合计 vs 1269L 原 = +429L 拆分元数据 (29% overhead), 子模块 header + re-export 累加
- P103 mutation-ledger 仍是剩余 1 步

**关联**:
- ADR-0093 → ADR-0094 → ADR-0095 → ADR-0096: 4 步连续兑现路径
- P88 → P100 → P101 → P102: 子模块拆分模式 4 阶段复用
- P102 是 4 步路径中的第 3 步, 第 4 步 P103 mutation-ledger 即将闭环

## Validation

```bash
# P102 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_lint.py').read()); ast.parse(open('projects/omo/src/omo/omo_lint_surfaces.py').read())"
# 期望: 静默 OK

# P102 R3 验证 2: mutation-surfaces 功能不变
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint mutation-surfaces
# 期望: ✅ omo lint mutation-surfaces pass: surfaces=28

# P102 R3 验证 3: 行数统计
wc -l projects/omo/src/omo/omo_lint.py projects/omo/src/omo/omo_lint_surfaces.py
# 期望: 594L + 179L, omo_lint.py 较 P101 末 -137L

# P102 R3 验证 4: re-export 向后兼容
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "from omo.omo_lint import cmd_lint_mutation_surfaces, cmd_lint_ingress_registry, cmd_lint_c2g_omo_boundary; print('✅ re-export OK')"
# 期望: ✅ re-export OK

# P102 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P102 R5: governance
cd projects/omo && uv run omo governance
# 期望: 100.0 A+ (或 99+ A+ with drift)

# P102 R6: mof-version
bin/mof-version record "P102: omo_lint surfaces 子模块拆分 (731→594L, <600L ideal 首次达成)"
# 期望: v0.0.90 → v0.0.91
```

## References

- P85-P99: 见 ADR-0093 + ADR-0094 + ADR-0095 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步 (估数偏差在 P101 校正)
- ADR-0094: P100 omo_lint schemas 子模块拆分 (1269→800L)
- **ADR-0095: P101 omo_lint yaml-bypass 子模块拆分 (800→731L, 顺序校正)** ← 前置
- **ADR-0096: P102 omo_lint surfaces 子模块拆分 (731→594L, 本 ADR)**

---

*最后更新: 2026-06-25 · P102 omo_lint surfaces 子模块拆分收口 (<600L ideal 首次达成, 累计 -53% 行数)*
