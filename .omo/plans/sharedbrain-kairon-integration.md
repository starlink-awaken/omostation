# SharedBrain × kairon 融合实施计划

> 日期: 2026-05-29 | 状态: 待确认 | 关联: architecture-v4-4-plus-1-plus-3-plus-i.md

## 最终态架构图

```
用户 ──→ CLI (bos / wksp / gstack / pallas)
                   │
    ┌──────────────▼──────────────────┐
    │     Agora Service Mesh (I0)     │
    │  统一发现 / 路由 / 熔断 / 管线   │
    │  协议: MCP / REST / BOS-URI     │
    └─┬────────────┬────────────┬────┘
      │            │            │
      ▼            ▼            ▼
 ┌─────────┐ ┌──────────┐ ┌──────────┐
 │SharedBrain│ │  kairon  │ │ agentmesh│
 │ 运行内核  │ │ 知识栈   │ │ agent运行时│
 │          │ │          │ │ (TS)     │
 │ EU经济   │ │ kronos   │ │          │
 │ 数字免疫 │ │ minerva  │ └──────────┘
 │ 器官演化 │ │ sophia   │
 │ 合规控制 │ │ ontoderive│     . . . gbrain, gstack 等
 │ identity │ │ eidos    │
 │ BOS路由  │ │ kos      │
 │ 语音处理 │ │ SSOT     │
 └────┬─────┘ └─────┬────┘
      │             │
      └──────┬──────┘
             │
    ┌────────▼──────────┐
    │   共享数据平面      │
    │  • core-models     │
    │  • eidos adapters  │
    │  • SSOT domains    │
    │  • pipeline:json   │
    └───────────────────┘
```

---

## Phase A — 协议桥接（预计 2 天）

### 目标
让 Agora 成为两个系统的统一 MCP 服务网格，任何项目通过 Agora 发现和调用所有 MCP 工具。

### 任务

#### A1 — SharedBrain MCP 注册到 Agora
- **文件**: `kairon/packages/agora/registry.yaml` + `SharedBrain/config/agora-registry.yaml`
- **内容**:
  - 将 SharedBrain 的 12 个 MCP 工具注册到 Agora registry
  - 端点: `mcp://sharedbrain:7421/sse` (SSE) + `mcp://sharedbrain:7420/stdio`
  - 命名空间: `sharedbrain/` 前缀（如 `sharedbrain/memory_search`, `sharedbrain/task_submit`）
- **验证**: `agora registry list` 包含 SharedBrain 条目

#### A2 — SharedBrain 侧配置 Agora 为 MCP 网关
- **文件**: `SharedBrain/config/agora-client.yaml`
- **内容**:
  - SharedBrain 的 `D-Gateway` 将 agora 注册为上游 MCP 网关
  - 所有对外调用走 `mcp://agora/` 路径
- **验证**: SharedBrain 通过 agora 调用 `minerva/research` 成功

#### A3 — 连通性验证
- **文件**: `SharedBrain/tests/integration/test_agora_bridge.py` (新建)
- **验证场景**:
  1. `agora → sharedbrain/memory_search`: kairon 调用 SharedBrain D-Memory 搜索
  2. `sharedbrain → agora → minerva/research`: SharedBrain 调用 kairon 研究引擎
  3. `sharedbrain → agora → eidos/validate`: SharedBrain 通过 kairon 验证 organ 数据 Schema
- **期望**: 3/3 端到端调用成功

### Phase A 完成标准
- [ ] Agora registry 包含 12 个 SharedBrain MCP 工具
- [ ] SharedBrain 通过 Agora 成功调用至少 1 个 kairon 工具
- [ ] kairon 通过 Agora 成功调用至少 1 个 SharedBrain 工具
- [ ] 新增集成测试 3/3 PASS

---

## Phase B — 数据统一（预计 1 周）

### 目标
两个系统共享统一数据模型和双向数据流，零数据孤岛。

### 任务

#### B1 — core-models 导入 SharedBrain Z-Spore
- **文件**: 
  - `kairon/packages/core-models/entity.py` → `SharedBrain/nucleus/Z-Spore/archetypes/entity_v1.py` (新建)
  - `kairon/packages/core-models/relation.py` → `SharedBrain/nucleus/Z-Spore/archetypes/relation_v1.py` (新建)
  - `kairon/packages/core-models/knowledge_graph.py` → `SharedBrain/nucleus/Z-Spore/archetypes/knowledge_graph_v1.py` (新建)
