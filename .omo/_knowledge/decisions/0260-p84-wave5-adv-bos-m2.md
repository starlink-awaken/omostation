---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
id: ADR-0260
related: 
---


# ADR-0260: wave5 — ADV19/21/23 检测闭环 + 加硬 ADV25/27/29 + bos/m2 工具

## Decision

1. **能力轨闭环**: scenario_lib 实现 `byzantine_quorum_detected` /
   `replay_attack_detected` / `cross_key_collusion_detected`（ADV19/21/23）。
2. **对抗强度**: 新增 ADV25 split-brain / ADV27 identity-spoof /
   ADV29 supply-chain-tamper — 管线未实现 → 诚实 FAIL，守
   `check-adversarial-effectiveness`（全过=自欺）。
3. **bos-stdio**: `--migrate-candidates` 只读启发式排序（禁止标签假迁移）。
4. **MOF D3**: `m2-ssot-inventory --emit-batch N` 写出批迁移计划 YAML。

## Status

**ACCEPTED** 2026-07-29.
