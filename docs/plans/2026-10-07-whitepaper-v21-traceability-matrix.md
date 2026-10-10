---
schema: md/v1
status: draft-for-review
lifecycle: planning
owner: dashboard-convergence
last-reviewed: 2026-10-08
title: "织星 Dashboard 白皮书 v2.1 逐项追踪与产品验收矩阵"
---

# 织星 Dashboard 白皮书 v2.1 逐项追踪与产品验收矩阵

本文是统一 Dashboard 执行计划的需求追踪附件，目标是把白皮书中可验收的产品、架构、制度、体验和运营要求逐项连接到能力、责任、证据和退出门。它是候选规划，不是 BET、G0-BIND、发布许可或运行事实。

## 0. 权威输入与判定规则

| 输入 | 权威身份 | 用法 |
|---|---|---|
| `2026-09-26-织星主权智能操作系统白皮书-v2.1.md` | SHA-256 `969fd87cda1fd49d0f81b4515710728167c3c335845657f94a9f99d481f2ea3f` | 主权、目的、价值、架构、对象、权力、战略、指标与运行节律的规范输入 |
| `2026-09-26-织星主权智能操作系统全景架构蓝图-v2.1.md` | SHA-256 `3b9ed61194ae7cdb95756e455a46ca05ea3e428095d1d9c5cb69f1a7ee8946db` | 20 个规范对象的字段合同与关系模型唯一来源；本矩阵不复制字段定义 |
| `2026-09-26-织星主权智能操作系统路线图与里程碑-v2.1.md` | SHA-256 `3488312fca7dd25f30010fe0e52a6a3c7c8e7f327a1ce65d6c4440f771fe30cd` | 约束 W0–W6 阶段顺序、退出条件和 70/20/10 投入比例 |
| `2026-09-26-织星主权智能操作系统文档导航与权威矩阵-v2.1.md` | SHA-256 `0ab6d71b49ff0f4a1509ba8a6a89f9aedb33b84c67b7a537e0c945b429387ddf` | 解决接受包内部的规范文档层级、关系与适用边界 |
| `2026-09-26-织星主权智能操作系统v2.1-现状审计与升级报告.md` | SHA-256 `a7092c5f49502e252b7c04b29c83846398d2a7519346435c9569ac1eef09292d` | 作为输入包内历史基线；不能替代当前 runtime 和业务验收 |
| Principal 接受回执 | SHA-256 `6b01e8a2dadb8aad8e30d8bab99a4cb21802a357d3a7fd4b5c2f48ac3db2c274`，精确接受信封 SHA-256 `959b63d1cc72c4dfe2bb4116ea72cc531e0af53c6021354b6c3326c6ececf82f` | 证明该 v2.1 信封被接受；明确不授予 Workspace binding、Ledger 写入、Claims activation、部署、服务控制或外部副作用权限 |
| `2026-09-26-织星主权智能操作系统v2.1-文档包-manifest.yaml` | SHA-256 `cb9b5193b1171c375a6d4026af1c52bb384f909fdabed5e6815925853b4f31e0` | 固定输入包成员和包级摘要 |
| `docs/VISION-ROADMAP.md`、统一 Dashboard 执行基线 | 现有 Workspace 产品与实现映射 | 映射 DCP 工作包、能力 Owner 和候选验证 |

接受回执仅绑定指定信封，不构成 Workspace binding、正式 BET/Run 准入、服务发布或运行授权。状态只表达本轮可复核证据：`有候选` 表示源码/测试存在但未纳入受信运行；`部分` 表示有方案或局部实现但缺一个或多个验收面；`未证` 表示没有满足要求的直接证据；`不适用` 必须给出理由和产品/架构复核人。每个当前状态须带下方证据索引；没有能直接支持该状态的证据时，降为 `未证`。PR、测试、健康端点或投影绿灯都不能单独证明真实业务价值。

### 0.1 当前状态证据索引

| 编号 | 直接证据 | 支持范围 |
|---|---|---|
| E1 | `.omo/evidence/2026-10-07-live-dashboard-availability-r2.md` | 02:07Z 页面/API/投影真实运行态、`STALE/UNKNOWN`、读者 503、投影 lease 与 data observed 时间差、LaunchAgent 间隔 |
| E2 | `.omo/evidence/2026-10-07-dashboard-action-auth-inventory-r2.md` | 运行时 API/写操作数量、中央可选认证和候选源码与运行态差异；只支撑静态/运行路由范围结论 |
| E3 | `.omo/evidence/2026-10-07-route-component-capability-audit.md`、`.omo/evidence/2026-10-07-route-convergence-disposition-v2.md` | 页面组件能力、旧路由 disposition 与仍缺少的生产 parity/退役验收 |
| E4 | `.omo/evidence/2026-10-07-dcp20-workcase-auth/verification.md`、`.omo/evidence/2026-10-07-dcp20c-outbox-command-protocol.md`、`.omo/evidence/2026-10-07-dcp20c-agent-request-assertion/verification-r2.md` | Work Case/Agent 授权候选验证范围、Agent 默认拒绝及 durable outbox 未完成边界 |
| E5 | `.omo/evidence/2026-10-07-compact-observation-hardening-validation.md`、`.omo/evidence/compact-observation-code-review-r2.md` | bounded observer 候选及独立复核；source-only plist 和 live recovery 未完成 |
| E6 | `docs/plans/2026-10-04-dashboard-platform-convergence-execution-plan.md` §2、§7 及 2026-10-07 运行复核 | 路由/API、G0 当前证据边界和多次运行复测；历史时间点必须与 E1/E9 最新快照区分 |
| E7 | 接受包 `2026-09-26-织星主权智能操作系统v2.1-现状审计与升级报告.md` | 输入包的历史现状审计和需求差距；不是 2026-10-07 运行态或业务闭环证明 |
| E8 | `.omo/evidence/2026-10-07-live-dashboard-availability-r4.md` | 09:12Z 后续复核：5173/43191 health/8090 可达，`43191/data.json` 503，BFF 200 但 STALE；候选 BFF 修改仍未部署 |
| E9 | `docs/reports/2026-10-08-dashboard-sse-overload-recovery.md` §20:27–20:28、§20:34–20:35 UTC | 当前 Chromium 页面/API 并发复核：Cockpit 页面可渲染但 BFF `PARTIAL`；Zhixing 页面部分可渲染，首屏 API/SSE 因 `projection_validation_busy` 间歇 503；后续 health 恢复到 `BOUND_FRESH` 只证明顺序单次状态 |

E7–E8 中的历史判断仅用于定位需求；与当前状态冲突时以 E1–E6 或 E9 中最新且适用的直接证据为准。矩阵其他逐项状态的原始证据多在 2026-10-07 02:07Z 采集；除非条目明确引用 E9，不代表已按 E9 最新时间重新验证。

### 0.2 源条款定位、来源类型与审议边界

稳定源身份由文件路径 + 已接受文件包摘要 + 章节/条款 ID 组成；下文行号是该摘要下的定位辅助，不独立替代摘要。原文摘要变化时，所有对应行必须重新核验。矩阵行必须反向指回唯一源条款，不能仅用章节标题或跨章节大段合并。`UNVERIFIED` 表示当前实现/消费者/运行清单尚未盘点，`UNPROVEN` 表示已有盘点但验收证据缺失，二者不能互换。候选设计、工程测试、运行状态、治理接受和业务价值分别记证据类别；一类证据不得替代另一类。

三类产品主体“管理员、Agent、业务人员”来自用户的产品设计方向，不是白皮书中的原生主体分类。白皮书规范主体/角色包括人类 Principal、Agent 作为受授权执行者，以及 Operator、Steward、Governor、Auditor、Principal 五类权力角色。矩阵中的三主体映射必须标为产品设计扩展，再逐项映射至规范角色与服务端 authority；不能从导航可见性推断权限。

### 0.3 白皮书开放问题与 Principal 审议决策

以下条目是白皮书明确留下、要求在相应阶段前作正式决定的事项。接受整个 v2.1 文档包不自动替代每项的责任人、时点和决策回执；本节记录的是追踪状态，不代 Principal 作决定。

| 条款 ID | 白皮书原文锚点 | 待决事项 | 当前映射 / 状态 |
|---|---|---|---|
| WP-OPEN-01 | WP §27.1，行 2105 | 首个黄金场景的精确定义与人工 baseline | DCP-W0-A；未决，需真实 Scene owner 与 Principal/业务验收人 |
| WP-OPEN-02 | WP §27.2，行 2106 | 唯一 Constitution 的物理权威位置 | DCP-W0-B / DCP-00；未决，保持现有权威不变 |
| WP-OPEN-03 | WP §27.3，行 2107 | Episode、DecisionRecord、OutcomeObservation、HumanVerdict 与 OMO/MOS schema 的最小兼容模型 | DCP-TRACE-01 / DCP-30；未决，禁止新建第二本体 |
| WP-OPEN-04 | WP §27.4，行 2108 | `.omo/goals/current.yaml` 是否完全成为 Portfolio 派生投影 | DCP-00；未决，不改动现行 authority |
| WP-OPEN-05 | WP §27.5，行 2109 | Outcome 与 HumanVerdict 的唯一生产写面 | DCP-W0-B / DCP-20；未决，保持写入关闭 |
| WP-OPEN-06 | WP §27.6，行 2110 | 长期 mandate 中可自动执行的 R0/R1 Value/Evolution 变更范围 | DCP-20 / DCP-30；未决，不扩展自治 |
| WP-OPEN-07 | WP §27.7，行 2111 | 资源与注意力成本归集到 Episode 的方法 | DCP-W0-A / DCP-40；未决，先测人工基线 |
| WP-OPEN-08 | WP §27.8，行 2112 | 既有 BET 的保留、合并、退役和历史化规则 | DCP-00 / DCP-TRACE-01；未决，禁止批量 Ledger 写入 |
| WP-OPEN-09 | WP §27.9，行 2113 | execution-chain warnings 的消费者/手工/退役分类 | DCP-W0-B / DCP-40；未决，先盘点 consumers |
| WP-OPEN-10 | WP §27.10，行 2114 | LifeOS 扩至健康、家庭、组织时的 Principal/Space/Charter 独立合同 | W4–W6；未决，当前 work-first 边界不外扩 |
| WP-REVIEW-01 | WP §28.1，行 2122 | 真实结果而非系统活动是最高目标函数 | 精确 v2.1 包接受回执存在；决策运行绑定仍待证 |
| WP-REVIEW-02 | WP §28.2，行 2123 | work-first、LifeOS-ready 验证路径 | 精确 v2.1 包接受回执存在；W0 样本未完成 |
| WP-REVIEW-03 | WP §28.3，行 2124 | 1—2—8—5—1 是关系模型，不是新运行时 | 精确 v2.1 包接受回执存在；架构边界运行证明未完成 |
| WP-REVIEW-04 | WP §28.4，行 2125 | 元体系无业务执行权且递归终止于人类 | 精确 v2.1 包接受回执存在；运行 PEP/执行分离未证 |
| WP-REVIEW-05 | WP §28.5，行 2126 | 现有目标与 BET 重新证明战略位置 | 精确 v2.1 包接受回执存在；逐 BET mapping 未完成 |
| WP-REVIEW-06 | WP §28.6，行 2127 | 先完成 Constitution/Authority/Object/Relation 再生成新 Goal/BET | 精确 v2.1 包接受回执存在；Workspace binding/G0 未完成 |
| WP-REVIEW-07 | WP §28.7，行 2128 | 最终里程碑以连续真实 Outcome 而非工程量证明 | 精确 v2.1 包接受回执存在；连续价值窗口未开始 |
| WP-REVIEW-08 | WP §28.8，行 2129 | 两主闭环 + 嵌套回路的 counter-loop、饱和上限和 kill switch | 精确 v2.1 包接受回执存在；映射和运行验收未完成 |
| WP-REVIEW-09 | WP §28.9，行 2130 | 单/双/三环学习分权，第三环永久由 Principal 裁决 | 精确 v2.1 包接受回执存在；运行授权链未证 |
| WP-REVIEW-10 | WP §28.10，行 2131 | 可信性采用不可抵消向量门 | 精确 v2.1 包接受回执存在；组合 evaluator 未运行验收 |
| WP-REVIEW-11 | WP §28.11，行 2132 | Trace、Provenance、Authenticity、Truth/Value 分离 | 精确 v2.1 包接受回执存在；端到端数据合同未证 |
| WP-REVIEW-12 | WP §28.12，行 2133 | Mixed-Initiative 自治保留接管、重置、撤销、关停权 | 精确 v2.1 包接受回执存在；操作级 authority/recovery 未证 |

WP §28 建议的后续《宪法与元体系设计包》四部分（Personal Constitution、Meta-types/Object Model、Authority & Interface Contract、Global Invariants & Amendment Protocol）在 WP §28.13–28.16（行 2135–2146）另列为 DCP-W0-B 输入；未接受前不得以当前矩阵替代该设计包，也不得开始 Goal/Portfolio 或 Ledger 写入。

## 1. 总体模型与最终验收

| 白皮书纲领 | 产品实现约束 | 当前状态 | 通过证据 |
|---|---|---|---|
| 1 个最终主权：Principal | 身份、目标、红线、授权、撤销和关停权均能追溯到明确的人类 Principal；Dashboard 管理员身份不能自动等价 Principal | 部分〔E2、E4〕 | 唯一 Constitution/Principal 权威源、身份到 Principal 的服务端绑定、授权与撤销回执、访问拒绝用例 |
| 2 个主闭环：价值、进化 | Journey 与 Evolution 使用同一 Episode/Outcome/Receipt 因果链；提案、回放、灰度、提升和回滚不能自批 | 未证〔E1、E7〕 | 一条真实价值闭环和一条经独立审批的可逆进化闭环，包含用户 verdict 和真实后果 |
| 8 个核心体系 | 八体系各有唯一权威与明确边界，Dashboard 仅聚合权威数据 | 部分〔E3、E7〕 | S1–S8 映射、系统间契约、权威写入者清单和无重复状态机检查 |
| 5 个横切平面 | 五平面通过共用 Policy/PEP/Metric/View 施加约束，不各自造状态机 | 部分〔E1、E2、E5、E7〕 | 五平面跨 Journey 的安全、恢复、资源、时间来源、体验验收证据 |
| 1 个元体系 | 定义到退役的 `Define→Compile→Enforce→Observe→Reconcile→Learn→Retire` 链纳入现有机制，不新增超级控制器 | 未证〔E3、E5、E7〕 | 契约版本、变更权威、兼容迁移、独立观察与退役/回滚演练 |
| 北极星：每周真实、成功、被消费的闭环旅程 | 工程活动、PR、Agent 数、调用量和静态 KPI 不计为价值 | 未证〔E1、E7〕 | 连续 12 周、带业务消费人确认的 Episode/Outcome/HumanVerdict/ValueRecord；指标有 owner、来源、年龄及反作弊策略 |
| 价值闭环 A（WP §7.2，行 587–602） | Signal→Context→Decision→Goal/BET→Mandate/Policy→WorkflowRun→Deliverable/Receipt→HumanVerdict→Outcome→ValueRecord | 未证〔E1、E4、E7〕 | 单独的真实 Episode 端到端链、独立消费/裁决回执和原始数据复算 |
| 进化闭环 B（WP §7.2，行 604–620） | Outcome/Failure→Memory Update→Improvement Hypothesis→Replay→Sandbox→Shadow→Canary→Human/Policy Decision→Promote/Reject/Rollback/Retire | 未证〔E5、E7〕 | 与价值闭环分开追踪；真实结果、独立批准、回放、回滚和退役证据齐备；不得成为平行运行系统 |

源模型定位：WP §0.1–0.3（原文行 49–106）、§7.2（行 585–620）。闭环中的每个箭头都必须能映射稳定对象关系与 writer/authority；仅有页面、运行数量或工程 artifact 不能证明闭环成立。

## 2. 二十四条指导原则逐项映射

