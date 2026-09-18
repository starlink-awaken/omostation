---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-09-18
type: ssot
---

# Capability registry

> Status: active
> Owner: governance
> Runtime path: `.omo/capabilities/`
> Legacy compatibility: `.omo/registry/` is retained only for historical evidence lookup

## Files

| File | Purpose |
|------|---------|
| `.omo/capabilities/projects-capabilities.yaml` | Core workspace capability records |
| `.omo/capabilities/sharedwork-sample.yaml` | External/SharedWork sample records for Phase 14 triage |
| `.omo/capabilities/system-packages.yaml` | Package baseline records (merged package-baseline.yaml) |
| `.omo/capabilities/agent-clis.yaml` | Agent CLI baseline |
| `pilot-contract.yaml` | Selected Phase 12 pilot interface contract |
| `article-samples.yaml` | Article ingestion policy samples |
| `omo-governance-surfaces.yaml` | `.omo` 顶层资产分类 + `projects/omo`/`projects/c2g` 联动治理注册表 |
| `mutation-surfaces.yaml` | Brokered write entry points (CLI entrypoints → mutation targets) |
| `internal-write-profiles.yaml` | Worker/dispatch internal write paths (runtime writes) |
| `direct-io-baseline.yaml` | Grandfathered direct I/O baseline (policy: must stay empty) |
| `governance-checks.yaml` | GaC declarative rule registry (ADR-0106) + X1-X4 checker classes |
| `document-governance.yaml` | Document ownership, lifecycle, freshness, and discoverability policy |
| `governance-alerts.yaml` | X1-X4 alert rules when checks fail |
| `governance-evolution-roadmap.yaml` | Systemic governance evolution roadmap, capability traces, and golden path contracts |
| `task-policies.yaml` | Task YAML field validators (red-line policies) |
| `debt.yaml` | Tech debt item catalog + dashboard/report refs |
| `dependency-baseline.yaml` | Workspace-wide min version constraints |
| `mof-capabilities.yaml` | 4-layer MOF tool registry |
| `workers.yaml` | Worker role/lease/transport policy |
| `external-connection-fabric.yaml` | External knowledge/data/resource/method/tool/channel/model descriptor and lifecycle SSOT |
| `documents-domain-projects.yaml` | Documents 知识域的 Cowork 客户端、Workspace MCP、Skill/Workflow 与只读 Runtime owner-job 路由绑定；域身份仍由 L4 manifest registry 拥有 |
| `documents-content-plane-migrations.yaml` | Documents runtime/cache 迁移族、目标 owner、消费者、回滚与确认门；只读 checker 保证候选恰好归属一个族 |
| `agent-workflows` | Executable workflow and diff-check registry, including current-state coherence coverage |
| `compute/engines.yaml` | LLM runtime engine + scheduling endpoints |
| `compute/nodes.yaml` | Physical compute nodes |
| `action-permission-matrix.yaml` | 三级权限名单 — autoloop 自主执行的安全边界 (ADR-0402) |
| `agent-workflows.yaml` | Agent workflow 兼容投影 (只读生成物，非 SSOT) |
| `agents/` | Agent 注册表目录 (governor 等) |
| `alert-channels.yaml` | 告警通知渠道注册表 (channel kind) |
| `architecture-perception-registry.yaml` | Architecture Perception Registry |
| `autonomy-metrics.yaml` | 自主度评估 5 维度指标定义 (ADR-0403 P3) |
| `branch-prefix-policy.yaml` | 分支前缀策略 SSOT — 命名/生命周期/门禁统一注册表 |
| `capability-providers.yaml` | Agent CLI/provider 静态声明 (运行时可用性只做观测，不做准入) |
| `ci-surfaces.yaml` | CI 平面检查接线 (SSOT ref CR-CI-SURFACE-SSOT) |
| `connector-manifest.yaml` | 外部数据源连接器元数据登记 (类型/传输/认证/增量同步/BOS 路由) |
| `document-warning-baseline.yaml` | 文档告警签名基线 (sha256 rule/path/evidence) |
| `documents-scene-mof-map.yaml` | Documents Scene ↔ MOF Mapping Registry |
| `drift-log.yaml` | Drift Log Registry — 架构漂移记录 |
| `external-channels.yaml` | External Channels Inventory SSOT (ECCP P0) |
| `gate-known-debt.yaml` | Skip-layer known-debt (ADR-0422) |
| `gatekeeper-grace.yaml` | contract_gatekeeper 存量豁免清单 (修复后移除) |
| `harness-policy.yaml` | Harness Controller Policy Registry — 收束所有治理的唯一运行时 |
| `hook-manifest.yaml` | Git hooks 清单注册表 |
| `memory-os.yaml` | Memory OS 控制面索引 (ADR-0372) |
| `memory-rbac.yaml` | Memory OS RBAC policy table (ADR-0372 Phase 6) |
| `mof-m2-extensions/` | MOF M2 扩展模型目录 (capability_provider/digital_agent/swarm 等) |
| `notification-config.yaml` | HITL Proposal 通知配置 (BET-Y1Q4-HITL-02) |
| `observability-events.yaml` | 统一事件面注册表 (Unified Event Surface Registry) |
| `phase-escapes/` | Phase 逃逸说明目录 |
| `phase-scope.yaml` | Phase scope registry — 路径与阶段解锁映射 (ADR-0223) |
| `phase-verdict.yaml` | Phase unlock verdict SSOT |
| `predictive-governance.yaml` | Predictive Governance Registry |
| `probe-heartbeat-matrix.yaml` | 探测器心跳矩阵 — 心跳 SLA 定义 |
| `redlines.yaml` | Redline registry (STRAT-P85 G2.1) |
| `ruff-diagnostics-baseline.yaml` | Ruff blocking regression baseline (ADR-0407) |
| `rule-gate-mapping.yaml` | 门禁到治理规则映射 (gate → rules) |
| `runtime-projections.yaml` | Runtime Projection Registry |
| `scene-cards-v3.yaml` | Scene 卡注册表投影 (生成物) |
| `services.yaml` | 常驻服务注册表 (scheduler services) |
| `signal-sources.yaml` | 外部信号源注册表 (感知面信号源) |
| `spine-gateway-policy.yaml` | 外发频次硬熔断策略 (circuit_breaker) |
| `subtraction-quota.yaml` | 减法配额 (Subtraction Quota) |
| `swarm-coordination.yaml` | Swarm 协同 SSOT (G-CONV.7 / ADR-0220) |
| `trend-fusion.yaml` | Cross-Domain Trend Fusion Registry |
| `write-owners.yaml` | `.omo/` 状态平面写权限定义 (GaC #38) |
| `x3-delivery-soft-gate.yaml` | X3 交付软门禁 (deprecated，被 BET-Y1Q1-T1-01 取代) |
| `x3-role-metrics.yaml` | X3 role metrics projection |

## Write Surface Registries Boundary

Three registries describe write paths from different angles:

| Registry | View | When to update |
|----------|------|----------------|
| `omo-governance-surfaces.yaml` | Architectural/top-down: which planes/assets exist and who may write them | New asset or plane added |
| `mutation-surfaces.yaml` | Operational/bottom-up: which CLI entrypoints perform brokered writes | New broker write command added |
| `internal-write-profiles.yaml` | Runtime/worker: which worker-internal paths are permitted | New worker write path added |

## Rule

Registry records are evidence for discovery and binding. They do not authorize live mutation or external installation.
