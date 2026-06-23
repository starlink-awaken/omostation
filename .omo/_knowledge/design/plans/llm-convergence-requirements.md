---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# LLM 调用统一收敛 — 需求规格说明书

> 文档编号: REQ-2026-LLM-CONVERGE-v1.0
> 状态: draft planning input | 优先级: P0 | 关联: Phase 2 M2.2-M2.4
> 发起人: reasonix-code | 审阅人: [待指定]
> 创建日期: 2026-05-30
> 规划落点: `llm-convergence-planning-packet.md`

---

## 1. 背景与问题陈述

### 1.1 当前架构

omostation 当前存在 **3 套独立的 LLM 调用路径**，各自管理自己的 API key、模型选择和调用逻辑：

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM 调用现状（碎片化）                      │
│                                                             │
│  agent-runtime ────→ urllib.request（参数化，默认 DeepSeek）  │
│                                                             │
│  gbrain         ────→ AI Gateway（per-touchpoint 默认模型)    │
│                     │  chat=Anthropic · expansion=Anthropic  │
│                     │  embedding=ZeroEntropy                 │
│                                                             │
│  LiteLLM        ────→ 独立部署（:4000），但未被实际接入       │
│                                                             │
│  sophia/ssot/    ────→ 各自直连 DeepSeek/OpenAI（碎片化）     │
│  ontoderive/                                                   │
│  metaos                                                      │
│                                                             │
│  KOS            ────→ 无直接 LLM 调用（通过 Minerva 间接）     │
│  Minerva CLI    ────→ cli.py 硬编码 DeepSeek/LongCat/GLM     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 现存问题

| 问题 | 影响 | 严重度 |
|------|------|:------:|
| API key 分散在多个组件中 | 泄漏面大，轮换困难 | 🔴 严重 |
| LLM 调用碎片分布在 7+ 组件中 | 各自维护 base_url/api_key，不一致风险高 | 🔴 严重 |
| agent-runtime 无统一 base_url 抽象 | 虽已参数化，但无中央管控 | 🟡 中等 |
| 无统一成本追踪 | 不知道每月 LLM 花费 | 🟡 中等 |
| 无 Fallback 机制 | OpenAI 挂了整个系统不能用 | 🟡 中等 |
| 本地开发必须用真实 API | 无法离线开发、测试成本高 | 🟡 中等 |
| gbrain 和 agent-runtime 各自维护 LLM 配置 | 配置分散，不一致风险 | 🟡 中等 |

### 1.3 愿景目标

> 所有 LLM 调用通过 **LiteLLM** 统一路由。各组件不再直接管理 API key 和模型选择，只指向 `http://localhost:4000/v1`（兼容 OpenAI 格式）。

---

## 2. 目标架构

### 2.1 收敛后架构

```
                    ┌──────────────────────────────┐
                    │       LiteLLM Proxy          │
                    │       localhost:4000          │
                    │                              │
                    │  ┌──── 路由规则 ──────────┐   │
                    │  │  agent-runtime → gpt-4o │   │
                    │  │  gbrain       → claude  │   │
                    │  │  local dev    → ollama  │   │
                    │  │  minerva      → qwen    │   │
                    │  └────────────────────────┘   │
                    │                              │
                    │  Providers:                   │
                    │  OpenAI · Anthropic · Gemini  │
                    │  DeepSeek · Ollama · Groq     │
                    └──────────┬───────────────────┘
                               │
          ┌────────────────────┼──────────────────────────┐
          │                    │                          │
          ▼                    ▼                          ▼
   agent-runtime          gbrain                   Minerva CLI
   (设 env var)      (扩展 litellm recipe,         (cli.py 硬编码
                      改默认模型)                   清理 → env var)

   sophia · ssot · ontoderive · metaos
   (碎片收敛 → 统一 env var 机制)
```

### 2.2 关键原则

1. **LiteLLM 是唯一入口**：所有组件只配置 `base_url=http://localhost:4000/v1`，不配置具体 provider key
   - **架构选择：fail-closed**。LiteLLM 宕机时各组件不可用（生产环境），开发环境通过 `LLM_FALLBACK_DIRECT=true` 可临时启用直连
