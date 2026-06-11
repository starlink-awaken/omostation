# OPC Roadmap — Personal Swarm AI Brain

> Status: revised planning baseline after entry convergence and R46-R50 governance probes
> Date: 2026-06-11
> Scope: Workspace/eCOS v5 to OPC personal swarm AI brain

## 1. Vision

OPC is the personal swarm AI brain for one person: it remembers long-term context, understands goals, decomposes work, dispatches specialized agents, chooses models and compute, records evidence, and improves itself through governed feedback loops.

The system should feel like one product, not a pile of projects. Humans enter through cockpit, agents enter through Agora, long-term facts live in canonical memory, execution is handled by the swarm/runtime stack, and every meaningful change leaves an OMO trail.

## 2. Current Architecture Snapshot

The current workspace is no longer the older 8-project picture. Treat the following as the working architecture map for roadmap planning:

| Area | Main projects | OPC role |
|---|---|---|
| Self layer | `l4-kernel` | L4 domain registry, self-state, KEMS health, personal control surface |
| Human entry | `cockpit`, `hermes-console` | CLI/Web cockpit, status, cards, user-facing operations |
| Agent entry and mesh | `agora` | MCP convergence, BOS URI routing, proxy, rate limit, circuit breaker, audit hook |
| Knowledge and memory | `kairon`, `gbrain` | KOS, ingestion, graph/structured memory, research and recall |
| Governance | `omo`, `omo-debt`, `metaos`, `model-driven` | goals, tasks, debt, audit, lifecycle models, gates, immune checks |
| Runtime and protocol | `runtime`, `ecos` | sandbox, scheduler, matrix, SSB/protocol log, L0 anchoring |
| Swarm and capability | `swarm-engine`, `aetherforge`, `aetherforge-swarm-ext` | task market, DAG, worker lifecycle, planning/perception extensions |
| Model and compute | `llm-gateway`, `compute-mesh` | model provider abstraction, model scheduling, compute discovery, worker resources |
| Product scenarios | `family-hub`, cockpit/Web surfaces | family health, work assistance, technical radar user journeys |

## 3. Target Architecture

The target architecture is organized around five product capabilities:

1. One way in: humans use `cockpit`, agents use `agora MCP`, Web/API uses `cockpit HTTP`. Recent entry convergence work claims this target is implemented, so the roadmap treats it as verification and hardening work, not greenfield implementation.
2. One memory spine: ingest, search, recall, source attribution, and archive share canonical sources.
3. One swarm execution spine: OMO Task becomes swarm DAG, workers execute, runtime isolates, results return to memory.
4. One model/compute plane: `llm-gateway` and `compute-mesh` are the only model and compute abstractions.
5. One evolution loop: radar discovers upgrades, OMO plans them, swarm executes them, audit verifies them.

## 4. Roadmap Milestones

### M0 — Baseline Freeze

Goal: freeze the factual baseline before implementation.

Deliverables:

- Current project inventory from submodules and docs.
- Recent-change digest from the latest root commits, submodule pointer updates, and R46-R50 probe reports.
- Current/stale/conflicting fact matrix.
- OPC capability map.
- Initial debt entries for drift and conflicts.

Acceptance:

- Every core project has exactly one role in the roadmap.
- Entry convergence claims are classified as verified, unverified, or stale.
- R46-R50 governance findings are included in the execution baseline.
- Stale facts are not silently normalized; they are listed as debt.
- No business code changes.

### M1 — Entry Convergence Verification and Hardening

Goal: verify and harden the already-claimed 3-entry architecture.

Deliverables:

- Confirmed human entry: `cockpit CLI`.
- Confirmed agent entry: `agora MCP :7431`.
- Confirmed Web/API entry: `cockpit HTTP :8090`.
- Verified Agora routes for cockpit, l4-kernel, and runtime MCP capabilities.
- Deprecated direct stdio MCP entries documented as compatibility-only paths.
- Updated journey probes that use `Agent -> Agora MCP -> bos://...`, not direct agent-to-internal-MCP paths.

Acceptance:

- Agent instructions point to Agora MCP by default and contain no recommended direct internal MCP path.
- `bos://cockpit/**`, `bos://runtime/**`, and `bos://l4-kernel/**` resolve through Agora or have registered debt.
- Deprecated entries are marked, documented, and excluded from primary journey probes.
- Gate B review checks real route behavior, not only documentation claims.

### M1.5 — Cross-Repo Governance Baseline

Goal: move recent audit-rollout and probe work into the baseline gates for every later phase.

Deliverables:

- R46 `audit-rollout --include-metrics` treated as an active governance capability.
- R47 ci-lint metrics artifact and trend script treated as ongoing observability work.
- R48-R50 kairon/metaos/gbrain probe reports converted into concrete prerequisite tasks.
- Per-repo governance readiness table for kairon, metaos, gbrain, runtime, and omo.

