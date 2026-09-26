---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Episode Pipeline Principal-ID Normalization — fix SH-5 silent failure
bet_id: BET-Y2Q4-SH-5.1
---


# BET-Y2Q4-SH-5.1 — Episode Pipeline Principal-ID Normalization

## Context

PR #4363 merged the SH-5 closeout → episode pipeline bridge, but a
follow-up diagnostic (2026-09-26) revealed the bridge silently no-ops
in production:

```
sqlite> SELECT producer, principal_id, COUNT(*) FROM event_log GROUP BY producer, principal_id;
omo-sovereignty|principal:xiamingxing|1
omo-personal-episode|xiamingxing|2
```

The ledger has a sovereignty role-assignment keyed on the canonical
`principal:xiamingxing`, but SH-5 emits events with bare `xiamingxing`
(because `OMO_PRINCIPAL_ID` defaults to that).  `PersonalEpisodeService
.observe_principal()` filters strictly:

```python
rows = [
    row
    for row in all_rows
    if row.get("producer") == PERSONAL_EPISODE_PRODUCER
    and row.get("principal_id") == principal_id
]
```

So the two episodes never reach the principal filter and
`gate_gaps=['no episodes observed']` persists.  BCOS north-star status
remains `not_ready`.

## Root cause

`bin/ssot/scene-outcome-recorder.py:_write_event_ledger_outcome` reads
`OMO_PRINCIPAL_ID` directly without canonicalizing.  Sovereignty's
`_ID_PREFIXES['principal'] = 'principal:'` (in
`projects/omo/src/omo/sovereignty/roles.py:67`) requires the prefix.
This is the same kind of prefix mismatch SH-5 was supposed to fix at the
structural level — except SH-5 was scoped to bridge wiring, not
principal-id hygiene.

## Goal

Auto-normalize the principal_id passed to `surface.append()` in
`_write_event_ledger_outcome` so it always carries the `principal:`
prefix when the caller supplies a bare name.  Add a hermetic test that
asserts the recorded events are observable by
`PersonalEpisodeService.observe_principal('principal:xiamingxing')`.

## Non-goals

- Do not change sovereignty prefix constants.
- Do not refactor the broader OMO_PRINCIPAL_ID convention across all
  callers; SH-5.1 only fixes the bridge side (where episodes are
  emitted).  A follow-up SH-6 may normalize all OMO call sites.
- Do not alter ledger schema or broker.

## Done when

- `bin/ssot/scene-outcome-recorder.py:_write_event_ledger_outcome`
  calls a new helper `_canonical_principal_id()` that prepends
  `principal:` when the input does not already start with `principal:`.
- A live `agent-workflow.py closeout` followed by a north-star pulse
  reports `status: collecting` (not `not_ready`).
- `bin/ssot/test-episode-bridge.py` extends to assert that emitted
  events land under `principal:xiamingxing` and are observed by
  PersonalEpisodeService.

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- appetite: 0.5 day (small fix)
- risk_level: L1 (localized normalization, no ledger schema change)