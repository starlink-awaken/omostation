---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0097: P103 omo_lint mutation-ledger 子模块拆分 (594→544L, ADR-0093 4 步路径完整兑现)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P103
- **Extends**: ADR-0093 (P99 兑现路径) + ADR-0094/95/96 (P100/P101/P102)
- **Superseded by**: (无)

## Context and Problem Statement

P102 末 omo submodule working tree 状态:
- `src/omo/omo_lint.py`: **594L** (P102 末, 累计 -675L)
- `projects/omo/src/omo/omo_lint_schemas.py`: 519L (P100)
- `projects/omo/src/omo/omo_lint_yaml_bypass.py`: 102L (P101)
- `projects/omo/src/omo/omo_lint_surfaces.py`: 179L (P102)
- `projects/omo/src/omo/omo_lint_doc.py`: 304L (P88, 未 commit)
- god-module error/warn/ideal (1500/800/600): **全 0**

**P103 是 ADR-0093 P100-P103 4 步路径的收官阶段**:
- 调研 1 个候选区段: mutation-ledger (L379-L436, 57L)
- 业务: 校验 `.omo/change-log/mutations.jsonl` 账本
- 依赖最小: `Path` + `omo.omo_io.read_jsonl`, 零 omo_xxx 内部 helper

**P103 决策**: 拆 **mutation-ledger (57L)**, 兑现 ADR-0093 P100-P103 4 步路径完整闭环。

## Decision

### D1: omo_lint_mutation_ledger.py 子模块创建 (P103 R3 实施)

**实际区段**: line 379-436 (58L 含尾部空白, 净 57L)

**拆出内容** (1 个 cmd):
- **`cmd_lint_mutation_ledger`** (L379-435, 57L):
  - 账本文件存在且非空
  - 8 必填字段 (created_at / actor / action / target / artifact_ref / source_ref / broker_ref / result)
  - artifact_ref 必须 `.omo/` 开头 + 真实文件存在
  - 至少 1 个 committed mutation
  - 真实运行: `entries=40 committed=40` (P103 末验证)

**模块依赖**: `Path` (stdlib) + `omo.omo_io.read_jsonl` (内部 SSOT)

**拆分策略** (P100/P101/P102 模式复用):
1. 创建 `omo_lint_mutation_ledger.py` (92L 头部 + 函数体)
2. omo_lint.py 删除 line 379-436 (58L)
3. 在 omo_lint.py surfaces re-export 后添加:
   ```python
   from .omo_lint_mutation_ledger import (  # noqa: E402, F401
       cmd_lint_mutation_ledger,
   )
   ```

### D2: 收口统计

| 指标 | P102 末 | P103 末 | 变化 |
|------|---------|---------|------|
| `omo_lint.py` | 594L | **544L** | **-50L (-8%)** |
| `omo_lint_mutation_ledger.py` | (新) | 92L | +92L |
| god-module error (>1500L) | 0 | 0 | ✓ |
| god-module warn (>800L) | 0 | 0 | ✓ |
| god-module ideal (<600L) | 0 | 0 | ✓ |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 56 | **57** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

**omo_lint 子模块群最终结构 (P88 + P100-P103)**:
| 模块 | 起始阶段 | 行数 | 业务 |
|:----|:--------|:----|:----|
| `omo_lint.py` | (原) | **544L** | main() 入口 + direct-omo-io + task-policy + self-evolution |
| `omo_lint_doc.py` | P88 | 304L | doc-lifecycle |
| `omo_lint_schemas.py` | P100 | 519L | 7 schema check + cmd_lint_schemas |
| `omo_lint_yaml_bypass.py` | P101 | 102L | yaml-bypass 越权检测 |
| `omo_lint_surfaces.py` | P102 | 179L | 6 governance-surface cmd |
| `omo_lint_mutation_ledger.py` | P103 | **92L** | mutation-ledger 账本校验 |
| (合计) | | **1740L** | (vs 原 1269L, +471L 拆分元数据) |

### D3: ADR-0093 P100-P103 4 步路径完整量化

| 阶段 | 拆解目标 | 拆前 | 拆后 | 减幅 | 阶段成就 |
|:----:|:--------|:----:|:----:|:----:|:--------|
| P100 | schemas | 1269L | 800L | **-469L (-37%)** | 0 error 达成 |
| P101 | yaml-bypass | 800L | 731L | -69L (-9%) | 0 warn 达成 |
| P102 | surfaces | 731L | 594L | -137L (-19%) | <600L ideal 首次 |
| **P103** | **mutation-ledger** | **594L** | **544L** | **-50L (-8%)** | **<600L ideal 完整** |
| (累计) | 4 子模块 | **1269L** | **544L** | **-725L (-57%)** | **4 阶段 100% 闭环** |

