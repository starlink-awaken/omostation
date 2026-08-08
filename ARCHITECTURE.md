# ARCHITECTURE.md — eCOS v6 Architecture Contracts

> This document owns stable architecture concepts: layers, dependency direction, routing contracts, and governance boundaries.
> It does not own runtime facts, current phase, health score, test counts, tool counts, service counts, or ports.

## 0. Workspace Tools Layer (L2) — 统一工具链

> 2026-08-06 新增。将域级重复工具抽象为 workspace 级共享能力。

### 0.1 目录结构

```
workspace/tools/
├── __init__.py              # 统一导出
├── base/                    # 抽象基类
│   ├── __init__.py          # BaseController, BaseExtractor, BasePredictor
│   ├── base_controller.py   # 统一控制器（信号扫描、状态聚合、健康检查）
│   ├── base_extractor.py    # 统一提取器（实体识别、关系抽取、知识分类）
│   └── base_predictor.py    # 统一预测器（趋势预测、风险预警、过期检测）
├── kems/                    # KEMS 知识工程引擎
│   ├── __init__.py
│   └── kems_engine.py       # 知识提取 + 融合 + 图谱
├── ocr/                     # OCR 流水线（预留）
├── runtime/                 # 运行时脚本（预留）
└── domain/                  # 域插件
    ├── __init__.py          # DomainRegistry
    ├── domain_registry.py   # 域注册中心
    ├── health_commission.py # 卫健委域插件
    └── contract_law.py      # 合同法规域插件
```

### 0.2 设计原则

1. **基类抽象通用能力** — 三域控制器 80% 重复代码消除
2. **域插件实现差异** — 每个域继承基类，仅实现域特有逻辑
3. **BOS URI 注册** — 域服务可注册为 `bos://analysis/<domain>/<service>/`
4. **CLI 统一入口** — `python omostation.py <command>` 操作全域

### 0.3 调用链

```
CLI (omostation.py)
  → DomainRegistry.discover() — 发现域
  → BaseController.health_check() — 健康检查
  → BaseExtractor.extract_from_ocr() — OCR 知识提取
  → KEMEngine.run_full_pipeline() — 完整 KEMS 流水线
  → DomainPlugin.domain_specific_scan() — 域特有扫描
```

---

## 1. Source-Of-Truth Map

| Fact Type | Authoritative Source |
|-----------|----------------------|
| Runtime state, health, active tasks | [`.omo/state/system.yaml`](.omo/state/system.yaml) |
| Current goals | [`.omo/goals/current.yaml`](.omo/goals/current.yaml) |
| Project metadata | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| BOS services | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Ports | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| Vault paths (iCloud/local) | [`protocols/vault-paths.yaml`](protocols/vault-paths.yaml) |
| X-axis guarantees | [`protocols/x-axis-registry.yaml`](protocols/x-axis-registry.yaml) |
| Governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| L0 constraints | [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) |
| GaC rules (X1-X4) | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) |
| Agent workflows | [`.omo/_truth/registry/agent-workflows/`](.omo/_truth/registry/agent-workflows/) |
| Runtime projection registry | [`.omo/_truth/registry/runtime-projections.yaml`](.omo/_truth/registry/runtime-projections.yaml) |
| Debt registry | [`.omo/_truth/registry/debt.yaml`](.omo/_truth/registry/debt.yaml) |
| Task lifecycle | [`.omo/tasks/README.md`](.omo/tasks/README.md) |
| ADR index & process | [`.omo/_knowledge/decisions/INDEX.md`](.omo/_knowledge/decisions/INDEX.md) · [process standard](.omo/standards/adr-process.md) |
| Registry index (all registries) | [`.omo/_truth/registry/INDEX.md`](.omo/_truth/registry/INDEX.md) |
| Documentation ownership | [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) |
| MOF M3 元元模型 | [`projects/ecos/src/ecos/ssot/mof/m3.yaml`](projects/ecos/src/ecos/ssot/mof/m3.yaml) |
| MOF M1 governance 实例 | [`projects/ecos/src/ecos/ssot/mof/m1/governance/`](projects/ecos/src/ecos/ssot/mof/m1/governance/) |
| MOF capabilities | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| P74 workflow solidification (ADR-0130) | [`.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`](.omo/_knowledge/decisions/0130-p74-workflow-solidification.md) |
| 知识网关 L3-I0 解耦 + 事件索引管道 (ADR-0294) | [`.omo/_knowledge/decisions/0294-knowledge-gateway-decoupling-and-event-pipeline.md`](.omo/_knowledge/decisions/0294-knowledge-gateway-decoupling-and-event-pipeline.md) |
| Memory OS 控制面 (ADR-0372) | [`.omo/_knowledge/decisions/0372-memory-os-control-plane.md`](.omo/_knowledge/decisions/0372-memory-os-control-plane.md) · [architecture](docs/architecture/memory-os.md) · [registry](.omo/_truth/registry/memory-os.yaml) |
| 外部连接织层 | [`.omo/_truth/registry/external-connection-fabric.yaml`](.omo/_truth/registry/external-connection-fabric.yaml) · [standard](.omo/standards/external-connection-fabric.md) |
| 外部连接织层运行时边界 (ADR-0298) | [`.omo/_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md`](.omo/_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md) |
| Workflow Mesh worker 租约与接管 (ADR-0299) | [`.omo/_knowledge/decisions/0299-workflow-mesh-worker-lease-and-reclaim.md`](.omo/_knowledge/decisions/0299-workflow-mesh-worker-lease-and-reclaim.md) |
| Scene cards (9 cards, dual-track admission) | [`docs/scene-cards/`](docs/scene-cards/) · validate: `make scene-card-check` |
| Journey specs (state machines) | [`docs/journey-specs/`](docs/journey-specs/) · validate: `make journey-check` |
| Dual-track scene admission (ADR-0387) | [`.omo/_knowledge/decisions/0387-dual-track-scene-admission.md`](.omo/_knowledge/decisions/0387-dual-track-scene-admission.md) |
| Scene execution engine | `bin/ssot/journey-runner.py` (rebuild) · `signal-poller.py` (感知面) · `scene-outcome-recorder.py` (结果面) |
| Permission scope vocabulary | [`.omo/standards/permission-scope-vocabulary.yaml`](.omo/standards/permission-scope-vocabulary.yaml) |
| Signal sources registry | [`.omo/_truth/registry/signal-sources.yaml`](.omo/_truth/registry/signal-sources.yaml) |

