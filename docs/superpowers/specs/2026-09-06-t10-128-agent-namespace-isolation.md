---
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q4-T10-128
created: 2026-09-06
status: active
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-06
---

# Spec: 并发 Agent 分支命名空间隔离

## Problem

多个并发 agent session 在 `gac-worktree.sh claim` 时共享 `work/` 前缀命名空间，容易产生分支名冲突。
当 agent 自动创建分支时，若多个 agent 同时 claim 类似 session 名称，可能导致分支覆盖或混淆。

## Goal

引入 `agent/{actor_id}/` 命名空间前缀，将 agent 自动创建的分支与人工 `work/` 分支物理隔离。

## Scope

### In Scope

1. **`bin/gac/gac-worktree.sh`** — claim 子命令强制使用 `agent/{actor_id}/` 前缀
   - 当调用方为 agent（通过环境变量 `AGENT_ACTOR_ID` 或 `--actor-id` 参数标识）时，分支前缀改为 `agent/{actor_id}/`
   - 当调用方为人类（无 actor-id 标识）时，保持现有 `work/` 前缀不变
   - 分支名格式: `agent/{actor_id}/{session-slug}`

2. **`bin/gac/swarm-discipline-cli.py`** — claim-gc 支持 agent 命名空间
   - 自动清理 `agent/` 前缀下 >7 天无活动的分支
   - 与现有 `work/` TTL 清理逻辑并行

3. **`.omo/_truth/registry/branch-prefix-policy.yaml`** — 补充 agent/ 命名空间策略
   - 添加 TTL 策略（7 天）
   - 添加 creator 标记

### Out of Scope

- 不修改已有 `work/` 前缀分支的行为
- 不修改已存在的 agent 分支
- 不重构现有 PASW 子模块隔离机制

## Done When

- `gac-worktree.sh claim bet-session-xxx --actor-id agent-xxx` 创建 `agent/agent-xxx/bet-session-xxx` 分支
- `gac-worktree.sh claim bet-session-xxx`（无 actor-id）保持创建 `work/bet-session-xxx` 分支
- `swarm-discipline-cli.py claim-gc --namespace agent --ttl-hours 168` 清理过期 agent 分支
- `branch-prefix-policy.yaml` 包含 agent/ TTL 策略

## Verify

```bash
# Test 1: agent claim creates agent/ prefixed branch
AGENT_ACTOR_ID=test-agent bash bin/gac/gac-worktree.sh claim test-ns-session 2>&1 | grep -q "agent/"
# Test 2: human claim keeps work/ prefix  
bash bin/gac/gac-worktree.sh claim test-human-session 2>&1 | grep -q "work/"
# Test 3: branch-prefix-policy has agent TTL
grep -q 'ttl_days' .omo/_truth/registry/branch-prefix-policy.yaml
```
