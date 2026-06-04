# SharedBrain × kairon 融合实施计划

> 日期: 2026-05-29 | 版本: v2.0 | 状态: 已评审修改
> 评审: Momus (reluctant-teal-halibut) | 关联: architecture-v4-4-plus-1-plus-3-plus-i.md

## 评审修订摘要

| # | 修订来源 | 变更内容 |
|---|----------|----------|
| 1 | 🔴 架构违规 | C2a EU 定价从 `agora/middleware/` → 新建 `kairon/packages/eu-pricing/` (L2)，Agora 仅路由 |
| 2 | 🔴 前提矛盾 | B1 "复制" → "PyPI 安装 + Z-Spore 薄适配器"，符合 `convergence.yaml` |
| 3 | 🔴 循环依赖 | B3 拆为 B3a (基础 SSOT Schema, Phase B) + B3b (最终 organ 状态同步, C1 之后) |
| 4 | 🟠 风险过高 | C1 从并行委托 → 串行委托 C1d→C1c→C1a→C1b，每步有验证期 |
| 5 | 🟠 基础设施缺失 | 新增 Phase A-0 集成测试环境 (Docker Compose + CI) |
| 6 | 🟠 无序操作 | 所有 Phase 间新增 Go/No-Go 关卡 |
| 7 | 🟠 无降级测试 | 每个委托器官新增降级/回退测试 |
| 8 | 🟠 Python 版本 | 明确决策：kairon 升级到 Python ≥3.12（中间态），Phase C 结束后评估 3.14 |

---

## 最终态架构图

```
用户 ──→ CLI (bos / wksp / gstack / pallas)
                   │
    ┌──────────────▼──────────────────┐
    │     Agora Service Mesh (I0)     │
    │  统一发现 / 路由 / 熔断 / 管线   │
    │  协议: MCP / REST / BOS-URI     │
    │  ⚠️ I0 只路由，不承载业务逻辑     │
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
 │          │ │ eu-pricing│ ← 新增 L2
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

## Phase A-0 — 集成基础设施（Day 0，预计半天）

### 目标
建立统一的集成测试环境，所有后续 Phase 的测试都运行在此环境中。

### 任务

#### A0.1 — Docker Compose 集成环境
- **文件**: `SharedBrain/tests/integration/docker-compose.yml` (新建)
- **内容**:
  ```yaml
  services:
    agora:       { image: kairon-agora, port: 7430 }
    sharedbrain: { image: sharedbrain-bos, port: 7421, depends_on: [agora] }
    kairon-kos:  { image: kairon-kos, depends_on: [agora] }
    kairon-eidos:{ image: kairon-eidos, depends_on: [agora] }
    minerva:     { image: kairon-minerva, depends_on: [agora] }
  ```
- **验证**: `docker compose up --wait` 所有 5 服务 healthy

#### A0.2 — CI 集成管道
- **文件**: `.github/workflows/sharedbrain-kairon-integration.yml` (新建)
- **内容**: 构建两个项目 → 启动 Compose → 运行集成测试 → 导出日志
- **验证**: CI 绿色通过

#### A0.3 — 性能基线采集
- **文件**: `SharedBrain/tests/integration/baseline_latency.py` (新建)
- **内容**: 分别在集成前记录 SharedBrain 和 kairon 的本地调用延迟基线
- **验证**: 基线数据写入 `SharedBrain/tests/integration/baselines/`

### Phase A-0 完成标准
- [ ] Docker Compose 5 服务全部 healthy
- [ ] CI 管道绿色通过
- [ ] 性能基线数据采集完成

---

## Phase A — 协议桥接（预计 2 天）

### 目标
让 Agora 成为两个系统的统一 MCP 服务网格，任何项目通过 Agora 发现和调用所有 MCP 工具。

### Go/No-Go 前置条件
- [x] Phase A-0 完成（Docker Compose + CI + 基线）

### 任务

#### A1 — SharedBrain MCP 注册到 Agora
- **文件**: `kairon/packages/agora/registry.yaml` + `SharedBrain/config/agora-registry.yaml`
- **内容**:
  - 将 SharedBrain 的 12 个 MCP 工具注册到 Agora registry
  - 端点: `mcp://sharedbrain:7421/sse` (SSE) + `mcp://sharedbrain:7420/stdio`
  - 命名空间: `sharedbrain/` 前缀（如 `sharedbrain/memory_search`, `sharedbrain/task_submit`）
  - 健康检查：注册前验证 SharedBrain MCP 端口可达
- **验证**: `agora registry list` 包含 SharedBrain 条目，健康检查通过

