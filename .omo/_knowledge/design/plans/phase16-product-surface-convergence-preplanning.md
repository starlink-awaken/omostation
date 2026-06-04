# Phase 16 product surface convergence plan

> Status: completed
> Created: 2026-06-01
> Completed: 2026-06-01
> Owner: governance agent execution
> Entry gate: Phase 15 closeout GO + explicit human approval
> Source refs: `phase15-autonomous-governance-preplanning.md`, `../_knowledge/design/system-design-baseline.md`, `../PRODUCT-ARCH-JOURNEY.md`, `phase11-program-plan.md`
> Theme: Knowledge Capture/Search Product Surface Convergence

---

## 1. Purpose

Phase 16 is the first product-surface phase after the governance loop has been consolidated. It addresses the largest gap identified in the retrospective: the workspace has strong governance, evidence, routing, and capability substrate, but the `P0` user / product entry layer remains fragmented.

Phase 16 therefore focuses on converging entry surfaces, user journeys, and scenario shells on top of the guardrails produced by Phase 15. Phase 16 is not an ecosystem-expansion phase and it is not a shortcut around Phase 15 policy controls.

The completed scope narrows the product-surface convergence to one user-facing proof: `knowledge-capture-search`. This proves a user can provide knowledge text or a markdown file, search it back, and inspect a visible outcome state with evidence references.

The double-layer deposition rule is explicit:

- repo `.omo/` stores live evidence, plans, tests, scenario contracts, and closeout.
- external OMO stores case, pattern, and playbook as method artifacts only.
- external OMO must not copy repo live state or become shadow SSOT.

---

## 2. Scope boundary

The target convergence scope is deliberately narrow:

| Surface | Why it is in scope |
|---------|--------------------|
| `knowledge-capture-search` | Primary proof for user-visible value after Phase 15 governance consolidation |
| SharedBrain runtime-home | Carries user entry and result-home semantics without absorbing gbrain/kairon responsibilities |
| gbrain capture/search | Provides the capture/search/retrieval capability contract |
| kairon governance trace | Records capability binding and scenario evidence |
| External OMO method layer | Stores retrospective, pattern, and playbook without copying repo live truth |

---

## 3. Non-goals

- Do not bypass Phase 15 policy tests, evidence ledger, or recovery requirements.
- Do not reopen broad ecosystem absorption under a product label.
- Do not expose marketplace or external install workflows as a default user surface.
- Do not rewrite every UI or CLI surface in one phase.
- Do not ship unsupervised live autonomy as a product feature.
- Do not treat fixture-backed gbrain evidence as production live gbrain readiness.

---

## 4. Candidate wave structure

| Wave | Packet | Theme | Candidate scope | Exit evidence |
|------|--------|-------|-----------------|---------------|
| W1 | `P16-W1-JOURNEY-BASELINE` | Product journey baseline | Inventory entrypoints and map SharedBrain/gbrain/kairon/agentmesh roles | `.omo/evidence/phase16/journey-baseline.yaml` |
| W2 | `P16-W2-SCENARIO-SHELL` | Scenario shell contract | Define `knowledge-capture-search` and its intent/context/policy/execution/verification/recovery shell | scenario + shell evidence |
| W3 | `P16-W3-CAPTURE-SEARCH-WALKTHROUGH` | Capture/search walkthrough | Produce one fixture-backed, user-visible capture/search result | walkthrough + recovery evidence |
| W4 | `P16-W4-ADOPTION-CLOSEOUT` | Adoption and method handoff | Record adoption closeout, repo closeout, and external OMO case/pattern/playbook | adoption + closeout + external OMO method artifacts |

---

## 5. Requirements

### 5.1 User-journey requirements

1. A new user must be able to discover the primary workspace capabilities without reading scattered design docs first.
2. A recurring user must be able to see what the system is ready to do, what requires approval, and what is blocked.
3. A high-risk action must preserve confirmation, policy visibility, and verification hooks instead of disappearing behind automation.
4. Every primary journey must end with a visible outcome state: success, blocked, needs approval, or failed with recovery path.

### 5.2 Architecture requirements

1. Phase 16 must consume the Phase 15 evidence ledger rather than inventing a parallel product-state truth.
2. The scenario shell must bind intent, context, policy, execution, and verification through stable references.
3. Product-surface convergence must reuse existing `I0` routing and capability contracts rather than bypass them with bespoke shortcuts.
4. The implementation shape must remain one active packet at a time.

### 5.3 Verification requirements

1. Core journeys need reproducible walkthrough evidence.
2. Product-surface errors must expose recovery and approval states explicitly.
3. MVP adoption evidence must include at least one operator-facing and one end-user-facing journey.

---

## 6. Promotion criteria

Phase 16 planning can be promoted only when:

- Phase 15 has a recorded closeout GO.
- Phase 15 policy tests are passing and cover promotion, draft activation, and rollback requirements.
- Phase 15 recovery drill evidence exists for the journey families Phase 16 will expose.
- Human review confirms the Phase 16 scope stays on product-surface convergence instead of ecosystem expansion.
- No Phase 16 task exists in `tasks/active/` before the above gates pass.

---

## 7. Handoff rule

The full detailed design for Phase 16 should be emitted as a reviewed Phase 15 W4 handoff artifact. This document is the bounded planning shell that reserves the next phase, fixes its entry gate, and protects the scope boundary in advance.