| ID | 原则 | Dashboard 必须满足的可观察行为 | 执行计划映射 | 当前状态 / 缺口 |
|---|---|---|---|---|
| P01 | 人类主权优先 | 目标、风险红线、高影响授权和终止权属于 Principal；Agent 不代替裁决 | DCP-20A/B、DCP-21、DCP-30 | 部分；服务端 Principal 全覆盖和真实人工裁决未证〔E2、E4〕 |
| P02 | 真实结果优先 | 明确区分产物、完成、Outcome、被消费价值 | DCP-30A/B/C、DCP-40 | 未证；无真实消费回执闭环〔E1、E7〕 |
| P03 | 一条权威链 | 从 Vision 到 Learning 通过可查询因果 ID 连接 | DCP-TRACE-01、DCP-20、DCP-30 | 部分；当前追踪矩阵和对象 writer 尚未全量绑定〔E2、E3、E4〕 |
| P04 | 单一人类入口 | Cockpit `/panorama` 作为 Zhixing 唯一人类体验，旧入口逐项迁移并保留回滚 | DCP-00、DCP-ROUTE-01 | 部分；SSOT 文档已有，物理入口、旧页迁移与受管启动未验收〔E1、E3〕 |
| P05 | 单一执行脊柱 | 跨层正式执行由 OMO/Workflow Mesh 持有，不由 Dashboard 复制调度 | DCP-20C、DCP-30 | 部分；Agent command/outbox 与真实写入仍 HOLD〔E4〕 |
| P06 | 一个逻辑真值，多种投影 | Dashboard 投影可重建且永不写成第二权威 | DCP-10/11、DCP-40 | 部分；完整源契约和 freshness/partial 展示未稳定运行〔E1、E5〕 |
| P07 | 关系先于组件 | 新页、API、服务必须说明目的、权力边界、权威源与生命周期 | DCP-TRACE-01、DCP-ROUTE-01 | 部分；56 页目录有候选 disposition，跨系统能力关系未逐项验收〔E3〕 |
| P08 | 复用优于新建 | 同功能优先复用既有 Cockpit/OMO/ECOS/Knowledge；新增能力需要替代旧面或证明必要性 | DCP-00、DCP-ROUTE-01 | 部分；目标架构有定义，服务/入口真实收敛未验收〔E3、E6〕 |
| P09 | 声明、运行、价值分离 | UI 明示源码候选、运行健康与业务结果的不同证据级别 | DCP-10、DCP-40 | 部分；Cockpit 有 LIVE/STALE/UNKNOWN 源码候选，端到端和价值分离未验收〔E1、E5〕 |
| P10 | 权限靠近副作用执行 | 每个写路由有可信 Principal、Capability、Resource Scope 和 fail-closed PEP | DCP-20A/B、DCP-AUTH-02 | 未证；静态矩阵 155 个运行时写操作只有 143 个带中央可选 auth wrapper，handler/downstream 还需逐项核验〔E2〕 |
| P11 | 进化不得自证 | proposer、执行者和 verifier 分离；promotion 需要外部批准 | DCP-30、DCP-40、后续 Evolution bet | 未证；进化接受与独立回放闭环未实现验收〔E7〕 |
| P12 | 可逆性默认 | shadow→canary→promotion 有明确 kill switch、撤销和回滚 | DCP-30C、DCP-40、W3–W6 | 部分；工程候选有 worktree/rollback，产品级逐场景恢复演练未证〔E3、E4〕 |
| P13 | 注意力预算是一等资源 | Inbox、审批、提醒具优先级、批处理、静默、安静时段与成本归因 | DCP-UX-ACCEPT-01、DCP-40 | 未证；未建立通知/审批/解释负担基线与护栏〔E7〕 |
| P14 | 价值指标抗污染 | 工程/治理活动默认不计价值，指标要有归因、反作弊和人工裁决 | DCP-30、DCP-40 | 未证；无连续真实消费样本〔E1、E7〕 |
| P15 | 复杂度必须付费 | 新的长期 route/API/service/automation 对应替代或退役清单和维护成本 | DCP-ROUTE-01、DCP-40 | 部分；路由目标 disposition 有候选，零孤儿/零重复的整体证明未完成〔E3〕 |
| P16 | 时间和来源是一等字段 | 每个正式断言含来源、版本、观测时间、有效期、置信和失效方式 | DCP-10/11、DCP-TRACE-01 | 部分；数据层有候选字段，full/compact、BFF、UI 端到端同源一致性未证〔E1、E5〕 |
| P17 | 故障必须可见且可恢复 | 不可用/过期/未知不转绿、不用缺失值补零；可接管、恢复、重试、回滚 | DCP-10/11、DCP-40 | 部分；真实访问证明 full API 503、刷新年龄越界时 BFF 在 STALE/UNKNOWN 间波动〔E1〕 |
| P18 | 退役是正常生命周期 | 有消费者、依赖、迁移和回滚证据前不退役；达到条件后确实移除旧面 | DCP-ROUTE-01、DCP-40 | 部分；旧路由 disposition 尚未逐项 parity / consumer proof〔E3〕 |
| P19 | Agent 可替换、制度不可遗忘 | durable Role/Queue/Policy/Checkpoint 存在于系统而非会话 | DCP-20C、DCP-21 | 部分；lease/assertion 候选存在，受信 OMO broker/outbox 未就绪〔E4〕 |
| P20 | 最小上下文编译 | Agent 只读任务闭包中必要来源；Dashboard 可显示上下文及 provenance | DCP-20C、DCP-30 | 部分；控制胶囊合同存在，真实跨场景运行与泄露负测未完成〔E4〕 |
| P21 | 组合健康优先 | 任何上游 halt/stale/unknown 都压制局部绿灯 | DCP-10/11、DCP-40 | 部分；projection lease 与 data observed 时间可分离，republisher 续 lease 但保留旧 `observed_at`〔E1、E5〕 |
| P22 | 持久角色、临时语义执行者 | 职责/SLO/队列/checkpoint 持久；Agent 在有界任务中启动和退出 | DCP-20C、DCP-21 | 部分；队列与身份候选有，实际受控派发及结束语义未证〔E4〕 |
| P23 | 控制器必须自证健康 | Observer 有独立 Observer；超时、缺失、无消费都失败而不是健康 | DCP-11、DCP-40 | 部分；collector 候选经复审，未进入受信 revision、未做 live recovery/30 组样本〔E5〕 |
| P24 | 信任根位于受控对象之外 | 高影响动作由独立规则、权限、执行器和 verifier 控制 | DCP-20A/B/C、DCP-40 | 未证；Agent possession broker、完整 route PEP 和独立 live verifier 尚未打通〔E2、E4〕 |

## 3. 八个核心体系、五个横切平面与二十个对象

| 白皮书域 | 逐项要求 | 唯一写入权威/产品表现 | 计划绑定 | 当前验收缺口 |
|---|---|---|---|---|
| S1 主权与宪法 | Principal、Constitution、Values、Risk Appetite、Non-goals、Revocation | Principal/治理源；Cockpit 展示授权和撤销影响 | DCP-20、DCP-21、DCP-UX | 身份 broker、唯一 Constitution、真实撤销端到端未证〔E2、E4〕 |
| S2 感知与情境 | Signal、Source、ContextSnapshot、Freshness、Dedup、Classification | 连接器/Signal authority；Cockpit inbox 显示 source 和时间 | DCP-10/11、DCP-30 | source freshness 不连贯；Signal 到 Episode 稳定绑定未证〔E1、E5〕 |
| S3 知识与记忆 | KnowledgeClaim、Belief、Memory、Preference、Provenance、Conflict、Decay、Forget | Kairon/MOS/gbrain 的声明与记忆 authority | DCP-21、DCP-30、DCP-TRACE | 逻辑读写收敛与纠错/遗忘传播闭环未证〔E3、E7〕 |
| S4 战略/目标/组合 | Vision、Objective、KR、Campaign、Milestone、BET、Dependency、WIP、Kill criteria | Portfolio/OMO governance authority；Dashboard 作为只读投影 | DCP-00、DCP-TRACE、DCP-40 | Goals/Portfolio/ledger 权威冲突与 binding 未关闭〔E6〕 |
| S5 决策 | DecisionRecord、Options、Trade-off、Assumption、Confidence、Review/Supersession | Decision authority；Cockpit 提供解释、选项、拒绝/不行动 | DCP-21、DCP-30、DCP-UX | DecisionRecord 未与 Episode/Outcome 成为稳定枢纽〔E7〕 |
| S6 治理与信任 | Policy、Admission、Permission、Mandate validation、Audit、Gate、Waiver、Evidence grade | OMO/GaC/MOF 和代码 PEP；UI 只能解释结果 | DCP-20A/B/C | 155 个运行时写操作完整授权矩阵与唯一审计 writer 未证〔E2〕 |
| S7 运行与执行 | WorkPacket、WorkflowRun、Dispatch、Lease、ToolCall、ActionReceipt、Retry、Compensation、Recovery | OMO/Workflow Mesh 和 Runtime；Cockpit 查看/批准受授权动作 | DCP-20C、DCP-30 | Broker/outbox 下游幂等恢复及统一运行状态未证〔E4〕 |
| S8 价值验证与进化 | Outcome、HumanVerdict、Revision、TimeBurden、ValueRecord、EvolutionProposal、Experiment、Promotion | Outcome/Value authority 与 Principal verdict；候选进化由独立治理批准 | DCP-30、DCP-40、W3–W6 | 真实用户消费与学习效果持续样本缺失，proposal 不得自动晋级〔E1、E7〕 |
| CP-SEC 安全隐私信任 | 身份、分级、最小权限、供应链、外发范围 | 各 writer PEP + 身份 authority | DCP-20、DCP-30 | 三主体服务端认证、resource scope 和隐私测试未通过〔E2、E4〕 |
| CP-REL 可靠恢复 | 健康、降级、RTO/RPO、恢复演练、关键旅程 SLO | Run/Service authority；UI 暴露异常及接管动作 | DCP-11、DCP-30、DCP-40 | API 503、源新鲜度和 managed runtime 未通过〔E1、E5〕 |
| CP-ECON 资源经济 | 时间、注意力、Token、算力、并发、维护成本 | Episode/Run 的预算与成本 writer | DCP-30、DCP-40 | 每条 Journey 的资源/注意力归因尚未实测〔E7〕 |
| CP-TEMP 时间来源 | observed_at、validity、schema、causation、migration | 各源提供；adapter 保真传递 | DCP-10/11、DCP-TRACE | lease、artifact generation、facet observed_at 需统一并区分〔E1、E5〕 |
| CP-UX 人机体验 | Inbox、解释、审批、通知、纠错、无障碍 | Cockpit 产品层；授权和结果状态由服务端/领域权威返回 | DCP-21、DCP-UX、DCP-30 | 键盘/屏幕阅读器/注意力预算及通知 burden 验收缺失〔E3、E7〕 |

### 3.1 二十个规范对象的覆盖合同

字段名、版本和必填性完全遵循架构蓝图 v2.1 §7；这里仅映射责任与验收，不建立第二份 schema。

| 对象 | 权威/写入责任 | Dashboard 用法 | 状态 |
|---|---|---|---|
| Principal | S1 身份 authority | 绑定用户视图与最终责任主体 | 未证〔E2、E4〕 |
| Constitution | S1 Principal/constitution writer | 解释目标、边界、偏好与撤销状态 | 部分〔E6、E7〕 |
| Signal | S2 source adapter | Inbox 来源和去重依据 | 部分〔E1、E7〕 |
| ContextSnapshot | S2/S3 snapshot producer | 提供当时已知/未知事实与 provenance | 未证〔E1、E7〕 |
| KnowledgeClaim | S3 knowledge authority | 展示声明、来源、置信、有效期和冲突 | 部分〔E3、E7〕 |
| Episode | 跨 S2/S5/S7/S8 派生 | 统一旅程因果视图和用户反馈锚点 | 未证〔E4、E7〕 |
| DecisionRecord | S5 decision writer | 展示选项、取舍、信心、复审和 supersession | 未证〔E7〕 |
| Objective/KR | S4 portfolio authority | 展示愿景进度但不能用工程 proxy 补分 | 部分〔E6〕 |
| BET | S4 portfolio/ledger authority | 只读呈现授权承诺、依赖、kill criteria | 部分〔E6〕 |
| WorkPacket | S7 OMO authority / S6 admission | Agent/执行者任务合同 | 部分〔E4〕 |
| ControlCapsule | S6/S7 compiler | 显示本次任务的上下文与证明闭包 | 未证〔E4〕 |
| Mandate | S1/S6 authority | 显示授权范围、预算、期限、撤销方式 | 部分〔E2、E4〕 |
| PolicyDecision | S6 deterministic PEP | 显示 allow/deny/needs-human/degrade 及理由 | 部分〔E2、E4〕 |
| WorkflowRun | S7 OMO | 统一显示执行状态、checkpoint 和恢复 | 部分〔E4〕 |
| ActionReceipt | S7 effect writer | 证明副作用、幂等 ID 和结果 | 未证〔E4〕 |
| CoverageReceipt | S6/S7 独立验证 writer | 证明控制实际装载/执行及缺失/降级 | 未证〔E4、E5〕 |
| OutcomeObservation | S8 source observer | 观察世界变化，不混入价值裁决 | 未证〔E1、E7〕 |
| HumanVerdict | 仅 S1 Principal 对 S8 Outcome 的裁决 writer | 接受、修改、拒绝、忽略或不行动；业务人员仅提供消费证据，除非服务端明确绑定为该 Episode 的 Principal/授权裁决者 | 未证〔E4、E7〕 |
| MemoryUpdate | S3/S8 controlled writer | 显示候选、批准、纠正、遗忘与传播 | 部分〔E3、E7〕 |
| EvolutionProposal | S8 proposer；S6/S1 independent promotion | 展示回放、实验、批准、回滚、退役 | 部分〔E5、E7〕 |

对象统一验收还必须验证六类公共语义：身份/版本、owner/authority、状态/生命周期时间、关联/因果、来源/证据、敏感性/退出；Episode 的 OutcomeObservation 与 HumanVerdict 必须由不同 ID、时间和 writer 保存。

### 3.1.1 对象关系、权力边界与证据合同

| 条款 ID | 白皮书锚点 | 必须单独验收的合同 | 当前状态 / 缺口 |
|---|---|---|---|
| WP-REL-01 | WP §11.2，行 880–885 | 二十对象逐一具有 identity/version、owner/authority、state/lifecycle time、association/causality、source/evidence、sensitivity/exit 六类公共语义 | 部分〔E4、E7〕；对象名录存在，逐对象合同与 consumer 运行映射未完 |
| WP-REL-02 | WP §11.3–11.4，行 886–936 | 关系守恒、六个元类型与六种规范关系；任何投影/摘要不可改写因果、权威或对象身份 | 未证〔E3、E4、E7〕；需建立 source clause→relation→writer/API 清单和断链负测 |
| WP-REL-03 | WP §11.5–11.6，行 937–960 | 七种认知声明状态及统一因果上下文可区分事实/假设/未知等认知状态，保留 source、authority、time 和 lineage | 未证〔E1、E4、E7〕；UI 状态 union 不能替代知识权威对象状态合同 |
| WP-CAPSULE-01 | WP §11.7，行 961–968；BP §10 | Control Capsule 编译最小任务闭包；缺失/陈旧/错绑定上下文遇 effectful action 时必须 fail closed | 部分〔E4、E5〕；存在候选合同和部分负测，未在真实 Episode/runtime 验证 |
| WP-RECEIPT-01 | WP §11.8，行 969–984；BP §11 | Coverage Receipt 绑定 Capsule/Run/Episode/Actor/runtime/effect；独立 verifier 可复算控制是否实际执行；业务 Outcome 独立于工程结论 | 部分〔E4、E5〕；候选 receipt 不构成真实副作用与 Outcome 的同次链 |
| WP-RISK-01 | WP §12，行 985–1030 | R0–R3 权限与可逆性分层、决策冲突词典序、no-action 是正式决策；默认不推断 READ_ONLY | 部分〔E2、E4〕；R0–R3 需拆独立 gate/负测，当前无全 effect inventory |
| WP-META-01 | WP §10.1–10.8（行 742–852）、§31.7（行 2355–2370） | 元体系管理概念/边界/关系/契约/生命周期，不派工、不执行业务、不成为第二 SSOT；递归终点为 Principal，TCB 各边界由独立 writer/verifier 守护 | 未证〔E3、E5、E7〕；治理文档存在，运行权力分离/TCB 跨信任域证据未完成 |
| WP-VISION-01 | WP §25.1–25.4，行 2035–2074 | 体系、BET、Objective、Vision 有不同完成定义；Vision 只能按 `VISION_PROVEN` 条件由长期真实证据与 Principal adjudication 完成 | 未证〔E1、E4、E7〕；需独立接受连续窗口、用户结果、迁移/关停证据 |
| WP-AUTHORITY-01 | WP §1.3（行 147–163）、§34.2（行 2470–2479） | 白皮书拥有愿景/原则/体系边界/长期战略/完成定义；蓝图拥有架构合同；路线图拥有阶段顺序与退出证据；当前运行/BET/PR 状态必须另用新鲜事实源 | 部分〔E6、E7〕；矩阵需保持文档 authority 与 runtime snapshot 分层，不能把源条款当运行状态 |

`WP-RISK-01` 当前继续拆为 BP §15.3 的 R0/R1/R2/R3、单写者、Wave cap、handoff、对象身份保持，以及 BP §15.4 的 L0→L1、L1→L2、L2→L3、L3→L4 聚合/异常升级子合同；每项 authority、负测和 receipt 不同，不能以汇总行一并判 PASS。

### 3.2 白皮书、架构蓝图与路线图逐项验收映射

本表严格区分三个规范来源：`WP` 指《织星主权智能操作系统白皮书 v2.1》，`BP` 指《织星主权智能操作系统全景架构蓝图 v2.1》，`RM` 指《织星主权智能操作系统路线图与里程碑 v2.1》。章节号只在对应文件内部有效，不跨文档借号。下表覆盖所有顶层章节；BP §15、§19–23 已按原文子项拆解为可审阅映射，但许多当前实现、运行和业务证据尚缺，DCP-TRACE-01 仍未完成。