#### A2 — SharedBrain 侧配置 Agora 为 MCP 网关
- **文件**: `SharedBrain/config/agora-client.yaml`
- **内容**:
  - SharedBrain 的 `D-Gateway` 将 agora 注册为上游 MCP 网关
  - 所有对外调用走 `mcp://agora/` 路径
  - 配置超时: 10s（默认）, 重试: 2 次, 断路器: 5 次失败 → open 30s
- **验证**: SharedBrain 通过 agora 调用 `minerva/research` 成功

#### A3 — 连通性验证（含故障场景）
- **文件**: `SharedBrain/tests/integration/test_agora_bridge.py` (新建)
- **快乐路径测试**:
  1. `agora → sharedbrain/memory_search` — kairon 调用 SharedBrain D-Memory
  2. `sharedbrain → agora → minerva/research` — SharedBrain 调用 kairon
  3. `sharedbrain → agora → eidos/validate` — SharedBrain 通过 kairon 验证
- **故障路径测试**:
  4. Agora 宕机时 SharedBrain MCP 调用超时（验证 10s 超时）
  5. kairon 服务不可达时返回清晰错误（验证降级日志）
  6. 断路器触发后恢复（验证 open → half-open → closed）
- **期望**: 3/3 快乐路径 + 3/3 故障路径通过

### Phase A Go/No-Go 关卡
- [ ] Agora registry 包含 12 个 SharedBrain MCP 工具
- [ ] SharedBrain 通过 Agora 成功调用 ≥1 个 kairon 工具
- [ ] kairon 通过 Agora 成功调用 ≥1 个 SharedBrain 工具
- [ ] 所有 6 个集成测试（3 快乐 + 3 故障）PASS
- 🚦 **失败则终止** — MCP 桥是后续所有工作的先决条件

---

## Phase B — 数据统一（预计 1 周）

### 目标
两个系统共享统一数据模型和双向数据流，零数据孤岛。

### Go/No-Go 前置条件
- [x] Phase A 关卡通过

### 任务

#### B1 — core-models 通过 PyPI 引入 SharedBrain Z-Spore 适配器
- **策略变更**: 原方案"复制"core-models → 改为 **PyPI 安装 + Z-Spore 薄适配器**，符合 `convergence.yaml` 第 7 行约定
- **操作**:
  1. kairon 发布 `kairon-core-models` 到 PyPI（或本地索引）
  2. SharedBrain `pyproject.toml` 添加 `kairon-core-models` 依赖
  3. 新建 Z-Spore 薄适配器（非复制，仅类型映射）:
     - `SharedBrain/nucleus/Z-Spore/archetypes/entity_adapter.py` → 将 `kairon_core_models.Entity` 映射为 Z-Spore Entity
     - `SharedBrain/nucleus/Z-Spore/archetypes/relation_adapter.py`
     - `SharedBrain/nucleus/Z-Spore/archetypes/knowledge_graph_adapter.py`
- **约束**: 保持 Z-Spore 的 5 层验证链（Token → Variant → Specification → Instantiation → Execution），不破坏 SharedBrain 的核心架构
- **验证**: `pip install kairon-core-models` 成功，适配器 import 无循环依赖
- **模型漂移防护**: kairon core-models 发新版本时，适配器自动标记 `needs_review`（通过版本号对比）

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

#### B3a — SharedBrain organ 数据批量入 kos index + SSOT 基础 Schema 注册
- **文件**: 
  - `kairon/packages/eidos/src/eidos/adapters/sharedbrain.py` (增强现有, +~300 行)
  - `kairon/packages/ssot/domains/sharedbrain.yaml` (新建)
- **内容**:
  - 增强正向适配器: `batch_organs_to_kos_index()` — 扫描 SharedBrain 所有活跃 organ，生成 kos Entity 索引
  - 增强正向适配器: `organ_identity_to_agent_registry()` — 将 identity_bridge 映射导入 agent-runtime
  - 增量同步逻辑（对比 SHA-256，只同步变更的 organ）
  - SSOT 注册 `sharedbrain.organ` 为 SSOT 事实源域
  - 定义 organ 数据结构 Schema（名称·状态·基类·端口·依赖）
  - 配置冲突规则：SharedBrain 为权威源
- **验证**: 
  - 10 个活跃 organ × 20 实体 = 200+ 实体成功入 kos index
  - SSOT validate 通过

#### B3b — 最终 organ 状态同步（Phase C1 之后执行）
- **依赖**: C1 完成后 organ 状态变更（delegated 标记）
- **内容**: 将 C1 中标记的 delegated/removed 器官状态同步到 SSOT + kos index
- **验证**: SSOT 中的 organ 状态与 SharedBrain 实际状态一致

