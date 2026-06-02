# Debt governance mechanism design

Date: 2026-06-02
Status: approved-through-interactive-design
Scope: create a persistent, multi-dimensional debt governance mechanism inside `.omo`, with cross-project debt pointers, dynamic metrics, and progressive gates

## 1. Context

The workspace already has strong `.omo` governance, but debt is still spread across multiple surfaces:

1. analysis docs such as `debt-systems-analysis-and-governance.md`
2. implementation plans such as `debt-cleanup-plan.md`
3. active and blocked tasks under `.omo/tasks/`
4. summary fields in `state/system.yaml`

This creates three problems:

1. debt items are visible, but not modeled as first-class governance objects
2. health signals can drift away from actual debt reality
3. the system can record debt, yet still lack a durable review cadence and lifecycle model

The goal is not to create another static backlog. The goal is to create a **living debt governance mechanism** that can:

- register debt as first-class objects
- measure debt across multiple dimensions
- expose dynamic health and entropy signals
- upgrade some debts into governance gates when necessary
- keep `.omo` as the governance kernel without shadow-copying project truth

## 2. Goals

This mechanism should:

1. make debt a first-class governance object in `.omo`
2. keep the debt ledger canonical in `.omo`, while allowing debt items to point into `projects/*`, `SharedBrain/`, CI, runtime, and docs
3. replace single-score thinking with a multi-dimensional debt view
4. distinguish clearly between identified, scheduled, mitigated, verified, and closed debt
5. support continuous iterative review instead of one-off cleanup waves
6. allow high-risk debt to escalate into progressive governance gates

## 3. Non-goals

This design does not:

1. copy project-local implementation truth into `.omo`
2. turn every debt item into a blocking gate
3. redesign all workspace quality metrics at once
4. replace project-specific issue trackers or internal backlogs
5. force every historical debt item to be fully re-authored before the mechanism can start

## 4. Chosen design posture

### 4.1 Scope anchor

