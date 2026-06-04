# Phase 9 Wave 4 execution plan

## Goal

Turn the Wave 1-3 workspace refactor into a usable operating baseline by proving one governed rollout / acceptance path, tightening runtime/ops boundaries, and closing Phase 9.

## Default exit bar

Because no human reply was available during the Wave 4 kickoff, the default exit bar is **single live path**:

1. rollout / ops contracts exist and are machine-checkable
2. one real `project.dispatch` path evaluates `allow`
3. one real acceptance record is written from the live envelope
4. Wave 4 and Phase 9 closeout docs are both recorded

## Scope

1. define the first rollout policy for `system-space`
2. define the first runtime boundary contract for operational residue
3. bind rollout policy + runtime boundary to a worker envelope
4. add rollout evaluation and acceptance CLI seams
5. prove one live acceptance path using the Wave 3 granted approval artifact
6. close Wave 4 and Phase 9 with retrospective judgment

## Deliverables

1. `spaces/system-space-rollout-policy.yaml`
2. `runtime/system-runtime-boundary.yaml`
3. `.omo/workers/runs/phase9-wave4-rollout-ops-envelope.yaml`
4. `.omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml`
5. `scripts/omo_rollout.py`
6. `.omo/plans/phase9-wave4-execution-plan.md`
7. `.omo/summaries/phase9-wave4-closeout.md`
8. `.omo/summaries/phase9-closeout-retrospective.md`

## Exit gate

1. rollout policy requires granted approval plus delivery evidence
2. runtime residue stays inside runtime-owned roots
3. `python3 scripts/omo_worker.py worker rollout-eval .omo/workers/runs/phase9-wave4-rollout-ops-envelope.yaml` returns `decision=allow`
4. `python3 scripts/omo_worker.py worker rollout-accept ...` writes an acceptance record and updates the envelope gate
5. Phase 9 control docs point to `current_phase: 9`, `phase_status: completed`, `current_wave: 4`
