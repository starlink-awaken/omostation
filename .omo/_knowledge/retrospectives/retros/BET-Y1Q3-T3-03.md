---
title: BET-Y1Q3-T3-03 复盘 — mem0/memtheta 退役 (核实性收口)
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  human_gate: false。三 done_when 两条已被早前轮次解决 (partial_simulation 移除 +
  mem0 shadow 默认 OFF), 本轮完成退役标记与审计文档更新。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T3-03 复盘 (核实性收口)

## done_when 对照 (2026-08-16 实测)

| done_when | 结果 | 证据 |
|---|---|---|
| memory-os.yaml 不再 partial_simulation | ✅ | 全仓 rg 零命中 |
| mem0/memtheta 代码标记 experimental 且默认不加载 | ✅ | kos 两适配器零代码引用 (全仓确认); mos mem0_shadow 默认 OFF (MOS_MEM0); 审计文档标记 retired-experimental |
| 适配器审计文档更新 | ✅ | memory-os-adapter-audit.md 表格+§2 退役确认 |

## Q3

- partial_simulation 与引用移除是早前轮次交付 (memory-os 收敛), 本 bet 剩余工作 = 文档面退役标记
- mem0_shadow (mos) 是活替代, 非删除 — feature-flagged 保留评估位

## Q5

- T6-01 (gbrain/kairon 归并) 依赖链: T3-03 ✅ (本条) + T3-02 (已停审待批) + T3-01 (done)
- kos 两适配器文件保留为存证, 若未来再引需显式改标记
