---
title: Wave/Gate ↔ BET 台账差异对齐
type: architecture-map
owner: governance-team
created: 2026-08-15
bet: BET-Y1Q1-T6-02
lifecycle: contract
does_not_invent: 第四套 ID。Wave/Gate 名称保留蓝图原文；BET 轨道保留 3y-bet-ledger.yaml。
ssot:
  waves: docs/architecture/digital-twin-blueprint-v1.md
  gates: docs/architecture/blueprint-multi-agent-execution-control-v1.md
  bets: docs/plans/3y-bet-ledger.yaml
  north_star: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
last_updated: 2026-08-18
---

# Wave / Gate ↔ BET 映射

权威 ID 只有两套：**蓝图的 W0–W6 / G-1+G0–G7**，和 **台账的 BET-Y1QxTx / T1–T8（含 T6-SUBTRACT）**。
本页是对照表，不是第三套编号，也不给 Episode / Mandate / WorkPacket 另起前缀。

北极星（Plan §0.3）：织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。

落地执行仍走既有链：`Plan` → `3y-bet-ledger` → `agent-workflow start --bet` → `closeout` → `.omo/_knowledge/retros/<BET-ID>.md`。

## 1. Wave → 现行 BET 轨道

| Wave | 蓝图职责 | 最接近的 BET 轨道 | 对齐程度 |
|---|---|---|---|
| W0 | 事实基线、冻结新顶层概念、假绿门禁 | **T1-TRUTH** | 接近 1:1（D0/D1/指针/止血） |
| W1 | MOF 核心模型、SQLite Ledger | **T5-ORCH**（omo/ecos 写面） | 部分。MOF/L0 另有 governance-evolution，不是独立 BET 轨道 |
| W2 | 瘦 OMO 主权 / Mandate / Gate | **T5-ORCH** + **T3-COGNI** | 多对一。蓝图「瘦内核」与台账「编排硬化/心智」切开 |
| W3 | 真实信号、只读承诺 | **T2-PERCEPT** | 接近 1:1 |
| W4 | Decision Inbox、监督执行 | **T8-SURFACE** + **T4-OUTCOME** | 一对多。Inbox 在 T8，裁决事件在 T4 |
| W5 | Outcome / Memory / Agent Cell / Evolution | **T3-COGNI** + **T4-OUTCOME** + **T6-EVOLUTION** | 一对多。Cell/技能结晶不在 W0–W6 原表里独立成轨 |
| W6 | Canary、收敛、退役 | **T6-SUBTRACT** + **T7-SCENE** | 部分。减法年是 Y1 主轴，场景生命周期是另一条轨 |

## 2. Gate → 现行 BET / 既有执行器

| Gate | 蓝图判定 | 现有执行器（不新造 ID） | BET 挂钩 |
|---|---|---|---|
| G-1 Readiness | workflow / 锁 / 入口 | `agent-workflow compliance`、`observe` | T1-TRUTH |
| G0 Strategy | 非重复、依赖、WIP | `bet-ledger claim-check` | 全轨道 |
| G1 Packet | AC、写面、回滚 | bet `done_when` / `write_surfaces` / `circuit_breaker` | 全轨道 |
| G2 Admission | 身份、权限、健康 | `agent-workflow` profile 矩阵、`doctor` | T1 / T5 |
| G3 Isolation | worktree、run、claim | `gac-worktree claim`、ADR-0203 claim | T1-00 / D3 |
| G4 Execution | 心跳、D0、预算 | D0 `git add`、`circuit_breaker` | D0/D2 |
| G5 Verification | 独立测量、证据 | `agent-workflow verify` + `chain-bind-check` | 本 bet 补的链门 |
| G6 Integration | 兼容、门禁、canary | `make gac-local-gate`、PR | 全轨道 |
| G7 Outcome | 真实人类结果 | retro + T4 adjudication | T4-OUTCOME / D5 |

## 3. 无法一对一的项（保持原 ID，只记差异）

| 项 | 为什么对不上 | 处理建议 |
|---|---|---|
| Episode / Mandate / WorkPacket | 蓝图对象，台账没有同名 bet | 继续作为 OMO/blueprint 概念；落地时挂到已有 BET 的 `write_surfaces`，**不要**发 `BET-EP-*` |
| G-CONV.1–7 | 2026-07 收敛台账，已被 G-Y1Q1 / BET 事实上取代 | 保持归档/指针，不把 G-CONV 数字改写成 BET 号 |
| T6-EVOLUTION | 活轨道，W0–W6 表没有「技能结晶/归因链」波次 | 映射为 W5 的旁路能力，不新开 W7 |
| T9-OBSERV | 活轨道，蓝图把可观测散落在 G-1/Watchdog | 映射为 G-1 持续条件，不新开 Wave |
| 11 套 Phase 编号 | Markdown 硬编码 Phase，与 Y1Q×T 并存 | 不在本表统一编号；新文档只引用 BET-Y1QxTx 或 W0–W6 原文 |
| `goals/current.yaml` 的 `phase: 49` | 运行时投影，不是执行轨道 | 继续当 system.yaml 投影，禁止当第三套进度 |
| 场景卡 9 + journey 11 + `_truth/scenarios` | 产品身份，不是 Wave | D3/D5 未授权本轮重写；只在 T7-SCENE 消化 |

## 4. 使用规则

1. Agent 认领工作时写 **BET-Y1QxTx-nn**，不要写「做 W3」代替台账 ID。
2. 蓝图讨论可以用 W0–W6 / G-1–G7，但 closeout 证据必须落到 bet + run + retro。
3. 发现新工作缺口：先改 `3y-bet-ledger.yaml` 增 bet，或修订本对照表的「无法一对一」行。禁止发明第四套前缀。
