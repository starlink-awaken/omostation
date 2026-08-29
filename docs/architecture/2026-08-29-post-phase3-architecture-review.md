---
status: active
lifecycle: spec
owner: engineering-agent
last-reviewed: 2026-08-29
title: Phase 1-3 架构深度审议 — 链路完整度、体系化程度与剩余缺口 (2026-08-29)
type: doc
---

# Phase 1-3 架构深度审议 — 链路完整度、体系化程度与剩余缺口 (2026-08-29)

> 审议立场: 基于 2026-08-29 实测数据, 对 Phase 1-3 (22 PR) 交付后的架构状态做压力测试式评估。数据含自打脸部分。
> 前序: [`2026-08-28-five-dimension-review.md`](2026-08-28-five-dimension-review.md) · [`2026-08-28-value-flow-deep-analysis.md`](2026-08-28-value-flow-deep-analysis.md)

---

## 〇、Phase 1-3 交付清单与实际成色

### 交付清单

| Phase | PR/Commit | 工具 | 声称功能 |
|-------|-----------|------|----------|
| **Phase 1** | corrosion-pipeline-connector | `bin/gac/corrosion-pipeline-connector.py` | G1: meta-doctor→修复提案; G2: meta-doctor→收件箱推送 |
| **Phase 1** | decision inbox (cockpit decide) | `bin/ssot/decision-agent.py` + `.omo/state/decision-inbox.json` | 事件驱动决策提案 |
| **Phase 1** | scene card upgrade | `docs/scene-cards/*.yaml` (v2 schema) | 场景卡双轨准入 |
| **Phase 2** | scene→journey connector | `bin/gac/scene-journey-connector.py` | assisted 场景卡自动创建 Journey |
| **Phase 2** | value→evolution connector | `bin/gac/value-evolution-connector.py` | 价值记录→进化引擎输入→自动执行高置信提案 |
| **Phase 2** | calendar signal routing | `bin/bc-os/signal_router.py` (calendar 扩展) | 日历信号源接入 |
| **Phase 3** | kernel bridge (MetaOS↔OMO) | `bin/gac/kernel-bridge.py` | MetaOS 核心功能委托给 OMO |
| **Phase 3** | model-ecos bridge | `bin/gac/model-ecos-bridge.py` | Model-Driven 生命周期↔ECOS MOF 衔接 |
| **Phase 3** | l4-memory bridge | `bin/gac/l4-memory-bridge.py` | L4 域管理↔OMO/MOS 记忆层衔接 |
| **Phase 3** | probe heartbeat matrix | `bin/gac/probe-heartbeat-monitor.py` + `.omo/_truth/registry/probe-heartbeat-matrix.yaml` | 8 探测器 SLA 监控 |

### 实际成色评估

| 工具 | 成色 | 实测 |
|------|------|------|
| corrosion-pipeline-connector | 🟢 **实跑** | 已写入 5 条真实异常到 decision-inbox (含 P1 引用失效×2) |
| decision-agent | 🟢 **实跑** | 订阅 WorkflowFailed/StepFailed/StepTimeout, 写入 evolution-proposals/ |
| scene-journey-connector | 🟡 **半实跑** | 仅记录 mapping 到 `scene-journey-map.json`, 不实际执行 journey |
| value-evolution-connector | 🟡 **半实跑** | 记录价值到 `value-executions.json`, 但 `auto-evolve` 仅计数不真正执行 |
| kernel bridge | 🔴 **脚手架** | 仅维护 `kernel-json` 状态文件, 无实际委托逻辑 |
| model-ecos bridge | 🔴 **脚手架** | 仅维护 `model-ecos-bridge.json`, 无实际 Stage/MOF 同步 |
| l4-memory bridge | 🔴 **脚手架** | 仅维护 `l4-memory-bridge.json`, 无实际域/内容同步 |
| probe-heartbeat-monitor | 🟢 **实跑** | 8 探测器 SLA 检查, 输出真实失败 (system_health.yaml 49.7h/SLA 48h) |

