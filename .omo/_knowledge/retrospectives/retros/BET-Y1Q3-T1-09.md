---
title: "BET-Y1Q3-T1-09 retro — D4 escape-hatch solidification"
status: archived
bet: BET-Y1Q3-T1-09
date: 2026-08-21
last_updated: 2026-08-25
lifecycle: history
owner: unassigned
type: retro
---

# BET-Y1Q3-T1-09 复盘

## 北极星

逃逸不再是无限复用的万能票：每次 skip 留下 fingerprint；agent 不能再用人类紧急 ID 跳新失败；预存债有登记处。

## 做了什么

- 权限类拆分 + 旧 id alias 至 2026-08-28
- observe-then-skip（pre-push / swarm-git 先跑 ci-local-fast）
- `requires_human` 在 AGENT_ID 路径 fail-closed
- `escape-digest.py --dry-run` 聚类 66 条历史记录（44 worktree / 22 hotfix），不改白名单
- skip policy `mode: shadow`；人类口立即硬拒

## 没做什么

- 不翻 shadow→fail
- 不接线 GitHub
- 不扩 INIT_ALL
- 台账 `docs/plans/3y-bet-ledger.yaml` 与另一 run 撞 claim，BET 条目在工作树，提交时若锁仍在则下一刀补合

## 教训

台账 66 条全部 `ci_local_skip` 且 reason 抄自白名单，所以无法下沉。传感器必须记录失败身份，否则二阶回路是空的。

## Follow-through (2026-08-22)

- 过期 alias 拒绝理由点名 `partial-worktree` / `local-preflight-preexisting`
- `make escape-digest` + hygiene-patrol 第 7 柱跑 `escape-digest.py --dry-run`（不改白名单、不从无 fingerprint 的历史 66 条编造 known-debt）
- `escape-token-issue` 与 `escape-digest.py --dry-run` 写入 AGENTS.md 与 git-discipline
