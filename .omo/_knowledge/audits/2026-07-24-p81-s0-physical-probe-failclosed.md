---
title: STRAT-P81 Stage0 S0.3 — physical 4-host probe fail-closed
date: 2026-07-24
type: audit
stage: S0
strat: STRAT-P81
needs-human: true
---

# Physical base probe (S0.3 · fail-closed)

## Probe (2026-07-24T03:39:25Z)

Scripted inventory (not hand-filled). Scratch: `physical-probe.json`.

| Target | Result |
|--------|--------|
| local-mac (127.0.0.1) | **OK** ping+local |
| macmini 192.168.31.210 | **FAIL** ping timeout; SSH timeout |
| y7000p 192.168.31.128 | **FAIL** ping timeout; SSH timeout |
| macbook tailscale | **FAIL** `tailscale status --json` timeout |
| measure_physical --auto-default-lan --start | **FAIL** `ssh_fail` macmini :22 timeout |

## Inventory

- `reachable_physical_hosts` (this probe) = **1** (`local-mac` only)
- G-DEL.1 `min_physical_hosts` = **4** (`.omo/_truth/registry/phase-scope.yaml::metrics_caliber`)
- `meets_g_del_1_unblock` = **false**
- `env_class` = `insufficient_physical`

## Needs-human (continue)

1. Bring macmini online / fix LAN / SSH for 192.168.31.210  
2. Register y7000p (or cloud / tailnet peer) after real probe  
3. Ensure tailscale CLI responds; prefer tailnet addresses for remote hosts  
4. Re-run `python3 bin/delivery/measure_physical.py --auto-default-lan --start`

## Forbidden

- 手填 `reachable_physical_hosts ≥ 4`
- 在 sim / 单机环境下写 G-DEL.1/3 官方 `meets_gate=true`（ADR-0226）

## S1 unlock

S0.3 **未绿** → S1 remains **LOCKED** per strat-p81-agent-execution-brief.md §1.
