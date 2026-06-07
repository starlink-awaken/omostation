# AetherForge 架构重构设计 v2

> 系统思维 · 战略规划 · L0 建模 · 战术落地
> 2026-06

---

## 一、战略层: 为什么需要重构

### 当前断层

```
L0 M1 (定义层)          ❌ 只定义了 compute_engine 的存在
                           没定义配额/路由/成本/可用性
                           
Gateway (资源层)        ❌ Provider 标 ONLINE = 有 Key
                           实际可用性不知道
                           
Mesh (调度层)           ❌ GetBestNode 只算 load_factor
                           不看配额/成本/真实可用性
                           
codexbar (数据层)       ❌ 能查实时配额，没接进调度
cc-switch (数据层)      ❌ 47 个 Provider 配了，7 个显示
Credentials (数据层)    ❌ 有 Key 没服务状态
```

### 核心矛盾

> **数据存在，但不在正确的位置。决策需要的信息分散在 5 个互不知晓的系统中。**

---

## 二、架构层: 目标状态

### 2.1 总架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       PRESENTATION LAYER                            │
│  CLI (aetherforge) · MCP (6 tools) · Dashboard · Provider Info     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION LAYER                           │
│  Swarm (GroupChat · GraphWorkflow · Hierarchical · Auction)        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                       RESOURCE LAYER                                │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  ProviderManager │  │  ModelManager   │  │  TopologyManager    │ │
│  │                  │  │                 │  │                     │ │
│  │  credentials     │  │  pricing        │  │  nodes              │ │
│  │  availability    │  │  capabilities   │  │  network zones      │ │
│  │  quotas          │  │  routing rules  │  │  scheduling         │ │
│  └────────┬────────┘  └───────┬─────────┘  └──────────┬──────────┘ │
└───────────────────────────────┼─────────────────────────┼───────────┘
                                │                         │
┌───────────────────────────────┼─────────────────────────┼───────────┐
│                    DATA LAYER │                         │           │
│                               ▼                         ▼           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ L0 M1   │  │ CredDB  │  │ CostDB  │  │ codexbar CLI       │ │
│  │ YAMLs   │  │ SQLite  │  │ SQLite  │  │ (实时配额)          │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心引擎

```
ProviderManager — 统一资源管理层
─────────────────────────────────
  职责: 所有 Provider 的注册/可用性/配额
  
  register(provider, credentials)   # 从 env / cc-switch / CLI 注册
  is_available(provider) → Status   # 三步检测: Key→在线→配额
  get_quota(provider) → Quota       # 统一配额模型 (codexbar+本地)
  get_status(provider) → Report     # 完整状态报告
  
  数据源优先级:
    1. codexbar CLI (实时配额: DeepSeek, OpenAI, Gemini...)
    2. L0 M1 YAML (静态定义: pricing, routing_policy)
    3. CredentialsManager (本地凭据 + 预算)
    4. Provider API 直查 (自有余额接口)

RouteScheduler — 统一调度引擎
─────────────────────────────────
  职责: 模型 + Provider + 节点 三级路由
  
  select(request) → Route
    1. Model Match: 请求的模型在哪些 Provider 上有
    2. Provider Filter: 配额够? 在线? 速率允许?
    3. Strategy Score: cost/speed/quota/balanced 综合评分
    4. Node Bind: 绑定到最优计算节点

QuotaModel — 统一配额抽象
─────────────────────────────────
  prepaid:   余额递减 (DeepSeek ¥498)
  monthly:   月限重置 (OpenAI $50/月)
  weekly:    周限重置 (Claude Code)
  rate:      速率限制 (GPT-4 10000 TPM)
  free:      免费额度 (Gemini 60 req/min)
```

### 2.3 数据流

