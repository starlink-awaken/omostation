---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T1-14
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# OBJ-VALUE Portfolio Split — Design

## Problem

VISION-2029 is a **result-plane** promise (signal → signed output → remember edits),
but portfolio `required_objectives` only carried `OBJ-TRUST` and `OBJ-HOLDABILITY`.
Agents therefore optimize gates/DX while north-star metrics stay unmeasured.

## Decision

1. Add **`OBJ-VALUE`** with three KRs (all `unmeasured`, KR not `required: true`):
   - `KR-VALUE-JOURNEY-COMPLETION` — effective work journey completion rate
   - `KR-VALUE-WEEKLY-ADOPTION` — weekly principal-accepted suggestions (falsification meter)
   - `KR-VALUE-REVISION-RATE` — principal revision-rate baseline
2. Wire `OBJ-VALUE` into `vision.required_objectives`.
3. Add campaign **`CMP-Y1-VALUE-PROOF`**.
4. Split delivery into bets:
   - `BET-Y1Q4-T1-14` — register objective/KR/campaign (this change)
   - `BET-Y1Q4-T4-02` — journey-completion baseline
   - `BET-Y1Q4-T4-03` — weekly signal/adoption meter
   - `BET-Y1Q4-T4-04` — revision-rate baseline
   - `BET-Y1Q4-T4-05` — spine value-proof debt inventory (sample backfill)

## Non-goals

- Do not set `kr.required: true` (would trip `NONTERMINAL_BET_UNBOUND` on unbound candidates).
- Do not implement meters inside T1-14.
- Do not expand T8 DX surface in this campaign.

## Coverage rationale

T1-14 covers all three KRs as the **registration surface**.
T4-02/03/04 each exclusively implement one KR.
T4-05 covers all three as **debt governance**, with explicit `coverage_rationale`.

## Strategy refs

- `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` §0.3 / §2.2 / §8
- Falsification: ≥3 principal-accepted suggestions/week for 12 consecutive weeks by 2027-12-31
