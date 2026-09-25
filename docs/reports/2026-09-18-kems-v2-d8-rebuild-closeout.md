---
schema: md/v1
status: active
lifecycle: history
owner: runtime
last-reviewed: 2026-09-25
type: implementation-evidence
schema_version: report/v1
created: 2026-09-18
---


# kems-v2 D-8 rebuild closeout

## Resolution

D-8 is resolved as a semantic rebuild, not a byte-level recovery. The v2.2.0
toolchain now has all 12 Python tools under git-hosted
`projects/runtime/scripts/kems-v2`.

## Authoritative evidence

- Runtime delivery: [omostation-runtime#79](https://github.com/starlink-awaken/omostation-runtime/pull/79)
  merged as child main `f95d8a4b2578c746f3977a4686f1ebe8f981f907`.
- Root pointer: [omostation#3951](https://github.com/starlink-awaken/omostation/pull/3951)
  merged as main `697364604bf2ff7fdf3bff1ee846e91602a6a0c2`.
- Tool count on child main: `12`.
- Runtime focused tests: `tests/test_kems_v2_rebuild.py` 2/2 PASS.
- Runtime lint: PASS.
- Root reachability: `projects/runtime` 1/1 PASS against child `origin/main`.
- Root GaC: 57/57 PASS.

## Design guardrails

- No hard-coded Documents domain defaults.
- No symlink-based four-domain tool deployment.
- Consumers pass explicit workspace-owned `--root` / `--domains` values.
- Domain-specific graph scale expectations were removed.
- `kems-cross-check` now validates explicit domain roots directly.

## Boundary

This closes the engineering recovery debt. It does not prove business value,
activate Claims Authority, or mark the broader Agent Cell objective complete.
