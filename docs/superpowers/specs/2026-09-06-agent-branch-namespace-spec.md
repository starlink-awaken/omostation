---
schema_version: specification/v1
spec_version: 1.0.0
title: 并发 Agent 分支命名空间隔离 — agent/{actor}/{session} 三段式
bet_id: BET-Y1Q4-T10-128
status: accepted
lifecycle: contract
last-reviewed: 2026-09-06
type: plan
owner: governance-team
last_updated: 2026-09-06
---

# Agent 分支命名空间规格 (BET-Y1Q4-T10-128)

## 决策

- **格式**: `agent/{actor_id}/{session}` 三段式 (`/` 分隔, BET done_when 原文口径), 弃用 `--` 双段式 (存量 0, 不留兼容层)
- **actor_id 回退链**: `--actor` 参数 > `$OMO_ACTOR` env > `governance-agent`
- **语义变更**: agent/ 前缀从 clone-lifecycle 专用改为 worktree-claim 专用 (拓扑回滚: 独立 clone 未消除竞争, PITFALL-COO-003 计数 5)

## 变更面

1. branch-prefix-policy.yaml: naming.agent 正则 + prefixes.agent (ttl 7d/creators/description)
2. gac-worktree.sh: claim 分支名 agent/{actor}/{session} + actor 解析 + 残留阻断 (circuit_breaker)
3. gac-branch-prune.sh: agent/ 段 TTL 清理 (读 policy ttl, 不硬编码) + cron 接线
4. swarm-coordination.yaml: d2 retired → conditional_active
5. swarm-discipline-cli.py branch-check: 恢复 occupancy (仅 agent/ 前缀; work/ 跳过)

## 验收

- BET verify 两条 (claim grep agent/ + check-branch-naming agent/{actor}/{session})
- D2: 同 actor 同 session 重复 claim 阻断; work/ 跳过
- 清理器: 8 天假分支消失, 新鲜分支保留
