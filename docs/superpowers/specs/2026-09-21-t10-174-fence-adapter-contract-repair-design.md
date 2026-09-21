---
schema_version: specification/v1
spec_version: 1.0.0
title: Clone-lifecycle claims-authority fence adapter contract repair
bet_id: BET-Y1Q4-T10-174
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-21'
last-reviewed: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
type: ssot
---

# Clone-lifecycle claims-authority fence adapter contract repair

## Problem

The 2026-09-21 Decision-4 lifecycle execution terminated at binding validation with zero
external effects. One measured root cause: the `bin/gac/clone-lifecycle.py` Wave B1 fence
adapter speaks a different contract than the canonical broker
(`projects/omo/src/omo/workflow/claims_authority.py`) enforces for
`issue-legacy-fence`, `enter-legacy-publishing` and `settle-legacy-publication`. Every
adapter-built request would be rejected before any state transition, so the post-activation
fence path defined by the WP1 design spec §6.4 is currently unexecutable.

Concrete defects (measured against the broker validators on 2026-09-21):

1. `build_remote_observation_pair()` emits `claims-remote-observation/v1` records with
   `remote_ref`/`observed_oid`/`expected_oid`/`effect_process_id` keys. The broker requires
   the exact `claims-remote-observation/v2` field set
   (`schema`, `repository_identity_digest`, `remote_ref_digest`, `observed_remote_oid`,
   `monotonic_ns`, `broker_observed_at`, `git_executable_digest`,
   `effect_process_identity_digest`, `command_digest`, `descriptor_digest`) with monotonic
   ordering and freshness bounds.
2. Absent remote refs are sent as the empty string; the broker rejects any
   `observed_remote_oid`/`expected_remote_oid` that is not 40 lowercase hex.
3. `enter_legacy_publish_fence()` sends `v1_decision: "allow"` as a request field
   (unknown to the broker), `head_sha` instead of `head_oid`, `claim_version` taken from
   broker `status.sequence`, `lease_epoch` not sourced from the claim row, and omits
   `claim_id`, `v1_allow_receipt_digest` and `path_digest`.
4. `settle_legacy_publish_fence()` mints a fresh `request_id`; the broker requires the
   `settlement_request_id` returned by the `enter` receipt. It passes a raw
   `effect_process_id` where a digest is required and omits top-level `remote_ref` and
   `observed_remote_oid`.

## Required behavior

- Remote observation records use schema `claims-remote-observation/v2` with the exact
  broker field set; digests are canonical (`sha256:<64 hex>`), `monotonic_ns` values are
  non-negative with first ≤ second, and `broker_observed_at` is written fresh at
  construction time.
- A not-yet-existing remote ref canonicalizes to 40 zeros (`0000000000000000000000000000000000000000`).
- `issue-legacy-fence` requests carry `claim_id`, `claim_version` and `lease_epoch` from
  the broker observation receipt for the same v1 snapshot, plus `head_oid`,
  `expected_remote_oid`, `path_digest`, `changeset_digest` and `v1_allow_receipt_digest`.
- The `enter-legacy-publishing` receipt's `settlement_request_id` is retained by the fence
  session and reused verbatim as the `request_id` of exactly one
  `settle-legacy-publication` request; settle carries `remote_ref`, `observed_remote_oid`
  and `effect_process_identity_digest`.
- The fence precondition stays fail-closed: a fence may only be issued when the broker
  observation receipt for the same snapshot records an effective v1 allow. Managed v2
  identity clones remain non-publishable through this lane (the broker's
  `V1_AUTHORITY_FORBIDDEN` rule is not worked around); when no allow receipt exists the
  adapter rejects before any Git effect with a typed code and zero broker writes.
- Adapter-built requests are validated in tests against the broker's own validators
  imported from `projects/omo`, so drift fails in CI instead of at lifecycle execution time.

## Non-goals

- Do not change `claims_authority.py` validation semantics, including the
  v2-identity + v1-allow prohibition (open principal decision item).
- Do not change the canonical push argv in `cmd_integrate()` byte-for-byte (WP1
  constraint), do not add a second push path or automatic retry.
- Do not flip activation state, do not activate any descriptor, do not execute a
  lifecycle transaction, and do not fabricate or backfill lifecycle receipts.
- Do not alter pre-activation inert behavior: without an exact activation receipt the
  seam remains `unactivated` and preserves legacy effect behavior.

## Verification

- `uv run pytest -q tests/test_clone_lifecycle.py` GREEN, including new contract tests
  that pass every adapter-built request through the broker validators.
- `python3 -m py_compile bin/gac/clone-lifecycle.py`.
- `make gac-local-gate` GREEN; `git diff` touches only the bet's write surfaces.

## Boundaries

One external effect per operation, no force push, no `--no-verify`, no mutation of
historical receipts, no promotion of v2 above shadow, no instruction capability.
