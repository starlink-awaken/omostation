---
title: 织星脊面运行模式 v1 — Spine-Face Operating Pattern
status: active
lifecycle: contract
owner: 夏明星
created: 2026-08-25
last-reviewed: 2026-08-25
type: architecture-pattern
id: SFOP/v1
horizon: Y1 日历剩余（2026-08 → 2027-07）；Y2 仅在 Y1 总门后解冻
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - ARCHITECTURE.md
  - docs/plans/3y-bet-ledger.yaml
integrates:
  - docs/architecture/digital-twin-blueprint-v1.md
  - docs/architecture/blueprint-multi-agent-execution-control-v1.md
  - docs/architecture/wave-gate-bet-map.md
  - docs/architecture/resident-agent-system-v1.md
  - docs/architecture/bcos-system-v1.md
  - docs/architecture/memory-os.md
  - docs/architecture/sustainable-value-loop-v1.md
  - docs/architecture/north-star-v3-design.md
  - docs/architecture/project-strategy-v1.md
  - docs/plans/age-v2-long-term-roadmap.md
  - docs/plans/2026-08-25-y1-value-loop-phase.md
note: >
  本文是运行时语法，不是第二套三年规划，也不是第 N 套 Wave 编号。
  愿景/总门/证伪只引用 Plan。分层/BOS/入口契约只引用 ARCHITECTURE.md。
  执行拆分只引用 3y-bet-ledger。本文只回答：散落的子系统各自占哪个槽、
  彼此如何嵌、禁止长成什么形状、现有命令怎么接到一条金线上。
---

# 织星脊面运行模式 v1（SFOP）

## 0. 一句话

> **人只进一个收件箱；跨层执行只进一条工作流脊柱；Cell / 算力 / metaos 都是脊柱的后端；resident 只投影事件不派活；北极星只计量裁决不过问生产；MOS 是记忆控制面不是又一个库。**

这不是新系统。这是把已经存在的 Plan 四面一脊、ARCHITECTURE 分层、8D 观测、数字分身 Episode/Cell、resident、BCOS、AGE-v2、可持续价值环 **收成同一套槽位语法**，让后续工作只能填槽，不能再开槽。

---

## 1. 为什么要模式，而不是第 15 份架构文

仓库里已经有多套都能自圆其说的架构语言，彼此几乎不互相约束：

| 语言 | 文档 | 它真正回答的问题 |
|---|---|---|
| 三年战略 | Plan | 为什么做、何年何门、证伪 |
| 代码分层 | ARCHITECTURE.md | 东西放哪、依赖朝哪 |
| 信息流 | Plan §3.1 四面一脊 | 信号怎么变成署名产出 |
| 8D 全景 | cockpit panorama | 观测切面 |
| 数字分身 | digital-twin-blueprint | Episode / Mandate / Cell |
| 执行控制 | blueprint-multi-agent + wave-gate-bet-map | W0–W6 / G-1–G7 ↔ BET |
| 常驻 | resident-agent-system-v1 | 五角色事件投影 |
| 业务域 | bcos-system-v1 | 信号路由 / 进化 / 北极星 |
| 价值环 | sustainable-value-loop + north-star-v3 | 时间账本 |
| 记忆 | memory-os | MOS 控制面 |
| 算力落地 | AGE-v2 roadmap | 多 Cell 自治（易长成第二 OS） |
| 九维战略 | project-strategy-v1 | 场景/功能/旅程诊断 |
| 阶段契约 | 2026-08-25-y1-value-loop-phase | 日历重同步 S0–S3 |

缺的不是愿景，是 **语法**：一个组件同时可以自称「内核 / 编排 / 落地 OS / 进化引擎 / 价值层」。模式的工作是给每个组件 **唯一槽位**，再规定槽与槽之间只允许哪些箭头。

编号纪律（继承 wave-gate-bet-map）：权威 ID 只有 Plan 的 Y1Qx 与台账 `BET-*`。本文 **不** 发明 SFOP-01、W7、Phase 8。讨论可用槽位名；落地必须落到既有命令和既有 bet。

