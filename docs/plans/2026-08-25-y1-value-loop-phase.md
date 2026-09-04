---
title: 织星中段蓝图迭代 — 日历重同步、四面一脊与 Y1 收口
lifecycle: plan
owner: 夏明星
created: 2026-08-25
last_updated: 2026-08-25
type: phase-blueprint
horizon: 2026-08 → 2027-07 (Y1 日历剩余) · 2027H2 仅在 Y1 总门通过后解冻
supersedes:
  - docs/plans/two-week-integration-and-forward-plan.md
does_not_supersede:
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/plans/3y-bet-ledger.yaml
  - .omo/_knowledge/decisions/0410-strategy-mainline-plan-supersedes-panorama.md
related:
  - ARCHITECTURE.md
  - docs/architecture/project-strategy-v1.md
  - docs/architecture/memory-os.md
  - docs/architecture/digital-twin-blueprint-v1.md
  - docs/reports/2026-08-20-blueprint-strategy-retrospective.md
  - docs/reports/2026-08-24-resident-system-deep-review.md
  - .omo/_knowledge/decisions/0412-model-driven-disposition.md
  - .omo/_knowledge/decisions/0413-gbrain-kairon-merge-disposition.md
  - .omo/_knowledge/decisions/0423-conv3-project-convergence.md
note: >
  本文是阶段契约，不是第二套三年规划。愿景/证伪/Y1–Y3 总门只引用 Plan。
  规模读 `bet-ledger.py surface|status`，成熟度读 `maturity-scorecard.py`，不在正文追更。
  前一短版（四周 VL-1）降为 S0 的打开波次，不再作为阶段本身。
---

# 织星中段蓝图迭代 — 日历重同步、四面一脊与 Y1 收口

## 0. 一句话

**台账上的 Y1Q3 已经关账，日历上的 Y1 才刚开始。** 2026-08 仍处在三年规划的 Y1Q1（止血·接通·起跑）。把九个月的季度压缩进三周、再把 AGE-v2 / resident / 成熟度 9.0 当成「下一阶段」，是用工程速度改写了战略时间。下一阶段不是四周冲刺，而是：**把执行日历拉回 Plan，用十一到十二个月做完真正的 Y1——接通两端、收敛编排入口、按名单减法——Y1 总门（2027-07）不过则不进入 Y2。**

| 维度 | 判定 |
|---|---|
| 愿景 | `VALID`。北极星与 2027-12-31 证伪条件不改 |
| 战略时间 | `DESYNCED`。Ledger Y1Q3=done，Plan Y1Q1 窗口是 2026-08→10 |
| 代码分层 | `SOUND`。L0–L4 / I0 / X 依赖方向仍对 |
| 信息形状 | `WRONG`。中段过厚，感知/结果两端空 |
| 编排拓扑 | `FRAGMENTED`。N 套调度器并行，缺唯一 dispatcher |
| 产品形态 | `UNBUILT IN USE`。规划是一个收件箱+一条时间线+一个记忆面板，日常仍是 670 个 bin |
| 成熟度分数 | `NOT THE GOAL`。现场 scorecard 7.7 / 目标 9.0；T10 宣称 9.0 为声明领先 |
| 下一阶段 | **日历重同步后的 Y1 剩余**（S0–S3 → 2027-07），不是 AGE-v2 Phase 8 |

---

## 1. 三套坐标系，只允许嵌套，不允许再长一套

系统现在同时用三套语言描述自己。蓝图必须先规定它们怎么嵌，否则「下一阶段」会继续变成第四套叙事。

```
① 代码归属（ARCHITECTURE / project-registry）     回答：东西放哪
   L4 Self → L3 Cockpit → I0 Agora → L2 引擎 → L1 运行时 → L0 协议
   X1–X4 横切治理     M0 model-driven 横切建模

② 信息流动（Plan §3.1 四面一脊）                   回答：信号怎么变成署名产出
   外部世界 → 感知 → 认知 → 执行脊柱 → 结果 → 回流认知

③ 空间八维（cockpit panorama / 8D）               回答：全景观测切面
   LifeOS 意图 → C2G 策略 → Goals → Agora 蜂群
   → AetherForge 算力 → AGE-v2 落地 → MOS/KOS 记忆 → X-Plane 熵减
```

