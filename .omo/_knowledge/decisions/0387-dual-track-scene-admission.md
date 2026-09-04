---
id: ADR-0387
title: 双轨场景准入 — 内部 pipeline 场景的独立准入轨道
status: archived
type: decision
owner: architecture-governance
date: 2026-08-07
lifecycle: spec
last_updated: 2026-08-07
related:
  - 0297-external-connection-fabric-and-product-truth.md
  - 0326-external-activation-preflight.md
  - 0340-external-scene-trial-contract.md
---

# ADR-0385: 双轨场景准入 — 内部 pipeline 场景的独立准入轨道

## Context

external-connection-fabric (ADR-0297) 及其工具链 (external-activation-preflight, external-scene-trial) 为外部资源消费型场景 (如 document-review 消费 iris 邮件/OA 连接器) 设计了完整的准入流程。

engineering-delivery 是内部 pipeline 场景——它消费 CI 门禁 (make targets) 和 agent workflow 基础设施，不消费外部资源。当它走 external-scene-trial 准入时，preflight 如实报 `blocked`，因为 `required_capabilities` (gac-local-gate, agent-workflow-lifecycle) 不在 external resource catalog 中。

这不是 bug，是架构事实：用外部资源工具评估内部 pipeline 场景，capability 对不上是必然的。

## Decision

建立**双轨场景准入架构**：

| 轨道 | 适用场景 | 能力来源 | 权限模型 | 证据格式 | 持久化 |
|------|---------|---------|---------|---------|--------|
| External track | 外部资源消费 (document-review, agora-bos-gateway) | external resource catalog | vault 凭据引用 | catalog observation | external-scene-trials.jsonl |
| Internal track | 内部 pipeline (engineering-delivery) | make targets + project-registry | RBAC scope (permission://internal/) | git PR evidence + CI output | internal-scene-trials.jsonl |

两条轨道共享：
- Scene card 格式 (scene-card/v1)
- Scene card intake 验证 (scene-card-intake.py)
- Trial contract schema (metric, sample_plan, evidence_refs)
- Fabric 红线 (activation=forbidden until admitted, 不伪造)
- Append-only JSONL 持久化模式 (fcntl locked)

Scene card 通过 `scene_type` 字段声明类型，路由到对应轨道：
- `scene_type: external_resource` (或缺失) → external track
- `scene_type: internal_pipeline` → internal track

## Consequences

- **正面**: 内部 pipeline 场景不再被外部资源 catalog 的语义边界阻塞
- **正面**: 两条轨道各自验证与其场景类型相关的能力（SRP）
- **正面**: 共享格式和红线，不分裂治理体系
- **负面**: 两条 preflight + trial 工具链需要同步维护（DRY 风险）
- **缓解**: 远期 (Phase 3 vision) 可统一为可插拔 validator 框架

## Alternatives Considered

1. **扩展 external catalog 包含内部能力** — 语义污染。external catalog 是外部连接的 SSOT，混入内部 CI 基建能力会模糊边界。❌
2. **不建内部轨道, manual approval** — 不可审计。绕过工具链手工批准违背 fabric 治理原则。❌
3. **统一框架 (一步到位)** — YAGNI。当前只有 1 个 internal scene card (engineering-delivery)，建统一框架过度设计。等 3+ internal scenes 再做。❌
4. **当前方案: 独立工具链 + 共享格式** — KISS + SRP。每条轨道简单独立，共享 scene card 格式和红线原则。✅

## Implementation

- `bin/ssot/internal-scene-preflight.py` — 内部能力验证 (make target 匹配 + git evidence 验证 + RBAC 权限检查)
- `bin/ssot/internal-scene-trial.py` — proposal-only trial builder + `--record` 持久化
- `tests/unit/test_internal_scene_preflight.py` — 13 tests (all pass)
- PR #1091 (Phase 1 scene card) + PR #1095 (Phase 2 tooling)

## Follow-ups

- Phase 3 vision: 当出现第 3 个 internal pipeline scene card 时，重构为统一 `scene-admission` 框架 + 可插拔 validators (OCP)
- 考虑统一 JSONL log (scene-trials.jsonl + track field) 替代分离的 external/internal logs