---

## 2. 模式本体：7 个槽位

```
                    ┌─────────── H 人类面 ───────────┐
                    │  cockpit: inbox / journeys     │
                    │           / outcomes / memory  │
                    └──────────────┬─────────────────┘
                                   │ 只读意图 / 只写裁决
        P 感知面                   ▼
   外部世界 ──► signal-sources ──► InboxItem ──► S 脊柱（唯一 dispatcher）
                iris / router                      OMO Workflow Mesh
                手动投递(degraded)                     │
                                                       ├► B 后端
        C 认知面                                       │   runtime workers
   MOS 控制面 ◄──── 回流 decision_outcome               │   AGE-v2 Cell
        │          ▲                                   │   aetherforge/omlxc
        ▼          │                                   │   metaos（决策，不派工）
   gbrain / kos    │                                   │
   （能力后端）     │                                   └► J 投影
                   │                                       resident 五角色
        O 结果面   │                                       （订阅 Mesh 事件）
   Adjudication ───┘
   attest-review
   north_star（只计量）

        K 宪法     Plan / L4 / ADR / GaC / MOF
                   约束产能，不充当价值分子
```

| 槽 | 名字 | 唯一问题 | 现任主人 | 状态 |
|---|---|---|---|---|
| **K** | 宪法 | 什么允许做、什么算失败 | Plan + L4 + ADR + GaC + MOF | [EXISTS] |
| **H** | 人类面 | 主人每天打开什么 | cockpit 四界面 | [EXISTS] 未成习惯 |
| **P** | 感知面 | 外部信号从哪进、如何去重 | `signal-sources.yaml` + iris + `signal_router` + 手动投递 | [EXTEND] 流量≈0 |
| **C** | 认知面 | 世界/自我/意图/因果存在哪 | MOS `bos://memory/mos/*` | [EXTEND] 门面在、旁路在 |
| **S** | 脊柱 | 谁有权改变 WorkflowRun | OMO Workflow Mesh | [EXISTS] 需关掉平行入院 |
| **B** | 后端 | 步骤实际跑在谁身上 | runtime / AGE-v2 Cell / aetherforge / metaos | [EXISTS] Cell 有第二 OS 倾向 |
| **J** | 投影 | 事件如何变成记忆/告警/提案 | resident 五角色 | [EXISTS] 空转、模板沉淀 |
| **O** | 结果面 | 人类接受/修改/拒绝记在哪 | adjudication + attest-review + north_star | [EXTEND] 工具在、周计数无 |

槽比层少。分层（L0–L4/I0/X/M0）继续管仓库边界；槽管 **运行时责任**。一个项目可以出现在多个层的依赖里，但 **对运行时只能占一个主槽**。

8D 是观测切面，映射到槽，而不是第八套运行时：

| 8D | 槽 |
|---|---|
| LifeOS 意图 | H + K |
| C2G 策略 / Goals | K（ingress 进台账，不进脊柱） |
| Agora 蜂群 | 织层（槽间路由，见 §2.1） |
| AetherForge 算力 | B |
| AGE-v2 落地 | B（Cell），禁止升为 S |
| MOS/KOS 记忆 | C |
| X-Plane 熵减 | K 的执行器（GaC / rot-defense），分子不得进 O |

### 2.1 织层不是第 8 个业务槽

Agora + BOS URI 是 **槽与槽之间的总线**。它发现和转发，不拥有 Inbox、不推进 WorkflowRun、不写裁决。新的 `bos://` 域必须声明服务的是哪个槽，禁止「BOS 自己成为编排器」。

---

## 3. 散件入槽（系统清单）

每个现有子系统只许出现在一行的「主槽」。第二列是允许的兼职（只读或被调用）。

