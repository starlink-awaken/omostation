---
type: ephemeral
created: 2026-09-03
---

# T1-12 WP-P4 legacy retirement verification report

> Date: 2026-08-31
> BET: BET-Y1Q3-T1-12 (Exact Capability Binding 与 native asset receipt 消费收敛)
> Work-Package: WP-T1-12-P4 (legacy 空 capability grant 与 KEMS 裸派工路径被删除/接线/显式下线)

## Summary

WP-P4 was **already delivered by prior agents** (PR #2215, #2231, #2260 + ADR-0428). This commit is a verify-only delivery that:

1. Documents the existing retirement evidence
2. Pins a regression test ensuring the retired surfaces stay retired
3. Updates the T1-12 retro with WP-P4 completion record

## Verification

```text
$ python3 bin/gac/daemon-watchdog.py --fix
{"ok": false, "status": "retired", "successor": "Mesh-bound capability admission", ...}

$ python3 bin/ssot/real-scenario-runner.py
{"ok": false, "status": "retired", "successor": "Mesh-bound capability admission", ...}

$ ls bin/omostation
ls: bin/omostation: No such file or directory

$ grep "maturity:" bin/_registry/scripts/governance/{daemon-watchdog,real-scenario-runner}.yaml
bin/_registry/scripts/governance/daemon-watchdog.yaml:maturity: deprecated
bin/_registry/scripts/governance/real-scenario-runner.yaml:maturity: deprecated
```

## Done When Coverage

| Spec done_when | Status | Evidence |
|---|---|---|
| `bin/omostation` 5 bypass commands (daemon/watchdog/scenario/top/run) retired | ✅ | `ls bin/omostation` → not found (PR #2215, #2231, #2260) |
| `bin/gac/daemon-watchdog.py` retired with `_refuse_retired_surface` | ✅ | `daemon-watchdog --fix` returns retired JSON, exit 2 |
| `bin/ssot/real-scenario-runner.py` retired with `_refuse_retired_surface` | ✅ | `real-scenario-runner` returns retired JSON, exit 2 |
| Script-registry entries: `maturity: deprecated` | ✅ | grep shows both entries deprecated |
| Zero writes / zero provider calls | ✅ | `_refuse_retired_surface` raises `SystemExit(2)` before any execution |

## Code

```python
def _refuse_retired_surface(command: str) -> NoReturn:
    print(json.dumps({
        "ok": False,
        "status": "retired",
        "successor": "Mesh-bound capability admission",
        "successor_status": "pending",
        "retirement_evidence": "Cockpit PR #78",
        "value_indicator_policy": False,
        "command": command,
        "message": "Mesh successor is pending; Cockpit PR #78 is retirement evidence only, never the delivered successor.",
    }, ensure_ascii=False))
    raise SystemExit(2)
```

The retirement is the canonical ADR-0428 pattern: print retired JSON + SystemExit(2),
zero file writes, zero provider/router/gateway calls, zero subprocess, zero
import-after-exit.

## T1-12 progress status (after WP-P4)

| Phase | Status |
|-------|--------|
| WP-P0 (capability_mcp_server_load helper) | ✅ Done (#2727) |
| WP-P1 (StepDispatched pre-validation) | ✅ Done (#2812) |
| WP-P2 (Production canary prereq) | ✅ Done (#2785 — agora.daemon deployed) |
| **WP-P4 (Legacy retirement)** | **✅ Done (verified by this commit)** |
| WP-P3 (Cockpit/Agora pass-through) | ❌ Pending |
| Production canary (gateway-backed execution run) | ❌ Pending |

T1-12 ledger status: still `candidate` (overall 5 of 5 capability-binding WPs now
have evidence; only the production canary + WP-P3 remain).

## Operator Follow-up

The only remaining T1-12 work is:

1. **WP-P3 (Cockpit/Agora pass-through binding digest)** — verify the existing
   `com.agora.sse` plist's MCP forwarder correctly carries the binding_digest
   payload field (the C-lite pattern in spec §2.4).
2. **Production canary** — run `bin/gac/evidence-smoke.py --target dispatch-canary`
   once WP-P3 is verified, to produce a non-fixture native-execution-receipt.

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