2. **兼容 OpenAI 格式**：LiteLLM 暴露 `/v1/chat/completions` 接口，完全兼容 OpenAI SDK
3. **不改各组件业务逻辑**：只改 LLM client 初始化处的 `base_url`，不影响 tool call、function calling 等业务逻辑
4. **渐进式迁移**：可以一个组件一个组件改，不改的组件仍然走原来的直连路径
5. **回滚机制**：改坏了只需把 `base_url` 改回原来的值

---

## 3. 范围定义

### 3.1 包含范围（In Scope）

| 组件 | 文件 | 当前调用方式 | 目标 |
|------|------|-------------|------|
| agent-runtime | `src/agent_runtime/engine.py` → `_call_llm()` | `urllib.request`，默认 DeepSeek，通过 `AGENT_RUNTIME_BASE_URL` 环境变量可配置 | 设 env var（无需改代码） |
| gbrain | `src/core/ai/recipes/litellm-proxy.ts` | 已有 LiteLLM recipe，但仅定义了 embedding touchpoint | 扩展 recipe 添加 chat/expansion，设为默认 provider |
| gbrain | `src/core/ai/gateway.ts` | per-touchpoint 默认模型（chat=Anthropic, expansion=Anthropic, embedding=ZeroEntropy） | 添加 LiteLLM 为首选，保留其他 provider 为 fallback |
| Minerva CLI | `src/minerva/cli.py:114-134` | 3 处硬编码直连（DeepSeek/LongCat/GLM） | 改为从环境变量读取，默认指向 `:4000/v1` |
| sophia | `src/sophia/server/mcp_server.py:57` | `AsyncOpenAI(base_url="https://api.deepseek.com")` | base_url → `:4000/v1` |
| ssot | `src/ssot_kernel/extractor/llm.py:134` | `OpenAIBackend(base_url="https://api.openai.com/v1")` | base_url → `:4000/v1` |
| ontoderive | `engine/intelligence/providers.py:74` | `OpenAI(base_url=self.base_url or None)` | base_url → `:4000/v1` |
| metaos | `src/metaos/layers/m_layer.py:48` | `requests.post(url=OLLAMA_BASE_URL)` | base_url → `:4000/v1` |
| LiteLLM 配置 | `/tmp/litellm_config.yaml` | 仅配了 OpenAI/Anthropic | 按实际可用的 provider 配置，对齐 gbrain 模型 |
| 测试套件 | `tests/integration/*.py` | 直接检查 `:4000/health` | 改为检查具体 model 可用性 |

### 3.2 不包含范围（Out of Scope）

| 项目 | 理由 |
|------|------|
| agentmesh 接入 LiteLLM | adapter 已存在，等 agentmesh 正式上线时接 |
| KOS 内部 LLM 调用 | 无直接调用（通过 Minerva 间接），Minerva CLI 已在 In Scope |
| 成本追踪面板 | LiteLLM 内置，但 UI 集成留到 Phase 3 |
| 模型自动回退链 | LiteLLM 支持，但配置策略需人工决定 |
| 本地 Ollama 部署 | 开发环境可选，不强制 |

### 3.3 受影响组件清单

| 组件 | 需要修改 | 改动量 | 风险 |
|------|:--------:|:------:|:----:|
| agent-runtime engine.py | ❌ 不改代码，设 env var | 0 行 | 🟢 低（纯配置变更） |
| agent-runtime tools.py | ❌ 不改 | 0 | —（已确认 _call_llm 是唯一路径） |
| gbrain litellm-proxy.ts | ✅ 扩展 recipe | ~10 行 | 🟢 低（新增 touchpoint 定义） |
| gbrain gateway.ts | ✅ 改默认 provider | ~10 行 | 🟡 中（需验证 fallback 逻辑） |
| gbrain defaults.ts | ✅ 改默认模型 | ~5 行 | 🟢 低 |
| Minerva CLI cli.py | ✅ 清理硬编码 | ~15 行 | 🟡 中（涉及 3 个 provider） |
| sophia mcp_server.py | ✅ base_url 配置化 | ~5 行 | 🟢 低 |
| ssot extractor/llm.py | ✅ base_url 默认值改 env var | ~5 行 | 🟢 低 |
| ontoderive providers.py | ✅ base_url 默认值改 env var | ~5 行 | 🟢 低 |
| metaos m_layer.py | ✅ LLM_BASE_URL 统一 | ~5 行 | 🟢 低 |
| LiteLLM config.yaml | ✅ 增加 provider 定义 | ~20 行 | 🟢 低（纯配置） |
| 测试套件 | ✅ 更新端点 | ~10 行 | 🟢 低 |