**结论**: 10 个工具中, **3 个实跑** (corrosion-pipeline, decision-agent, probe-heartbeat), **2 个半实跑** (scene-journey, value-evolution), **3 个纯脚手架** (kernel/model-ecos/l4-memory bridge)。Phase 3 的"连接桥"名义上是桥, 实际上是**桥墩的钢筋骨架**——接口定义清晰, 但桥面未通车。

> 来源: [`bin/gac/kernel-bridge.py:25-30`](bin/gac/kernel-bridge.py) (DELEGATABLE_FUNCTIONS 仅声明, 无实现) · [`bin/gac/model-ecos-bridge.py:25-31`](bin/gac/model-ecos-bridge.py) (STAGE_MOF_MAP 仅声明) · [`bin/gac/l4-memory-bridge.py:25-29`](bin/gac/l4-memory-bridge.py) (DELEGATABLE_FUNCTIONS 仅声明)

---

## 一、链路完整度评估

### 1.1 意图→策略→目标→执行→复盘 全链

```
意图(Intent) ──→ 策略(Strategy) ──→ 目标(Goal) ──→ 执行(Execute) ──→ 复盘(Review)
     │                 │                │               │                │
   cockpit          c2g-spec-ingress   BET ledger     agent-workflow    sediment/retro
   pitch            strategy-agent     3y-bet-ledger  swarm claims     BCOS evolve
   NL prompt        C2G ingress        goals/current  resident execute  north_star
```

| 环节 | 连接状态 | 自动化程度 | 断点 |
|------|----------|-----------|------|
| **意图→策略** | 🟡 半连通 | 手动 + c2g-spec-ingress workflow | C2G 实际 materialization 需人工触发, 无自动 pitch→task 管道 |
| **策略→目标** | 🟡 半连通 | BET 台账静态存在 | BET claim-check 存在但无自动 strategy→BET 绑定 |
| **目标→执行** | 🟡 半连通 | agent-workflow start/claim/verify | Swarm claims 冻结于 08-18, messages=0, 六蜂群不干活 |
| **执行→复盘** | 🟢 连通 | sediment 自动沉淀 + retro 五问 | retro 引用率仅 6.7% (1/15), 沉淀→再利用断链 |
| **复盘→进化** | 🔴 断开 | BCOS evolve 四阶段建成 | proposal_adoption_rate=0.0, 964 提案 0 采纳 |

### 1.2 各环节详细评估

#### 意图→策略 (Intent→Strategy)

- **已有**: `c2g-spec-ingress` workflow ([`.omo/_truth/registry/agent-workflows.yaml:38-49`](.omo/_truth/registry/agent-workflows.yaml)), `strategy-agent` profile, C2G 项目 ([`projects/c2g/`](projects/c2g/))
- **断点**: 
  - C2G 实际运行依赖人工触发, 无自动化的 pitch→task materialization 管道
  - `bin/cockpit/decide` 收件箱存在但仅 5 条测试/防腐数据, 无真实策略输入
  - 意图解构器 (`ecos-constraint intent compile`, ADR-0195) 存在但未与 C2G ingress 接线
- **评估**: 机制存在, 但未形成闭环自动化

#### 策略→目标 (Strategy→Goal)

- **已有**: BET 台账 ([`docs/plans/3y-bet-ledger.yaml`](docs/plans/3y-bet-ledger.yaml), 145 条), `goals/current.yaml`, `bet-ledger.py status/claim-check`
- **断点**:
  - BET 台账主要是静态规划文档, 无自动化的 strategy→BET 绑定
  - `bet-ledger.py claim-check` 仅做一致性检查, 不做自动派单
  - 目标层级 (T1-T10 十条轨道) 与执行层 (agent-workflow) 之间缺少自动映射
