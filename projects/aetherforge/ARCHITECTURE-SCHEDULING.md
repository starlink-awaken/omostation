# AetherForge 算力调度架构 — 完整设计

> 回答: 可用性? 配额? 大盘? 调度? 路由? 成本? L0?
> v1.0 | 2026-06

---

## 一、现状与问题

### 当前存在的断层

| 层面 | 现状 | 问题 |
|:-----|:------|:------|
| **可用性** | `detect_cloud_nodes()` 有 API Key 就标 ONLINE | ❌ 有 Key ≠ 可用。可能欠费、限流、IP 被封 |
| **配额** | codexbar 能查，但没接入调度决策 | ❌ 调度器不看配额，超限了还继续路由 |
| **大盘** | `credentials quota <provider>` 单查 | ❌ 没有全局一览视图 |
| **调度** | `GetBestNode()` 只看 load_factor + zone | ❌ 不看配额余量、不看成本、不看速率限制 |
| **路由** | `RouterPipeline` 只做模型级路由 | ❌ 没有 Provider 级路由（同样的模型多家都有） |
| **成本** | `PricingRegistry` 有定价，但没用 | ❌ 调度器不按成本做决策 |

### 配额的复杂性

用户的 Provider 有 **多种配额模型**:

| 类型 | 示例 | 特征 |
|:-----|:------|:------|
| **预付费余额** | DeepSeek (¥498 余额) | 递减余额，花完为止 |
| **月限** | OpenAI (每月 $X) | 每月重置 |
| **周限** | Claude Code (每周用量) | 每周重置，超限 429 |
| **速率限** | 大多数 API (TPM/RPM) | 每分钟/秒限制 |
| **免费额度** | Gemini (每分钟 60 次) | 固定速率，超限 429 |

---

## 二、L0 数据模型设计

### 需要新增的 M1 类型

```yaml
# M1: compute_engine 增强 — 配额关联
ENG-DEEPSEEK:
  type: compute_engine
  quota_model: prepaid          # prepaid | monthly | weekly | rate | free
  quota_source: codexbar        # codexbar | local | api
  cost_model: per_token         # per_token | subscription | credit
  capabilities: [chat, reasoning]

# M1: quota_definition — 配额定义
QD-DEEPSEEK:
  type: quota_definition
  provider: deepseek
  model: prepaid
  unit: CNY
  balance_source: codexbar      # 实时查询: codexbar usage --provider deepseek

# M1: routing_policy — 路由策略
RP-DEFAULT:
  type: routing_policy
  strategy: cost_first           # cost_first | speed_first | balanced | quota_first
  fallback: true
  constraints:
    max_cost_per_1k: 0.01
    min_quota_percent: 10       # 配额低于 10% 时降级
```

---

## 三、架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        L0 MOF (M1 YAMLs)                         │
│  compute_engine / quota_definition / routing_policy / cost_model  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ 加载
┌────────────────────────────────┴─────────────────────────────────┐
│                     QuotaEngine (新建)                            │
│                                                                   │
│  职责: 统一配额查询 + 可用性判断                                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Data Sources:                                              │   │
│  │  1. codexbar CLI (实时: DeepSeek, OpenAI, Gemini...)        │   │
│  │  2. cc-switch DB (历史用量)                                  │   │
│  │  3. CredentialsManager (本地预算约束)                        │   │
│  │  4. Provider API (直接查询: 自有余额接口)                    │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  is_available(provider) → bool    # 真实可用性                    │
│  get_quota(provider) → Quota      # 统一配额模型                  │
│  get_remaining(provider) → float  # 剩余配额百分比                │
│  get_usage_trend(provider) → ...  # 用量趋势                      │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ 查询
              ┌──────────────────┼──────────────────┐
              │                  │                  │
        ┌─────┴─────┐    ┌──────┴──────┐    ┌─────┴─────┐
        │  Router    │    │  Mesh       │    │  Dashboard │
        │  Pipeline  │    │  Scheduler  │    │  CLI       │
        │  (Gateway) │    │  (Mesh)     │    │           │
        └───────────┘    └─────────────┘    └───────────┘
```

---

## 四、核心引擎设计: QuotaEngine

```python
class QuotaEngine:
    """统一配额引擎 — 替代分散的配额检查逻辑。"""

    def is_available(self, provider: str) -> Availability:
        """三步检测:
           1. 有 Key? (CredentialsManager)
           2. 服务在线? (TCP/HTTP 探测)
           3. 配额充足? (codexbar / 本地)
        """
        if not self.has_credentials(provider):
            return Availability.UNAVAILABLE_NO_KEY
        if not self._probe(provider):
            return Availability.UNAVAILABLE_OFFLINE
        quota = self.get_quota(provider)
        if quota.remaining_pct < 10:
            return Availability.UNAVAILABLE_QUOTA_EXHAUSTED
        return Availability.AVAILABLE

    def get_quota(self, provider: str) -> UnifiedQuota:
        """统一配额视图，屏蔽底层差异:
           - codexbar 实时余额 → UnifiedQuota
           - 本地预算约束 → UnifiedQuota
           - cc-switch DB → UnifiedQuota
        """
        # 1. Try codexbar for real-time quota
        # 2. Fallback to local budget
        # 3. Fallback to unlimited

    def get_best_provider(self, criteria: RoutingCriteria) -> str:
        """按条件选择最优 Provider:
           - cost_first: 成本最低
           - quota_first: 配额最充裕
           - balanced: 综合评分
        """
