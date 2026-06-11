# OPC Roadmap OMO Execution Plan

> Status: revised planning baseline after entry convergence and R46-R50 governance probes
> Date: 2026-06-11
> Scope: OMO-governed execution plan for OPC personal swarm AI brain

## OMO Execution Contract

All phases follow the same mechanism:

1. Pre-check: read phase state, planned tasks, active tasks, debt registry, dashboard.
2. Goal: declare the user-value objective.
3. Tasks: execute only scoped task items.
4. Validation: run the planned checks and record evidence.
5. Audit: append audit records for meaningful changes.
6. Debt: register unresolved drift, missing capability, or failed gate.
7. Signal: emit phase closeout or blocker signal.
8. Retrospective: write a closeout summary before marking done.

No phase may be marked complete without gate evidence and retrospective.

## Phase 0 — Fact Baseline

Goal: freeze the current Workspace/eCOS v5 factual baseline for OPC planning.

Tasks:

- OPC-P0-T1-project-inventory: rebuild inventory from `git submodule status --recursive` and project manifests.
- OPC-P0-T2-doc-drift-audit: compare README, AGENTS, PANORAMA, ENTRY, JOURNEY, and `.omo/state/system.yaml`.
- OPC-P0-T3-capability-map: map projects to entry, memory, governance, swarm, model, compute, scenario, and evolution capabilities.
- OPC-P0-T4-debt-register: register stale or conflicting facts as OMO debt.
- OPC-P0-T5-recent-change-digest: absorb latest root commits, submodule pointer updates, entry convergence docs, and R46-R50 probe reports.

Validation:

- Project inventory matches submodule status.
- Each core project has one primary OPC role.
- Stale/current/conflicting facts are listed.
- Recent entry convergence status is classified as verified, unverified, or debt.
- R46-R50 probe findings are captured before later phases start.

Architecture constraints:

- Do not edit business code.
- Do not hand-edit `.omo/state/system.yaml`.
- Do not introduce new architecture layers.

Audit:

- Record baseline creation and drift findings.

Debt:

- Register unresolved documentation drift, phase confusion, and missing project role descriptions.
- Register any unverified entry convergence claim or missing probe evidence.

Signal:

- Emit `opc_phase0_baseline_ready` when baseline is complete.

Retrospective:

- Record what is confirmed, what is stale, what must be checked before Phase 1.

## Phase 1 — Entry Convergence Verification and Hardening

Goal: verify and harden cockpit, Agora, and cockpit HTTP as the three external entry points after recent convergence work.

Tasks:

- OPC-P1-T1-entry-contract-verify: verify human, agent, and Web/API entries match current docs and implementation.
- OPC-P1-T2-agora-mcp-route-verify: verify cockpit, runtime, and l4-kernel MCP capabilities route through Agora.
- OPC-P1-T3-bos-entry-routes-verify: verify `bos://cockpit/**`, `bos://runtime/**`, and `bos://l4-kernel/**` route behavior.
- OPC-P1-T4-deprecated-path-cleanup: mark old direct MCP entries as compatibility-only and remove them from primary Agent guidance.
- OPC-P1-T5-journey-probes-update: rewrite direct MCP probes as `Agent -> Agora MCP -> bos://...` primary probes.

Validation:

- Agent docs default to Agora MCP.
- Internal MCP services are described as implementation details.
- Entry journey probes exist.
- Direct cockpit/l4-kernel/runtime MCP probes are deprecated or rewritten as Agora-routed probes.
- Route behavior is validated, not only documented.

Architecture constraints:

- Do not add new external entry points.
- Do not let agents bypass Agora for cross-layer calls.
- Web/API aggregation belongs to cockpit HTTP.

Audit:

- Record entry contract changes and deprecated surfaces.

Debt:

- Register any remaining direct-agent entry as debt.
- Register stale journey probes and stale Agent configuration examples as debt.

Signal:

- Emit `opc_phase1_entry_contract_ready`.

Retrospective:

- Record remaining compatibility windows and deprecation risks.

## Phase 1.5 — Cross-Repo Governance Baseline

Goal: promote recent R46-R50 governance work into mandatory gates for later OPC phases.

Tasks:

