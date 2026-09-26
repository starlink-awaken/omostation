---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-5.1 Closeout Retro — Episode Pipeline Principal-ID Normalization"
bet_id: BET-Y2Q4-SH-5.1
created: "2026-09-26"
run_id: 20260926T032835Z-project-code-change-991698be
---


# BET-Y2Q4-SH-5.1 Closeout Retro

> **TL;DR**: SH-5 closed the closeout → episode bridge but emitted events with
> bare `xiamingxing` principal_id, silently filtered out by
> PersonalEpisodeService. SH-5.1 normalizes to `principal:xiamingxing` at
> the recorder boundary, unblocking north-star `personal_value: collecting`.

## Deliverables

- `bin/ssot/scene-outcome-recorder.py` — new `_canonical_principal_id()` helper
- `bin/ssot/test-episode-bridge.py` — seeded sovereignty uses canonical form
- `docs/superpowers/specs/2026-09-26-episode-pipeline-principal-normalization.md` — accepted spec
- `docs/plans/3y-bet-ledger.yaml` — SH-5.1 registered, `meta.total_bets: 473`

## Q1 — actual time vs appetite

Appetite: 0.5 day.  Actual: same-session delivery after SH-5.1 was
recognized as a silent-failure root cause.  No appetite drift.

## Q2 — done_when validation

| # | condition | result |
|---|-----------|--------|
| 1 | recorder emits Episode.Decision.v1 + Outcome.Human.v1 with `principal_id` matching canonical `principal:<id>` form | ✅ verified: live ledger rows 4–5 carry `principal_id='principal:xiamingxing'` |
| 2 | test-episode-bridge asserts under canonical principal | ✅ `total_episodes=5, readiness=collecting` |
| 3 | live north-star pulse shows `status=collecting, episodes > 0` | ✅ direct pulse: `personal_value: collecting, gate_gaps=['no_qualifying_weeks']` |

## Q3 — root cause vs symptom

The previous SH-5 retro called out "declared ≠ executed" as the strategic
diagnosis.  SH-5.1 narrows it to the concrete filter mismatch: the
recorder passed through `OMO_PRINCIPAL_ID` verbatim while sovereignty
strict-enforces `principal:<id>` form.  PersonalEpisodeService observes
exactly the canonical form, so emitted events landed in the broker but
were invisible to the readiness gate.

The fix is one line at the boundary — but the systemic lesson is more
valuable: **string-typed identifiers with strict prefix conventions
need boundary normalization at every emit site, not just trust in the
caller**.  SH-6 may audit all `OMO_PRINCIPAL_ID` callers.

## Lessons

- **Cross-boundary type coercion**: when one side emits strings and the
  other side filters strings, even small syntactic differences
  (`xiamingxing` vs `principal:xiamingxing`) silently kill the contract.
  Emitting sites must canonicalize.
- **Hermetic test caught the mismatch**: the SH-5 hermetic test passed
  with bare `xiamingxing` because the test seeded sovereignty with the
  same bare form.  SH-5.1 seeds sovereignty with the canonical form to
  detect future regressions.
- **Producer identity was correct in SH-5** but principal identity was
  not — easy to miss because the bridge test only counted rows under
  whatever principal it happened to use.

## Next steps

1. Land this BET in main; live north-star will accumulate qualifying
   episodes naturally on subsequent closeouts.
2. SH-6 candidate: audit all OMO_PRINCIPAL_ID callers across `bin/`,
   `projects/`, and modules for canonical-form usage; consider a
   centralized helper to enforce.
3. After ≥3 weeks of real closeouts, re-pulse BCOS and observe
   `gate_gaps` shrink from `no_qualifying_weeks` to ready.