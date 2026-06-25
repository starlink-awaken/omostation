---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 15 cross-review

> Date: 2026-05-31
> Status: review complete; pre-planning only
> Review target: `../design/phase15-autonomous-governance-design.md`
> Source refs: `../../plans/phase15-autonomous-governance-preplanning.md`, `../design/phase12-14-architecture-design.md`

---

## 1. Review result

Phase 15 is directionally valid if it stays focused on supervised autonomous governance. The correct role is to make Phase 12-14 evidence, proposals, deferred scope, and recovery controls continuously auditable.

The main risk is scope laundering: Phase 15 could become a back door for Phase 14 ecosystem expansion or Phase 13 live mutation. The design blocks that by keeping proposal compilation inactive, requiring policy tests, and preserving human approval for activation.

---

## 2. Multi-dimensional review

| Dimension | Finding | Severity | Required control |
|-----------|---------|----------|------------------|
| Scope | Governance-loop scope is coherent; ecosystem expansion stays in Phase 14 | P1 | Explicit non-goals and policy tests |
| SSOT | Evidence ledger is useful, but must not overwrite live state | P0 | Promotion envelope + human approval |
| Security | Mutation-capable proposals need rollback and operation-level approval | P0 | Mutation proposal envelope + recovery drill |
| Operability | Dashboard snapshot can reduce drift if ledger remains authoritative | P1 | Dashboard stale-state rule |
| Testing | Policy-as-tests is the right enforcement layer | P0 | pytest checks for active-task and promotion invariants |
| Human control | Proposal-to-task compiler must not activate tasks | P0 | Inactive task draft envelope |

---

## 3. Required governance guardrails

| Guardrail | Required support |
|-----------|------------------|
| Governance evidence ledger | A canonical evidence index for promotion, deferred scope, scenario traces, mutation proposals, closeouts, and recovery drills |
| Policy test harness | Executable checks for no live promotion from plan text, one active packet, no hidden deferred scope, and no draft activation leaks |
| Inactive task draft envelope | Draft output path and schema that cannot be confused with `.omo/tasks/active/*.yaml` |
| Recovery drill transcript | Structured record proving rollback instructions were rehearsed |
| Dashboard snapshot contract | Read-only summary that points to ledger evidence instead of copying truth |

---

## 4. Open issues before Phase 15 execution

| Issue | Current concern | Resolution path |
|-------|-----------------|-----------------|
| Ledger location | Current design allows `.omo/_truth/governance-evidence/` or equivalent future SSOT | Decide exact path during Phase 15 W1, after entry gate |
| Draft task path | `.omo/tasks/drafts/` does not currently exist as an approved execution boundary | Define inactive draft envelope before compiler output |
| Policy coverage | Current tests cover planning docs but not full governance invariants | Add policy test harness in W2 |
| Phase 14 dependency | Phase 15 should not wait forever if Phase 14 is explicitly deferred | Allow human-approved reprioritization after Phase 13 closeout |

---

## 5. Decision

Proceed with Phase 15 as a pre-planning design package. Do not create Phase 15 active tasks from this review. The valid execution path remains Phase 11 completion, Phase 12-14 gate progression, then Phase 15 promotion only after its entry criteria are met.
