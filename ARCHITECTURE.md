---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# ARCHITECTURE.md — eCOS v6 Architecture Contracts

> 最后更新: 2026-09-03
> This document owns stable architecture concepts: layers, dependency direction, routing contracts, and governance boundaries.
> It does not own runtime facts, current phase, health score, test counts, tool counts, service counts, or ports.

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
| MOF tooling (compiler/bridge/predictive) | [`projects/ecos/src/ecos/ssot/tools/`](projects/ecos/src/ecos/ssot/tools/) · `mof-scan` · `mof-bridge-match` · `mof-predictive-loop` · `ecos-constraint-compiler` |
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
| LECP 生命事件契约 (LECP v3.0) | [`protocols/lecp-schema.yaml`](protocols/lecp-schema.yaml) |

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

Information-flow roles (perception, cognition, spine, outcome) and how
AGE-v2 / resident / BCOS nest as backends, projectors, or meters — not as
second operating systems — are owned by
[`docs/architecture/os-operating-pattern-v1.md`](docs/architecture/os-operating-pattern-v1.md).
Dao / Fa / Shu / Qi as a reading of MOF M3–M0 (not a fifth ontology) lives in
[`docs/architecture/dao-fa-shu-qi.md`](docs/architecture/dao-fa-shu-qi.md).
This file keeps layer placement and routing contracts; those files keep slot
grammar and hard slot checks (`sfop-slots` in the local GaC gate). Do not add a
third runtime narrative.

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

### 4.2 Spine Value Pipeline & Human-in-the-Loop Evolution (ADR-0437)

The spine value pipeline governs the single-operator operating loop: ingress signal → triage → sovereign draft generation → Cockpit review & HITL signature → diff extraction & idle LoRA adaptation.
- Routing: `bos://cockpit/spine/sign`, `bos://cockpit/spine/distill`, `bos://cockpit/spine/replay`
- Persona LoRA Adapters are trained in idle compute nodes (Mac mini M4 roaming) and dynamically mounted on sovereign models (`bos://compute/aetherforge/infer`).

## 5. Governance Surfaces

```
.omo/                 -> state plane: goals, state, evidence, tasks, audits
projects/omo/         -> kernel plane: schemas, brokers, audit/lint/sync logic
                        + c2g ingress (strategy/pitch-to-task materialization, ADR-0412 内包)
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

See [`.omo/_knowledge/decisions/INDEX.md`](.omo/_knowledge/decisions/INDEX.md) for the full ADR index.

## 9. Related Documents

| Document | Role |
|----------|------|
| [`docs/architecture/digital-twin-blueprint-v1.md`](docs/architecture/digital-twin-blueprint-v1.md) | 第二数字分身目标架构、Decision Episode 主链、MOF Control Compiler 与 90 天收敛路线 |
| [`docs/architecture/blueprint-multi-agent-execution-control-v1.md`](docs/architecture/blueprint-multi-agent-execution-control-v1.md) | 蓝图多 Agent 战略执行、Work Packet、九级 Gate、证据与职责分离契约 |
| [`.omo/_archive/operations-2026H1/blueprint-agent-instruction-pack-v1.md`](.omo/_archive/operations-2026H1/blueprint-agent-instruction-pack-v1.md) | 可分发给 Executor、Verifier、Strategic Director 和各 Agent 平台的统一操作指令 |
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
