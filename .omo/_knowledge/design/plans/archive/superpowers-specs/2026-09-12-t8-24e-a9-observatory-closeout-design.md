---
schema_version: specification/v1
spec_version: 1.0.0
title: A9 全景观测终验对账、43191 进程平稳退役与 Closeout
bet_id: BET-Y1Q4-T8-24E
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-12
decision_ref: decision://accepted/BET-Y1Q4-T8-24E
---

# T8-24E — A9 全景观测终验对账与 Closeout

## Context

T8-24 系列（Cockpit-UI 全面重构与六面合流涅槃战役）的终验环节。
A9 全景观测平台（原 live_server.py, PID 74291/43191）已完成功能迁移至 Cockpit，
本 BET 负责终验对账、进程平稳退役与 Closeout 签署。

## Scope

- Cockpit 数据点与原 43191 达到 100% 一致性与 SHA-256 对齐
- A9 全景观测准入门禁证据链完成签署
- 平稳停止 live_server.py (PID 74291)，所有入口统一指向 Cockpit
- make gac-local-gate 全绿通过

## Verification

```
python3 bin/gac/ci-check-runner.py && make gac-local-gate
```

## Done Criteria

1. Cockpit 数据点与原 43191 达到 100% 一致性与 SHA-256 对齐
2. A9 全景观测准入门禁证据链完成签署
3. 平稳停止 live_server.py (PID 74291)，所有入口统一指向 Cockpit
4. make gac-local-gate 全绿通过

## Write Surfaces

- `docs/reports/` — 终验对账报告
- `.omo/_knowledge/retros/` — 收口 retro
