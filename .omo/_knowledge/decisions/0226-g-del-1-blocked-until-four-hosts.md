---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-19
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0225-g-del-physical-multihost-gate-caliber.md
supersedes: []
amends: [0225]
---

# ADR-0226: G-DEL.1 正式 BLOCKED 直至 4 物理节点（fail-closed）

> **编号**: D1 claim `g-del-continue` → **0226**。  
> **目的**: 防止在仅 2 机可达时用模拟或 2 机调度冒充 ADR-0210「4 机调度 >99%」达标。

## Context

ADR-0210 兑现期原文：**4 机**调度成功率 > 99%。  
ADR-0225 选定方案 A（物理口径），盘点 `reachable_physical_hosts=2`（local-mac + macmini）。  
若 G-DEL.1 以 2 机 physical pass 或 in-process sim 静默变绿，会腐蚀门禁诚实性。

## Decision

1. **G-DEL.1 状态 = `BLOCKED`（fail-closed）**，登记于 `phase-scope.yaml::metrics_caliber.physical_gates[g_del_1]`。  
2. **阻塞原因**: `reachable_physical_hosts=2 < min_physical_hosts=4`（ADR-0210 四机门禁）。  
3. **解除条件**: 盘点/探测 `reachable_physical_hosts ≥ 4` 且物理测量 `meets_physical_gate=true`。  
4. **CI**: `phase-gate-check` 拒绝  
   - sim 环境填 G-DEL.1 官方 pass 字段；  
   - 物理报告中 `physical_hosts < 4` 却 `meets_gate`/`meets_physical_gate=true`。  
5. **G-DEL.3** 仍允许 **≥2** 物理机（跨机同步可用 2 机真机达标）。

## Consequences

- G-DEL.1 不得在 2 机底座上宣称官方达标。  
- 硬件扩容（y7000p SSH / cloud）可并行，但不阻塞 G-DEL.2b/3/4/5b。  
