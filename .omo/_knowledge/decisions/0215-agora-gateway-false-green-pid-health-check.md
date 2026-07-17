---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0202-fake-green-prevention.md
  - 0179-runtime-probe-false-positive-treatment.md
  - 0212-ledger-history-gap-not-physical-trim.md
supersedes: []
---

# ADR-0215 — agora-gateway 假绿灯治本（PID 重置 + health_check 落盘）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **Runtime pin**: `projects/runtime` → `24a6042`

## Context

复合健康分长期停在 ~83，分项为：

| 分项 | 权重 | 典型值 | 说明 |
|------|------|--------|------|
| governance_anomaly | 0.5 | 100 | 无 GaC 异常 |
| runtime (service_online) | 0.3 | ~75 (3/4) | 执行面 |
| freshness | 0.2 | 80 | health.yaml 偏旧 |

执行面假绿灯会同时污染 runtime 维与探测语义。agora-gateway 暴露两处：

1. **Bug A (`scheduler.py`)**：`running_since` 不随 PID 变化重置 → 进程重启后 uptime/freshness 永久虚高  
2. **Bug B (`health_scan.py`)**：`_probe_daemons` 填了 `health_check` 却未 dump `system_health.yaml` → 健康检查永不落盘

## Decision

### D1 — 合入 runtime `24a6042`

- PID 变化时重置 `running_since` 并持久化  
- probe 后 `_dump_probed_health` 落盘 `health_check`  

### D2 — 根仓只 bump 指针

不在主仓回放 runtime 源码；子模块 main 已含修复，根仓 `projects/runtime` gitlink → `24a6042`。

### D3 — 健康分后续

本 ADR 不直接改 compass 权重。预期：刷新 `system_health` + 重跑 `compass_radar` 后 runtime/freshness 更真；复合分是否上升取决于当前 daemon 集合在线实况。

## Consequences

- 假绿灯根因在 L1 被钉死，BRIEF daemon 100% 与 runtime 探测语义对齐更可靠  
- 脏 worktree（`work/fix-agora-gateway-zombie`）上的混杂回退 **不得** 直接合 main；只 cherry 指针 bump  