### Phase B Go/No-Go 关卡
- [ ] core-models 通过 PyPI 成功引入 SharedBrain，适配器 import 通过
- [ ] 反向适配器（kairon → SharedBrain）5+ 单测 PASS
- [ ] 正向适配器（SharedBrain organs → kos index）200+ 实体入库
- [ ] SSOT SharedBrain domain Schema 验证通过
- [ ] 双向数据同步（增量）测试 PASS
- 🚦 **通过后 Phase C 才可开始**

---

## Phase C — 能力融合（预计 3-5 周）

### 目标
SharedBrain 轻量化：重叠域从 kairon 获取能力，同时将独有能力开放给 kairon。

### Go/No-Go 前置条件
- [x] Phase B 关卡通过

---

### 子阶段 C1 — SharedBrain 去重（~2 周，串行执行）

> ⚠️ 串行委托策略：一次只委托一个器官，每步有验证期。而非原方案的 4 个同时。

#### C1d — D-Monitoring → agora/metrics（第 1 步，最低风险）
- **为什么先做**: 纯上报，无业务逻辑风险。验证 Agora 桥的稳定性。
- **操作**:
  1. D-Monitoring 的 `unified_metrics_facade.py` 增加 `push_to_agora` 模式
  2. agora 的 metrics 中间件接收 SharedBrain 的指标推送
  3. 去重（不重复暴露两个 Prometheus 端点）
- **降级开关**: `DMonitoringFallback`: 当 agora/metrics 不可达时，回退到本地 Prometheus 暴露
- **降级测试**: `test_degrade_monitoring_fallback()` — 模拟 agora 500 → 验证回退到本地
- **验证**: SharedBrain 指标出现在 agora Prometheus 面板 + 降级测试 PASS
- **验证期**: 至少 1 天运行观察

#### C1c — D-Gateway P2P → agora（第 2 步，低风险）
- **为什么其次**: P2P 已独立，删除仅影响发现，不影响数据平面。
- **操作**:
  1. 删除 `organs/D_Gateway/organs/p2p_discovery.py`
  2. 删除 `organs/D_Gateway/organs/kademlia_dht.py`
  3. MCP server 改为注册到 Agora（已在 Phase A 完成）
  4. 连接池保留（SharedBrain 内部使用）
- **降级开关**: 无（P2P 已由 Agora 完全替代）
- **验证**: SharedBrain 不再有 P2P 相关代码（或标记 deprecated）
- **验证期**: 至少 1 天运行观察

#### C1a — D-Harvest → kronos（第 3 步，中风险）
- **为什么第三步**: 首次真正的能力委托，涉及数据摄取链路，但可降级。
- **操作**:
  1. D-Harvest 各 organ 调用改为 `mcp://agora/kronos/` 包装层
  2. kronos 新增 `feed_ingest` 工具（RSS/Atom → pipeline:json）
  3. D-Harvest 测试迁移到 kronos 集成测试
  4. D-Harvest 器官标记 `status: delegated`（不删除，保留代码）
- **降级开关**: `DHarvestFallback`: 当 kronos 不可达时，回退到 D-Harvest 本地实现
- **降级测试**: `test_degrade_harvest_fallback()` — 模拟 kronos 超时 → 验证回退 + 日志
- **验证**: 现有 D-Harvest 场景通过 kronos 完成摄取 + 降级测试 PASS
- **验证期**: 至少 2 天运行观察

#### C1b — D-KnowledgeIntegration → minerva + ontoderive（第 4 步，高风险）
- **为什么最后**: 查询路径中的关键路径，风险最高的委托。延迟影响最大。
- **操作**:
  1. FactGraph 查询改为 `mcp://agora/minerva/search`
  2. embedding search 改为 `mcp://agora/kos/search`
  3. 知识积分逻辑改为 `mcp://agora/ontoderive/derive`
  4. D-KnowledgeIntegration 器官标记 `status: delegated`
- **延迟缓解**: 查询结果在 D-Memory 中缓存（30s TTL），减少跨系统调用
- **降级开关**: `DKIFallback`: 当 minerva/kos 不可达时，回退到 D-KI 本地实现
- **降级测试**: `test_degrade_ki_fallback()` — 模拟 minerva 超时 → 验证回退
- **验证**: 端到端知识检索链路 + 降级测试 PASS；延迟 < 基线 × 1.5
- **验证期**: 至少 3 天运行观察

---

### 子阶段 C2 — kairon 获取 SharedBrain 独有能力（~1.5 周）

