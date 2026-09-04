---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last_updated: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-04
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G4: Governance owner 字段迁移 (troubleshootable 6→8)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-04
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G4)

## 背景与问题

`maturity-scorecard.py::score_troubleshootable` 检测 `governance-migration.py --dry-run`
是否返回 "No changes needed"。
当前 139 个 governance checks 缺 owner/expected/remediation 字段，troubleshootable = 6。

根因：governance-checks.yaml 的 checks 增量演进，多数条目未补 owner/expected/remediation
字段（具备"谁负责 + 期望 + 修复"才算可排障）。

## 架构选择

复用现有 `bin/ssot/governance-migration.py --apply`（自动 infer owner/expected/remediation
并回填 governance-checks.yaml）。该工具已实现字段推断逻辑，不新增工具。

- 执行：`uv run --with pyyaml python3 bin/ssot/governance-migration.py --apply`
- 产出：governance-checks.yaml 所有 checks 补全 owner/expected/remediation
- 验证：`--dry-run` 返回 "No changes needed"

替代方案（未采用）：人工逐条填 139 个字段——不现实且易错，现有迁移工具已覆盖。

## 验收标准

1. **[governance-migration dry-run = No changes needed]**
   - 验证方式：`uv run --with pyyaml python3 bin/ssot/governance-migration.py --dry-run`
   - 证据类型：输出含 "No changes needed"

2. **[scorecard troubleshootable = 8]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json`
   - 证据类型：scores.troubleshootable = 8

3. **[governance-checks.yaml 全量 owner 覆盖]**
   - 验证方式：grep 统计 checks 条目 owner 字段
   - 证据类型：无缺失

## 反指标

本 spec **不追求**以下指标作为成功度量：
- owner 归属 100% 业务精确（迁移工具启发式推断，人工精修是后续演进）
- 改造 governance-checks.yaml schema（迁移只回填既有字段）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 复用迁移工具 vs 人工 | 复用 --apply | 工具已实现推断逻辑，避免重复造轮 |
| 2 | 全量 vs 分批 | 全量 apply | 139 个一次迁移，工具幂等 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G4) | agent |
