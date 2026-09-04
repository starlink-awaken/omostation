---
title: BET-Y1Q3-T6-03 复盘 — mof-deepen 测试面补齐
type: retro
owner: engineering-agent
created: 2026-08-16
related:
  - PR #1574 (commit 16558bc41)
context: >-
  为 575843deb 无主落账的 10 个 mof-deepen 模块补齐最小测试面。
  参考 test_signal_poller.py 的 importlib.util.spec_from_file_location 模式
  处理带连字符的模块文件名。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T6-03 复盘

## Q1 实际耗时 vs appetite

appetite 2 days, 实际 0.5 天。快于预期——仅写 10 个 smoke 测试，不涉及重构。

## Q2 done_when 全过?

| # | done_when | 结果 |
|---|---|---|
| 1 | 每个模块至少 1 个 smoke 测试 (import + 核心函数可调用) | ✅ 10 个模块各 1 个 smoke 测试 |
| 2 | ADMIN_SCENES dispatcher 注册路径有集成测试覆盖 | ✅ test_admin_scenes_import_and_dispatcher 验证 |
| 3 | 新增测试在 CI 全绿 | ✅ 15 个 CI 检查全绿 |

全过, 置 done。

## Q3 计划与事实的偏差

1. **台账文件名与实际文件名不匹配** — 台账写 `scene_reflection.py` 但实际文件是 `scene-reflection.py`（连字符）。
   处置：参考 test_signal_poller.py 的 importlib.util.spec_from_file_location 模式处理连字符文件名。
2. **ROOT 路径计算错误** — tests/test_mof_deepen_smoke.py 在 tests/ 目录，用 `parents[2]` 会跑到主仓外。
   处置：改用 `parents[1]` 直接取 worktree 根目录。
3. **claim 命令需 --affected-receipt 参数** — 仅传 --path 会返回 exit code 2 但无错误信息。
   处置：补全 --affected-receipt 参数指向 JSON receipt。

## Q4 表面积影响

+112 行 (tests/test_mof_deepen_smoke.py)。换 10 个模块的最小触达验证，ROI 为正。

## Q5 给下一个 agent 的建议

1. **带连字符的 Python 模块无法直接 import** — 必须用 importlib.util.spec_from_file_location。
2. **worktree 环境下路径计算要小心** — tests/ 目录向上 1 级才是 worktree 根目录，不是 2 级。
3. **agent-workflow claim 命令需 affected-receipt** — 即使已生成 affected-graph.json，也要显式传参。
4. **PR 合并后 worktree 需手动释放** — gac-worktree.sh release 会自动清理 17 个子模块分支 + 主分支。
