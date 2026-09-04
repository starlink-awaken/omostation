---
type: ephemeral
created: 2026-09-03
---

# Agora canonical L4 route evidence

## Scope

BET-Y1Q3-T10-22 fixes Agora's L4 service route resolution. It does not delete the
nested L4 copy, change production consumers, or migrate Documents content.

## Evidence matrix

| Axis | Result | Evidence |
| --- | --- | --- |
| Implementation | PASS | Agora commit `16fa25c` adds explicit-root, Workspace-SSOT, and legacy-nested resolution in `projects/agora/src/agora/mcp/mcp_bootstrap.py`. |
| Registration | PASS | `KNOWN_SERVICES["l4-kernel"]` is built through `_build_l4_kernel_service()` and publishes `l4_route_mode` plus `l4_kernel_root`. |
| Consumer tests | PASS | `uv run pytest tests/unit/test_mcp_l4_route.py tests/unit/test_proxy_toolbox_integration.py -q`: 9 passed. Ruff passed for the touched source and test files. |
| Runtime route smoke | PASS | In the isolated Workspace clone, resolution returned `projects/l4-kernel` with mode `canonical-workspace`; the service argv used that directory. |
| Child delivery | PASS | PR #39 (`starlink-awaken/omostation-agora`) merged to `main` as `1910ccaf`; no CI checks were configured for the branch. |
| Root integration | PASS | Root gitlink is updated only after child merge/reachability verification. |
| Documents migration | NOT IN SCOPE | Physical content-plane cleanup remains a separate owner-by-owner migration wave. |

## Route contract

1. `L4_KERNEL_ROOT` is highest priority and invalid values fail closed.
2. `OMOSTATION_WORKSPACE_ROOT/projects/l4-kernel` is the explicit Workspace route.
3. Without environment overrides, a Documents registry marker plus
   `projects/l4-kernel` identifies the canonical Workspace root.
4. A standalone nested `projects/l4-kernel` is retained only as
   `legacy-nested` and is observable in service metadata.
5. No candidate root yields `unavailable` and disables the service entry.

## Residual risk

The nested L4 copy still exists and may drift from canonical L4. This wave removes
route ambiguity but does not prove behavioral parity or retire the nested copy.
Those require a separate inventory, consumer cutover, canary, and retirement BET.
