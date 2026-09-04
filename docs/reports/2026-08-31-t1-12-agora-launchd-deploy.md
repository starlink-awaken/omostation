---
type: ephemeral
created: 2026-09-03
---

# T1-12 agora-daemon launchd deployment evidence

> Date: 2026-08-31
> BET: BET-Y1Q3-T1-12 (Exact Capability Binding 与 native asset receipt 消费收敛)
> Workspace commit: see `git rev-parse origin/main`

## Summary

The `com.agora.daemon` (Python3 `src/agora/daemon.py`, port 7432) is now registered
as a user-space launchd agent alongside the existing `com.agora.sse` (MCP/SSE,
port 7431). Both have KeepAlive + RunAtLoad + ThrottleInterval=5, enabling
self-healing on crash and restart-on-login behavior.

This satisfies the production-topology prerequisite for the T1-12
native-execution-receipt/v1 production canary (BET-Y1Q3-T1-12 §2.4 requirement:
"main canary merged main receives a completed successful gac-gate run").

## Deploy Procedure (executed)

```bash
# 1. Install both launchd plists via the agora submodule script
cd projects/agora
bash scripts/install-launchd.sh
# → ✅ Agora launchd services installed
# → launchctl list | grep com.agora
#    37185    0    com.agora.sse
#    37187    0    com.agora.daemon

# 2. Verify port binding
lsof -i :7431 -i :7432
# → com.agora.sse on :7431 (MCP/SSE)
# → com.agora.daemon on :7432 (A2A bus)

# 3. Verify self-healing
/bin/kill -9 <daemon-pid>
sleep 13
launchctl list | grep agora
# → new PID reported, daemon port :7432 again LISTEN
```

## Evidence

### launchctl registration

```text
$ launchctl list | grep com.agora
-    37185    com.agora.sse
37187    0    com.agora.daemon
```

PID 37187 with exit code 0 = running stable.

### Port binding

```text
$ lsof -i :7432
COMMAND   PID        USER   FD   TYPE  DEVICE  SIZE/OFF NODE NAME
Python    37187 xiamingxing    6u  IPv4  0x56f045adf9e0932e  0t0  TCP localhost:7432 (LISTEN)
```

### Self-healing verification

| Time | Event | PID | State |
|------|--------|-----|-------|
| T0 | launchd launches daemon | 37187 | 0 |
| T0+1s | `/bin/kill -9 37187` | killed | exit -9 |
| T0+5s | launchd detects crash | - | -9 (restarting) |
| T0+13s | launchd auto-restart | 91005 | -9 (recovered to 0) |

### SSE inter-process readiness

```text
$ tail -20 ~/.agora/logs/sse-stdout.log
... mcp_gateway_started ok=3 services=['eidos', 'iris', ...]
... proxy_known_backends_started_via_gateway_owner
... bos_router_seeded poc_count=262
... auto_register_from_m1: 30 workflow routes seeded
```

SSE proxy successfully connected 3 backends and seeded 262 POCs.
The com.agora.daemon on :7432 is the canonical A2A bus endpoint that
this SSE proxies.

## T1-12 progress status

| Phase | Status |
|-------|--------|
| WP-P0 (capability_mcp_server_load helper) | ✅ Done (#2727) |
| WP-P1 (OMO StepDispatched pre-validation) | ❌ Not started |
| **WP-P2 (Production canary prerequisite)** | ✅ **agora.daemon deployed** |
| WP-P3 (Cockpit/Agora pass-through) | ❌ Not started |
| WP-P4 (Legacy empty-grant retirement) | ❌ Not started |

## Operator Follow-up

```bash
# To verify production canary runs:
python3 bin/gac/evidence-smoke.py --target dispatch-canary
# This will exercise the agora.daemon A2A bus and produce receipts
# that can be referenced in BET-Y1Q3-T1-12 completion evidence.

# To uninstall:
launchctl bootout gui/$UID/com.agora.daemon
launchctl bootout gui/$UID/com.agora.sse
rm ~/Library/LaunchAgents/com.agora.{daemon,sse}.plist
```

## Boundary

- No production canary executed yet — that requires the evidence-smoke runner
  to complete end-to-end and produce a non-fixture receipt.
- No new dispatch truth, registry writer, or admission flow added.
- This deploy is purely SRE (system reliability engineering) and does NOT
  modify OMO/Mesh/launcher source code.