```
用户请求 "用 GPT-4o 写代码"
       │
       ▼
RouteScheduler.select()
       │
       ├── ModelManager.get_models("gpt-4o")
       │   → [OpenAI, Azure, DeepSeek(兼容)]  # 哪些 Provider 有这个模型
       │
       ├── ProviderManager.filter(providers)
       │   → is_available() 三步检测
       │   → get_quota() 配额检查
       │   → [DeepSeek(¥498, 0%), OpenAI($42/$50, 84%)]
       │
       ├── RouterPipeline.score(candidates)
       │   → CostScore(DeepSeek $0.001 < OpenAI $0.01)  ✓
       │   → SpeedScore(...)
       │   → QuotaScore(DeepSeek 100% > OpenAI 16%)     ✓
       │
       ├── TopologyManager.bind(winner)
       │   → 选择具体计算节点
       │
       ▼
   返回: Route(provider=deepseek, model=deepseek-chat, 
               node=deepseek-cloud, cost=$0.001/1K)
```

---

## 三、L0 层: 完整建模

### 3.1 新增 M1 命名空间

```
m1/
├── compute_engine/       ✅ 已有 (7 files)  → 增强 quota_model 字段
├── compute_node/         ✅ 已有 (4 files)
├── hardware_asset/       ✅ 已有 (4 files)
├── network_zone/         ✅ 已有 (5 files)
├── model/                ✅ 已有 (pricing YAML) → 增强 routing 字段
│
├── quota_definition/     🆕 新建 — 配额定义
│   ├── QD-DEEPSEEK.yaml     # 预付费余额型
│   ├── QD-OPENAI.yaml       # 月限型
│   └── QD-GEMINI.yaml       # 免费速率型
│
├── routing_policy/       🆕 新建 — 路由策略
│   ├── RP-BALANCED.yaml     # 综合策略
│   ├── RP-COST-FIRST.yaml   # 成本优先
│   └── RP-SPEED-FIRST.yaml  # 速度优先
│
├── availability_check/   🆕 新建 — 可用性检测配置
│   ├── AC-DEEPSEEK.yaml     # HTTPS probe
│   └── AC-OLLAMA.yaml       # TCP port probe
│
└── dashboard_view/       🆕 新建 — 大盘视图定义
    └── DV-MAIN.yaml         # 主视图配置
```

### 3.2 M1 类型定义示例

```yaml
# quota_definition/QD-DEEPSEEK.yaml
id: QD-DEEPSEEK
type: quota_definition
provider: deepseek
quota_model: prepaid              # 预付费余额
unit: CNY
source: codexbar                  # 通过 codexbar CLI 查询
check_command: "codexbar usage --provider deepseek --format json"
refresh_interval: 300             # 5 分钟刷新
max_cost_per_1k_input: 0.0005
max_cost_per_1k_output: 0.0015
```

```yaml
# routing_policy/RP-BALANCED.yaml
id: RP-BALANCED
type: routing_policy
strategy: balanced
weights:
  cost: 0.35
  speed: 0.25
  quota: 0.25
  affinity: 0.15
constraints:
  max_cost_per_1k_input: 0.01
  max_cost_per_1k_output: 0.03
  min_quota_pct: 10
  prefer_local: true
fallback:
  enabled: true
  max_retries: 2
  cooldown_seconds: 30
```

### 3.3 L0 对上层支撑

```
L0 定义                   → 上层使用
──────────────────────────────────────────────────
quota_definition          → ProviderManager.get_quota()
                          → 知道用 codexbar 还是本地查
                          → 知道刷新间隔

routing_policy            → RouteScheduler.select()
                          → 知道权重配比
                          → 知道硬约束 (max_cost)
                          → 知道回退策略

compute_engine.quota_model → QuotaModel 统一抽象
                          → 预付费/月限/周限/速率

availability_check        → ProviderManager.is_available()
                          → 知道怎么探测 (HTTP/TCP/CLI)
```

---

## 四、战术层: 实施路线

### Phase 1 — L0 建模 + QuotaEngine (当前)

| 任务 | 产出 | 工作量 |
|:-----|:------|:------:|
| M1 quota_definition YAMLs | 3-5 个配额定义 | 0.5d |
| M1 routing_policy YAMLs | 3 个策略定义 | 0.5d |
| M1 availability_check YAMLs | 2 个检测配置 | 0.5d |
| `QuotaEngine` 实现 | 统一配额查询 + codexbar 集成 | 1d |
| `ProviderManager` 实现 | 统一资源管理 + 三步可用性检测 | 1d |
| **总计** | | **3.5d** |

