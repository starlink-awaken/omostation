---
schema_version: specification/v1
spec_version: 1.0.0
title: UNTYPED 批量分类规则表 — BET-Y1Q4-T10-04
bet_id: BET-Y1Q4-T10-04
status: accepted
lifecycle: contract
last-reviewed: 2026-09-05
type: plan
owner: governance-team
last_updated: 2026-09-05
---

# UNTYPED 批量分类规则表 (BET-Y1Q4-T10-04)

> 基线: 2026-09-05, UNTYPED 软信号 1939 | 目标: <300 且硬阻塞维持 0

## 分类原则

- **长期知识** (会被长期引用的 SSOT 语义) → `type: ssot` → 跑 `--fix` 补 owner/last-reviewed
- **时点产物** (run/report/草稿, 只增不改) → `type: ephemeral` + `status: archived` → 不触发 EXPIRED 硬阻塞
- **工具产物/镜像** → 不分类, 已由 IGNORE_DIRS 降噪 (#3133)

## 目录 → type 规则表

| 目录 | type | 附加字段 | 数量 (基线) |
|------|------|----------|-------------|
| .omo/_knowledge/decisions/ | ssot | --fix 补 owner/date | 357 |
| .omo/_knowledge/design/ | ssot | 同上 | 196 |
| .omo/_knowledge/management/ | ssot | 同上 | 150 |
| .omo/_knowledge/superpowers/ | ssot | 同上 | 77 |
| .omo/_knowledge/patterns/ | ssot | 同上 | 27 |
| .omo/_knowledge/process/ | ssot | 同上 | 26 |
| .omo/_knowledge/reference/ | ssot | 同上 | 9 |
| .omo/standards/ | ssot | 同上 | 55 |
| .agents/skills/ | ssot | 同上 | 28 |
| .omo/_knowledge/audits/ | ephemeral | status: archived | 134 |
| .omo/_knowledge/decision-proposals/ | ephemeral | status: archived | 131 |
| .omo/_knowledge/sediment/ | ephemeral | status: archived | 118 |
| .omo/_knowledge/summaries/ | ephemeral | status: archived | 167 |
| .omo/_knowledge/retros + retrospectives/ | ephemeral | status: archived | 94 |
| .omo/_knowledge/task-prompts/ | ephemeral | status: archived | 38 |
| .omo/_archive/ | ephemeral | status: archived | 75 |
| runtime/sandbox, projects/knowledge 等 | 保持 untyped | 子模块/沙箱自行治理 | ~143 |

## 执行机制 (复用 --fix, DRY)

分类脚本扩展 `generate-docs-index.py --fix` 增加 `--classify <rules.yaml>` 模式:
按上表目录规则批量写 `type`/`status`, 然后常规 `--fix` 补 ssot 的 owner/date。
**不新建独立脚本** (bin/ 脚本配额 add 1 = delete 1)。

## 风险与回滚

- 批量写 frontmatter 后立即 `--check` 验证硬阻塞 0, 回归则 `git checkout -- .omo` 回滚
- ephemeral+archived 不设 last_updated (时点语义), 由 mtime 天然追溯
