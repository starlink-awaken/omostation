# 数字生命体架构 — Digital Organism Architecture

> **版本**: v1.0 | **日期**: 2026-08-08
> **状态**: 战略设计 (ADR待写)
> **理论**: 系统论 × 信息论 × 控制论 × 图灵论
> **前置**: 28+ PRs (Meta-0执行层80%完成), 13条设计决策确认, 四论映射完成

---

## 0. 愿景

织星 eCOS 不是一个工具——它是夏明星的**数字生命体**。一个能感知、思考、决策、行动、反思、进化的活系统，最终成为"第二个数字的我"，覆盖工作/家庭/健康/财务/教育全领域，可扩展给家庭成员，可形成组织蜂群。

**渐进自主度**: 第1月"新手助理" → 第3月"上手" → 第6月"比你自己做还快" → 第12月"完全替代"。

---

## 1. 四论框架

| 理论 | 约束维度 | 核心命题 | 工程映射 |
|------|---------|---------|---------|
| 系统论 | STRUCTURE | 系统大于部分之和; 开放系统需要边界 | namespace隔离 + Meta-0~3层次 + 涌现进化 |
| 信息论 | FLOW | 信息=不确定消除; 信道有容量上限 | signal→info→knowledge→wisdom 流水线 |
| 控制论 | FEEDBACK | 负反馈稳态, 正反馈增长; 延迟致振荡 | Trust Policy(负) + 熟悉度升级(正) + 滑动窗口(阻尼) |
| 图灵论 | COMPUTATION | 计算=状态+转移+纸带; 停机不可解 | journey=有限自动机; checkpoint=人工Oracle |

**五条收敛原则**:
1. **Ashby必要多样性**: 治理复杂度 ≥ 被治理复杂度
2. **Shannon信息不减损**: context只增不删, 每环节保留决策依据
3. **Wiener反馈阻尼**: |Δtrust/日| ≤ 0.05, 滑动窗口7天, 滞回区间防抖
4. **Turing计算边界**: 不可计算判断(公文质量/领导意图)→人工Oracle
5. **Autopoiesis进化治理**: S1自动(≤100行)/S2确认(新能力)/S3审批(架构变更)

---

## 2. 四面一脊 × 四层元架构

```
         外部世界
            ↓ Signal (信息论: 不确定消除)
    ┌───────────────┐
    │ ① 感知面        │  signal-poller → iris connectors
    │   Perception   │  (已有, 需扩展信号源)
    └───────┬───────┘
            ↓ Information
    ┌───────────────┐
    │ ② 认知面        │  MOS三表(agent_belief) + Advisor + TELOS
    │   Cognition    │  (核心缺口 — Keystone)
    └───┬───────┬───┘
        │       │
   ┌────▼──┐ ┌─▼────┐
   │决策   │ │反思   │  Trust Policy + Risk Gate | Reflection + PatternMiner
   │(控制论)│ │(控制论)│  (负反馈稳态)              | (正反馈学习)
   └────┬──┘ └─┬────┘
        │       │
    ┌───▼───────▼───┐
    │ ③ 执行脊柱     │  journey-runner + dispatchers + capability-router
    │   Spine       │  (已有, 80%完成)
    └───────┬───────┘
            ↓ Action (图灵论: 状态机执行)
    ┌───────────────┐
    │ ④ 结果面        │  outcome-recorder + reflection → feedforward
    │   Outcome     │  (已有, 需桥接MOS)
    └───────┬───────┘
            ↓ Feedback (控制论: 闭环)
    ┌───────────────┐
    │ Meta-3 进化    │  evolution-agent + self-modification(S1-S3) + MOF
    │   Evolution   │  (缺失 — 需新建)
    └───────────────┘
            ↓ 新结构/能力/愿景 (系统论: 涌现+自创生)
         回到① (循环)
```

---

## 3. 13条架构决策 (grill-me产出)

