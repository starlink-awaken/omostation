---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Self-Healing Drifts Foundation — L2.5 layer introduction
bet_id: BET-Y2Q4-SH-1
---


# BET-Y2Q4-SH-1 — Self-Healing Drifts Foundation

## Context

`#4310 docs(diagnostic)` 报告了 31 个 drift 发现，按机制归为 5 类（M1-M5）。其中 M1（写后忘）和 M5（ritual 未运营）源自同一个根因 R1——**系统缺乏"持续守护"机制**。当前治理动作（cron 跑、信号刷新、ritual 触发、产物归档）依赖**人记得**或**单次 commit 触发**。一旦间隔超 7-30 天，必然漂移。

诊断证据：
- `debt-dashboard/current.yaml` 9 天未更新（state-freshness FAIL）
- `runtime/dashboard/agent-brief.json` 22.3 小时未刷新
- `.omo/state/heartbeats/weekly-review.json` 32 天未跑
- `.omo/_delivery/agent-workflows/runs/` 有 2 个 stale active run

PR #4128 (a02f54d30) "真复核 26 篇过期 SSOT" 修了 4 篇 + 登记 1 债；4 天后 11 篇又过期。**修一类 drift 不能解决反复发作**——必须建立自动守护层。

## Goal

在 L2 (内核) 和 L1 (运行时) 之间引入 **L2.5 Self-Healing Layer**，提供 5 个原子能力：

1. `drift-face-detector` — 检测 5 类 drift（dashboard / brief / ephemeral / runs / ritual）
2. `auto-pruner` — 自动 prune 过期产物 + 重生成 dashboard + 归档 ephemeral
3. cron 触发 — 每日 + 每周双 cadence 自动跑
4. `drift-face-clean` — 一键全跑入口（人手动 + CI 双重可调）
5. 报告输出 — drift matrix + auto-fix report 上报到 panorama health

## Non-goals

- **不改 SSOT 文档** — 仅 prune/regenerate 状态/产物类，不动 `.omo/standards/` `.omo/_truth/`
- **不直接 push PR** — auto-fix 仅本地修复；gitlink bump / frontmatter patch 类必须经 PR review
- **不替 owner 决策** — 真 zombie / ritual 跳过等需要 owner 决策的，仍旧走决策路径
- **不取代 P74** — 本 BET 与 P74 互补；P74 检 workflow 沉默，本 BET 检 signal 过期

## Done when

- `bin/ssot/drift-face-detector.py` 存在且覆盖 5 类 drift（output: drift matrix JSON）
- `bin/ssot/auto-pruner.py` 存在且对 4 类可自动修（dashboard regen, brief refresh, runs prune, ephemeral archive）
- `.omo/cron/registry.yaml` 增加 2 条 cron entry（daily + weekly cadence）
- `make drift-face-clean` (Makefile 入口) 整合 detect + prune + report
- 单元测试覆盖 5 类 detect + 4 类 prune（fixture + 端到端）
- 接入 `make gac-local-gate` 后仍 PASS（不破坏现有 gate）
- 实证：跑 1 次后，#1/#15-#16/#24/#26 这 4 项 finding 应被自动修

## Verification

```bash
uv run --with pyyaml python bin/ssot/drift-face-detector.py --json
uv run --with pyyaml python bin/ssot/auto-pruner.py --dry-run --json
make drift-face-clean    # 实际跑
make gac-local-gate       # 不破坏
```

## 关联债务

- 完成后应能 close:
  - `DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP` (部分，本 BET 只修复 drift 复发机制，不修规则接线本身)
- 关联发现 (from #4310):
  - **#1** state-freshness FAIL (debt-dashboard 9d)
  - **#4** 13 ephemeral reports 应归档
  - **#15-#16** 2 stale active runs
  - **#24** brief 22.3h stale
  - **#26** weekly-review ritual 32d 断供

## Bootstrap authorization

- workflow: `project-doc-change` → `project-code-change`
- agent: governance-agent
- worktree: 必走 `bin/gac/gac-worktree.sh claim <session>`
- ADR-0203 流程: bootstrap → start --profile governance-agent --bet <BET-ID> → claim → work → closeout