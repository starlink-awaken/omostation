---
title: BET-Y1Q2-T1-19 retro — Codex ACP stdio permission-broker 切割
type: retro
status: active
owner: engineering-agent
created: 2026-08-20
bet: BET-Y1Q2-T1-19
lifecycle: history
last-reviewed: 2026-08-20
---

# BET-Y1Q2-T1-19 复盘（五问）

## Q1 实际耗时 vs appetite?
- **appetite**: 1 day
- **实际**: 30 minutes
- **比例**: 顺利完成 workers.yaml 与 omo transport 切换。

## Q2 done_when 是否全部通过?
- [x] `workers.yaml` 默认 transport 设定为 `[acp_stdio, cli_prompt]`
- [x] omo ACP stdio 管道就绪并合并至主干
- [x] `cli_prompt` 安全退役，降级通道保留

## Q3 过程中发现的与 plan 不符的事实
- ACP stdio 在单机进程隔离下大幅减少了终端文本污染与权限逃逸风险。
