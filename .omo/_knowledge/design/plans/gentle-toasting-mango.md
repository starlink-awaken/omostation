# omostation Phase 17-25 多Phase执行计划

> 日期: 2026-06-02 | 基于 omostation-strategic-architecture-v2.1
> 治理框架: OMO 4-plane (control/truth/knowledge/delivery)
> 红队审计: 已完成并采纳修正

---

## Context

omostation已完成10器官从SharedBrain提取到kairon (Phase 11-16)。剩余9个活跃器官(~87K行, 466 BaseMembrane实例, 18个归档器官交叉引用)。系统健康分29.1 (raw 97.0 × debt_weight 0.3)，9项未解决OMO债务。

本计划基于v2.1战略架构文档及红队分析修正，采用OMO治理框架，分9个Phase逐步收敛至终态。

**关键红队修正已纳入:**
- SharedBrain双模架构(库+按需独立)
- 器官提取vs重写区分
- P17代码优先承诺
- P19拆分为3子Phase

---

## 终态目标

| 维度 | 现状 | 目标(P25) |
|------|------|----------|
| SharedBrain形态 | 9活跃器官, ~87K行 | sharedbrain-core(~5K库)+standalone(~2K按需) |
| kairon包数 | 26 | 28+ (新增observability, gc-engine, pontus) |
| gbrain | TypeScript+PG, 74tools | 不变 |
| Hermes Console | 不存在 | React+TS, MCP客户端 |
| BaseMembrane | 466实例 | 0 |
| Nucleus引用 | ~320 | 0(活跃代码) |
| 归档器官交叉引用 | 18文件 | 0 |
| 健康分 | 29.1 | 97.0 |
| OMO债务 | 9项未解决 | 7项resolved, 2项独立track |

---

## Phase 概览

| Phase | 名称 | 时间 | 关键产出 | 健康分 |
|:-----:|------|:----:|---------|:-----:|
| P17 | 架构治理基础 | 1周 | sharedbrain-core协议代码提交 | 29.1→34.0 |
| P18 | SharedBrain协议化 | 2周 | core库实现+回路引擎+神经元 | 34.0→48.5 |
| P19a-c | agentmesh渐进吸收 | 6周 | TS→Python迁移, 跨P19-P21 | 48.5→58.2 |
| P20 | 器官提取波1 | 3周 | 4简单器官提取 | 58.2→67.9 |
| P21 | 器官重写波2 | 5周 | 2复杂器官重写+2新包 | 67.9→72.8 |
| P22 | Pontus管线引擎 | 3周 | YAML DSL+DAG调度 | 72.8→77.6 |
| P23 | Hermes Console | 3周 | 知识仪表盘+Agent交互 | 77.6→87.3 |
| P24 | 深度解耦 | 3周 | BM清零+Nucleus替换 | 87.3→97.0 |
| P25 | 集成与收敛 | 2周 | E2E测试+文档+债务关闭 | 97.0 |

---

## Phase 17: 架构治理基础 [1周]

### 里程碑: M17 — sharedbrain-core/protocols/ 代码提交

**入口门控:**
- [x] Phase 16 completed
- [x] 10器官提取完成
- [x] 战略架构文档v2.1交叉审阅通过

### P17-W1: 战略文档交叉审阅与修订 [Day 1-2]
- **任务ID:** P17-W1-ARCHITECTURE-FOUNDATION (已存在, in_progress)
- **产出:** v2.1战略文档最终版, 20个架构决策文档化
- **验收:** 20/20决策有明确理由; 9器官迁移方案每项有可行步骤

### P17-W2: sharedbrain-core协议定义v1 [Day 3-5]
- **任务ID:** P17-W2-SHAREDBRAIN-PROTOCOLS-V1 (待更新)
- **关键产出(代码提交):**
  1. `kairon/packages/core-models/src/core_models/protocols/identity.py` — IdentityProtocol
  2. `kairon/packages/core-models/src/core_models/protocols/health.py` — HealthProtocol
  3. `kairon/packages/core-models/src/core_models/protocols/circuit.py` — CircuitProtocol + YAML Schema
  4. `kairon/packages/core-models/src/core_models/protocols/metrics.py` — MetricsProtocol
  5. `kairon/packages/core-models/src/core_models/protocols/governance.py` — GovernanceProtocol
  6. `kairon/packages/core-models/src/core_models/stem_cell.py` — 干细胞验证器(5接口定义)
- **验收:** 6个.py文件编译通过; ruff check通过; Python类型注解完整

### P17-W3: metaos差距分析 [Day 3-5, 与W2并行]
- **任务ID:** P17-W3-METAOS-GAP-ANALYSIS (已存在)
- **产出:** metaos各壳子模块(immune/gate/engine/governance/router) vs D_Immunity/D_Genesis需求的差距清单
- **验收:** 每个壳子模块有"缺什么"清单并按P0/P1/P2排列