> 依赖 B3a（SSOT 基础注册）已完成

#### C2a — EU 计价 → 新建 eu-pricing 包（L2 能力层）
- **架构修复**: 原方案将 EU 定价放 Agora middleware（违反 I0 规则）→ 改为独立 L2 包
- **文件**: `kairon/packages/eu-pricing/` (新建)
  - `pyproject.toml` | `src/eu_pricing/__init__.py`
  - `src/eu_pricing/ledger.py` — EU 余额管理、消耗记录
  - `src/eu_pricing/mcp_server.py` — 暴露 MCP 工具 `eu_pricing/check_balance`, `eu_pricing/consume`
- **Agora 中的角色**: 仅路由。`EURoutingMiddleware` 在请求前后调用 `eu-pricing/check_balance` 和 `eu-pricing/consume`，不自行计算
- **内容**:
  ```python
  # kairon/packages/eu-pricing/src/eu_pricing/ledger.py
  class EULedger:
      """EU 虚拟资源会计 —— 这是 L2 能力层业务逻辑，不在 I0 中"""
      def check_balance(self, caller: str) -> EUBalance: ...
      def consume(self, caller: str, eu_units: int) -> EUTransaction: ...

  # Agora 中间件 —— 仅路由，不计算
  class EURoutingMiddleware:
      def on_request(self, tool, caller):
          result = self.route_to("eu-pricing", "check_balance", caller)
          if not result.sufficient:
              raise HTTPException(402, "EU balance insufficient")
  ```
- **依赖**: Phase A 完成（通过 Agora 调用 SharedBrain EU）
- **验证**: pipeline 每一步有 EU 成本，余额不足返回 402

#### C2b — 免疫审计接入 minerva 研究流
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
- **依赖**: B3a（需 organ 状态已入 SSOT 才能检测异常）
- **验证**: forge entropy 监控检测异常 → 自愈触发 → SharedBrain organ 恢复

---

### 子阶段 C3 — 身份映射统一（~3 天）

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
- **依赖**: B3a（需 identity_bridge 数据已入 kos index）
- **验证**: agent-runtime 创建 Agent 后，SharedBrain identity_bridge 可见；反之亦然

---

### Phase C 完成标准
- [ ] C1d: D-Monitoring 指标统一到 agora/metrics + 降级测试 PASS
- [ ] C1c: D-Gateway P2P 代码删除/标记 deprecated
- [ ] C1a: D-Harvest 所有场景通过 kronos 完成 + 降级测试 PASS
- [ ] C1b: D-KnowledgeIntegration 调用迁移到 minerva/kos + 降级测试 PASS + 延迟达标
- [ ] B3b: SSOT 最终 organ 状态同步完成
- [ ] C2a: eu-pricing 包运行，pipeline 每一步有 EU 成本
- [ ] C2b: minerva 研究结果经免疫审计后再入库
- [ ] C2c: forge entropy 检测异常 → SharedBrain 自愈触发
- [ ] C3a: identity_bridge ↔ agent-runtime 身份双向同步
- [ ] SharedBrain 测试 ≥ 14,000 PASS（delegated 测试转为桥接验证测试）
- [ ] kairon 新增测试 ~50 PASS
- [ ] 集成测试延迟 ≤ 基线 × 2（允许跨系统 MCP 调用的合理开销）

---

## 架构合规性

| 规则 | 状态 | 备注 |
|------|------|------|
| I0 = Agora + ops（仅限 MCP） | ✅ | Phase A 正确地将 Agora 定位为集成织物 |
| I0 不得承载业务逻辑 | ✅ | C2a 已修复：EU 定价移入 eu-pricing (L2)，Agora 仅路由 |
| I0 可被所有层引用（唯一跨层例外） | ✅ | 通过 MCP 在系统中实现 |
| 非 I0 层之间禁止直接引用 | ✅ | 所有提议的交互都通过 Agora (I0) |
| MCP 为强制协议 | ✅ | Phase A 将 MCP 确立为集成标准 |
| pipeline:json 为推荐协议 | ✅ | C1a kronos 摄取、C1b minerva 研究均使用 pipeline:json |

---

## 跨系统错误语义

| 错误类型 | kairon 侧 | SharedBrain 侧 | 映射规则 |
|----------|-----------|----------------|----------|
| 服务不可达 | `MCPConnectionError` | `GatewayUnreachableException` | → 触发降级 (fallback to local) |
| 调用超时 (>10s) | `MCPTimeoutError` | `GatewayTimeoutException` | → 重试 1 次 → 仍失败则降级 |
| 断路器跳闸 | `CircuitBreakerOpen` | `GatewayBlockedException` | → 等待 half-open → 不降级 |
| 数据校验失败 | `SchemaValidationError` | `DataIntegrityException` | → 记录到 SSOT error log，不写入 |
| EU 余额不足 | `HTTP 402 EU Insufficient` | `EconomyException` | → 任务排队，等待 EU 充值 |

