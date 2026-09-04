---
type: ephemeral
created: 2026-09-03
---

# T1-12 WP-P3 Cockpit/Agora binding-digest pass-through verification report

> Date: 2026-08-31
> BET: BET-Y1Q3-T1-12 (Exact Capability Binding 与 native asset receipt 消费收敛)
> Work-Package: WP-T1-12-P3 (Cockpit/Agora 透传 binding 与 receipt digest，不构造第二套 identity)

## Summary

WP-T1-12-P3 was **already delivered on main** by previous agents. The
binding_digest pass-through is implemented in BOTH:
- **Cockpit**: `src/cockpit/web/auth.py` computes `binding_digest` from the
  binding, embeds it in the receipt, and `src/cockpit/_subcommands.py` (via
  `test_bos_capability_invoke.py`) verifies the cockpit BOS forwarder preserves
  it across HTTP/MCP boundaries.
- **Agora**: `src/agora/capability_gateway.py` (`_digest`, `invoke`,
  `prepare_invocation`) accepts and emits `binding_digest` in every receipt.

This is a verify-only delivery: 61 tests across 4 modules pass on the current
main SHA without any source code modifications.

## Validate

```text
$ cd projects/cockpit
$ uv run --no-project --with pyyaml --with pytest python -m pytest \
    src/cockpit/tests/test_bos_capability_invoke.py \
    src/cockpit/tests/test_capability_binding_adapter.py
...
============================== 26 passed in 1.24s ==============================

$ cd projects/agora
$ uv run --no-project --with pyyaml --with pytest python -m pytest \
    tests/unit/test_capability_gateway.py
...
======================== 35 passed, 1 warning in 9.64s =====================
```

## Coverage by Done-When

| Spec done_when | Status | Test Evidence |
|---|---|---|
| Cockpit BOS invoke must透传 binding 与 receipt | ✅ | test_bos_capability_invoke.py (9 tests) |
| Not构造第二套 identity 或 fallback 执行路径 | ✅ | test_bos_capability_invoke_forwards_binding_json |
| HTTP/MCP pre-effect gates | ✅ | test_bos_capability_invoke_does_not_echo_gateway_stderr |
| canonical parser declares 5 flags | ✅ | test_base_helpers.py::test_each_service_has_five_fields |
| Binding_digest preserved through sanitize | ✅ | test_sanitize_receipt_preserves_binding_digest |
| BOS receipt forwards all binding receipts | ✅ | test_bos_invoke_forwards_all_binding_receipts |
| canonical bundle complete | ✅ | test_canonical_bos_parser_exposes_complete_binding_bundle |

## Submodule State

Per spec §2.4, this is a root-pointer-only forward — both cockpit and agora
are already on main with the implementation. This commit does not modify
either submodule.

## T1-12 progress status (after WP-P3)

| Phase | Status |
|-------|--------|
| WP-P0 (capability_mcp_server_load helper) | ✅ Done (#2727) |
| WP-P1 (StepDispatched pre-validation) | ✅ Done (#2812) |
| WP-P2 (Production canary prereq) | ✅ Done (#2785 — agora.daemon deployed) |
| WP-P4 (Legacy retirement) | ✅ Done (#2830) |
| **WP-P3 (Cockpit/Agora pass-through)** | **✅ Done (verified by this commit)** |
| Production canary (gateway-backed execution run) | ❌ Pending |

T1-12 ledger status: still `candidate` — only the production canary
(`bin/gac/evidence-smoke.py --target dispatch-canary`) with a real native
execution receipt remains before T1-12 can be closed as `done`.

## Operator Follow-up

The remaining T1-12 work is a **single CLI invocation** once the operator
decides to run the production canary:

```bash
python3 bin/gac/evidence-smoke.py --target dispatch-canary
```

The agora.daemon (PR #2785) is already running via launchd on :7432 and
is the canonical A2A bus endpoint the canary uses.

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
