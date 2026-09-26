---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-5.3 Closeout Retro — A Declared Rule Is Not an Implemented Rule"
bet_id: BET-Y2Q4-SH-5.3
created: "2026-09-26"
run_id: 20260926T084606Z-project-code-change-772ad14a
---

# BET-Y2Q4-SH-5.3 Closeout Retro

> **TL;DR**: `bin/ssot/workflow-scene-map.yaml` declares `default:` plus
> `fallback_resolution: default` and documents "rule 3: otherwise fall back to
> default", but its only consumer read `scene_map["map"]` and nothing else.
> Measured on `origin/main@a3b4852a5`: 26 registered workflows, 19 map entries,
> **7 workflows dropped their closeout episode on every run**. SH-5.2 had made
> that drop loud; this bet made it not happen.

## Deliverables

- `bin/agent-workflow.py` — `_scene_card_from_map(scene_map, workflow_id) ->
  (path, notice)`: `map:` first, then `fallback_resolution: default` feeding
  `default:`, empty path = unresolved. `_bridge_closeout_to_scene` now calls it,
  bails with the resolver's own notice, and prints an `[INFO]` line on every
  fallback hit so a resolved-by-default closeout stays distinguishable from a
  direct hit.
- `tests/test_scene_outcome_episode_bridge.py` — 6 resolver cases (direct hit,
  fallback hit, no `fallback_resolution`, `fallback_resolution` naming an empty
  `default:`, blank map entry behaves like an absent one, unusable scene map,
  fallback-hit vs unresolved-bail). Plus repair of 4 stale end-to-end
  assertions, described under Q2.
- `docs/superpowers/specs/2026-09-26-scene-map-fallback-gap.md` — the
  measurement, the consumer snippet proving `default:` was never read, and the
  three-rule contract.
- `docs/plans/3y-bet-ledger.yaml` — `BET-Y2Q4-SH-5.3` registered via
  `bin/gac/ledger-safe-insert.py` (475 bets, no pre-existing entry modified).

## Q1 — What was intended