## 2. Layer Model

Layer names and project placement are owned by [`docs/project-registry.yaml`](docs/project-registry.yaml) and generated into [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md).

The stable dependency direction remains:

```text
entry surfaces -> routing mesh -> engines/runtime/protocol -> governed state and evidence
```

External resources enter through the same direction:

```text
external descriptor -> sandbox/admission -> Agora route -> Workflow Mesh execution
                    -> OMO evidence -> Kairon/KOS/gbrain derived memory
```

Workflow execution has one control-plane fact source:

```text
admission -> StepDispatched -> worker ACK/lease -> timeout/reclaim -> evidence/verification
                         \-> OMO append-only events and projections
```

Worker YAML dispatch artifacts, runtime logs and handoff notes are derived
operational materials. They may explain or recover an execution, but they do
not advance WorkflowRun state without the corresponding OMO event.

## 3. Entry Architecture

| Audience | Preferred Entry | Contract |
|----------|-----------------|----------|
| Human operator | `cockpit` CLI/Web | One human-facing entry surface |
| AI agent | `agora` MCP via `bos://` URI | Cross-layer calls go through the mesh |
| Governance automation | `omo` CLI/MCP broker | Governed state mutations are audited |
| Web/API consumers | cockpit-mounted HTTP surfaces | Public web entry remains converged at L3 |
| Knowledge write (card PUT) | `cockpit /api/knowledge/put` → EventBus → `KnowledgeIndexer` | L3 网络优先解析 + 写后事件广播 (ADR-0294) |
| Memory recall / write (agent default) | `bos://memory/mos/*` (Phase 1+) · skill `memory-recall` | Memory OS 控制面 (ADR-0372)；P0 见 skill 回退路由 |

Do not introduce a new top-level human or agent entry without updating the relevant registry, boundary documentation, and governance checks.

## 4. BOS URI Domains

| Domain | URI Prefix | Role |
|--------|------------|------|
| Memory | `bos://memory/` | Knowledge, facts, search, storage; control plane `bos://memory/mos/*` (ADR-0372) |
| Governance | `bos://governance/` | OMO, policy, task/debt/audit flows |
| Analysis | `bos://analysis/` | Research, ontology derivation, code analysis |
| Persona | `bos://persona/` | Persona and personal knowledge bridges |
| Capability | `bos://capability/` | Tools, runtime capabilities, execution surfaces |

The complete machine-readable service map is [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml). Markdown should reference that file rather than duplicating service counts or route inventories.

### 4.1 External Connection Fabric

External knowledge, data, resources, methods, tools, models and channels share one descriptor and
lifecycle contract. The fabric is a cross-cutting capability, not a new top-level project:

| Responsibility | Owner |
|---|---|
| Descriptor and protocol contract | ECOS |
| Scene-bound admission, approval and evidence | OMO |
| Discovery and capability routing | Agora (`agora.external_connections`) |
| Knowledge source adapters | Kairon / Iris |
| Method compilation and evaluation | Kairon / Sophia |
| Execution, delivery receipts and recovery | Runtime / Workflow Mesh |
| Model, credentials, quota and cost | AetherForge |
| Human connection catalog and visibility | Cockpit |

The machine-readable contract is [`external-connection-fabric.yaml`](.omo/_truth/registry/external-connection-fabric.yaml).
Credentials are referenced, never stored in descriptors; unavailable or stale resources must remain
visible as such and must not be projected as successful live state.
Runtime discovery uses the `external.resources` entry-point group; Agora returns a credential-free
receipt that can be appended as OMO `EvidenceRecorded` without owning workflow state.

## 5. Governance Surfaces

