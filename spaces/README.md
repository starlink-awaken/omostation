# spaces/

`spaces/` is the workspace home for **user-space and tenant-space manifests**.

It is intentionally separate from:

1. `.omo/` — governance/control/control-truth
2. `projects/*` — capability code and execution runtimes
3. `data/` — shared data substrate
4. `runtime/` — ephemeral local runtime state

## What belongs here

1. space manifests
2. tenant or workspace boundary metadata
3. routing references from a space to a project or data owner
4. asset indexes or ownership pointers

## Phase 9 baseline objects

1. `registry.yaml` — workspace-level registry of known spaces
2. `_schema/space-manifest.schema.yaml` — contract for space manifests
3. `system-space.yaml` — first system-owned workspace space manifest

## Phase 9 Wave 3 contract objects

1. `_schema/space-identity-admission.schema.yaml` — actor + space membership identity anchor contract
2. `system-space-identity-admission.yaml` — first system-space identity / capability / admission baseline
3. `system-space-capability-taxonomy.yaml` — first machine-checkable action taxonomy for system-space
4. `system-space-admission-matrix.yaml` — first admission decision matrix for cross-root actions

## Phase 9 Wave 4 contract objects

1. `system-space-rollout-policy.yaml` — first system-space rollout / acceptance policy

## What does not belong here

1. governance state and phase truth
2. project source code
3. high-volume databases or snapshots
4. ephemeral runtime logs or pid files
