# Phase 6 Wave 2 execution plan

> Status: completed packet
>
> Goal: `G6.2` discovery + templates

## Objective

Turn blueprint discovery and task template instantiation into governed runtime primitives without creating a second metadata truth.

## What Wave 2 landed

1. **Blueprint discovery registry**
   - frontmatter blueprint scan in `scripts/omo_discovery.py`
   - truth registry persisted at `.omo/_truth/task-center/discovery-registry.yaml`
2. **Template instantiation**
   - blueprint-to-task packet materialization
   - generated packets remain schema-valid and OMO-governed
3. **Control boundary**
   - discovery writes only to truth/task packet surfaces
   - execution still flows through the same task schema and worker runtime

## Verification

1. `python3 -m pytest .omo/tests/test_omo_discovery.py -q`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`

## Exit judgment

Wave 2 is complete when task blueprints can be discovered into truth and instantiated into valid governed packets without bypassing task schema or live control.