| 规范条款 | 必须实现的约束 | 唯一 authority / writer | 产品面与接口 | 必须验收的场景 | 退出门 |
|---|---|---|---|---|---|
| WP §0–5 白皮书地位、基线、根因、理论与宪法 | 愿景围绕真实角色责任和本人接受的受托结果；八项权利不可让渡；目标/事实分轴；旧日期诊断只作历史基线 | Principal；现有 OMO 权威链；各动态源 owner | `/panorama`、Decision Inbox、权利/恢复入口与 evidence detail | 工程活动冒充价值；历史数字冒充当前；权利被 Agent 或普通管理员代行 | 每项宪法要求关联唯一 authority、当前证据、产品交互与安全负例；无证据即 UNPROVEN |
| WP §6–10 原则、1—2—8—5—1、核心体系、横切平面与元体系 | 24 原则逐条映射；一主权内核、两闭环、八体系、五平面、一元体系；元体系不成为第二 dispatcher/真值 | 每体系明确唯一 owner；OMO 仅承载其授权职责；Principal 管目的与高风险权力 | IA、体系地图、依赖拓扑、制度连续性视图 | owner 重叠、平行 inbox/ledger、元体系成为业务写入者、横切能力遗漏 | 24 原则与 8/5/1 职责双向映射；冲突测试及唯一 writer 证据通过 |
| WP §11–14 对象、权力边界、系统间契约与反馈动力学 | 20 个规范对象、关系守恒、分段 writer、读写契约、快慢回路隔离 | 各对象 canonical owner；OMO/Ledger broker；Outcome 与 HumanVerdict 独立 writer | 对象详情、Episode/Run/Outcome 时间线、契约/API 清单 | 无 owner 对象、关系断裂、Outcome 与裁决混写、快环改慢环目标 | 对象/关系/API 清单逐项有 owner、schema、source、生命周期与反例；端到端 replay 通过 |
| WP §15–18 杠杆点、宏观战略、组合/BET、指标与证据 | 资源投向真实价值；BET 不替代 Portfolio 权威；指标有分子分母、来源、证据级别和不可抵消 guardrail | Portfolio owner；Principal；独立 evaluator | Portfolio、北极星与分项 Guardrail、BET/Outcome 下钻 | 任务数/PR/绿灯替代结果；分母排除失败项；可信性折算成单一分数 | 原始事件可复算；BET/目标/Outcome 权威链完整；guardrail 单项失败可压制总体通过 |
| WP §19–24 节律、收敛、错误/降级、红队、里程碑与回滚 | 周期/预算有界；能力原位复用优先；失败态和全局停机明确；阶段门不可由日期自动放行 | Ops/领域 owner；OMO/PEP；Principal 对停止与目标变更有权 | 运维节律、故障面、阶段路线图、暂停/恢复/回滚 UI | stale 信号判无事件、自动批准、无限重试、门槛到期自动绿、恢复遗漏副作用 | 错误矩阵和每个 Phase 均有演练/退出/rollback 证据；停止规则实际可触发 |
| WP §25–34 完成/停止、开放问题、审议、外部对照、制度连续性、多 Agent 与成熟度 | 完成定义覆盖价值/权力/连续性成熟；开放问题保留决策 owner；外部框架仅作对照；多 Agent 遵守角色/并行约束 | Principal；Architecture owner；Portfolio 与独立 Auditor | 成熟度视图、架构审议、开放决策与 Agent role/cell 详情 | 把接受误当实施；无主权威问题；多 Agent 共写同一面；成熟度自评 | 每个条款绑定状态和证据；未决项有 owner/date/默认安全态；R0–R3 与并行写入约束通过负测 |
| BP §0–3 文档权威、当前态、架构不变量 | v2.1 文档各有权威边界；动态基线标注 as-of；14 条目标不变量逐条落硬门 | 各规范文档 owner；运行事实 source owner；独立 verifier | 文档权威矩阵、目标/事实分层、Assurance gate | 旧证据/新文档覆盖现行权威；文档声称即实现；不变量仅靠说明 | 当前文档摘要和每条不变量均有精确来源、authority、负测与退出证据 |
| BP §4–7 逻辑/物理架构、SSOT 与 20 对象 | 1—2—8—5—1 到 P-L0..4/I0/M0/X 映射；规范/运行/证据/认知真相分层；对象、关系和分段写权守恒 | 对象/事件唯一 writer；物理组件 owner；OMO/Ledger broker | 体系/组件拓扑、权威图、对象/API 下钻 | 重复主权组件、projection 当 SSOT、对象多 writer、物理服务绕过 owner | 每个对象和物理组件一一绑定 authority、消费者及恢复路径；跨边界负测通过 |
| BP §8.1–8.3 价值主链与工程链 | Signal→Episode→Decision→Mandate→WorkPacket/Capsule→Run/Receipt→OutcomeObservation→HumanVerdict→Close；工程链只作为能力支撑，不直接计价值 | Signal/source adapter；Decision writer；OMO Run/Receipt；Outcome observer；Principal verdict writer | `/inbox`、Episode 详情、Decision/Outcome 时间线、只读 Portfolio projection | 真实 Signal 与 no-action；失败/等待/补偿状态；PR merged 但无 Outcome；Outcome 与 verdict 分开更改 | W1 至少一个同次动作真实 E4 Episode；W2 连续窗口通过 |
| BP §8.2 Episode 状态机 | 只允许定义的转移；`awaiting_authority` 超时不批准；`OutcomeMissing` 保持 evaluating/unprovable；failed 不改写成 success | OMO Episode projection；各段事件 writer | Episode 时间线、待裁决队列、状态 API | 非法转移、超时授权、缺失 Outcome、failed 后恢复新 Episode、no-action 复查条件 | 状态转移模型测试与真实回放都通过 |
| BP §9 七段制度连续性 | Define→Compile→Enforce→Observe→Reconcile→Learn→Retire 首尾闭合；只有声明/owner/review date 不算有效规则 | Constitution/Policy authority；OMO compiler/PEP；独立 observer/auditor；Principal 负责高风险退役 | 治理域规则详情显示七段状态、证据和断点；API 提供逐段 receipt | 每段缺失、stale、无消费、observer 自失效；有效性与退役候选分离 | 每条 required invariant 具备 owner、compile、enforce、observe、reconcile、effectiveness 与 retirement 证据 |
| BP §10 Capsule 合同与编译 | 绑定身份/任务/authority/source freshness/effects/capabilities/budgets/hazards/proofs/omissions/degradation/signature；effect graph 与关系、owner、risk、data class 共同决定上下文 | OMO WorkPacket/Capsule compiler；Principal/Mandate authority | Agent 工作项的“本次授权”抽屉；Capsule inspect/read API | 省略/过期/冲突、scope 扩大、lease 改变、只读转写入、编译器版本漂移均刷新或拒绝 | 精确字段合同、重编译/过期/撤销负测、冷启动替换 Agent 回放通过 |
| BP §11 Coverage Receipt | 绑定 Capsule/Run/Episode/Agent/runtime；记录控制版本、执行点、输入摘要、动作、proof、遗漏和独立 verifier；控制覆盖、工程成功、业务价值三种结论分离 | 实际 PEP + OMO/Ledger broker；Verifier 独立核验 | Run 详情展示 coverage 状态和原始 evidence 链接；receipt API | 缺 receipt=UNPROVABLE；checker timeout/error 不变绿；动作成功但业务 Outcome 未知 | 同次真实副作用产生防伪 receipt；独立 replay 可复算 |
| BP §12 PDP/PEP 与 effect taxonomy | 所有 effectful API 在副作用前复核身份、Mandate、scope、freshness、lease、digest、idempotency、补偿和系统模式；无法证明 READ_ONLY 默认 effectful | OMO/现有 broker + 各真实副作用边界 PEP；审计 writer 唯一 | 每个 action preview/confirm/deny 面；OpenAPI 与运行路由清单 | 八类边界：governed state、Git、外部通信、服务与凭证、删除迁移、模型外发、算力费用、Constitution/Policy/Ledger；匿名、越界、重放、撤销均拒绝 | 运行 API 清单 100% 映射 PEP/拒绝证据，无 UI-only guard |
| BP §13 三道防线与 TCB | 事前阻断、持续监督、独立保证分属可验证信任域；executor 不能改写 required check、receipt 或 Principal recovery key | Identity/Mandate、Ledger broker、Capsule compiler、PEP、独立 watchdog/reviewer | 管理员的信任链视图；部署/证明 API 只读 | 共享 OS 权限下的伪独立、executor 改验收、根凭证撤销/丢失/轮换、out-of-band halt | 关键控制至少跨一个 executor 不可写的边界，并完成 key lifecycle 与 compromise recovery 演练 |
| BP §14 Resident 健康与权限 | Role/Queue/Lease/Checkpoint/SLO 持久，Agent 临时启动；liveness 不等于功能健康；自动调和仅限预定义、内部、可逆、幂等 | Resident desired-state owner；确定性 supervisor；OMO 持有派工和执行权 | 管理员 Runtime/Resident 视图、health API | PID 活着但无消费、stale digest、队列滞留、重复、dead letter、observer 失明、超 scope 修复请求 | 功能 SLO 证明 input→consume→verified outcome；超 scope 只创建 incident/proposal |
| BP §15.1 五控制级 | C-L0 Reflex 毫秒—分钟控制单次工具/写入/进程（PEP/sandbox/quota；deny/error/不可补偿升级）；C-L1 Run/Episode 分钟—小时控制 WorkPacket/Run/Episode（Workflow Mesh；lease 丢失/scope drift/等待超时升级）；C-L2 Scene/Domain 小时—天控制场景/来源/领域队列（domain steward/reconciler；连续退化/跨域冲突升级）；C-L3 Portfolio 周—月控制 Objectives/BET/预算/WIP（Portfolio review；价值不成立/依赖冲突/容量超限升级）；C-L4 Constitution/Meta 月—季度控制目的/边界/制度/演化（Principal+独立审查；价值冲突/重大风险/体系失配升级）。快环只能保护慢环，正常状态在本层闭合 | 各层唯一 controller；Principal；Portfolio owner；独立 Auditor | 控制级拓扑、每级例外队列、升级事件 API | 每级分别注入正常闭合、阈值越界、错误升级、低级无权修改高级目标 | 五级的时标、对象、目标、controller、升级条件都有可执行契约与逐级负测；升级不丢 source/authority |
| BP §15.2 五类逻辑角色 | Operator/Steward/Governor/Auditor/Principal 按职责、允许承担者、不可兼任条件分权；产品主体与规范角色分别建模 | 服务端 principal/role authority；OMO policy；独立 Auditor | persona × authority × action/resource 矩阵与审计页 | 执行者自验收、高风险批准者自执行、Agent 代 Principal、普通管理员凭证升权 | 所有产品主体/制度角色映射均有服务端证据和越权拒绝测试 |
| BP §15.3–15.4 Agent Cell、并行与信息压缩 | R0 低不确定只读可合并 Planner/Executor/Verifier；R1 内部可逆 mutation 至少 PEP+独立机器验证；R2 外部有限可逆动作审批者与执行者分离；R3 不可逆/高影响动作需 Principal 明确批准+独立 verifier。相同写面只有一个 writer，Wave 并行上限由 Portfolio 明确；handoff 携带 WorkPacket/Capsule/checkpoint/unresolved findings/receipts，Agent 替换不改权威对象身份 | OMO dispatcher/lease owner；PEP；Portfolio owner；Principal；独立 verifier | Agent Cell/lease/receipt 面、写锁与 Wave capacity 仪表 | 各风险级别合并角色负例、双 writer 竞争、超并行上限、handoff 冷启动、Agent 替换 | R0–R3 每类有 allow/deny/receipt 测试；单 writer/CAS 和 Wave 上限由服务端强制；替换后可 replay |
| BP §19 当前能力处置矩阵 | 每项能力依证据标为 EXISTS/EXTEND/BUILD-IN-PLACE/RETIRE；逐条绑定原文能力名、旧判定日期、当前实现证据、目标 owner、消费者、主要缺口与退役/迁移条件 | 各 capability/project owner；独立 source auditor | 能力目录与处置视图、消费者/API/依赖清单 | 已归档资产被复活、旧状态当动态事实、无 consumer 的能力继续扩张 | 原文每行均有一条矩阵记录；现状未核查项写 UNVERIFIED，不从 2026-09-07 旧标签推断 |
| BP §20 项目边界映射 | 每个原文项目逐项记录目标职责、可以扩展、明确禁止；新增能力先找现有 owner，只有独立安全/故障/扩缩容/许可边界充分证明才可新建 | 每个既有项目 owner；Architecture authority 决定边界 | 项目能力地图与依赖视图 | 第二 dispatcher/SSOT、Cockpit 复制状态机、无隔离理由新顶级项目 | 原文每个项目行都有目标 owner、扩展允许、禁止边界及当前仓库/API证据 |
| BP §16 组合健康 | HALT/RECOVERY/STALE/UNKNOWN 在组合级压制局部绿；不可用、未覆盖、过期不得以分数平均掩盖 | 独立组合健康 evaluator；源只提供事实 | `/panorama` 全局状态、依赖图、下钻与 source age | 单 facet stale、source missing、fresh lease + old payload、critical resident failed、局部 green 与组合 halt | 组合判定单调、负例覆盖、状态可追溯回 source version/observed_at |
| BP §17 故障、降级与恢复 | 区分 degraded/read-only/paused/recovery/halt；恢复必须验证重放、补偿、RTO/RPO 和安全态 | 运行/服务 authority；恢复执行仍经 OMO/PEP | 全局 incident banner、能力级降级面、接管/恢复步骤 | API 503、投影陈旧、identity broker down、账本锁/损坏、外部副作用超时、冷启动恢复 | 每个 critical path 有故障矩阵、RTO/RPO、恢复与回滚演练；失败冻结晋级 |
| BP §18、§22 Golden Slice 与完成门 | 同一真实 Episode 使用 Capsule、pre-effect PEP、Coverage Receipt，并具 Outcome 与 Principal verdict；产品、制度和最终愿景门分离 | Scene owner；OMO；Principal；独立 Auditor | `/panorama`→Inbox→Episode→Run→Outcome 工作路径 | 至少 3 个 W0 真实样本；W1 同一次真实动作完整机制与 E4；W2 4 周；W6 12 周、迁移/关停验证 | 分阶段按 E0–E5 和路线图退出条件验收；不得用文档/PR/Gate 全绿替代价值 |
| BP §19 当前能力处置矩阵 | 每项能力依证据标为 EXISTS/EXTEND/BUILD-IN-PLACE/RETIRE；旧判断 as-of 2026-09-07，不自动成为当前状态 | 各 capability/project owner；独立 source auditor | 能力目录与处置视图、消费者/API/依赖清单 | 已归档资产被复活、旧状态当动态事实、无 consumer 的能力继续扩张 | 每行有当前证据、处置 owner、消费者、迁移/退役条件；历史判断不可直接通过 |
| BP §20 项目边界映射 | OMO/Cockpit/ECOS/Agora/MetaOS/Runtime/知识等项目有目标职责、可扩展范围和禁止边界；优先原位扩展 | 每个既有项目 owner；Architecture authority 决定边界 | 项目能力地图与依赖视图 | 第二 dispatcher/SSOT、Cockpit 复制状态机、无隔离理由新顶级项目 | 所有目标能力映射到既有 owner；新项目需安全/故障/扩缩容/许可边界论证 |
| BP §21 红队十项 | 复杂度债、实现幻觉、冷启动、身份伪造、SPOF、版本迁移、模型耦合、经济失控、测试自洽、防腐系统腐化逐项有攻击/验证/剩余风险 | 独立安全 Auditor；被测 owner 修复 | Threat/finding register、红队演练回执 | 十项攻击各自命中负例、修复回归与剩余风险审议 | 无未处置 Critical/High；所有剩余风险由 Principal/治理 owner 接受或阻断阶段门 |
| BP §22 验收与完成定义 | Engineering/Operational/Value 三门分离；制度连续性、Golden Slice、最终愿景各有单独且不可互相替代的完成条件 | 独立 Verifier；业务验收人；Principal | 阶段卡、证据包、Value/Runtime/Engineering 三面板 | 工程绿但服务 stale；服务在线但无 Value；E4/E5 与连续观察不足 | 三门分别 PASS 且证据摘要绑定；缺任一门为 PARTIAL/UNPROVEN |
| BP §23 架构门与路线衔接 | G0→G8 严格依赖；每门含前置/产物/负测/通过/失败/rollback/继续授权；日期不自动放行 | Portfolio owner；架构治理 authority；Principal 按门提供授权 | G0–G8 依赖图与阶段门监控 | 跳门、阶段超时自动放行、前置失效后继续 | 路线每项能映射架构门和新鲜 receipt；门禁失败自动保持 HOLD |
| BP §24–25 架构决策与审议门 | 关键决策摘要不覆盖正文合同；审议问题、接受对象和变更范围精确绑定 | Architecture owner；Principal；文档控制 owner | ADR/审议包/摘要与接受信封 | 摘要越权改变正文、接受旧哈希、提出范围不清的批准 | 每个批准绑定精确文档摘要、允许范围和禁止副作用 |
| RM §0–5 文档使用边界、愿景、North Star、守护指标、战略分轨与 W0–W6 依赖 | 路线图只拥有顺序/证据/阶段门；North Star 有同口径复算；Guardrail 不被总分抵消；价值轨与可信控制轨并行并有汇合条件 | Principal；Portfolio owner；指标 evaluator | 北极星、phase dependency 与 guardrail dashboard | roadmap 越权改愿景；synthetic value、工程活动计分、P0 之外的阶段轨道阻塞 | 指标复算与 W0–W1 Golden Slice join 节点证据通过 |
| RM §6–12 W0–W6 Phase 合同 | 每阶段明确 Wave、必需输入、交付物、退出/降级和不做事项；连续窗口不能事后补 | 各 Phase/Scene owner；Principal 处理授权 | Roadmap/Gantt、phase evidence bundle | W0 超时无裁决、W1 越过 scoped safety gate、W2–W6 缺连续数据 | 按阶段新鲜证据逐项 PASS；未通过停在当前 Phase |
| RM §13–18 里程碑、Portfolio→Outcome、BET、指标、预算、停止和恢复 | 30d/90d/1y/3y 里程碑与权威链、资源预算、kill/rollback 守恒 | Portfolio owner；Ops；Principal | 计划/实际资源、预算、kill/recovery 与 Outcome 链 | 超预算、指标分母漂移、stop 条件命中仍运行 | 原始工时/成本/事件可复算；stop/rollback 可演练；无未决恢复 owner |
| RM §19–24 风险、证据、收敛、红队、接受与完成 | 风险有 owner/mitigation；E0–E5 等级不混用；架构收敛有退役门；Principal 精确接受；Phase 与愿景完成条件可审计 | Risk owner；独立 QA/Auditor；Principal | 风险/证据/收敛矩阵与 acceptance receipt | 历史 hash 被复用、退役无消费者证明、合成 QA 被当运行证据 | 当前版本精确审查、证据分级、复核与接受齐备；完成定义逐条过门 |

### 3.3 BP §15、§19–23 子项审阅与验收映射

以下逐项拆解严格以审阅包内架构蓝图 v2.1 的原文表格、列表和编号为锚点。E1–E7 是本矩阵现有证据索引；它们只能支持其“支持范围”内的结论。凡缺少针对该子项的实现、运行或业务证据，均标 `UNPROVEN`；设计文字和 2026-09-07 的蓝图处置标签不作为当前达成证据。Owner 是目标责任角色，不代表当前已有人员认领。

#### BP §15 多层级、多周期、多组、多 Agent 控制结构

