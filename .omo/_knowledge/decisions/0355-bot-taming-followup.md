---
title: Bot 撞车治理 follow-up (governance-verify 真测试 + 外部 agent swarm 感知 + claim TTL GC)
status: deferred
type: decision
scope: gac-worktree cleanup / submodule-freshness-gatekeeper / swarm discipline / 外部 agent loop
date: 2026-08-03
related:
  - PR #877 (cleanup 查 claim + 回收 release + 孤儿报告)
  - PR starlink-awaken/omostation-agora#14 (agora 两线合璧)
  - ADR-0220 (swarm discipline G-CONV.7)
  - ADR-0349 (PASW 子模块隔离)
---

# ADR-0355: Bot 撞车治理 follow-up

## 背景

`starlink-awaken` bot (eCOS 自动驾驶主力, 676 commit/7天, 100% 占比) 高频推进 fabric/PASW/ADR 时, 撞手动操作的 3 个根因:

1. **PASW cleanup 不查 swarm D2 claim** → 清了手动 claim 的 worktree (老王撞车, bump commit 丢)
2. **claim 堆积** → 195 个孤儿 claim 堵 D2 lock (worktree 清了 claim 没 release)
3. **gatekeeper 盲目 bump origin/main tip** → bump 线B (b2f8fcb) 断裂 cockpit 线A 依赖

## 已交付 (2026-08-03)

| 调教 | 交付 |
|---|---|
| #1 cleanup 查 swarm claim | gac-worktree-cleanup.sh 回收前查 D2 claim, 有活跃 claim 跳过 |
| #2a 回收时 release claim | cleanup 回收 worktree 顺带 release 对应 claim |
| #2b 孤儿 claim 报告 | cleanup 结尾报告孤儿数 (不自动清) |
| #2 存量 GC | 195 孤儿 claim 现场清零 (runtime, load_branch_claims + release_branch_lock) |

## Deferred follow-up (本 ADR 记债, 不提前实施 YAGNI)

### F1: governance-verify 真测试取代占位 (gatekeeper #3)

`submodule-freshness-gatekeeper.yml` 的 governance-verify 步骤注释 "暂时允许通过, 后续由真实的单测取代" — 占位不跑测试, 导致 bump 后不查下游 import 断裂.

- **触发**: 高耦合 submodule (agora/cockpit) 再因分叉 bump 断裂下游
- **实施**: governance-verify 换真跨 submodule 测试, 或轻量 import 抽查 (cockpit 依赖的 agora 关键符号如 `_resolve_with_router`)
- **根本解**: 保证 submodule main 不分叉 (PR agora#14 模式), 本 follow-up 是补充防御

### F2: 外部 agent loop 跑前查 swarm claim/window (#4)

starlink-awaken 外部 agent loop (高频直接 push, 非 Actions cron) 跑前不查 swarm 活跃 claim, 撞手动操作 (主 worktree 并发 dirty + UU).

- **触发**: 外部 agent 撞手动操作频繁
- **实施**: 外部 agent loop 跑前调 `swarm-discipline-cli.py` 查活跃 claim + window-status, 有手动操作时避让. 代码不在本仓 (外部 agent), 用现有 `swarm window-start` 机制协调

### F3: claim TTL GC (自动清老孤儿)

#2b 只报告孤儿不自动清 (防误清活跃), 但孤儿会堆积 (本次 195).

- **触发**: 孤儿 claim 堆积影响 D2 lock (新 claim 分支名冲突)
- **实施**: cleanup 或专用 gc 命令, claim 文件 mtime > N 天 + 无 worktree → 自动 release. 注意 mtime 可能被 git restore 重置 (本次 195 孤儿 mtime 全 <1d), 须结合 worktree 存在性判断

## 决策

**记债 deferred, 不提前实施 (YAGNI)**. PR #877 + PR agora#14 merge 后本次撞车坑全根治. F1/F2/F3 在各自触发条件满足时再补, 避免过度工程.

## 关联

- PR #877: cleanup 调教 (#1+#2, 本仓)
- PR starlink-awaken/omostation-agora#14: agora 两线合璧 (根因解)
- ADR-0220: swarm discipline (G-CONV.7 / D1-D4 gates)
- ADR-0349: PASW 子模块隔离
