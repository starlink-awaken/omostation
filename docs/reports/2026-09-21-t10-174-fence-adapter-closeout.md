---
title: BET-Y1Q4-T10-174 fence adapter contract repair — closeout receipt
type: report
bet_id: BET-Y1Q4-T10-174
status: completed
created: '2026-09-21'
run_id: 20260921T084356Z-project-code-change-57dcd804
---

# BET-Y1Q4-T10-174 Closeout Receipt

## Delivery

- Spec: `docs/superpowers/specs/2026-09-21-t10-174-fence-adapter-contract-repair-design.md` (digest `sha256:8784a5e527d64e40d6ca0bfae97748c8caa818dd0dc7deb1b00f75cb82e89aea`)
- PR: https://github.com/starlink-awaken/omostation/pull/4157 (squash-merged 2026-09-21T09:51:07Z)
- Merged reachable commit: `git://origin/main@d85f4124ac66d0fe85ae5c7055661a4d7a919aa8`

## Change surface

- `bin/gac/clone-lifecycle.py` — legacy publish fence adapter realigned to the canonical claims-authority broker contract:
  - `build_remote_observation_pair` emits the exact `claims-remote-observation/v2` 10-field record; absent remote refs use the canonical 40-zero OID; local stable-field/monotonic drift checks fail closed.
  - `_legacy_fence_context` resolves claim CAS values (claim_id / claim_version / lease_epoch / v1_allow_receipt_digest / v1_snapshot_digest / changeset_digest / path_digest / expected_remote_oid) from injected verification and rejects malformed context before any broker call (`LEGACY_FENCE_CONTEXT_UNAVAILABLE` / `LEGACY_FENCE_CONTEXT_INVALID:<key>`).
  - `enter_legacy_publish_fence` builds issue (exact 17 fields) + enter (exact 12 fields) requests and requires a non-empty `settlement_request_id`.
  - `settle_legacy_publish_fence` reuses the enter receipt `settlement_request_id` and carries remote_ref / observed_remote_oid / effect_process_identity_digest (exact 11 fields).
  - Canonical push argv unchanged byte-for-byte; pre-activation inert behavior unchanged.
- `tests/test_clone_lifecycle.py` — WP1 Wave B1 contract tests validating every adapter-built request against the real broker validators (`_REMOTE_OBSERVATION_FIELDS`, `_validate_remote_observation_pair`) plus fail-closed and replay cases.
- `docs/plans/3y-bet-ledger.yaml` — BET-Y1Q4-T10-174 registration with accepted-spec binding.

## Verification (engineering axis)

| Check | Command | Result |
|-------|---------|--------|
| Unit/contract tests | `uv run --with pyyaml --with pytest python -m pytest -q tests/test_clone_lifecycle.py` | 103 passed (incl. 12 b1 contract tests) |
| Compile | `python3 -m py_compile bin/gac/clone-lifecycle.py` | exit 0 |
| Governance gate | `uv run --with pyyaml python bin/gac/gac-local-gate.py --scope run --run-id 20260921T084356Z-project-code-change-57dcd804 --json` | `ok: true` (exit 0) |
| Ledger YAML | `python3 -c "import yaml; yaml.safe_load(...)"` + bet count/dup check post-rebase | OK, no duplicates |
| CI | PR #4157 checks (gac-local-gate, interface-check, evidence-smoke, test, contract-lint, security-scan, ...) | all pass, none fail |

## Operational axis

- live_canary: post-merge main carries the fixed adapter; the same contract suite runs against broker reference code unchanged (projects/omo not touched by this bet).
- fresh_receipt: this report.
- replay: `.omo/_knowledge/retros/BET-Y1Q4-T10-174.md`.
- cleanup: worktree `ws-fix-clone-lifecycle-fence-contract` released after closeout PR merge; no runtime state mutated, no lifecycle receipts fabricated.

## Rollback

`git revert` of merge commit `d85f4124ac66d0fe85ae5c7055661a4d7a919aa8` restores the prior adapter; the pre-fix code was itself inert pre-activation, so rollback risk is limited to losing the contract tests.

## Boundary notes

- No broker (`claims_authority.py`) semantics change. The v1-allow observe-receipt precondition for `issue-legacy-fence` remains structurally unreachable under the current v2 managed-clone identity (see `claims_authority.py` V1_AUTHORITY_FORBIDDEN managed_clone rule and `lifecycle.py` always-deny v1 adapter). Activation semantics are reserved for a principal decision surfaced separately.
