---
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-24
last_updated: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-01
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G1: Script Registry 全量登记 (evolvable 6→8)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-01
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G1)

## 背景与问题

`maturity-scorecard.py::score_evolvable` 检测 `script-registry.py validate` 是否返回 `VALIDATION PASSED`。
当前 **452 个 bin/ 脚本未登记**（registry 只有部分），evolvable = 6/10。

根因：script registry (`bin/_registry/scripts/`) 是增量登记的，历史上没有一次性全量扫描回填。
script-registry.py 已具备 `register` 子命令（自动猜 category/owner + 生成 schema v1 yaml），但缺批量回填。

## 架构选择

复用现有 `bin/ssot/script-registry.py register <path>`（单脚本登记，自动猜 category/owner），
循环 452 个缺失脚本批量登记。不新增工具（复用现资产，避免重复造轮子）。

- 生成物：`bin/_registry/scripts/<category>/<stem>.yaml`（每脚本一个，schema script-registry/v1）
- id = 相对路径（与 validate 的 actual_scripts 比对一致）
- category/owner 由 guess_category/guess_owner 自动推断
- 排除 `bin/_registry/` 自身 + `_` 前缀目录（validate 逻辑已处理）

替代方案（未采用）：重写 registry 为单文件 SSOT——破坏现有按目录组织，且 validate 逻辑需重写，风险大于收益。

## 验收标准

1. **[script-registry validate PASS]**
   - 验证方式：`python3 bin/ssot/script-registry.py validate`
   - 证据类型：输出含 "VALIDATION PASSED"

2. **[maturity-scorecard evolvable = 8]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json | jq .scores.evolvable`
   - 证据类型：JSON 输出 = 8

3. **[452 个注册文件存在]**
   - 验证方式：`find bin/_registry/scripts -name '*.yaml' | wc -l` ≥ 已登记数
   - 证据类型：文件计数

## 反指标

本 spec **不追求**以下指标作为成功度量：
- 每个脚本的 description 都人工填写（452 个自动生成可用默认空 description，人工精修是后续优化）
- owner 归属 100% 精确（guess_owner 启发式足够支撑 validate PASS，精确归属是演进项）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 批量脚本 vs 人工逐个 | 批量循环 register | 452 个人工不现实，register 已具备自动推断 |
| 2 | 单文件 SSOT vs 按目录 | 按目录 (现有) | 不破坏现有结构，validate 已兼容 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G1) | agent |
