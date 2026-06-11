# OPC Architecture Gaps

> Status: revised planning baseline after entry convergence and R46-R50 governance probes
> Date: 2026-06-11
> Purpose: gap map from current Workspace/eCOS v5 to OPC personal swarm AI brain

## 1. Entry Residual Gaps

Current issue:

- The workspace historically had multiple practical entry paths: cockpit CLI, cockpit MCP, cockpit HTTP, Agora MCP, Agora HTTP, runtime MCP, l4-kernel MCP.
- Recent docs and commits claim the target 3-entry architecture is implemented: cockpit CLI, Agora MCP, cockpit HTTP.
- The remaining gap is verification and cleanup: direct internal MCP paths must not remain primary Agent journeys.

Target:

- Human: `cockpit CLI`.
- Agent: `agora MCP :7431`.
- Web/API: `cockpit HTTP :8090`.

Risks:

- Agents may keep direct stdio MCP configs and bypass Agora governance.
- Journey probes may keep documenting direct cockpit/l4-kernel MCP access as if it were primary.
- Duplicate authentication, audit, and routing behavior may persist through compatibility windows.
- Documentation may continue to teach old entry points.

Required decisions:

- Agora MCP is the only default agent entry.
- Internal MCP services remain callable only as Agora-routed implementation details.
- cockpit HTTP is the only public HTTP surface.
- Entry work is no longer a greenfield task; it is a verification and hardening task.

## 2. Fact and Documentation Drift

Current issue:

- Root README still reflects an older project count and architecture snapshot.
- `docs/PANORAMA.md`, `.omo/state/system.yaml`, and current submodule inventory have different phase and project views.
- Some newer projects have template README content or thin descriptions.
- Recent R46-R50 work changed governance, metrics, and probe status; the OPC plan must absorb those deltas.

Target:

- One canonical roadmap baseline with current, stale, and conflicting facts clearly marked.
- Architecture docs are navigation and truth pointers, not parallel truth stores.

Risks:

- Future agents may optimize against outdated project lists.
- Phase numbers may be mistaken for product maturity.
- Stale docs may claim capabilities that are not journey-validated.

Required decisions:

- Treat submodule inventory and current project files as factual inputs.
- Treat older docs as evidence, not automatically current truth.
- Register drift as OMO debt instead of silently rewriting history.
- Read recent commits and probe reports before executing any OPC phase.

## 3. Memory Gaps

Current issue:

- cockpit local research search is not the same as global KOS/gbrain recall.
- gbrain, KOS, cockpit DB, and external document sources do not yet read as one personal memory product.
- Source attribution and search scope need to be surfaced consistently.
- kairon has direct JSONL append paths, gbrain has multiple JSONL writers plus a non-atomic overwrite path, and metaos currently lacks a `.omo/` governance plane.

Target:

- `bos://memory/**` gives a clear semantic route for ingest, search, recall, source lookup, and archive.
- Each output has source, timestamp, owner, freshness, and reuse policy.

Risks:

- Users may trust incomplete local search as if it were global recall.
- Duplicate memory records may drift.
- Generated outputs may not be reusable because source context is missing.
- Product memory may be built on persistence paths that are not schema-checked, append-only, or cross-repo audited.

Required decisions:

- Every long-term memory write must be schema-checked and audited.
- Every search response must declare scope.
- Canonical source pointers must be preserved across derived outputs.
- kairon/gbrain/metaos persistence hardening is a prerequisite for trusted personal memory.

## 4. Swarm Execution Gaps

Current issue:

- `swarm-engine` contains market, DAG, lifecycle, economy, conflict, semantic orchestration, dispatcher, and event bus concepts.
- `aetherforge` aggregates gateway, swarm, and mesh, but canonical API boundaries need to be locked.
- OMO tasks and swarm worker tasks are not yet one obvious execution chain.

Target:

- User goal becomes OMO Task.
- OMO Task becomes swarm DAG.
- Workers execute through runtime and model/compute planes.
- Results return to memory and audit.

Risks:

- `aetherforge` may duplicate core swarm logic.
- Runtime may absorb semantic decisions that belong to swarm/OMO.
- Worker failure may remain operational noise instead of governed debt.

Required decisions:

- `swarm-engine` owns task market and DAG semantics.
- `aetherforge` is the product aggregation API.
- `runtime` owns execution isolation.
- OMO owns gates, debt, audit, and phase state.

## 5. Model and Compute Gaps

Current issue:

- `llm-gateway` and `compute-mesh` exist, but business modules may still call providers or local execution directly.
- Cost, speed, capability, privacy, and fallback policies need to be first-class task attributes.

Target:

- `llm-gateway` is the only model abstraction.
- `compute-mesh` is the compute and worker resource abstraction.
- Model and compute telemetry flows into OMO metrics.

Risks:

- Provider-specific code spreads through the workspace.
- Cost cannot be attributed to tasks.
- Sensitive personal data may be sent to unsuitable providers.

Required decisions:

- New provider support goes through `llm-gateway`.
- Task budget includes token, cost, and time.
- Privacy class is mandatory for personal or medical contexts.

## 6. Governance Gaps

Current issue:

- OMO governance is strong, but phase state, planned tasks, debt registry, and product roadmap need tighter alignment.
- Some plans are architecture-heavy and not tied to user journeys.
- R46 `audit-rollout --include-metrics`, R47 metrics artifacts/trends, and R48-R50 probe reports are now active planning inputs, not future ideas.

Target:

- Every phase has goal, tasks, gate, validation, audit, debt, signal, and retrospective.
- Roadmap milestones map to user value, not just technical phase numbers.

Risks:

- More governance artifacts may be created without product progress.
- Phase completion may be claimed without journey validation.
- Agents may update docs but skip audit/debt records.
- Cross-repo audit may remain documentation-only if not promoted into phase gates.

Required decisions:

- Phase completion requires validation evidence.
- Architecture changes require journey impact review.
- Debt is registered when facts conflict or gates fail.
- Cross-repo audit/metrics should become a baseline gate from Phase 0.5 onward, not wait until final hardening.

## 7. Product Scenario Gaps

Current issue:

- North Star scenarios exist: technical radar, work assistance, family health.
- They need repeatable product journeys from cockpit/Web instead of manual expert operation.

Target:

- At least two North Star scenarios run repeatedly through a user-facing entry.
- Outputs include source, timestamp, next action, and memory writeback.

Risks:

- The system may remain an engineering platform rather than a personal brain.
- Users may need to understand internal repositories to get value.
- Scenario outputs may not feed back into memory and future planning.

Required decisions:

- Product journeys are acceptance gates, not optional demos.
- Scenario results must write back to memory.
- Scenario tasks must enter OMO task/audit/debt flows.

## 8. Self-Evolution Gaps

Current issue:

- The vision includes technical radar and self-improvement, but the full loop is not yet a governed recurring operating rhythm.

Target:

- Radar discovers useful changes.
- System scores candidates.
- Approved candidates become planned tasks.
- Swarm executes.
- OMO audits.
- Retrospectives update memory and roadmap.

Risks:

- Auto-generated tasks may flood the backlog.
- The system may optimize itself without user approval.
- Upgrade recommendations may lack evidence.

Required decisions:

- Automated upgrade suggestions enter planned, not active.
- Human approval is required for execution.
- Every recommendation needs evidence links and expected value.