---

## 4. 详细需求

### 4.1 LiteLLM 配置需求 (REQ-CONFIG-01)

```
优先级: P0
描述: LiteLLM 配置至少包含一个可用的 provider，不再依赖 OpenAI/Anthropic
验收标准:
  - LiteLLM 启动后 `curl :4000/health` 返回 healthy_count > 0
  - 至少一个 model 可通过 `curl :4000/v1/chat/completions` 调用成功
  - 配置文件中不包含未配置 API key 的 provider（避免 health check 报错）
配置方式:
  - 从环境变量读取 API key
  - 支持 Ollama（本地）、Gemini、DeepSeek 等替代 provider
```

### 4.2 agent-runtime 迁移需求 (REQ-AGENT-01)

```
优先级: P0
描述: agent-runtime 通过环境变量指向 LiteLLM，无需修改代码
当前代码:
  projects/kairon/packages/agent-runtime/src/agent_runtime/engine.py
  → _call_llm() 使用 urllib.request，完全参数化

当前支持:
  - AGENT_RUNTIME_PROVIDER（默认 deepseek）
  - AGENT_RUNTIME_BASE_URL（支持任意 base_url 覆盖）
  - AGENT_RUNTIME_API_KEY（链式回退到 Hermes credential pool）

修改要求:
  1. 在部署脚本/启动命令中设 AGENT_RUNTIME_BASE_URL=http://localhost:4000/v1
  2. 设 AGENT_RUNTIME_API_KEY=sk-litellm-proxy（占位值，LiteLLM 不验证 key）
  3. 保留现有代码不变（环境变量覆盖本身就是支持的方式）
  4. 不改动 tool calling、function calling、streaming 等业务逻辑

回滚方案:
  将 AGENT_RUNTIME_BASE_URL 改回空值或 https://api.deepseek.com 即可

验收标准:
  - 设置 env var 后 agent-runtime /health 返回正常
  - agent-runtime /chat 可正常响应（需 LiteLLM 有可用模型）
  - 无回归：原有功能（tool call、streaming）不受影响
```

### 4.3 gbrain 默认 provider 需求 (REQ-GBRAIN-01)

```
优先级: P1
描述: 让 gbrain 的 chat/expansion/embedding 调用默认走 LiteLLM
当前架构:
  - per-touchpoint 默认模型（chat=Anthropic, expansion=Anthropic, embedding=ZeroEntropy）
  - litellm-proxy.ts recipe 已注册，但仅定义了 embedding touchpoint

前置条件:
  先扩展 litellm-proxy.ts recipe 定义 chat 和 expansion touchpoint

修改要求:
  1. litellm-proxy.ts: 添加 chat 和 expansion touchpoint
  2. defaults.ts: 将默认 chat/expansion 模型改为 litellm:gpt-4o / litellm:claude-... 等
  3. 保留其他 recipe（openai, anthropic, ollama 等）作为 fallback 选项
  4. 不改动 gbrain 的业务逻辑（search、takes、dream cycle 等）

验收标准:
  - gbrain 测试套件通过（bun test）
  - gbrain 的 AI 调用通过 LiteLLM 路由
  - 当 LiteLLM 不可用时，自动 fallback 到其他 provider
```

### 4.4 Minerva CLI 迁移需求 (REQ-MINERVA-01)

