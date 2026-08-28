---
schema: bet-retro/v1
bet_id: BET-Y1Q3-T6-15
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-28
---

# BET-Y1Q3-T6-15 R1 retro

R1 was rebuilt from the actual GitHub main SHA rather than a moving local
tracking ref. Existing templates registry/baseline work was recognized as
already resolved; only the remaining ADR and tracked-artifact failures were
changed.

- Base: `591540105c446b44faab0b185bd33ae1ea58586a`
- Registry: 519/519, PASS
- ADR coverage, compile, conflict scan, hygiene and diff check: PASS
- No Documents content, host plist, scheduler, user data or gitlink changed
- Host retention and personal value remain `UNPROVABLE` / `NOT_PROVEN`

The next admissible phase is H1 only after this R1 branch is merged and a real
main `gac-gate` canary succeeds.

R1 strict gate disposition: repository checks pass, but mainline
`doc-governance --no-new-warnings` remains blocked by 104 legacy warnings and
one exceeded exception budget; `bet-ledger lint` reports 37 historical
completion evidence mismatches. These remain separate governance debt and no
budget/evidence was falsified to claim green.