| 原文锚点 / 子项 | 逐项要求 | 当前证据与状态 | 明确缺口 | 目标 Owner | 阶段门 | 可验收证据 |
|---|---|---|---|---|---|---|
| §15.1 C-L0 Reflex | 毫秒—分钟内约束单次工具/写入/进程；PEP、sandbox、quota；deny/error/不可补偿时升级 | E2 仅盘点部分 API/写操作；E4 为候选授权验证；`PARTIAL` | 尚无全量副作用边界到 PEP 的运行映射，无法证明所有拒绝在 effect 前发生 | OMO/各副作用边界 PEP owner | G2 规范；G3 首个真实 Episode | API/effect 清单与 PEP 绑定；越权、deny、timeout、不可补偿负测及运行 receipt |
| §15.1 C-L1 Run/Episode | 分钟—小时控制 WorkPacket、Run、Episode；处理 lease 丢失、scope drift、等待超时 | E4 覆盖部分 Work Case/Agent 授权候选；`PARTIAL` | 尚无完整状态机、lease 失效与真实 Episode 运行闭环证据 | OMO Workflow Mesh / Episode authority | G2→G3 | 状态转移合同、lease/scope/timeout 注入、升级事件与重放 receipt |
| §15.1 C-L2 Scene/Domain | 小时—天控制场景、来源、领域队列；连续退化或跨域冲突升级 | 当前索引无 Scene SLO/跨域冲突运行证据；`UNPROVEN` | 缺领域 owner、队列 SLO、退化阈值、升级接收方和跨域隔离负测 | Scene/domain steward | G3→G4 | 至少一个 Scene 的队列输入/消费/结果 SLO、连续退化与跨域冲突演练及升级 receipt |
| §15.1 C-L3 Portfolio | 周—月控制 Objective、BET、预算、WIP；价值不成立、依赖冲突、容量超限升级 | E6 有候选计划；没有本矩阵范围内的当前 Portfolio/WIP 运行回执；`PARTIAL` | 计划文档不证明预算、冲突和容量控制已运行或唯一 writer 已强制 | Portfolio owner | G0/W0 定义；G4 验证运行 | Portfolio 原始事件重算、预算/WIP 越界负测、依赖冲突升级及 writer authority 证据 |
| §15.1 C-L4 Constitution/Meta | 月—季度/重大事件控制目的、边界、制度、演化；由 Principal + 独立审议；价值冲突/重大风险/体系失配升级 | v2.1 精确接受包可证明文档接受，不等同运行控制；`PARTIAL` | 缺权力在运行面落实、冲突升级、独立复核及 Principal 裁决的实际记录 | Principal；Constitution authority；独立 Auditor | G0 接受；G7 验证演化 | 精确版本绑定的权力/变更接口、模拟冲突升级、Principal 决定与独立审计记录 |
| §15.1 快慢环守恒 | 快环只能保护慢环，不能自行修改慢环目标；本层正常闭合，仅阈值越界/权限不足/系统冲突上报 | E2/E4 不覆盖目标修改的完整 authority chain；`UNPROVEN` | 缺快环写慢环目标的拒绝证据、升级信号保留 source/authority 证明 | OMO policy owner；Principal | G2→G3 | 低级 controller 尝试修改高层目标被拒；合法异常升级可关联原始事件、来源与权限 |
| §15.2 Operator | 执行已授权动作；Agent/worker 可承担；高风险不得自验收 | E2 有限认证/路由盘点；没有高风险执行与验收隔离全矩阵；`PARTIAL` | 缺身份×动作×资源矩阵和高风险自验收拒绝的运行证据 | OMO identity/PEP owner；独立 Auditor | G2→G3 | 服务端 principal/role/action/resource 矩阵；Operator 自验收负测及拒绝日志 |
| §15.2 Steward | 维护局部队列、SLO、依赖、上下文；不能自改域目标 | 当前索引无对应 authority/域目标写权限证据；`UNPROVEN` | 缺可承担者、局部写权限和域目标拒绝规则 | Scene/domain steward；policy owner | G2→G4 | Steward 正常维护回放；修改域目标被拒；队列/SLO/依赖变更均有审计 receipt |
| §15.2 Governor | 解释适用政策并 allow/deny/degrade；不能执行其批准的高风险动作 | E2 仅部分 API auth inventory；`PARTIAL` | 缺 governor 决策与执行面分离、degrade 语义和独立权限边界 | OMO policy/Governor owner | G2→G3 | 决策服务身份、策略版本、allow/deny/degrade 输出；高风险自执行负测 |
| §15.2 Auditor | 独立核对 evidence/coverage/outcome；不得由被审计者控制输入和输出 | E5 有候选独立 review；不证明生产审计信任域独立；`PARTIAL` | 缺 executor 不可改写的输入/输出边界及真实 Outcome 核验 | 独立 Auditor / Verifier | G2→G4 | 权限域证明、篡改输入/输出负测、独立 replay 与审计回执 |
| §15.2 Principal | 人类本人掌握目的、宪法、高风险授权、最终裁决；Agent 不代理不可让渡权利 | v2.1 精确接受回执存在；未证明运行身份绑定/授权/撤销能力；`PARTIAL` | 接受信封与 workspace/runtime 权利绑定不同；缺授权、撤销、关停闭环运行证据 | Principal；identity/authority owner | G0→G3 | 人类身份强绑定、授权/撤销/暂停/关停 E2E 与 Agent 代行拒绝回执 |
| §15.2 角色不可兼任矩阵 | Operator、Steward、Governor、Auditor、Principal 按职责/承担者/不可兼任条件分权；与管理员、Agent、业务人员主体区分 | E2/E3 仅覆盖部分认证和表面；`PARTIAL` | 缺产品主体到规范角色的完整映射、冲突组合及服务端执行证据 | Identity/policy owner；产品 owner | G2→G3 | 主体×角色×资源×动作矩阵、所有禁止组合的 API 级拒绝测试 |
| §15.3 R0 | 低不确定只读可合并 Planner/Executor/Verifier | 未见按风险级别分派及读写校验的运行证据；`UNPROVEN` | 缺 READ_ONLY 证明和合并角色的审计/限制合同 | OMO dispatcher；PEP | G2 | R0 样例：只读权限证明、可合并条件、越界写入拒绝与 receipt |
| §15.3 R1 | 内部可逆 mutation 至少有 PEP 和独立机器验证 | E4 有授权候选测试，未证明生产 effect 链；`PARTIAL` | 缺可逆性/补偿合同、真实 pre-effect PEP 和独立 verifier receipt | OMO/PEP owner；独立 verifier | G2→G3 | R1 正/负/过期用例，补偿回放，PEP 前置拒绝和独立验证回执 |
| §15.3 R2 | 外部有限可逆动作由批准者与执行者分离 | 当前证据索引无外部 effect 分离运行证据；`UNPROVEN` | 缺批准身份、执行身份、范围/期限、补偿与审计链 | Principal/delegate authority；外部 adapter owner | G3→G4 | R2 批准/执行双身份对照，超范围/重放拒绝，外部结果与补偿 receipt |
| §15.3 R3 | 不可逆/高影响动作需 Principal 明确批准及独立 verifier | 接受回执不等于单项运行批准；`UNPROVEN` | 缺按动作绑定的 Principal 明确批准、独立复核和不可绕过门 | Principal；独立 verifier；PEP | G3→G7 | R3 明确批准信封绑定 effect/digest/scope；缺批准拒绝；执行后独立核验 |
| §15.3 单写者/Wave 上限 | 同一写面同时仅一个 writer；Wave 并行上限由 Portfolio 明确 | E6 记录计划约束，不证明运行时 CAS/租约已强制；`PARTIAL` | 缺逐写面 owner、竞争写入拒绝和并行上限实际配置证据 | OMO lease/lock owner；Portfolio owner | G2→G4 | 同写面并发冲突实验、CAS/lease receipt、超 Wave cap 拒绝与配置摘要 |
| §15.3 共享对象与事件 | Agent group 共享结构化对象/事件，不共享无限聊天上下文 | 当前索引无上下文/事件边界完整证据；`UNPROVEN` | 缺结构化共享契约、最小披露与上下文上限验证 | OMO WorkPacket/Capsule owner | G2→G3 | 事件/schema 契约、上下文截断/敏感信息负测、冷启动可复现回执 |
| §15.3 Handoff | 必须传递 WorkPacket、Capsule、checkpoint、未决 findings、receipts | E4/E5 有候选 Work Case/receipt；handoff 全字段和真实接管未证；`PARTIAL` | 缺字段完整性、摘要绑定、未决问题不丢失及断点接续证明 | OMO packet/handoff owner；Verifier | G2→G4 | 接管前后对象/digest 对照、缺项拒绝、未决 finding 和 receipt replay |
| §15.3 Agent 替换 | 替换 Agent 不改变 Role、Run、Episode 或权威对象身份 | 当前无全新 Agent 接管真实对象的直接证据；`UNPROVEN` | 缺 cold-start 替换测试及身份/authority 保持证明 | OMO identity/lease owner；独立 verifier | G4→G5 | 新 Agent 无历史聊天，仅凭正式对象安全完成或停止；身份/对象 ID 不变 |
| §15.4 信息压缩 | C-L0 Receipt→C-L1 Episode/Run→C-L2 Scene SLO/exception→C-L3 Portfolio value/risk→C-L4 宪法冲突/系统风险/长期趋势 | 当前索引无该聚合层级的可追溯性证明；`UNPROVEN` | 缺逐级聚合规则、异常优先、原始事件下钻及不得丢 source/authority 的验证 | 各层 projection owner；独立 observer | G3→G4 | 原始事件到五级摘要可双向 drill-down/replay；普通日志被压缩而异常/趋势/待裁决项完整保留 |

#### BP §19 当前能力处置矩阵

下列状态列仅复述蓝图中 **as-of 2026-09-07** 的处置标签，不作现状结论。当前列均以可直接证明该能力现状的证据为准；E1–E7 没有逐项覆盖这些能力，因此未特别注明者一律为 `UNPROVEN`。完成时需补齐消费者/API/依赖清单、迁移与退役条件。

| 蓝图能力（原文逐行） | 2026-09-07 标签 | 当前证据 / 状态 | 缺口 / 必须核查 | 目标 Owner | Gate | 可验收证据 |
|---|---|---|---|---|---|---|
| Human Principal / Constitution | EXTEND | 精确接受包证明接受，不证明 bind/运行；`PARTIAL` | 当前权威绑定、消费者、授权撤销、宪法版本变更面未核 | L4 + OMO authority | G0/G2 | 唯一 authority 图、角色/宪法消费者/API 清单、授权撤销 E2E |
| Cockpit 单一入口 | EXTEND | E1/E3 证明有页面和运行快照，且存在 stale/可用性差距；`PARTIAL` | Decision/Outcome/Recovery 统一旅程、旧入口消费者及退役条件未证 | cockpit | G1/G3/G4 | 页面/路由/API/消费者 inventory；三类关键旅程 E2E；旧入口迁移回放 |
| Agora/BOS 单一织层 | EXISTS | E1–E7 未直接证明当前路由 owner 与 receipt 语义；`UNPROVEN` | route receipt 与 authority receipt 的隔离、活跃消费者及退役条件待核 | agora | G1/G2 | 当前注册/消费者/路由回执；授权判断无法由 Agora 越权执行的负测 |
| OMO / Workflow Mesh 单一 S | EXTEND | E4/E6 有候选流程与计划；未证完整生产链；`PARTIAL` | Capsule/Receipt/组合健康唯一 owner、覆盖面和恢复证据待补 | omo | G2/G3/G4 | 活跃 API/worker/consumer 列表、唯一调度证明、完整 Run replay |
| MetaOS 决策/免疫能力 | EXTEND | 当前索引未验证能力调用和边界；`UNPROVEN` | 与唯一 S slot 的调用边、独立 dispatcher/inbox 排查、消费者/退役决策缺失 | metaos + omo architecture owner | G1/G2 | 运行调用图、权限边界、无独立派工负测、候选退役/迁移验证 |
| ECOS MOF / L0 | EXTEND | E5 仅涉及 observer 候选，不覆盖完整 MOF/L0；`UNPROVEN` | 编译输入、输出、PEP 消费者、schema/版本兼容与负测缺失 | ecos | G2 | 编译产物 digest、真实 consumer/API 及缺 invariant/错版本拒绝回执 |
| model-driven 生命周期 | EXTEND | 当前索引无具体生命周期能力证据；`UNPROVEN` | 是否形成平行 ontology/runtime、实际生成对象及消费者未核 | model-driven | G1/G2 | 生成路径、生命周期 owner、schema消费者、无第五 ontology 的审计 |
| Event Ledger | EXTEND | E4 提及 durable outbox 未完成边界；实际权威/恢复完整性未证；`PARTIAL` | 锚定、唯一事件 writer、消费者、重放/损坏恢复需核 | OMO Broker | G2/G3 | Ledger schema/anchor/consumer 清单，损坏/重放/恢复验证及唯一 writer 证明 |
| Control Capsule | BUILD-IN-PLACE | E4/E5 有候选工作与 observer 验证，不证明端到端受信编译；`PARTIAL` | omission/freshness/effect graph、生产签名及运行消费者未证 | omo + ecos | G2/G3 | 精确 schema/编译器摘要、stale/omission/scope-drift 负测、真实 Capsule replay |
| Coverage Receipt | BUILD-IN-PLACE | E4/E5 有部分候选 evidence；跨执行点绑定和独立验证未证；`PARTIAL` | action/PEP/runtime/identity/Outcome 绑定、伪造防护缺失 | OMO evidence contract | G2/G3 | effect 前后可重算 receipt；缺失/伪造/篡改/timeout 均不能报 PASS |
| PDP/PEP | EXTEND | E2 有路由/auth 清单但候选源码和运行差异；`PARTIAL` | 全部 effect 点的 pre-effect 覆盖和独立边界需核 | OMO policy + 各 effect PEP | G2/G3 | 100% effect inventory 对应运行 PEP；未映射 API 自动拒绝；信任域审计 |
| Mutation Gateway | EXTEND | E2 盘点部分写入口；未证明 shell/tool/external effect 统一；`PARTIAL` | adapter、shell、外部 API 的能力封装/补偿/审计缺口未知 | OMO/C2G brokers | G2/G3 | 全 effect route inventory、旁路扫描、越权/重放/补偿演练 |
| Harness DAG | EXTEND | E5 有候选独立 review；不证明整体组合语义；`PARTIAL` | gate precedence、失败状态和禁止第二 OS 的执行证据待补 | OMO admission/validation owner | G2/G4 | DAG 节点/输入/输出 owner 清单；critical failure 注入使整体不绿 |
| 孤立/重复 Harness 脚本 | RETIRE | E3 说明有 route/component inventory，但未列出脚本消费者/处置全表；`UNPROVEN` | 不能凭标签删除；需覆盖映射、所有 consumer、迁移/replay | Harness owner + 每个 consumer owner | G1/W0 | 每个候选脚本的 consumer/ref 搜索、替代入口、迁移回放与退役记录 |
| P74 silence detection | EXTEND | 当前索引没有 P74 当前运行证据；`UNPROVEN` | silence 观测范围、自身健康、误报漏报、组合健康优先级待核 | Workflow Mesh observer owner | G1/G3 | 输入/盲区/自健康测试；observer 停止时总体 UNKNOWN/HALT 的故障注入 |
| Rule lifecycle | EXTEND | 当前索引无规则七段生命周期完整运行证据；`UNPROVEN` | compile/enforce/effectiveness/retirement 的消费和审计缺失 | governance registry owner | G2/G4 | required rule 七段状态及消费回执；stale/零 consumer/退役负测 |
| runtime / sandbox | EXTEND | E1 有运行服务快照但未证明 executor sandbox/attestation；`PARTIAL` | Capsule admission、code/config digest 与补偿边界未知 | runtime | G2/G3 | 实际执行身份、sandbox profile、digest mismatch 阻断与恢复演练 |
| omlxc compute | EXTEND | E1–E7 无本能力运行/费用 receipt；`UNPROVEN` | capability budget、machine identity、成本与回收/退役证据待核 | runtime/omlxc | G1/G4 | 机器身份、预算阻断、资源事件与 Episode/outcome 成本归因 |
| AetherForge | EXTEND | 当前索引无 egress/cost/fallback 运行证明；`UNPROVEN` | task policy、隐私/成本 receipt、fallback 和 provider 替换缺口待核 | AetherForge | G1/G4 | provider 路由 receipt、越权出站拒绝、成本/模型替换回放 |
| Knowledge/KOS/GBrain/MOS | EXTEND | 当前索引未逐项核实来源/撤销/decay；`UNPROVEN` | 知识来源、冲突、衰减、撤销及 Episode 绑定需核 | knowledge composite owner | G1/G4 | source provenance、撤销和过期负测、真实 Episode 引用/回放 |
| Scene Card/Journey | EXTEND | E3 有页面/组件能力审计，不证明真实 Outcome 晋升；`PARTIAL` | Scene/Journey contract、真实样本/晋升门和消费者未逐条核查 | Scene owner + cockpit | G1/G3/G4 | 合同与运行 owner、至少一个非合成样本端到端、E4 晋升及反例 |
| Outcome recorder | EXTEND | E4 有候选 Work Case；缺独立真实 human verdict/归因；`PARTIAL` | outcome 与 verdict 独立 writer、因果链和业务消费证据缺 | OMO/Cockpit outcome plane | G3/G4 | 真实 E4 Outcome、独立 HumanVerdict、来源/消费人/归因/成本 receipt |
| Observability | EXTEND | E1 提供页面/API/source age 观察；observer self-health 和组合语义未全；`PARTIAL` | 采集失败、陈旧源、observer 自身失明时状态语义待验证 | observability + OMO projection | G1/G3/G4 | source age/identity 与 raw source 下钻；observer kill/stale 负测保持 UNKNOWN |
| resident heartbeat | EXTEND | E1 的健康/服务可达快照仅证明 liveness 子集；`PARTIAL` | heartbeat 不等于 consume/effectiveness；缺消费与结果 SLO | resident owner + deterministic observer | G1/G4 | PID 活但无消费、stale digest、队列阻塞时失败信号与恢复证据 |
| resident monitor | EXTEND | E1/E5 不证明 desired/observed reconcile 合同；`UNPROVEN` | 对账幂等性、漂移/重复/死信处理及超 scope 边界未知 | resident monitor owner | G2/G4 | desired/observed 差异注入、幂等 reconcile、超权限仅生成 incident |
| resident sediment | EXTEND | 当前索引无有效产出/消费率证据；`UNPROVEN` | 低效、重复、零处理的停止/退役阈值缺 | resident sediment owner | G1/G4 | 输入到有效沉淀/复用/Outcome 的抽样链；零消费限额和退役 receipt |
| resident decision | EXTEND | E4 候选决策授权仅局部；`PARTIAL` | 按需启动、限权、独立评测及提案/决策真值界限未全 | resident decision owner + OMO | G2/G4 | 有界输入/输出 contract、超 scope 拒绝、提案与权威决定分离回放 |
| resident execute | EXTEND | E4 有 Agent 默认拒绝候选；未证运行时只消费已授权 WorkPacket；`PARTIAL` | WorkPacket binding、PEP 和运行身份未在真实副作用闭合 | resident execute owner + PEP | G2/G3 | 无包/过期/撤销包拒绝；合法包效应与 Receipt 可追溯 |
| 进程代码身份 | BUILD-IN-PLACE | E5 提及 source-only plist 和 live recovery 未完成；`PARTIAL` | 运行代码与磁盘/投影摘要绑定及重启后证明仍缺 | runtime/observability | G2/G3 | 运行 PID→executable→code/config digest 的独立读证；错摘要 fail closed |
| 组合健康 | BUILD-IN-PLACE | E1 有 STALE/UNKNOWN 实例；E5 有候选 hardened observer；不能证明单调合成；`PARTIAL` | critical precedence、源年龄、lease 与 payload freshness 一致性未完全验证 | OMO projection + Cockpit | G1/G3 | source-by-source freshness；故障注入证 HALT/UNKNOWN 压制局部绿；完整页面/API E2E |
| 冷启动替换评测 | BUILD-IN-PLACE | E4/E5 未证明无历史上下文替换；`UNPROVEN` | packet 完整性、最小权限、成功/拒绝/停止标准缺 | Harness replay owner | G4/G5 | 随机 Agent 替换、空会话冷启动、可完成或安全停止、对象/权限稳定回执 |
| 已归档 mesh-router 等旧 owner | RETIRE | E1–E7 不含当前 registry/consumer 直接证据；`UNPROVEN` | archived 标记不能替代所有 consumer/ref 检查和历史兼容策略 | registry owner + 遗留 consumer owners | W0/G1 | registry 状态、依赖/consumer 全图；禁止新引用；兼容解析和退役复核 |
| family-hub 当前扩张 | RETIRE / paused | 当前索引无此场景的价值/consumer 样本；`UNPROVEN` | paused 是否生效、边界是否仍被引用、未来解锁门需验证 | family-hub owner；Portfolio owner | W0/G1 | 当前状态/服务/入口核查、引用清单；无价值样本时无扩张授权 |

