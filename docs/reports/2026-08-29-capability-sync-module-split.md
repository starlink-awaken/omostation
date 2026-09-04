---
type: ephemeral
created: 2026-09-03
---

# T10-60 capability-sync verification helper split — mainline closeout

## Result

The compatibility CLI was reduced from the CI-observed 1,575 lines to 1,490
lines in phase 1, then to the current 1,048 lines in phase 2 by extracting only
verification receipt shaping, bounded stdin parsing, principal verification,
fixed federation-observer delegation, and mesh-verification helpers into
`lib/capability_sync_verification_helpers.py`.

`bin/capability-sync.py` remains the public executable entrypoint. Its existing
`verify_material_against_mesh`, `verify_principal_envelope`, stdin parser,
federation delegation, and receipt names remain available through thin wrappers;
no registry, dispatcher, provider, or authority was added.

## Verification

- RED: the new hard LOC invariant failed at `1575 <= 1500`.
- GREEN: the current mainline invariant passes at 1,048 lines.
- Ruff format/check passes for the changed CLI, helper, and tests.
- Capability-sync, native inspection, native execution receipt, and trace
  binding targeted regressions: 253 passed; the Python 3.9 import/probe path
  passed.
- The root workflow fixture now copies the extracted helper; the two previously
  failing capability preflight identity tests pass (`2 passed`).
- `make check-capability-registry` passes after initializing the generator's
  scanned `family-hub` and `gbrain` submodules. A partial clone otherwise
  reports a false 81-tool drift by marking those servers `exists:false`; no
  generated projection was hand-edited.
- The strict god-module report still returns nonzero for five unrelated global
  errors, but its scoped predicate confirms `capability-sync.py` is absent from
  the hard-error list. Those pre-existing errors are not part of this BET.

## Boundary

This is an engineering/governance gate repair only. It does not claim personal
value, alter capability semantics, or change Documents content/runtime. The
T10-59 root-oneoff registry PR can be rechecked after this gate repair lands.

## Rollback

Revert the helper import/wrappers and delete the helper module plus its LOC
regression test. No generated registry or runtime rollback is required.

## Phase 2 (2026-08-30): mesh verification block extraction

- Mainline merge: PR #2704 was squash-merged as
  `4da346b57463b59073ec2f94f049451e78844fb0`.
- `bin/capability-sync.py`: 1,490 → **1,048 lines** (god-module error threshold 1,500 — now 452 lines of headroom).
- Extracted into `lib/capability_sync_verification_helpers.py` (107 → 561 lines):
  VERIFICATION_SCHEMA/FIELDS/EXPECTED_FIELDS, MESH_LOG, MAX_MESH_LOG_BYTES,
  VERIFICATION_MESH_EVENT_STATES, `_mesh_stat_fingerprint`, `_mesh_path_stat`,
  `_load_workflow_mesh_projection`, `_project_verification_mesh_run`,
  `_read_mesh_snapshot`, `_parse_verification_envelope`, `_verify_worker_context`,
  `verify_material_against_mesh` — re-exported from the CLI as the
  library-only compatibility boundary.
- Targeted tests: **253 passed** (test_capability_sync / test_capability_trace_binding /
  test_capability_native_inspection / test_capability_native_execution_receipt);
  the canonical projection check passes on the fully initialized mainline
  clone. The first local failure was a partial-clone false drift, not a
  semantic projection change.
- Python 3.9 import compatibility: both files parse at `feature_version=(3, 9)`.
- Capability registry projection: fresh generation is byte-identical to the
  checked-in projection on the fully initialized mainline clone — no semantic
  capability change.
- The inherited T1-12 engineering test receipt was re-attested to the current
  test-file digest after this behavior-preserving split; no T1-12 status or
  value claim changed.

## Closeout

The closeout run `20260830T074703Z-bet-execution-481d71f0` records the
mainline verification. This is an engineering/governance delivery only;
principal-bound value remains `NOT_PROVEN`.