| 组件 | 主槽 | 允许兼职 | 禁止变成 | 落地动作 |
|---|---|---|---|---|
| Plan / ADR-0410 | K | — | 进度仪表 | 引用，不改写北极星 |
| GaC / rot-defense / scorecard | K | 观察 | 价值分子 | 分数退出价值面板 |
| MOF / ecos / M1 YAML | K + S 入院校验 | DSL | 第二 dispatcher | 入院走 Mesh，不单独派工 |
| model-driven | K（M0，ADR-0412 留子仓） | cockpit 适配 | 内核 | 不降库、不扩入口 |
| cockpit CLI/Web | H | 对 S/C/O 的薄壳 | 业务引擎 | 日常只暴露四界面 |
| `scene-card-decision-inbox` | H/P 缝 | — | 工作流引擎 | 金线入口 |
| `signal_router` / `signal-poller` | P | — | 进化器 | 只路由到 inbox |
| iris / 外部连接织层 | P | — | 执行器 | 凭证不进描述符 |
| MOS / `cockpit memory` | C | — | 第二知识库 | 默认读写只走 MOS |
| gbrain / kairon-kos | C 的能力后端 | — | 控制面 | 不互融；禁旁路直打 |
| OMO Workflow Mesh | **S** | — | — | **唯一 dispatcher** |
| agent-workflow / WorkPacket / clone | S 的工程入院 | K 的纪律 | 个人价值环 | 工程事件标 `out_of_value` |
| Exact Capability Binding | S 的能力门 | — | 价值证明 | Cell 必须过同一扇门 |
| journey-runner / scene cards | S 的产品投影 | H | 场景数量游戏 | 同时只活 1 张卡 |
| AGE-v2 Agent Cell / cartridge / LSP | **B** | — | 第二 OS / 第二 dispatcher | `cell_*` 必须经 Mesh admission |
| aetherforge / omlxc | B | — | 编排器 | infer/预算，不收件 |
| runtime workers | B | — | 控制面 | ACK/lease 回 Mesh |
| metaos | B（编排决策） | — | 与 omo 双核 | 维持 ADR-0423 边界 |
| resident 五角色 | **J** | — | 派工面（execute 不得绕 Mesh） | 只订阅；execute 只能 ack 已入院步骤 |
| BCOS `evolution_engine` | J 的提案源 / **默认冻结 apply** | — | 自动改脊柱 | S0–S3 `--apply` 关闭 |
| BCOS `north_star_*` | **O 的仪表** | — | 用治理 tick 冒充省时 | 只读裁决与主人确认 |
| attest-review / weekly-review | O | H 的周日仪式 | 自动完成 | 必须主人按键 |
| digital-twin Episode/Mandate | S 的对象模型 | — | 第四套 ID | 挂 WorkPacket，不另起 BET-EP-* |
| family-hub / observability | 暂停 | — | 复活当主环 | CONV-3 维持 |
| SEMA / AST merge | 工具（K/S 卫生） | — | Phase 主叙事 | 冻结扩展 |
| C2G / Goals | K 的策略 ingress | — | 运行时调度 | 物化成 bet 后才进 S |

---

## 4. 模式八律（可执行的形状约束）

1. **单人类面。** 新的顶层人类入口（CLI 家族、Web 控制台、聊天主入口）默认拒绝。要加能力，加在四界面之一后面。
2. **单 dispatcher。** 能把工作从「建议」变成「正在跑」的，只有 Mesh admission。`cockpit cell`、`resident execute`、`agent-runtime`、裸 KEMS dispatch、`evolution_engine --apply` 都不是主路径。
3. **后端不拥有收件箱。** Cell / forge / runtime 不读主人意图、不写 InboxItem。
4. **投影不派活。** resident 可以提案、沉淀、告警；要把提案变成执行，必须再进 H（主人点）或 S（已有 Mandate）。
5. **仪表不生产。** north_star / scorecard / compass_radar 禁止作为「本周价值」的唯一证据。O 槽只认 `human_verdict ∈ {accepted, edited, rejected, ignored}`。
6. **记忆默认 MOS。** 主环读写不直打 gbrain/kairon；旁路必须标 `degraded`。
7. **宪法不是价值。** GaC 全绿、BET done、成熟度 7.7→9.0、PR 数，全部是 K/S 的工程观察量，进不了北极星分子。
8. **填槽不新槽。** 发现缺口先问「哪个槽缺接线」。答案若是「需要新的运行时/新的 Wave 编号/新的操作系统」，方案作废。

