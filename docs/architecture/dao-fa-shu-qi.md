---
title: 织星道法术器 — MOF 嵌套的理论体系与硬约束
status: active
lifecycle: contract
owner: 夏明星
created: 2026-08-25
last-reviewed: 2026-08-25
type: theoretical-system
id: DFSQ/v1
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - ARCHITECTURE.md
  - projects/ecos/src/ecos/ssot/mof/m3.yaml
note: >
  道法术器不是第五套本体。硬检查入口：
  python3 bin/gac/check-sfop-slots.py （gate id sfop-slots）
  python3 bin/gac/check-execution-chain.py （gate id execution-chain, CR-EXEC-CHAIN-01）。
---

# 织星道法术器（DFSQ/v1）

> **人只进一个收件箱；跨层执行只进一条工作流脊柱；禁止平行操作系统。**

| 层 | 读法 | 已有基建 | 硬约束 |
|---|---|---|---|
| **道** | 为什么存在、什么可以存在 | Plan 北极星与证伪；M3 Element | 不可执行，只可违背后判失败 |
| **法** | 必须 / 禁止 | M2 schema；L0 `CR-SFOP-*`；script-registry × ci-surfaces × cron | `check-sfop-slots.py` + `check-execution-chain.py` |
| **术** | 怎么做 | Mesh / MOS / agent-workflow / resident 投影 | 填槽，不新开术的种类 |
| **器** | 用什么做 | `COMP-WS-*` Component；bin 脚本 | 自报槽位；至少出现在一本触发账里 |

**阻断律**

- CR-SFOP-01：每个 `COMP-WS-*` 必须声明合法 `sfop_slot` 与 `dao_layer`。
- CR-SFOP-02：活跃 Project 中 `sfop_slot=S` 至多一个，且为 `COMP-WS-omo`。
- CR-EXEC-CHAIN-01：声称活跃却不在 script-registry / ci-surfaces / cron 任一本账里 → fail-closed；现网未接线的登记项只 warn。

禁止：第二 dispatcher、第五套本体、把 AGE-v2 / resident / BCOS 当成第二控制面。
