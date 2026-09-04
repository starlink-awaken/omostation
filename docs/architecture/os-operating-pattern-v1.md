---
title: 织星脊面运行模式 v1 — Spine-Face Operating Pattern
lifecycle: contract
owner: 夏明星
created: 2026-08-25
last_updated: 2026-08-25
type: architecture-pattern
id: SFOP/v1
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - ARCHITECTURE.md
  - docs/plans/3y-bet-ledger.yaml
related:
  - docs/architecture/dao-fa-shu-qi.md
note: >
  运行时槽位语法。愿景只引用 Plan。硬检查：
  python3 bin/gac/check-sfop-slots.py （gate id sfop-slots）。
---

# 织星脊面运行模式 v1（SFOP）

> **人只进一个收件箱；跨层执行只进一条工作流脊柱；Cell / 算力 / metaos 都是脊柱的后端；resident 只投影事件不派活；北极星只计量裁决不过问生产；MOS 是记忆控制面不是又一个库。**

理论读法（道法术器嵌套 MOF）见 [`dao-fa-shu-qi.md`](dao-fa-shu-qi.md)。阻断检查：`python3 bin/gac/check-sfop-slots.py`（gate id `sfop-slots`）。

## 槽位

| 槽 | 名字 | 现任 | 禁止变成 |
|---|---|---|---|
| K | 宪法 | Plan / L4 / ecos / GaC | 价值分子 |
| H | 人类面 | cockpit / cockpit-ui | 第二顶层入口 |
| P | 感知面 | signal-sources / iris | 进化器 |
| C | 认知面 | MOS；gbrain/kairon 为后端 | 第二控制面 |
| **S** | 脊柱（唯一 dispatcher） | **COMP-WS-omo / Mesh** | 第二 OS |
| B | 后端 | runtime / AGE-v2 Cell / aetherforge / omlxc / metaos | 收件箱主人 |
| J | 投影 | resident | 自己派活 |
| O | 结果面 | attest / north_star | 用 gate 次数冒充采纳 |
| F | 织层 | agora / bus-foundation | 编排器 |

## 八律

1. 单人类面。2. 单 dispatcher（Mesh）。3. 后端不拥有收件箱。4. 投影不派活。5. 仪表不生产。6. 记忆默认 MOS。7. 宪法不是价值。8. 填槽不新槽。

新项目：声明 `sfop_slot` + `dao_layer`，不要发明新运行时。