**vs ADR-0093 估数偏差**:
- schemas: 估 432L, 实 485L (+12%) - 包含 imports + 4 常量
- yaml-bypass: 估 72L, 实 76L (+6%) - 包含尾部空白
- surfaces: 估 136L, 实 148L (+9%) - 6 cmd + 5 空白行
- mutation-ledger: 估 56L, 实 57L (+2%) - 最接近
- **累计偏差**: +49L (+9%), ADR-0093 估数排序偏差在 P101 已校正

### D4: submodule commit 模式 (P88/P100/P101/P102 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_lint_mutation_ledger.py + 修改 omo_lint.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

**omo_lint.py 当前 working tree**: **544L** ✅ (<600L ideal)
**omo_lint_mutation_ledger.py 当前 working tree**: 92L ✅

## Consequences

**正面**:
- **ADR-0093 4 步路径完整闭环**: P100-P103 全部实施, 11 轮推迟 (P89-P99) → 4 阶段 (P100-P103) 兑现
- **累计 -57% 行数**: omo_lint.py 从 1269L 缩到 544L, 缩至原 43%
- **5 子模块架构完整**: doc/schemas/yaml-bypass/surfaces/mutation-ledger 各司其职
- **业务边界清晰**: 每个子模块 <600L ideal 阈值, 无 god-module 风险
- **P100/P101/P102/P103 模式复用**: re-export + 头注释 + 独立验证, 工具链稳定

**负面**:
- omo submodule working tree 仍未 commit (P88-P103 同模式), 5 个新文件 + 4 处修改文件待审批
- 1740L 合计 vs 1269L 原 = +471L 拆分元数据 (37% overhead), 子模块 header + re-export 累加
- 13 god-module TS AST 工具 (gbrain 10 个) 仍是 P104+ 待推进

**关联**:
- ADR-0093 → ADR-0094 → ADR-0095 → ADR-0096 → **ADR-0097**: 4 步完整兑现路径, 第 5 步收口
- P89 → P99 → P100 → P101 → P102 → **P103**: 11 轮推迟 → 4 阶段实施完整闭环
- P103 是 omostation god-module 治理的 **milestone**: 0 error + 0 warn + <600L ideal 全面达成

## Validation

```bash
# P103 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_lint.py').read()); ast.parse(open('projects/omo/src/omo/omo_lint_mutation_ledger.py').read())"
# 期望: 静默 OK

# P103 R3 验证 2: mutation-ledger 功能不变
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint mutation-ledger
# 期望: ✅ omo lint mutation-ledger pass: entries=40 committed=40

# P103 R3 验证 3: 行数统计
wc -l projects/omo/src/omo/omo_lint.py projects/omo/src/omo/omo_lint_mutation_ledger.py
# 期望: 544L + 92L, omo_lint.py 较 P102 末 -50L

# P103 R3 验证 4: re-export 向后兼容
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "from omo.omo_lint import cmd_lint_mutation_ledger; print('✅ re-export OK')"
# 期望: ✅ re-export OK

# P103 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P103 R5: governance
cd projects/omo && uv run omo governance
# 期望: 100.0 A+ (或 99+ A+ with drift)

# P103 R6: mof-version
bin/mof-version record "P103: omo_lint mutation-ledger 子模块拆分 (594→544L, ADR-0093 4 步路径完整兑现)"
# 期望: v0.0.91 → v0.0.92
```

## References

- P85-P99: 见 ADR-0093 + ADR-0094 + ADR-0095 + ADR-0096 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094: P100 omo_lint schemas 子模块拆分 (1269→800L)
- ADR-0095: P101 omo_lint yaml-bypass 子模块拆分 (800→731L, 顺序校正)
- ADR-0096: P102 omo_lint surfaces 子模块拆分 (731→594L, <600L ideal 首次)
- **ADR-0097: P103 omo_lint mutation-ledger 子模块拆分 (594→544L, 本 ADR, ADR-0093 4 步完整兑现)**

---

*最后更新: 2026-06-25 · P103 omo_lint mutation-ledger 子模块拆分收口 (ADR-0093 4 步路径完整兑现, 累计 -57% 行数)*