#### BP §20 项目边界映射

| 原文项目/表面 | 目标职责 | 允许扩展 | 明确禁止 | 当前证据 / 状态与缺口 | 目标 Owner | Gate 与验收证据 |
|---|---|---|---|---|---|---|
| l4-kernel | P-L4 自我、角色、空间、长期身份 | Constitution/Role 查询和版本投影 | 调度任务；另一份运行真值 | 未有项目级运行/消费者图；`UNPROVEN` | l4-kernel | G1：身份/角色读写 API、consumer、与运行状态隔离证据 |
| cockpit | P-L3 单一人类入口 | Decision Inbox、Portfolio、Outcome、Recovery UX | 复制 OMO 状态机/策略引擎 | E1/E3 证明页面及路由，但 unified journey/stale 及 parity 缺口未闭；`PARTIAL` | cockpit | G1/G3/G4：关键旅程 E2E、唯一入口/owner 图、无策略复制负测 |
| cockpit-ui | Cockpit 表现层 | 可视化、渐进披露、控制反馈 | 独立后端真值和入口 | E3 覆盖组件/路由审计，不足以证明全部 UI 到 API 的权限/行为闭环；`PARTIAL` | cockpit-ui / cockpit | G1/G3：页面→API→权威追踪矩阵、无后端权威/入口副本测试 |
| agora | I0 BOS/MCP 路由织层 | Capsule/receipt 透传、route health | 授权决策、Workflow ownership | 当前索引无路由与 authority 隔离 runtime 证据；`UNPROVEN` | agora | G1/G2：路由调用图、纯透传验证、越权审批/派工拒绝 |
| omo | P-L2 治理内核、唯一 S slot、事件和 broker | Capsule、Receipt、组合健康、reconciler 合同 | 业务全能 god module | E4/E5 为局部候选；唯一 dispatcher/全量消费者及组合健康未证；`PARTIAL` | omo | G1/G2/G3/G4：运行调度链/唯一 writer 图、跨模块契约和故障 replay |
| metaos | 决策、免疫、规划后端 | PDP 候选、风险/策略推理 | 第二 dispatcher、第二 inbox | 现有证据未证明部署调用图/禁止边界；`UNPROVEN` | metaos + omo architecture | G1/G2：权限/调用图、无派工/入口副本负测 |
| knowledge | 知识/记忆/检索复合体 | 来源、冲突、衰减、Episode views | 将模型推断写成事件真值 | 当前索引未逐项验证来源与撤销合同；`UNPROVEN` | knowledge | G1/G4：provenance/decay/revocation 测试及推断不写事件真值证明 |
| ecos | P-L0 protocol/MOF/L0 constraints | Capsule/Receipt/Policy schema 与编译器 | 新 runtime、业务状态存储 | E5 局部 observer 不足以代表 ECOS 能力；`UNPROVEN` | ecos | G1/G2：编译器/consumer 图、无运行态写入负测、版本兼容回放 |
| model-driven | M0 生命周期框架 | rule/object lifecycle 生成与验证 | 第五 ontology、第二元体系 | 无当前生成/consumer 证据；`UNPROVEN` | model-driven | G1/G2：所有输出 schema/owner/消费者清单、与唯一 ontology/Meta 关系验证 |
| runtime | P-L1 sandbox/scheduler/execution | effect admission、attestation、compensation | 决定 Principal 目标和价值 | E1 只证明服务状态，不证明运行控制合同；`PARTIAL` | runtime | G2/G3：执行路径、attestation、compensation 证据；尝试写目标/价值被拒 |
| omlxc | 本地算力和物理放置 | machine identity、resource receipt、retirement | 绕过 AetherForge/OMO 语义调度 | 无当前成本/route/runtime 证据；`UNPROVEN` | runtime/omlxc | G1/G4：route/identity/cost receipt、绕过语义调度负测 |
| aetherforge | 模型推理网关 | 隐私、成本、fallback、model receipt | 直接修改 governed state | 无本地验证的完整运行路径/成本证明；`UNPROVEN` | AetherForge | G1/G4：task route/egress/cost/fallback receipts；state mutation 拒绝 |
| bus-foundation | data/event/control 传输 | outbox transport、schema observation | 将 Bus 当 Ledger 或 dispatcher | 当前索引无传输与权威边界证据；`UNPROVEN` | bus-foundation + OMO | G1/G2：topic/schema/consumer 图、重放与不持有 Ledger/dispatch authority 证明 |
| observability | telemetry 和 trace | observer self-health、coverage view | 以日志替代 Evidence/Outcome | E1 有观察实例，self-health/覆盖率完整性未证；`PARTIAL` | observability | G1/G4：缺失/伪造日志不能当 evidence；observer 自身失效演练 |
| toolbox | 外部工具和 adapter 入口 | 统一 capability envelope/PEP | 未注册广义 shell 权限 | E2 有部分写 API inventory；不能证明所有工具全覆盖；`PARTIAL` | toolbox + OMO/PEP | G1/G3：工具/effect inventory 与注册表 100% 对照；未注册/广义 shell 拒绝 |
| family-hub | 未来家庭递归扩展 | 保持 paused，保留边界验证 | 当前阶段扩建产品和共享主权 | 无 paused 生效/引用核查与价值样本；`UNPROVEN` | family-hub + Portfolio | W0/G1：停用态/消费者核查、没有价值和 authority 证据则阻断扩建 |
| Documents | 人类长期纲领和审议材料 | Constitution/whitepaper/blueprint/roadmap | 实时健康、Run 状态、凭证 | 接受包证明版本/文档存在，不足以证明文档外动态投影无重复；`PARTIAL` | Documents owner + canonical state owners | G0/G1：文档 authority/hash 清单，扫描动态真值/凭证副本并验证唯一来源 |

#### BP §21 红队十项审查

状态针对“设计响应是否已在当前实现/运行中验证”；蓝图原文明确总体运行有效性尚未证明，因此下列各项当前均为 `UNPROVEN`，除非表内列出范围有限的局部证据。剩余风险必须保留为显式字段，不以关闭 finding 代替风险判断。

| # / 攻击面 | 原文设计响应 | 当前证据 / 状态 | 必做攻击与验收 | 修复 Owner / 独立 Auditor | Gate | 剩余风险记录 |
|---|---|---|---|---|---|---|
| 1 复杂度债：连续性机制变成又一套平台 | 不新建系统；七段链映射现有 owner；subtraction gate | E3 是局部 route disposition，不是全架构新增表面积盘点；`UNPROVEN` | 提交前后组件/API/服务/owner/consumer 差异；新增能力无 owner 或无消费者必须拒绝/退役；核对是否产生新 dispatcher/SSOT | Architecture owner / 独立 Architecture Auditor | G1/G2 | 现有 owner 内部仍可能膨胀；记录未收敛消费者及 Principal 处置 |
| 2 实现幻觉：文档完整被误认能力存在 | EXISTS/EXTEND/BUILD-IN-PLACE/RETIRE；Engineering/Operational/Value 分门 | E1/E5 反而显示 stale 与 candidate/runtime 差异，但不构成全项测试；`PARTIAL` | 每项抽查真实入口、测试、运行和 Outcome；文档/测试/健康端点单独不得升状态；随机挑战状态证据 | 每能力 owner / 独立 Verifier | G1→各 Gate | 报告夸大动态事实的风险；记录抽样覆盖范围与未抽样项 |
| 3 冷启动：新 Agent 缺上下文 | WorkPacket + Capsule + Receipt + cold-start replacement test | E4/E5 未证明真实无历史接管；`UNPROVEN` | 随机换 Agent、清空聊天上下文，仅提供正式对象；验证安全完成或停止、未决项与权限不变 | OMO packet owner / 独立 Verifier | G4/G5 | Capsule 仍可能遗漏语义上下文；保留接管失败样本 |
| 4 信任启动：Agent/host/process 身份伪造 | 短期 capability、identity、digest attestation、remote required check | E2 是 auth 范围盘点；E5 未完成 live recovery/source proof；`PARTIAL` | 身份/host/code digest 错配、撤销 token、重复 token 对抗；确认 effect 前 fail closed 且独立记录 | Identity/runtime owner / 安全 Auditor | G2/G3 | 主机 root 仍属高信任域；登记信任根、密钥轮换和离线攻击残余 |
| 5 SPOF：Agora/OMO/Ledger/PEP/cloud model 宕机 | 本地权威、READONLY/HALT、outbox/replay、预定义 fallback | E1 是一次服务/接口快照，不是多依赖故障演练；`UNPROVEN` | 对每个单点逐一失效注入；验证 READONLY/HALT、数据恢复、幂等副作用和 RTO/RPO | 对应项目 owner / 独立 SRE Auditor | G3/G4/G7 | 单机硬件灾难需离线备份；记录恢复目标/实际差距 |
| 6 版本迁移破坏重放 | version/digest/upcaster/successor/双读影子 | 当前索引无历史 Episode 全量 replay/迁移证据；`UNPROVEN` | schema/policy/Capsule 新旧版本双读/影子及历史事件重放；差异不明则停止晋级 | ECOS/schema owner / 独立 Verifier | G2/G4 | 长期 migration cost 和旧 consumer；保留版本覆盖周期/未迁移比例 |
| 7 Agent/模型耦合 | 角色合同、结构化 schema、AetherForge route、替换评测 | 当前索引未验证至少两类 provider/能力档位；`UNPROVEN` | 迁移 provider/模型运行相同任务族；比较合规、质量、负担、成本及安全拒绝 | AetherForge + OMO role owner / 独立评测者 | G4/G5 | 高难任务可能仍有质量差异；标示适用范围和 fallback 成本 |
| 8 经济失控 | 预算、WIP、exception-only escalation、cost/outcome | E6 有预算/资源计划，不证明真实成本归因；`UNPROVEN` | 从原始资源/人工时间事件复算每个 Outcome 治理成本；预算/WIP 超限应阻断或降级 | Portfolio/Finance owner / 独立 evaluator | G1/G4 | 价值归因延迟/主观性；记录区间、不确定性及未计成本 |
| 9 测试自洽 | 组合健康 critical precedence、独立 observer、negative/chaos test | E5 有候选 observer 验证，未证明跨信任域整体故障检测；`PARTIAL` | missing lock、checker timeout、digest mismatch、observer failure 注入，整体必须非绿；独立源复算 | OMO health owner / 不同信任域 Auditor | G2/G4 | 共信任域可能共同失败；登记独立性边界与无法注入的场景 |
| 10 防腐体系自身腐化 | rule lifecycle/self-health/三道防线/独立 replay/retirement | E5 source-only/live recovery 未闭；无 observer kill/zero-consumer 证据；`UNPROVEN` | kill observer、stale rule、zero-consumer、duplicate loop；自身健康丢失须 UNKNOWN/HALT，并触发退役/恢复流程 | governance/resident owner / independent Auditor | G4/G7 | 最终依赖 Principal 周期复核；登记审查周期、漏检风险和 owner |

#### BP §22 验收与完成定义

| 原文锚点 / 可验收条件 | 当前证据 / 状态 | 必须补齐的缺口 | 目标 Owner | Gate | 通过所需证据 |
|---|---|---|---|---|---|
| §22.1 Engineering：合同正确实现 | E4/E5 有局部候选测试；不是全架构/消费者/负测证明；`PARTIAL` | 每个合同补 code/schema/test/diff/consumer/negative test 精确链接 | 对应 capability owner；独立 Verifier | 各 Gate | 受审版本源码摘要、完整 consumer 清单、正负测、独立复核 receipt |
| §22.1 Operational：真实环境稳定运行 | E1 显示实时故障/STALE 情况，E5 未完成 live recovery；`PARTIAL` | fresh runtime identity、SLO、恢复/replay、observer health 及连续窗口 | Ops/runtime owner；独立 SRE | G3/G4/G7 | 新鲜运行身份、观测窗、故障/恢复/replay 事件及 SLO 复算 |
| §22.1 Value：真实结果有归因 | E4 是候选验证材料；无已核验真实 business Outcome/HumanVerdict 全链；`UNPROVEN` | 非测试 Outcome、人工裁决、成本与负担及因果链 | Scene/business owner；Principal | G3/G4/G5 | 真实 Signal→Episode→Outcome→HumanVerdict/消费证明及成本/负担核算 |
| §22.1 三门不可互代 / 总体 done | 计划文档说明三门分离；当前无完整三门证据包；`UNPROVEN` | 三门精确版本、owner、来源、日期和摘要绑定；value-exempt 项有理由 | Portfolio owner；独立 Verifier | 每个 phase exit | 同一 scope 的三张独立 gate receipt；缺一则总体 `PARTIAL/UNPROVEN` |
| §22.2 连续性 1：不变量有 authority/compiler/PEP/observer/recovery/retirement | E2/E5 仅局部认证/observer；`PARTIAL` | 每条关键不变量逐段绑定实施/恢复/退役 evidence | Policy/ECOS/PEP owners | G2/G4 | 不变量逐条矩阵、运行控制 receipt、失败/恢复/退役演练 |
| §22.2 连续性 2：effectful WorkPacket 有 fresh Capsule | E4 有候选绑定测试；全量 effectful 覆盖和 freshness 运行证据缺；`PARTIAL` | 全量清单、签名/新鲜度和未覆盖自动拒绝 | OMO/ECOS | G2/G3 | effectful WorkPacket 100% 样本清单与 fresh Capsule digest、过期拒绝 receipt |
| §22.2 连续性 3：effectful Action 有 CoverageReceipt | E4/E5 候选 evidence；全执行点覆盖未证；`PARTIAL` | action/PEP/runtime/identity 统一绑定及 receipt 完整率 | OMO evidence owner | G2/G3 | 对照 effect inventory 的 100% coverage receipt；缺失自动 `UNPROVABLE` |
| §22.2 连续性 4：五类关键故障不会投影 Overall HEALTHY | E1 已观测 stale/unknown；E5 候选 observer；完整故障集合未测；`PARTIAL` | missing lock/lease、stale Capsule、checker timeout、observer failure、digest mismatch 各自注入 | OMO health evaluator | G3/G4 | 每项注入记录 + 组合状态判定；不得由其他绿项抵消 |
| §22.2 连续性 5：新 Agent 无历史聊天可接管 | 无直接冷启动接管证据；`UNPROVEN` | 全新 Agent、无聊天依赖、权限不扩大的 replay | OMO handoff owner | G4/G5 | 独立见证冷启动任务；安全完成/停止、authority 和对象身份不变 |
| §22.2 连续性 6：Resident 有 input/consume/result/SLO/DLQ/self-health | E1 仅运行状态快照，不证明 resident 功能；`UNPROVEN` | 每个参与 overall 的 resident 指标/队列/DLQ/self-health；无 SLO 则隔离 | Resident owner；observer owner | G4 | 每个 resident 原始输入到结果的样本、SLO 复算、DLQ/自健康演练 |
| §22.2 连续性 7：关键 projection 可由 Ledger 重建 | E4 提示 outbox 未完成边界；无关键 projection 重建 proof；`UNPROVEN` | projection 清单、Ledger event 完整性、冷重建一致性 | OMO Ledger/projection owner | G3/G4 | 从固定 Ledger 摘要空库重建，逐字段与源事件对账及差异 receipt |
| §22.2 连续性 8：关键恢复路径至少一次演练 | E1/E5 显示运行故障和 candidate 尚未 live recovery；`UNPROVEN` | 关键路径目录、恢复基线及一次真实或高保真演练 | Runtime/Ops owner | G4/G7 | 演练计划、执行日志、RTO/RPO、replay/副作用校验和独立签收 |
| §22.2 连续性 9：回归率与治理成本在连续窗口下降 | 无同口径连续基线；`UNPROVEN` | 定义分子/分母、窗口、成本归因和 source owner | Portfolio/evaluator | G4/G5 | 独立从原始事件重算的连续窗趋势、负担/质量 guardrail |
| §22.2 连续性 10：无第二 dispatcher/Ledger/Portfolio 真值 | E3 仅部分入口清单；全仓/运行 authority 图缺；`UNPROVEN` | 代码、服务、consumer、registry、运行请求全图及重复 writer 扫描 | Architecture owner；独立 Auditor | G1/G2/G4 | 全仓与运行面唯一 authority/writer 图、重复真值负测与迁移处置 |
| §22.3 Golden Slice 1：真实信号与人工裁决连续时间窗 | 无已核验业务时间窗；`UNPROVEN` | 样本真实性、裁决人和连续窗口基线 | Scene owner；业务验收人 | G3/G4 | 非合成源样本、独立人工 adjudication、连续窗原始事件 |
| §22.3 Golden Slice 2：必要对象可从 Signal 关联至 Outcome | E4 候选 workcase；完整真实对象链未证；`PARTIAL` | 所有必要对象 ID、关系和每段 owner/replay | OMO/Scene owner | G3 | 同一 Episode 全链关系查询、独立 replay、断链负测 |
| §22.3 Golden Slice 3：effectful 路径无未授权绕过 | E2/E4 有局部 auth 候选；全 effect 边界未证；`PARTIAL` | 旁路/脚本/外部工具/运行时全量覆盖和 fail-closed | PEP owners；安全 Auditor | G3 | effect inventory 与 PEP 100% 对照、绕过尝试被阻断的运行记录 |
| §22.3 Golden Slice 4：可降级、撤销、恢复、重放 | E1/E5 暴露 stale/503 和未完成 live recovery；`UNPROVEN` | 真实降级、撤销、恢复和无重复副作用证据 | Ops/runtime/OMO | G3/G4 | 故障注入到恢复的全链 receipt、撤销即时生效、replay 等价验证 |
| §22.3 Golden Slice 5：接受率/修改率/遗漏减少/节时/干扰可读 | 无统一可信人类负担基线；`UNPROVEN` | 业务验收者、量表、采样和原始数据口径 | Scene owner；业务验收人 | W0→G4 | W0 baseline 和连续窗口复算；缺测明示 UNMEASURED |
| §22.3 Golden Slice 6：测试/合成/未核验样本不计真实价值 | E1–E7 的状态原则有声明；未见指标计算器反操纵验证；`PARTIAL` | 生产 evaluator 对来源类别的过滤和复算 | North Star evaluator | G1/G4 | 合成/测试/未核验样本注入后真实价值分子不变的测试及原始事件重算 |
| §22.3 Golden Slice 7：不同 Agent/模型接管验证 | 未见替换运行证据；`UNPROVEN` | 至少一次可审计 provider/Agent 替换及质量/权限对照 | OMO/AetherForge；独立 evaluator | G4/G5 | 冷启动接管 receipt、同任务族对照、无权扩大和负迁移记录 |
| §22.3 任一不满足保持 evaluating/NOT_PROVEN | 本矩阵明示证据边界；当前 dashboard/runtime 存在 stale/503 事实；`PARTIAL` | 实际 evaluator 的 fail-closed 状态派生、不能手工升级完成 | Overall evaluator；Portfolio | 所有 Gate | 缺任一 Golden Slice 条件自动 `evaluating/NOT_PROVEN` 的接口/运行负测 |
| §22.4 愿景 1：至少两个真实领域复用同一主权/主链 | 当前无两个领域真实闭环证据；`UNPROVEN` | 第二领域真实 owner、Outcome 和相同 canonical objects | Portfolio + 两个 Scene owners | G6 | 两个不同领域 E4/E5 replay，唯一 Principal/Episode/Capsule/PEP/Outcome authority |
| §22.4 愿景 2：连续窗口稳定创造被接受、可归因结果 | 无连续真实窗口；`UNPROVEN` | qualifying outcome 口径、窗口、归因与验收 | Portfolio/evaluator；Principal | G8 | 原始事件独立重算连续窗口、Principal 接受及对照基线 |
| §22.4 愿景 3：人类认知和执行负担下降 | 无一致负担前后基线；`UNPROVEN` | 人工等待/修改/审查/遗漏/干扰口径和因果验证 | Scene/business owner | G8 | W0 与后续窗口可比数据、质量安全不退化证明 |
| §22.4 愿景 4：Agent/model/host/capability 可替换且制度真值保留 | 单项候选测试不证明全链可替换；`UNPROVEN` | 替换矩阵、迁移/恢复/身份 authority 证据 | OMO/runtime/AetherForge | G5/G8 | 至少跨 Agent/model/host/capability 的替换回放及真值一致性 |
| §22.4 愿景 5：安全/隐私/恢复/成本/注意力/体验均受护栏 | E1/E2 显示局部运行/权限事实，不是护栏全向量；`PARTIAL` | 每项护栏的 owner、阈值、分母、源、回滚策略 | Portfolio + domain owners | G4/G8 | 不可抵消 guardrail 原始数据、单项越界压制总体通过及恢复记录 |
| §22.4 愿景 6：进化 replay→shadow→canary→adjudication，可拒绝/退役 | 当前索引无学习晋升/退役连续链；`UNPROVEN` | 各阶段 authority、版本、rollback 与退役消费者验证 | Evolution/MOS owner；Principal | G5/G7/G8 | 候选从 replay 到 adjudication 的版本链、拒绝/回滚/退役演练 |
| §22.4 愿景 7：Principal 可理解/暂停/撤销/导出/关停 | 接受回执存在，不证明运行接口；`PARTIAL` | 各权利入口、效果、恢复/导出完整性和越权防护 | Principal；Cockpit/OMO authority owners | G3/G8 | Principal 实测五项操作和审计记录；Agent/管理员不能代行 |
| §22.4 愿景 8：表面积/治理成本不随能力无界扩张 | E3 有 route disposition 局部审计；无趋势/成本基线；`UNPROVEN` | 面积/owner/consumer/成本的连续指标和 subtraction 执行 | Architecture + Portfolio | G1/G8 | 组件/API/角色/规则数量与单位 Outcome 成本趋势、退役/拒建记录 |