```
优先级: P1
描述: 清理 Minerva CLI 中 3 处硬编码的直连 LLM 调用
当前代码:
  projects/kairon/packages/minerva/src/minerva/cli.py:114-134

硬编码列表:
  1. cli.py:114 → OpenAICompatibleClient(base_url="https://api.deepseek.com")
  2. cli.py:122 → OpenAICompatibleClient(base_url="https://api.longcat.chat/openai")
  3. cli.py:130 → OpenAICompatibleClient(base_url="https://open.bigmodel.cn/api/paas/v4")

修改要求:
  1. 将 cli.py 中硬编码的 base_url 改为从环境变量或配置对象读取
  2. 默认指向 http://localhost:4000/v1
  3. 保留通过环境变量显式指定特定 provider 的能力（用于调试/测试）
  4. 不改动 Minerva 核心 LLM client（OpenAICompatibleClient 已是参数化的）

验收标准:
  - Minerva CLI 在不设特殊环境变量时走 LiteLLM
  - 设环境变量可覆盖回直连（如 DEEPSEEK_BASE_URL 等）
  - 无回归：cli.py 原有功能不变
```

### 4.5 碎片收敛需求 (REQ-OTHER-01)

```
优先级: P2
描述: 收敛 sophia/ssot/ontoderive/metaos 的 LLM 调用到 LiteLLM
当前调用点:
  - sophia:  mcp_server.py:57     → AsyncOpenAI(base_url="https://api.deepseek.com")
  - ssot:    extractor/llm.py:134 → OpenAIBackend(base_url="https://api.openai.com/v1")
  - ontoderive: providers.py:74   → OpenAI(base_url=self.base_url or None)
  - metaos:  m_layer.py:48        → requests.post(url=OLLAMA_BASE_URL)

修改要求:
  1. sophia mcp_server.py: AsyncOpenAI base_url 改为从 env var 读取
  2. ssot extractor/llm.py: OpenAIBackend base_url 默认值改为 env var
  3. ontoderive providers.py: base_url 默认值改为 env var
  4. metaos m_layer.py: OLLAMA_BASE_URL → LLM_BASE_URL 统一环境变量
  5. 所有改动兼容现有行为（env var 未设时保持当前行为）

验收标准:
  - 以上 4 个组件的 LLM 调用在默认配置下走 :4000/v1
  - 通过环境变量可覆盖控制各自的行为
  - 无回归：现有功能不受影响
```

### 4.6 测试验证需求 (REQ-TEST-01)

```
优先级: P1
描述: 验证 LLM 收敛后的全链路可用性

新增测试覆盖:
  1. agent-runtime → LiteLLM 连通性测试
  2. gbrain → LiteLLM 连通性测试（利用已有测试框架）
  3. LiteLLM 不可用时的降级行为测试

更新现有测试:
  - test-e2e-phase1.py LiteLLM health check 改为检查 model 可用性
  - test-perf-baseline.py 更新 LiteLLM 端点延迟基线

验收标准:
  - 所有测试通过（烟雾、E2E、故障注入、性能基线）
  - LiteLLM 宕机时各组件正确降级，不崩溃
```

### 4.7 配置环境变量需求 (REQ-ENV-01)

```
优先级: P2（后续迭代）
描述: 统一 LLM 配置环境变量

新增环境变量:
  LLM_PROVIDER         # 默认: litellm，可选: openai, anthropic, ollama
  LLM_BASE_URL         # 默认: http://localhost:4000/v1
  LLM_API_KEY          # 默认: sk-litellm-proxy（占位）
  LLM_MODEL            # 默认: gpt-4o-mini（可根据组件覆盖）

现状说明:
  - agent-runtime 已支持 AGENT_RUNTIME_BASE_URL 等变量，与统一方案兼容
  - Minerva CLI 和碎片组件收敛后将采用相同机制

当前阶段:
  先通过各组件已有的 env var 机制实现收敛
  环境变量标准化与统一命名留到 Phase 3
```

---

## 5. 实施计划

### 5.1 阶段一：LiteLLM 配置调整（预计 0.5 天）

**前置条件**：
```
□ docker ps | grep litellm      # 确认 LiteLLM 容器运行中
□ curl localhost:4000/health     # 确认 health check 正常
□ echo $OPENAI_API_KEY           # 确认至少一个 provider 的 API key 已配置
```

```
步骤 1.1: 确认可用的 provider（Ollama/Gemini/DeepSeek/其他）
步骤 1.2: 更新 LiteLLM config.yaml，移除不可用的 provider，对齐 gbrain 模型
步骤 1.3: 验证 curl :4000/health 返回 healthy_count > 0
步骤 1.4: 用 curl 测试 /v1/chat/completions 能正常返回
```

### 5.2 阶段二：agent-runtime 接入（预计 0.25 天）

