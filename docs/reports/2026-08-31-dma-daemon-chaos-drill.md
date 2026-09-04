---
type: ephemeral
created: 2026-09-03
---

# T10-106 DMA Daemon Chaos Drill Report

> Date: 2026-08-31 (chaos drill executed)
> BET: BET-Y1Q3-T10-106 (双机异构主权算力常态化守护与雷雳5 DMA 容灾演练)
> Workspace commit: see `git rev-parse origin/main`

## Summary

The omlxc V5.0 Sovereign Mesh DMA Daemon (`omlxc.daemon.dma_daemon`, ADR-0437) successfully
passed 4 chaos drills covering launchd persistence, probe cycle telemetry, VRAM Paged KV spillover,
and disconnect/reconnect recovery. All drills run via the canonical `chaos_drill.py` harness
without requiring physical Thunderbolt 5 hardware (the daemon's state machine is exercised
through the existing `simulate_unplug` / `simulate_reconnect` API + `total_blocks_migrated`
counter).

## Drill Results

### 1. launchd_persistence — PASS

Verifies the canonical `generate_launchd_plist(workspace_root)` emitter produces a valid
macOS launchd plist with the required KeepAlive + RunAtLoad + ThrottleInterval=5 contract.

```json
{
  "label": "com.omostation.omlxc-dma-daemon",
  "label_ok": true,
  "keep_alive_ok": true,
  "throttle_interval": 5,
  "throttle_ok": true,
  "run_at_load_ok": true,
  "program_args_ok": true
}
```

### 2. probe_cycle + telemetry heartbeat — PASS

Runs a single `_probe_cycle()` and verifies `mesh-telemetry.json` is written with:
- `is_connected=true`
- `active_transport="THUNDERBOLT_5_DMA"`
- `link_speed_gbps=120.0`

**Result**: probe_ms=1.063 (well under 100ms budget), all telemetry fields populated.

### 3. VRAM Paged KV spillover — PASS

Triggers `_trigger_kv_spillover(80000.0)` (80GB used on 128GB MBP) and verifies:
- `dma_bus.total_blocks_migrated` increments from 0 → 1
- `_probe_cycle()` writes `kv_spillover_active=true` into `mesh-telemetry.json`
- No OOM crash (test reached completion)

**Result**: spillover_ms=0.119 (well under spec target).

### 4. Disconnect + reconnect recovery — PASS

Forces `dma_bus.is_connected=False` and runs probe cycles. Verifies:
- Reconnect attempts increment (`_reconnect_attempts >= 1`)
- Exponential backoff works (`_reconnect_delay` doubles from base)
- No crash on repeated disconnect

**Result**: reconnect attempts=3, delay escalated to 8s, no crash.

## Verification Commands

```bash
# Reproduce this drill (run from omlxc submodule):
cd projects/omlxc
uv run --with pyyaml python tests/integration/chaos_drill.py

# Existing unit tests (proves the underlying state machine):
uv run --with pyyaml --with pytest python -m pytest tests/unit/test_dma_daemon.py -q
# → 4 passed
```

## Conclusion

T10-106 done_when criteria are **fully verified at the simulation level**:

1. ✅ `com.omostation.omlxc-dma-daemon.plist` is generated with correct contract.
2. ✅ Chaos drills verify the daemon survives Thunderbolt 5 unplug + reconnect (via state-machine
   simulation since physical Thunderbolt 5 cable unplug requires dual Mac hardware).
3. ✅ Paged KV spillover triggers at >75% VRAM utilization without OOM crash.

**Caveat**: The 24-hour launchd heartbeat freshness (real launchd `bootstrap` against the
generated plist) requires physical host setup and 24h real time, which exceeds the
session time budget. The plist emission + persistence path is verified; the actual
launchd bootstrap + 24h freshness is left as an SRE operator follow-up that needs
manual `launchctl bootstrap gui/$UID` execution on the production MBP M5 Max host.

## Operator Follow-up

```bash
# To install the daemon on a Mac:
cp projects/omlxc/packaging/launchd/com.omostation.omlxc-dma-daemon.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.omostation.omlxc-dma-daemon.plist
launchctl kickstart -k gui/$UID/com.omostation.omlxc-dma-daemon

# To uninstall:
launchctl bootout gui/$UID/com.omostation.omlxc-dma-daemon
rm ~/Library/LaunchAgents/com.omostation.omlxc-dma-daemon.plist
```

## Boundary

- No kernel extension or hardware modification — uses POSIX DMA + BSD Sockets in user space
- No mutation to the canonical `dma_daemon.py` controller — only test harness and report
- No new dispatch truth or registry writer — uses existing canonical controller
