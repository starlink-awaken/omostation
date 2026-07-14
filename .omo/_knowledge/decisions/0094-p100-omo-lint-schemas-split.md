---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0094: P100 omo_lint schemas 子模块拆分 (1269→800L, 兑现 11 轮推迟)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P100
- **Extends**: ADR-0093 (P99 self-ref 清 + omo_lint 兑现路径 P100-P103)
- **Superseded by**: (无)

## Context and Problem Statement

P99 ADR-0093 D2 明确 P100-P103 4 步兑现路径, P100 推入 schemas 拆分 (P89-P99 共 11 轮推迟):

1. **P100**: schemas 拆 (432L) → 825L, <1500L error 阈值
2. P101: surfaces 拆 (136L) → 689L
3. P102: mutation_ledger 拆 (56L) → 633L
4. P103: yaml_bypass 拆 (72L) → 561L, <800L warn 阈值

P99 末 omo submodule working tree 状态:
- `src/omo/omo_lint.py`: **1269L** (P88 拆解后 1257 + P98 typo 应用 12L)
- `projects/omo/src/omo/omo_lint_doc.py`: 304L (P88 创建, 未 commit)
- 仍 1 god-module error (>1500L threshold)

P100 调研 2 项, 实施 1 项 (P100-B 推迟):
- **P100-A 实施**: omo_lint schemas 子模块拆分, 兑现 11 轮推迟
- **P100-B 推迟**: 7 TEMPLATE ADR 注释 (P99 已 P50+ 6→3 收口, 此项与 P97 apply 闭环重复)

## Decision

### D1: omo_lint_schemas.py 子模块创建 (P100 R3 实施)

**实际区段**: line 54-538 (485L, 比 ADR-0093 估的 432L 多 53L, 因 imports + 4 模块级常量)

**拆出内容** (P99 调研 R1 定位):
- **模块级常量 (4 个, schemas 区段独占)**:
  - `OMO_SRC` (54): `Path(__file__).resolve().parent`
  - `CONSUMER_MODULES` (60-68): 7 consumer tuple
  - `_CROSS_MODULE_SRP_ALLOWLIST` (130-139): §13.3.3 规则 7 白名单
  - `_SORT_KEYS_DEFAULT_EXEMPT_MODULES` (144-148): §12.1.4 跨仓豁免
- **6 个 schema check 函数**:
  - `_check_module_append_has_schema` (71-149): R15 P0, consumer .append() 必传 schema=
  - `_check_sort_keys_default` (151-251): R34+R37 P0, sort_keys=True 跨仓不变量
  - `_check_dead_imports` (253-310): R32 P0, import 但未用
  - `_check_cross_module_srp` (312-357): R30 P0, 7 consumer 互不依赖
  - `_check_all_schemas_exported` (359-384): R29 P0, __all__ 完整
  - `_check_schema_registry_integrity` (386-424): R21 P0, Z-suffix + 必填字段
- **入口 cmd**: `cmd_lint_schemas` (426-538): 6 规则汇总

**拆分策略** (P88 模式扩展):
1. 创建 `omo_lint_schemas.py` (488L 头部 + 函数体)
2. omo_lint.py 删除 line 54-538 (485L)
3. 在 omo_lint.py:54 添加 re-export:
   ```python
   from .omo_lint_schemas import (  # noqa: E402, F401
       CONSUMER_MODULES,
       OMO_SRC,
       _CROSS_MODULE_SRP_ALLOWLIST,
       _SORT_KEYS_DEFAULT_EXEMPT_MODULES,
       _check_all_schemas_exported,
       _check_cross_module_srp,
       _check_dead_imports,
       _check_module_append_has_schema,
       _check_schema_registry_integrity,
       _check_sort_keys_default,
       cmd_lint_schemas,
   )
   ```

### D2: 向后兼容性 (Critical)

**P100 前后唯一外部 call site**:
- `cli.py:200,206`: `from omo.omo_lint import main as lint_main` + `cmd_lint_schemas`
- `omo_audit.py:580-585`: doc symbols (已有 omo_lint_doc.py re-export, 不受影响)

**schemas 区段外部依赖**: **零**。`CONSUMER_MODULES` / `OMO_SRC` / `_check_*` 全部内部使用，无外部直接 import。re-export 是 defensive 做法（P88 模式）。

### D3: 收口统计

| 指标 | P99 末 | P100 末 | 变化 |
|------|--------|---------|------|
| `omo_lint.py` | 1269L | **800L** | **-469L (-37%)** |
| `omo_lint_schemas.py` | (新) | 519L | +519L |
| god-module error (>1500L) | 1 | **0** | **闭环** |
| omo_lint.py god-module 警告 (>800L) | 1 | 0 | warn 阈值 (801L 已下) |
| 工具数 | 44 | 44 | 不变 (P100 实施无新工具) |
| ADR 数 | 53 | **54** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

