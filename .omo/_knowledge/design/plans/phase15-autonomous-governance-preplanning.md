# Phase 15 autonomous governance pre-planning

> Status: completed
> Created: 2026-05-31
> Updated: 2026-06-01
> Owner: governance agent draft; human ratification required before execution
> Entry gate: Phase 14 closeout GO + explicit human approval
> Alternate entry: explicit human reprioritization after Phase 13 closeout, with risk acceptance if Phase 14 is deferred
> Baseline alignment: `../_knowledge/design/system-design-baseline.md`
> Source refs: `phase12-program-plan.md`, `phase13-metacognition-preplanning.md`, `phase14-deferred-ecosystem-backlog.md`, `../_knowledge/design/phase12-14-architecture-design.md`, `../_knowledge/design/phase15-autonomous-governance-design.md`

---

## 1. Purpose

Phase 15 is the first post-Phase-14 consolidation phase under the `OMO Baseline Framework (4P3V1L)`. Its job is to operationalize the single governed lifecycle loop on top of the `00` SSOT substrate, `I0` integration fabric, and `X1/X2` governance and recovery axes.

Phase 15 is therefore a governance-loop phase, not a product-surface phase. It turns the outputs of Phase 12-14 into a durable supervised operating loop that can observe, assess, propose, approve, rehearse, and verify without silently mutating live SSOT.

Execution review added one correction: Phase 15 must not strengthen OMO in isolation. The completed phase therefore also records project health and a governed user-value loop, so the control plane remains tied to `projects/` capabilities and concrete user-facing scenarios.

---

## 2. Phase focus inside the baseline

| Baseline slice | Phase 15 role | Why now |
|----------------|---------------|---------|
| `00` SSOT substrate | Normalize evidence and draft boundaries so planning, review, and execution stop drifting apart | The system already has enough evidence; the gap is queryability and policy enforcement |
| `I0` integration fabric | Make scenario traces, mutation proposals, and recovery evidence routable through stable contracts | Governance evidence is only useful if it can be traced across entry seams |
| `X1` governance policy | Convert hard guardrails into executable tests | Prevent policy from living only in prose |
| `X2` anti-entropy / recovery | Rehearse rollback and recovery before any future live autonomy | Later autonomy must inherit recovery, not invent it |

Phase 15 does not deliver `P0` product-surface convergence. That is the entry scope for Phase 16 after Phase 15 guardrails are in place.

---

## 3. Scope

| Workstream | Scope | Primary evidence |
|------------|-------|------------------|
| Governance evidence ledger | Normalize promotion, deferred-scope, mutation proposal, scenario trace, and closeout evidence into one audit path | ledger schema + fixture validation |
| Policy-as-tests | Convert non-negotiable guardrails into executable checks | pytest policy suite |
| Proposal-to-task compiler | Convert approved metacognition proposals into draft task packets without activating them | dry-run task packet + approval envelope |
| Supervised operating dashboard | Summarize capability health, proposal quality, backlog pressure, and recovery readiness | dashboard snapshot |
| Recovery rehearsal | Run rollback and incident drills against fixtures or dry-run targets | drill transcript + pass/fail report |
| Phase 16 handoff contract | Emit the minimum planning handoff Phase 16 needs without starting product-surface execution early | Phase 16 handoff note + scoped recommendation |

---

## 4. Non-goals

- Do not enable production auto-mutation by default.
- Do not create Phase 15 active tasks while Phase 11, 12, 13, or 14 gates remain open.
- Do not treat Phase 14 backlog volume as a Phase 15 success metric.
- Do not bypass the one-active-packet rule.
- Do not expose marketplace or external install workflows without admission, sandbox, and rollback controls.
- **No P0 surface work during Phase 15.**
- Do not turn the Phase 14 deferred backlog into a second execution plan.

---

## 5. Candidate wave structure

| Wave | Packet | Theme | Candidate scope | Exit evidence |
|------|--------|-------|-----------------|---------------|
| W1 | `P15-W1-EVIDENCE-LEDGER` | Evidence ledger baseline | Define the unified ledger schema and migrate Phase 12-14 evidence pointers into fixtures | schema validation + fixture report |
| W2 | `P15-W2-POLICY-AS-TESTS` | Policy executable gates | Turn promotion, mutation, deferred-scope, and one-packet rules into policy tests | policy test report |
| W3 | `P15-W3-PROPOSAL-COMPILER` | Proposal-to-task dry-run | Compile selected Phase 13 proposals into inactive task packet drafts with approval envelopes | dry-run packet + review report |
| W4 | `P15-W4-RECOVERY-DASHBOARD` | Supervised operating closeout | Dashboard snapshot, recovery drill, redteam, and Phase 16 handoff recommendation | audit + recovery drill + handoff note |

---

## 6. Entry criteria

Phase 15 planning can be promoted only when:

- Phase 12 has delivered capability registry, scenario trace, one fusion pilot, and closeout audit.
- Phase 13 has delivered read-only metacognition reports and mutation proposal envelopes.
- Phase 14 has either completed selected ecosystem expansion or has an explicit human-approved defer decision.
- The `OMO Baseline Framework (4P3V1L)` is the active planning reference for post-Phase-14 work.
- The human owner approves Phase 15 as governance-loop work, not ecosystem expansion work.
- No Phase 15 active task exists before promotion.

---

## 7. Exit criteria

Phase 15 can close only when:

- Evidence ledger fixtures validate all required evidence envelope types.
- Policy tests block at least these violations: live SSOT promotion without envelope, multiple active packets, hidden deferred scope, mutation proposal without rollback, and task activation without approval.
- Proposal-to-task compiler emits inactive drafts only.
- Recovery rehearsal proves rollback instructions are discoverable and testable.
- The Phase 16 handoff recommendation is recorded without activating any product-surface packet.
- Cross-audit confirms Phase 15 did not mutate live SSOT outside approved gates.

---

## 8. Metrics

| Metric | Meaning | Target |
|--------|---------|--------|
| `policy_test_pass_rate` | Percentage of governance policy checks passing | 100% at closeout |
| `proposal_traceability_rate` | Approved proposals with source evidence, expected change, rollback, and verification | 100% for sampled proposals |
| `draft_activation_leak_count` | Draft packets accidentally entering active state | 0 |
| `rollback_drill_success_rate` | Recovery drills passing against fixture or dry-run targets | 100% for selected drills |
| `governance_cycle_time` | Time from proposal to reviewed inactive task draft | measured, not optimized until baseline exists |
| `phase16_handoff_scope_leak_count` | Product-surface items incorrectly executed during Phase 15 | 0 |

---

## 9. Required OMO mechanism support

Phase 15 requires OMO to treat governance evidence as first-class, not as free-form prose:

- `Governance evidence ledger`: canonical index for promotion, deferred-scope, scenario, proposal, mutation, and closeout evidence.
- `Policy test harness`: pytest-backed checks for phase promotion and active task invariants.
- `Inactive task draft envelope`: a task packet format that cannot be confused with `.omo/tasks/active/*.yaml`.
- `Recovery drill transcript`: structured evidence that rollback instructions were rehearsed.
- `Dashboard snapshot contract`: stable summary for health, proposal quality, backlog pressure, and recovery readiness.
- `Phase 16 handoff note`: scoped recommendation that can be reviewed later without authorizing immediate execution.

These mechanism iterations are design support only. They do not authorize Phase 15 execution before entry gates pass.
