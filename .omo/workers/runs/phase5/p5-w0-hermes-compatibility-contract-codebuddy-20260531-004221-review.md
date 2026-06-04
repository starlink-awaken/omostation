# Review Note

## Summary of work done

### Deliverable
- Created `.omo/_knowledge/design/phase5-hermes-contract.md`

### What was frozen

1. **Scope boundary** (§1): Three-tiered classification — IN (ingress + memory + API key fallback), OUT (scheduler backbone, cron definitions, task-definition ownership, MCP tool source, kanban visualization — all with migration targets), MAINTENANCE ONLY (existing bridge symlinks, existing cron definitions, existing MCP tools — keep running, no new investment).

2. **Integration contracts** (§2): Three contracts — Ingress Contract for WeChat/IM → Gateway (routes.ts frozen), Memory Consumption Contract for MCP interface (best-effort, OMO native preferred), Fallback Dependency Contract for API key resolution (secret_ref chain with explicit priority).

3. **Ownership handoff plan** (§3): Wave 1 migrates scheduler (12 cron jobs + bridge symlinks → agentmesh + Task Center), Wave 3 migrates MCP tools and memory consumption (→ agent-runtime + OMO native API).

4. **Non-negotiables** (§4): No new shadow SSOT, no secret values in Hermes paths, no Hermes as scheduler backbone for new work, trace continuity mandatory.

5. **Evidence cross-reference** (§5): Maps directly to the two `evidence_required` criteria from the task YAML.

### Key decisions that were frozen

- Direction A confirmed (from `hermes-convergence-strategy.md`)
- Direction B deferred to Phase 6+ evaluation
- All new scheduling/tool/skill work must use OMO-native components
- Hermes memory consumed through MCP — no native OMO memory API in Phase 5 scope

### Files created
- `.omo/_knowledge/design/phase5-hermes-contract.md`

### Files read
- `.omo/tasks/active/P5-w0-hermes-compatibility-contract.yaml`
- `.omo/plans/phase5-wave0-task-specs.md`
- `.omo/_knowledge/design/hermes-convergence-strategy.md`
- `.omo/_knowledge/design/phase5-program-architecture.md`
- `.omo/plans/phase5-entry-gate-checklist.md`
- `.omo/tests/test_phase5_wave0_docs.py`
- `projects/agentmesh/packages/gateway/src/hermes/routes.ts`
