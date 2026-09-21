---
schema_version: specification/v1
spec_version: 1.0.0
title: Dashboard write-integrity and synthesis recovery
bet_id: BET-Y2Q2-T8-04
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-21'
last-reviewed: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# Dashboard write-integrity and synthesis recovery

## Problem

The dashboard implementation already removed the duplicate workbench proposal
writer and added cross-domain synthesis lens cards, but the current source
retains an audit comment naming `ZhixingAdjudicateProposal`. The ledger's
machine-verifiable acceptance therefore reports one remaining occurrence
instead of the required zero. A later refactor also replaced the original
title-valued synthesis marker with a shared `cross-domain` marker, but the
marker assignment is not yet committed in the live dashboard checkout.

## Change

Keep the proposals tab and duplicate writer removed. Remove the stale
function-name audit comment while preserving the explicit note that the global
persona guidance bar is the sole write exception. Commit the existing
`data-synthesis-card="cross-domain"` assignment so the mounted stuck/value lens
cards remain discoverable after the synthesis-card refactor.

The implementation evidence is anchored to dashboard commits `4743384` (the
original write-integrity and synthesis change) and the final T8-04 recovery
commit created by this run. The dashboard repository is local-only and has no
remote; exact commit identity and post-recovery syntax checks are therefore the
authoritative deliverable evidence.

## Acceptance

- `workbench_ui.js` contains zero occurrences of `ZhixingAdjudicateProposal`.
- The removed proposals implementation remains absent.
- `ecosystem_ui.js` assigns `data-synthesis-card` to both synthesis lens cards
  at runtime and contains at least one source occurrence for verification.
- The concatenated eight core dashboard UI files pass `node --check`.
- The footer remains a truthful description of the sole write exception.
- Ledger lint and the focused governance checks pass.

## Non-goals

This does not change the global persona guidance write path, proposal storage,
API contract, Claims Authority lifecycle, runtime server configuration, other
BET entries, business value evidence, gitlinks, CI, or branch protection.

## Rollback

Revert the minimal T8-04 recovery commit. Because it only removes an obsolete
comment and preserves an already-authored marker assignment, rollback restores
the prior dashboard source without data migration or runtime mutation.