| # | 决策 | 要点 |
|---|------|------|
| 1 | 执行模型 | A+B+C混合: daemon tick(监控) + journey-runner(编排) + Claude Task(执行) |
| 2 | 能力分层 | C1观察(自主) C2准备(自主) C3沟通(积累) C4系统(连接器) C5交易(风控门禁) |
| 3 | Trust Policy | 4原则: 可逆性 + 熟悉度 + 风险加权 + 学习闭环 |
| 4 | 紧急覆盖 | Advisor裁决 + 安全兜底(holding response) + 事后review |
| 5 | 心智模型 | 5层: Identity/Strategy/Pattern/Knowledge/Feedback, 日轻量+周重量 |
| 6 | Agent拓扑 | 3层: 常驻(感知/编排/参谋/治理) + 按需(文档/邮件/数据) + 涌现(从重复诞生) |
| 7 | 外部工具 | Capability Router: Claude Code/Codex/Crush按能力+成本路由, 治理沙箱 |
| 8 | C5风控 | Risk Gate: 金额分层 + 白名单 + 冷却期 + 延迟执行 + 全审计 |
| 9 | 多人架构 | 共享基建 + 独立namespace + 家庭共享区 + 蜂群临时编组 |
| 10 | 权限分割 | 7层过滤器: 身份→关系→敏感度→用途→时间→操作→委托 + 动态授权 |
| 11 | 自进化 | 4层元架构(Meta-0~3) + S1/S2/S3自修改 + MOF governance约束 |
| 12 | 可观测性 | 日志+指标+追踪+事件 → 统一dashboard |
| 13 | 进化Agent | 定期内外扫描(日debt/周research/月vision) → 提案 → S1自动/S2确认/S3审批 |

---

## 4. 实施路线图 — 五阶段

### Phase 0: 接血管 (CRITICAL, ~1周)

> 目标: 让已有器官开始协作

| 任务 | 对应缺口 | 产出 |
|------|---------|------|
| MOS agent_belief三表建表 | CRITICAL #1 | `projects/kairon/packages/mos/src/mos/agent_belief/` — world_snapshot + capability_calibration + decision_outcome schema + BOS读写路径 |
| Neo4j本地实例配置 | CRITICAL #2 | `.env`设NEO4J_URI + `make mos-neo4j-up` + 验证持久化 |
| Aetherforge wire到AgentHost | CRITICAL #3 | AgentHost tick中调Aetherforge emit_event → agent行为可观测 |
| MOS Bridge: outcome→decision_outcome | HIGH #7 | scene-outcome-recorder写MOS表 |
| MOS Bridge: reflection→world_snapshot | HIGH #7 | scene-reflection写MOS表 |

**验收**: `bos://memory/mos/recall` 返回真实数据; agent行为通过Aetherforge可追踪。

### Phase 1: 建大脑 (HIGH, ~2-3周)

> 目标: 系统能思考

| 任务 | 对应缺口 | 产出 |
|------|---------|------|
| MOF M2: Agent spec模型 | HIGH #4 | `ecos/ssot/mof/m2/agent.yaml` |
| MOF M2: Permission模型 | HIGH #4 | `ecos/ssot/mof/m2/permission.yaml` |
| MOF M2: Capability Provider模型 | HIGH #4 | `ecos/ssot/mof/m2/provider.yaml` |
| Trust Policy Engine实现 | HIGH #5 | 扩展SceneWatcher: +trust_score评估 +4原则 +滑动窗口阻尼 |
| Advisor Agent实现 | HIGH #6 | 扩展SceneWatcher→Advisor: 读MOS三表 + L4 TELOS注入 + evaluate_action() |
| Agent Registry实现 | HIGH #8 | `.omo/_truth/registry/agents/` + MOF校验 + 动态注册 |
| L4 injector扩展TELOS | 集成缺口 | claude_injector支持TELOS上下文注入给Advisor |

