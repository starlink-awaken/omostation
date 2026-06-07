# AetherForge × L0 MOF — 全面融合规划

> 将 eCOS L0 MOF 的 6 个 M1 命名空间全部接入 AetherForge，
> 实现"定义即发现、注册即路由"的完整闭环。

---

## 一、L0 MOF 全景

```
L0 M1 命名空间 (17个)
├── compute_engine/       LLM 引擎端点    ✅ 已接入
├── compute_node/         物理/虚拟节点   ❌ 未接入
├── hardware_asset/       硬件资源        ❌ 未接入
├── network_zone/         网络区域        ❌ 未接入
├── model/                模型定义/定价   ❌ 未接入
├── ... 12个其他命名空间
```

### 当前接入状态

| M1 目录 | 文件数 | 用途 | AetherForge 接入 |
|:---------|:------:|:-----|:----------------|
| `compute_engine/` | 7 | LLM 引擎 (Ollama/OpenAI/Azure/Bedrock/Vertex…) | ✅ `TopologyScanner.load_static_nodes()` |
| `compute_node/` | 4 | 物理机器 (Mac/MacMini/Y7000P/Cloud) | ✅ `M1Loader → MachineInfo` |
| `hardware_asset/` | 4 | CPU/RAM/GPU 规格 | ✅ `M1Loader → MachineInfo` |
| `network_zone/` | 5 | 网络区域 (localhost/LAN/VPN/Proxy/WAN) | ✅ `M1Loader → NetworkZoneInfo` |
| `model/` | 6 | 模型定义/定价/治理 | ✅ `PricingRegistry + models CLI` |
| `constraint_mgmt/` | 1 | 约束管理 | ✅ `CredentialsManager + budget CLI` |

---

## 二、融合架构

```
                          ┌──────────────────────────────────────┐
                          │          aetherforge CLI/MCP          │
                          └──────────┬───────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────────┐
              │                      │                          │
        ┌─────┴──────┐       ┌──────┴──────┐          ┌───────┴──────┐
        │  Gateway    │       │    Mesh      │          │  Credentials  │
        │  Provider   │       │  Topology    │          │  SQLite DB    │
        │  调用/限流   │       │  发现/健康    │          │  (Phase 1)    │
        └─────────────┘       └──────┬───────┘          └──────────────┘
                                     │
                        ┌────────────┴────────────┐
                        │    L0 MOF Loader         │
                        │  统一加载所有 M1 YAML     │
                        └────────────┬────────────┘
                                     │
        ┌────────────┬───────────────┼───────────────┬────────────┐
        │            │               │               │            │
   ┌────┴────┐ ┌────┴────┐   ┌──────┴──────┐  ┌────┴────┐  ┌───┴────┐
   │compute_ │ │compute_ │   │hardware_    │  │network_ │  │ model   │
   │engine   │ │node     │   │asset       │  │zone     │  │         │
   └─────────┘ └─────────┘   └────────────┘  └─────────┘  └────────┘
```

---

## 三、逐层接入方案

### Phase A: `compute_node` — 物理节点信息

**当前**: `ComputeNode` 有 topology/status/load，但缺少机器级元数据。

**目标**: 加载 `NODE-*.yaml` 并关联到 `ComputeNode`。

```yaml
# NODE-MACMINI.yaml (已有)
id: NODE-MACMINI
type: compute_node
device_type: mac_mini
os: macOS 15
hostname: macmini.local
```
→ 关联到 `ENG-OLLAMA-MACMINI.engine_type → NodeRef: NODE-MACMINI`
→ 在 `mesh list` 中显示机器信息

**工作量**: 小 (1天)

### Phase B: `hardware_asset` — 硬件资源规格

**当前**: `ComputeNode.max_concurrency` 是硬编码的。

**目标**: 从 `HW-*.yaml` 加载 CPU/GPU/RAM 规格，自动计算 `max_concurrency`。

```yaml
# HW-CPU-Y7000P.yaml (已有)
id: HW-CPU-Y7000P
type: hardware_asset
node_ref: NODE-Y7000P
device_type: cpu
model: "Intel Core i7-13500H"
```

→ 关联 `ENG-LMSTUDIO-Y7000P → NODE-Y7000P → HW-CPU-Y7000P + HW-RAM-Y7000P + HW-RTX4060-Y7000P`

**工作量**: 小 (1天)

### Phase C: `network_zone` — 网络拓扑

**当前**: `network_zone` 是 `ComputeNode` 上的字符串字段。