**前置条件**：
```
□ cd projects/kairon/packages/agent-runtime && make test    # 当前测试通过
```

```
步骤 2.1: 确认 engine.py 已支持 AGENT_RUNTIME_BASE_URL / AGENT_RUNTIME_API_KEY（已支持）
步骤 2.2: 在部署脚本/启动配置中设：
  export AGENT_RUNTIME_BASE_URL=http://localhost:4000/v1
  export AGENT_RUNTIME_API_KEY=sk-litellm-proxy
步骤 2.3: 运行 agent-runtime 测试确认无回归
步骤 2.4: 启动 agent-runtime 验证 /chat 响应
```

### 5.3 阶段三：gbrain 接入（预计 1 天）

**前置条件**：
```
□ cd projects/gbrain && bun test  # 当前测试通过
□ litellm-proxy.ts recipe 已扩展 chat/expansion touchpoint（代码修改前置）
```

```
步骤 3.1: 扩展 litellm-proxy.ts recipe → 增加 chat 和 expansion touchpoint
步骤 3.2: 在 defaults.ts 中将默认模型改为 litellm:gpt-4o / litellm:claude-... 等
步骤 3.3: 运行 bun test
步骤 3.4: 验证 gbrain AI 调用路径（chat + expansion + embedding）
```

### 5.4 阶段四：Minerva CLI + 碎片收敛（预计 1.5 天）

**前置条件**：
```
□ cd projects/kairon/packages/minerva && make test    # 当前测试通过
□ cd projects/kairon/packages/sophia && make test      # 当前测试通过
□ cd projects/kairon/packages/ssot && make test        # 当前测试通过
```

```
步骤 4.1: 清理 Minerva CLI cli.py 中 3 处硬编码 base_url → env var
步骤 4.2: sophia mcp_server.py AsyncOpenAI base_url → env var
步骤 4.3: ssot extractor/llm.py OpenAIBackend base_url 默认值 → env var
步骤 4.4: ontoderive providers.py base_url 默认值 → env var
步骤 4.5: metaos m_layer.py OLLAMA_BASE_URL → LLM_BASE_URL 统一
步骤 4.6: 各组件测试通过
```

### 5.5 阶段五：测试与验证（预计 0.5 天）

**前置条件**：
```
□ 全量测试套件执行前基线（smoke + E2E + 故障注入 + 用户旅程）已通过
□ 各组件均已接入：agent-runtime, gbrain, Minerva CLI, sophia, ssot, ontoderive, metaos
```

```
步骤 5.1: 运行全量测试套件（烟雾 + E2E + 故障注入 + 用户旅程）
步骤 5.2: 验证 LiteLLM 宕机时各组件降级行为
步骤 5.3: 更新性能基线
步骤 5.4: 设置 LLM_FALLBACK_DIRECT=true 验证直连 fallback 可用
```

### 5.6 里程碑与交付

| 里程碑 | 产出 | 验收人 |
|--------|------|--------|
| M1 | LiteLLM 配置就绪，health check 通过 | agent |
| M2 | agent-runtime 走 LiteLLM，测试通过（纯配置变更） | agent + reviewer |
| M3 | gbrain + Minerva CLI 走 LiteLLM，测试通过 | agent + reviewer |
| M4 | 碎片收敛：sophia/ssot/ontoderive/metaos 接入，测试通过 | agent + reviewer |
| M5 | 全量测试通过，性能基线更新 | reviewer |

---

## 6. 风险与回滚

### 6.1 风险登记册

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|----------|
| LiteLLM 与 OpenAI SDK 不完全兼容 | 低 | 高 | 先用简单请求测试兼容性，streaming/tool call 逐项验证 |
| agent-runtime `urllib.request`（同步）与 async 框架混合可能导致事件循环阻塞 | 低 | 中 | 验证 agent-runtime 是否在 async 上下文中调用 `_call_llm`；如在，考虑用 `asyncio.to_thread` 或换成 `httpx.AsyncClient` |
| gbrain recipe 扩展后 litellm-proxy.ts 的 chat/expansion touchpoint 与 gateway 路由逻辑不兼容 | 低 | 中 | 先在小范围验证 recipe 扩展，确认 model resolution 正常工作后全量切换 |
| 多组件同时修改后排查难度大 | 中 | 中 | 分阶段推进（5 个阶段），每个阶段独立验证；利用 git branch 隔离各阶段改动 |
| 本地无可用模型（Ollama 未装、API key 未配）| 中 | 高 | 开发环境通过 `LLM_FALLBACK_DIRECT=true` 启用直连 fallback |

