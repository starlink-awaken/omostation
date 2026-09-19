---
schema: bet-retro/v1
bet_id: A2-closeout-sop
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-19
type: ephemeral
completed_at: 2026-09-19
---

# Retro: A2 — closeout 5 步 SOP 模板化

## Summary

固化 BET closeout 5 步标准流程: worktree claim → implement/verify/retro → closeout
(ledger flip) → commit/push/rebase → PR/merge。新增 `docs/SOPs/ledger-closeout-sop.md`
和 `bin/plan/bet-closeout-auto.py` (5 步检查自动化, dry-run 默认).

## What went well

- **现有 skill 复用**: bet-closeout-chain (8 步详细版) 已沉淀, A2 把 8 步浓缩到 5 步
  (合并 spec binding + 收尾 PR, 突出高频主路径) → docs/SOPs/ledger-closeout-sop.md
- **dry-run 默认**: 不自动执行 commit/push/gh (高风险), 只验证 retro + ledger 状态 + 提示步骤
- **跨 repo 适配表**: 列出 5 个 repo 的工具差异 (主仓/cockpit-ui/omlxc/runtime/family-hub)
- **常见坑速查**: 9 类典型症状 + 修复映射 (SPEC_BINDING_REQUIRED, missing_bet_binding, ...)
- **9 个单元测试覆盖**: retro 验证 + frontmatter 检查 + ledger 状态查询 + UTC 格式

## What was learned

- **台账 id 格式**: 不是 `- id:` 而是 `  id:`, 段边界判断不能简单看 `- id:`
  (会误匹配 `non_goals: - ...` 列表项); 改为 "下个 `id:` 行出现 = 段末"
- **validator 看 git tracked**: script-registry 的 validate 只检查 `git ls-tree HEAD`,
  新加脚本 commit 后才计入, 否则会报 Orphaned registration
- **P73 truth-driven**: 写 closeout SOP 不能凭空造步骤, 必须从 11+ 个已合并 PR
  (#3585/#3703/#3715/#3730/#3753/#3766/#3768/#3791/#3805/#3823/#3958) 提取共识模式

## What to improve

- closeout-auto.py 当前只 dry-run, 未实现自动改台账 (status flip + done_at + CE 注入)
- 跨 repo 部分只列差异表, 未提供每 repo 的 wrapper 脚本 (P2 候选)
- 缺 CI 集成: 当前 SOP 文档, 还没有 pre-rebase/post-merge 自动调用脚本

## Metrics

- Files added: 3 (docs/SOPs/ledger-closeout-sop.md 200L, bin/plan/bet-closeout-auto.py 150L,
  tests/bin/test_bet_closeout_auto.py 110L)
- Files modified: 0
- Tests: 9/9 pass in 0.20s
- SOP 步数: 5 (从 bet-closeout-chain 8 步浓缩)
- Cross-repo 适配表行: 5 (omostation/cockpit-ui/omlxc/runtime/family-hub)
- 常见坑速查行: 9
- PR: TBD
- Total LOC delta: +460

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| docs/SOPs/ledger-closeout-sop.md 创建 | ✅ |
| 5 步标准流程定义 (claim / implement / closeout / commit / merge) | ✅ |
| 跨 repo 适配表 (5 repo 差异) | ✅ |
| 常见坑速查 (9 类症状) | ✅ |
| 验证清单 (10 项) | ✅ |
| bin/plan/bet-closeout-auto.py 实现 | ✅ |
| --dry-run 默认 (高风险步骤不自动) | ✅ |
| retro frontmatter 验证 (六件套) | ✅ |
| ledger 定位 + 状态读取 | ✅ |
| 9 个单元测试 | ✅ |
| ruff check 0 errors | ✅ |
| script-registry 登记 (governance/bet-closeout-auto.yaml) | ✅ |
| doc-governance-check --no-new-warnings PASS | ✅ |