---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-5.2 Closeout Retro — The Probe Measured a Proxy"
bet_id: BET-Y2Q4-SH-5.2
created: "2026-09-26"
run_id: 20260926T055953Z-project-code-change-11704717
---

# BET-Y2Q4-SH-5.2 Closeout Retro

> **TL;DR**: SH-5 was recorded `done` on a probe that could not have detected the
> failure it claimed to exclude. The probe asserted on a producer label that
> `scene-outcome-recorder` stamps on *every* row by design, so it stayed green no
> matter who wrote the row. Measurement says the bridge was never dead — it had
> written 10 events across 5 closeouts. What was broken was the verification, and
> SH-5.2 fixed the verification.

## Deliverables

- `bin/gac/check-episode-pipeline.py` — `ok` re-bound to
  `payload.source == 'scene-outcome-bridge'`; `bridge_event_count` /
  `bridge_closeout_count` surfaced; `--self-test` added carrying the two fixtures.
- `bin/agent-workflow.py` — `_bridge_closeout_to_scene` names a reason at all 7
  bail-outs instead of returning silently.
- `bin/ssot/scene-outcome-recorder.py` — `_warn_write_failure()` at the two
  write-attempt swallow sites; absent-kernel sites deliberately left quiet.
- `docs/plans/3y-bet-ledger.yaml` — SH-5.2 registered, `done_when` #2 revised
  under its own escape clause, `verify` preconditions stated.
- `docs/superpowers/specs/2026-09-26-episode-pipeline-verification-gap.md` — accepted spec.
- PR #4377.

## Q1 — What was intended

Close the gap between SH-5's recorded `done` and its machine-checkable first
done_when criterion, which read 0 rows of `producer=scene-outcome-recorder` even
after PRs #4368/#4369/#4370 landed. Appetite 2 days; actual ~1 session.

## Q2 — What actually happened

The premise of SH-5's criterion was wrong, and SH-5.2's goal text inherited that
error. Measured against `runtime/omo/event-ledger.sqlite3`:

| quantity | value |
|---|---|
| `event_log` rows | 13 |
| rows with `payload.source = 'scene-outcome-bridge'` | 10 |
| distinct closeout `correlation_id`s among them | 5 |
| rows with `producer = 'omo-personal-episode'` | 12 |
| rows with `producer = 'scene-outcome-recorder'` | 0 |

`scene-outcome-recorder.py` sets `episode_producer = "omo-personal-episode"` on
purpose: `PersonalEpisodeService.observe_principal` filters on exactly that
string. So `producer='scene-outcome-recorder'` was never reachable — the
criterion was unsatisfiable, not merely unmet.

Two consequences worth naming:

1. **The guard could not fail.** `ok = episode_count >= 1` is satisfied by any
   episode row from any writer. Proved by mutation: on a fixture with 6 proxy
   rows and 0 bridge rows, the pre-SH-5.2 probe returns `ok=True`, the re-bound
   probe returns `ok=False`.
2. **The silence was real.** When the scene map briefly held two YAML documents
   in one stream, `_bridge_closeout_to_scene` hit `except Exception: return` and
   printed nothing. A malformed map and an idle closeout were indistinguishable
   from the outside.

## Q3 — What changed as a result

- The probe now asks "did the bridge write?" rather than "does the label exist?".
- Every bridge bail-out prints a reason; the recorder's swallowed write failures
  print what they swallowed. Neither change alters control flow.
- `--self-test` carries the case the old predicate could not express, so a future
  rebinding back to a producer-only proxy turns red on its own.
- North-star `personal_value` reads `collecting` (was `not_ready`) with
  `operational_proof: proven`.
- No `governance-checks.yaml` rule changed; the probe stays warn-only and is not
  wired into `make gac-local-gate` or any CI surface (0 registry/CI references),
  which is what let it be rebound without moving the shared gate's exit code.

## Q4 — Lessons

1. **A check is only as good as its discriminator.** Before trusting a guard, ask
   which *other* states would also satisfy it. If the answer is "most of them",
   the guard is decoration.
2. **`done` on a ledger is a claim about a measurement, so the measurement has to
   be re-runnable.** SH-5 stayed `done` because nobody re-ran its criterion after
   the merge. The re-run is cheap; the correction cost a whole follow-up bet.
3. **Quote the field, not the story.** The search for "0 recorder rows" produced a
   confident wrong conclusion ("the bridge never writes"). The correct query was
   one JSON path deep into `payload_json`.
4. **`bin/` is quota-governed and the escape is a registry edit.** A standalone
   `test-*.py` was rejected by `script-registry validate` and
   `check-bin-quota-diff` at once; the only waiver lives in
   `governance-checks.yaml`, which this bet's circuit breaker forbids touching.
   Under that constraint, co-locating the guard with the guarded script was the
   quota-neutral move — and the better one: the invariant and its test now change
   together or not at all.
5. **Scope discipline paid.** SH-5's discrepancy could have been reopened, or
   absorbed into SH-6 whose scope SH-5.1 had already reserved. A sub-numbered
   follow-up with its own done_when kept the historical records honest.

## Recorded trace (satisfies done_when #3)

A scene map holding two YAML documents now surfaces as, instead of silence:

```
[WARN] SH-5 bridge emitted no episode: scene map unparseable:
ComposerError: expected a single document in the stream
  in "<unicode string>", line 1, column 1:
    map:
    ^
but found another document
  in "<unicode string>", line 3, column 1:
    ---
    ^ (run=20260101T000000Z-case-c-00000000)
```

Reproduced by driving `_bridge_closeout_to_scene` against a temp workspace whose
`bin/ssot/workflow-scene-map.yaml` holds a two-document stream.

## verify precondition discovered during execution

`check-episode-pipeline.py` and `north_star_meter_v2.py` both default to
`runtime/omo/event-ledger.sqlite3`, which is gitignored. In a fresh worktree the
first reports `ledger db missing` (exit 0, warn-only) and the second exits 2 with
`event_ledger_missing`. Neither failure was caused by this change; the ledger
`verify` entries now state the precondition instead of implying `exit 0` always.

## Follow-ups reported, not fixed (principal scope)

1. `bin/ssot/test-episode-bridge.py:33` defines `PRODUCER = "scene-outcome-recorder"`
   and never uses it — the real assertion at `:157` checks `omo-personal-episode`.
   Likely origin of SH-5's mis-stated metric.
2. `bin/ssot/workflow-scene-map.yaml` declares `default:` and
   `fallback_resolution: default`, but the consumer only reads `scene_map["map"]`;
   the documented fallback has no implementation.
3. Episode evidence lives under `.omo/_knowledge/workflow-mesh/`, excluded by
   `.gitignore:23` as "高频 churn, 非治理 SSOT". It is per-checkout runtime state,
   so it evaporates with the worktree that produced it.
