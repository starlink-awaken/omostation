---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T10-44
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# OMO root gitlink reachability recovery

## Objective

Restore the root repository's `projects/omo` gitlink to the authoritative child
`origin/main` without changing child source code, other gitlinks, runtime state,
or user configuration. The recovery exists because root governance verification
currently reports the pinned child commit as `DIVERGED` and not present on child
`origin/main`, which blocks otherwise unrelated root pull requests.

## Contract

- The only root implementation surface is `projects/omo`.
- The target is the exact commit resolved from the authoritative child
  `origin/main` during preflight; it must be reachable and fetchable in a fresh
  recursive clone.
- The child repository is not modified in this BET.
- No other root gitlink, source file, workflow, registry, runtime artifact,
  crontab, LaunchAgent, or Documents file may change.
- Acceptance is based on content/tree reachability and fresh-clone evidence,
  not on local child checkout state alone.

## Done when

- `projects/omo` points to the authoritative child `origin/main` commit.
- Full recursive clone and child reachability checks succeed.
- `check-submodule-pointer-drift.py` reports no divergence or unreachable pin.
- `make governance-release-gate` and the relevant root governance checks pass.
- The recovery PR carries an exact before/after pointer receipt and rollback is
  the previous root gitlink commit.

## Non-goals

- No child source implementation or child branch rewrite.
- No changes to unrelated gitlinks, BET status, completion/value evidence,
  schedules, host processes, or Documents content.

## Verification

```bash
git ls-tree origin/main projects/omo
python3 bin/gac/check-submodule-pointer-drift.py --json
python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main --json
make governance-release-gate
```