**目标**: 从 `ZONE-*.yaml` 加载网络区域定义，支持延迟/带宽/路由。

```yaml
# ZONE-HOME-LAN.yaml (已有)
id: ZONE-HOME-LAN
type: network_zone
zone_type: lan
latency_profile: low
```

→ 调度器 `ZoneAffinityScore` 利用延迟 profile 做路由决策
→ 节点间拓扑匹配支持多级 (region/zone/host + network_zone)

**工作量**: 中 (1-2天)

### Phase D: `model` — 模型注册与定价

**当前**: Provider 的 `available_models()` 是硬编码的列表。

**目标**: 从 `MODEL-*.yaml` 加载模型定义、定价、能力标签。

```yaml
# MODEL-UNIFIED-ARCH.yaml (已有)
id: MODEL-UNIFIED-ARCH
type: Model
name: 统一架构模型
properties:
  mapping:
    功能域视图: 5+4+1
    技术栈视图: L0-L4
```

当前 M1 `model/` 目录的定义偏架构层，需要补充具体的模型定价数据。建议新增 `MODEL-PRICING.yaml` 格式：

```yaml
id: MODEL-GPT4O
type: model_pricing
provider_ref: ENG-CC-SWITCH
model_id: gpt-4o
cost_per_1k_input: 0.0025
cost_per_1k_output: 0.01
context_window: 128000
capabilities: [chat, vision, tools]
```

→ `ModelScheduler` 读取 cost_per_1k 做成本路由
→ `CostTracker` 使用真实价格而非估算
→ `mesh cost` 显示准确的费用

**工作量**: 中 (2天)

### Phase E: `constraint_mgmt` — 约束治理

**当前**: 无约束系统。

**目标**: 加载 MOF 约束，在调度层强制执行。

```yaml
# constraint: gpt-4 月预算 $50
model: gpt-4
type: budget_constraint
monthly_limit: 50.0
action: block  # block | warn | log
```

→ `RateLimiter` 集成月度预算约束
→ 超限时自动降级到备用模型

**工作量**: 中 (2天)

---

## 四、实施路线图

| Phase | 模块 | L0 源 | 工作量 | 依赖 |
|:------|:-----|:-------|:------:|:-----|
| **A** | 计算节点信息 | `compute_node/` | 1d | — |
| **B** | 硬件资源规格 | `hardware_asset/` | 1d | Phase A |
| **C** | 网络拓扑 | `network_zone/` | 1-2d | — |
| **D** | 模型定价 | `model/` | 2d | — |
| **E** | 约束治理 | `constraint_mgmt/` | 2d | Phase D |
| **F** | 凭据 SQLite (cc-switch) | 新建 `credentials.db` | 1d | — |
| **G** | 配额外部化 (codexbar) | 新建 `quotas` 表 | 1d | Phase F |

### 完成状态

```
Sprint 4: Phase A + B + C  ✅ 完成
  → mesh info, mesh list --verbose, M1Loader
  
Sprint 5: Phase D          ✅ 完成
  → PricingRegistry, models list --cost
  
Sprint 6: Phase E + F + G  ✅ 完成
  → CredentialsManager, credentials CLI, budget 约束
```

---

## 五、关键设计决策

### 关联模型 (Reference Resolution)

```python
# compute_engine.yaml → compute_node.yaml → hardware_asset.yaml
ENG-OLLAMA-MACMINI  ──node_ref──▶  NODE-MACMINI
                                   ├── HW-MEM-MACMINI
                                   └── (no GPU)

ENG-LMSTUDIO-Y7000P ──node_ref──▶  NODE-Y7000P
                                  ├── HW-CPU-Y7000P
                                  ├── HW-RAM-Y7000P
                                  └── HW-RTX4060-Y7000P
```

`TopologyScanner` 需增加引用解析器，自动加载关联的 M1 节点。

### 运行时 ↔ 静态分离

- **L0 M1 YAML**: 静态定义 (安装/Ollama 模型列表/网络配置)
- **运行时数据**: 动态状态 (CPU 使用率/可用内存/在线状态)
- 静态信息加载时注入，动态信息健康检查时更新

### Models 工具查询

新增 CLI 子命令：

```bash
aetherforge models list                  # 列出所有已知模型+定价
aetherforge models list --provider openai  # 筛选
aetherforge models cost gpt-4o           # 查询具体模型成本
aetherforge models search vision          # 按能力搜索
```