- **内容**: 将 kairon 的 Entity/Relation/KnowledgeGraph/Provenance 核心模型复制为 SharedBrain Z-Spore archetype
- **约束**: 保持 Z-Spore 的 5 层验证链（Token → Variant → Specification → Instantiation → Execution），不破坏 SharedBrain 的核心架构
- **验证**: SharedBrain import 核心模型成功，无循环依赖

#### B2 — eidos→SharedBrain 反向适配器
- **文件**: `kairon/packages/eidos/src/eidos/adapters/eidos_to_bos.py` (新建, ~200 行)
- **内容**:
  ```python
  class EidosToBosAdapter:
      """将 kairon 知识卡片写入 SharedBrain D-Memory"""
      def knowledge_cards_to_bos_memory(cards: list[KnowledgeCard], target: str)
      def derivation_result_to_bos_loop(task_id: str, result: DerivationResult)
      def index_to_bos_factgraph(index_entries: list[IndexEntry])
  ```
- **依赖**: Phase A 完成（通过 Agora 调用 SharedBrain MCP）
- **验证**: 单测 5+ cases，kairon 知识能写入 SharedBrain HoloMemory

#### B3 — SharedBrain organ 数据批量入 kos index
- **文件**: `kairon/packages/eidos/src/eidos/adapters/sharedbrain.py` (增强现有, +~300 行)
- **内容**:
  - 新增 `batch_organs_to_kos_index()` — 扫描 SharedBrain 所有活跃 organ，生成 kos Entity 索引
  - 新增 `organ_identity_to_agent_registry()` — 将 identity_bridge 映射导入 agent-runtime
  - 新增增量同步逻辑（对比 SHA-256，只同步变更的 organ）
- **验证**: 10 个活跃 organ × 20 实体 = 200+ 实体成功入 kos index

#### B4 — SSOT 域注册 + 共享数据平面
- **文件**:
  - `kairon/packages/ssot/domains/sharedbrain.yaml` (新建)
  - `kairon/packages/ssot/domains/sharedbrain_schemas/` (新建)
- **内容**:
  - 注册 `sharedbrain.organ` 为 SSOT 事实源域
  - 定义 organ 数据结构 Schema（名称·状态·基类·端口·依赖）
  - 配置 kairon→SharedBrain 数据流规则（冲突时：SharedBrain 为权威源）
- **验证**: SSOT validate 通过，SharedBrain domain 数据一致性检查通过

### Phase B 完成标准
- [ ] core-models Entity/Relation/KnowledgeGraph 成功导入 Z-Spore
- [ ] 反向适配器（kairon → SharedBrain）5+ 单测 PASS
- [ ] 正向适配器（SharedBrain organs → kos index）200+ 实体入库
- [ ] SSOT SharedBrain domain 注册 + Schema 验证通过
- [ ] 双向数据同步（增量）测试 PASS

---

## Phase C — 能力融合（预计 2-4 周）

### 目标
SharedBrain 轻量化：重叠域从 kairon 获取能力，同时将独有能力开放给 kairon。

### 子阶段 C1 — SharedBrain 去重（1 周）

#### C1a — D-Harvest（知识摄取）→ kronos
- **当前状态**: D-Harvest 提供 web scrape / document parse / RSS feed 等
- **目标**: 关闭 D-Harvest 的活跃器官，所有摄取走 kronos
- **操作**:
  1. D-Harvest 各 organ 调用改为 `mcp://agora/kronos/` 包装层
  2. kronos 新增 `feed_ingest` 工具（RSS/Atom → pipeline:json）
  3. D-Harvest 测试迁移到 kronos 集成测试
  4. D-Harvest 器官标记 `status: delegated`（不删除，保留代码）
- **验证**: 现有 D-Harvest 场景通过 kronos 完成摄取

#### C1b — D-KnowledgeIntegration → minerva + ontoderive
- **当前状态**: D-KnowledgeIntegration 提供 FactGraph + RAG + embedding search
- **目标**: 关闭自有的知识处理管线，调用 kairon
- **操作**:
  1. FactGraph 查询改为 `mcp://agora/minerva/search`
  2. embedding search 改为 `mcp://agora/kos/search`
  3. 知识积分逻辑改为 `mcp://agora/ontoderive/derive`
  4. D-KnowledgeIntegration 器官标记 `status: delegated`