### P17-W4: agentmesh能力清单 [Day 3-5, 与W2/W3并行]
- **任务ID:** P17-W4-AGENTMESH-AUDIT (已存在)
- **产出:** agentmesh 7包→kairon包映射文档; 重叠功能标记
- **验收:** 无遗漏能力映射; 浏览器/Edge能力明确标记(AR-5发现)

### P17 Exit Gate:
- [ ] sharedbrain-core协议代码已提交(kairon/core-models/protocols/)
- [ ] metaos差距清单完成
- [ ] agentmesh映射文档完成
- [ ] 债务: SB_PHASE17_PLAN → resolved
- [ ] P18-P25任务冻结审查(仅P18可unfreeze)

---

## Phase 18: SharedBrain协议化 [2周]

### 里程碑: M18 — sharedbrain-core库可导入使用

### P18-W1: NeuralCenter实现 [Day 1-4]
- **任务ID:** P18-W1-NEURAL-CENTER
- **产出:** `kairon/packages/core-models/src/core_models/neural_center.py`
  - 服务注册API, 服务发现API, 健康感知器, 信号路由器
- **验收:** ≥10服务注册并发测试; 路由延迟<10ms; 编译通过

### P18-W2: CircuitEngine实现 [Day 3-7, 与W1交叉]
- **任务ID:** P18-W2-CIRCUIT-ENGINE
- **产出:** `kairon/packages/core-models/src/core_models/circuit_engine.py`
  - .circuit YAML加载/解析; 状态机执行器; SLA超时检测; 断点续传
- **验收:** ≥2个回路定义加载并执行; DAG步骤依赖正确; 超时降级测试

### P18-W3: NeuronPool实现 [Day 6-8]
- **任务ID:** P18-W3-NEURON-POOL
- **产出:** `kairon/packages/core-models/src/core_models/neuron_pool.py`
  - BaseNeuron基类; 健康探测; 故障转移; 连接池复用
  - 神经元: identity-neuron, genesis-neuron, knowledge-neuron, monitoring-neuron, economy-neuron
- **验收:** 健康探测<5s; 故障转移自动切换; 连接池复用验证

### P18-W4: D_Window删除 + 归档引用解析 [Day 8-10]
- **任务ID:** P18-W4-CLEANUP-DWINDOW-REFS
- **产出:**
  1. `rm -rf organs/D_Window`, 更新INDEX.md
  2. 18个归档器官交叉引用 → 改为显式ArchivedOrganError
- **验收:** rg D_Window返回0; 18引用非静默None; SharedBrain编译通过

### P18 Exit Gate:
- [ ] sharedbrain-core可pip install导入
- [ ] D_Window已删除
- [ ] 归档引用已解析
- [ ] 债务: SB_ROOT_CLEANUP → resolved; SB_BRIDGE_FIX → resolved

---

## Phase 19: agentmesh渐进吸收 [6周, 跨P19-P21]

### 里程碑: M19 — agentmesh能力在kairon可用, TS代码可归档

**红队修正**: 原P19分配2周是数量级错误。拆分为3子Phase，回退策略保留直到P19c完成。

### P19a: 核心类型迁移 [Week 1-2]
- **任务ID:** P19-W1-AGENT-RUNTIME-ENHANCE (需更新)
- **产出:**
  1. agentmesh/core-types → core-models (Agent/Task/Tool/Capability等类型定义)
  2. 接口映射文档+功能对等验证
  3. Python类型通过mypy/pyright
- **验收:** 类型定义编译通过; agentmesh仍可独立运行(回退有效)

### P19b: 引擎能力迁移 [Week 3-4, 与P20并行]
- **任务ID:** (新任务)
- **产出:**
  1. agentmesh/engine → agent-runtime (任务调度/编排/message-bus/agent-runner)
  2. agentmesh/toolkit → forge (工具注册/发现/capability-discovery)
  3. 每模块功能对等测试
- **验收:** 功能对等测试≥70%; agentmesh仍可独立运行

### P19c: 网关与Hub迁移 [Week 5-6, 与P21并行]
- **任务ID:** P19-W2-AGENT-HUB-CREATE (待更新)
- **产出:**
  1. agentmesh/gateway → agora (MCP网关, 重叠功能合并)
  2. agentmesh/agents → agent-hub (Agent注册/发现/注销)
  3. agentmesh/model-orchestrator → llm-gateway (模型编排)
  4. TS代码归档到_archived/agentmesh/
- **验收:** MCP工具数不减少; 确认Agent浏览器/Edge能力未丢失(AR-5发现)

