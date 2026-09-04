---
title: "RCA：Governance Runtime Convergence（2026-08-14）"
status: archived
lifecycle: history
owner: governance-team
last_updated: 2026-08-15
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# 复盘（RCA）：Governance Runtime Convergence（2026-08-14）

## 结论
任务目标已闭环：PR 已合并到主线，主工作树清理完成，交付链路可继续执行后续任务。

## 1. 触发事实
- 合并提交：`1f4b56af167d53698425ff6aa49f641e176e1646`（PR #1472）
- 合并后，在主 worktree 检测到以下本地脏文件：
  - `.omo/_truth/registry/memory-os.yaml`
  - `.omo/state/a2a-messages.jsonl`
  - `.omo/state/agent-tick-daemon.jsonl`
  - `projects/omo/uv.lock`

## 2. 问题描述
在 PR 交付收口前后的“状态一致性确认”阶段，主仓与子仓出现了非计划改动，使得工作树状态与交付状态不清晰，可能影响下一步任务的起点确定。

## 3. 根因分析（问题-成因）
- 问题：状态文件和子仓依赖文件在工作区被改写后未及时回退。
- 成因：多次上下文切换和交付步骤后，未做一条固定的“收尾清理闭环”（checkout/reconcile）。
- 放大因素：
  - 同时存在隔离 worktree 与共享 worktree，导致认知上存在分支/路径焦虑；
  - 缺少统一执行的收尾命令清单（尤其含子仓状态文件）。

## 4. 影响评估
- 直接影响：主仓显示“dirty”，降低后续变更可追溯性。
- 间接影响：人为判断“是否已完成 closeout”存在误差风险，但未对已合并代码功能产生回归。

## 5. 修复与收口措施
1) 回退脏文件（主仓）
- `git checkout -- .omo/_truth/registry/memory-os.yaml .omo/state/a2a-messages.jsonl .omo/state/agent-tick-daemon.jsonl`
2) 回退子仓脏文件
- `git -C projects/omo checkout -- uv.lock`
3) 状态核验
- `git status --short`
- `git submodule status projects/omo`

## 6. 改进措施（防复发）
- 每次功能/交付收口增加固定复核清单：`status` + `submodule status` + 对已知状态文件回滚。
- 对有 PR 合并或 closeout 的任务，优先产出 1 页复盘文档（RCA）并入 `docs/notes`。
- 下一轮任务前先在同一主入口执行 “收口状态确认” 再开始新改动。

## 7. 证据文件
- 合并后 closeout 记录：[governance-runtime-convergence-closeout-20260814](./governance-runtime-convergence-closeout-20260814.md)
- 本次 RCA：[governance-runtime-convergence-rca-20260814](./governance-runtime-convergence-rca-20260814.md)
