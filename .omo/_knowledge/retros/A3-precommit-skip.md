---
schema: bet-retro/v1
bet_id: A3-precommit-skip
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-19
type: ephemeral
completed_at: 2026-09-19
---

# Retro: A3 — auto-fix-loop closeout-branch skip

## Summary

扩展 `bin/gac/auto-fix-loop.py` 增加 closeout-branch 模式: 当分支名匹配
`-closeout` / `-retro` / `-ledger` / `a[1-9]-` / `bet-execution-` 时,
跳过 FRONTMATTER-MISSING 对 `.omo/_knowledge/retros/*.md` 路径的修复,
避免 closeout PR 携带 retro 时 auto-fix 把 `last-reviewed` 改成今天产生
第二个 commit, 与本地 ledger 不同步 (PITFALL-COO-005, batch 31 复盘)。

## What went well

- **复用已有架构**: auto-fix-loop 已有 Drift 分类 (FRONTMATTER-MISSING) + fix_cmd,
  新增一个 `FRONTMATTER-MISSING-RETRO-SKIPPED` drift 类型 + closeout 检测逻辑即可
- **强制 + 模式双开关**: `SKIP_FIX_LOOP_BRANCH=1` env 强制 + 5 种分支名 pattern 自动检测
- **JSON 兼容**: 新增 drift 类型在 JSON 输出中清晰可见 (`kind: FRONTMATTER-MISSING-RETRO-SKIPPED`)
- **13 单元测试**: 覆盖正向/反向 + env override + 路径边界
- **副作用小**: 不动 fix-frontmatter.py 自身, 单纯在 auto-fix-loop 层过滤

## What was learned

- **retro 路径不止一处**: `.omo/_knowledge/retros/` 主目录 + `.omo/_knowledge/retrospectives/retros/` 历史归档,
  pattern 覆盖必须两个都包含
- **分支检测要稳**: 用 `re.search` 而非 `re.match`, 避免 branch 前缀变化导致漏匹配
  (e.g. `^agent/governance-agent/a[1-9]-` 显式锚定到子目录)
- **不破坏主流程**: 跳过 retro 的同时, 非 retro 文件仍正常修复, 维持漂移检测闭环
- **drift kind 命名**: 加 `-SKIPPED` 后缀 vs `-RETRO-EXEMPT`, 选前者因为短且自解释
- **script-registry 输入规范化**: inputs 多行格式需要明确列出每项, 旧 "无 (脚本自动定位)" 不够明确

## What to improve

- 当前的 5 个 pattern 是经验值, 后续可让 git-discipline skill 提供权威名单
- 跳过 retro 是策略性决策 (不让 auto-fix 改 last-reviewed), 但 retro 本身的 doc-governance
  仍会报错 (status: closed vs lifecycle: history → invalid_metadata drift) — 待 P107 处理
- closeout branch 合并后, retro 路径的 frontmatter 仍需 fix-frontmatter.py --batch 修一次
  (脚本提示 "manual: 合并后再统一 batch 处理")

## Metrics

- Files modified: 3 (bin/gac/auto-fix-loop.py +110L, bin/_registry/...yaml, docs/SOPs/ledger-closeout-sop.md)
- Files added: 1 (tests/bin/test_auto_fix_loop.py 130L)
- Tests: 13/13 pass in 0.20s
- Closeout patterns: 5
- Retro path prefixes: 2
- New drift kind: FRONTMATTER-MISSING-RETRO-SKIPPED
- Env override: SKIP_FIX_LOOP_BRANCH
- PR: TBD
- Total LOC delta: +240

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| `_git_current_branch()` 加 helper | ✅ |
| `is_closeout_branch()` 5 pattern 检测 | ✅ |
| `is_retro_path()` 2 prefix 检测 | ✅ |
| FRONTMATTER-MISSING drift 跳过 retro path | ✅ |
| 新增 FRONTMATTER-MISSING-RETRO-SKIPPED drift | ✅ |
| JSON 输出含 closeout-mode hint | ✅ |
| env SKIP_FIX_LOOP_BRANCH 强制开关 | ✅ |
| 13 单元测试 (含 env override + 路径边界) | ✅ |
| script-registry yaml 更新 (inputs/deps/related) | ✅ |
| SOP §3.5 加 A3 说明段 | ✅ |
| ruff check 0 errors | ✅ |
| script-registry validate 692 PASS | ✅ |
| auto-fix-loop.py --json 实测 4 retro skipped + 1 non-retro fix | ✅ |