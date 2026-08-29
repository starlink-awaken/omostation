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
