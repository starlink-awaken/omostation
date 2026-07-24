---
title: Physical hosts + G-DEL.3 fail-closed (STRAT-P80 T2)
date: 2026-07-24
type: audit
needs-human: true
---

# Physical base probe (fail-closed)

## Probe (2026-07-24T02:29:04.787388+00:00)

| Target | Result |
|--------|--------|
| ping 127.0.0.1 | OK |
| ping 192.168.31.210 (macmini) | **FAIL** timeout |
| ssh BatchMode macmini | **FAIL** timeout |
| y7000p candidates | **FAIL** (no reach) |
| measure_physical --auto-default-lan | error: local-mac node not listening; remote unreachable |

## Inventory (scripted, not hand-filled)

- reachable_physical_hosts (this probe) = **1** (local only)
- phase-scope G-DEL.1 min_physical_hosts = **4**
- G-DEL.3 official pass requires ≥2 physical machines with measure_physical

## Needs-human

1. Bring macmini online / fix LAN / SSH keys for 192.168.31.210  
2. Register y7000p (or cloud node) after real probe  
3. Re-run `python3 bin/delivery/measure_physical.py --auto-default-lan --start`  

**禁止**手填 `reachable_physical_hosts≥4` 或官方 pass 字段（ADR-0226）。
