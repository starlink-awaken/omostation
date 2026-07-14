---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0095: P101 omo_lint yaml-bypass 子模块拆分 (800→731L, 校正 P102-P103 顺序)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P101
- **Extends**: ADR-0093 (P99 兑现路径) + ADR-0094 (P100 schemas 拆)
- **Superseded by**: (无)

## Context and Problem Statement

P100 末 omo submodule working tree 状态:
- `src/omo/omo_lint.py`: **800L** (1269 → 800, -469L)
- `projects/omo/src/omo/omo_lint_schemas.py`: 519L (P100 创建)
- `projects/omo/src/omo/omo_lint_doc.py`: 304L (P88 创建, 未 commit)
- **god-module error (>1500L)**: 0 ✓ P100 已闭环
- **god-module warn (>800L)**: 1 (801L, P100 末 800L 触发, 但仍在阈值内)

P101 调研 4 个候选区段, **校正 ADR-0093 顺序**:

| 候选 | 估数 (ADR-0093) | 实测 | 业务独立 |
|------|----------------|------|---------|
| schemas | 432L | 485L | ✓ (P100 已做) |
| surfaces | 136L | 116L+26L = 142L | ✗ 5 个 thin wrapper, 核心已外置 |
| **yaml-bypass** | **72L** | **74L** | ✓ 仅依赖 Path + yaml |
| mutation-ledger | 56L | 57L | ✓ 仅依赖 read_jsonl |

**校正结论**: ADR-0093 估数排序 = surfaces < yaml-bypass < mutation-ledger, 但实际:
- yaml-bypass 业务最独立 (零 omo_xxx 内部依赖)
- mutation-ledger 同样独立但更小 (57L)
- surfaces 拆完收益小 (只是把 thin wrapper 移走)

**P101 决策**: 拆 **yaml-bypass (74L)** 而非 surfaces (136L)。

**校正 P102-P103**:
- P102: surfaces 拆 (~142L) → 589L
- P103: mutation-ledger 拆 (57L) → 532L, <600L ideal

## Decision

### D1: omo_lint_yaml_bypass.py 子模块创建 (P101 R3 实施)

**实际区段**: line 71-146 (76L 包含 2 空白行, 净 74L)

