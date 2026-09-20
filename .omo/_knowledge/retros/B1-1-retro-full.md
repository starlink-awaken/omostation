---
schema: bet-retro/v1
bet_id: B1-1-retro-full
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: B1.1 — auto-fix-loop retro 字段扩展

## Summary

扩展 `bin/gac/auto-fix-loop.py` 处理 retro 类文档的全字段漂移.
原来只检测 "missing_frontmatter (无 YAML)", 现新增两类:
- `FRONTMATTER-MISSING-FIELD`: frontmatter 存在但缺字段 (如 last-reviewed)
- `INVALID-METADATA`: 字段值不在 allowed set (如 status='closed' 应为 'archived')

两条对偶 RETRO-SKIPPED 变体, 在 closeout 分支同样跳过 retro 路径 (A3 兼容).

## What went well

- **二元模式扩展**: A3 已有 closeout-skip 框架, B1.1 直接复用 is_closeout_branch + is_retro_path
- **真实数据驱动**: 实际 retro 仓库中:
  - 47 retro 文件有 status='closed' (invalid_metadata 类)
  - 82 retro 文件有 missing required frontmatter fields (field 类)
  - 4 retro 文件完全没有 frontmatter
- **修复入口明确**: `fix-frontmatter.py --batch .` 一条命令覆盖三类
- **JSON 输出稳定**: 新增 drift kind 在 JSON 中可见, 不破坏 CI 解析

## What was learned

- **doc-governance 输出格式 3 类**: 
  - `does not start with YAML` (无 frontmatter)
  - `missing required frontmatter fields` (frontmatter 缺键)
  - `status must be one of` / `lifecycle must be one of` (字段值不在 allowed set)
- **retry-by-design**: 旧 A3 已用 `if closeout_mode and ...`, B1.1 必须同样用
  `if closeout_mode:` (无条件) 才能处理新增两个集合
- **branch 命名避坑**: `b11-retro-full` 误命中 `-retro\b` pattern, 改名为 `b1-1-retro-full`
  (用 `1-1` 而非 `11`)

## What to improve

- **修复入口粗糙**: `fix-frontmatter.py --batch .` 一次性扫全仓, 不能定向
  retro 单独路径. 未来可加 `--batch --retro-only`
- **未触达 deep 字段**: 如 `bet_id` 缺失 / `completed_at` 格式错误 / `schema_version`
  不匹配, 都是 frontmatter 内部问题, 当前 drift 没分类到这些细分
- **CI 集成缺失**: 当前只在本地跑 auto-fix-loop, CI 不验证 retro 字段合规.
  后续可在 pre-commit 加轻量级检查

## Metrics

- Files modified: 1 (bin/gac/auto-fix-loop.py +60L, 现 488L)
- Files added: 1 (tests/bin/test_auto_fix_loop_b11.py 110L)
- Tests: 4/4 pass (新增) + 13/13 A3 regression pass
- New drift kinds: 4 (FRONTMATTER-MISSING-FIELD, INVALID-METADATA,
  FRONTMATTER-MISSING-FIELD-RETRO-SKIPPED, INVALID-METADATA-RETRO-SKIPPED)
- Real data: 47 + 82 retro drift + 4 missing-fm retro
- PR: TBD
- Total LOC delta: +170

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| FRONTMATTER-MISSING-FIELD drift 检测 | ✅ |
| INVALID-METADATA drift 检测 (status/lifecycle) | ✅ |
| 对偶 RETRO-SKIPPED 变体 (closeout-mode 跳过) | ✅ |
| apply_fix 支持新 drift kinds | ✅ |
| 4 新增单元测试 (含 SKIP_FIX_LOOP_BRANCH=1 路径) | ✅ |
| A3 13 测试回归 PASS | ✅ |
| ruff check 0 errors | ✅ |
| --json 输出包含所有 6 种 drift kinds (实测) | ✅ |
| fix-frontmatter.py --batch 入口正确 | ✅ |