#### BP §23 架构门、路线衔接与执行硬边界

下表的 Gate 内容锚定蓝图 §23 主依赖图；W0–W6 的阶段合同、输入/输出和验收样例锚定路线图 v2.1 §§5–12、§20.4 及附录 A。不得把架构 Gate 编号当成 BET/Ledger 状态。

| 原文锚点 / 条件 | 对应 W 阶段 / Gate | 当前证据 / 状态 | 缺口 / 目标 Owner | 可验收产物与通过条件 |
|---|---|---|---|---|
| G0 纲领/权威/术语接受 | W0 前置 | 接受信封精确摘要已存在；Workspace binding 和实施授权明确未包含；`PARTIAL` | 缺 canonical term、当前 workspace/source bindings；Principal + 文档/architecture owner | 接受摘要/文档关系精确绑定；无误用接受信封作为部署或 BET 授权 |
| G1 当前真值审计 + Golden Slice 选择与人工 baseline | W0.A/B/C | E1–E7 为局部快照/候选审计，非完整 source map 和 3 个真实样本；`PARTIAL` | 缺 owner/authority 全图、≥3 非合成样本、人工 baseline；Product/Scene owner | source→owner 图、3 个可回读样本、耗时/错误/结果 baseline、未知项 UNMEASURED |
| G2 最小不变量 + Capsule/Receipt v0 | W0.B→W1.B | E4/E5 有候选；不能证明 production contracts 或 independent trust boundary；`PARTIAL` | 缺 required invariant、可信域、compiler/validator 绑定；OMO/ECOS/PEP owner | 最小合同和摘要、缺项/过期/越权负测、Receipt v0 独立 replay |
| G3 首个真实 Episode + pre-effect PEP + 组合健康 | W1 汇合 | E1 显示当前 dashboard stale/503 问题，E4 是候选 workcase；无已核验真实 Episode；`UNPROVEN` | 缺同一真实动作中的 Outcome/HumanVerdict、PEP effect 和组合健康；Scene/OMO/Principal | 一个非合成 E4 Episode；未授权 effect 被 effect 前拒绝；独立 Coverage Receipt；critical health precedence |
| G4 Trustworthy Golden Slice 连续窗口 + Runtime/Resident SLO | W2 | 当前无连续窗口；E1 stale/503 与 E5 live recovery 未完成形成反证；`UNPROVEN` | 缺路线图要求的连续窗口、恢复/replay、resident SLO；Ops/Scene owner | W2 五个汇合条件连续窗口都 PASS；fresh runtime identity、Recovery 和 SLO 原始样本 |
| G5 学习效果闭环 | W3 | 无独立 baseline/shadow/challenger/回滚证据；`UNPROVEN` | 缺稳定任务族、质量/负担/安全对照和可撤销候选；Evolution owner | 固定基线 replay/shadow 比较、净改善/无负迁移、撤销再测 receipt |
| G6 第二场景复用 | W4 | 当前无第二场景真实 E4/E5 证据；`UNPROVEN` | 缺第二场景 owner、合同、隔离和卸载测试；Portfolio/Scene owners | 第二场景端到端 Outcome；Restricted 数据拒绝；同一内核，无第二 dispatcher/ledger/入口 |
| G7 有限自治与可生存进化 | W5 | 无全新 Agent 接管、kill/demotion、故障恢复与长期连续性合证；`UNPROVEN` | 缺 supervised autonomy profile、即时降级、resident SLO 和演练；OMO/runtime/Principal | 空会话接管、摘要错配拒绝、故障/kill/demotion、恢复且无重复 effect |
| G8 LifeOS 长期愿景验证 | W6 | 未达多场景、12 周 E5、第二环境和 Principal final adjudication；`UNPROVEN` | 缺 required KR/guardrail/长期持有性原始证据；Principal + Portfolio | 独立重算连续 12 周、至少两场景/第二环境、完整 guardrail、Principal 明确裁决 |
| 路线图 W0.A 真实 Golden Slice 样本与人工 baseline | G1；W0 exit | E1–E7 无 3 个可回溯真实业务样本及统一人工基线；`UNPROVEN` | Scene/Product owner；须保留拒绝/no-action 与人工耗时、错误、可接受结果 | ≥3 个非合成样本原始来源、样本裁决、人工链路/耗时/错误 baseline、独立复算 receipt |
| 路线图 W0.B 宪法不变量/Authority Map/Control Level/trust domain/最小可信基 | G1→G2；W0 exit | 计划和矩阵存在候选映射，未证明来源完整或 executor 不可写边界；`PARTIAL` | Architecture/Security owner；每条不变量补 owner/威胁/执行点/失效语义 | 全量 authority/trust-domain map；至少一个控制或验收面由 executor 权限域外强制；独立审阅摘要 |
| 路线图 W0.C EXISTS/EXTEND/BUILD-IN-PLACE/RETIRE 复用矩阵 | G1；W0 exit | 本矩阵复用处置表已建立，但当前 consumer/runtime 证据逐项不足；`PARTIAL` | Architecture + project owners；禁止新顶级系统，BUILD-IN-PLACE 必须点名既有 owner | 每项能力及项目映射到当前 owner/consumer/依赖/迁移/退役证据；无 owner/无 consumer 标记 UNPROVEN |
| 路线图 W1.A 统一入口上的真实 Episode、输出/审阅/修订/结果 | G3；W1 exit | E4 是候选 Work Case 材料，非已核业务 Outcome/HumanVerdict；`UNPROVEN` | Scene owner + 业务验收人 | 同一真实 Episode 的入口事件、修改差异、Outcome、独立 HumanVerdict 和人工负担数据 |
| 路线图 W1.B Capsule/PEP/CoverageReceipt v0 双轨控制 | G2→G3；W1 exit | E4/E5 候选实现/验证；没有同一真实 Episode 的真实 effect receipt；`PARTIAL` | Workflow/Governance owner + PEP + 独立 Verifier | 正向/负向/过期/缺上下文测试；真实 E3 receipt；无 PEP effect 被拒；executor 改写控制/receipt 被 out-of-band 拒绝 |
| 路线图 W1.C 仅修复阻塞 A/B 的入口/身份/锁/运行/数据问题 | G3；W1 exit | 当前存在 reader 503 与 freshness 缺口〔E1〕，修复候选并不等于运行恢复；`PARTIAL` | Platform owner；Product owner 确认仅消除 A/B blocker | blocker 前后同一观测；无第二路径/第二服务；独立 verifier 确认原故障消失且无新增回归 |
| 路线图 W2 汇合：Useful + Authorized + Observable + Recoverable + Replaceable | G4；W2 exit | 当前投影 stale/UNKNOWN、Zhixing `/data.json` 503，且无连续真实 Episode 窗口；`UNPROVEN` | Product owner 对端到端负责；Runtime steward、Governance owner、Principal | 同一 Golden Slice 连续至少 4 周；五条件各自独立 receipt；关键链 resident 有 SLO 或明确隔离；失败恢复和新 Agent 替换通过 |
| 路线图 W3 学习候选 replay/shadow/challenger/人工 review/晋升或拒绝 | G5；W3 exit | 无固定任务族连续 baseline、candidate memory 对照和撤销证据；`UNPROVEN` | Learning steward + Scene owner + Principal 保留反馈权 | 至少连续 8 周相对 baseline 减少负担/错误、质量安全不退化；候选可撤销且版本因果可辨 |
| 路线图 W4 第二 Scene + DomainPack/adapter + 隔离与共享合同 | G6；W4 exit | 无第二真实 Scene 及 E4/E5 证据；`UNPROVEN` | 第二 Scene owner + Platform/DomainPack steward + Principal | 第二场景真实 E4/E5；Restricted 数据隔离；无第二 dispatcher/SSOT/记忆面；adapter 可卸载且核心不损坏 |
| 路线图 W5 风险分级自治、Resident、kill/demotion、Agent 更换与故障存活 | G7；W5 exit | 无新 Agent 冷启动、kill/demotion、backend 故障恢复和稳定 SLO 的联动证据；`UNPROVEN` | Autonomy/Policy owner + Independent Verifier + Runtime steward + Principal | 一个低风险能力 supervised 稳定；自治即时降级、凭证撤销、队列/Resident 恢复、无重复 effect；无自我批准 |
| 路线图 W6 多场景复利、第二环境、12 周愿景包和 Principal 裁决 | G8；W6 exit | 当前无 required KR 全 E5、第二环境或 Principal final adjudication；`UNPROVEN` | Principal + Portfolio/Scene owners + Independent assurance | 原始事件独立重算连续 12 周；第二环境真实 E3/E4；required KR 全 E5；年度 subtraction 和 Principal 明确裁决 |
| §23 Gate 通用合同：前置/产物/负测/通过/失败/回滚/继续授权 | G0–G8 每门 | 现有计划列出门名和部分验收，当前没有逐 Gate 全合同运行回执；`PARTIAL` | 每个 Gate 需分别填齐七项，且失败不自动推进；Gate owner + Verifier | Gate contract 卡含所有字段、正负测、回滚和精确继续授权摘要；字段缺失即 HOLD |
| §23 日期不得自动放行 | 所有 W 阶段 | 计划明确规定日期从 fresh baseline 后相对计算；无自动放行执行证据；`PARTIAL` | 检查 scheduler/dashboard/ledger 是否能按日期变状态；Portfolio + OMO owner | 超期注入仍停留当前 Gate/HOLD，须由授权 owner 和新鲜 evidence 显式通过 |
| §23.1-1 W0 同时做 Golden Slice baseline 与最小不变量压缩 | W0.A/B 并行，W0 exit join | 执行计划含 W0 分线草案，未证明真实样本和不变量均通过；`PARTIAL` | 缺两个工作流独立证据及汇合规则；Product/Architecture owners | W0.A/B/C 各自收据，W0 exit 只有 A/B/C 全过后可继续 |
| §23.1-2 Episode 与 Capsule/Receipt v0 并行，之后再扩大并行 | W1.A/B | 计划设计有 A/B 双轨；未证明同一真实 Episode join；`PARTIAL` | 缺同一动作/同一 Episode join key 与并行上限；Scene/OMO owner | 一个 Episode 关联 A/B 的真实 Outcome/PEP/Receipt；扩大并行需新的授权门 |
| §23.1-3 副作用不可绕过与 Golden Slice 实用性同一汇合门 | W1→G3 | 当前无满足两边的真实样例；`UNPROVEN` | 防止安全实现脱离真实价值，或实用样例绕过 PEP；Scene/PEP owners | 同一 Episode 同时验证业务可用 Outcome 与完整 pre-effect control |
| §23.1-4 先组合健康诚实，再依赖 Dashboard/resident | G3→G4 | E1 已证明当前投影 STALE/UNKNOWN、Zhixing data.json 503 的现实缺口；`PARTIAL` | 不可用静态页面/单 endpoint 健康替代 source freshness；dashboard/observer owner | source-by-source freshness 与组合故障演练通过后才可用 Dashboard/resident 作为自动判断依据 |
| §23.1-5 Resident 与真实 Episode 同期验证，不作大工程前置 | W1/W2 | 当前未有 resident input→consume→result 与同一 Episode 证据；`UNPROVEN` | 缺最小 SLO 和 resident 与场景同步验收；Scene/resident owner | resident 与真实 Episode 同步观察；无 SLO/无消费时隔离出 overall |
| §23.1-6 一个可信 Golden Slice 后再扩第二场景 | G4→G6 | 没有 G4 通过证据；`UNPROVEN` | 必须先有完整连续窗和恢复；Portfolio owner | 第二场景 admission 自动检查 G4 fresh PASS receipt，否则拒绝 |
| §23.1-7 Outcome 与负担改善成立后才提高自治 | G5→G7 | 无有效 Outcome/负担连续基线；`UNPROVEN` | 自治 profile 不得基于工程完成或自动化率；Principal/Portfolio | Outcome、负担、安全与成本全量护栏通过，随后由 Principal 明确提高权限 |
| §23.1-8 replay/rollback/retirement 完成后才允许自我进化 | G7/G8 | 当前无端到端 replay→rollback→retirement 证据；`UNPROVEN` | 缺进化对象、消费者、退役与恢复路径；Evolution owner/Principal | replay、rollback、旧消费者迁移及退役演练通过；无回滚路径则晋升拒绝 |
| §23.2 不批量 Ledger 写入 | 所有设计阶段 | 接受信封未授权 Ledger 写；本矩阵无 Ledger 写入；`PASS（范围内只读）` | 后续任何绑定仍需 operation-specific authority；Ledger owner | 只读检查记录；如计划转写，另行独立批准并核验 |
| §23.2 accepted design/spec 在绑定提案之前 | W0 binding | 有候选设计文档；尚无该子条款的独立接受/完整性 receipt；`PARTIAL` | 需确定 accepted spec hash/范围/Verifier；Principal + Product owner | 精确 spec 摘要、review receipt 和拒绝未接受版本绑定的负测 |
| §23.2 每个 BET 绑定上游 Gate、下游 Outcome、取消条件 | W0–W6 planning | E6 计划有部分映射；未逐 BET 验证，当前矩阵不写 BET；`UNPROVEN` | 每条 BET/任务后续登记前必须有三字段及 owner；Portfolio owner | 全 BET 逐项映射清单、断链/缺取消条件拒绝验证 |
| §23.2 每 Wave writer 上限由 Portfolio 明确 | W0–W2 总 writer ≤2；每个 authority surface 同时 writer =1 | 路线图有上限文字，无当前并行控制运行证据；`PARTIAL` | 未核当前并行状态/写面锁；Portfolio/OMO lease owner | accepted concurrency profile、超限并发注入被拒及审计事件 |
| §23.2 子仓优先、根指针最后 | repository integration | E6 计划声明策略；未逐次集成审查；`PARTIAL` | 缺当前代码交付路径/根指针 admission evidence；各 repo owner | integration trace 显示子仓验证后再更新根指针；顺序错则 admission fail |
| §23.2 runtime/host/external operation 有 operation-specific authority | 每项运行操作 | 接受信封明确不覆盖服务控制/外部副作用；E2 仅部分 action auth inventory；`PARTIAL` | 逐操作 authority scope、身份、期限、撤销和副作用审计未全；Principal/operation owner；PEP | 操作级授权摘要、越权/过期/撤销拒绝及真实副作用 receipt |
| §23.2 所有价值默认 NOT_PROVEN 直到真实结果门 | 全阶段 | 矩阵原则如此；North Star 真实业务事件 evaluator 尚未验证；`PARTIAL` | 报表、API、导出各处统一 fail-closed 及测试/合成过滤；Portfolio evaluator | 合成/PR/测试事件注入不提升价值状态；真实 Outcome/HumanVerdict 才可转 E4/E5 |
| §23.2 已在 main 正确实现时复用/放弃重复分支 | 每个实现任务 | E3 有旧路由处置材料，但未逐能力与当前 main 证明；`PARTIAL` | 写入前检查 main/current owner、覆盖、消费者、变更 diff；严禁回退自愈真值；Task owner + 独立 Verifier | 当前 main 与目标能力对照、无需新增/重复分支的证据，或批准的差异和回滚策略 |

