---
schema: md/v1
status: active
lifecycle: report
owner: governance-agent
last-reviewed: 2026-09-29
type: report
---

# release-diagnose Closeout

## Delivered

`bin/gac/gac-worktree.sh release-diagnose <session>` remains a read-only preflight with deterministic exit codes:

- `0`: clean and inspectable
- `1`: inspectable with findings
- `2`: worktree or metadata cannot be inspected

The classification is now metadata-backed:

- `[dirty-root]`: ordinary root changes, including ordinary `projects/*` files;
- `[gitlink]`: root index entry with mode `160000`;
- `[dirty-submodule]`: content changes inside an initialized recursive submodule;
- `[generated]`: explicit `.omo/*`, `docs/generated/*`, or `docs/cli/*` paths;
- `[invalid-pasw]`: configured PASW directory exists but is not an independent Git worktree;
- `[orphan-pasw]`: unconfigured direct `.subtrees/*` directory is not a valid Git worktree.

Root status uses NUL-delimited porcelain records. Rename/copy records consume the second path record and report only the destination, preserving spaces in paths.

## Verification

- `bash -n bin/gac/gac-worktree.sh`: passed.
- `bash tests/test_gac_worktree_release_diagnose.sh`: passed; precise categories, rename/space handling, and read-only before/after snapshots.
- `python3 -m pytest tests/test_gac_worktree_lifecycle.py tests/test_gac_worktree_lifecycle_submodule.py -q`: 30 passed.
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint`: passed; 503 bets, no errors.
- `git diff --check`: passed.

## Blocked verification

`agent-workflow verify 20260929T021821Z-project-code-change-33e17d57 --from-diff --execute` returned non-zero because:

- `pyright-sweep-check` could not import missing `bin/sweep/nested-with.py`;
- `gac-local-gate` could not build missing `projects/cockpit-ui/dist/index.html` because the checkout has no `projects/cockpit-ui/package.json`; it also reported pre-existing resident BOS and evidence-freshness baseline failures.

The local gate passed all listed checks related to the changed shell path; the failures above are checkout/runtime or baseline governance prerequisites, not focused-test failures.

## Scope

`release` behavior, JSON output, and PASW initialization depth were not changed. No release/reset/clean action is performed by the command.
