---
schema: value-evidence/operational-live-canary/v1
bet: BET-Y1Q3-T4-01
axis: operational
evidence_key: live_canary
canary_source: BET-Y1Q2-T1-19
canary_run: 20260821T020119Z-bet-execution-f21e7fdc
canary_rounds: 3
protocol_defects_found: 9
canary_status: pass
independently_verified: true
retro: .omo/_knowledge/retros/2026-08-21-t1-19-acp-canary-retro.md
verified_at: 2026-08-22
lifecycle: history
owner: governance-team
last_updated: 2026-08-26
---

last-reviewed: 2026-08-26
---
真实 canary 运行(operational 证据):
- T1-19 ACP stdio cutover 三轮真实 canary(run f21e7fdc)
- 发现 9 个真实协议缺陷(mock 全绿未拦住, 真实进程握手才暴露)
- R1 canary PASS + 独立 verifier ACCEPT_WITH_NOTES
- 修复(PR #67 等)后 T1-19 done(2026-08-21)

这是 operational 轴的 live canary 证据: 真实运行、真实握手、真实缺陷修复。
