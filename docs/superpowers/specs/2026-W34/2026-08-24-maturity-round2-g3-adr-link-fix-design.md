---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last-reviewed: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-03
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G3: ADR 链接修复 (traceable 6→8)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-03
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G3)

## 背景与问题

`maturity-scorecard.py::score_traceable` 检测 `adr-link-validator.py` 是否 rc=0。
当前 20 条 broken ADR links（9 个 ADR 文件），traceable = 6。

根因：ADR 文件位于 `.omo/_knowledge/decisions/`，多数相对链接少写一层 `../`
（从 decisions 到 workspace root 需 3 层 `../../../`，写成 2 层 `../../`）；
部分目标文件已迁移（adr-process.md → .omo/standards/、check-submodule-hygiene.py → bin/ssot/）；
个别目标已不存在（runtime/matrix.yaml、scheduler_state.json 是运行时/已删文件）。

## 架构选择

逐条修正相对路径层数 + 指向迁移后真实位置；对真不存在的目标（matrix.yaml、
scheduler_state.json）改为纯文本反引号引用（保留历史描述，不保留 broken 链接）。

- 路径层数修正：`../../X` → `../../../X`（workspace root 目标）
- 迁移文件：指向新位置（.omo/standards/adr-process.md、bin/ssot/check-submodule-hygiene.py、projects/omo/src/omo/omo_state.py）
- 死链接：改纯文本

替代方案（未采用）：删除链接文本——丢失历史引用上下文，违反 ADR 记录完整性。

## 验收标准

1. **[adr-link-validator rc=0]**
   - 验证方式：`uv run --with pyyaml python3 bin/gac/adr-link-validator.py`
   - 证据类型：输出含 "PASS: All N ADR links valid"

2. **[scorecard traceable = 8]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json`
   - 证据类型：scores.traceable = 8

3. **[0 broken links]**
   - 验证方式：validator 输出无 "target does not exist"
   - 证据类型：无 broken 行

## 反指标

本 spec **不追求**以下指标作为成功度量：
- 把所有 ADR 链接改写成绝对路径（相对路径是仓库内既定惯例）
- 回溯补全所有历史 ADR 的链接（只修 broken，不动已有效链接）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 修路径 vs 删链接 | 修路径 | 保留历史引用，目标多可解析到真实文件 |
| 2 | 死链接处理 | 改纯文本 | 保留描述，消除 broken |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G3) | agent |