```
.omo/                 -> state plane: goals, state, evidence, tasks, audits
projects/omo/         -> kernel plane: schemas, brokers, audit/lint/sync logic
projects/c2g/         -> ingress plane: strategy/pitch-to-task materialization
projects/ecos/        -> protocol plane: MOF and L0 constraints
```

Rules:

- `.omo/` is data and evidence, not a place for new long-lived execution logic.
- State mutations should use OMO CLI/MCP, C2G ingress, or registered brokers.
- New governance surfaces require runtime behavior, registry entries, and validation gates. Documentation alone is not implementation.
- External capabilities require a registered descriptor, scene binding, health evidence, and a reversible lifecycle before activation.
- Worker execution requires a durable dispatch context, ACK/lease evidence and an explicit reclaim path; a generated packet is not completion evidence.
- Direct `.omo/` or `spaces/` writes are violations unless routed through an approved audited path.

## 6. Port Registry & Transport (P77/P78)

```
protocols/port-registry.yaml  — I0 SSOT (name, transport, status, env_var)
projects/ecos/port-registry.yaml  — L0 mirror (aligned to I0)
```

- Every service port **must** be registered in `protocols/port-registry.yaml` with `name`, `transport` (stdio/http/sse/udp), and `status` (active/deprecated/reserved).
- Ports should be referenced via `{SERVICE}_PORT` env var, not literals (P77-7 env-var-SSOT).
- Deprecated ports (8765/9090) retain entry for historical resolution but `status: deprecated`.
- Foundry v2: port-governance deck validates hardcoded ports on every 6h cron cycle.

## 7. Core Flows

```
user or agent -> cockpit or agora -> bos:// route -> target service -> audited response or state transition
external or local source -> kairon ingestion/schema/search -> gbrain or local substrate -> retrieval
intent or pitch -> c2g or OMO broker -> task/debt/audit registry -> validation -> evidence
service definition -> runtime scheduler/matrix/sandbox -> health observation -> governance alert or recovery
external resource -> descriptor -> scene-bound admission -> capability route -> receipt/evidence -> derived memory
```

## 8. Recent Architecture Decisions

| ADR | Decision | Date |
|-----|----------|------|
| [ADR-0371](.omo/_knowledge/decisions/0371-pasw-submodule-isolation.md) | PASW — Per-Agent Submodule Worktree 隔离 | 2026-08-04 |
| [ADR-0370](.omo/_knowledge/decisions/0370-agt-ecos-integration.md) | AGT × eCOS v6 Integration via BOS URI External Adapter Pattern | 2026-08-04 |
| [ADR-0368](.omo/_knowledge/decisions/0368-runtime-taskfallback-test-contract.md) | Runtime Registry 测试契约与 TaskFallback 响应对齐 | 2026-08-04 |
| [ADR-0367](.omo/_knowledge/decisions/0367-sweep-tooling-scaling-roadmap.md) | Python 质量扫描基础设施规模化路线图 | 2026-08-04 |
| [ADR-0366](.omo/_knowledge/decisions/0366-pyright-sweep-algorithm.md) | Pyright 与 Ruff 扫描修复算法固化 | 2026-08-04 |
| [ADR-0365](.omo/_knowledge/decisions/0365-architecture-strategy-closeout.md) | Scenario-first architecture strategy and Workflow Mesh execution spine | 2026-08-04 |
| [ADR-0364](.omo/_knowledge/decisions/0364-kems-repeated-shadow-promotion-gate.md) | KEMS Repeated Shadow Promotion Gate | 2026-08-04 |
| [ADR-0363](.omo/_knowledge/decisions/0363-external-resource-refresh-plan.md) | External Resource Refresh Plan and Controlled Reachability | 2026-08-04 |
| [ADR-0362](.omo/_knowledge/decisions/0362-kems-runtime-health-and-recovery.md) | KEMS runtime health and verified SQLite recovery | 2026-08-04 |

## 9. Related Documents

| Document | Role |
|----------|------|
| [`docs/ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md`](docs/ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md) | 场景优先的长周期架构战略、子项目边界与 Workflow Mesh 路线基线 |
| [`README.md`](README.md) | Front door and quick orientation |
| [`AGENTS.md`](AGENTS.md) | Agent/developer operating guide |
| [`CLAUDE.md`](CLAUDE.md) | AI session context loader |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer index |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | System panorama and BOS routing |
| [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) | Architecture deep-dive (modules, data flow, control flow) |
| [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) | Functional capability map (8 domains, 32 capabilities) |
| [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) | Agora BOS URI callchain white-box |
| [`.omo/standards/external-connection-fabric.md`](.omo/standards/external-connection-fabric.md) | External resource, method, tool and channel contract (§7: dual-track admission) |
| [`docs/scene-cards/`](docs/scene-cards/) | Scene cards (9 cards: external + internal pipeline) |
| [`docs/journey-specs/`](docs/journey-specs/) | Journey state machine specs (3 journeys) |
| [`.omo/standards/permission-scope-vocabulary.yaml`](.omo/standards/permission-scope-vocabulary.yaml) | RBAC scope controlled vocabulary for internal pipeline scenes |
| [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) | Vision and roadmap |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | Documentation ownership contract |
