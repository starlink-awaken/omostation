---
type: ephemeral
created: 2026-09-03
---

# Binding enforcement caller scans — shadow → warning promotion evidence

Method: inventory every production entrypoint that invokes
`bin/capability-sync.py load|invoke`, then record whether it supplies the
full binding bundle (`--binding-json --inspection-receipt-json
--admission-receipt-json --operation-id --effect-classification`).
`shadow_missing`/`warning_missing` receipts from unbound callers are the
observable marker. Callers are NOT inferred from unit tests alone.

## Scan #1 — main @ e3397add7..94172a1ba window (2026-08-26, pre-promotion)

| Entrypoint | Invokes sync invoke/load | Bundle | Status |
|---|---|---|---|
| `cockpit.commands.bos.cmd_bos_capability` / `run_bos_capability_invoke` (#86) | yes | optional, all five flags supported | migrated |
| `cockpit.web.api_kems` dispatch endpoint | retired (HTTP 410, #86) | n/a | removed |
| `cockpit.agent_runtime_server` / `_mcp_server` | never calls capability-sync | n/a | gated by binding_receipt (403/envelope) |
| root scripts / cron surfaces | none found (`grep -r "capability-sync.py" bin/ .github/`) | n/a | none |

Unbound production callers: **0** (every caller either migrated or removed).

## Scan #2 — PR-context check of the warning promotion commit

The promotion commit itself flips `BINDING_ENFORCEMENT` to `warning`; the
PR-context CI run executes `tests/test_capability_sync.py::test_unbound_invoke_is_shadow_observed_before_fail_promotion`
against the flipped constant (assertion is now derived from the module
constant), which is the second consecutive observation that the only
unbound path is the legacy CLI surface kept alive intentionally during the
warning window.

## Conclusion

Criteria for shadow→warning met. Fail promotion requires two further clean
scans during the warning window and remains intentionally pending
(owner: capability-binding follow-up; tracked in BET-Y1Q3-T1-12 retro).