- **验证**: 端到端知识检索链路（query → agora → minerva/kos → 返回）

#### C1c — D-Gateway P2P → agora + eidos
- **当前状态**: D-Gateway 有 Kademlia DHT P2P 发现 + MCP 暴露 + 连接池
- **目标**: P2P 发现部分废弃，连接池保留，MCP 暴露保留但注册到 Agora
- **操作**:
  1. 删除 `organs/D_Gateway/organs/p2p_discovery.py`
  2. 删除 `organs/D_Gateway/organs/kademlia_dht.py`
  3. MCP server 改为注册到 Agora（已在 Phase A 完成）
  4. 连接池保留（SharedBrain 内部使用）
- **验证**: SharedBrain 不再有 P2P 相关代码（或标记 deprecated）

#### C1d — D-Monitoring Prometheus → agora/metrics
- **当前状态**: D-Monitoring 有独立的 Prometheus + Grafana 暴露
- **目标**: 指标统一上报到 agora/metrics 中间件
- **操作**:
  1. D-Monitoring 的 `unified_metrics_facade.py` 增加 `push_to_agora` 模式
  2. agora 的 metrics 中间件接收 SharedBrain 的指标推送
  3. 去重（不重复暴露两个 Prometheus 端点）
- **验证**: SharedBrain 指标出现在 agora Prometheus 面板

### 子阶段 C2 — kairon 获取 SharedBrain 独有能力（1 周）

#### C2a — EU 计价接入 kairon pipeline
- **背景**: SharedBrain D-Economy 有 EU（Energy Unit）虚拟资源会计系统，器官按调用次数/数据量/CPU 时间消耗 EU
- **目标**: kairon pipeline（minerva→ontoderive→eidos）的每一步消耗 EU 计价
- **文件**: `kairon/packages/agora/src/agora/middleware/eu_pricing.py` (新建, ~150 行)
- **内容**:
  ```python
  class EUPricingMiddleware:
      """每次 MCP 调用消耗 EU，EU 余额不足则熔断"""
      def on_request(self, tool: str, caller: str) -> EUCost
      def on_response(self, tool: str, cost: EUCost)
      def check_balance(self, caller: str) -> EUBalance
  ```
- **依赖**: Phase A 完成（通过 Agora 调用 SharedBrain EU）
- **验证**: minerva research 一次完整调用消耗 N EU，余额不足时返回 402

#### C2b — 免疫审计接入 minerva 研究流
- **背景**: SharedBrain D-Immunity 有 `immunity_audit()` 工具，对内容做语义审计（异常检测、隐私泄露、政策违规）
- **目标**: minerva 研究结果在入库前经过免疫审计
- **文件**: `kairon/packages/minerva/src/minerva/pipeline/immune_audit.py` (新建, ~100 行)
- **内容**:
  ```python
  class ImmuneAuditStage:
      """pipeline:json chain 的免疫审计阶段"""
      def execute(self, cards: list[KnowledgeCard]) -> list[KnowledgeCard]:
          for card in cards:
              result = agora.dispatch("sharedbrain/immunity/audit", card)
              if result.risk == "HIGH":
                  card.flag("immune_review_required")
          return cards
  ```
- **验证**: 高风险知识自动标记，防止直接入库

#### C2c — 器官自愈规则接入 forge/entropy
- **背景**: SharedBrain D-Genesis 的 `self_healing_engine.py` 监控器官异常并触发自愈
- **目标**: forge 的 entropy 监控检测到器官异常时，触发 SharedBrain 自愈
- **文件**:
  - `kairon/packages/forge/src/forge/entropy/healing_trigger.py` (新建, ~100 行)
  - `kairon/packages/forge/src/forge/entropy/rules/sharedbrain_organ_health.yaml` (新建)
- **内容**:
  ```python
  class SharedBrainHealingTrigger:
      """entropy 检测到异常 → 触发 SharedBrain organ 自愈"""
      RULES = {
          "organ_timeout": "sharedbrain/genesis/heal --organ {organ} --reason timeout",
          "organ_memory_leak": "sharedbrain/genesis/heal --organ {organ} --reason memory",
          "organ_cpu_spike": "sharedbrain/genesis/cool-down --organ {organ}"
      }
  ```
- **验证**: forge entropy 监控检测异常 → 自愈触发 → SharedBrain organ 恢复

### 子阶段 C3 — 身份映射统一（3 天）