Use **`.omo` governance kernel + cross-project debt pointers`**.

That means:

- debt objects live in `.omo`
- affected systems are referenced by pointers and evidence refs
- implementation truth remains in the owning project or runtime surface

### 4.2 Governance mode

Use **gated-progressive governance**.

That means:

- all debt can be observed and scored
- only selected debt upgrades into watchlist or gate status
- governance becomes stronger where risk or drift justifies it

## 5. Architecture

### 5.1 Debt Registry

Create a first-class debt registry in `.omo` as the authoritative debt ledger.

Each debt item should be an independent object, not an embedded blob in `state/system.yaml` or scattered prose in retrospectives.

Each item should include at least:

- `id`
- `title`
- `dimension`
- `subdimension`
- `domain`
- `scope`
- `severity`
- `entropy_class`
- `lifecycle_state`
- `owner`
- `affected_roots`
- `evidence_refs`
- `mitigation_refs`
- `opened_at`
- `last_reviewed_at`
- `next_review_at`
- `gate_level`

### 5.2 Multi-dimensional debt model

Debt should not be managed as a single flat list. It should be split across stable dimensions:

1. code/test debt
2. architecture debt
3. governance/process debt
4. runtime/ops debt
5. integration/dependency debt
6. knowledge/doc debt

Every debt item must have one primary dimension. Optional secondary dimensions are allowed where cross-cutting debt is real.

### 5.3 Control shell

`state/system.yaml` should not hold the full debt ledger.

Instead, it should hold only:

- debt summary metrics
- top watchlist/gate counts
- pointers to the canonical debt registry and dashboard outputs

This preserves `.omo` control-plane readability while keeping debt truth structured elsewhere.

## 6. Metric system

The mechanism should maintain several coordinated indicators rather than one overloaded score.

### 6.1 Debt Health

Debt Health answers: **is debt governance currently under control?**

It should reflect at least:

- debt coverage quality
- whether high-severity debt is actively governed
- whether overdue review items exist
- whether gate debts are being bypassed

### 6.2 Debt Entropy

Debt Entropy answers: **is the debt system becoming disordered?**

It should be decomposed into at least:

1. **classification entropy** — too many debts in vague buckets such as “other”
2. **state entropy** — too many debts stuck in middle states for too long
3. **pointer entropy** — missing owners, missing refs, missing review dates, stale evidence
4. **time entropy** — old debts drifting without closure or revalidation

Entropy is intentionally not just “more debt.” It measures **loss of structure**.

### 6.3 Backlog Pressure

Backlog Pressure answers: **how much execution drag is current debt creating?**

It should consider:

- number of high-severity debts
- number of aging debts
- number of repeated phase-to-phase carryovers
- number of debts still waiting for scheduling

### 6.4 Coupling Load

Coupling Load answers: **how many systems or governance planes does a debt span?**

Debt affecting multiple roots should automatically weigh more than isolated debt.

For example, a debt touching `.omo`, `projects/kairon/`, CI, and SharedBrain should score higher than one isolated to a single package.

## 7. Lifecycle state machine

Each debt item should move through an explicit lifecycle:

`identified -> classified -> scheduled -> in_progress -> mitigated -> verified -> closed`

Three additional side states are allowed:

- `watching`
- `blocked`
- `archived`

### 7.1 Rules

1. `scheduled` does not mean resolved
2. `mitigated` does not mean closed
3. only `verified` debt may become `closed`
4. `reopen` must be possible if debt reappears
5. summary fields such as `resolved_debt_items` must be derived from ledger state, not manually drifted

## 8. Governance actions

The mechanism should support at least these actions:

- `register`
- `reclassify`
- `schedule`
- `escalate`
- `revalidate`
- `close`
- `reopen`

These actions should be auditable and should preserve evidence continuity.

## 9. Progressive gate model

Not every debt should block progress. Gates should be progressive.

### 9.1 Escalation ladder

1. ordinary debt → ledger item
2. risky debt → watchlist
3. persistently deteriorating or system-critical debt → gate debt

### 9.2 Candidate upgrade rules

Debt should be eligible for escalation when it is:

- high severity and high entropy
- drifting across multiple phases
- cross-project or cross-plane coupled
- affecting Go/No-Go, admission, rollout, or core safety signals
- in `scheduled` / `in_progress` without timely revalidation

## 10. Output surfaces

The mechanism should produce at least four outputs:

### 10.1 Debt Registry

Canonical structured debt objects in `.omo`.

### 10.2 State Summary

Compact debt summary fields and pointers in `state/system.yaml`.

### 10.3 Dashboard Snapshot

Human-readable dynamic output showing:

- debt health
- entropy
- aging hotspots
- watchlist debts
- gate debts
- cross-domain debt heat

### 10.4 Review / Retro Packs

Phase or wave review outputs summarizing:

- newly registered debts
- closed debts
- drifted debts
- escalated debts
- reopened debts

## 11. Review cadence

To keep the ledger alive, the mechanism should define a fixed cadence:

1. incremental refresh after important debt-related changes
2. debt review at each wave closeout
3. mandatory revalidation of gate debt at phase gates
4. time-based review via `next_review_at` for long-lived watching debts

## 12. Cross-project pointer rules

Because the ledger is `.omo`-anchored, debt items should point to external evidence rather than copy it.

Each debt item may point to:

- affected roots
- evidence refs
- implementation refs
- mitigation refs
- owning system refs

This preserves the “no shadow SSOT” rule.

## 13. Error handling and safety

The mechanism should avoid these failure modes:

1. declaring debt resolved when it is only scheduled
2. allowing stale debt items to silently inflate health
3. letting critical debt bypass phase gates without explicit acknowledgment
4. storing debt evidence only in narrative docs without structured object linkage

## 14. Testing and verification

Verification of the mechanism should cover:

1. lifecycle state correctness
2. metric computation correctness
3. entropy decomposition correctness
4. gate escalation rule correctness
5. summary derivation correctness
6. pointer integrity and stale-ref detection
7. dashboard / review pack output correctness

## 15. Success criteria

This design is successful when:

1. debt becomes a first-class structured governance object
2. `.omo` can show debt by dimension, severity, age, entropy, and coupling
3. the system stops conflating “scheduled” with “resolved”
4. health and entropy signals become auditable and dynamically refreshed
5. high-risk debt can progressively upgrade into real governance gates
6. `.omo` governs debt without replacing project-local truth
