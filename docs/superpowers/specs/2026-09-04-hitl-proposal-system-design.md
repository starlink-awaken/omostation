---
schema_version: specification/v1
spec_version: 1.0.0
title: HITL Proposal System — harness 层人类审批提案生成与 Cockpit 集成
bet_id: BET-Y1Q4-T8-04
status: accepted
lifecycle: contract
owner: omo-platform-team
created: 2026-09-04
last-reviewed: 2026-09-04
type: ssot
---

# HITL Proposal System

## Intent

开发 HITL (Human-in-the-Loop) 提案系统, 在 harness BET 执行过程中自动生成审批提案,
用户通过 Cockpit 审批, agent-workflow 等待审批结果后继续执行。

## 核心流程

```
harness run → stage_execute → 检测到 human_gate=true → 生成 HITL proposal
                                    ↓
                        存储到 .omo/_knowledge/hitl-proposals/<proposal_id>.yaml
                                    ↓
                        cockpit decide list → 用户审批
                                    ↓
                        agent-workflow 轮询 proposal 状态
                                    ↓
                        审批通过 → 继续执行 / 拒绝 → 中止或降级
```

## Contract

### 新增文件

- `bin/harness/hitl-proposal.py` — HITL proposal 生成器/管理器
- `tests/test_hitl_proposal.py` — 7 单元测试

### 修改文件

- `bin/agent-workflow.py` — stage_execute 集成 HITL proposal 等待逻辑
- `bin/cockpit` — `decide list` 显示 HITL proposals, `decide approve/reject` 更新状态

### Proposal 格式

```yaml
# .omo/_knowledge/hitl-proposals/<proposal_id>.yaml
schema_version: hitl-proposal/v1
proposal_id: hitl-<timestamp>-<random>
bet_id: BET-XXX
run_id: harness-XXX-<timestamp>
title: "Human approval required"
description: "..."
options:
  - id: approve
    label: "Approve"
    description: "Allow the action"
  - id: reject
    label: "Reject"
    description: "Deny the action"
status: pending  # pending | approved | rejected | expired
created_at: "2026-09-04T08:00:00Z"
expires_at: "2026-09-05T08:00:00Z"
responded_at: null
response_actor: null
response_option: null
```

## Non-goals

- 不替换现有 agent-workflow 的 claim/verify 流程
- 不改变现有 BET 状态机
- 不实现自动审批 (必须人工)

## Risks

- **R1 提案存储损坏**: 原子写入 (tempfile + rename)
- **R2 审批超时**: 24h TTL, 过期自动降级为 direct execution
- **R3 并发审批冲突**: 单写者租约 (file lock)

## Circuit Breaker

- 提案生成失败 → 降级为 direct execution (无 HITL)
- 审批超时 (24h) → 自动降级为 direct execution

## Verify

- `python3 bin/harness/hitl-proposal.py --help` → exit 0
- `python3 -m pytest tests/test_hitl_proposal.py -v` → 7/7 PASS
- `make gac-local-gate` → 全绿
- `cockpit decide list` → 显示 pending proposals
- `cockpit decide approve <proposal_id>` → 更新状态为 approved
- `cockpit decide reject <proposal_id>` → 更新状态为 rejected