#### C3a — identity_bridge → agent-runtime
- **背景**: SharedBrain identity_bridge 管理 AgentRole → A1 agent_identity 映射；kairon agent-runtime 有 engine/identity 模块
- **目标**: 统一身份源，identity_bridge 为权威 A1 身份提供者，agent-runtime 消费
- **文件**:
  - `kairon/packages/agent-runtime/src/agent_runtime/engine/identity/providers/sharedbrain.py` (新建, ~200 行)
  - `SharedBrain/identity_bridge/adapters/agent_runtime_adapter.py` (新建, ~100 行)
- **内容**:
  - agent-runtime 通过 Agora 查询 identity_bridge 获取 AgentRole
  - identity_bridge 的 AgentRole → agent-runtime 的 AgentIdentity 映射
  - 双向同步：identity_bridge 变更 → agent-runtime 更新；agent-runtime 新建 Agent → identity_bridge 注册
- **验证**: agent-runtime 创建 Agent 后，SharedBrain identity_bridge 可见；反之亦然

### Phase C 完成标准
- [ ] D-Harvest 所有场景通过 kronos 完成（标记 delegated，不删代码）
- [ ] D-KnowledgeIntegration 调用迁移到 minerva/kos/ontoderive
- [ ] D-Gateway P2P 代码删除或标记 deprecated
- [ ] D-Monitoring 指标统一到 agora/metrics
- [ ] EU 计价中间件在 Agora 工作（pipeline 每一步有 EU 成本）
- [ ] minerva 研究结果经免疫审计后再入库
- [ ] forge entropy 检测异常 → SharedBrain 自愈触发
- [ ] identity_bridge ↔ agent-runtime 身份双向同步
- [ ] SharedBrain 测试 16,676 仍 PASS（或被标记 delegated 的 14,000+ 通过）
- [ ] kairon 新增测试 ~50 PASS

---

## 验收标准（总）

| 维度 | 当前 | 目标 | 验收方式 |
|------|------|------|----------|
| 协议统一 | 各自有 MCP，无互相调用 | Agora 统一路由，双方 MCP 互调 | `agora registry list` + e2e test |
| 数据统一 | 独立 schema，无同步 | core-models 共享，双向适配器运行 | SSOT validate + 增量同步测试 |
| 能力去重 | 6 个域重叠 | 2 个域重叠（Execution + Memory） | SharedBrain 3 organ delegated |
| 能力互补 | EU/免疫/演化独享 | kairon 也可用 | pipeline EU 计价 + 免疫审计 |
| SharedBrain 测试 | 16,676 | ≥ 14,000（减去 delegated 测试） | pytest |
| kairon 测试 | 待确认 | +50 新增 | pytest |
| 架构违规 | 无 | 无反向 import | arcnode 验证 |

---

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| SharedBrain Python 3.14 vs kairon 3.10 版本差异 | 🔴 高 | Phase A/B 走 MCP 协议（语言无关），Phase C 适配器在 kairon 侧用 3.10 实现 |
| organ delegated 后 SharedBrain 行为退化 | 🟡 中 | 保留原代码（标记 delegated 不删），提供降级开关 |
| Agora 成为单点故障 | 🟡 中 | Agora 已有 degrade 模式；双方也保留直连 MCP 端点作为 fallback |
| 双向同步一致性问题 | 🟡 中 | SSOT 注册 SharedBrain domain 为权威源，冲突时优先 |
| 测试量过大难以维持 | 🟢 低 | delegated 的测试只验证桥接层，不运行原完整测试 |

---

## 执行顺序依赖

```
Phase A (协议桥接)
  └─→ Phase B (数据统一)
        ├─→ Phase C1 (去重) ──→ Phase C2 (互补) ──→ Phase C3 (身份)
        │                              │
        │   C1a D-Harvest→kronos       C2a EU 计价
        │   C1b D-KI→minerva           C2b 免疫审计
        │   C1c D-Gateway P2P→agora    C2c 器官自愈→forge
        │   C1d D-Monitoring→agora
        │
        └─→ B3 (SSOT 注册) ← 依赖 C1 完成后 organ 状态变更
```

Phase A 完成后，B 和 C 可以部分并行：
- B1/B2/B4 不依赖 A2（core-models 导入后即可开发）
- C1 各子任务相互独立，可并行
- C2 依赖 A2 + B2（需 Agora 连通 + 适配器就绪）
- C3 依赖 B3（需 identity_bridge 数据已入 kos index）