- **评估**: 规划完备, 但规划→执行的桥梁是人工

#### 目标→执行 (Goal→Execute)

- **已有**: `agent-workflow.py` (ADR-0203), swarm coordination (ADR-0220), resident execute role, claims 表
- **断点**:
  - Swarm claims 冻结于 2026-08-18, 93 个过期 active claims 未清理
  - A2A messages = 0, 六蜂群从未互相通信
  - 真实产出仅 3 个 WorkflowRequested
  - `resident execute` 有批准门 (HITL), 但无自动任务来源
- **评估**: 心脏在跳 (6/6 heartbeat), 手脚不动

#### 执行→复盘 (Execute→Review)

- **已有**: sediment 角色 ([`docs/architecture/resident-agent-system-v1.md:66-73`](docs/architecture/resident-agent-system-v1.md)), retro 五问, `.omo/_knowledge/sediment/`, `.omo/_knowledge/retros/resident/`
- **断点**:
  - retro 引用率 6.7% (1/15), 沉淀的知识未被后续 session 消费
  - sediment→下次 prompt 注入机制 (ADR-0128 Phase 2) 存在但未与 retro 引用联动
- **评估**: 唯一基本连通的环节, 但消费端几乎闲置

#### 复盘→进化 (Review→Evolution)

- **已有**: BCOS evolve 四阶段 ([`docs/architecture/bcos-system-v1.md:38-51`](docs/architecture/bcos-system-v1.md)), north_star_meter_v2/v3, evolution-proposals/
- **断点**:
  - `proposal_adoption_rate: 0.0`, 964 提案 0 采纳
  - evolve 引擎无 cron 触发, 仅手动 `--apply`
  - value-evolution-connector 的 `auto-evolve` 仅计数不执行
- **评估**: 进化引擎转不动, 是体系最大的"造好了血管没有血液"案例

### 1.3 链路完整度总结

```
链路环节       连通度   自动化    关键断点
─────────────────────────────────────────────────────
意图→策略       40%     手动      C2G 无自动 materialization
策略→目标       30%     手动      BET 台账静态, 无自动绑定
目标→执行       35%     半自动    Swarm 冻结, 无真实任务流
执行→复盘       60%     半自动    retro 引用率 6.7%
复盘→进化       20%     手动      0 采纳, 无自动触发
─────────────────────────────────────────────────────
全链综合        37%     手动为主  无闭环自动化
```

> 来源: [`docs/architecture/2026-08-28-value-flow-deep-analysis.md:14-82`](docs/architecture/2026-08-28-value-flow-deep-analysis.md) (五条断链诊断) · [`docs/architecture/omostation-full-ecosystem-map-2026-08-28.md:197-253`](docs/architecture/omostation-full-ecosystem-map-2026-08-28.md) (launchd 全景)

---

## 二、体系化程度评估

### 2.1 治理机制闭环

#### 已形成的闭环

| 闭环 | 机制 | 状态 |
|------|------|------|
| **检测→立案** | meta-doctor → corrosion-pipeline → decision-inbox | 🟢 实跑 (5 条真实异常) |
| **立案→修复** | decision-inbox → remediation-engine | 🟡 提案存在, 修复需人工 |
| **修复→验证** | agent-workflow verify → gac-local-gate | 🟢 机制存在 |
| **验证→沉淀** | sediment → knowledge/sediment/ | 🟢 自动沉淀 |
| **规则生命周期** | ADR-0431 L4 约束层 + rules-lifecycle.py | 🟡 框架存在, 未全覆盖 |
| **探测器心跳** | probe-heartbeat-matrix → inbox/debt/weekly | 🟢 8 探测器 SLA 监控 |

#### 治理机制密度 vs 效能

