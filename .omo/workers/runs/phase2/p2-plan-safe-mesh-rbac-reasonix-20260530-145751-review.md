# Review Note — P2-PLAN-SAFE-MESH-RBAC

## Summary of work done

### Inputs consumed
- `.omo/tasks/active/P2-plan-safe-mesh-rbac.yaml` — task definition
- `.omo/standards/operation-levels.md` — L0-L3 classification, deny path pattern, first-wave candidates, sensitive capabilities rule
- `.omo/standards/agent-registry-heartbeat.md` — heartbeat protocol, identity token schema, cache behavior, deadlock detection
- `.omo/MASTER-BLUEPRINT.md` — architecture context, M2.2 Safe Mesh placement
- `.omo/plans/phase2-task-specs-v2.md` — M2.0-M2.5 gate sequence
- `.omo/standards/operation-level-rollout-plan.md` — detailed tool inventory, first-wave selection rationale
- `.omo/plans/planning-blueprint-delivery-test-standard.md` — plan/evidence/review format standards

### Deliverable 1: Deployment Roadmap
**File:** `.omo/plans/safe-mesh-rbac-deployment-roadmap.md`

Contents:
1. **§1 Safe Mesh definition** — 4 layers: Operation Levels + Heartbeat + Identity + RBAC
2. **§2 Current state baseline** — what's done (operation-levels, heartbeat design) vs what's new (RBAC)
3. **§3 RBAC model (NEW)** — 5 roles (reader/operator/curator/admin/auditor), agent-type mapping, RBAC check flow, extended identity token schema with `role` field
4. **§4 6-Wave rollout roadmap** — 3 governance gates (Waves 1, 2, 6) + 3 delivery tracks (Waves 3, 4, 5)
5. **§5 Delivery Track vs Governance Gate** — comparison table clarifying the distinction
6. **§6 Integration matrix** — 7 integration points (I1-I7) across all components
7. **§7 Acceptance scenarios** — RBAC-specific + full Safe Mesh end-to-end
8. **§8 Dependencies & preconditions**
9. **§9 Risk register**

### Deliverable 2: Updated Task YAML
**File:** `.omo/tasks/active/P2-plan-safe-mesh-rbac.yaml`

Added `evidence` section with 4 evidence items pointing to the roadmap document, plus `next_action` and `needs_human_review` fields.

### Key architecture decisions

| Decision | Rationale |
|----------|-----------|
| RBAC CHECK at agentmesh Gateway (not per-MCP-server) | Leverage existing Gateway routing layer, avoid N implementations |
| `role` as explicit JWT field (not derived from `agent_type`) | agent_type → role is default mapping, but override allows flexible policy without changing agent identity |
| 4 sensitive capability categories blocked | Aligned with `operation-levels.md` §7 — Apple, WeChat, Family OS, SMB, Media, high-autonomy |
| L2 deny as `_confirmed:true` not per-role | Keeps deny path consistent with existing L2/L3 standard; role check happens before deny path |

### Test plan verification
1. ✅ Roadmap reviewed against operation levels — rollup inventory baseline (§7 of operation-levels.md) incorporated into Wave 3 first-wave candidates
2. ✅ Roadmap reviewed against heartbeat standards — identity token extended with `role` field, integration point I3-I7 map back to heartbeat/registry
3. ✅ Rollout sequence distinguishes delivery track (Waves 3,4,5 — code) vs governance gate (Waves 1,2,6 — design/audit)

### Next steps (human)
1. **Review RBAC model** (§3) — approve/modify roles, agent-type mapping, permission rules
2. **Approve Wave 1 gate** — unblock Wave 2 execution (identity token extension + RBAC middleware)
3. **Review sensitive capabilities list** (§4 Wave 4)
4. **Confirm resource allocation** for Waves 3-5 (implementation) — estimate: 2-3 sprints

### Unresolved risks
- RBAC granularity may cause performance regression if checked per-request at Gateway level
- SharedBrain MCP tools not yet classified — default L2+ may be too restrictive
- Token rollover during Wave 2→3 transition could disrupt running agents
