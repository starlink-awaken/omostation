---
schema_version: report/v1
type: report
title: W0 Portfolio v2 dogfood canary receipt
bet_id: BET-Y1Q4-T1-09
status: archived
lifecycle: evidence
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
value_indicator_policy: false
---

# W0 Portfolio v2 Dogfood Canary Receipt

> Engineering evidence only. `value` axis remains **NOT_PROVEN**. No personal
> decision outcome. No W1–W6 created.

## Immutable tree

| Ref | Value |
|---|---|
| Worktree tip (pre-PR) | recorded at closeout |
| Spec | `docs/superpowers/specs/2026-09-03-w0-portfolio-dogfood-canary-design.md` @ `sha256:01a55448c6a923ce5366ee53099308aefa47d8ff951aeb4e6b0797c5ad092e51` |
| Canary tests | `tests/test_bet_portfolio_canary.py` @ `sha256:8abdd474b1813d086d4ecd31df6866446e4cc928c2cd83ce556c7a9d0391074b` |
| Workflow run | `20260904T123031Z-bet-execution-feba75ca` |

## Positive chain (fixture)

Isolated ledger fixture exercises:

Vision → Objective/KR → Campaign/Milestone → child BET → Spec binding →
completion matrix → retro marker → derived Milestone met → parent-close block.

- `pytest tests/test_bet_portfolio_canary.py -q` → **12 passed**
- `value_indicator_policy=false` and value axis `NOT_PROVEN` asserted on every bet
- Projection `source_digest` stable across two renders of identical bytes

## Negative matrix (typed fail)

| Code | Mutation | Expected |
|---|---|---|
| OBJECTIVE_BINDING | drop OBJ-TRUST | Milestone false-close |
| KR_BINDING | empty KR list | Milestone false-close |
| KR_UNPROVEN | KR status unmeasured | Milestone false-close |
| COVERAGE_BET | canary child → candidate | Milestone false-close |
| SPEC_DIGEST | corrupt content_digest | digest mismatch |
| COMPLETION | overall_state evaluating | incomplete matrix |
| RETRO | drop retro marker | missing retro field |
| VISION_VERDICT | omit human_final_verdict | Vision false-close |
| PARENT_CLOSE | product child incomplete | parent Milestone blocked |
| PROJECTION_POISON | flip fixture byte | digest changes |
| W1_W6_ABSENT | fixture scan | only MS-W0- / CMP-W0- |

Original fixture bytes restored / re-materialized after each mutation; no production Ledger write.

## CLI / Cockpit projection parity

| Surface | Result |
|---|---|
| Cockpit `portfolio status` | `unavailable` / `missing_control_projection` (T1-08 broker gap) |
| Control JSON | absent — no invented fallback |
| Markdown projection | regenerated via `portfolio project-goals --apply-markdown` at closeout |

Digest parity on the live control plane is **unavailable↔unavailable** until
`portfolio-status.json` gains a registered broker. Canary fixtures prove digest
stability without writing `.omo/_control`.

## KR evidence (value-exempt)

| KR | Status after canary | Evidence |
|---|---|---|
| KR-TRUST-CHAIN-COVERAGE | proven | this report + canary tests + W0 child retros |
| KR-HOLDABILITY-ORPHAN-BETS | proven | portfolio coverage/lint + enforced bindings + canary |

These KRs measure infrastructure holdability/coverage — not personal value.

## Clone / replay notes

- Child-first evidence for T8-05 already on main (`fd884f36` / root `#3107`)
- Post-merge: exact-SHA replay via required checks on this PR
- Canonical clone cleanup: worktree retire after merge

## Rollback

Remove only canary test/report/status command if false-green. Do not delete
child retros or durable governance evidence.