**嵌套规则：**

- ① 是仓库边界，稳定，不为本阶段重画。
- ② 是战略主轴。Y1 成败只看 ② 的两端是否接通、脊柱是否唯一。
- ③ 是观测切面，不是新的运行时。AGE-v2、AetherForge、X-Plane 都是 ② 里脊柱或横切的**后端/仪表**，不能各自再长一个操作系统。

一句话架构：

> **一个人的业务操作系统 = 每日一个收件箱，背后一条工作流脊柱，记忆只走 MOS 控制面，算力与 Cell 都是脊柱的后端，治理只做熵减不做产能。**

证伪条件仍是 Plan §0.3：到 2027-12-31 未能连续 12 周每周 ≥ 3 条被本人采纳的建议，定位转为纯知识管理或关停。Y1 总门在更早的 **2027-07**：冗余清零 + 保护量守住 + 每周 ≥ 3 条采纳 + 采纳率 ≥ 30%。不过门则 **Y2 不启动扩展，继续做 Y1**（Plan §7）。这是长周期的硬闸，四周习惯门只是它的起点。

---

## 2. 近月回顾：资产与时间作弊

近月四幕（立宪 → 打假 → 关账 → 中段爆炸）仍成立，见前短版。长周期真正要记住的不是 PR 清单，是两件结构事实。

### 2.1 做成了的承重件（冻结为资产，禁止重造）

| 承重件 | 位置 | 在 ② 里的角色 |
|---|---|---|
| 三年规划 + ADR-0410 | L4 | 宪法 |
| agent-workflow / clone / GaC | L2–L3 | 脊柱的入院与证据 |
| OMO Workflow Mesh | L2 | **目标唯一 dispatcher** |
| 知识层目录归一（ADR-0413） | L2 | 双头治理面已收；能力面仍双栈 |
| omo-debt + c2g 内包 | L2 | 治理面归并已做 |
| MOS 控制面（ADR-0372） | L2 | 认知/记忆的门面（多数后端仍旁路） |
| cockpit 作为人类入口契约 | L3 | 产品三界面的唯一壳 |
| Agora BOS 路由 | I0 | 跨层调用总线 |
| aetherforge / omlxc | L1/X | 算力后端 |
| 完成语义（WorkPacket / attestation / evidence 三轴） | L0–L2 | 结果面的计量工具 |
| CONV-3（ADR-0423） | 边界 | family-hub 暂停、mesh-router 归档、metaos 划界 |

### 2.2 时间作弊：Ledger 季度 ≠ Plan 季度

Plan §7 的 Y1 日历：

| Plan 季度 | 日历 | 唯一验收问题 | Ledger 在 2026-08 的状态 |
|---|---|---|---|
| Y1Q1 | **2026-08→10** | 过去一周真实工作信号 > 0 | 标 done |
| Y1Q2 | 2026-11→2027-01 | 这个月接受了几条建议、改了什么 | 标 done |
| Y1Q3 | **2027-02→04** | 知识层归并；MOS 唯一读写 | 目录归并已做，标 done |
| Y1Q4 | 2027-05→07 | 六项冗余清零 + 保护量 | 标 done |
| Y2 | 2027 全年 | 心智全量、第二场景、修订率下降 | 技术 bet 大量标 done |
| 愿景证伪 | **2027-12-31** | 连续 12 周每周 ≥ 3 条采纳 | 周计数尚未开始 |

知识层归并按 Plan 本应在 2027-02，实际 2026-08 做完目录归一——这可以算「提前消耗不可逆点」，**不能**顺便把 Q1 的「信号 > 0」和 Q2 的「有修订内容」一起勾掉。AGE-v2 Phase 5–7、resident、BCOS 进化引擎、成熟度冲刺，是把 Y2/Y3 的中段能力提前生产，同时 Y1Q1 的唯一验收问题仍未满足。

