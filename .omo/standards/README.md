---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# .omo Standards Registry

> `.omo/standards/` 的入口注册表。
> 当前只将 **跨阶段、持续生效、会被 workflow 直接引用** 的文档视为 active standards。

---

## Active standards

| 文件 | 角色 |
|------|------|
| `adr-process.md` | ADR 流程标准 (MADR 模板 + 生命周期 + 验证工具) |
| `agent-workflow-contract.md` | 可执行 agent 工作流契约 |
| `agent-cli-worker-collaboration.md` | 外部 worker 协作、dispatch、reclaim、handoff |
| `agent-mutation-protocol.md` | agent 变更协议 (advisory lock + AppendOnlyLog) |
| `agent-registry-heartbeat.md` | registry heartbeat / liveness 契约 |
| `article-ingestion-policy.md` | 文章摄入准入策略 |
| `auto-generated-artifacts.md` | 自动生成产物的治理规则 |
| `capability-binding-policy.md` | 场景-能力绑定策略 |
| `capability-metamodel.md` | 能力元模型 |
| `debt-gate-level-enum.md` | 债务 gate_level 枚举 SSOT |
| `doc-presentation-pattern.md` | 文档呈现模式 (digest + pointer + lint) |
| `doc-ssot-contract.md` | 文档 SSOT 正交契约 |
| `health-metrics-semantics.md` | 健康指标语义 |
| `interface_contract.md` | L0/L3 接口契约 (TaskObject, AgentMessage) |
| `kos-baseline-drift-monitor.md` | KOS baseline 监控 |
| `mcp-tool-and-transport-standard.md` | MCP 工具返回契约 + 传输约束 |
| `mutation-proposal-envelope.md` | 变更提案信封 |
| `omo-governance-surfaces.md` | 三层治理契约 (.omo / projects/omo / projects/c2g) |
| `omo-submodule-split-validation.md` | omo 拆分验证清单 |
| `operation-levels.md` | L0-L3 操作分级定义 |
| `opc-review-template.md` | OPC 审查模板 (8 段硬结构) |
| `phase2-full-execution-go-no-go.md` | phase 2 执行门禁标准 |
| `PITCH-TEMPLATE-C2G.md` | C2G 战略 Pitch 模板 |
| `planning-blueprint-delivery-test-standard.md` | 规划 / 交付 / 测试统一标准 |
| `ssot-7-domain-schema.md` | SSOT 7 域 schema 规范 |
| `ssot-guardian.md` | SSOT drift guardian 机制 |
| `submodule-inclusion-policy.md` | 子模块纳入策略 |
| `task-gate-model.md` | 任务门模型 |
| `task-yaml-rules.md` | 任务 YAML 规则 |
| `x1-swarm-trust-protocol.md` | X1 蜂群信任协议 |
| `x2-budget-integrity-standard.md` | X2 预算完整性标准 |
| `x2-rule-template-standard.md` | X2 新鲜度规则模板 |
| `x3-value-stack-standard.md` | X3 价值栈与成本归因标准 |
| `x4-hitl-mutation-standard.md` | X4 HITL 变更生命周期 |

## Archived (moved to .omo/_archive/standards/)

| 文件 | 原状态 | 归档原因 |
|------|--------|----------|
| `ARCHITECTURE_CONVERGENCE.md` | stale | v5→v6 迁移分析, 一次性报告 |
| `C2G-Decoupling-Audit.md` | stale | 一次性审计, 非持续生效 |
| `hardcoded-paths-inventory.md` | completed | 已完成, 所有路径已修复 |
| `post-phase1-governance-and-phase2-entry.md` | historical | Phase 1 关闭 gate snapshot |
| `eCOS-v6-Architecture-Alignment.md` | stale | v5→v6 对齐白皮书, 迁移已完成 |
| `GRAND-UNIFIED-PIPELINE.md` | deprecated | 被 DOC-LIFECYCLE.md 取代 |
| `pipeline-json-v1.1.md` | deprecated | 被 DOC-LIFECYCLE.md 取代 |
| `dependency-baseline.md` | deprecated | 被 DOC-LIFECYCLE.md 取代 |
| `x3-metaos-admission-rules.md` | deprecated | 被 DOC-LIFECYCLE.md 取代 |
| `MCP_STANDARDS.md` | merged | 合并到 mcp-tool-and-transport-standard.md |
| `mcp-transport.md` | merged | 合并到 mcp-tool-and-transport-standard.md |
| `operation-level-rollout-plan.md` | merged | 合并到 operation-levels.md |

## Usage rules

1. `tasks/README.md` 与 `plans/README.md` 只能引用 active standards。
2. archived 文档可作为历史证据, 不再作为执行入口。
3. 若新增 standard，必须同时更新本注册表与 `.omo/INDEX.md`。
4. X1-X4 规则真相源位于 `../_truth/x1-*.yaml` ~ `x4-*.yaml`；`standards/` 只定义解释性标准，不再复制治理规则正文。