Acceptance:

- Each later phase can cite cross-repo audit/metrics expectations.
- kairon is treated as a real 16-package workspace, not a meta-stub.
- metaos and gbrain missing `.omo/` governance planes are tracked as explicit gaps.
- gbrain JSONL and non-atomic write risks are tracked before product memory work depends on them.

### M2 — Personal Memory Spine

Goal: make personal memory searchable, attributable, reusable, and governed.

Deliverables:

- Memory boundaries for gbrain, KOS, cockpit local DB, external documents, Family/work sources.
- `bos://memory/**` route policy.
- Cross-repo persistence hardening prerequisites for kairon, gbrain, and metaos.
- Source metadata policy: source, timestamp, owner, reuse policy, freshness.
- Memory quality metrics.

Acceptance:

- One real question can go through collect, ingest, search, output, archive.
- Search surfaces show scope and source.
- Long-term writes are schema-checked and audited.
- kairon/gbrain/metaos persistence risks are either remediated or registered as blocking debt.

### M3 — Swarm Execution Spine

Goal: convert user goals into governed multi-agent execution.

Deliverables:

- Swarm task object contract.
- Agent role set: researcher, planner, coder, reviewer, operator, critic.
- Dispatch, heartbeat, retry, failure debt, and result collection plan.
- Minimal demo that decomposes one goal into at least three worker tasks.

Acceptance:

- Every worker task has owner, status, input, output, and audit.
- Failure creates retry or debt.
- Results can be written back to memory.

### M4 — Model Gateway and Compute Mesh

Goal: remove direct model/provider coupling from business modules.

Deliverables:

- `llm-gateway` as the only model provider abstraction.
- Model registry with provider, context, cost, latency, tool support, privacy class.
- Task-level budget policy.
- `compute-mesh` worker discovery and heartbeat contract.

Acceptance:

- Tasks can choose model by cost, speed, capability, or balanced policy.
- Provider failure has fallback.
- Cost and latency are visible by task, phase, and provider.

### M5 — North Star Product Scenarios

Goal: prove OPC value through real use cases.

Scenarios:

- Technical radar: collect AI/agent/knowledge-engineering updates, analyze relevance, create upgrade tasks.
- Work assistant: generate sourced structured drafts for real work questions.
- Family health: summarize family medical records and produce next actions.

Acceptance:

- At least two scenarios can run repeatedly.
- Outputs include source, timestamp, and next action.
- Users do not need to understand underlying project boundaries.

### M6 — Self-Evolution Loop

Goal: make system improvement a governed recurring workflow.

Deliverables:

- Radar to gap to task to swarm to audit to retrospective loop.
- Upgrade scoring: value, risk, cost, dependency, verification difficulty.
- Weekly evolution report.
- Drift detector for entry drift, documentation drift, duplicate facts, and Agora bypass.

Acceptance:

- Weekly report contains at least three upgrade candidates.
- At least one candidate becomes an OMO planned task.
- Auto-generated tasks require human approval before active execution.

### M7 — Governance Hardening and Release Train

Goal: make OPC maintainable as a long-running personal operating system.

Deliverables:

- 1-2 week roadmap release train.
- Phase gates and review templates.
- Cross-repo audit rollout hardening and expansion plan.
- Documentation sync policy for PANORAMA, ENTRY, JOURNEY, and ROADMAP.

Acceptance:

- Every release has summary, verification, and remaining debt.
- Every phase has retrospective.
- Dashboard shows phase, milestone, blockers, and debt health.
- Cross-repo metrics are not only planned; they are used by phase gates.

## 5. Key Review Gates

| Gate | After | Review focus |
|---|---|---|
| Gate A | M0 | Fact baseline and stale/conflicting fact handling |
| Gate B | M1 | Entry convergence and Agora-only agent path |
| Gate B2 | M1.5 | R46-R50 governance probes absorbed into cross-repo gates |
| Gate C | M2 | Memory recall, source attribution, archive, and persistence hardening |
| Gate D | M3-M4 | Swarm dispatch, model selection, cost tracking, result writeback |
| Gate E | M5 | Real scenario usefulness and repeatability |
| Gate F | M6 | Self-evolution loop with human approval |
| Gate G | M7 | Release train and governance hardening |

## 6. Non-Negotiable Constraints

- Do not add new external agent entry points.
- Do not bypass Agora for cross-layer agent calls.
- Do not keep direct internal MCP journey probes as primary agent paths after entry convergence.
- Do not let product scenarios depend on private low-level implementation details.
- Do not duplicate canonical facts across memory stores without source pointers.
- Do not build memory/product features on top of untracked raw JSONL or non-atomic writes.
- Do not allow self-evolution tasks to become active without human approval.
- Do not mark a phase complete without validation evidence and retrospective.