这八律比任何新 ADR 都优先：与八律冲突的路线图（含 AGE-v2「多 Cell 自治生态」、BCOS 自动进化落地、可持续价值环把 compass_radar_run 算成省时）在冲突处让路，文档降为「槽内扩展愿望」，不是运行时主线。

---

## 5. 因果对象（沿用已有类型，不新造前缀）

一条合法的个人价值因果链：

```
Signal (signal-sources / 手动投递)
  → InboxItem (scene-card-decision-inbox / cockpit inbox)
  → WorkPacket | Episode（同一入院，挂 bet 或 scene_id）
  → Mesh WorkflowRun / Step
  → Backend receipt（runtime | Cell | forge）
  → EvidenceRecorded（OMO）
  → Adjudication / attestation（主人三键）
  → MOS decision_outcome（human_verdict + 修订差）
  → north_star 只读投影
```

工程建设链（agent-workflow / GaC / clone）是 **平行的系统建设者链**，必须打 `out_of_value`，不得流入上图最后两步的分子。这是数字分身蓝图「系统建设者责任不得凌驾人生责任」的运行时写法。

W0–W6 / G-1–G7 继续是蓝图讨论语言，closeout 仍落 BET（wave-gate-bet-map 不变）。

---

## 6. 产品形态（槽 H 的唯一皮肤）

三年只做一个形态（Plan §6）：

| 界面 | 槽 | 节奏 | 现有入口（EXTEND，不新造） |
|---|---|---|---|
| inbox | H←P | 每日 | `cockpit inbox` / `cockpit bos-inbox` / decision-inbox API / `scene-card-decision-inbox.py` |
| journeys | H←S | 每周 | `cockpit journey` / `cockpit workflow` / `journey-runner.py` |
| outcomes | H←O | 每周 | `attest-review.py` / `weekly-review` / `cockpit bcos` 只读 |
| memory | H←C | 按需 | `cockpit memory` / `bos://memory/mos/*` |
| signals | H←P 运维 | 按需 | `signal-poller.py --health` / `cockpit resident signals` |

`cockpit daily` 今天是研究摘要，**不是** 这条金线。不要把它冒充 inbox。金线日常命令见 §8。

---

## 7. 目标运行时（把平行脊柱收掉之后）

```
人类：cockpit {inbox,journey,outcomes,memory}
Agent：bos://… 经 Agora
两者要跑步骤 → 只能 Mesh admission
                ├ backend: runtime | cell | forge | metaos-decision
                └ projector: resident.{sediment,decision,monitor,heartbeat}
完成 → Evidence → 主人裁决 → MOS decision_outcome
宪法：Plan 门 + GaC；进化提案可以生成，apply 必须再进 H 或 S
```

相对今天的变化不是加模块，是 **关入口**：

- AGE-v2：从「落地 OS」降为 B。长期路线图 Phase A/B（Cell pool / Cell 市场）在 Y1 总门前不实施。
- resident execute：只能处理已入院的 `WorkPacketDispatched`；禁止自己成为触发器。
- evolution_engine：观察/提案保留；`--apply` 在 S0–S3 视为违规主路径。
- north_star v3 A 轴：删除「compass_radar_run / agent_tick 算省时」；A 轴只接裁决与主人确认（与 Plan 一级指标对齐）。

---

## 8. 怎么落地（接线，不施工新平台）

落地分成两条：一条 **金线**（主人本周能走完），一条 **收敛**（把其它入口降级）。两条都只改接线与门禁，不新建项目。

### 8.1 金线（S0 打开波次，7–14 天）

目标：任意一周，主人用已有命令走通 P→H→S→O→C 回流。允许感知面 `degraded` 手动投递。