- OPC-P15-T1-r46-metrics-baseline: treat `audit-rollout --include-metrics` as active governance capability.
- OPC-P15-T2-r47-trend-baseline: track ci-lint metrics artifacts and trend plotting as observability inputs.
- OPC-P15-T3-r48-kairon-probe-actions: convert kairon probe findings into tasks, including JSONL write hardening.
- OPC-P15-T4-r49-metaos-probe-actions: convert metaos probe findings into tasks, including `.omo/` governance plane initialization.
- OPC-P15-T5-r50-gbrain-probe-actions: convert gbrain probe findings into tasks, including zod AppendOnlyLog and non-atomic write remediation.

Validation:

- R46-R50 findings are referenced from the OPC task plan.
- kairon is classified as a real multi-package workspace, not a meta-stub.
- metaos and gbrain missing `.omo/` planes are explicit debt or tasks.
- Cross-repo metrics expectations are attached to later phase gates.

Architecture constraints:

- Cross-repo governance is a baseline gate, not final polish.
- Probe findings must become tasks or debt, not remain prose.
- Do not force owner-dependent cross-repo changes without recording ownership and risk.

Audit:

- Record promotion of R46-R50 findings into OPC gates.

Debt:

- Register unresolved kairon/gbrain/metaos governance gaps.

Signal:

- Emit `opc_phase15_cross_repo_governance_baseline_ready`.

Retrospective:

- Record which probe findings are blockers and which are follow-up hardening.

## Phase 2 — Memory Spine

Goal: create a governed personal memory path for ingest, search, recall, attribution, and archive.

Tasks:

- OPC-P2-T1-memory-boundary: define gbrain, KOS, cockpit DB, and external source boundaries.
- OPC-P2-T2-memory-uri: define `bos://memory/**` route policy.
- OPC-P2-T3-recall-flow: design collect-to-recall-to-output-to-archive flow.
- OPC-P2-T4-source-map: define source metadata.
- OPC-P2-T5-memory-metrics: define recall, duplication, freshness, and attribution metrics.
- OPC-P2-T0-persistence-prerequisites: verify kairon/gbrain/metaos persistence hardening is complete or registered as blocking debt.

Validation:

- One real question can move through collect, ingest, search, output, and archive.
- Search responses declare scope.
- Outputs include source metadata.
- kairon JSONL writers, gbrain audit writers, gbrain non-atomic pin writes, and metaos missing `.omo/` plane are resolved or explicitly blocking.

Architecture constraints:

- One fact has one canonical source.
- No long-term raw JSONL writes without schema and append-only abstraction.
- No source-free derived output.
- Trusted memory cannot depend on untracked raw append or non-atomic overwrite paths.

Audit:

- Record memory writes, source-map changes, and recall validation.

Debt:

- Register duplicate memory stores, missing source metadata, and local/global search confusion.
- Register unsafe persistence as blocking debt when it affects personal memory trust.

Signal:

- Emit `opc_phase2_memory_spine_ready`.

Retrospective:

- Record memory quality baseline and next reliability work.

## Phase 3 — Swarm Execution Spine

Goal: convert high-level goals into governed multi-agent execution.

Tasks:

- OPC-P3-T1-task-object: define swarm task object.
- OPC-P3-T2-swarm-boundary: lock boundaries among OMO, swarm-engine, aetherforge, and runtime.
- OPC-P3-T3-agent-roles: define standard worker roles.
- OPC-P3-T4-worker-dispatch: design dispatch, heartbeat, retry, and failure debt.
- OPC-P3-T5-min-demo: specify a minimal three-worker demo.

Validation:

- A goal can decompose into at least three worker tasks.
- Worker tasks have owner, status, input, output, and audit.
- Failure creates retry or debt.

Architecture constraints:

- `swarm-engine` owns task market and DAG.
- `aetherforge` owns product aggregation.
- `runtime` owns execution isolation.
- OMO/MetaOS gates high-risk execution.

Audit:

- Record task decomposition, dispatch, completion, and failure events.

Debt:

- Register unclear ownership, failed workers, and missing result writeback.

Signal:

- Emit `opc_phase3_swarm_spine_ready`.

Retrospective:

- Record swarm reliability, role usefulness, and human intervention points.

## Phase 4 — Model Gateway and Compute Mesh

Goal: centralize model and compute selection through governed infrastructure.

Tasks:

