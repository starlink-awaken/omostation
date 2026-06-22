---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 12/13 cross-review and revision

> Date: 2026-06-01
> Status: review complete; planning docs revised
> Scope: Phase 12 planning gap, archived Phase 13 metacognition draft, Phase 11 Wave 4 bridge
> SSOT note: live phase/state remain owned by `state/system.yaml` and `goals/current.yaml`.

---

## 1. Review finding

The current control plane is Phase 11 Wave 1 active. Phase 12 has no registered planning gate yet, while Phase 11 Wave 4 already declares a Phase 12 pre-planning handoff. Phase 13 exists only as `plans/archive/phase13-metacognition.md`, but that archived draft claims Phase 1-12 are complete and proposes direct implementation under home-directory paths. That is stale and unsafe as an execution source.

The correction is to insert a formal Phase 12 planning gate and replace Phase 13 execution assumptions with a pre-planning gate that is blocked until Phase 12 proves production readiness, data substrate control, protocol contracts, and supervised autonomy boundaries.

---

## 2. Cross-review dimensions

| Dimension | Phase 12 revision | Phase 13 revision |
|-----------|-------------------|-------------------|
| SSOT integrity | Phase 12 is registered as pre-planning only; no live phase/status mutation | Phase 13 references live SSOT and explicitly supersedes the archived draft |
| Sequencing | Phase 12 depends on Phase 11 Wave 4 closeout GO | Phase 13 depends on Phase 12 closeout GO and explicit human ratification |
| Product value | Moves from internal hardening to stable user/runtime operation | Moves from "self-awareness" slogan to inspectable self-assessment and supervised suggestions |
| Engineering safety | Requires packaging, FastMCP, path config, observability, migration dry runs | Disallows auto-apply and cross-instance consensus until rollback/audit gates exist |
| Data governance | Treats DB consolidation as a Phase 12 data-substrate decision and dry-run, not a Phase 13 coding shortcut | Consumes Phase 12 data contracts; does not invent new storage locations |
| Security | Identity/admission and approval boundaries are gate items | Human approval, operation-level limits, and rollback evidence are mandatory |
| Testability | Every wave has concrete verification commands or review artifacts | Metacognition outputs must be reproducible, read-only first, and covered by governance tests |
| Maintainability | Uses `.omo/plans/` and indexes; avoids home-path implementation plans | Keeps archived Phase 13 as historical input only |

---

## 3. Required revisions landed

- Revised `plans/archive/phase12-planning-gate.md` as the entry gate and constrained `plans/archive/phase12-program-plan.md` as the canonical Phase 12 program.
- Added `plans/archive/phase13-metacognition-preplanning.md`.
- Added `plans/archive/phase14-deferred-ecosystem-backlog.md` for work removed from Phase 12.
- Updated `plans/README.md` to register both as PRE-PLANNING.
- Updated `plans/archive/phase11-wave4-execution-plan.md` so the Phase 12 handoff points to the new gate and records Phase 13 pre-planning as a downstream input.
- Updated root/control/design indexes so future agents can find the new gates without reading archived material.
- Added `tests/test_phase12_13_planning_docs.py` to lock the pre-planning status, sequencing gates, archive supersession language, and index coverage.

---

## 4. Open risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Existing archived Phase 13 draft still contains executable-looking snippets | P1 | New Phase 13 pre-planning doc states it supersedes archive for planning; `plans/README.md` routes active readers to new doc |
| Phase 12 scope could become a dumping ground for all deferred hardening | P1 | Wave gates restrict Phase 12 to production readiness, data substrate, protocol federation, and supervised autonomy readiness |
| DB consolidation can corrupt local data if executed prematurely | P0 | Kept as dry-run and migration-decision work in Phase 12, never as direct Phase 13 execution |
| Metacognition can become unbounded auto-mutation | P0 | Phase 13 gate requires read-only first, approval queues, rollback evidence, and operation-level limits |

---

## 5. Decision

Phase 12/13 are not execution-ready. They are now formal pre-planning artifacts with explicit entry gates:

- Phase 12 entry requires Phase 11 Wave 4 closeout GO.
- Phase 13 entry requires Phase 12 closeout GO plus human ratification.

No active task should be created for Phase 12/13 until those gates are satisfied.
