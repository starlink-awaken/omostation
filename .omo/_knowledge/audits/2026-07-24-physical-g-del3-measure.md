---
title: G-DEL.3 两机真机测量 (n=1000, WiFi, p99 未达标)
date: 2026-07-24
type: audit
strat: STRAT-P81
front: P1
related_cards:
  - needs-human-p80-physical-hosts
  - needs-human-batch2-physical-recovery-checklist
evidence:
  - .omo/_knowledge/audits/2026-07-24-physical-g-del3-quick.json
---

# G-DEL.3 两机真机测量 — WiFi p99 未达标 (如实记录)

## 测量 (2026-07-24T13:07:32Z, STRAT-P81 P1)

- env_class: **physical_multi_host** ✅ (2 hosts: local-mac 127.0.0.1:18765 + macmini 192.168.31.210:18765)
- controller: xiamingxingdeMacBook-Pro.local
- macmini: ping OK (avg 7.4ms) + SSH:22 OPEN (key 自动认证), en1 WiFi active, en0 Ethernet inactive

## G-DEL.3 结果 (n=1000, cross_host_put)

- p99_ms: **159.83ms** ❌ (≥100ms, 未达标, definitive n=1000)
- p50: 8.6ms / p90: 12.3ms / p95: 16ms (主体快)
- 尾部尖峰: 24 ops 在 [150,200)ms
- meets_physical_gate: false · gate_status: OPEN (min_physical_hosts=2 达标, 但 p99 超)

## G-DEL.1 (context, 老王不碰)

- success_rate: 100% (200/200) ✅ · dispatch_p99: 154ms
- gate_status: BLOCKED (physical_hosts=2 < min_physical_hosts=4, ADR-0226)
- 4 机门禁须人类 (ADR-0226)

## 归因

WiFi 尾部尖峰 (24 ops 150-200ms) 拉高 p99. wired_path unavailable (macmini en0 Ethernet inactive, 走 WiFi en1). Large-N n=1000 definitive (非小样本噪声).

## 重测计划 (交接单 P1 next_action)

1. macmini 插以太网 (en0 active) + local host 以太网
2. 重跑 `python3 bin/delivery/measure_physical.py --auto-default-lan --start --n-ops 1000` (wired)
3. wired p99<100ms → 申请卡进 Inbox (人类宣布, 不自宣)
4. wired 仍超 → 归因 (驱动/路由) + 排查

## 口径 (fail-closed, ADR-0226)

- meets_physical_gate 保持 false (p99 未达标)
- 老王不得自宣 G-DEL.3 达标
- 4 机 G-DEL.1 须人类 (ADR-0226)

## 看板影响

- needs-human-p80-physical-hosts: 更新 (macmini 可达 + G-DEL.3 p99 159ms WiFi, 待以太网重测 + 待 y7000p/macbook 到 4 机)
- phase-scope inventory: macmini reachable +1 (evidence: g-del3-quick.json)