### 6.2 架构选择与回滚方案

#### 架构选择：fail-closed 模式

本方案选择 **fail-closed（纯代理模式）**：
- LiteLLM 是唯一入口，各组件不保留直连 API key
- 优点：API key 集中管控，符合最小权限原则
- 缺点：LiteLLM 宕机时整个系统不可用

开发环境通过 `LLM_FALLBACK_DIRECT=true` 可临时启用直连 fallback，
但生产环境必须保持 fail-closed。

#### 回滚方案

```
agent-runtime 回滚:
  将 AGENT_RUNTIME_BASE_URL 改回空值或 https://api.deepseek.com
  将 AGENT_RUNTIME_API_KEY 改回原值或注释掉

gbrain 回滚:
  在 defaults.ts 中将默认模型改回 anthropic:claude-...
  如有需要，还原 litellm-proxy.ts recipe 扩展

Minerva CLI / 碎片组件回滚:
  恢复 env var 默认值或注释掉收敛代码

LiteLLM 回滚:
  docker stop litellm
  注意：fail-closed 模式下 LiteLLM 停止后各组件不可用
  开发环境可通过 LLM_FALLBACK_DIRECT=true 恢复直连

---

## 7. 验收检查清单

### 7.1 功能验收

```
□ LLM-PASS-01: LiteLLM :4000/health 返回 healthy_count > 0
□ LLM-PASS-02: 通过 LiteLLM 成功调用一次 chat completion
□ LLM-PASS-03: agent-runtime /health 返回正常
□ LLM-PASS-04: agent-runtime /chat 能正常响应
□ LLM-PASS-05: gbrain AI 调用走 LiteLLM 路径
□ LLM-PASS-06: LiteLLM 宕机时组件不崩溃（优雅降级）
□ LLM-PASS-07: Minerva CLI 默认走 LiteLLM（不设 env var 时）
□ LLM-PASS-08: sophia LLM 调用走 LiteLLM
□ LLM-PASS-09: ssot LLM 调用走 LiteLLM
□ LLM-PASS-10: ontoderive LLM 调用走 LiteLLM
□ LLM-PASS-11: metaos LLM 调用走 LiteLLM
□ LLM-PASS-12: 设 LLM_FALLBACK_DIRECT=true 时各组件的直连 fallback 可用
```

### 7.2 测试验收

```
□ LLM-TEST-01: 烟雾测试 5/5 PASS
□ LLM-TEST-02: E2E 全链路 11/11 PASS
□ LLM-TEST-03: 故障注入 5/5 PASS（含 LiteLLM 宕机场景）
□ LLM-TEST-04: 用户旅程 5/5 PASS
□ LLM-TEST-05: 性能基线采集完成
□ LLM-TEST-06: gbrain bun test 通过
```

### 7.3 架构验收

```
□ LLM-ARCH-01: 所有组件不再直接管理 API key（通过 LiteLLM 集中管理）
□ LLM-ARCH-02: 各组件 LLM 调用统一走 :4000/v1
□ LLM-ARCH-03: 没有新的 LLM 调用碎片引入
□ LLM-ARCH-04: 回滚方案文档化且可行
```

---

## 8. 附录

### A. 当前调用点清单

```
agent-runtime:
  engine.py:_call_llm() — 约行 120-160
  → urllib.request(url=f"{base_url}/chat/completions")
  → base_url 取自 AGENT_RUNTIME_BASE_URL（默认 https://api.deepseek.com）
  → api_key 从 env var / Hermes credential pool 链式解析
  → 收敛方式：设 AGENT_RUNTIME_BASE_URL=http://localhost:4000/v1（0 行代码修改）

gbrain:
  src/core/ai/gateway.ts — per-touchpoint 默认模型
  src/core/ai/recipes/litellm-proxy.ts — 已注册，仅 embedding touchpoint
  → 收敛方式：扩展 recipe + 改默认模型

