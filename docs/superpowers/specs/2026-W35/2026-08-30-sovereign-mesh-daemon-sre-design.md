---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-106
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Sovereign Mesh Daemon SRE & Thunderbolt 5 Chaos Drill Design Specification

## 1. Objective
Deploy omlxc.dma_daemon and resident.daemon as persistent macOS user launchd agents, and execute physical Thunderbolt 5 unplug, 75% memory threshold spillover, and node disconnection chaos drills to verify sub-50ms degradation and sub-1.5s recovery.

## 2. Architecture & Components
- Launchd Configuration: com.omostation.omlxc-dma-daemon.plist registered in user launchd with KeepAlive and ThrottleInterval=5.
- DMA Telemetry & Watchdog: omlxc.daemon.dma_daemon monitoring link throughput, error counters, and memory watermark.
- Paged KV Memory Spillover: omlxc.dataplane.paged_kv migrating idle KV pages to remote node upon 75% threshold breach.
- Chaos Drill Suite: Automated tests simulating hardware link severance, PCIe resets, and node partitioning.

## 3. Verification Criteria
- Launchd agent active with fresh mesh-telemetry.json heartbeats.
- Chaos drills pass with 10GbE fallback <= 50ms and DMA restoration <= 1.5s.
- Zero OOM crashes under memory spillover stress.