```

### 统一配额模型 (UnifiedQuota)

```python
@dataclass
class UnifiedQuota:
    provider: str
    model: QuotaModel  # prepaid | monthly | weekly | rate | free
    
    # 余额型 (prepaid)
    balance_remaining: float = 0.0
    balance_total: float = 0.0        # 原始充值额
    balance_unit: str = "CNY"          # CNY | USD | token
    
    # 周期型 (monthly / weekly)
    period_limit: float = 0.0
    period_used: float = 0.0
    period_reset: str = ""             # "2026-07-01"
    
    # 速率型 (rate)
    rpm_limit: int = 0
    rpm_remaining: int = 0
    
    # 通用
    remaining_pct: float = 0.0         # 0-100
    source: str = "codexbar"           # 数据来源
    last_updated: float = 0.0
    available: bool = True
```

---

## 五、调度与路由

### 路由策略 (RoutingPolicy)

```yaml
policy:
  strategy: balanced
  weights:
    cost: 0.4          # 成本权重
    speed: 0.3          # 速度权重  
    quota: 0.3          # 配额充裕度权重
  constraints:
    max_cost_per_1k: 0.01
    min_quota_pct: 10
  fallback:
    enabled: true
    max_retries: 2
    cooldown_seconds: 30
```

### 调度流程

```
请求到达
  │
  ▼
1. Provider 过滤 (QuotaEngine.is_available)
  │ 跳过: 无Key/离线/配额不足
  │
  ▼
2. 模型匹配 (PricingRegistry)
  │ 找到请求模型在哪些 Provider 上有
  │
  ▼
3. 策略评分 (RouterPipeline)
  │ CostScore + SpeedScore + QuotaScore + ZoneAffinityScore
  │
  ▼
4. 选择最优 (最高分)
  │
  ▼
5. 调用 → 成功/失败 → 记成本 → 更新配额缓存
```

### 例子: "用 GPT-4o 写代码"

```
可用 Provider:
  OpenAI    成本 $0.01/1K  速度 800ms   配额 72%
  DeepSeek  成本 $0.001/1K 速度 1200ms  配额 ¥498 (100%)
  MiniMax   成本 $0.002/1K 速度 900ms   配额 ??? (codexbar 不支持)
  Azure     未配置 ❌

策略 cost_first → DeepSeek (最便宜, 配额最充裕)
策略 balanced → DeepSeek (综合分最高)
策略 speed_first → OpenAI (最快, 如果配额够)
```

---

## 六、大盘 (Dashboard)

```bash
# 全局一览
aetherforge dashboard
┌─────────────────────────────────────────────────────────────┐
│  AetherForge Dashboard                                      │
├─────────────────────────────────────────────────────────────┤
│  Cloud Providers (7):                                       │
│  deepseek    🟢 ¥498.42/¥498.42  0% used                   │
│  minimax     🟡 ???              (codexbar 不支持)          │
│  openrouter  🟢 ???              (codexbar 不支持)          │
│  siliconflow 🟢 ???              (codexbar 不支持)          │
│  nvidia      🟢 ???              (codexbar 不支持)          │
│  xunfei      🟡 ???              (codexbar 不支持)          │
│  xiaomi      🟡 ???              (codexbar 不支持)          │
├─────────────────────────────────────────────────────────────┤
│  Local:  ollama-local    🟢 13 models                       │
│  Tailscale: 2 nodes     🟢                                  │
│  Proxy: 2 nodes         🟢                                  │
├─────────────────────────────────────────────────────────────┤
│  本月总花费: $12.45 │ 预算: $50.00 │ 剩余: $37.55 │ 75%     │
└─────────────────────────────────────────────────────────────┘

# 单 Provider 详情
aetherforge provider deepseek
  Status:      🟢 可用
  Quota:       ¥498.42 余额 (100%)
  Cost Model:  预付费 (CNY)
  Models:      deepseek-chat ($0.0005/$0.0015)
               deepseek-reasoner ($0.001/$0.002)
  Endpoint:    https://api.deepseek.com
  Auth:        cc-switch (sk-5e4d...)
```

---

## 七、实施路线

| Phase | 内容 | L0 建模 | 代码 | 优先级 |
|:------|:------|:--------|:------|:------|
| **P1** | QuotaEngine + codexbar 统一查询 | `quota_definition` M1 | `quota_engine.py` | 🔴 |
| **P2** | 可用性三步检测 (Key→在线→配额) | `availability_check` M1 | 增强 `detect_cloud_nodes()` | 🔴 |
| **P3** | 调度器集成配额感知 | `routing_policy` M1 | 增强 `RouterPipeline` | 🔴 |
| **P4** | Dashboard 大盘 | `dashboard_view` M1 | `dashboard` CLI | 🟡 |
| **P5** | 多模型路由 (同模型多家Provider) | `model_provider_map` M1 | 增强 `PricingRegistry` | 🟡 |
| **P6** | 自动降级/切换 | `fallback_policy` M1 | 增强 `MeshScheduler` | 🟢 |

---

## 八、一句话回答你的问题

> **L0 上目前没有配额/路由/成本模型的定义**——之前只定义了 `compute_engine` 的存在，没定义它的"怎么用"。
>
> **功能上**：你需要一个 `QuotaEngine` 统一管理所有 Provider 的配额查询（codexbar + 本地），然后调度器根据配额 + 成本 + 速度做路由决策。
>
> **现在 cloud 节点标 ONLINE 是假的**——只因为有 Key 而已。真正的可用性需要三步检测：有 Key？服务在线？配额够？
>
> **大盘**还没做。**路由策略**还没写。**成本**只在模型定价层面，没进调度决策。

要开始做 P1（QuotaEngine）吗？