**长周期第一原则：执行跟日历走，不跟台账的 done 标签走。** 台账空了只说明「按当前拆分没有可领工程项」，说明拆分已经和战略时间脱节。VL-1 不再新开 12 条 bet 刷进度；要开也只开「日历 Y1Q1–Q4 尚未被事实满足」的项。

### 2.3 体积（观察量，指向减法失败）

相对 2026-08 基线：`src_loc` +27%，`bin_scripts` +116%（310→670），ADR +42，`gac_required` +4。`test_loc` 上升（保护量未破）。合成协作场景 221→5 是真减。`projects/` 自 8/1 净值约 +56 万行。Y1 是净减法年，这条曲线是反的。

---

## 3. 目标架构（加深的是形状，不是新层）

### 3.1 信息流：四面一脊必须成为运行时，而不只是战略图

```
外部世界（邮件/笔记/日历/工程待决/对话）
        │  ① 感知面  薄层   [EXTEND]  kairon/iris + signal-sources.yaml
        │                         + 手动投递（degraded 必须可见）
        ▼ Signal
   ② 认知面  薄层   [EXTEND]  MOS：world_snapshot / capability_calibration
        │                         / intent / decision_outcome（枢纽）
        ▼ Intent
   ③ 执行脊柱  唯一   [EXISTS→CONVERGE]
        │     OMO Workflow Mesh
        │       admission → dispatch → lease → run → evidence → verify
        │     后端（不是第二脊柱）：
        │       runtime workers | AGE-v2 Cell | aetherforge infer | omlxc
        │     投影器（不是第二调度器）：
        │       resident sediment/decision/monitor/heartbeat
        ▼ Deliverable
   ④ 结果面  薄层   [EXTEND]  AdjudicationRecorded + /outcomes
        │                         + attest-review + weekly-review
        └── 回流 ②  （没有裁决，认知面不许自称在学习）
```

三个新面继续是薄层，禁止新项目。脊柱已经存在，问题是它旁边长出了平行脊柱。

### 3.2 编排收敛：1 dispatcher + N backends（禁止 N+1）

现状（至少六套「能调度别人」的东西同时活着）：

| 系统 | 实际模型 | 今天的错位 | 目标角色 |
|---|---|---|---|
| OMO Workflow Mesh | 事件+租约+证据 | 应是唯一控制面，但常被绕过 | **Dispatcher（唯一）** |
| ecos/workflow + M1 | 协议级 YAML 步骤 | 与 Mesh 双入口 | DSL / 入院校验，调用 Mesh |
| metaos | 进程内 DAG / 决策门控 | 与 omo 边界已写（ADR-0423），入口仍在 | Backend：编排决策，不暴露独立人类入口 |
| AGE-v2 Agent Cell | 动态 Cell / cartridge / LSP | 按「落地操作系统」在扩 | **Backend**：受审执行单元 |
| resident 五角色 | 事件投影 + cron tick | 当自治 agent 用，管道空转 | **Projector**：消费 Mesh 事件，不派活 |
| BCOS evolution | 观察/提案/批准 | 有自我进化写回平台的冲动 | **Meter**：只度量 ④，不改 ③ |
| aetherforge swarm | 语义编排+算力 | 半承重 | **Backend**：infer / 预算 |
| SEMA / AST merge | 结晶技能 / 语义合并 | 刚升成 Phase 7 主叙事 | **Utility**：冻结，无主环证据不扩展 |

收敛成功的判据不是「代码合并」，是 **关闭独立入口**：

- 人类只进 `cockpit`（inbox / journeys / outcomes / memory）。
- Agent 只进 `bos://` 经 Agora；跨层执行只进 Mesh admission。
- 不允许 `cockpit daemon`、`resident execute`、`age cell run`、`bcos evolve --apply` 成为第二条主路径。需要它们时，都表现为 Mesh 的 step backend 或 post-event projector。

这是 2026-06 就写过的编排收敛模式。AGE-v2 没有使它过时，只是把 N 变成了 N+1。**本阶段禁止第 N+2 套。**

### 3.3 记忆：MOS 是控制面，不是又一个库