页面/API 尚无对应产品入口的条款必须明确标注 `N/A`、给出权威观察位置和产品/架构复核人；不允许用“无页面需求”省略机制验收。每项退出门由独立 Verifier 复核并绑定精确源码、测试和运行证据摘要。

### 3.4 路线图源条款审计缺口（DCP-TRACE-01 未关闭）

当前 §3.2 对路线图只有四段聚合映射（§0–5、§6–12、§13–18、§19–24），不能证明每个条款已各自连接能力/API、owner、验收证据和退出门。下表把审计发现转为可追踪的未完成行；它们的状态表示“矩阵覆盖状态”，不表示对应产品功能实现状态。所有编号行在完成源条款 ID、consumer/API 和独立 verifier 绑定之前均不得判 PASS。

| 条款 ID | 路线图原文锚点 | 独立追踪的要求 | 当前追踪状态 / 必须补齐 |
|---|---|---|---|
| RM-DOC-01 | RM §0.1–0.3，行 53–89 | 文档拥有/不拥有边界、冻结术语、状态标记 | UNMAPPED；绑定相应 authority receipt 和证据等级解释 |
| RM-METRIC-01 | RM §1.2.1–1.4，行 115–151 | 三层同口径复算、十项不可抵消 guardrail、愿景证明公式 | UNMAPPED；每个指标补分子/分母、窗口、source、freshness、owner、anti-gaming 和复算 |
| RM-STRATEGY-01 | RM §3.1、§4.3，行 198–248 | 战略—战役—战术—战斗四层守恒；不能因“先治理”无限阻塞真实价值轨 | UNMAPPED；补一条价值轨与可信控制轨的依赖/汇合/停止决策 |
| RM-W0-01 | RM §6.1–6.4，行 301–348 | W0 完整 phase contract、waves、不做事项、现场真相补充门；5–10 工作日硬上限 | PARTIAL；分别映射目标/输入/输出/owner/writer cap/时间起算/证据/退出/kill/rollback/价值规则；三真实样本和人工 baseline 仍未提供 |
| RM-W1-01 | RM §7.1–7.3，行 351–385 | W1 phase contract、waves 与 Capsule 必须扩展 WorkPacket 的字段和失败约束 | PARTIAL；补时窗、唯一 scoped journey、E2/E3/E4、pre-effect PEP、Receipt、停止与回滚；字段缺失拒绝测试未绑定 |
| RM-W2-01 | RM §8.1–8.2，行 389–419 | useful、authorized、observable、recoverable、replaceable 五条件必须在同一 Episode 同时成立 | UNMAPPED；当前 Gate G4 汇总不能替代五个可单独拒绝、同 scope 的条件 receipt |
| RM-W3-01 | RM §9.1–9.2，行 423–451 | 连续 8 周学习证据；单环自动、双环提案、三环由 Principal 决策 | PARTIAL；补三层 authority/禁止组合/负测、基线、质量/安全不退化和 promotion 回执 |
| RM-W4-01 | RM §10.1–10.2，行 455–479 | 第二场景必须按频率、可逆性、裁决人、连接器、隐私边界排序，健康/家庭/高风险财务等受限 | PARTIAL；补逐项选择条件、拒绝条件、实际 Scene owner 与跨域隔离验收 |
| RM-W5-01 | RM §11.1–11.2，行 483–507 | 持久 Role/queue/lease/checkpoint/desired/SLO/escalation；Agent 实例可替换；heartbeat 不等于功能 | PARTIAL；补 resident input→consume→verified outcome、超 scope 拒绝、冷启动替换与真实运行 SLO |
| RM-W6-01 | RM §12.1–12.2，行 511–535 | W6 为候选验证而非开发终止；年度 Constitution review、季度 subtraction、角色可接管 | UNMAPPED；补持续治理 owner、日历起点、fail/延迟状态和 Principal review receipt |
| RM-MILESTONE-01 | RM §13–13.1，行 537–554 | 30 天、90 天、1 年、3 年里程碑与超期/缺测/guardrail/外部依赖降级语义 | UNMAPPED；补每窗起算、数据新鲜度、未测显示、延期/超期/重授权和非自动放行 |
| RM-OBJECT-01 | RM §14.1–14.3，行 558–686 | Portfolio→Campaign→BET→Spec→WorkPacket→Run→Evidence→Outcome→Verdict 链、各对象生命周期责任、proposal overlay 不占 canonical ID | UNMAPPED；逐对象补唯一 writer、消费者、完成条件、关系完整性和断链负测 |
| RM-BET-01 | RM §15.1–15.3，行 689–725 | BET 准入/非 BET 范围/Portfolio 守恒；ID、单 writer、child-first/root-last、失败处理、accepted binding、supersede、consumer/retire | PARTIAL；当前 §23.2 只覆盖部分原则，必须拆 15.3 各守恒条款并绑定回执 |
| RM-METRIC-02 | RM §16.1–16.6，行 728–819 | baseline 校准、拟议目标属性、制度连续性、effect taxonomy、root_episode 去重和 materiality | UNMAPPED；逐项指标字段、READ_ONLY/各 effect 类别分母、retry/compensation 不增分及 merge/split 复算 |
| RM-BUDGET-01 | RM §17.1–17.4，行 823–863 | 70/20/10、writer ≤2、authority surface 单 writer、Campaign WIP=1、四类控制预算、L0–L4 时间尺度及 Principal 注意力合同 | PARTIAL；补实际预算 owner、阈值、采集源、超限保护动作与恢复记录 |
| RM-STOP-01 | RM §18.1–18.3，行 867–902 | 12 类全局停止触发、9 层回滚及恢复完成定义 | PARTIAL；为每项增加触发器/立即动作/状态/停止 owner/恢复前置/验证/重开授权/receipt；服务重启不算恢复完成 |
| RM-RISK-01 | RM §19，行 904–922 | 13 项风险的表现、早期信号、控制、owner、剩余风险 | UNMAPPED；每个风险有 finding ID、严重度、测试或监测、接受人/阻断门 |
| RM-EVIDENCE-01 | RM §20.1–20.4，行 926–977 | E0–E5 阶梯、Phase 报告八项、决策规则、W0–W6 独立 QA 执行矩阵 | PARTIAL；当前证据引用未区分类型/新鲜度/范围/Verifier；需逐 phase 绑定具体 QA 与 artifact digest |
| RM-CONVERGENCE-01 | RM §21.1–21.3，行 981–1003 | 保留/扩展/建设/退役；默认禁止；BUILD-NEW 例外判定 | PARTIAL；BP §19/20 不能替代 RM 收敛程序；每行补当前 consumer、迁移和回滚证据 |
| RM-REDTEAM-01 | RM §22，行 1005–1022 | 路线图自己的 12 项红队攻击、响应与剩余风险 | UNMAPPED；与 BP §21 十项分别建行，逐攻击绑定 fixture、finding、严重度、实际结果与 residual-risk owner |
| RM-ACCEPT-01 | RM §23，行 1024–1048 | 八个接受问题与接受后的五步顺序；禁止接受后立即批量创建 BET | PARTIAL；包级信封不构成每个后续写入授权；补逐项 disposition、顺序验证和 binding proposal 门 |
| RM-COMPLETION-01 | RM §24.1–24.3，行 1050–1070 | 路线图完成、单 Phase 完成、整体愿景完成三种定义保持分离 | UNMAPPED；与 BP §22/§25 交叉映射但不可合并；补独立接受人、连续窗口和结果证据 |

W0–W6 的既有阶段行只是索引。逐阶段还必须记录 `target_owner`、`actual_claim_ref`、`independent_verifier`、`owner_status`、建议窗口/硬上限/起算事件、缺失窗口处理、退出条件和回滚 receipt。目标角色名称不等于实际认领。

#### 3.4.1 路线图缺口的目标责任、产品面与可复核退出证据

下表把 3.4 的缺口进一步转换为可落地的产品/架构合同。此处的页面和接口均是目标能力面，不表示当前已有对应路由；实际负责人仍须通过正式 Run/Claim 认领。除非后续有新鲜运行或业务证据，3.4 的矩阵覆盖状态保持不变。

| 条款 ID | 目标责任角色 | 产品/能力面与权威边界 | 独立验收证据与退出条件 |
|---|---|---|---|
| RM-DOC-01 | 文档控制 owner；Architecture reviewer | Cockpit 文档权威与证据等级视图；白皮书、蓝图、路线图分别保有其规范边界，运行状态由各事实源提供 | 用精确摘要和章节锚点核对文档身份；注入旧摘要、冲突术语和候选状态，验证界面显示来源/状态/适用范围且不把文档接受渲染为运行通过；独立 reviewer 复算 |
| RM-METRIC-01 | Portfolio/指标 owner；独立 evaluator；Principal 负责愿景裁决 | Cockpit North Star 与不可抵消 guardrail 视图；展示分子、分母、窗口、来源年龄和逐项结果，不由单一总分覆盖失败 guardrail | 从原始事件独立复算三层指标与愿景证明公式；注入合成、重复、缺 Outcome 和过期样本验证不增值；十项 guardrail 可各自阻断，Principal 对愿景结论留有精确裁决回执 |
| RM-STRATEGY-01 | Principal；Portfolio owner；Scene owner | 战略→Campaign→Objective/BET→WorkPacket 的层级视图；价值轨与可信控制轨并行展示依赖、汇合点和阻断原因 | 对照实际 Portfolio/BET 和两个轨道的输入输出，证明目标不漂移、可信控制不无限拖延价值样本；每个 HOLD 有明确触发条件、裁决角色和复审点 |
| RM-W0-01 | W0/Scene owner；Principal；独立 verifier | W0 charter、baseline、未决决策和时间盒视图；写入边界保持在正式准入允许范围 | 三个真实样本及人工 baseline 可复算；记录窗口起算、owner claim、输入/输出、writer 上限、停止与回滚演练；在 5–10 工作日硬上限内形成独立 Phase receipt，否则按路线图降级/停止语义处理 |
| RM-W1-01 | Scene owner；OMO Workflow Mesh/PEP owner；业务验收人 | Cockpit Inbox→Episode→Run→Receipt 的单一 scoped journey；WorkPacket/Capsule 由现有执行权威承载，Dashboard 只读展示 | 对同一真实 Episode 验证 Capsule 字段完整、effect 前 PEP、失败不晋级、Receipt 可独立复算，随后取得 E2/E3/E4 对应证据；业务验收人确认真实消费，否则不得进入 W2 |
| RM-W2-01 | Product/Scene owner；Runtime steward；Governance/PEP owner；Principal 处理必要裁决 | Golden Slice 汇合卡及五条件证据抽屉：useful、authorized、observable、recoverable、replaceable；另展示 OutcomeObservation/HumanVerdict 独立权威生产流、生产级 effect 前 PEP、desired/observed reconciler、组合健康、恢复、单入口和关键 Resident SLO/隔离 | 五项 receipt 绑定同一 Episode、scope 和 revision，任一失败阻断；另须证明 OutcomeObservation 与 HumanVerdict 有分离 writer/ID，pre-effect PEP 覆盖真实生产路径且 desired/observed reconciler 可复核；完成连续 4 周真实 Outcome、关键失败恢复演练、主要旅程可由 Cockpit 唯一入口完成，以及关键链 Resident 有最小功能 SLO 或被暂停/隔离并排除于 Overall health。证据须区分 E2/E3/E4 与连续 4 周形成的 E5 候选；五条件单次通过不足以退出 W2 |
| RM-W3-01 | Learning/Memory owner；业务场景 owner；Principal | 学习回路视图区分单环自动、双环提案、三环 Principal 裁决，并显示连续周窗口 | 连续 8 周样本、质量/安全基线及改进前后复算齐备；角色越权组合被拒绝，双环提案经批准，三环有 Principal 回执；窗口中断不得事后补齐 |
| RM-W4-01 | 第二 Scene owner；Platform/DomainPack steward；Principal 审核高敏感数据与自治边界 | 第二场景评估与隔离卡，按频率、可逆性、裁决人、连接器和隐私边界排序；复用同一对象、入口、Mesh、记忆、控制和 Outcome 合同，不建第二 dispatcher/SSOT/记忆面 | 候选场景逐一说明收益、风险、数据边界、owner 与拒绝理由；Adapter/contract E2、真实跨场景运行 E3、第二场景 Outcome E4 与连续窗口 E5 证据齐备；跨域隔离通过、共享核心不分叉且持续产生真实 Outcome 后才退出 W4 |
| RM-W5-01 | Resident desired-state owner；OMO supervisor；Ops | Runtime/Resident 视图呈现 Role、queue、lease、checkpoint、desired state、SLO 和 escalation；heartbeat 单独标记为存活信号 | 证明 input→consume→verified outcome 的功能 SLO；注入队列滞留、lease 丢失、scope 超限与冷启动替换，验证拒绝/升级/恢复 receipt；Agent 实例替换不改变权威对象身份 |
| RM-W6-01 | Principal；Portfolio council/role；各 Scene owner；Independent assurance role | 至少两个 Scene 的愿景候选验证面，连接完整价值归因、必需 KR、第二环境证据、年度 Constitution review、季度 subtraction、角色接管和安全缩减/退出 | 按 RM §12.1/§1.4 证明必需 KR 全部 E5、连续 12 周可从原始事件复算、第二环境有真实 E3/E4、核心权威不分叉、系统可安全缩减或退出，并取得 Principal 最终裁决；年度 review/季度 subtraction 是持续治理要求，不能替代 W6 阶段退出条件 |
| RM-MILESTONE-01 | Portfolio owner；Ops；Principal | 30 天、90 天、1 年、3 年里程碑时间线，展示起算事件、实际进度、数据年龄、外部依赖和降级状态 | 从精确起算事件重算每个观察窗；注入缺测、超期、guardrail 失败和依赖中断，页面显示未测/延期/需重授权且不自动放行；每次继续均有对应授权与 receipt |
| RM-OBJECT-01 | Portfolio/OMO 各对象 owner；Architecture owner；独立 verifier | 按 RM §14.1 展示 Portfolio→Campaign→BET→accepted Spec→WorkPacket→Run→Evidence/Receipt→OutcomeObservation→HumanVerdict/Revision→KR projection/Learning proposal；另以关系链接显示 Objective/KR 与 DecisionRecord，不把补充关系宣称为唯一线性链；proposal overlay 与 canonical ID 分层显示 | 对规范对象逐一绑定唯一 writer，或明确派生/producer 规则和读取 validator；Episode 必须标明无整条 direct writer、由 OMO 按 `episode_id` 从事件派生；Evidence 由机制产生并由独立 validator 读取。逐对象记录 consumer、生命周期和完成条件；断链、重复 ID、双 writer 与 overlay 冒充 canonical 的负测均拒绝；端到端 replay 可重建选择/不行动到结果/裁决的因果关系 |
| RM-BET-01 | Portfolio/Ledger owner；BET writer；独立 verifier | BET 生命周期与父子 Portfolio 守恒面，展示准入、绑定、supersede、失败、consumer 和退役状态 | 对 §15.3 每项守恒规则提供输入/输出摘要和可审计的单 writer 强制证据；child-first/root-last 顺序错误、未接受绑定和双 writer 负测失败关闭；可采用 CAS 等具体机制，但机制选择不得冒充路线图要求；只有正式 Ledger receipt 可改变状态 |
| RM-METRIC-02 | 指标/data owner；Portfolio evaluator；独立审计人 | 指标词典与基线校准面；列出制度连续性、effect taxonomy、root_episode 和 materiality 规则 | 逐指标从原始事件复算；READ_ONLY 与各 effect 类分母分别核对，retry/compensation 不新增成功，Episode merge/split 前后结果可解释；字段、来源、freshness、owner 和反操纵规则齐备 |
| RM-BUDGET-01 | Portfolio owner；各 authority-surface writer；Ops；Principal | 70/20/10 投入、writer≤2、单 writer、Campaign WIP=1、四类控制预算、L0–L4 时标与 Principal 注意力视图 | 预算各有权威来源、阈值和采集时间；注入 writer/WIP/资源/注意力超限，验证保护动作、停止原因、恢复责任和审计 receipt；预算变更由其授权角色批准 |
| RM-STOP-01 | Ops/各 domain stop owner；Principal；独立 verifier | 全局停止触发器和九层 rollback/recovery 面；状态从触发、冻结、恢复检查到重新开放逐步记录 | 12 类停止条件逐项注入并核对即时动作、停止 owner、恢复前置、验证和重开授权；服务重启单独不能满足恢复完成；所有层级留下可复演 receipt |
| RM-RISK-01 | Risk owner；安全 Auditor；Principal/授权风险接受人 | 13 项路线图风险登记与下钻；每项显示表现、早期信号、控制、owner、严重度和剩余风险 | 每项风险绑定稳定 finding ID、可复核测试/监测与阻断门；注入信号验证告警/升级；残余风险有明确接受人或保持 HOLD，不以登记完成冒充已缓解 |
| RM-EVIDENCE-01 | Phase owner；QA/Verifier；独立 Auditor | E0–E5 证据阶梯、Phase 报告和 W0–W6 QA bundle；证据类型、时间、scope、digest、执行者、原始证据引用和重放方式可下钻 | 每个阶段按路线图要求绑定 artifact/source digest、`current_as_of`、真实检查步骤和重放方式；旧、合成、越 scope 和作者自验收证据不得提升等级；QA 只使用 `PASS/FAIL/DEGRADED/UNPROVABLE`，并与阶段报告逐项一致 |
| RM-CONVERGENCE-01 | Architecture owner；项目/capability owner；独立 source auditor | 能力保留/扩展/原位建设/退役目录，关联当前 consumer、数据权威、API、迁移和回滚 | 每个能力以当前源码/runtime/consumer 证据作处置；退役前证明迁移和回滚，BUILD-NEW 必须满足原文例外论证；已归档能力不得仅凭历史标签复活 |
| RM-REDTEAM-01 | 独立安全 Auditor；被测 capability owner；风险接受人 | 路线图 12 项红队攻击台账，与 BP §21 十项分开追踪并可按 finding/严重度/剩余风险下钻 | 12 项攻击逐项绑定 fixture、实际执行结果、响应/修复回归和 residual-risk owner；风险分级及阻断阈值须引用另一个已接受的安全政策，不能归因于路线图 §22；若适用政策未绑定则风险接受/阶段门为 UNPROVEN，模拟成功攻击不因文档响应而判通过 |
| RM-ACCEPT-01 | Principal；Architecture/document owner；独立 verifier | 八个接受问题逐项 disposition 与五步后续顺序视图；包级接受、Workspace binding、Ledger、运行和发布授权分开展示 | 精确复核每个问题的决定、scope、摘要和回执；故意跳过任一步或批量创建 BET 的演练被拒绝；只有各自必要门通过后才能进入对应后续阶段 |
| RM-COMPLETION-01 | 文档控制 owner；Phase owner；业务验收人；独立 Auditor；Principal | 路线图文档接受、单 Phase 完成、整体愿景完成三条分开的验收视图，并关联 BP §22/§25 但不合并定义 | 路线图完成只按 §24.1：术语一致、阶段门明确、无真实 BET ID/隐式 Ledger mutation、动态事实限定为历史快照、Principal 精确接受信封；单 Phase 按 §24.2 自身退出条件验收；整体愿景另按 §24.3/§1.4 的连续 E5 真实结果公式裁决。三者不得共享一个完成状态，缺项均保持未完成 |

