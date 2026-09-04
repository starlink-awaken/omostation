---
title: 织星道法术器 — MOF 嵌套的理论体系与硬约束
lifecycle: contract
owner: 夏明星
created: 2026-08-25
last_updated: 2026-08-26
type: theoretical-system
id: DFSQ/v1
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - ARCHITECTURE.md
  - projects/ecos/src/ecos/ssot/mof/m3.yaml
  - docs/architecture/os-operating-pattern-v1.md
note: >
  道法术器不是第五套本体。它是对已有 MOF 金字塔的中文读法，
  加上 SFOP 槽位作为 Component 的运行时分类。硬检查入口：
  python3 bin/gac/check-sfop-slots.py （gate id sfop-slots，阻断）。
---

# 织星道法术器（DFSQ/v1）

> **人只进一个收件箱；跨层执行只进一条工作流脊柱；禁止平行操作系统。**

| 层 | 读法 | 已有基建 | 硬约束 |
|---|---|---|---|
| **道** | 为什么存在、什么可以存在 | Plan 北极星与证伪；M3 Element | 不可执行，只可违背后判失败 |
| **法** | 必须 / 禁止 | M2 schema；L0 `CR-SFOP-*`；SFOP 八律；script-registry × ci-surfaces × cron | `check-sfop-slots.py` + `check-execution-chain.py` |
| **术** | 怎么做 | Mesh / MOS / agent-workflow / resident 投影 | 填槽，不新开术的种类 |
| **器** | 用什么做 | `COMP-WS-*` Component | 必须自报 `sfop_slot` + `dao_layer` |

运行时槽位语法：[`os-operating-pattern-v1.md`](os-operating-pattern-v1.md)。

**法的阻断律**

- CR-SFOP-01：每个 `COMP-WS-*` 必须声明合法 `sfop_slot` 与 `dao_layer`。
- CR-SFOP-02：活跃 Project 中 `sfop_slot=S` 至多一个，且为 `COMP-WS-omo`。
- CR-SFOP-04：P（感知）/ O（结果）允许空槽。空不是缺口。
- CR-SFOP-05：H 不得直接 import B。允许的 H→B 路径是经 F（agora），或 `cockpit.adapters` 作为 H 侧 B 端口（防腐层）。其它 H 文件新调用 fail-closed；baseline 键不含行号。
- CR-SFOP-06：声称活跃（`status: active` / `claimed_active: true`）的 cron 账本条目必须声明合法 `sfop_slot`；未声称活跃的存量缺槽仅 warn。声称活跃的 H 槽 cron 不得执行 B 项目路径。
- CR-DFSQ-01：`dao_layer=dao` 不得出现在 cron 执行账本。
- CR-DFSQ-02：`dao_layer=qi` 的项目树不得编写 L0 `type: required`。
- CR-X3-NS-001：北极星分子不得是治理自指量（已迁出 SFOP 编号；原 CR-SFOP-03）。
- CR-EXEC-CHAIN-01：声称活跃却不在 script-registry / ci-surfaces / cron 任一本账里 → fail-closed；现网未接线的登记项只 warn。

`toolbox` 是仓外能力平面（`build_backend: external-capability-runtime`），不要求 `COMP-WS-toolbox.yaml`。

新工作区项目加入方式：新增 `COMP-WS-<name>.yaml`，从既有枚举声明槽位，而不是发明新运行时。registry 有项目、无对应节点 → 检查器 warning（可成长：补节点即可）。缺槽或双 dispatcher → fail-closed。H→B 新调用不得写入 baseline 藏违例。

禁止：第二 dispatcher、第五套本体、把 AGE-v2 / resident / BCOS 当成第二控制面。