ADR-0372：MOS 统一写读编排，不替换 Vault / KOS / gbrain。T6-01 只收了**目录与治理面**。能力面仍是：

```
召回请求 → 理论上 bos://memory/mos/*
         → 实际上仍可能直打 gbrain / kairon-kos / 本地文件 / KB graph
```

日历 Y1Q3（2027-02→04）的真正剩余工作不是再搬目录，而是：

1. 主环的读和写 **默认** 只走 `bos://memory/mos/*`（skill `memory-recall` 已是契约）。
2. 旁路直打标 `degraded`，八周后旁路调用量趋近 0。
3. `decision_outcome` 成为结果面回填的唯一枢纽（Plan §3.3）。没有它，自主性阶梯无数据可爬。

gbrain 与 kairon 异构栈（bun+Postgres vs uv+多包）**不互融**。Y1 不重写业务逻辑。

### 3.4 产品形态：三年只做一个

Plan §6，不新发明界面：

| 界面 | 频率 | 对应 ② | 今天 |
|---|---|---|---|
| `/inbox` 决策收件箱 | **每日** | 感知→结果的人机缝 | 已建，未成为习惯 |
| `/journeys` 旅程时间线 | 每周 | 脊柱的人读投影 | 模板在，无活旅程 |
| `/outcomes` 结果与校准 | 每周 | 结果面 | 工具在（attest / north_star），无连续周 |
| `/memory` 记忆检索 | 按需 | 认知面 | 有基础，入口分散 |
| `/signals` 信号源健康 | 按需 | 感知面运维 | 注册表在，流量≈0 |

**一年后 `/inbox` 仍不是每日必开，应关停功能扩张而不是继续加 Cell。** 这比成熟度 9.0 更接近愿景。

不做：移动 App、聊天机器人主入口、Agent 画布、插件市场、第二套 Web 控制台。

### 3.5 项目边界：18→8 的剩余（归并是删入口，不是搬文件）

| 目标项目 | Plan 吸收 | 2026-08 事实 | 到 2027-07 的动作 |
|---|---|---|---|
| knowledge | gbrain+kairon | 目录归一，双栈仍在 | 控制面收敛到 MOS；不互融 |
| omo | omo+omo-debt+c2g | 内包已做 | 维持；metaos 不并入 |
| ecos | ecos+model-driven | **ADR-0412：M0 保留独立子仓** | 服从 ADR，不重开降库 |
| agora | agora+bus-foundation | 仍两仓 | S1 收传输入口，不强制物理合并 |
| runtime | runtime+aetherforge | 未并；Y1Q4-T6-01 曾被预检阻塞 | S3 再判定；主环不依赖合并 |
| cockpit | cockpit+cockpit-ui | 仍两面 | S1 人类只见 cockpit；UI 为表现面 |
| metaos | 自证主链位置 | 边界已写 | S0–S3 不碰；Y1 末再判定并入 omo 或留下 |
| l4-kernel | 保留 | 保留 | 不扩 |
| 退役 | family-hub / observability | paused / 空壳 | 维持暂停，不复活 |
| 实验层 | AGE-v2 / SEMA / BCOS evolve | 8/24–25 爆种 | **冻结为 backend/meter** |

---

## 4. 愿景对照（长周期验收，不用分数代替）

| Plan 要求 | 最早合法窗口 | 现在 | 长周期怎么算完成 |
|---|---|---|---|
| 过去一周真实信号 > 0 | **现在–2026-10** | ≈0 | S0 退出条件 |
| `/inbox` 开始改变习惯 | Y1Q1–Q2 | 未激活 | 2026-12 前 ≥3 天/周打开 |
| 月度有「接受了哪几条、改了什么」 | 2026-11→2027-01 | 无连续记录 | S1 退出：当月可回放修订差 |
| MOS 为唯一读写路径 ≥ 8 周 | 2027-02→04 | 门面在、旁路在 | S2：旁路趋 0 |
| 六项冗余清零 + 保护量 | 2027-05→07 | bin 翻倍，双栈检索仍在 | S3 = Y1 总门 |
| 每周 ≥ 3 条采纳、采纳率 ≥ 30% | 2027-07 总门 | 周计数未开始 | 从 S0 开始累周，总门看连续而非峰值 |
| 修订率较 Y1 基线 ↓20% | **Y2 总门 / 愿景证伪 2027-12** | 无基线 | Y1 只建基线，不放权 |
| 第二场景 assisted | Y2Q2 | 9 张卡全 shadow | Y1 只升 **1** 张；第二张是 Y2 的奖赏 |
| 跨场景学习 | Y2Q3 | sediment 模板 | 没有 decision_outcome 回流就禁止宣称 |
| 中试 / 公文 routine | Y3，且业务已冻 | blocked | 保持冻结，解冻走 reentry，不走本文 |