### P19 Exit Gate:
- [ ] agentmesh 7包全部迁移+验证
- [ ] agent-runtime, agent-hub, forge, llm-gateway测试≥70%
- [ ] TS代码归档完成
- [ ] 回退策略关闭(确认不再需要)

---

## Phase 20: 器官提取波1 [3周]

### 里程碑: M20 — 4个简单器官提取完成

### P20-W1: D_Economy→eu-pricing [Day 1-3]
- **策略:** 提取(已验证可行)
- **产出:** eu-pricing/ledger.py(能量账本), eu-pricing/reputation.py, eu-pricing/market.py
- **BM清理:** 23文件→0
- **验收:** 测试≥70%; 编译通过+ruff check

### P20-W2: D_KnowledgeIntegration→kos [Day 4-7]
- **策略:** 提取(已验证可行)
- **产出:** kos/query_service.py, kos/context_injector.py, kos/freshness.py, kos/pattern_extractor.py
- **关键依赖:** 9个D_Memory懒引用→eidos/gbrain解析
- **验收:** 0个D_Memory引用; 测试≥70%; 回路<200ms

### P20-W3: D_Extension→forge [Day 6-8]
- **策略:** 提取(已验证可行)
- **产出:** forge/skill_extractor.py, forge/adapters/, forge/ratings.py
- **验收:** 编译通过+ruff check

### P20-W4: D_Harness→各包tests/ [Day 7-10]
- **策略:** 提取(最小器官, BM密度最高2.7/文件但可清理)
- **产出:** shared-lib/testing.py, shared-lib/snapshot.py, shared-lib/validation.py
- **BM清理:** 9文件→0
- **验收:** BM=0; 测试工具在各包可复用

### P20 Exit Gate:
- [ ] 4器官归档完成
- [ ] BM降至<200
- [ ] 各目标包测试≥70%

---

## Phase 21: 器官重写波2 [5周]

### 里程碑: M21 — 2复杂器官重写+2新包+observability/gc-engine上线

### P21-W1: D_Immunity→metaos(重写) [Day 1-8]
- **策略:** 重写(深度Z-Spore/Z-Microkernel耦合, 不可提取)
- **产出:** metaos/core/immune.py(RBAC+指纹+威胁检测), metaos/core/gate.py(身份+决策门控)
- **归档:** 量子安全/联邦信任→归档
- **协议:** identity_verify.circuit, identity-neuron
- **验收:** 身份回路<50ms p99; 威胁检测回路<200ms; BM: 145→0

### P21-W2: D_Genesis三向重写 [Day 3-12]
- **策略:** 重写(最复杂多向分散)
- **产出:**
  1. metaos/core/engine.py: 起源引导+生命周期管理
  2. agent-runtime/self_healing.py: 自愈执行器
  3. minerva: 进化反馈模块
- **回路:** self_healing.circuit, genesis-neuron
- **归档:** 原型管理/遗传算法/联邦进化
- **验收:** 自愈回路<5s; 3模块编译通过; BM: 82→0

### P21-W3: observability包新建 [Day 10-15]
- **任务ID:** P21-W3-OBSERVABILITY-CREATE
- **新建包:** kairon/packages/observability/
  - slo.py, alerts.py, metrics.py, health.py, dashboard.py
- **验收:** 编译通过; 告警Webhook测试; BM: 85→0

### P21-W4: gc-engine包新建 [Day 13-17]
- **任务ID:** P21-W4-GC-ENGINE-CREATE
- **新建包:** kairon/packages/gc-engine/
  - gc_core.py, excretion.py, distillation.py, retention.py
- **验收:** 编译通过; 测试≥70%; BM: 50→0

### P21 Exit Gate:
- [ ] 2重写+2提取+2新包完成
- [ ] SharedBrain活跃器官: 9→0(全部归档)
- [ ] BM降至<50

---

## Phase 22: Pontus管线引擎 [3周]

### 里程碑: M22 — 知识摄取规模化

### P22-W1: YAML DSL + DAG调度器 [Day 1-7]
- **新建包:** kairon/packages/pontus/
- **产出:** 管线定义YAML DSL; DAG依赖解析+拓扑排序; 并行执行引擎
- **验收:** ≥2管线模板可执行; DAG调度正确

### P22-W2: 数据质量 + 断点续传 [Day 6-15]
- **产出:** 断点续传; 格式校验+类型检查; 跨源实体去重; 源可信度评分
- **验收:** 断点恢复测试; 去重准确率>95%

---

## Phase 23: Hermes Console v1 [3周]

### 里程碑: M23 — 统一用户界面可用

### P23-W1: 项目骨架 + MCP客户端 [Day 1-7]
- **新项目:** projects/hermes-console/ (React+TypeScript+bun)
- **产出:** MCP客户端基础设施(连接池+缓存); 路由+组件树; agora集成
- **验收:** bun run dev可启动; MCP客户端发现≥10工具

