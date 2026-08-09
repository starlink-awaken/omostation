---
status: active
lifecycle: design
owner: xiamingxing
last-reviewed: 2026-08-09
---

# AetherForge 收敛设计 — 调度层定位与 LiteLLM 接管

> 依据一次代码级勘查,并已按 `feat/aetherforge-unification` 分支的最新进展修订。
> 按 [`doc-ssot-contract`](../../.omo/standards/doc-ssot-contract.md),文中不写包数、
> 行数、测试数等易变值 —— 复核方法见 §10。

## 1. 这份文档解决什么

1. **LiteLLM 要下线**,它占的"统一 LLM 入口"需要有人接管
2. **三个包与 omlxc / LM Link / wsvc 的边界模糊**,有重复风险
3. **swarm_engine 的定位** —— 它正在从"引擎"长出"场景"

核心判断:**架构本身是好的,不需要重构。** 缺的是门面、别名与接入,而其中门面
已在分支上完成(§5)。

## 2. 定位:调度层,不是运行时

> **AetherForge 把"我要什么"翻译成"谁来做、用哪块算力、花多少钱"。
> 模型怎么跑,是 omlx / LM Studio 的事。**

后续所有边界争议回到这句:**凡"决定"的归 aetherforge,凡"执行"的不归。**

## 3. 三层职责与依赖方向

三个包是三个**粒度**,不是三个同层模块 —— 这是它们不重叠的根本原因。

| 包 | 粒度 | 回答的问题 | 典型职责 |
|---|---|---|---|
| `llm_gateway` | 一次调用 | 这个请求发给谁? | provider 抽象、路由、配额、凭据、**OpenAI 门面** |
| `compute_mesh` | 一片算力 | 现在有哪些算力、多贵? | 拓扑扫描、健康、成本、zone 亲和、唤醒 |
| `swarm_engine` | 一个目标 | 这件事拆几步、谁来做? | 任务分解、竞价、仲裁、**领域 worker** |

依赖单向,**不得反转**:

```
        swarm_engine ──┐
                       ├──→ llm_gateway
        compute_mesh ──┘
```

`src/aetherforge/{gateway,mesh,swarm}` 是 compatibility shim(纯 re-export)。
**这层要保留** —— 它让外部无需知道 `llm_gateway` / `compute_mesh` / `swarm_engine`
这些内部包名,内部实现才可替换。

### 3.1 `compute_mesh` 的一处澄清

它扫的是 **provider 拓扑**(本地 ollama、OpenAI、Anthropic、Gemini、DeepSeek 等
endpoint),`ComputeNode` 的核心属性是 `base_url` / 成本 / zone。

**它不是"跨机器的模型池"。** 名字里的 mesh 指 provider 网格,不是机器网格。
跨机器模型聚合由 LM Link 承担(§4.2)。

## 4. 与外部组件的边界

| 组件 | 它负责 | 与 aetherforge 的关系 |
|---|---|---|
| **omlxc** | 本机模型生命周期:加载/卸载/预热/常驻 | **单向供给**。读它的模型清单,不反向管理 |
| **LM Link** | 跨机器模型池,OpenAI 兼容端点 | **作为一个 provider node** 被 mesh 扫入 |
| **wsvc** | 服务进程级管控 | OpenAI 门面**作为被管服务**登记 |
| **cockpit** | 展示 | **只消费不自算** |
| **agora / BOS** | 能力路由与寻址 | 通过 BOS URI 暴露能力 |

### 4.1 omlxc:单向供给

omlxc 是**管理面**(模型级),aetherforge 是**调度面**(请求级)。
模型端口等运行时事实应**运行时读取**,不做副本、不做定期同步 —— 单一事实源。

> 现状债:目前存在一条半自动同步链路,改为运行时读取是阶段一的一项。

### 4.2 LM Link:不重复造跨机聚合

LM Link 已原生完成跨机模型池化并提供 OpenAI 兼容端点。`compute_mesh` **不应**
再实现一套跨机发现,而应把该端点当作一个 provider node 纳入拓扑,从而保留自己
独有的价值(成本核算、zone 亲和、唤醒、健康历史)。

## 5. 接管 LiteLLM

### 5.1 缺口已从"一个"变成"半个"

先前判断:唯一硬缺口是 OpenAI 兼容 HTTP 门面 —— `llm_gateway` 是**库**,
LiteLLM 是**服务**,消费者要的是后者。

**该缺口已在 `feat/aetherforge-unification` 分支上补齐**:
`packages/gateway/src/llm_gateway/openai_proxy.py` 基于 aiohttp,暴露
`/v1/chat/completions`、`/v1/models`、`/v1/embeddings`、`/health`,
以 `python -m llm_gateway.openai_proxy` 启动,端口已在
[`protocols/port-registry.yaml`](../../protocols/port-registry.yaml) 登记为
`llm-gateway`。

同分支还新增 `src/aetherforge/bridge.py`,自述为 workspace 内 Python 模块的
**唯一 LLM 入口**(`llm_generate` / `llm_embed` / `llm_list_models` / `llm_health`)。

于是形成两级入口,**职责要分清**:

| 入口 | 面向 | 何时用 |
|---|---|---|
| `aetherforge.bridge` | 仓内 Python 模块 | 进程内直调,无网络开销 |
| `openai_proxy`(HTTP) | 外部工具、非 Python、跨机 | 任何只会说 OpenAI 协议的客户端 |

**两者必须共用同一个 `ModelGateway` 与同一份路由策略**,否则会出现"库里能路由、
HTTP 里路由不同"的双份真相。

### 5.2 仍缺的部分