---

## 5. 长周期阶段（跟 Plan 日历对齐）

短版 VL-1 的「四周习惯门」保留为 **S0 的打开波次**，不是整个下一阶段。

```
现在 2026-08                    2026-11              2027-02              2027-05         2027-07
   |-------- S0 接通 -----------|------ S1 收敛 ------|------ S2 记忆 ------|-- S3 收口 --|
   |  Plan Y1Q1                 |  Plan Y1Q2          |  Plan Y1Q3          |  Plan Y1Q4   |
   |  信号>0 · inbox 启动       |  唯一脊柱 · 减法     |  MOS 唯一读写       |  Y1 总门     |
                                                                              |
                                                                              +-- 不过门 → 延长 Y1，禁止 Y2
                                                                              +-- 过门   → 2027H2 才解冻放权
```

### S0 · 接通（现在 → 2026-10）= Plan Y1Q1

**唯一验收问题（Plan 原文）：** 过去一周系统看到了多少条来自真实工作的信号？必须 > 0。

打开波次（原 VL-1 四周）嵌在 S0 里：

1. 主人确认主环（默认知识策展/周回顾；备选工程 dogfood；公文保持冻）。
2. 平台冻结名单生效（AGE-v2 / SEMA / 新评分 / 新编排不得立项）。
3. 记录表面积起点。
4. inbox 放入真实条目；主人亲手走通一次（≤15 分钟）。
5. 开始数周：每周 ≥ 3 条裁决（采纳/改后采纳/忽略）。治理自审标 `out_of_value`。

S0 退出：连续两周信号 > 0，且其中至少一周有 3 条非 `out_of_value` 裁决。退出失败则停功能交付，只修感知面（含手动投递 degraded）。

主环最小实现（全是 EXTEND）：

```
真实信号 → signal-sources / 手动投递 → cockpit inbox
        → 一条 3-node 旅程（取 → 问题清单 → 草稿或结论）
        → attest / weekly-review
        → AdjudicationRecorded → MOS decision_outcome
```

### S1 · 收敛（2026-11 → 2027-01）= Plan Y1Q2

**唯一验收问题：** 这个月我接受了系统几条建议？改了什么？必须有具体数字与修订内容。

架构动作（深，但不是新系统）：

1. **入口收敛**：人类默认只见 cockpit 四界面；bin 降为实现细节。发现层可以挂 670，导航层只能有 1。
2. **调度收敛第一刀**：Mesh 成为唯一 admission。AGE-v2 Cell、resident execute、metaos CLI 改为 backend 或关闭对外入口。允许暂时「能跑但不作为主路径」。
3. **指名减法**：零调用脚本归档；重复评分对外只留 scorecard（成熟度）+ north_star（价值）+ omo-status（运行）；family-hub / observability 维持暂停。
4. `/outcomes` 可回放当月修订差。没有修订差，S1 不算过。
5. 场景卡仍然只允许 1 张离开 shadow。

S1 退出：当月 ≥ 1 份可回放的「建议 / 人类修订 / 裁决」清单；`bin_scripts` 相对 S0 起点下降；无新平台层。

### S2 · 记忆（2027-02 → 2027-04）= Plan Y1Q3 日历（目录归并已提前消耗）

**唯一验收问题：** MOS 是否唯一读写路径？