### Phase 2 — RouteScheduler 重构

| 任务 | 产出 | 工作量 |
|:-----|:------|:------:|
| 三级路由 (模型→Provider→节点) | RouteScheduler | 2d |
| QuotaScore + CostScore 插件 | RouterPipeline 增强 | 1d |
| 自动降级/回退 | FallbackManager | 1d |
| **总计** | | **4d** |

### Phase 3 — Dashboard + 大盘

| 任务 | 产出 | 工作量 |
|:-----|:------|:------:|
| `aetherforge dashboard` | 大盘命令 | 1d |
| `aetherforge provider <name>` | 单 Provider 详情 | 0.5d |
| **总计** | | **1.5d** |

---

## 五、架构一致性原则

### 5.1 数据所有权

```
每个事实只有一个权威来源 (SSOT):

Provider 凭据    → CredentialsManager (SQLite)
Provider 配额    → codexbar CLI (实时) → QuotaEngine (缓存)
Provider 定价    → PricingRegistry (内置 + L0 YAML)
Provider 拓扑    → TopologyManager (Scanner + NetworkScanner)
Provider 可用性  → ProviderManager (三步检测)
Provider 成本    → CostTracker (SQLite)
```

### 5.2 调用链

```
CLI/MCP
  │
  ├── gateway.generate()
  │     → RouteScheduler.select()
  │         → ProviderManager.filter()
  │             → is_available() 三步检测
  │             → get_quota() 配额查询
  │         → RouterPipeline.score()
  │             → CostScore + QuotaScore + SpeedScore
  │         → ProviderManager.call()
  │             → record_llm_cost() → CostTracker
  │
  ├── mesh.list()
  │     → TopologyManager.get_nodes()
  │         → Scanner + NetworkScanner + M1Loader
  │
  └── credentials.quota()
        → ProviderManager.get_quota()
            → QuotaEngine (codexbar → local)
```

### 5.3 分层依赖

```
严禁反向依赖:

  Presentation → Orchestration → Resource → Data
      CLI             Swarm        Gateway     L0
      MCP             Hierarchical  Mesh        CredDB
      Dashboard       GroupChat     ProviderMgr CostDB
                                      codexbar
```

---

## 六、与现有系统的关系

```
cc-switch DB (47 providers, 模型定价, 端点)
  → ProviderManager 读取凭据
  → PricingRegistry 读取定价
  → QuotaEngine 不读 (配额在 codexbar)

codexbar CLI (实时配额)
  → QuotaEngine 主要数据源
  → Dashboard 展示

CredentialsManager (本地 SQLite)
  → ProviderManager 凭据层
  → Fallback: 当 codexbar 不可用时提供本地配额

EnergyLedger (Swarm 经济账本)
  → 独立的 Agent 激励体系
  → 不与 QuotaEngine 打通 (不同用途)
```

---

## 七、预期效果

```
Phase 1 后:
  aetherforge provider deepseek
  → Status: 🟢 可用 (有 Key ✓ 在线 ✓ 配额 ✓)
  → Quota: ¥498.42 (100%) [codexbar]
  
  aetherforge provider minimax
  → Status: 🟡 未知 (有 Key ✓ 在线 ? 配额 不可查)
  
  aetherforge list --quota
  → 所有 Provider 配额大盘

Phase 2 后:
  aetherforge gateway generate "你好"
  → RouteScheduler 自动选 DeepSeek
  → 因为: 成本最低 + 配额最充裕 + 支持 chat
  
  (当 DeepSeek 余额 < 10% 时)
  → 自动降级到 OpenAI (如果预算允许)
  → 或降级到本地 Ollama (免费)

Phase 3 后:
  aetherforge dashboard
  → 全局健康一览
  → 配额/成本/节点数
  → 月度预算使用趋势
```
