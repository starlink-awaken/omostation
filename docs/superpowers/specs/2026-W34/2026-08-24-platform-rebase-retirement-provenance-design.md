---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
last_updated: 2026-08-24
bet_id: BET-Y1Q3-T1-11
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# platform-rebase 退役溯源收敛设计

## 目的

复盘后确认 current main 尚缺 `platform-rebase` 独立 clone 退役过程的 provenance 收敛。在并行化、多 agent 操作中，退役的 clone 在归档时必须保留完整的操作来源、决策路径以及交付结果溯源（provenance）。
该 spec 旨在为接下来的跟进（T1 follow-up，即 BET-Y1Q3-T1-11）提供指导性约束，禁止无 spec 实施。

## 方案约束

1. **Provenance 数据持久化**：
   在 `bin/gac/clone-lifecycle.py` 中，当 `retire` 动作触发时，必须将 clone 的生命周期元数据（如 agent-id, run-id, delivery-attempt, git-hash 等）完整 dump 到归档区（如 `runtime/retired-clones.jsonl`）。
2. **生命周期审计门禁**：
   `make gac-local-gate` 需检查独立 clone 目录是否发生未授权修改。如果发现 `actor_id` 越权操作其他人的 clone，必须抛出 Error。
3. **安全与防腐**：
   对于跨平台的 fallback 逻辑，只有当 `provenance` 指纹校验通过后，才允许进行资源回收（销毁 clone 或 worktree）。

## 交付产物

- 更新 `bin/gac/clone-lifecycle.py`
- 更新相关 SSOT 状态，支持 provenance ledgering