- **密度**: 57 GaC checks ([`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)), 18 个 registry, 402 个工具脚本
- **效能**: 
  - 预算纪律失效: rule_baseline 139→180, script_baseline 498→504 (一周 4 次上调)
  - 防腐工具自身 `ok=False` (anti-corrosion-check.py)
  - 治理对象是过程不是价值: 57 个 check 里没有一个测"用户本周被省了多少时间"

> 来源: [`docs/architecture/2026-08-28-five-dimension-review.md:59-68`](docs/architecture/2026-08-28-five-dimension-review.md) (治理维度审议)

### 2.2 子系统职责边界

#### SFOP 槽位清晰度 ([`docs/architecture/os-operating-pattern-v1.md:27-39`](docs/architecture/os-operating-pattern-v1.md))

| 槽 | 名字 | 现任 | 边界清晰度 |
|---|---|---|---|
| K | 宪法 | Plan/L4/ecos/GaC | 🟢 清晰 |
| H | 人类面 | cockpit/cockpit-ui | 🟢 清晰 (ADR-0428 单入口收敛) |
| P | 感知面 | signal-sources/iris | 🟡 信号源单一 (仅邮件) |
| C | 认知面 | MOS; gbrain/kairon | 🟢 清晰 |
| **S** | 脊柱 | **COMP-WS-omo/Mesh** | 🟢 清晰 (唯一 dispatcher) |
| B | 后端 | runtime/AGE-v2/aetherforge | 🟡 AGE-v2 dormant, 边界模糊 |
| J | 投影 | resident | 🟡 resident vs BCOS 功能重叠 |
| O | 结果面 | attest/north_star | 🟢 清晰 |
| F | 织层 | agora/bus-foundation | 🟢 清晰 |

#### 职责重叠与真空

| 类型 | 位置 | 描述 |
|------|------|------|
| **重叠** | resident ↔ BCOS | 两者都做事件处理/信号路由/进化。resident 是事件投影, BCOS 是业务闭环, 但执行层交叉 |
| **重叠** | kernel-bridge ↔ model-ecos-bridge | 两者都是"脚手架桥", 委托逻辑完全相同 (仅状态文件不同) |
| **真空** | 真实任务生产 | 无系统负责"从用户生活中产生真实任务" |
| **真空** | 价值消费 | 无系统负责"把沉淀的知识转化为行动" |
| **真空** | 信号源扩展 | 日历/IM/OA 信号源未接入, 仅邮件且 0.14% 任务率 |

> 来源: [`docs/architecture/os-operating-pattern-v1.md:27-39`](docs/architecture/os-operating-pattern-v1.md) · [`docs/architecture/2026-08-28-five-dimension-review.md:70-78`](docs/architecture/2026-08-28-five-dimension-review.md) (防腐维度审议)

### 2.3 体系化程度总结

```
维度           评分   说明
─────────────────────────────────────────────
治理机制密度    9/10   57 checks, 18 registries, 全覆盖
治理机制效能    5/10   预算纪律失效, 防腐自身腐蚀
子系统边界      7/10   SFOP 清晰, 但 resident/BCOS 重叠
职责重叠        6/10   3 处重叠 (resident/BCOS, bridges)
职责真空        4/10   3 处真空 (任务生产, 价值消费, 信号源)
文档契约        8/10   doc-ssot-contract + 18 registry 对齐
运行时契约      6/10   BOS URI 注册但部分服务未实跑
─────────────────────────────────────────────
综合体系化      6.5/10  骨架完备, 血肉不足
```

---

## 三、剩余缺口识别

### 3.1 未连接的链路

| 缺口 | 严重度 | 描述 | 已有脚手架 |
|------|--------|------|-----------|
| **Bridge 通车** | 🔴 P1 | kernel/model-ecos/l4-memory 三桥仅骨架, 无实际委托/同步逻辑 | `bin/gac/*-bridge.py` |
| **Scene 激活** | 🔴 P1 | 20 张场景卡仅 2-3 张 active, 其余 draft/shadow | `docs/scene-cards/*.yaml` |
| **Swarm 复活** | 🔴 P1 | 六蜂群 claims 冻结, messages=0, 无真实产出 | `bin/gac/swarm-git` |
| **价值闭环** | 🟡 P2 | North Star B 轴 20/100, 决策吞吐极低 | `bin/bc-os/north_star_meter_v3.py` |
| **信号源扩展** | 🟡 P2 | 仅邮件, 0.14% 任务率, 日历/IM/OA 未接 | `bin/bc-os/signal_router.py` |
| **AGE-v2 点火** | 🟡 P2 | 10 模块 dormant, agent-cell/ 目录空 | `projects/omo/src/omo/resident/cell*.py` |
| **Retro 引用** | 🟢 P3 | 引用率 6.7%, 沉淀知识未消费 | `.omo/_knowledge/retros/` |

### 3.2 单点故障

| 单点 | 影响 | 缓解 |
|------|------|------|
| **唯一 dispatcher (Mesh/S 槽)** | Mesh 故障 → 全体系停摆 | 机制存在, 但无热备 |
| **单一信号源 (邮件)** | 邮件服务异常 → 感知层全盲 | 无多源冗余 |
| **人工审阅门 (HITL)** | 主人不在 → 所有 L2+ 任务阻塞 | 无异步批处理路径 |
| **meta-doctor** | 检测器自身 `ok=False` → 防腐失明 | probe-heartbeat 已部分覆盖 |
| **BET 台账人工维护** | 台账过时 → 规划与执行脱节 | 无自动同步 |
| **omlxc daemon** | 算力路由故障 → LLM 分类/推理全断 | 多后端路由 (本地+远程) |

### 3.3 长期治理与运维风险

| 风险 | 描述 | 当前信号 |
|------|------|----------|
| **表面积过载** | 26 launchd + 402 脚本 + 57 checks, 每新增一个都在扩表面 | AGENTS.md 自己的话: "表面积超限" |
| **减法跑不赢加法** | 规则 144→74 (砍), 但脚本 498→504 (涨) | ADR-0424 D3 动态守恒未执行 |
| **dormant 积压** | Cell×10 + planner/verifier + Goal-4X + ... | "以后会用"的代码是最贵的负债 |
| **声明 vs 事实** | docstring 声称已做而未做 (历史病) | 北极星 0 采纳率是当前形态 |
| **治理内循环** | 57 个 check 测的是过程合规, 不是用户价值 | 与"数字大脑为生活降本"愿景偏移 |
| **断指事故** | 7 起/48h, 每起需人工修复 | 高频人工干预, 运维自动化被高估 |

> 来源: [`docs/architecture/2026-08-28-five-dimension-review.md:36-47`](docs/architecture/2026-08-28-five-dimension-review.md) (运营维度审议) · [`docs/architecture/2026-08-28-value-flow-deep-analysis.md:84-97`](docs/architecture/2026-08-28-value-flow-deep-analysis.md) (根因归纳)

---

## 四、Phase 1-3 交付与愿景对齐

### 4.1 愿景回顾

用户愿景 (PREFERENCE/DA 记忆): **数字大脑 P0工作→P1健康→P2家庭→P3个人→P4教育**, 本质是"agent 为人的生活降本增效", 而非"agent 建设 agent 体系"。

### 4.2 Phase 1-3 与愿景对齐

| Phase | 交付 | 愿景对齐 | 评估 |
|-------|------|----------|------|
| Phase 1 | 防腐 G1/G2 接线 | ⚠️ 间接 | 管的是"体系自我防腐", 不是"用户生活任务" |
| Phase 1 | 决策收件箱 | ⚠️ 间接 | 收件箱是工具, 但无真实决策流入 |
| Phase 2 | 场景→Journey | ⚠️ 间接 | 场景卡未激活, 接线器无场景可接 |
| Phase 2 | 价值→进化 | ⚠️ 间接 | 进化引擎 0 采纳, 接线器无价值可传 |
| Phase 3 | 三桥连接 | ⚠️ 间接 | 桥是骨架, 通车后仍需真实负载 |
| Phase 3 | 探测器心跳 | ✅ 直接 | 运维自动化直接服务系统稳定 |

**残酷问题**: Phase 1-3 的全部交付都是**体系内循环**的完善, 与"生活降本"愿景存在偏移。整个体系当前最大的断链不是"桥未通车", 是**"用户生活的真实任务没有进来"** (任务邮件 0.14%, OA/日历未接)。

> 来源: [`docs/architecture/2026-08-28-five-dimension-review.md:94-111`](docs/architecture/2026-08-28-five-dimension-review.md) (愿景对齐审议)

---

## 五、修正后的路线建议

### 5.1 Phase 1-3 的合理定位

Phase 1-3 不是"完成时", 而是**"基础设施预备时"**:
- 桥墩已浇筑, 但桥面未通车
- 收件箱已建, 但无信可收
- 探测器已装, 但仅监控不驱动

**下一步不应继续"加连接"**, 而应**"引真实负载"**。

### 5.2 三段式修正路线

```
第 0 段 (减法清淤, 1 周) — 支付防腐债
  ├─ dormant 大扫除: Cell×10/planner/verifier/Goal-4X 逐个判定
  │   "6 个月内有激活计划?" 无 → 归档
  ├─ 三桥脚手架合并: kernel/model-ecos/l4-memory → 统一 bridge-runtime
  │   (三个几乎相同的委托框架是表面积负债)
  ├─ 提案池清淤: 964 new 做质量分层, 机器流水账批量归档
  └─ 过期 claims 清 93 个僵尸
  判据: script_baseline 从 504 下降; 三桥合一; claims 恢复活跃

第 1 段 (引真实负载, 2-3 周) — 让真实任务流进来
  ├─ 信号源: 日历 (系统日历可本地读, 无单位网络依赖) 先于 OA
  ├─ auto-journey 首任务实弹 (等/造一封真实任务邮件)
  ├─ 场景卡激活: admin-inbox 已有 active, 扩展至 unified-inbox
  └─ 北极星补真指标: 工作交付从"待接入"→接 mail-journey 产出
  判据: 真实任务信号 ≥1/周; journeys ≥1; X3 工作交付有真数

第 2 段 (桥通车, 3 周+) — 用真实负载驱动内循环
  ├─ 三桥合一后, 用真实场景驱动委托逻辑实现
  ├─ 提案 triage 只对 <100 个真提案跑 BCOS 四阶段
  ├─ 首批 adopted 提案派单 → 六蜂群 Goal 模式最小启动 (1 轨道)
  └─ Cell 是否点火: 看第 1 段任务量 — 有稳定 DAG 需求才点
  判据: adoption 0→5 (真提案口径); 桥有真实通车流量
```

### 5.3 与原 Phase 1-3 路线的差异

| 原路线 | 修正后 | 理由 |
|--------|--------|------|
| 继续加连接器 | 先减法清淤 | 3 个桥墩已够, 通车比加桥墩重要 |
| 信号源排 P2/S4 | 升到第 1 段 | 愿景对齐: 没真输入一切内循环空转 |
| 三桥分建 | 三桥合一 | 三个几乎相同的框架是表面积负债 |
| 四轨 Goal 并行 | 1 轨道试点 | 6/6 心跳但 0 messages——先证明能干活再扩 |

---

## 六、给用户的三个决策点

1. **dormant 判定权**: Cell×10/planner/verifier/Goal-4X 按"6 个月激活计划"判定归档——你之前说"一定要用起来", 是否接受"无近期计划=先归档可快速恢复"的读法?
2. **三桥合并**: kernel-bridge / model-ecos-bridge / l4-memory-bridge 合并为统一 `bridge-runtime`, 是否接受? (减少表面积, 保留全部声明式接口)
3. **信号源优先级**: 日历 (本地可读, 快) vs OA (单位网络, 价值高但依赖环境) 先接哪个?

---

## 附录 A: 关键指标快照 (2026-08-29)

| 指标 | 值 | 来源 |
|------|-----|------|
| launchd 常驻服务 | 26 | [`docs/architecture/omostation-full-ecosystem-map-2026-08-28.md:197-240`](docs/architecture/omostation-full-ecosystem-map-2026-08-28.md) |
| GaC checks | 57 | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) |
| 工具脚本 | 402 | `bin/gac + bin/ssot + bin/bc-os` |
| 场景卡 (active/draft) | 3/17 | `docs/scene-cards/*.yaml` |
| Journey specs (active/draft) | 1/12 | `docs/journey-specs/*.yaml` |
| 事件流 | 3783 条 (96% 心跳) | [`docs/architecture/2026-08-28-value-flow-deep-analysis.md:46`](docs/architecture/2026-08-28-value-flow-deep-analysis.md) |
| 北极星 adoption_rate | 0.0 | 同上 |
| Swarm claims 最后更新 | 2026-08-18 | 同上 |
| A2A messages | 0 | 同上 |
| retro 引用率 | 6.7% (1/15) | 同上 |
| 任务邮件率 | 0.14% (1/700) | 同上 |
| 探测器数量 | 8 | [`.omo/_truth/registry/probe-heartbeat-matrix.yaml:12-55`](.omo/_truth/registry/probe-heartbeat-matrix.yaml) |
| Phase 1-3 工具实跑率 | 3/8 | 本文 §〇 |

## 附录 B: 架构文档引用索引

| 文档 | 路径 | 角色 |
|------|------|------|
| 稳定架构契约 | [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) | 层模型、入口、BOS、治理面 |
| 运行模式 | [`docs/architecture/os-operating-pattern-v1.md`](os-operating-pattern-v1.md) | SFOP 槽位语法 |
| 道法术器 | [`docs/architecture/dao-fa-shu-qi.md`](dao-fa-shu-qi.md) | MOF 嵌套理论 |
| 常驻 Agent | [`docs/architecture/resident-agent-system-v1.md`](resident-agent-system-v1.md) | 五角色事件驱动 |
| BCOS | [`docs/architecture/bcos-system-v1.md`](bcos-system-v1.md) | 业务闭环系统 |
| Memory OS | [`docs/architecture/memory-os.md`](memory-os.md) | 记忆控制面 |
| 北极星 v3 | [`docs/architecture/north-star-v3-design.md`](north-star-v3-design.md) | 价值证明设计 |
| 全生态图解 | [`docs/architecture/omostation-full-ecosystem-map-2026-08-28.md`](omostation-full-ecosystem-map-2026-08-28.md) | 九层全景 |
| 五维审议 | [`docs/architecture/2026-08-28-five-dimension-review.md`](2026-08-28-five-dimension-review.md) | 运营/运维/治理/防腐/进化 |
| 价值流分析 | [`docs/architecture/2026-08-28-value-flow-deep-analysis.md`](2026-08-28-value-flow-deep-analysis.md) | 五条断链诊断 |
| Agent 工作流注册 | [`.omo/_truth/registry/agent-workflows.yaml`](../../../.omo/_truth/registry/agent-workflows.yaml) | 可执行 workflow 注册表 |
| 防腐五层框架 | [`.omo/_knowledge/decisions/0431-anti-corrosion-five-layer-framework.md`](../../../.omo/_knowledge/decisions/0431-anti-corrosion-five-layer-framework.md) | ADR-0431 |
| 防腐流水线 | [`.omo/_knowledge/decisions/0424-anti-corruption-pipeline-and-value-pacemaker.md`](../../../.omo/_knowledge/decisions/0424-anti-corruption-pipeline-and-value-pacemaker.md) | ADR-0424 |