Minerva CLI:
  cli.py:114 → OpenAICompatibleClient(base_url="https://api.deepseek.com")
  cli.py:122 → OpenAICompatibleClient(base_url="https://api.longcat.chat/openai")
  cli.py:130 → OpenAICompatibleClient(base_url="https://open.bigmodel.cn/api/paas/v4")
  → 收敛方式：清理硬编码 → env var

sophia:
  mcp_server.py:57 → AsyncOpenAI(base_url="https://api.deepseek.com")
  → 收敛方式：base_url → env var

ssot:
  extractor/llm.py:134 → OpenAIBackend(base_url="https://api.openai.com/v1")
  → 收敛方式：默认值 → env var

ontoderive:
  providers.py:74 → OpenAI(base_url=self.base_url or None)
  → 收敛方式：默认值 → env var

metaos:
  m_layer.py:48 → requests.post(url=OLLAMA_BASE_URL)
  → 收敛方式：OLLAMA_BASE_URL → LLM_BASE_URL 统一变量

LiteLLM:
  docker 容器，端口 :4000
  配置: /tmp/litellm_config.yaml
```

### B. LiteLLM 配置模板

```yaml
# /tmp/litellm_config.yaml — 收敛后的最小配置
# 模型版本与 gbrain 实际使用的模型对齐
model_list:
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: anthropic/claude-sonnet-4-6-20251001    # 与 gbrain DEFAULT_CHAT_MODEL 对齐
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: claude-haiku-4-5
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001      # 与 gbrain DEFAULT_EXPANSION_MODEL 对齐
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: gpt-4o-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
  - model_name: gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-2.0-flash-001             # 去掉 exp 后缀，用稳定版
      api_key: os.environ/GEMINI_API_KEY
  - model_name: deepseek-chat
    litellm_params:
      model: deepseek/deepseek-chat
      api_key: os.environ/DEEPSEEK_API_KEY
  - model_name: ollama-qwen
    litellm_params:
      model: ollama/qwen3.6:35b                       # 与 Minerva 默认模型对齐
      api_key: fake-key-not-needed
```

### C. agent-runtime 修改参考

```python
# agent-runtime engine.py 当前代码（无需修改）：
# _call_llm() 使用 urllib.request，base_url 完全参数化

# 收敛方式（生产环境部署）:
# 在启动命令/部署脚本中设置环境变量:
#   export AGENT_RUNTIME_BASE_URL=http://localhost:4000/v1
#   export AGENT_RUNTIME_API_KEY=sk-litellm-proxy

# 验证方式:
#   curl localhost:4000/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'

# 回滚:
#   unset AGENT_RUNTIME_BASE_URL
#   # 或设为: export AGENT_RUNTIME_BASE_URL=https://api.deepseek.com
```

### D. gbrain 修改参考

```typescript
// 修改前（litellm-proxy.ts — 只有 embedding touchpoint）:
export const litellmProxy: Recipe = {
  id: 'litellm',
  name: 'LiteLLM Proxy (universal)',
  tier: 'openai-compat',
  implementation: 'openai-compatible',
  base_url_default: 'http://localhost:4000',
  touchpoints: {
    embedding: { models: [], user_provided_models: true, default_dims: 0, ... },
  },
};

// 修改后: 增加 chat 和 expansion touchpoint
export const litellmProxy: Recipe = {
  id: 'litellm',
  name: 'LiteLLM Proxy (universal)',
  tier: 'openai-compat',
  implementation: 'openai-compatible',
  base_url_default: 'http://localhost:4000',
  touchpoints: {
    chat:      { models: [], user_provided_models: true, ... },   // 新增
    expansion: { models: [], user_provided_models: true, ... },   // 新增
    embedding: { models: [], user_provided_models: true, ... },   // 已有
  },
};

// 修改前（defaults.ts）:
// const DEFAULT_CHAT_MODEL = 'anthropic:claude-sonnet-4-6';

// 修改后:
// const DEFAULT_CHAT_MODEL = 'litellm:claude-sonnet-4-6';
```

---

> 本文档由 reasonix-code 于 2026-05-30 创建，供架构 agent 审阅。
> 审阅后请更新状态并反馈修改意见。