Close the gap between what the scene-map SSOT declares and what its consumer
implements, without touching the map data (assigning scene cards to the 7
workflows is the scene-card owner's call), and prove all four resolution paths
hermetically instead of by narrating a closeout.

## Q2 — What actually happened

The resolver is ~30 lines and the fix was not the hard part. Two things surfaced
while verifying:

1. **The bet's own verify command was unsatisfiable as written.**
   `pytest tests/test_scene_outcome_episode_bridge.py -q` → `expect: exit 0`,
   but the file was already red on `origin/main`: 4 of its 6 end-to-end cases
   failed before this branch existed. Proven by running main's unmodified copy
   of the file in this worktree: same 4 failures. Root cause: the file was
   written in #3747 (W2-05), and SH-5 (#4363) later added a *second* writer of
   the same event type. The tests filtered on
   `broker.read(event_type=EVT_OUTCOME_HUMAN)` with no further scope, so they
   began counting the recorder's own row as if it were the episode landing —
   `assert len(rows) == 1` became 2, and "non-personal scene writes nothing"
   became false. **Nothing in CI catches this**: the file is in no CI surface
   (`integration.yml` runs `projects/omo/tests/integration/`, `governance-check.yml`
   names one other root test), so the red was local-only and invisible.
2. **The recorder mirrors every adjudication.** Measured directly (fresh tmp
   DB, no kernel episode at all): a non-personal scene and a
   bridge-ineligible episode each still produce one `Outcome.Human.v1` row with
   `producer: omo-personal-episode` and `payload.source: scene-outcome-bridge`,
   carrying a synthetic dashed `episode_id` that is not a kernel episode. The
   kernel row is separately identifiable by `feedback_id` /
   `outcome_feedback_schema` in its payload.

So the delivered diff is the resolver plus assertions that state which of the
two rows they mean: `_kernel_outcomes()` (has `feedback_id`) for anything
claiming an episode landed, `_scene_mirror_outcomes()` for the recorder's own
trail, and an explicit `len(_outcomes()) == 2` in the golden path so the
two-layer write is documented rather than averaged away.

Verified against production data before writing any test: 26 registry workflow
ids → 19 direct hits, 7 fallback hits, 0 unresolved, and every resolved card
exists on disk. Each of the four negative shapes returns an unresolved notice.

## Q3 — What changed as a result

- Closeouts of `agent-onboarding`, `round-type-router`, `scene-execution`,
  `scene-lifecycle`, `state-sync`, `submodule-pointer-bump`,
  `submodule-pointer-close` now reach the scene recorder instead of bailing.
  That is 7/26 of registered workflows, and it will keep covering workflows
  added later that nobody mapped — which is the reason to implement the fallback
  rather than add 7 map entries that re-drift on the next addition.
- A fallback hit is loud (`[INFO]`), so "mapped" and "covered by default" stay
  separable from the ledger of stderr alone.
- The bridge stayed non-blocking in every path: no resolver branch raises, and
  an unusable scene map still ends in a named `[WARN]` bail.
- `tests/test_scene_outcome_episode_bridge.py` exits 0 (12 passed) and now
  distinguishes recorder emission from episode landing — which the version on
  main cannot do.

## Q4 — Lessons

- **A declaration in an SSOT is not a behaviour.** `fallback_resolution:
  default` sat in the file for its whole life with exactly one consumer, which
  ignored it. When a spec-style file states resolution rules, grep the
  consumers and read what they actually index — the diff between the declared
  rule set and the implemented one is a defect class, not documentation noise.
- **Never write a bet's `verify` from the intent alone; run it against the base
  first.** A green-expecting command on a file that is already red makes the
  contract unsatisfiable, and mid-flight the only ways out are all bad:
  silently narrow the command, or fix someone else's assertion without saying
  so. Baseline the verify commands on `origin/main` at `start` time.
- **An unscoped event-type filter is a proxy waiting to be wrong.** SH-5.2 was
  opened because a probe asserted on a producer label; this is the same shape
  one layer down — the same `source` label now appears on rows written by two
  different steps. Counting rows by type is only sound while exactly one writer
  emits that type.
- **Test debt invisible to CI is still debt.** Local-only red that every agent
  walks past becomes the accepted background noise that hides the next real
  failure.

## verify precondition discovered during execution

`pytest tests/test_scene_outcome_episode_bridge.py -q` on `origin/main` = 4
failed / 2 passed (measured, not inferred). The repair is test-only, inside the
bet's declared write surfaces, and touches neither `workflow-scene-map.yaml`
nor `scene-outcome-recorder.py`, so the circuit breaker held.

## Follow-ups reported, not fixed (principal scope)

1. **SH-5.2's probe still cannot see a failure inside the recorder.**
   `check-episode-pipeline.py` counts `payload.source ==
   'scene-outcome-bridge'`, and that label is on the *mirror* row, which the
   recorder writes before the kernel landing. So `ok` proves "the bridge was
   called", not "an episode received the outcome" — the residual blind spot is
   narrower than SH-5.2's own retro implies, but it is real. Candidate
   `BET-Y2Q4-SH-5.4`: count rows that carry `feedback_id`.
2. **SH-5.2's recorded evidence inherits that reading.** Its ledger
   `value.note` cites "10 event_log rows across 5 closeout correlation_ids"
   measured through the mirror, and the counts are volatile. No backfill; flag
   for the principal.
3. `PRODUCER = "scene-outcome-recorder"` at `bin/ssot/test-episode-bridge.py:33`
   is still dead (its only occurrence; the assertions use
   `omo-personal-episode`) — unchanged here.
4. These 7 workflows now resolve to `scenes/agent-workflow-closeout.yaml` by
   default. Whether that card is the *right* scene for e.g. `state-sync` is the
   scene-card owner's decision; a `map:` entry added later overrides it with no
   code change.