本表补充的是目标映射，不关闭 3.4 的 `UNMAPPED/PARTIAL`：要关闭每行，仍须把路线图原文的全部编号子条款逐一链接到具体 consumer/API、正式 claim、实际 verifier 和新鲜证据摘要。若目标产品面暂时没有实现，应把它登记为待执行 capability；不得为补矩阵而虚构 endpoint、负责人或运行结果。

## 4. 主权权利、产品角色与制度分离

### 4.1 八项 Principal 权利必须进入产品验收

| 权利 | 具体交互合同 | 验收 | 当前状态 / 证据 |
|---|---|---|---|
| 知情 | 能查看系统正在做什么、为什么、数据/能力来源和影响范围 | 来源、权限、状态、变更差异可追踪；缺失明确 UNKNOWN | 部分；来源/状态可见但数据陈旧、角色范围与影响闭包未全〔E1、E2、E3〕 |
| 选择 | 能采用、修改、拒绝、延期或选择不行动 | 每个决策都有明确选项，默认动作安全且被记录 | 未证；尚无完整真实 Episode 裁决闭环〔E4、E7〕 |
| 接管 | 任意阶段切回人工；暂停后不可继续执行 | 运行中接管端到端测试与 ActionReceipt | 未证；候选执行路径不等于已部署的接管与回执〔E1、E4〕 |
| 撤销 | 撤销 Mandate、能力、连接器、记忆和共享授权 | 撤权后相关写入口立即 fail closed，并传播至缓存/派生视图 | 部分；Work Case 局部授权候选，跨写路径传播未验收〔E2、E4〕 |
| 纠错 | 修订事实、偏好、角色、历史解释、价值判断 | 原历史可追溯，纠错产生新版本/事件而非覆盖原事实 | 未证；知识/记忆路由候选不能证明纠错传播闭环〔E3、E7〕 |
| 重置 | 清除个性化影响，回到非个性化基线 | reset receipt 与可重复基线比较 | 历史基线未发现；当前未验证。无 reset receipt 与复算证据〔E7 历史审计，不代表现状〕 |
| 迁移 | 导出数据、记忆、配置、证据和模型化资产 | 完整性、来源、隐私级别和导入恢复演练 | 历史基线未发现；当前未验证。无端到端 export/import/recovery 证据〔E7 历史审计，不代表现状〕 |
| 关停 | 关闭单一能力或整个系统且不制造新风险 | 有权停止、状态冻结、未完成责任清单和安全恢复演练 | 未证；静态服务与投影检查不能证明安全关停〔E1、E5、E6〕 |

### 4.2 三类产品主体映射到制度权力角色（产品设计扩展）

“管理员、Agent、业务人员”三主体来自用户的产品定位要求和本产品设计，不是白皮书原生分类；下表把产品体验主体映射到规范权力角色，权限最终必须由服务端 authority 决定。原文锚点为 WP §5.1/§5.9（行 479–522）、§6 P19/P22（行 526–551）及 §32.2（行 2386–2434）。

| 白皮书规范角色 | 职责与允许承担者 | 产品主体映射 | 不可兼任条件 | 服务端证据 |
|---|---|---|---|---|
| Operator | 执行已授权 WorkPacket；可由临时 Agent 或确定性 worker 承担 | Agent；经认证且单独获授权的管理员/业务人员也可承担有限操作 | 高风险动作不能自验收；不得自授予权限 | ActionReceipt 绑定 Principal/Mandate、lease、resource scope |
| Steward | 维护局部队列、SLO、依赖和上下文；可由 domain resident/controller 承担 | 管理员主要承担运行 Steward 职责；业务人员可在其业务域被授权为 Scene Steward | 不能自改域目标或 Constitution | 持久 role/queue/checkpoint/SLO 与变更回执 |
| Governor | OMO policy 与受限语义解释器解释适用政策并产生 allow/deny/degrade | 不属于人类 UI persona；管理员只能配置经过独立授权的参数 | 不能执行其批准的高风险动作；LLM 不能自裁 allow | 版本化 PolicyDecision、PEP 结果和 Coverage Receipt |
| Auditor | alternate agent、确定性 replay 或人类独立核验证据、coverage、outcome | 可由管理员中的独立审计者或外部 verifier 承担 | 不能由被审计者控制输入和结果 | 固定输入摘要、独立测量与签名 verdict |
| Principal | 修改目的、宪法、高风险授权及最终裁决；不可让渡权利仅由人类本人行使 | Principal 是单独的人类主权身份，不等于管理员或业务 persona | Agent 不代理；普通管理员凭证不自动升权 | Principal 绑定、Mandate、撤销、HumanVerdict 与恢复收据 |

Controller、PEP、Observer、Worker 是架构中的执行机制/组件，不是白皮书规范角色，不得与上表五类逻辑角色并列。管理员、Agent、业务人员是产品主体；其权限必须通过服务端 Principal、persona、capability 与 resource scope 绑定，不能在 UI 中用自由字符串完成授权。

## 5. 用户体验合同与真实场景

| 能力域 | 必须落地的体验 | 测量与验收 | 当前状态 / 证据 |
|---|---|---|---|
| 统一导航/跨入口 | 一个产品身份、一套壳、直接链接/刷新/query/hash 不丢上下文；每个旧入口有 parity、迁移和回滚 | 56 页与 15 alias 的逐项能力/API/error-state parity；孤儿链接为 0；三 persona deep-link 检查 | 有候选；生产入口仍未切换〔E1、E3、E6〕 |
| Attention Inbox | 去重、排序、静默、批处理、升级、安静时段、事项解释 | 通知/审批/纠错分钟数、误报/重复率、超预算告警、每条提醒的 actionable reason | 未证〔E3、E7〕 |
| 解释与决策 | 显示来源、反证、未知、选项、取舍、信心和复审日期 | 用户能在 Journey 中追溯证据并选择采用/改动/拒绝/延期/不行动 | 仅有设计线索，未真实验收〔E3、E7〕 |
| 审批与授权 | 请求说明 action/resource/risk/cost/expiry/revoke，支持 deny/needs-human | 三类主体 allow/deny/cross-resource/replay/expired 负测 | Work Case 有局部候选；完整写路由未证〔E2、E4〕 |
| 纠错与撤销 | 用户能修正事实、撤回共享/连接器/记忆，派生索引和摘要同步失效 | E2E 验证原事件不可覆写、撤销传播、重试幂等、audit receipt | 未证〔E3、E7〕 |
| 恢复/回滚/关停 | 失败可诊断、接管、暂停、恢复、补偿、回滚、导出和安全停止 | 真实故障注入/恢复演练和 RTO/RPO；不产生重复副作用 | 候选测试有，运行演练未证〔E1、E4、E5〕 |
| 无障碍与多终端 | 键盘/焦点、屏幕阅读器语义、色彩非唯一编码、缩放、窄屏布局 | WCAG 2.2 AA 目标检查、关键三 persona Journey 自动/人工验收 | 未证〔E3、E7〕 |
| 产品扩展 Journey 1：公文起草与审查 | 来源→拟稿→审查→修订→人工提交/引用→反馈 | 真实用户消费回执、来源 span、敏感数据最小化与可恢复修改 | 未证〔E3、E4、E7〕；不是白皮书指定的固定场景 |
| 产品扩展 Journey 2：会议到督办 | 决议→行动项→负责人/期限→确认→完成回执→结果 | 至少两项行动及缺负责人的拒绝样本；由业务验收人确认真实派发/完成 | 未证〔E3、E4、E7〕；不是白皮书指定的固定场景 |
| 产品扩展 Journey 3：工程交付 | 意图→Spec/Task/Run→PR/artifact→门禁→交接→接受/拒绝结果 | 独立 worktree；失败接管/撤销/回滚；merge 不自动算业务成果 | 有工程候选，业务消费闭环未证〔E3、E4、E7〕；不是白皮书指定的固定场景 |

白皮书原生要求是从工作与知识生产域选择真实、高频、可审阅、可回滚、具备 HumanVerdict 的 Golden Slice（BP §18；WP §16.2，行 1477–1484），三个具体旅程仅为待 Principal/Scene owner 选定的产品方案候选，不得当作已接受样本或场景承诺。

## 6. Epoch/Wave、退出门与组合顺序

| Epoch / Route wave | 依赖 | 交付目标 | 不可提前跨越的退出门 |
|---|---|---|---|
| A / W0：宪法与真值重置 | v2.1 精确接受；现有候选 source baseline | 需求逐项追踪；Portfolio/Goals/Architecture 权威图；选定一个真实 Golden Slice 并记录现状基线/拒绝样本 | 独立 review；真实资料由权利人提供/批准；不写生产、不伪造业务结果 |
| B / W0–W3：黄金价值闭环 | Episode/Outcome/HumanVerdict canonical schema、数据分级与用途保留 | 一条真实 Signal→Context→Decision→Run→Receipt→Verdict→Outcome→Memory | 连续 4 周真实结果；人工消费确认；未知数据始终 UNMEASURED |
| C / W1–W2：可信执行与单一体验 | W0 场景与受控身份/写入路径；并行做基础治理 | Cockpit 成为唯一人类产品，OMO 唯一执行脊柱，三 persona 的强制授权和可恢复体验 | 关键 Journey SLO、无假成功/PEP bypass/重复副作用；入口迁移/回滚 E2E |
| D / W3：学习效果证明 | 至少一个真实场景连续使用并有 adjudicated feedback | replay/evaluation、Revision 改善、资源/注意力成本下降 | 连续窗口统计有效，且安全、质量不退化；独立批准 promotion |
| E / W4–W5：第二场景与有限自治 | Epoch B–D 通过 | 第二 Journey 复用同一 Episode/Run/Outcome；低风险能力可撤销地进入 assisted/supervised | 不引入第二 dispatcher/SSOT；自治可即时降级；真实第二场景验收 |
| F / W6：复利与愿景验证 | 多场景、受控学习、连续运行 | 跨场景复用，价值、信任、可靠性、可持有性同时成立 | 连续 12 周指标门；无工程代理分数补位；迁移/关停/恢复演练通过 |

执行顺序采用两条并行轨：产品价值轨从 W0 开始做只读场景 shortlist、现状时间/注意力基线和拒绝样本设计；平台可靠/安全轨并行处理 DCP-11 与 DCP-20。W1 只依赖其 Golden Slice 自身的 W0 汇合门，不等待全平台 M2；但不得以场景提案替代真实业务资料/裁决，也不得在该场景生产写准入前触发实际外部写入。

投入默认按白皮书 70% 真实产品/价值闭环、20% 可靠/安全/恢复、10% 治理/元体系分配。P0 真值或安全事件可临时重分配，但必须绑定事故、退出日期、恢复比例的条件。

## 7. 下一批可执行 Bets（提案，尚未登记）

| Bet ID | Owner | 输入/边界 | 交付与验收 | 阶段关系 |
|---|---|---|---|---|
| DCP-TRACE-01 白皮书逐项追踪 | 产品/架构主控 + 独立 Verifier | 白皮书/蓝图/路线图精确摘要；只读计划工作 | 完成 24 原则、8 体系、5 平面、20 对象、8 权利、6 Epoch、三 Journey及 WP/BP/RM 所有顶层/子条款到能力、authority、产品面/API、验收、Owner、状态、证据与退出门双向链接；BP §15 的五级控制/R0–R3 分项规则、§19 每项能力处置、§20 每个项目边界、§21 十项红队（含 owner/测试/结果/严重度/剩余风险）、§22 每条三门/连续性条件、§23 每个 W0–W6 task-gate-receipt 映射都要逐行建档；独立复核无未映射条款 | W0 前置；BP §15、§19–23 子项映射已列，WP/BP/RM 其余子条款仍需逐项核对，且大量当前状态、实现/运行/Outcome 证据尚未绑定 |
| DCP-W0-A Golden Slice 与基线 | Product Owner + 真实 Scene owner + 独立业务验收人 | 仅用用户/业务 owner 授权的真实样本；最小披露；不代用户裁决 | shortlist；至少 3 个真实历史/当期样本；频率、当前人工耗时/错误/注意力基线；拒绝/no-action 样本；可接受结果与数据边界；唯一 North Star evaluator 和原始事件复算合同 | W0，5–10 个工作日且硬上限 10 日；与 DCP-11/DCP-20 并行 |
| DCP-W0-B Authority/信任域/复用处置 | Architecture + Security/Platform owner + Principal | 只读盘点现有 owner、trust domain、项目/资产边界；不变更访问策略 | 为 Golden Slice 画出数据/身份/写入/审计边界；逐项标注复用、适配、隔离、替换或退役及依据；Principal 签收所选场景的目标和非目标 | W0，5–10 个工作日；与样本基线并行；未签收则不进入该场景的真实 effectful 路径 |
| DCP-DESIGN-01 三主体产品设计 | Product Design + Accessibility QA + 三类主体代表 | 基于本矩阵与逐组件/API 审计；原型不得呈现未授权能力为可用 | 交付关键旅程图、导航/页面蓝图、视图与交互状态、权限可见性、视觉层级、研究计划和无障碍/可用性标准，详见 [`2026-10-07-dashboard-product-design.md`](2026-10-07-dashboard-product-design.md) | W0 只读设计；真实受测者同意后进入用户研究 |
| DCP-ROLE-MAP-01 persona/权力矩阵 | Identity/Product + Security Verifier | 服务端 auth/action inventory；只读审计 | 三产品主体映射五制度角色，列 persona × route × action × resource、可兼任/禁止兼任和负测 | DCP-20A/B 输入 |
| DCP-UX-ACCEPT-01 体验合同 | Product Design + Accessibility QA + 业务验收人 | route/component capability inventory；真实场景 fixture 需标注 synthetic | Inbox、解释、审批、通知、纠错、无障碍、移动端、注意力成本的可执行验收和失败态合同 | DCP-21 与三 Journey 输入 |
| DCP-W3-W6-ROADMAP 后续阶段闭合 | Product/Architecture + Portfolio Owner | v2.1 Epoch/Wave 与真实 W0 证据 | 为学习/回放、第二场景、有限自治、受控进化、跨环境复制、暂停/撤销/导出/关停分别定义 Owner、依赖、预算、退出证据和 rollback | W0 基线通过后分批建 BET |
| DCP-11 reader + freshness repair | Platform + independent code/runtime verifier | 16 MiB revision reader source fix、compact-observation candidate、受信发布输入 | 503 修复进入受信 revision；freshness 绑定真实 source `observed_at`；collector success/failure 保留 last-good 且失败不续成功时间；idle/busy 至少 30 warm samples 与 recovery | 当前最高优先平台切片；G0/runtime gate 前仅候选 |

本文这些 Bet 是拆解提案，需先经过精确输入、职责/allowlist、预期工件、独立复核和治理准入；不得把此文或现有绿色测试等同正式 BET 注册、G0 binding、生产写入许可或发布授权。

## 8. 覆盖缺口与审阅焦点

1. 现有六个 WP 宏观标签不能覆盖白皮书中的逐项规范；本矩阵把六项提升为索引，不取代 24 原则/8 体系/5 平面/20 对象/8 权利/6 Epoch 的逐条追踪。
2. 产品主体（管理员、Agent、业务人员）与 Operator/Steward/Governor/Auditor/Principal 五类制度角色分属体验和权力层，必须由服务端权威矩阵桥接，不得并成 `role` 自由字符串。Controller、PEP、Observer、Worker 是机制/组件。
3. W0 价值场景发现和治理/可靠性工作需并行；真实样本、用户裁决和业务消费回执仍必须来自授权的人。
4. Dashboard 价值验收必须把可靠性、安全、复杂度和注意力预算作为四个独立门，禁止折算为单一总分。
5. 旧路径只有完成能力/API/error parity、深链、三 persona 授权、链接扫描、consumer 检查和回滚后，才能进入退役门。
6. 历史现场曾出现 `/data.json` 503（旧运行服务 1 MiB 上限拒绝绑定投影）；该历史问题与后续 `projection_validation_busy` 并发 503 分开追踪，当前现场证据见 E9。页面状态不能作为真实业务健康证明。
7. §3.2 现已逐一引用 WP §0–34、BP §0–25、RM §0–24 的全部顶层章节编号，并对高风险合同单列验收行；仍需按原文子条款逐条完成 source-clause 双向审计、能力/API 绑定与可复算证据。章节编号覆盖不等于需求实现覆盖，因此 DCP-TRACE-01 仍进行中，不得声称白皮书要求已全量达成。