| 步 | 槽 | 现有命令 | 验收 |
|---|---|---|---|
| 1 投入信号 | P | `python3 bin/bc-os/signal_router.py --inbox <dir> --json` 或 `cockpit resident signals` 或把一条笔记/待决手工写入 inbox 引擎 | 出现 1 条非治理自测 InboxItem |
| 2 打开收件箱 | H | `cockpit inbox` / `cockpit bos-inbox` | 主人能看见并三键（采纳/改后采纳/忽略） |
| 3 最小旅程 | S | `python3 bin/ssot/journey-runner.py run …`（默认 dry-run；真跑须走 Mesh，禁止 SceneWatcher 直调） | 有 WorkflowRun 或明确 waiting 节点 |
| 4 若需算力/Cell | B | 只作为该 Run 的 step backend；`cockpit cell` 不得作为第 1 步 | Cell 带同一 WorkPacket / admission id |
| 5 周日签核 | O | `python3 bin/ssot/attest-review.py --since 7` | 产生 attestation；治理样本标 `out_of_value` |
| 6 回流记忆 | C | 裁决写入 MOS `decision_outcome`（经 `bos://memory/mos/*` 或 omo PersonalEpisodeService） | 能按 decision_id 读回 human_verdict |
| 7 只读仪表 | O | `python3 bin/bc-os/north_star_meter_v2.py --json` | 报告引用裁决，不引用 gate 次数 |

**金线失败判定：** 任何一步用「再写一个 cockpit 子命令家族 / 再开 AGE-v2 Phase / 再做评分器」来补。正确补法是修这一步的现有命令。

S0 退出（与阶段契约一致）：连续两周信号 > 0，且至少一周 3 条非 `out_of_value` 裁决。

### 8.2 收敛（S1，2026-11 → 2027-01）

按 W0-04 的 Keep / Bridge / Absorb / Retire，但对象换成 **派工入口**（不是再扫一遍项目）：

| 入口 | 今日 | S1 目标 |
|---|---|---|
| Mesh admission | Keep | 唯一生产派工 |
| agent-workflow start | Keep | 只服务系统建设者链 |
| `cockpit cell` / AGE-v2 cell_execute | 平行风险 | Bridge：拒绝无 admission id 的调用 |
| `omo resident execute --yes` | 可绕 | Bridge：无 WorkPacketDispatched 则拒绝 |
| KEMS 裸 dispatch | 已 fail-closed | Retire 死入口，保持关闭 |
| `evolution_engine --apply` | 可改状态 | Keep 观察；apply 需主人 Mandate |
| `cockpit daemon` / Agora 2.0 | 总线 | Keep 为织层；不是 dispatcher |
| 670 bin 直接调用 | 人类主入口 | Absorb 进 cockpit 发现层；人类日常只用四界面 |

Exact Capability Binding（已有 spec）是 S 槽的门：Cell 合并进生产路径的前提是同一 WorkPacket、同一 admission、同一 receipt。做不到就留在 B 的实验区。

### 8.3 记忆默认路径（S2，2027-02 → 04）

| 动作 | 文件/命令 | 完成定义 |
|---|---|---|
| 主环读 | skill `memory-recall` / `cockpit memory` | 默认 `bos://memory/mos/*` |
| 主环写 | MOS write + OMO evidence | decision_outcome 带 human_verdict |
| 旁路清单 | gbrain/kairon 直打 | 标 degraded；八周调用量趋 0 |
| 不互融 | ADR-0413 | 禁止「统一语言栈」立项 |

### 8.4 收口（S3，2027-05 → 07）

对照 Plan Y1 总门，用本模式翻译成槽位语言：

- P：每周真实信号有数（不是 0）。
- H：inbox 打开频率不再是 0。
- S：平行 dispatcher 入口为 0（或全部 Bridge 拒绝）。
- O：每周 ≥ 3 条采纳，采纳率 ≥ 30%，连续周开始累积。
- C：MOS 默认路径已满八周。
- K：指名冗余（零调用脚本、无消费者模块、休眠项目、双栈检索旁路、多余 required 规则、多余调度入口）逐项清零；`test_loc` 保护量守住。

