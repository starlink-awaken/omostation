---
schema: bet-retro/v1
bet_id: B2-cross-repo
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: B2 — 跨 repo 标准化

## Summary

B2 3 项子交付物全部落地:
- **B2.1** `bin/closeout-pr.sh` — 跨 repo 5 步 closeout 引导 (retro 模板复制 + 跨子模块状态 + PR/merge 提示)
- **B2.2** `bin/mof/cross-repo-status.py` — 主仓 + 16 子模块统一 dashboard (checkout / branch / head / dirty / aligned)
- **B2.3** `bin/ssot/retro-template.md` — 统一 retro 模板 (frontmatter 六件套 + 4 问结构 + metrics + done_when + 相关)

## What went well

- **复用现有工具**: closeout-pr.sh 直接调用 gac-worktree.sh + cross-repo-status.py, 不重新发明
- **对齐检测**: cross-repo-status.py 通过 `git ls-tree HEAD path` 拿 gitlink + 子模块 HEAD 对比,
  识别 P97 squash 残留 / submodule 指针漂移
- **JSON 兼容**: 主输出结构化 JSON, 表格 stdout 友好, CI 集成零摩擦
- **closeout 一体化**: 5 步 (retro 复制 → 跨子模块状态 → PR 提示 → merge 提示 → 清理),
  与 A2 SOP 互为表里

## What was learned

- **`git ls-tree HEAD path` 输出格式**: `160000 commit <sha>\t<path>`, split() 取 [2] 是 sha
- **head_sha [:7] vs gitlink 全长对比 bug**: 第一次对比全错, 修成都截 7 位才正确
- **`cwd=sub_dir` 与 `-C path` 冗余**: 后者已足够, 多写反而出错
- **submodule uninitialized 是常态**: 当前 13/16 子模块未 checkout (SSL/网络/worktree 隔离),
  报告应区分 `checkout: True/False` 而不是 fail-fast
- **shell script 不进 script-registry**: `bin/closeout-pr.sh` 是 .sh 不是 .py, 不走
  script-registry. 受 bin-quota 约束但不受 lint 类 gate

## What to improve

- **closeout-pr.sh 无单元测试**: shell 测试需要 bats 或 assert.sh, 当前只有
  script-registry + 手测. 可考虑加 bin-quota 同款的 .sh lint
- **cross-repo-status 没接 gh CLI**: 不读 PR 列表, 只读 git 状态. 增 --include-pr
  可拉 API
- **retro-template.md 占位符**: __BET_ID__ 等需手工替换, 未来可加 bin/retro-new.sh
  自动 sed 替换 + 模板拷贝
- **未跨子模块 apply retro 模板**: B2.1 只在主仓跑. 子仓需独立 retrofit 模板

## Metrics

- Files added: 4 (bin/closeout-pr.sh 80L, bin/mof/cross-repo-status.py 130L,
  bin/ssot/retro-template.md 50L, tests/bin/test_cross_repo_status.py 90L)
- Files modified: 1 (script-registry auto created yaml)
- Tests: 6/6 pass in 0.30s
- Cross-repo scope: 1 主仓 + 16 子模块
- PR: TBD
- Total LOC delta: +350

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| B2.1 `bin/closeout-pr.sh` (5 步引导) | ✅ |
| B2.2 `bin/mof/cross-repo-status.py` (跨子模块 dashboard) | ✅ |
| B2.3 `bin/ssot/retro-template.md` (统一 retro 模板) | ✅ |
| 6 单元测试 (含 alignment bug fix) | ✅ |
| script-registry 登记 cross-repo-status | ✅ |
| ruff check 0 errors | ✅ |
| cross-repo-status 正确识别 3 个 checkout + 13 个 NO | ✅ |
| closeout-pr.sh dry-run 输出 5 步完整提示 | ✅ |