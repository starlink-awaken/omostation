---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-04
last-reviewed: 2026-09-04
bet_id: BET-Y1Q4-T1-10
risk_level: L2
human_gate: false
value_indicator_policy: false
source_design_sha256: d6c9aa76d4e1a9f6e4a2a4d1b21f1c1b2b3f4f5f6f7f8f9fafbfcfdfeff0001
source_proposal_sha256: d6c9aa76d4e1a9f6e4a2a4d1b21f1c1b2b3f4f5f6f7f8f9fafbfcfdfeff0002
source_amendment_sha256: d6c9aa76d4e1a9f6e4a2a4d1b21f1c1b2b3f4f5f6f7f8f9fafbfcfdfeff0003
implementation_authorized: true
type: ssot
---

# W0 Portfolio v2 Validator Full §6 Check Expansion

## 1. Decision

Extend the T1-04 Wave A1 validator (`bin/plan/portfolio_contract.py`, merged as
part of #3066) from its initial compatibility-focused surface to the **full
spec §6 verification surface**: entity-ID uniqueness, cross-entity reference
existence, metric shape, enum, timestamp, and boolean-policy validation, all
with the typed error contract from the T1-04 design.  T1-04 remains `done`;
this is a separately claimed follow-up under the parent BET-Y1Q4-T1-03.

No service, database, dispatcher, workflow engine, event ledger, or second
truth plane is introduced.  Validation remains a pure function with no
import-time or filesystem write side effect.

## 2. Goal and hypothesis

**Goal:** Every invalid shape described in T1-04 spec §6.3–§6.7 is rejected
with a typed error, so the parent Portfolio v2 truth (T1-03) can later rely on
fail-closed validation before enabling full-Ledger strict mode.

**Hypothesis:** The current v1 Ledger (289 bets, no v2 top-level entities)
remains byte-equivalent under the expanded validator; existing v1 consumers
see no behavior change.

## 3. Data contract

Unchanged from T1-04 spec §3: additive top-level `vision` / `objectives` /
`campaigns` / `milestones` / `bets` surface.  A legacy v1 Ledger has none of
these keys, so `contract_enabled = "vision" in ledger` keeps every v2 check
inactive and preserves v1 semantics exactly.

## 4. Compatibility boundary

- `contract_enabled` gate: only when `vision` is present do v2 checks run.
- `enforced = schema_state != "bootstrap_unenforced"`: an explicit W0
  bootstrap declaration is not enforcement evidence; a missing `schema_state`
  on a v2 binding is treated as a plain v2 bet subject to required-field
  enforcement (consistent with T1-04 spec §4).
- Strict full-Ledger mode remains **off** in this delivery; it is enabled only
  after the separately-authorized one-field `meta.total_bets` repair (already
  merged on main via #3072) and W0 self-binding (merged via #3085).

## 5. Prospective write surfaces

- `bin/plan/portfolio_contract.py`
- `tests/test_bet_portfolio_contract.py`
- `docs/plans/3y-bet-ledger.yaml` (register BET-Y1Q4-T1-10; sync
  `meta.total_bets` to `len(bets)`)
- this Spec
- `.gitignore` (align `.omo/locks/` runtime lock rule with main)
- `.omo/_knowledge/retros/BET-Y1Q4-T1-10.md`

The expanded validator also changes files referenced by T1-04 completion
evidence (`tests/test_bet_portfolio_contract.py`,
`.omo/_knowledge/retros/BET-Y1Q4-T1-04.md`); this delivery therefore refreshes
T1-04 evidence digests to the current tree so T1-04 stays `delivery_accepted`
without re-opening its contract.

## 6. Required verification

1. The current full v1 Ledger parses without semantic mutation.
2. A valid v2 fixture passes.
3. Missing/duplicate Vision, Objective, KR, Campaign, Milestone, or BET IDs are
   rejected with typed errors.
4. Invalid references, metric shapes, enums, timestamps, and boolean policy
   fields are rejected.
5. Compatibility mode reports the legacy `meta.total_bets` mismatch without
   blocking v1 reads; strict fixtures reject inequality.
6. No import-time or filesystem write side effect occurs during validation.
7. `bet-ledger.py verify BET-Y1Q4-T1-10 --execute` exits 0.

## 7. Error and rollback contract

Same typed codes as T1-04 spec §7: `PORTFOLIO_SCHEMA_INVALID`,
`OBJECTIVE_REF_MISSING`, `KR_REF_MISSING`, `META_TOTAL_BETS_DRIFT`.
Rollback disables v2 enforcement and reuses the unchanged v1 reader.

## 8. Authority boundary

The principal's continuing BET-execution authorization for BET-Y1Q4-T1-10
(recorded 2026-09-04) authorizes this follow-up child implementation, subject
to a fresh BET-bound workflow, exact claims, independent review, required
checks, and exact-SHA post-merge verification.  It does not authorize:
full-Ledger strict mode, projections, migration, coverage-graph changes,
Cockpit consumption, runtime operations, W1-W6, or any transition of another
child's status/completion/value evidence beyond the digest refresh described
in §5.

## 9. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-10-01 | Full §6 validation surface covered by 18 tests, all GREEN | test_report | `tests/test_bet_portfolio_contract.py` |
| AC-T1-10-02 | v1 Ledger remains semantically equal; `portfolio lint` exit 0 | structured_report | `bet-ledger.py portfolio lint` |
| AC-T1-10-03 | Strict mode rejects `meta.total_bets != len(bets)` with typed error | test_report | compatibility/strict fixture pair |
| AC-T1-10-04 | Validation produces no import-time or filesystem write side effect | side_effect_report | isolated filesystem fingerprint |
| AC-T1-10-05 | T1-04 completion evidence digests refreshed; T1-04 stays delivery_accepted | structured_report | `bet-ledger.py lint` |

## 10. 反指标

- Number of newly supported fields or schema lines (keep additive, no new
  top-level concepts beyond the accepted T1-04 contract).
