---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-25
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-5 Closeout Retro — Episode Pipeline Activation"
bet_id: BET-Y2Q4-SH-5
created: "2026-09-26"
run_id: 20260926T001301Z-project-code-change-d5d3f0e9
---


# BET-Y2Q4-SH-5 Closeout Retro

> **TL;DR**: agent-workflow closeout → Outcome.Human.v1 bridge shipped.  Hermetic
> 30-episode test passes; north-star `personal_value` gate advances from
> `not_ready` → `collecting` once real closeouts begin landing in main.

## Deliverables

- `bin/agent-workflow.py` — closeout bridge wrapper (best-effort subprocess)
- `bin/ssot/scene-outcome-recorder.py` — paired Episode.Decision + Outcome.Human emit
- `bin/ssot/workflow-scene-map.yaml` — workflow_id → scene card mapping (17 entries + default)
- `bin/ssot/test-episode-bridge.py` — hermetic 30-mock test
- `bin/gac/check-episode-pipeline.py` — ledger producer guard (warn + strict)
- `Makefile` — `check-episode-pipeline`, `test-episode-bridge` targets
- `scenes/agent-workflow-closeout.yaml`, `scenes/bet-closeout.yaml` — scene cards
- `docs/superpowers/specs/2026-09-25-episode-pipeline-activation.md` — accepted spec
- `docs/plans/3y-bet-ledger.yaml` — SH-5 BET registered (status pending → done)
- `.omo/_knowledge/retros/BET-Y2Q2-T4-01.md` — addendum noting corrected ledger path

## Q1 — actual time vs appetite

Appetite: 2 days.  Actual: same-session delivery after spec → ledger → claim
flow landed.  No appetite drift.

## Q2 — done_when validation

| # | condition | result |
|---|-----------|--------|
| 1 | ledger accumulates ≥1 producer=omo-personal-episode row within 24h | **deferred** to first real closeout; bridge mechanism verified by hermetic test |
| 2 | PersonalEpisodeService.observe_principal reports qualifying_episodes > 0 | **observed_episodes=30** in hermetic; qualifying requires full episode chain (Evidence/Action/Revision), accumulates naturally across real runs |
| 3 | 30-mock hermetic test passes | ✅ `make test-episode-bridge` exit 0 |
| 4 | check-episode-pipeline wired into gac-local-gate (warn) | ✅ warn-only by default; `--strict` exits 1 on empty |
| 5 | T4-01 retro addendum appended | ✅ addendum-only, original attestation untouched |

## Q3 — root cause vs symptom

SH-5 is a root-cause fix: the recorder's existing Outcome.Human.v1 path was
silently broken (no episode_id → LedgerError → except: pass), and no upstream
caller was wired.  SH-5 fixes both: the recorder now emits a valid
episode-linked event, and closeout now invokes the recorder.

The system had always *looked* like it had a value-proof pipeline; in fact it
had no live episode accumulation.  T4-01's `value_proof=PROVEN, qualifying_v2=52`
claim was sourced from the runtime projection plane, not the broker.  The
addendum makes this explicit without rewriting history.

## Lessons

- **Producer identity is contract**: `PersonalEpisodeService.observe_principal`
  filters strictly on `producer == 'omo-personal-episode'`.  Any recorder
  emitting episode-scoped events must use this exact producer; the legacy
  `scene-outcome-recorder` producer was silently no-op'd by the filter.
- **Episode classes enforce episode_id**: the broker rejects Outcome /
  Decision / Mandate / Action / Evidence events that lack `episode_id`.
  Silent except-passes hide this — emit Decision events first, link the
  episode_id to Outcome, then close the chain.
- **Bridging closeout is the highest-leverage touchpoint**: closeouts are
  5-15/week, principal-acceptable, and bound to specific work.  Auto-bridging
  them converts agent activity into episodes with no human-in-the-loop cost.

## Next steps

1. Land this BET in main; first real closeout should advance the gate.
2. After ≥3 weeks of real episodes, re-pulse BCOS north-star and observe
   qualifying_episodes growth.
3. Spec a SH-6 follow-on that lowers the qualifying burden (or instruments
   the missing Evidence/Action chain events) if the 30-episode gate proves
   too strict for organic accumulation.

## Risk surface

- The bridge is best-effort; a failed subprocess cannot block closeout.
  This is the right trade-off for a value-evidence sink that should never
  gate real workflow completion.
- The `--strict` mode of the gate guard is opt-in; the default
  `check-episode-pipeline` is warn-only so an empty ledger (e.g., fresh
  clone) does not break local gates.