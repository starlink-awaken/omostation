---
title: macmini 网络可达性确认（sandbox 探测 · 非官方门禁 evidence）
date: 2026-07-24
type: audit
strat: STRAT-P81
related_cards:
  - needs-human-p80-physical-hosts
  - needs-human-batch2-physical-recovery-checklist
last_updated: 2026-08-25
lifecycle: history
owner: unassigned
---

# macmini 恢复可达 — 网络层探测

## 探测结果（2026-07-24, workspace sandbox 局域网侧）

| 节点 | ping | SSH:22 | 判定 |
|------|------|--------|------|
| macmini (192.168.31.210) | OK (~0.3ms) | **OPEN** | 网络层恢复 ✅ |
| y7000p (192.168.31.128) | OK | closed | 待开 SSH 服务 |
| macbook (tailscale) | — | — | 沙箱侧不可探（正常, tailnet） |

## 口径声明（fail-closed, ADR-0226）

- 本探测来自 **workspace sandbox（非注册物理节点）**, 仅证明网络层可达。
- **不构成** G-DEL.3/G-DEL.1 官方 evidence; `meets_physical_gate` 保持 false。
- 官方达标须在注册节点 local-mac 上跑 `measure_physical.py`, 且 p99<100ms + 人类确认。

## 下一步（用户已选: 先 G-DEL.3 两机）

1. 主力 Mac: `python3 bin/delivery/measure_physical.py --auto-default-lan --start`
2. 若 WiFi p99 卡 ~100ms 边缘 → macmini 插以太网重测（phase-scope next_action 已记）
3. 达标数据 → 申请卡进 Inbox → 人类宣布（不得自宣）

## 看板影响

- `needs-human-p80-physical-hosts`: 从"全不通"更新为"macmini 可达, 待真机测量"; 周提醒继续
- y7000p / macbook: 仍待用户侧就绪
