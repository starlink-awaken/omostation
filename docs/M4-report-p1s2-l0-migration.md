# L0-constraints v1 → v2 Migration Report
**Date**: 2026-07-06
**ADR**: ADR-0132 P1-S2
**Schema**: `projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml`

---

## Summary

- v1 条目数: **77**
- v2 条目数: **77**
- 校验错误: **0**

## type → severity 映射

| v1 type | v2 severity | 出现次数 |
|---------|-------------|----------|
| `advisory` | `low` | 1 |
| `preferred` | `medium` | 6 |
| `required` | `high` | 70 |

**合计**:

- `high`: 70 条
- `low`: 1 条
- `medium`: 6 条

## 校验结果

✅ 全部 77 条通过 ConstraintL0 schema 校验

## 字段映射详情 (12 字段 v2 形状)

| v1 字段 | v2 字段 | 转换 |
|---------|---------|------|
| `id` | `id` | 直传 |
| `description` | `description` | 直传 |
| `applies_to` | `applies_to` | 直传 |
| `dimension` | `dimension` | 直传 |
| `type` | `severity` | required→high, preferred→medium, advisory→low |
| `rule` | `rule_expr: {kind, args}` | 字符串 → 结构化 |
| `violation` | `violation_code + violation_message` | 拆分正则 |
| (新增) | `m3_parent` | ConstraintL0 |
| (新增) | `confidence` | fact 默认 |
| (新增) | `state` | scored_active 默认 |
| (新增) | `half_life_days` | 365 默认 |
| (新增) | `relation_constraints` | 空默认 |
| (新增) | `examples / references / rationale` | 空默认 |
