# AetherForge Gateway 架构分析 — cc-switch & codexbar 的遗产与融合

> 分析旧 SharedBrain B-OS 体系中 cc-switch / codexbar 的设计意图，
> 评估 AetherForge 当前的覆盖程度，给出融合方案。

---

## 一、旧体系架构 (SharedBrain B-OS, 已归档)

```
                    ┌──────────────────────────────────────┐
                    │          ComputeHarvester             │
                    │  定时收割: Ollama / cc-switch / ...   │
                    └────┬─────────────────────┬───────────┘
                         │                     │
                    ┌────┴─────┐         ┌─────┴──────┐
                    │ cc-switch │         │  codexbar  │
                    │           │         │            │
                    │ SQLite DB │         │ CLI 工具   │
                    │ model_pricing        │ usage --json│
                    │ tokens/credentials   │ 配额/预算  │
                    └───────────┘         └────────────┘
                         │                     │
                         └─────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │      QuotaRouter             │
                    │  调用前检查配额 → 路由 → 调用 │
                    └─────────────────────────────┘
```

### cc-switch 的设计意图

| 层面 | 设计 | 实现方式 |
|:-----|:-----|:---------|
| **令牌存储** | SQLite `model_pricing` 表存储所有 Provider 的 API Key、端点、模型定价 | 环境变量 `BOS_CC_SWITCH_DB` 指向 DB 路径 |
| **模型注册** | DB 中记录哪些模型可用、价格、能力 | `SELECT model_id, display_name FROM model_pricing` |
| **鉴权代理** | 请求经过 cc-switch 代理，统一注入认证凭据 | 未完整实现，仅做了元数据收割 |

### codexbar 的设计意图

| 层面 | 设计 | 实现方式 |
|:-----|:-----|:---------|
| **配额查询** | CLI `codexbar usage --format json --provider all` 返回各 Provider 剩余配额 | 子进程调用，JSON 解析 |
| **预算拦截** | 调用 LLM 前先查配额，超限则拒绝 | `QuotaRouter` 中预检查 |
| **缓存** | 5 分钟 TTL 缓存，避免频繁调用 CLI | `CodexBarCache` 线程安全 |

---

## 二、AetherForge 当前架构

```
                    ┌──────────────────────────────────────┐
                    │         aetherforge CLI / MCP         │
                    └──────────┬───────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │     Gateway          │
                    │  Provider 层 (9个)   │
                    │  RateLimiter (tpm)   │
                    │  CostTracker (成本)  │
                    │  RouterPipeline      │
                    └─────────────────────┘
```

### 当前能力覆盖

| 旧体系能力 | AetherForge | 差距 |
|:-----------|:-----------|:------|
| **令牌存储** | 环境变量 | ❌ 无 SQLite 凭据库，每次新增 Provider 要 export |
| **模型注册** | L0 M1 YAML | 🟡 YAML 与运行时未同步，pricing 未使用 |
| **配额查询** | RateLimiter.set_limit() | ❌ 硬编码限流，不从外部系统读取配额 |
| **预算拦截** | CostTracker 记录 | ❌ 只记账不拦截，超预算不会阻断请求 |
| **凭据池** | ❌ 无 | ❌ 不支持多 Key 轮转/故障转移 |
| **定时收割** | TopologyScanner.scan() | 🟢 类似但触发式非定时 |

---

## 三、差距分析

### 🔴 差距 1: 无集中凭据管理

**当前**: API Key 散落在环境变量里，每次新增 Provider 都要手动 export。

```bash
export DEEPSEEK_API_KEY=sk-xxx  # 当前方式
export OPENAI_API_KEY=sk-yyy
export ANTHROPIC_API_KEY=sk-zzz
```

**旧体系设计**: cc-switch SQLite 表里集中存储，一个 DB 文件管理所有凭据。

```
model_pricing table:
  model_id    | display_name | api_key     | base_url | cost
  gpt-4       | GPT-4        | sk-xxx      | ...      | 0.03
  deepseek-chat| DeepSeek    | sk-yyy      | ...      | 0.001
```

**差距**: 新增 Provider 的体验是 `export KEY=val` vs `INSERT INTO model_pricing`。前者对个人开发者也够用，但小团队场景就不够看了。

### 🔴 差距 2: 配额/预算无外部数据源

**当前**: `RateLimiter.set_limit("gpt-4", tpm=100000)` 是硬编码的。

**旧体系设计**: `codexbar usage --json` 返回实时剩余配额，`QuotaRouter` 据此做调度决策。

**差距**: 用户不知道 DeepSeek 还剩多少配额。报表里有历史成本，但没有"本月预算还剩多少"。

### 🟡 差距 3: 凭据轮转/多 Key 支持

旧体系的 `antigravity` 账号池支持多 Google 账号轮转。AetherForge 每个 Provider 只支持一个 API Key。

---

## 四、融合方案

### Phase 1: 凭据存储 SQLite 化 (cc-switch 遗产复活)

```
~/.aetherforge/credentials.db
├── providers 表: name, api_key, base_url, is_active
├── models    表: model_id, provider, cost_per_1k, capabilities
└── quotas    表: provider, tpm_limit, rpm_limit, monthly_budget
```

```bash
# CLI 管理凭据
aetherforge credentials add openai --key sk-xxx
aetherforge credentials list
aetherforge credentials remove openai
```

不再需要 export 环境变量。`create_provider()` 自动从 SQLite 读取凭据。

### Phase 2: 配额外部化 (codexbar 遗产复活)

两种模式：

```yaml
# aetherforge.yaml
rate_limiter:
  mode: local        # 本地硬编码 (当前)
  mode: codexbar     # 通过 codexbar CLI 查询
  mode: static_file  # 从 YAML 加载配额
```

当 `mode: codexbar` 时，`RateLimiter` 改为调用 `codexbar usage --json` 获取实时配额。

### Phase 3: 凭据池 + 自动轮转

```yaml
gateway:
  providers:
    openai:
      keys:
        - key: sk-primary
          weight: 80
        - key: sk-secondary
          weight: 20
```

请求按权重分发到不同 Key，一个 Key 触发限流时自动切换到另一个。

---

## 五、结论

| 旧能力 | 当前状态 | 优先级 | 建议 |
|:-------|:--------:|:------:|:-----|
| cc-switch 凭据 SQLite | ❌ 丢失 | 🟡 P1 | Phase 1 恢复 |
| codexbar 配额外部化 | ❌ 丢失 | 🟡 P1 | Phase 2 恢复 |
| antigravity 凭据池 | ❌ 丢失 | 🟢 P2 | Phase 3 |
| L0 M1 模型注册 | 🟡 半覆盖 | 🟢 P2 | 打通 YAML → 运行时同步 |
| 定时收割 | 🟢 覆盖 | — | 维持 |

**关键结论**: AetherForge 没有"丢掉" cc-switch 和 codexbar 的设计，而是在 Gateway 层用更标准的方式（环境变量 + RateLimiter + CostTracker）重新实现了。但**集中凭据管理**和**外部配额源**确实是丢失的设计意图，建议按 Phase 1 → Phase 2 逐步恢复。