**验收**: Agent提议动作 → Advisor读MOS评估 → Trust Policy决策 → permit/ask/block。

### Phase 2: 补领域 (MEDIUM, ~2-3周)

> 目标: 覆盖全生活

| 任务 | 对应缺口 | 产出 |
|------|---------|------|
| 家庭场景卡 (3-5张) | MEDIUM #9 | 家庭日历/采购/家务/亲子 |
| 健康场景卡 (2-3张) | MEDIUM #9 | 运动/饮食/体检 |
| 财务场景卡 (2-3张) | MEDIUM #9 | 收支/投资/报税 |
| 教育场景卡 (2-3张) | MEDIUM #9 | 作业/辅导/成长 |
| 对应journey specs (6-10条) | MEDIUM #9 | 家庭/健康/财务/教育流程 |
| 冷启动: WPS Notes预灌 | MEDIUM #10 | 批量导入知识到MOS world_snapshot |
| 冷启动: Documents预灌 | MEDIUM #10 | 公文模板/工作流程/人际关系到MOS |
| iris live dispatcher测试 | MEDIUM #15 | wpsnote/rss/zhihu/wxread逐个live |

**验收**: 4个新领域各有场景跑通dry-run; MOS有预灌知识(非空启动)。

### Phase 3: 建进化 (MEDIUM, ~3-4周)

> 目标: 系统自我迭代

| 任务 | 对应缺口 | 产出 |
|------|---------|------|
| 可观测性Dashboard | MEDIUM #11 | cockpit扩展: agent状态/trust趋势/journey热力图/debt看板 |
| Evolution Agent | MEDIUM #12 | 常驻agent: 日debt扫描/周research/月vision审计 |
| Risk Gate实现 | MEDIUM #13 | C5动作风控: 分层授权+白名单+冷却+审计 |
| Permission Matrix | MEDIUM #14 | 7层过滤器 + 动态授权 + 学习型权限 |
| Governor Agent | 集成 | Eidos PatternMiner wire + trust策略执行 + 周报synthesis |
| Workflow Mesh集成 | MEDIUM #16 | journey checkpoint → Mesh ApprovalRequested映射 |
| 自动Debt写入 | Meta-2 | Problem Detector → debt.yaml自动条目 |

**验收**: Evolution Agent周报产出进化提案; Risk Gate拦截C5异常; dashboard可视化全系统。

### Phase 4: 开放 (LOW, 持续迭代)

> 目标: 向外生长

| 任务 | 对应缺口 | 产出 |
|------|---------|------|
| Swarm协议 | LOW #17 | twin发现 + 临时编组 + 共享上下文 + 解散 |
| Capability Router | LOW #18 | Claude Code/Codex/Crush按能力路由 |
| Multi-namespace隔离 | LOW #24 | 多人共享实例的namespace机制 |
| Emergency Override | LOW #21 | 不可用检测 + Advisor代决策 + 安全兜底 |
| OA-write连接器 | LOW #22 | CDP Runtime.evaluate深抓 + OA提交 |
| 银行/电商连接器 | LOW #23 | API或browser自动化(受Risk Gate约束) |
| Agent Lifecycle Manager | LOW #20 | spawn/retire/version + 涌现创建 |

**验收**: 家庭成员各有twin运行; 蜂群可组建; C5操作受风控执行。

---

## 5. 已有基建全景 (不重建, 只连接)

### 已有且可用 (直接复用)