| 项 | 状态 |
|---|---|
| OpenAI HTTP 门面 | ✅ 分支已实现,**待合并** |
| 库级统一入口 `bridge` | ✅ 分支已实现,**待合并** |
| **别名层**(coding / reasoning / triage → 具体模型) | ❌ **门面中完全没有** |
| 鉴权 | ⚠️ 有痕迹,需核实是否为真实校验而非文档示例 |
| 成本落账 | ⚠️ `compute_mesh` 有实现,未接通门面 |

**别名层是当前第一缺口。** 它决定消费者能否无痛从 LiteLLM 切过来 ——
LiteLLM 侧用的是 `coding` / `reasoning` 这类名字,不是原始模型 ID。

按 §2 的定位,别名属于**调度决策**,应落在 `llm_gateway` 内、由门面与 bridge
共用,**不应**放进 omlxc(那会把管理工具变成半个网关)。

### 5.3 前置阻塞

`agora` 的 MCP gateway 中 `llm_gateway` 相关能力被显式置为 `enabled: False`,
注为"依赖包缺失"。**跨项目依赖未打通,接管无从谈起。**

### 5.4 多 HTTP 面的收敛

除 OpenAI 门面外,`src/aetherforge/triage/server.py` 另有一个分诊 REST 服务
(端口亦已登记)。设计上二者并存是合理的(一个是通用 LLM 入口,一个是分诊领域
接口),但**必须都纳入 wsvc 管控并在 port-registry 有主**,不能再出现"跑着但没人
登记"的服务。

## 6. swarm_engine:从引擎到场景

### 6.1 判断更新

先前判断是"建成但未接入"。按分支最新进展,这一判断需要修订:
swarm 正在长出**领域 worker**(邮件收发与守护、截止期跟踪、健康巡检、文档生成、
管理场景),以及 `intelligent_agent` / `evolution_agent` / `risk_engine` /
`trust_adjuster` 等决策件。

**方向是对的**:引擎 + 场景 worker,而不是继续加通用抽象。

### 6.2 接入原则

**先把已有 worker 接到真实事件流,再加新 worker。** 通用化是"建成但未接入"的
成因,不是解法。

### 6.3 首个场景建议:多 worktree 并行协调

近期两起严重事故(子模块远端被清空、机器级配置被反复改写)根因相同:
**多 agent 在各自 worktree 并行作业,缺乏协调与仲裁**。而 `arbitrator`、
`conflict_resolver`、`binding_strategies` 正为此设计,且已有充分事故素材可作
验证集。

新增的 `health_agent` 与 `deadline_tracker` 可直接复用在这个场景上。

### 6.4 接入方式

**影子模式先行** —— swarm 观察真实事件流并产出建议,不实际执行动作;与人工处置
结果对账,证明判断质量后再放开执行权。

## 7. 路线(已按分支进展修订)

### 阶段一 · 前置

- **合并 `feat/aetherforge-unification` 到 aetherforge main** —— 门面与 bridge 都在这上面
- 打通 `agora` → `llm_gateway` 依赖,恢复其 MCP 能力
- 文档收敛:aetherforge 顶层有多份架构文档变体且多数久未更新,收敛为一份
- 模型端口改为运行时读取,取消同步链路

### 阶段二 · 接管

**补别名层** → 核实/补齐鉴权 → 接通成本落账
→ 门面登记进 `services.yaml` 并由 wsvc 管控
→ **先切一个消费者验证**(建议选调用频次低、失败可见的内部工具)
→ 全量切换 → LiteLLM 停用观察 → 清理

### 阶段三 · swarm 接入

多 worktree 协调场景,影子模式运行并对账。

## 8. 风险与硬约束

| 风险 | 约束 |
|---|---|
| 门面成为唯一入口 = 单点 | **启动路径不得有任何外部网络依赖。** LiteLLM 曾因启动时拉取远端数据而挂起,该模式不得复制 |
| 代理软件干扰 | 门面须显式隔离系统代理设置 |
| bridge 与门面路由不一致 | 二者**必须共用**同一 `ModelGateway` 实例与策略,不得各配一套 |
| 别名缺失导致切换失败 | 别名层是切换的前置,不是可选项 |
| 多个 HTTP 面失管 | 全部纳入 wsvc + port-registry |
| swarm 一次接太多 | 影子模式 + 单场景,不得直接接管治理主流程 |
| 新设计沦为又一份变体 | 阶段一必须完成文档收敛 |

## 9. 待决事项

- [ ] 别名的定义源:独立配置文件 vs 复用 omlx 模型清单里的键名
- [ ] `compute_mesh` 的成本核算是否上升为全局成本面(涉及与 cockpit 的边界)
- [ ] swarm 首个场景确认(本文档建议多 worktree 协调)
- [ ] `bridge` 与门面是否合并为同一进程内的两种调用方式

## 10. 如何复核本文档的判断

本文档刻意不写易变数字。复核方式:

| 判断 | 复核方式 |
|---|---|
| 各包规模 | `find packages/*/src -name '*.py' \| wc -l` |
| 测试是否通过 | `uv run python -m pytest packages/<pkg> -q` |
| 依赖方向 | `grep -rn 'llm_gateway' packages/mesh/src packages/swarm/src` |
| 外部调用方 | `grep -rn 'aetherforge\|llm_gateway' bin/ projects/*/src` |
| 门面是否已合并 | 查 `packages/gateway/src/llm_gateway/openai_proxy.py` 是否在 main |
| 门面端口归属 | 查 `protocols/port-registry.yaml` 中 `llm-gateway` 条目 |
| 别名层是否补上 | `grep -rin alias packages/gateway/src/llm_gateway/openai_proxy.py` |
| agora 依赖是否打通 | `grep -n 'enabled' projects/agora/src/agora/auth/mcp_gateway.py` |