- OPC-P4-T1-llm-gateway-contract: define `llm-gateway` as the only model abstraction.
- OPC-P4-T2-model-registry: define provider capability metadata.
- OPC-P4-T3-budget-policy: define task token, cost, and time budgets.
- OPC-P4-T4-compute-mesh-contract: define compute worker discovery, heartbeat, and scheduling.
- OPC-P4-T5-metrics: connect model/compute metrics to OMO reporting.

Validation:

- Model selection supports cost, speed, capability, and balanced strategies.
- Provider failure has fallback.
- Cost and latency are attributable to task and phase.

Architecture constraints:

- No direct provider calls from business modules.
- New providers go through `llm-gateway`.
- Personal or medical data requires privacy class.

Audit:

- Record model choice, fallback, cost, latency, and compute allocation.

Debt:

- Register direct provider calls, untracked costs, and missing privacy classification.

Signal:

- Emit `opc_phase4_model_compute_ready`.

Retrospective:

- Record model cost baseline and compute reliability.

## Phase 5 — North Star Scenarios

Goal: prove OPC through repeatable product scenarios.

Tasks:

- OPC-P5-T1-tech-radar: technical radar journey.
- OPC-P5-T2-work-assistant: sourced work draft journey.
- OPC-P5-T3-family-health: family health summary and reminder journey.
- OPC-P5-T4-product-entry: expose scenarios through cockpit/Web.
- OPC-P5-T5-journey-validation: create and run probes.

Validation:

- At least two scenarios run repeatedly.
- Outputs include source, timestamp, and next action.
- Results write back to memory.

Architecture constraints:

- Scenarios do not call low-level private implementations directly.
- Scenario tasks enter OMO task/audit/debt flows.
- Product UX hides internal repository boundaries.

Audit:

- Record scenario runs, outputs, and follow-up tasks.

Debt:

- Register scenario dead ends, missing writeback, and unclear next actions.

Signal:

- Emit `opc_phase5_north_star_ready`.

Retrospective:

- Record which scenarios create real value and which remain demos.

## Phase 6 — Self-Evolution Loop

Goal: make improvement discovery and execution a governed recurring loop.

Tasks:

- OPC-P6-T1-evolution-loop: define radar to gap to task to swarm to audit to retrospective.
- OPC-P6-T2-upgrade-scoring: define value, risk, cost, dependency, and verification scoring.
- OPC-P6-T3-weekly-report: generate weekly evolution report.
- OPC-P6-T4-drift-detector: detect entry, doc, fact, and Agora bypass drift.
- OPC-P6-T5-human-approval: ensure auto-generated tasks stay planned until approved.

Validation:

- Weekly report has at least three upgrade candidates.
- At least one candidate becomes planned task.
- Drift detector catches stale docs or bypass entries.

Architecture constraints:

- Self-evolution may suggest and plan, not execute without approval.
- Every recommendation needs evidence.
- High-risk changes require explicit human approval.

Audit:

- Record recommendations, scores, approvals, and rejections.

Debt:

- Register unverified recommendations, task floods, and recurring drift.

Signal:

- Emit `opc_phase6_evolution_loop_ready`.

Retrospective:

- Record recommendation quality and approval bottlenecks.

## Phase 7 — Governance Hardening

Goal: establish release train, gates, and long-term maintenance rhythm.

Tasks:

- OPC-P7-T1-release-train: define 1-2 week roadmap release cadence.
- OPC-P7-T2-phase-gates: harden phase gates.
- OPC-P7-T3-cross-repo-audit: plan cross-repo audit rollout.
- OPC-P7-T3-cross-repo-audit-hardening: harden and expand the R46-R50 cross-repo audit/metrics baseline.
- OPC-P7-T4-doc-sync-policy: define PANORAMA, ENTRY, JOURNEY, and ROADMAP sync policy.
- OPC-P7-T5-review-template: create milestone review template.

Validation:

- Every release has summary, validation, and remaining debt.
- Every phase has retrospective.
- Dashboard can show phase, milestone, blockers, and debt health.
- Cross-repo metrics are actively consumed by gates, not merely documented.

Architecture constraints:

- No phase completion without validation evidence.
- No code completion without journey probe when user-facing.
- No docs claim without command, test, or artifact evidence.

Audit:

- Record release train events and gate decisions.

Debt:

- Register missing release evidence, stale docs, and weak gates.

Signal:

- Emit `opc_phase7_governance_hardened`.

Retrospective:

- Record governance overhead, release predictability, and next roadmap cycle.