1. 主环读写默认 `bos://memory/mos/*`，八周旁路趋 0。
2. `decision_outcome` 有真实 `human_verdict` 回流，不是模板 sediment。
3. 召回可解释：一条 inbox 产出能指出用了哪条记忆。
4. 不重开 gbrain×kairon 代码互融，不把 test_loc 当 culled 对象。

S2 退出：八周 MOS 默认路径 + 至少 20 条带 human_verdict 的 decision_outcome（这是 Y2 放权的数据种子，不是放权本身）。

### S3 · 收口（2027-05 → 2027-07）= Plan Y1Q4 / Y1 总门

**唯一验收问题：** 六项已识别冗余是否清零？保护量是否守住？每周 ≥ 3 条采纳、采纳率 ≥ 30% 是否成立？

六项冗余（Plan §2.2，指名）：知识层双头（能力面）、无消费者模块、无违规历史的 required 规则、零调用脚本、休眠项目、以及「N 套调度入口」。保护量：`test_loc` 不低于基线、ADR 总数不靠删除历史充数。

自主性阶梯 **只在 S3 且 calibration 有数据时** 允许 L0→L1。L2 受审执行是 Y2 的门，不提前。aetherforge 并入 runtime 在 S3 做一次承重判定：主链必经则并，否则维持后端。

**Y1 总门不过：** 冻结全部新增，2027H2 继续 Y1，不启动「第二场景 / 跨场景学习 / 放权」。这是 Plan 原文，不是惩罚条款。

### 解冻后的 Y2（2027H2 起，仅总门通过）

不在本阶段展开实现，只锁边界：

- 心智四模型有持久数据且被 Agent 读取（否则所谓 resident 仍是空投影）。
- 第二场景进 assisted；修订率相对 Y1 基线下降。
- 2027-12-31 愿景证伪点：连续 12 周每周 ≥ 3 条；修订率不降 = 没在学 = 定位被证伪。
- 公文/中试仍默认冻，解冻单独走 blocked reentry。

---

## 6. 控制论：两个必须闭合的环，一个必须拆掉的环

```
环 I  价值环（现在是断的）
  外部信号 → inbox → 脊柱 → 署名产出 → 裁决 → decision_outcome → 下周更好的建议
  闭合标志：修订率开始有基线（S1），并在 Y2 下降。

环 II 可持有性环（现在是反转的）
  新能力提案 → 是否消灭一个指名冗余？→ 否则拒绝 → surface 月报
  闭合标志：bin 与调度入口数下降，而不是 scorecard 上升。

环 III 治理自指环（必须拆）
  治理状态 → 治理规则 → 治理分数 → 更多治理资产 → 当作价值
  这就是 §0.1 的「加强治理加大分子」。成熟度冲刺、BCOS 自我进化、resident 对 workflow 失败再提案
  若无环 I 的裁决，一律视为环 III。
```

Ashby：治理规则的品种必须对得上真实干扰的品种。真实干扰是「主人没打开 inbox、信号为 0、产出不愿署名」。再增加 GaC 规则不增加这种品种。Y1 的控制动作是 **减少通道**（入口、调度器、评分器），让剩下的通道被环 I 充满。

---

## 7. 波次与门禁（S0 内部仍用短波次，避免再失焦）

### S0-W0（7 天）停损

```
☐ 接受「现在是日历 Y1Q1，不是后 Y1Q3」
☐ 主环选定（默认知识策展/周回顾）
☐ 冻结 AGE-v2 Phase 8 / SEMA 扩展 / 新评分 / 新编排
☐ surface 起点入库
☐ inbox 有 1 条真实条目
```

### S0-W1（到 2026-09 中）走通

```
☐ 主人亲手走通主环
☐ 至少 1 周 ≥ 3 条非 out_of_value 裁决
☐ 感知面允许手动投递，状态标 degraded 也算 > 0（Plan R2）
☐ 本波次净增 bin = 0
```

### S0-W2（到 2026-10 末）Q1 门

