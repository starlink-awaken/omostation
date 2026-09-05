---
schema_version: specification/v1
spec_version: 1.0.0
title: HITL Proposal System v1.1 — Wait + Multi-channel
bet_id: BET-Y1Q4-HITL-02
status: accepted
lifecycle: spec
owner: omo-platform-team
created: 2026-09-04
last-reviewed: 2026-09-05
type: ssot
---

# HITL Proposal System v1.1 — Wait + Multi-channel

## Intent

基于 BET-Y1Q4-HITL-01 v1.0 实现的 producer-only 提案系统, 加入:

1. **真正的 wait 语义**: harness stage_execute 生成 proposal 后, 阻塞 poll 直到 proposal 被 approved/rejected/expired
2. **多渠道通知**: Slack/邮件通知 principal 有 pending proposal
3. **跨主机锁**: 把 fcntl 单机锁升级为 etcd/redis 分布式锁 (覆盖多节点场景)

## 核心变更

```python
# v1.1: harness stage_execute 后追加
def stage_execute(...):
    # ... existing appetite check + HITL proposal creation
    if proposal_id:
        # 阻塞等待, 默认 24h 超时
        final = wait_for_decision(proposal_id, poll_interval=10, timeout=86400)
        if final["status"] == "rejected":
            r["ok"] = False
            r["error"] = "Human rejected execution"
            return r
        if final["status"] == "expired":
            # Circuit breaker: 降级为 direct execution
            print("HITL proposal expired, proceeding with direct execution")
```

## Contract

### 新增文件

- `bin/hitl-proposal-notify.py` — Slack/邮件通知入口
- `bin/hitl-proposal-wait.py` — 阻塞等待 CLI (供 harness 调用)
- `tests/test_hitl_proposal_wait.py` — wait 行为测试

### 修改文件

- `bin/harness` — stage_execute 在创建 proposal 后 wait (optional, 由 policy flag 控制)
- `bin/hitl-proposal.py` — 增加 `--wait` flag 给 create 子命令

## Non-goals

- 不替换现有 claim/verify
- 不改变 BET 状态机
- 不实现自动审批
- 不引入数据库 (继续 file-based)

## Risks

- **R4 wait 阻塞时间过长**: harness 进程被占, agent 不能并行执行其他任务
- **R5 多渠道通知 spam**: 同一 proposal 重复通知

## Circuit Breaker

- wait 超时 → 自动 approve + 继续执行 (默认 24h, 可配置)
- 通知失败 → 静默, 不阻断 execution

## Verify

- `python3 bin/hitl-proposal-wait.py <proposal_id> --timeout 60` → 阻塞 60s 后 exit 1
- 多渠道通知测试: pending proposal 触发 Slack message
- 24h TTL 触发自动 approve

## 时间估计

3 days (v1.0 已经实现核心, v1.1 是集成 + 扩展)