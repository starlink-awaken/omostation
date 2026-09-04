---
id: ADR-0370
title: AGT × eCOS v6 Integration via BOS URI External Adapter Pattern
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-04
note: "Reissues the AGT × eCOS v6 contract under a fresh id (replaces the placeholder that collided with ADR-0366); see ADR-0366 for the Pyright sweep algorithm."
---

# ADR-0370: AGT × eCOS v6 Integration via BOS URI External Adapter Pattern

## Status

Accepted
Implemented in PR #931, #934
Date: 2026-08-04

## Context

eCOS v6 需要集成 Agent Governance Toolkit (AGT) 作为外部治理适配器，提供：
- 策略评估与合规检查 (policy engine)
- 信任评分与身份验证 (trust scoring)
- 沙箱隔离与权限控制 (sandbox isolation)
- SRE 监控与健康检查 (SRE monitoring)
- MCP 安全审计 (MCP security)
- 能力市场与发现 (marketplace)
- Lightning 快速通道 (lightning cache)
- Hypervisor 审计哈希链 (audit hashchain)

AGENT 是 PyPI 包 (`pip install agent-governance-toolkit[full]`)，不在 eCOS monorepo 内，必须通过外部适配器模式集成。

## Decision

采用 **BOS URI External Adapter Pattern**，具体映射：

| eCOS 层 | AGT 映射 | 实现 |
|---------|---------|------|
| M1 Component | 8 个 `COMP-EXT-AGT-*.yaml` | `projects/ecos/src/ecos/ssot/mof/m1/component/` |
| M1 BOSRoute | 8 个 `BOSROUTE-AGT-*.yaml` | `projects/ecos/src/ecos/ssot/mof/m1/bosroute/` |
| I0 Service | 8 个 stdio transport 服务 | `projects/agora/etc/bos-services.yaml` |
| L0 Constraint | `CR-AGT-ASI-01` ~ `CR-AGT-ASI-10` | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml::agt_constraints` |
| X1 Policy | `X1-AGT-AUDIT-HASHCHAIN-202608` | `.omo/_truth/x1-governance-policies.yaml` |
| X3 Domain | `AGT` trust scoring domain | `.omo/_truth/x3-value-stack.yaml` |
| L1 Hook | `--agt-backend` flag | `bin/gac/gac-local-gate.py::run_agt_policy_engine()` |

### 核心约束

1. **Namespace 隔离**：所有 AGT 组件命名空间为 `agt`，避免与现有 `agentmesh` 概念冲突
2. **状态机合规**：M1 Component `status` 必须使用 M2 允许值 (`active/degraded/stopped/archived`)，禁止 `proposal_only`
3. **L0 结构**：AGT 约束存储在 `agt_constraints` 顶层键下，而非裸列表项
4. **Agora CLI fallback**：`run_agt_policy_engine()` 在 `FileNotFoundError` 时返回 `FAIL` 而非崩溃，确保无 Agora 环境仍可运行 gate
5. **block-write 策略**：CR-AGT-ASI-01/02/03/08/10 使用 `block-write` enforcement，与现有 X1 策略同级

## Consequences

### Positive
- AGT 作为一等公民集成到 eCOS 治理体系
- 11 项自动化测试覆盖所有注册点
- 运行时 fallback 保证无 Agora 环境不阻断 CI
- AGT trust score 0-1000 映射到 eCOS 5 级信任维度

### Negative
- `run_agt_policy_engine()` 当前在无 Agora 环境 always `FAIL`，会污染 gate 输出（需 --strict 或 --verbose 区分）
- X1 block-write 策略 scope 与现有策略有潜在重叠（`.omo/_truth/`、`bin/`），需运行时验证无冲突
- bos-services.yaml 修改在子模块内，主 PR 无法直接包含

### Risks
- Agora CLI 未安装时，`--agt-backend` 模式持续报 FAIL
- AGT 策略评估成本设为 0.0，实际生产环境可能有延迟
- `agt-integration.yaml` 仅定义配置，无运行时验证逻辑

## Follow-up

1. **P1**: 在 staging 环境验证 Agora CLI 可用性后，将 `run_agt_policy_engine()` 的 `FAIL` 降级为 `WARN`
2. **P2**: 将 `agt-policy-engine` 接入现有监控 dashboard，跟踪成功率
3. **P3**: 安全团队 review CR-AGT-ASI-01~10，确认 `block-write` 级别与组织策略一致
