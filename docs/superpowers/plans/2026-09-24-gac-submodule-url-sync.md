# Implementation Plan: GAC worktree submodule URL synchronization

> **Execution contract:** implement only the accepted spec for BET-Y2Q2-T11-02.

## Scope

- `bin/gac/gac-worktree.sh`: synchronize recursive submodule URLs inside a newly-created worktree before initialization.
- `tests/test_gac_worktree_claim_pasw.py`: add a behavioral regression test for stale local URL overrides.
- Governance SSOT: register the BET and bind this spec/plan.

## Steps

1. Add a fail-closed `git submodule sync --recursive` step immediately before the existing initialization branch.
2. Add a test that mutates a parent repository's submodule URL config to an invalid local path and confirms claim succeeds using `.gitmodules`.
3. Run shell syntax and the focused PASW test file.
4. Run governance verification for the claimed paths and close out with the evidence receipt.

## Acceptance criteria

- New worktrees do not inherit stale local submodule URL overrides during claim initialization.
- A synchronization failure stops claim before submodule checkout.
- Existing skip mode remains unchanged.
- No submodule gitlinks or child repository files change.