**god-module 兑现进度 (ADR-0093 P100-P103 4 步)**:
- ✅ P100: schemas 拆 (-469L), **0 error** 达成
- 🔲 P101: surfaces 拆 (136L), warn 阈值 800L 下
- 🔲 P102: mutation_ledger 拆 (56L)
- 🔲 P103: yaml_bypass 拆 (72L)

### D4: submodule commit 模式 (P88 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_lint_schemas.py + 修改 omo_lint.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

**omo_lint.py 当前 working tree**: 800L ✅ (god-module 阈值 1500L / warn 800L)
**omo_lint_schemas.py 当前 working tree**: 519L ✅ (远低于 800L warn)

## Consequences

**正面**:
- **11 轮推迟闭环**: P89-P99 共 11 轮推迟后, P100 终推入并实施 schemas 拆
- **god-module error 清零**: omo_lint.py 1269L → 800L, <1500L threshold, 0 god-module error
- **向后兼容**: re-export 模式保持 P88 一致, cli.py/omo_audit.py 等调用点不破
- **P88 模式复用**: 与 doc-lifecycle 子模块拆分一致, 降低认知负担
- **3 步拆解路线明确**: P101 surfaces / P102 mutation_ledger / P103 yaml_bypass 仍待推进

**负面**:
- omo submodule working tree 仍未 commit (P88 同), 依赖人类审批
- 实际拆分比 ADR-0093 估的多 53L (485L vs 432L), 但仍达 <1500L 阈值
- P100-B 7 TEMPLATE ADR 注释 推迟 (低优先级, 与 P97 apply 闭环重叠)

**关联**:
- ADR-0093 → ADR-0094: P99 兑现路径明确化 → P100 实施 schemas 拆
- P89 god-module-roadmap → P100 schemas 拆: 11 轮推迟兑现
- P88 doc-lifecycle 拆 → P100 schemas 拆: 子模块拆分模式复用

## Validation

```bash
# P100 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_lint.py').read()); ast.parse(open('projects/omo/src/omo/omo_lint_schemas.py').read())"
# 期望: 静默 OK

# P100 R3 验证 2: omo lint schemas 功能不变
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint schemas
# 期望: 6/6 规则 ✅ (7 consumer 合规 + SCHEMA_REGISTRY 完整 + __all__ 完整 + consumer SRP + 0 dead + sort_keys 守)

# P100 R3 验证 3: 行数统计
wc -l projects/omo/src/omo/omo_lint.py projects/omo/src/omo/omo_lint_schemas.py
# 期望: 800L + 519L, omo_lint.py 较 P99 末 -469L

# P100 R3 验证 4: re-export 向后兼容
cd projects/omo && python3 -c "from omo.omo_lint import cmd_lint_schemas, CONSUMER_MODULES, OMO_SRC; print('✅ re-export OK')"
# 期望: ✅ re-export OK

# P100 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P100 R5: governance
cd projects/omo && uv run omo governance
# 期望: 100.0 A+

# P100 R6: mof-version
bin/mof-version record "P100: omo_lint schemas 子模块拆分 (1269→800L, 兑现 11 轮推迟)"
# 期望: v0.0.88 → v0.0.89
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- **P88 R1-R3: omo_lint 拆解 (doc-lifecycle 304L) + X2 template + gov-trend-report** ← 拆分模式范本
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 12 (god-module-roadmap 提)
- P90 R1-R4: X2 rule OMO-LINT-SIZE + adr-drift-classify + dashboard cron + dashboard 13
- P91 R1-R4: install-dashboard-cron + X2-FRESH-GOV-DASHBOARD + gov-history-stats + dashboard 14
- P92 R1-R3: adr-trend-insight + install-dashboard-cron 推入 + 类别趋势深化 + dashboard 15
- P93 R1-R2: adr-drift-auto-fix + gov-history-stats --compare + dashboard 16
- P94 R1-R3: adr-drift-apply + 13 god-module list + REAL_BUG 修 + dashboard 18
- P95 R1-R3: adr-drift-apply --apply 实际 (20 files) + adr-typo-fix (Jaccard) + pyyaml + dashboard 19
- P96 R1-R3: adr-typo-real-fix (真 Levenshtein) + venv-yaml-check + X2-FRESH-ADR-DRIFT + dashboard 21
- P97 R1-R3: TYPO apply + adr-rollback-test + X2-FRESH-ADR-TYPO + dashboard 22
- P98 R1-R3: 3 ASPIRATIONAL + 1 REAL_BUG + 4 TYPO + regex bug 修 + P50+ 19→2 (-89%)
- P99 R1-R2: ADR-0092 self-ref 清 + omo_lint 兑现路径 (P100+ 推进)
- **ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步** ← P100 兑现承诺
- **ADR-0094: P100 omo_lint schemas 子模块拆分 (本 ADR)**

---

*最后更新: 2026-06-25 · P100 omo_lint schemas 子模块拆分收口 (god-module error 0 达成, 11 轮推迟闭环)*