不过门：延长 Y1，禁止把 AGE-v2 多 Cell 生态、第二场景、跨场景学习当主线。

---

## 9. 工程落地检查单（agent 用）

开始任何实现前回答：

```
☐ 这是填哪个槽？（K/H/P/C/S/B/J/O 必须恰好一个主槽）
☐ 是否新增人类入口或 dispatcher？是 → 停
☐ 现有哪条命令已经覆盖 80%？列出路径
☐ 金线哪一步会变绿？变不绿就不是本阶段的活
☐ 价值证据是 human_verdict 还是 gate/PR/分数？后者 → out_of_value
☐ 要不要新 bet？没有日历验收问题（信号/inbox/入口收敛/MOS/归档）→ 不要开
```

第一个可提交的实现切片（在主人拍板金线之后，尺寸由小到大）：

1. **文档约束**：AGE-v2 路线图、BCOS `--apply`、north_star A 轴，标明受本模式约束（本轮可做）。
2. **拒绝平行派工**：`cell_execute` / `resident execute` 无 admission id 则非 0 退出（S1，要测试）。
3. **inbox 手工投递**：一条命令把 stdin/文件变成 InboxItem（P degraded，S0）。
4. **attest → decision_outcome**：签核写 MOS（O→C，S0–S1）。
5. **north_star 只读裁决**：A 轴不再累加 radar/tick（O，S1）。

1 可在拍板当天做。2–5 各是一个 bet 量级，总数仍宜 ≤ 5。

---

## 10. 红队（模式本身）

| # | 攻击 | 回应 |
|---|---|---|
| 1 | 又一份架构，N 变成 N+1 | 本文是语法。愿景/分层/台账不被替代；冲突时其它路线图让路 |
| 2 | 7 个槽还是太多 | 运行时只记 4 面 + 1 dispatcher。H/K/J/B 是 4 面的皮肤、宪法、投影、手脚 |
| 3 | Mesh 当唯一 dispatcher 是否选错 | ARCHITECTURE 已规定 WorkflowRun 只认 OMO 事件。换 dispatcher = 改宪法，不在本模式授权 |
| 4 | Cell 降级会浪费 AGE-v2 | 浪费的是第二 OS。Cell 作为 B 仍然承重 |
| 5 | 金线 7 步主人走不完 | 允许 P degraded；3-node 旅程；15 分钟剧本。走不完就减步，不加平台 |
| 6 | north_star 删 tick 后分数崩了 | 崩了说明先前在测环 III。崩是纠偏 |
| 7 | 没有新 bet 如何落地 | 先接线现有命令。bet 只为「日历验收仍未满足」的缺口服务 |
| 8 | 与可持续价值环 L2 自进化冲突 | 自进化提案可以留在 J；apply 必须再进 H 或 S。Y1 不授权结构自动落地 |

---

## 11. 文档关系（嵌套，不并列）

```
Plan（愿景/日历/总门）
  └── 本模式（运行时语法 / 槽位）
        ├── ARCHITECTURE.md（仓库分层与 BOS，槽的物理位置）
        ├── digital-twin + execution-control + wave-gate-bet-map（S 的对象与门）
        ├── resident-v1（J 的规格）
        ├── bcos-v1 + north-star-v3 + sustainable-value-loop（P 路由 + O 仪表；进化=冻结 apply）
        ├── memory-os（C）
        ├── AGE-v2 roadmap（B 的扩展愿望，Y1 总门前不升格）
        └── 阶段契约 2026-08-25-y1-value-loop-phase（日历 S0–S3 = 本模式的铺设时间表）
```

变更规则：改槽位归属 → 改本文。改愿景 → 改 Plan（需主人）。改分层依赖 → 改 ARCHITECTURE。改季度任务 → 改台账。禁止在 AGE-v2 / BCOS / resident 文里另写一套「系统主线」。