**拆出内容**:
- **`_check_yaml_bypass`** (L71-128, 58L): Round 43 P0, 扫 .omo/debt/items/*.yaml 检测 status/lifecycle_state 越权
- **`cmd_lint_yaml_bypass`** (L129-146, 18L): 汇总入口

**模块依赖**: `Path` + `yaml` (stdlib only), 零 omo_xxx 内部依赖。

**拆分策略** (P100 模式复用):
1. 创建 `omo_lint_yaml_bypass.py` (102L 头部 + 函数体)
2. omo_lint.py 删除 line 71-146 (76L)
3. 在 omo_lint.py schemas re-export 后添加:
   ```python
   from .omo_lint_yaml_bypass import (  # noqa: E402, F401
       _check_yaml_bypass,
       cmd_lint_yaml_bypass,
   )
   ```

### D2: 收口统计

| 指标 | P100 末 | P101 末 | 变化 |
|------|---------|---------|------|
| `omo_lint.py` | 800L | **731L** | **-69L (-9%)** |
| `omo_lint_yaml_bypass.py` | (新) | 102L | +102L |
| `omo_lint_schemas.py` | 519L | 519L | 不变 |
| god-module error (>1500L) | 0 | 0 | ✓ |
| **god-module warn (>800L)** | 1 (801L) | **0** | **warn 阈值清零** |
| god-module error/warn 阈值 | — | <800L 净, <600L ideal | — |
| 工具数 | 44 | 44 | 不变 |
| ADR 数 | 54 | **55** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

**god-module 兑现进度 (ADR-0093 P100-P103 4 步, 校正后)**:
- ✅ P100: schemas 拆 (-469L), 0 error 达成
- ✅ **P101: yaml-bypass 拆 (-69L), 0 warn 达成** ← 净 731L < 800L
- 🔲 P102: surfaces 拆 (~142L) → 589L
- 🔲 P103: mutation-ledger 拆 (57L) → 532L, <600L ideal

### D3: 顺序校正 (ADR-0093 偏差承认)

**ADR-0093 估数 vs 实测**:
- schemas: 估 432L, 实 485L (+12%)
- surfaces: 估 136L, 实 142L (+4%)
- mutation-ledger: 估 56L, 实 57L (+2%)
- yaml-bypass: 估 72L, 实 74L (+3%)

**校正 P101-P103 顺序理由**:
1. yaml-bypass 业务最独立 (74L, 零 omo_xxx 依赖), 是最优入门拆分
2. mutation-ledger 同样独立但更小, 适合最后清理
3. surfaces 拆完是 thin wrapper 移位, 收益次于 yaml-bypass

**ADR-0093 顺序修正**:
- 原: P101 surfaces → P102 mutation-ledger → P103 yaml-bypass
- 校正: **P101 yaml-bypass → P102 surfaces → P103 mutation-ledger**

### D4: submodule commit 模式 (P88/P100 一致)

按 CLAUDE.md §📋 + ADR-0093 D2:
- omo submodule working tree 内变更 (创建 omo_lint_yaml_bypass.py + 修改 omo_lint.py) **不自动 commit**
- 待 omostation 人类审批 commit 节奏
- 根仓仅 commit 元数据 (本 ADR + 后续 mof-version 登记)

**omo_lint.py 当前 working tree**: **731L** ✅ (<800L warn 阈值清零)
**omo_lint_yaml_bypass.py 当前 working tree**: 102L ✅

## Consequences

**正面**:
- **P100-P101 连续 2 阶段 god-module 闭环**: error 0 → warn 0
- **顺序校正透明**: 承认 ADR-0093 估数排序偏差, 用实测调整
- **业务独立 yaml-bypass**: 102L 子模块零内部依赖, 复用率低风险
- **P100 模式复用**: re-export 模式保持一致, cli.py 调用点不破
- **P102-P103 路径明确**: surfaces (142L) + mutation-ledger (57L) = 199L 剩余

**负面**:
- omo submodule working tree 仍未 commit (P88/P100 同模式)
- 顺序校正打破 ADR-0093 字面顺序, 需在 X1 audit 中明确登记
- P102-P103 仍是预期, 真实工作量待验证

**关联**:
- ADR-0093 → ADR-0094 → ADR-0095: P99 兑现路径 → P100 schemas 拆 → P101 yaml-bypass 拆
- P88 doc-lifecycle → P100 schemas → P101 yaml-bypass: 子模块拆分模式持续复用
- ADR-0095 校正 ADR-0093 顺序: surfaces 推迟到 P102, mutation-ledger 推迟到 P103

## Validation

```bash
# P101 R3 验证 1: 模块解析
python3 -c "import ast; ast.parse(open('projects/omo/src/omo/omo_lint.py').read()); ast.parse(open('projects/omo/src/omo/omo_lint_yaml_bypass.py').read())"
# 期望: 静默 OK

# P101 R3 验证 2: omo lint yaml-bypass 功能不变
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint yaml-bypass
# 期望: 3 处越权 (与 P100 末一致)

# P101 R3 验证 3: 行数统计
wc -l projects/omo/src/omo/omo_lint.py projects/omo/src/omo/omo_lint_yaml_bypass.py
# 期望: 731L + 102L, omo_lint.py 较 P100 末 -69L

# P101 R3 验证 4: re-export 向后兼容
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "from omo.omo_lint import cmd_lint_yaml_bypass, _check_yaml_bypass; print('✅ re-export OK')"
# 期望: ✅ re-export OK

# P101 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P101 R5: governance
cd projects/omo && uv run omo governance
# 期望: 100.0 A+ (或 99.3 A+ with drift)

# P101 R6: mof-version
bin/mof-version record "P101: omo_lint yaml-bypass 子模块拆分 (800→731L, god-module warn 清零, 顺序校正)"
# 期望: v0.0.89 → v0.0.90
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 (doc-lifecycle 304L) + X2 template + gov-trend-report
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
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步 (估数偏差在 P101 校正)
- **ADR-0094: P100 omo_lint schemas 子模块拆分 (1269→800L)** ← 前置
- **ADR-0095: P101 omo_lint yaml-bypass 子模块拆分 (800→731L, 本 ADR)**

---

*最后更新: 2026-06-25 · P101 omo_lint yaml-bypass 子模块拆分收口 (god-module warn 清零, ADR-0093 顺序校正)*
