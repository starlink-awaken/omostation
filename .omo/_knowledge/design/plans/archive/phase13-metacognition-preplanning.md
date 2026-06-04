# Phase 13 metacognition pre-planning gate

> Status: completed
> Created: 2026-06-01
> Owner: governance agent draft; human ratification required before execution
> Entry gate: Phase 12 closeout GO + explicit human approval
> Supersedes as planning source: `archive/phase13-metacognition.md`
> Source refs: `phase12-planning-gate.md`, `phase12-program-plan.md`, `phase14-deferred-ecosystem-backlog.md`, `_knowledge/management/phase12-13-cross-review-2026-06-01.md`

---

## 1. Gate purpose

Phase 13 explores metacognition, bottleneck detection, supervised collaboration, and self-healing. It must remain bounded by auditability and approval controls. The archived Phase 13 draft is retained as historical input only; this document is the planning entrypoint.

The old framing of "self-awareness" is replaced with a testable definition: the system can produce reproducible self-assessment reports, identify blind spots from evidence, propose improvements with confidence and risk labels, and route every mutation through an approval and rollback path.

---

## 2. Entry conditions

- Phase 12 closeout GO is recorded.
- Human ratification approves Phase 13 planning promotion.
- Capability registry schema and scan baseline from Phase 12 are stable.
- At least one Phase 12 scenario has a reproducible trace.
- The Phase 12 single fusion pilot has smoke-test evidence and rollback notes.
- Operation-level approval matrix and human approval queue are available.
- Phase 14 deferred backlog exists so Phase 13 does not absorb ecosystem-expansion work by accident.
- No Phase 13 task is present in `tasks/active/` before the above gates pass.

---

## 3. Revised wave structure

| Wave | Theme | Scope | Guardrail |
|------|-------|-------|-----------|
| W1 | Read-only metacognition baseline | knowledge coverage, blind spot inventory, capability gap report, confidence scoring | read-only sources only; no mutation |
| W2 | Bottleneck and improvement proposal engine | top bottleneck detection, cost/freshness/capability signals, ranked suggestions | suggestions include evidence, confidence, risk, rollback notes |
| W3 | Supervised agent collaboration | task discovery, collaboration proposal, human approval queue, execution envelope | no auto-execute without approval; operation-level limits enforced |
| W4 | Self-healing and strategic sensing pilot | anomaly detection, rollback recommendation, trend report, roadmap delta proposal | rollback is rehearsed before live mutation; strategic deltas stay proposals |

---

## 4. Explicitly rejected from archived draft

- Direct implementation under `~/.hermes/scripts/` as the planning default.
- Claims that Phase 1-12 are already complete.
- DB consolidation as an immediate Phase 13 task.
- Unsupervised `agent.auto_execute`.
- Cross-instance consensus without identity/admission and rollback evidence.
- Long code snippets in planning docs that bypass current project package boundaries.

---

## 5. Verification model

Phase 13 execution packets must include:

- A read-only fixture or sample dataset.
- A deterministic self-assessment output schema.
- A blind-spot report with evidence pointers.
- Operation-level classification for every proposed action.
- Human approval evidence for every mutation.
- Rollback proof before any live self-healing action.

---

## 6. Promotion criteria

Phase 13 can move from pre-planning to gated execution only when a future planning review confirms:

- Phase 12 delivered capability registry, scenario trace, one fusion pilot, audit/redteam evidence, and Phase 14 backlog.
- The first Phase 13 packet is read-only.
- Auto-apply remains disabled by default.
- Governance tests cover archive supersession, entry gates, and index registration.

---

## 7. Completion evidence

Phase 13 completed as supervised metacognition, not live mutation:

- W1 read-only baseline: `.omo/evidence/phase13/metacognition-baseline.yaml`
- W2 bottleneck proposals: `.omo/evidence/phase13/bottleneck-proposals.yaml`
- W3 supervised collaboration envelope: `.omo/evidence/phase13/supervised-collaboration.yaml`
- W4 self-healing dry-run rehearsal: `.omo/evidence/phase13/self-healing-rehearsal.yaml`
- Closeout: `.omo/summaries/phase13-closeout.md`
- Retrospective: `.omo/summaries/phase13-retrospective.md`