```
☐ 连续两周真实信号 > 0
☐ inbox 打开开始留下痕迹（达不到「每日」也必须 ≠ 0）
☐ 1 张场景卡仍可停在 shadow，但 sample ≥ 3
☐ 进入 S1 或宣布 Q1 失败、停功能只做感知
```

S1 以后按月复盘，不再按周开新平台。每月只回答 Plan §10 的四问：收件箱、哪条建议省了时间、表面积涨跌、场景升/降/关。

---

## 8. 红队

| # | 攻击 | 回应 |
|---|---|---|
| 1 | 这是第二套三年规划 | 愿景/总门/证伪只引用 Plan；本文只做日历对齐与编排收敛 |
| 2 | 十一太长，不如再冲 4 周成熟度 | 4 周已经冲过 T10，现场仍 7.7，两端仍空。短周期对错形状无效 |
| 3 | Ledger 全 done，重开 Y1Q1 是否侮辱既有交付 | 既有交付是中段资产，计入 2.1。重开的是**未被事实满足的验收问题**，不是重做 Cell |
| 4 | AGE-v2 冻结会烂 | 冻结为 Mesh backend。继续当 OS 扩，才是腐烂 |
| 5 | 1 dispatcher 会不会选错（Mesh vs ecos/workflow） | 控制面事实源已是 OMO 事件（ARCHITECTURE §2）。ecos/workflow 做 DSL/入院，不争 dispatcher |
| 6 | 知识层「未完成」会诱发热战互融 | 明确不互融；S2 只收控制面路径 |
| 7 | 公文解冻后日历全乱 | 冻结合法；解冻走 reentry。主环不绑国转中心 |
| 8 | 没有主人习惯，长周期仍会变成 agent 刷周报 | S0 退出条件是真实信号与非 out_of_value 裁决。刷治理周报 = 环 III，算失败 |
| 9 | 18→8 会再引爆搬仓 | 本阶段只关入口、标暂停、MOS 默认路径；物理合并只在 S3 对 aetherforge 做一次判定 |
| 10 | 三套坐标系仍太复杂 | 运行时只认 ②。① 给仓库，③ 给观测。禁止用 ③ 立项 |

---

## 9. 文档关系

| 文档 | 关系 |
|---|---|
| `STRATEGY-3YEAR-PLAN-2026H2-2029.md` | 愿景与 Y1–Y3 总门 SSOT |
| `3y-bet-ledger.yaml` | 执行拆分 SSOT。与日历冲突时，**以 Plan 日历与本文验收问题为准** 补 bet，而不是把 done 当事实 |
| `ARCHITECTURE.md` | 分层与路由契约，不改 |
| `project-strategy-v1.md` | 九维诊断仍有效；其「12 个月放权 / 3 张卡升档」推迟到 Y1 总门之后 |
| `digital-twin-blueprint-v1.md` | 数字分身是 Y2+ 形态；Cell 在 Y1 只作 backend |
| 前短版 VL-1 | **降为 S0 打开波次**，不再单独作为阶段契约 |
| ADR-0412 / 0413 / 0423 / 0425 / 0426 | 边界与实验层入库；0425/0426 冻结扩展 |

---

## 10. 需要主人拍板的四件事

1. **是否接受日历重同步？** 承认现在是 Plan 的 Y1Q1，不是「Y1Q3 之后开始 Y2」。不接受，则本文作废，系统继续按台账空转进入平台扩张。
2. **是否接受 1 dispatcher + N backends？** Mesh 唯一入院；AGE-v2 / resident / BCOS evolve / SEMA 冻结为后端、投影或仪表。拒绝 = 选择继续 N+1。
3. **主环选哪张卡？** 默认知识策展/周回顾；备选工程 dogfood。公文保持冻。
4. **S0（到 2026-10）是否愿意每周打开 inbox？** 长周期的最小人因。不愿意，就不要让 agent 用 PR 把 Y1Q1 再标一次 done。

拍板前不把本文写入台账 done，不派生 12 条新 bet。若开 bet，只开「信号>0 / inbox 习惯 / 调度入口收敛 / 零调用归档 / MOS 默认路径」这类能对上日历验收问题的项，总数仍宜 ≤ 5。
