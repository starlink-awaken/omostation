# Phase 6 Wave 3 execution plan

> Status: completed packet
>
> Goal: `G6.3` skill federation

## Objective

Bridge AI-native skills into the same governed task runtime used by normal OMO packets.

## What Wave 3 landed

1. **Skill manifest truth**
   - manifests persisted under `.omo/_truth/task-center/skills/`
   - worker bridge, write scope, and delivery contract are explicit
2. **Governed skill packet bridge**
   - skill requests materialize into schema-valid blocked task packets
   - generated packets inherit source docs, deliverables, and runtime guardrails
3. **Runtime continuity**
   - skills no longer require an out-of-band scheduler contract
   - federation stays inside the same worker/task/governance chain

## Verification

1. `python3 -m pytest .omo/tests/test_omo_skill.py -q`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`

## Exit judgment

Wave 3 is complete when a skill can be registered as truth and translated into a governed task packet without inventing a parallel execution system.
