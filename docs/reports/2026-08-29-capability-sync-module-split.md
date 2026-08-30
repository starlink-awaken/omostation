# T10-60 capability-sync verification helper split

## Result

The compatibility CLI was reduced from the current CI-observed 1,575 lines to
1,490 lines by extracting only verification receipt shaping, bounded stdin
parsing, principal verification, and fixed federation-observer delegation into
`lib/capability_sync_verification_helpers.py`.

`bin/capability-sync.py` remains the public executable entrypoint. Its existing
`verify_material_against_mesh`, `verify_principal_envelope`, stdin parser,
federation delegation, and receipt names remain available through thin wrappers;
no registry, dispatcher, provider, or authority was added.

## Verification

- RED: the new hard LOC invariant failed at `1575 <= 1500`.
- GREEN: the invariant passes at 1,490 lines.
- Ruff format/check passes for the changed CLI, helper, and tests.
- Capability-sync, native inspection, native execution receipt, and trace
  binding targeted regressions: 252 passed; the Python 3.9 import/probe path
  passed.
- The root workflow fixture now copies the extracted helper; the two previously
  failing capability preflight identity tests pass (`2 passed`).
- The existing canonical projection test was separately observed to fail in a
  partial local clone because uninitialized submodules make the generator mark
  real MCP servers as `exists:false`; the generated projection was restored and
  not committed. Full-submodule CI is the authority for projection drift.
- Local god-module inspection confirms `capability-sync.py` is absent from the
  hard-error list after the split; unrelated dirty `projects/omo` state is not
  included in this delivery.

## Boundary

This is an engineering/governance gate repair only. It does not claim personal
value, alter capability semantics, or change Documents content/runtime. The
T10-59 root-oneoff registry PR can be rechecked after this gate repair lands.

## Rollback

Revert the helper import/wrappers and delete the helper module plus its LOC
regression test. No generated registry or runtime rollback is required.

## Phase 2 (2026-08-30): mesh verification block extraction

- `bin/capability-sync.py`: 1,490 → **1,045 lines** (god-module error threshold 1,500 — now 455 lines of headroom).
- Extracted into `lib/capability_sync_verification_helpers.py` (107 → 561 lines):
  VERIFICATION_SCHEMA/FIELDS/EXPECTED_FIELDS, MESH_LOG, MAX_MESH_LOG_BYTES,
  VERIFICATION_MESH_EVENT_STATES, `_mesh_stat_fingerprint`, `_mesh_path_stat`,
  `_load_workflow_mesh_projection`, `_project_verification_mesh_run`,
  `_read_mesh_snapshot`, `_parse_verification_envelope`, `_verify_worker_context`,
  `verify_material_against_mesh` — re-exported from the CLI as the
  library-only compatibility boundary.
- Targeted tests: **251 passed** (test_capability_sync / test_capability_trace_binding /
  test_capability_native_inspection / test_capability_native_execution_receipt);
  2 failures (`test_make_and_ci_run_blocking_canonical_check`,
  `test_agora_composite_native_inspection_...`) reproduce on unmodified main via
  `git stash` — pre-existing, unrelated to the split.
- Python 3.9 import compatibility: both files parse at `feature_version=(3, 9)`.
- Capability registry projection: fresh generation is byte-identical between
  main and the split branch (`git stash` A/B) — no semantic capability change.
  The pre-existing `check` drift against the checked-in registry reproduces on
  unmodified main and is owned by the concurrent registry-sync flow.
