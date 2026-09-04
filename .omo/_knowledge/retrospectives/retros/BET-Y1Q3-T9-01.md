---
title: BET-Y1Q3-T9-01 复盘 — 复盘制度落地四件套
type: retro
owner: governance-team
created: 2026-08-15
related:
  - .omo/_knowledge/retros/SESSION-RETROSPECTIVE-20260814-15.md
context: >-
  会话复盘六大失败模式中四个制度缺口的落地轮。PR #1524 (2 commits 链: e90be29+bcc5825
  子模块, 主仓 8713be8b9)。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T9-01 复盘

## Q1 实际耗时 vs appetite

appetite 3 days, 实际 0.5 天。快于预期——因为四件里三件是「小而准」的机制补丁,
不是重构。

## Q2 done_when 全过?

| # | done_when | 结果 |
|---|---|---|
| 1 | verify 含 diff vs claim 基线对比并 FAIL 未提交变更 | ✅ claim 记 baseline_commit + diff_baseline_report 挂 verify, 漂移 FAIL |
| 2 | err 日志按天 rotate 生效 | ✅ LOG_PATTERNS 补 *.err + --daily 模式 (跨天即轮转) |
| 3 | AGENT-BRIEF 含测试隔离 + 诊断三步法 | ✅ 新增 §3.1/3.2/3.3 三节 |
| 4 | verify 命令 exit 0 | ✅ make log-rotate --dry-run 通过 |

全过, 置 done。

## Q3 计划与事实的偏差

1. **原设计「verify 对比当前 diff vs claim 时基线」在实现时进化为「claim 时记 HEAD commit」** —
   比「claim 时 diff 快照」更稳 (commit 不可变, 快照会被后续操作污染)。
2. **diff_baseline 首版有两个坑, 都在 CI 被抓**:
   - 子模块脏状态误判漂移 (test_verify_blocks_required_claim_tier 挂) → 加 --ignore-submodules
   - .omo/state/ 运行时噪音 (daemon as_of 时间戳) 未过滤 → 加 noise_prefixes
   讽刺的是: 修 bug 过程恰好撞上自己刚写进 AGENT-BRIEF 的测试隔离规则——制度生效前先打了自己脸。
3. **god-module 存量债意外挡路**: 4 文件 >1500L (blueprint_control 2950L 等) 是先于
   检查引入的存量, 我的 PR 触碰 omo 指针才引爆 CI。处置: GOD_MODULE_ALLOWLIST 登记
   4 文件放行 (存量不挡新交付, ADR-0155 先例), 拆解仍归 BET-Y1Q2-T6-10。

## Q4 表面积影响

+127 行 (lifecycle +86/diagnostics +18/log-rotate +12/AGENT-BRIEF +11)。
换四类失败模式的制度化拦截, ROI 为正。god-module allowlist 是登记不是新增代码。

## Q5 给下一个 agent 的建议

1. **D2 启动条件已满足一半**: T9-01 verify-diff 部分 merge ✅, 剩 T1-05A done (08-21 窗口)。
2. **diff_baseline 的 noise_prefixes 需随运行时面扩展维护** — 新增 daemon 写面时要记得补前缀。
3. **GOD_MODULE_ALLOWLIST 的 4 文件拆到 <=1500L 后必须删条目** (见 omo_lint.py 注释)。
4. E741 (l 变量名) 被 ruff regression gate 抓——新代码别用单字母循环变量。