---

## 验收标准（总）

| 维度 | 当前 | 目标 | 验收方式 |
|------|------|------|----------|
| 协议统一 | 各自有 MCP，无互相调用 | Agora 统一路由，双方 MCP 互调 | `agora registry list` + e2e test |
| 数据统一 | 独立 schema，无同步 | core-models PyPI 共享，双向适配器运行 | SSOT validate + 增量同步测试 |
| 能力去重 | 6 个域重叠 | 2 个域重叠（Execution + Memory） | SharedBrain 4 organ delegated |
| 能力互补 | EU/免疫/演化独享 | kairon 也可用 | pipeline EU 计价 + 免疫审计 + 自愈触发 |
| SharedBrain 测试 | 16,676 | ≥ 14,000 (delegated → 桥接验证) | pytest |
| kairon 测试 | 待确认 | +50 新增 | pytest |
| 架构违规 | 无 | 无反向 import，无 I0 承载业务逻辑 | arcnode 验证 |
| 集成延迟 | N/A | ≤ 基线 × 2 | baseline_latency.py 对比 |
| 降级能力 | 无 | 4 个 delegated organ 各有无损降级回退 | test_degrade_* 测试 |

---

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| Python 版本差异 (3.10 vs 3.14) | 🔴 高 | **决策**: 阶段 I (Phase A-C) 将 kairon 升级到 ≥3.12（中间态），解决基础兼容性；Phase C 结束后评估 3.14。短期通过 MCP 协议隔离 |
| Agora 成为单点故障 | 🟡 中 | 双方保留直连 MCP 端点作为 fallback；Agora 已有 degrade 模式；4 个 organs 各有降级开关 |
| organ delegated 后 SharedBrain 行为退化 | 🟡 中 | 保留原代码（标记 delegated 不删）；每个 organ 有降级测试；串行委托 + 验证期 |
| 双向同步一致性问题 | 🟡 中 | SSOT 注册 SharedBrain domain 为权威源，冲突时优先；增量 SHA-256 对比 |
| core-models 模型漂移 | 🟡 中 | PyPI 版本号对比 + 适配器自动标记 `needs_review`；B1 中定义了漂移防护 |
| MCP 跨系统调用延迟 | 🟡 中 | C1b 关键路径加 30s 缓存；A0.3 基线采集；Phase C 验收时检查延迟 ≤ 基线 × 2 |
| 委托器官回退路径未经验证 | 🟡 中 | 每个 delegated organ 有降级测试 + 降级开关。串行执行确保回退路径始终可验证 |
| kairon 升级到 3.12 破坏现有测试 | 🟢 低 | uv workspace 可在升级前先用 `uv lock --python 3.12` 预检兼容性 |

---

## 执行顺序依赖

```
Phase A-0 (集成基础设施)
  └─→ Phase A (协议桥接)  ──→ 🚦 Go/No-Go
        └─→ Phase B (数据统一)
              ├── B1 (core-models + Z-Spore 适配器)
              ├── B2 (反向适配器 eidos→bos)
              ├── B3a (正向适配器 + SSOT 基础 Schema)
              │
              └── 🚦 Go/No-Go ──→ Phase C
                    │
                    ├── C1d (监控→agora)     ← 第1步，最低风险
                    ├── C1c (P2P→agora)       ← 第2步
                    ├── C1a (摄取→kronos)     ← 第3步
                    ├── C1b (知识→minerva)    ← 第4步，最高风险
                    │
                    ├── B3b (SSOT 最终同步)   ← C1 完成后
                    │
                    ├── C2a (EU 计价包)  ──── 依赖 A2
                    ├── C2b (免疫审计)  ──── 依赖 A2
                    ├── C2c (自愈规则)  ──── 依赖 B3a
                    │
                    └── C3a (身份同步)  ──── 依赖 B3a
```

### 并行执行机会

- Phase A 内: A1 和 A2 可并行开发，A3 串行（需等待两者完成）
- Phase B 内: B1, B2, B3a 可并行（互不依赖）
- C2 内: C2a 和 C2b 可并行（共享依赖 A2 但不互相依赖）
- ❌ C1 必须串行（每个 organ 委托后需验证期）
- ❌ C3a 必须在 B3a 之后（需 identity_bridge 数据已入 kos index）