### P23-W2: 仪表盘 + 面板 [Day 5-15]
- **产出:** 知识图谱可视化(D3/Cytoscape); Agent对话+任务管理; 系统健康仪表盘
- **验收:** 知识图谱交互浏览; Agent对话收发; 健康状态实时刷新

---

## Phase 24: 深度解耦 [3周]

### 里程碑: M24 — BaseMembrane清零+Nucleus替换

### P24-W1: BaseMembrane清零 [Day 1-10]
- **产出:** rg BaseMembrane在活跃代码返回0; 466实例→0
- **验收:** 测试通过率不退化; 编译无错误

### P24-W2: Nucleus替换 [Day 8-15]
- **产出:** 320引用→Agora事件总线(wksp://events)+pathlib
- **验收:** 0个nucleus引用; 事件总线通信测试通过
- **注意:** L3风险, 需人工审批

---

## Phase 25: 集成与收敛 [2周]

### 里程碑: M25 — 全系统验证+债务关闭

### P25-W1: E2E集成测试 [Day 1-7]
- **产出:** 4契约验证; 自愈回路完整演练; 性能基准报告
- **验收:** 自愈<5s; 知识查询<200ms; 身份验证<50ms

### P25-W2: 文档终稿+债务关闭 [Day 5-10]
- **产出:** SharedBrain README更新; PROJECTS.yaml更新; 5项债务→resolved
- **验收:** 健康分=97.0; make test-fast全绿; ruff check全绿

---

## OMO集成

### 任务创建规范
每个Phase任务按 `.omo/tasks/active/{phase}-{wave}.yaml` 命名，包含:
- entry_gate (前置条件)
- risk_level + allowed_operation_level
- evidence_required (交付证据)
- acceptance_criteria (验收标准)
- depends_on (依赖任务)

### 债务更新计划
| 债务ID | 解决Phase | 动作 |
|--------|:--------:|------|
| SB_PHASE17_PLAN | P17 | resolved |
| SB_ROOT_CLEANUP | P18 | resolved |
| SB_BRIDGE_FIX | P18 | resolved |
| SB_DECOMPOSITION | P21 | resolved (所有器官已归档) |
| SB_PROJECTS_YAML | P25 | resolved |
| SB_UNTESTED_PKGS | P25 | improved |
| SB_ORPHANED_TASKS | P25 | improved |
| D2_CI_E2E | 独立track | pending |
| D3_EU_PRICING | 独立track | pending |

### 健康分轨迹
29.1(P16) → 34.0(P17) → 48.5(P18) → 58.2(P19) → 67.9(P20) → 72.8(P21) → 77.6(P22) → 87.3(P23) → 97.0(P24) → 97.0(P25)

### 代码优先承诺
- P17完成标准 = 协议.py文件提交(非文档审阅)
- P18+任务冻结为pending直到P17产出代码
- 不再创建新task YAML直到P17 Exit Gate通过

---

## 风险矩阵

| # | 风险 | 概率 | 影响 | Phase | 缓解 |
|---|------|:----:|:----:|:-----:|------|
| R1 | D_Immunity重写破坏安全能力 | 低 | 高 | P21 | 先定义协议再重写; 保留参考实现 |
| R2 | agentmesh TS逻辑遗漏 | 中 | 中 | P19 | 能力清单逐项验证; 回退策略 |
| R3 | P19跨语言迁移超时 | 高 | 中 | P19a-c | 6周拆分; 每2周可验证里程碑 |
| R4 | BM清理引入回归 | 中 | 低 | P24 | 每文件清理后编译+测试 |
| R5 | Nucleus替换破坏通信 | 中 | 高 | P24 | 并行运行Agora+nucleus再切流 |
| R6 | Hermes Console MCP性能 | 中 | 中 | P23 | 连接池+缓存; 纯MCP不直连DB |
| R7 | Agent浏览器能力丢失 | 中 | 中 | P19c | 明确标记; 迁移后验证 |
| R8 | 计划替代执行(治理戏剧) | 高 | 高 | P17 | 代码优先; P17无代码=未完成 |

---

## 验证方法

每个Phase Exit Gate验证:
1. `python -m py_compile` — 所有修改文件
2. `ruff check` — 代码规范
3. `make test-fast` — 回归测试(不退化)
4. OMO debt ledger更新 — 债务状态同步
5. 交叉审阅 — 至少1人审阅关键变更

P25终态验证:
1. `make test-fast` 全绿
2. `ruff check` 全绿  
3. 4契约E2E测试通过
4. `rg BaseMembrane` 活跃代码=0
5. `rg 'from nucleus\.'` 活跃代码=0
6. 健康分=97.0
