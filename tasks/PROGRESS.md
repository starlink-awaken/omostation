---
schema: md/v1
status: active
lifecycle: history
type: progress
owner: governance-team
last-reviewed: 2026-11-27
bet_id: BET-Y2Q4-T10-279
title: compute-i9-01 接入进度指针
---

# compute-i9-01 接入进度

> 本文件只做**阶段指针**，不复制事实内容。硬件、网络、控制面的读数一律以 Discovery 件为准；
> 阻断项与变更申请以 Phase 0/1 提案件为准。

| 阶段 | 状态 | 权威出处 |
|------|------|----------|
| Phase 0 Discovery（只读取证） | 完成 | `reports/COMPUTE-I9-01-INTEGRATION-DISCOVERY-20261029.md` |
| Phase 1 变更申请与人类授权 | **已授权（2026-11-25 逐条）** | `reports/COMPUTE-I9-01-PHASE0-PHASE1-20261029.md` §5 授权记录（CR-1 纳管 / CR-2 绑 ts / CR-3 / CR-5 授权执行） |
| CR-4 节点入登记面 | **已执行（2026-11-25）** | nodes.yaml + project-registry compute_nodes + workers.yaml declared 条目 |
| Phase 2 受限 Worker 接入 | **待物理开机**（2026-11-28 三路 WoL 均未唤醒，lab 网段 ARP `FAILED`） | `reports/COMPUTE-I9-01-PHASE0-PHASE1-20261029.md` §6（可达性回读 + 唤醒尝试 + 解锁动作）；节点恢复后按 §5 前置顺序执行 CR-1/2/3/5 远端腿 |
| Phase 3 八项回执 + Golden Slice 人工验收 | 未开始 | 前置：Phase 2 完成 + 闸 2 人工验收 |

## 两个 Agent 不可自证的门槛

1. **人类部署授权**：rootless 迁移、`8080` 暴露面收紧、`lb-worker` 处置、节点登记，均需逐项授权，不得代签。
2. **人工 Golden Slice 验收**：规格明文「Agent 自报成功不等于 `WorkflowVerified`」，故本 BET 不由 Agent 置 `done`。

## 台账位置

`docs/plans/3y-bet-ledger.yaml` · `BET-Y2Q4-T10-279`：`status: in_progress`，
`overall_state: evaluating`，`engineering: NOT_STARTED`。
