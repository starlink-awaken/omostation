---
schema: md/v1
status: active
lifecycle: report
owner: governance-agent
last-reviewed: 2026-09-28
type: report
---

# release-diagnose Closeout

## Delivered

`bin/gac/gac-worktree.sh release-diagnose <session>` is a read-only preflight that classifies release blockers and returns deterministic exit codes:

- `0`: clean and inspectable
- `1`: inspectable with findings
- `2`: worktree or metadata cannot be inspected

## Verification

- `bash -n bin/gac/gac-worktree.sh`: passed.
- `bash tests/test_gac_worktree_release_diagnose.sh`: passed; clean, dirty-root, dirty-submodule, and missing-session cases.
- `python3 -m pytest tests/test_gac_worktree_lifecycle.py tests/test_gac_worktree_lifecycle_submodule.py -q`: 30 passed.
- `release-diagnose --help`: passed and left Git status unchanged.

## Blocked verification

`make gac-local-gate` was executed and returned non-zero in the isolated worktree. Failures were pre-existing environment/incomplete-checkout conditions: missing cockpit-ui build assets, missing Cockpit/Agora/ECOS files, and missing pinned OMO workflow packet compiler. No failure pointed to the changed shell path or focused tests.

The required workflow start also returned `WORK_PACKET_COMPILER_UNAVAILABLE` from the pinned OMO checkout. This is recorded as a governance/runtime prerequisite blocker, not hidden or retried blindly.

## Cleanup

No release/reset/clean action is performed by the new command. The implementation worktree remains isolated until the branch is reviewed and integrated.