| 组件 | 位置 | 行数 | 角色 |
|------|------|------|------|
| journey-runner | bin/ssot/ | 500 | Meta-0执行引擎 |
| signal-poller | bin/ssot/ | 134 | ①感知面 |
| scene-outcome-recorder | bin/ssot/ | 143 | ④结果面 |
| scene-reflection | bin/ssot/ | 150 | Meta-2反思 |
| capability-token | bin/ssot/ | 141 | 权限令牌 |
| journey-state-store | bin/ssot/ | 133 | 状态持久化 |
| 9 scene cards | docs/scene-cards/ | — | 场景规格 |
| 3 journey specs | docs/journey-specs/ | — | 状态机 |
| HealthMonitorAgent | omo/ | — | Meta-1运维 |
| JourneyRunnerAgent | omo/ | — | Meta-0编排 |
| SceneWatcher | omo/ | 198 | ②认知(待扩展为Advisor) |
| AgentHost + Protocol | omo/ | — | Agent运行时 |
| Eidos PatternMiner | kairon/ | 568 | Meta-2模式检测 |
| L4 claude_injector | l4-kernel/ | 290 | TELOS注入 |
| Workflow Mesh | omo/ | 17函数 | 事件生命周期 |
| Aetherforge bus | aetherforge/ | — | Agent通信 |
| MOS Phase10 | kairon/ | — | 记忆OS(Neo4j) |
| MOF M3 | ecos/ | 653 | 元元模型 |
| KOS BOS services | agora/ | — | 知识检索 |
| iris connectors | kairon/ | 20个 | 外部连接 |

### 已有但未连接 (Phase 0-1接通)

| 组件 | 当前状态 | Phase 0/1做什么 |
|------|---------|----------------|
| Aetherforge bus | 存在不被用 | wire到AgentHost → agent行为可观测 |
| Eidos PatternMiner | 存在不被用 | wire到Governor → 模式检测驱动涌现 |
| L4 injector | 注入schema不注入TELOS | 扩展注入TELOS → Advisor有上下文 |
| Workflow Mesh | 存在journey不用 | 映射checkpoint→ApprovalRequested |
| MOS Neo4j | fixture模式 | 设URI → 真实持久化 |
| SceneWatcher | 198行confidence评估 | 扩展为Advisor + Trust Policy |
| KOS | BOS注册但不被查 | Advisor查KOS获取知识上下文 |
| iris 20个 | 只用2个 | live测试+dispatch扩展 |

---

## 6. BET对齐

本路线图对齐BET台账8条Track:

| Track | 本方案Phase | 状态 |
|-------|-----------|------|
| T1-TRUTH | 全程贯彻 | ✅ 实践中 |
| T2-PERCEPT | Phase 0扩展 | ✅ 基础完成 |
| T3-COGNI | Phase 0-1核心 | ⏳ **Keystone (MOS三表)** |
| T4-OUTCOME | Phase 0桥接 | ✅ 基础完成 |
| T5-ORCH | Phase 0-1集成 | ⏳ Mesh集成待做 |
| T6-SUBTRACT | Phase 3 | ✅ 基础完成 |
| T7-SCENE | Phase 2扩展 | ✅ work域完成 |
| T8-SURFACE | Phase 3 | ❌ 待做 |

**Y1北极星**: "一个场景走完真实闭环" — inbox-to-decision live验证已通过 (PR #1126)。

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 冷启动太慢, 用户放弃 | 高 | 致命 | Phase 2预灌WPS Notes/Documents知识 |
| NEO4J部署复杂 | 中 | 高 | Docker本地实例 + fixture fallback |
| 治理过度, 每步要确认 | 中 | 中 | Trust Policy动态放权, 熟悉场景自动skip |
| 外部工具质量不稳定 | 中 | 中 | Capability Router按performance选最佳 |
| 多领域散精力 | 中 | 中 | 严格按Phase顺序, work域跑通再扩展 |
| Aetherforge集成复杂 | 低 | 高 | Phase 0只做最小wire(emit_event), 不改架构 |

---

## 8. 下一步

1. **写ADR**: 把本文档转为ADR-0389 (数字生命体架构)
2. **创建BET任务**: Phase 0的5个任务写入bet-ledger
3. **开始Phase 0**: MOS三表是Keystone, 一切从这里开始
4. **每个Phase完成写retro**: 锁定经验教训
