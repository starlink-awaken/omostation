---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Phase 15 autonomous governance design

> Date: 2026-05-31
> Updated: 2026-06-01
> Status: pre_planning design
> Scope: Phase 15 supervised autonomous governance loop
> Canonical input: `../../plans/phase15-autonomous-governance-preplanning.md`
> Baseline input: `system-design-baseline.md`
> Upstream inputs: `../../plans/archive/phase12-program-plan.md`, `../../plans/archive/phase13-metacognition-preplanning.md`, `../../plans/archive/phase14-deferred-ecosystem-backlog.md`, `phase12-14-architecture-design.md`
> Live SSOT: `../../state/system.yaml`, `../../goals/current.yaml`, `../../tasks/active/`

---

## 1. Executive architecture

Phase 15 is the governance flywheel after the capability ecosystem is no longer a one-off project. Inside the baseline framework, it operationalizes the single governed lifecycle loop on top of `00`, `I0`, `X1`, and `X2`.

```text
Phase 12 evidence
  -> Phase 13 proposals
  -> Phase 14 selected expansion evidence
  -> Phase 15 governance evidence ledger
  -> policy tests
  -> inactive task drafts
  -> human approval
  -> active execution in a later approved packet
```

The key boundary is simple: Phase 15 may automate observation, validation, compilation, and rehearsal. It must not automate live mutation by default.

---

## 2. Control-plane principles

1. **Evidence is the product**: Phase 15 succeeds by making governance evidence queryable and testable.
2. **Compilation is not activation.** Proposal-to-task output must remain inactive until human approval creates an active packet.
3. **Policy before convenience**: if a dashboard or compiler output disagrees with policy tests, policy tests win.
4. **Recovery is mandatory**: every mutation-capable proposal needs rollback and verification before it can become an execution candidate.
5. **No phase laundering**: Phase 15 cannot quietly execute Phase 14 backlog or Phase 13 mutation work under a new name.
6. **Phase 15 does not deliver P0 product-surface convergence.** It prepares the guardrails Phase 16 will later consume.

---

## 3. Component design

| Component | Responsibility | Artifact boundary | Mutation allowed |
|-----------|----------------|-------------------|------------------|
| Governance evidence ledger | Index evidence envelopes from Phase 12-14 and new Phase 15 rehearsals | `.omo/_truth/governance-evidence/` or equivalent future SSOT | No live SSOT mutation |
| Policy test harness | Encode promotion, mutation, deferred-scope, and one-active-packet rules | `.omo/tests/` | Test-only |
| Proposal-to-task compiler | Transform approved proposals into inactive task drafts | `.omo/tasks/drafts/` or equivalent future draft path | Draft write only |
| Operating dashboard snapshot | Summarize health, proposal quality, backlog pressure, and recovery readiness | dashboard report | Read-only |
| Recovery rehearsal runner | Execute fixture or dry-run rollback checks | transcript + report | Fixture/dry-run only |
| Phase 16 handoff contract | Emit the minimal product-surface planning handoff without activating Phase 16 | reviewed handoff note | No execution |

---

## 4. Evidence model

Phase 15 should not invent incompatible evidence shapes. The ledger should normalize a small set of envelopes:

| Envelope | Required fields | Source phase |
|----------|-----------------|--------------|
| Promotion envelope | source phase, target phase, approval, evidence refs, rollback, verification | 12-15 |
| Deferred-scope envelope | item, reason, owner, re-entry condition, expiry/review date | 14-15 |
| Scenario trace envelope | scenario id, capability bindings, input, output, failure policy, evidence refs | 12 |
| Mutation proposal envelope | source, target, expected change, operation level, approval need, rollback, verification | 13-15 |
| Closeout envelope | completed scope, non-goals preserved, test evidence, residual risk | 12-15 |
| Recovery drill envelope | drill target, fixture/dry-run mode, rollback command, expected state, observed result | 15 |
| Phase handoff envelope | upstream phase, downstream phase, handoff boundary, non-goals preserved, approval need | 15-16 |

The deferred-scope ledger itself remains `../../plans/archive/phase14-deferred-ecosystem-backlog.md`; Phase 15 consumes it and must not recreate it.

---

## 5. Detailed flow

1. `P15-W1-EVIDENCE-LEDGER` defines the ledger schema and validates fixture evidence from Phase 12-14.
2. `P15-W2-POLICY-AS-TESTS` converts guardrails into policy tests.
3. `P15-W3-PROPOSAL-COMPILER` compiles selected approved proposals into inactive drafts.
4. `P15-W4-RECOVERY-DASHBOARD` runs dashboard snapshot, recovery rehearsal, and cross-audit.
5. `P15-W4` also emits the minimal Phase 16 handoff recommendation.
6. Any later activation still requires a human-approved promotion or task activation packet.

---

## 6. Failure handling

| Failure | Required behavior |
|---------|-------------------|
| Missing evidence ref | policy test fails; compiler refuses draft output |
| Proposal lacks rollback | mutation candidate remains proposal-only |
| Draft appears in active tasks | P0 policy failure |
| Dashboard conflicts with ledger | dashboard marked stale; ledger remains authoritative |
| Recovery drill fails | no mutation-capable proposal can be promoted from that drill family |
| Product-surface work appears in Phase 15 packet | scope violation; packet fails review until removed |

---

## 7. Phase 15 review matrix

| Dimension | Required answer |
|-----------|-----------------|
| Scope | Governance loop only; no new ecosystem expansion and no P0 delivery |
| SSOT | Evidence ledger and inactive drafts only; no live promotion from design text |
| Security | Mutation proposals require operation level, approval, rollback, and verification |
| Testing | Policy tests, fixture validation, compiler dry-run, recovery rehearsal |
| Drift guard | Blocks phase laundering, hidden deferred scope, and draft activation leaks |

---

## 8. Relationship to Phase 12-16

| Neighbor phase | Phase 15 consumes | Phase 15 must not reinterpret |
|----------------|------------------|-------------------------------|
| Phase 12 | registry, scenario trace, pilot audit, package dry-run | registry existence as permission for broad install |
| Phase 13 | metacognition reports and proposal envelopes | proposal as approval |
| Phase 14 | selected expansion evidence and deferred ledger updates | backlog as execution plan |
| Phase 16 | receives only a handoff recommendation | Phase 16 scope as a hidden Phase 15 delivery |

---

## 9. Non-negotiable guardrails

- Phase 15 remains pre-planning until Phase 14 closeout GO or explicit human reprioritization.
- Phase 15 must not create active tasks while earlier phase gates remain open.
- Proposal-to-task compiler output must be inactive by construction.
- Auto-apply remains disabled by default.
- Live SSOT changes require promotion envelope and human approval.
- The Phase 14 deferred backlog remains the sole deferred-scope ledger.
