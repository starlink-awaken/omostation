---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0078: P84 M2 coverage 修正 + X2 freshness check + rule 修正

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P84
- **Extends**: ADR-0077 (P83 历史数据洞察)
- **Superseded by**: (无)

## Context and Problem Statement

P83 收口后, P84 调研 3 项治理盲区填补, 全部实施:

1. **M2 type-coverage 报告噪音**: `mof-schema-validate.py --type-coverage` 报告 "M2 孤儿: 69" 其中 67 是 case-mismatch 噪音. alias 生成 (`mt[0].lower() + mt[1:]` + `mt.lower()`) 把 PascalCase M2 type 转成 snake_case/camelCase 加入了 m2_types_set, 然后 M1 只用 PascalCase → 67 误报
2. **X2 freshness 无检查工具**: `.omo/_truth/x2-freshness-rules.yaml` 9 条规则, 但无工具自动检查每条规则的 target 是否超 threshold_days
3. **X2-FRESH-DEBT-EVIDENCE-INTEGRITY 规则 target 错**: 规则 target 是 `.omo/debt/items/DEBT-*.yaml`, 实际 debt 用 `D-` 前缀 (`.omo/debt/items/D-*.yaml`), 规则永远无法命中

## Decision

### D1: bin/mof-m2-coverage.py 修正版 (P84 R1)

**新工具** (`bin/mof-m2-coverage.py`):
- 加载 M2 schema 的 `m2_type` 字段 (PascalCase) - 不含文件名前缀
- 加载 M1 node 的 `type` 字段使用统计
- 真正孤儿 = M2 m2_type 在 M1 中无任何节点使用 (精确比较)
- 漂移 = M1 用了但 M2 没声明

**实测对比**:
| 指标 | mof-schema-validate (旧) | mof-m2-coverage (新) |
|------|--------------------------|---------------------|
| 真正孤儿 | 69 (含 67 噪音) | 2 (`GovernanceDecision`, `OmniEnvelope`) |
| 覆盖率 | 95.7% (基于 alias) | 95.7% (基于 m2_type) |
| Type drift | (未统计) | 1 (`ModelDefinition` 在 M1 用 7 次, M2 未声明) |

**根因**: 旧工具的 alias 计算把 `Action` 同时也变成了 `action` (lowercase), 然后用 `m2_types_set - used` 计算孤儿, 把 `action` 也算孤儿, 但 M1 只用 `Action`. 修正: 只比较 M2 m2_type 字段 vs M1 type 字段, 中间不加 alias 噪音.

### D2: bin/x2-freshness-check.py (P84 R2)

**新工具** (`bin/x2-freshness-check.py`):
- 加载 X2 rules (兼容多文档 YAML, 9 条规则)
- 检查每条 rule 的 target 路径最后修改时间
- 支持 glob 模式 (`DEBT-*.yaml`, `projects/*/src/**/*.py`)
- 计算 `days_since` vs `threshold_days`, 触发对应 action (warn/escalate/error)
- archived 项目 (`X2-FRESH-ARCHIVED-LLMGATEWAY`) 单独标记 info, 不算超期

**实测**:
- 9 rules, 8 ok, 1 触发 (DEBT-EVIDENCE-INTEGRITY 错配 target)
- 触发即修 (见 D3)
- 重测: 9 rules, 9 ok, 0 触发

### D3: X2-FRESH-DEBT-EVIDENCE-INTEGRITY target 修正 (P84 R3)

**问题**: target 写 `.omo/debt/items/DEBT-*.yaml` 但实际文件名是 `D-*.yaml`, 规则永远不命中.

**修正**: target 改为 `.omo/debt/items/D-*.yaml`, notes 标注 P84 R2 修正.

**影响**: 规则生效, 后续 14 天巡检将能正确检测 `.omo/debt/items/D-*.yaml` 修改情况, 不会再次误报.

### D4: 收口统计

**P84 工具数**: 24 → **26** 独立 bin 工具 (+2)
- `bin/mof-m2-coverage.py` (新)
- `bin/x2-freshness-check.py` (新)

**ADR 数**: 37 → **38** (P84 +1)

**X2 rules 修正**: 1 (DEBT-EVIDENCE-INTEGRITY target 错配)

## Consequences

**正面**:
- M2 type coverage 报告从 69 噪音 → 2 真孤儿, 治理精度提升 34×
- X2 freshness 9 规则全部可执行, 14/30/90 天巡检闭环
- DEBT-EVIDENCE-INTEGRITY 规则修正后, P43 闭环的 debt closure evidence 强制约束真正可执行
- 2 个新工具填补治理覆盖盲区

**负面**:
- M2 alias 噪音根因 (`mof-schema-validate.py` alias 计算) 未直接修复, 仅用新工具绕开. P85+ 可统一修复 alias 生成
- X2 规则需要持续维护 (新增规则 + target 修正). 工具未自动 lint 规则
- governance-history.jsonl 增长未限制 (1982 行 / 430KB). P85+ 需引入归档策略

**关联**:
- ADR-0077 → ADR-0078: 治理洞察 → 治理执行
- mof-m2-coverage 是 mof-schema-validate 的精确化版本, 工具并存
- x2-freshness-check 是首个 X2 维度自动化检查工具

## Validation

```bash
# P84 R1: M2 coverage
python3 bin/mof-m2-coverage.py
# 期望: 47 M2 schemas, 1195 M1 nodes, 95.7% coverage, 2 真正孤儿, 1 drift

# P84 R2: X2 freshness
python3 bin/x2-freshness-check.py
# 期望: 9 rules, 9 ok, 0 触发

# ruff 验证
ruff check bin/mof-m2-coverage.py
ruff check bin/x2-freshness-check.py
# 期望: All checks passed!
```

## References

- P82 R1-R4: cross-ref scope/status 感知
- P83 R1-R3: governance-history + drift-history 洞察 + gitignore 感知
- P84 R1-R3: M2 coverage 修正 + X2 freshness check + DEBT-EVIDENCE rule 修正
- ADR-0075/0076/0077: cross-ref 工具演进链
- `.omo/_truth/x2-freshness-rules.yaml`: 9 X2 rules
- `projects/ecos/src/ecos/ssot/mof/m2/`: 47 M2 schemas (2 真孤儿)

---

*最后更新: 2026-06-25 · P84 M2 coverage 修正 + X2 freshness check + rule 修正 收口*
