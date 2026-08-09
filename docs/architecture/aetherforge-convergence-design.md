---
status: active
lifecycle: design
owner: xiamingxing
last-reviewed: 2026-08-09
---

# AetherForge 收敛设计 — 调度层定位与 LiteLLM 接管

> 决策依据来自一次代码级现状勘查(2026-08-09)。文中不写包数、行数、测试数等易变值
> —— 按 [`doc-ssot-contract`](../../.omo/standards/doc-ssot-contract.md),这些从
> `packages/*/pyproject.toml`、`pytest` 实际结果、`docs/project-registry.yaml` 读取。
> 复核方法见文末 §9。

## 1. 这份文档解决什么

三个同时到期的问题:

1. **LiteLLM 要下线**(见 §4 背景),它占的"统一 LLM 入口"位置需要有人接管
2. **aetherforge 三个包职责边界模糊**,与 omlxc / LM Link / wsvc 有疑似重叠
3. **swarm_engine 建成但未接入** —— 有实现、有测试,仓内却无调用方

结论先行:**架构本身是好的,问题几乎全在接入面。** 不需要重构,需要补一层门面 + 选对第一个场景。

## 2. 定位:调度层,不是运行时

> **AetherForge 把"我要什么"翻译成"谁来做、用哪块算力、花多少钱"。
> 模型怎么跑,是 omlx / LM Studio 的事。**

这一句是本设计的宪法。后续所有边界争议,回到这句判断:
**凡是"决定"的,归 aetherforge;凡是"执行"的,不归。**

## 3. 三层职责与依赖方向

三个包对应三个**粒度**,不是三个同层模块 —— 这是它们不重叠的根本原因。

| 包 | 粒度 | 回答的问题 | 典型职责 |
|---|---|---|---|
| `llm_gateway` | 一次调用 | 这个请求发给谁? | provider 抽象、路由策略、配额、凭据 |
| `compute_mesh` | 一片算力 | 现在有哪些算力可用、多贵? | 拓扑扫描、健康、成本、zone 亲和、唤醒 |
| `swarm_engine` | 一个目标 | 这件事拆成几步、谁来做? | 任务分解、竞价分配、仲裁、收敛 |

依赖方向(**单向,不得反转**):

```
        swarm_engine ──┐
                       ├──→ llm_gateway
        compute_mesh ──┘
```

`compute_mesh` 引用 `llm_gateway` 的 `policies` / `scheduler` / `types`。
`src/aetherforge/{gateway,mesh,swarm}` 是 compatibility shim(纯 re-export),
对外提供稳定导入路径,内部实现可换。**这层要保留** —— 它是唯一让外部
不必知道 `llm_gateway` / `compute_mesh` / `swarm_engine` 这些内部包名的地方。

### 3.1 关于 `compute_mesh` 的一处澄清

`compute_mesh` 扫的是 **provider 拓扑**(本地 ollama、OpenAI、Anthropic、Gemini、
DeepSeek 等 endpoint),`ComputeNode` 的核心属性是 `base_url` / 成本 / zone。

**它不是"跨机器的模型池"。** 这一点容易误判 —— 名字里的 mesh 指的是
provider 网格,不是机器网格。跨机器模型聚合由 LM Link 承担(见 §4.2)。

## 4. 与外部组件的边界

系统里已经有多个"看起来在做类似事"的组件。边界必须写死,否则会再造重复
(近期已有多起重复/覆盖类事故,教训见 [`AGENTS.md`](../../AGENTS.md) 与治理 ADR)。

| 组件 | 它负责 | 与 aetherforge 的关系 |
|---|---|---|
| **omlxc** | 本机模型生命周期:加载/卸载/预热/常驻集 | **单向供给**。aetherforge 读它产出的模型清单,不反向管理 |
| **LM Link** | 跨机器模型池,暴露 OpenAI 兼容端点 | **作为一个 provider node** 被 `compute_mesh` 扫入 |
| **wsvc** | 服务进程级管控(起停/健康/端口) | aetherforge 的 HTTP 门面**作为被管服务**登记 |
| **cockpit** | 展示 | **只消费不自算**,调 aetherforge 的 API |
| **agora / BOS** | 能力路由与寻址 | aetherforge 通过 BOS URI 暴露能力 |

### 4.1 omlxc:单向供给

omlxc 是**管理面**(模型级),aetherforge 是**调度面**(请求级)。
模型端口等运行时事实,由 aetherforge **运行时读取** omlxc 的模型配置,
不做副本、不做定期同步 —— 单一事实源,少一个漂移面。

> 现状债:目前存在一条半自动同步链路。改为运行时读取是 §7 阶段一的一项。

### 4.2 LM Link:不要重复造跨机聚合

LM Link 已原生完成跨机器模型池化,并提供 OpenAI 兼容端点。
`compute_mesh` **不应**再实现一套跨机发现,而应把该端点当作一个 provider node
纳入拓扑。这样 mesh 保留自己独有的价值(成本核算、zone 亲和、唤醒、健康
历史),而不与 LM Link 争夺同一职责。

## 5. 接管 LiteLLM

### 5.1 背景

LiteLLM 的下线判断依据(独立于本设计,已单独评估):跨机聚合职能被 LM Link
取代;工具链中已标记 deprecated;无生产代码依赖;实际流量枯竭且云端回落链路
本身不可用;并且它是多起启动阻塞/端口冲突问题的来源。

### 5.2 缺口分析

对比 LiteLLM 提供的能力与 `llm_gateway` 现有能力:

| 能力 | `llm_gateway` 现状 |
|---|---|
| provider 抽象(本地 + 多家云) | ✅ 已有 |
| 路由策略 / 调度 | ✅ 已有 |
| 配额、凭据管理 | ✅ 已有 |
| 本地模型直连 | ✅ 已有 |
| 别名映射 | ⚠️ 有,但硬编码在代码里 |
| 回落链 | ✅ 已有 |
| **OpenAI 兼容 HTTP 端点** | ❌ **缺** |
| 成本落账 | ⚠️ `compute_mesh` 有实现,未接通 |

**唯一的硬缺口是 HTTP 门面。**
`llm_gateway` 是**库**,LiteLLM 是**服务**,而消费者要的是后者。

### 5.3 接管清单

1. **HTTP 门面** — `/v1/chat/completions`、`/v1/models`、`/v1/embeddings`,
   薄薄一层包住现有 gateway 入口。这是唯一需要新写的组件。
2. **别名配置化** — 把代码内的别名映射提升为配置,与模型清单同源。
3. **鉴权** — 单 token,绑定 tailnet + localhost,不对其他网段开放。
4. **成本落账** — 接通 `compute_mesh` 已有的成本记录。

### 5.4 前置阻塞

`agora` 的 MCP gateway 中,`llm_gateway` 相关能力被显式置为 `enabled: False`,
原因注为"依赖包缺失"。**跨项目依赖未打通,接管无从谈起** —— 这是阶段一的第一项。

## 6. swarm_engine 接入路径

### 6.1 问题不在代码,在入口

`swarm_engine` 有完整实现与通过的测试,但仓内无直接调用方,仅通过 BOS 的
stdio 能力暴露 —— 那是**一次性命令**,不是常驻能力。这解释了"建成但未接入"。

### 6.2 接入原则

**先选一个真实高频场景做第一个 workflow,不做通用平台化。**
通用化是"建成但未接入"的成因,不是解法。

### 6.3 首个场景建议:多 worktree 并行协调

近期两起严重事故(子模块远端被清空、机器级配置被反复改写)根因相同:
**多 agent 在各自 worktree 并行作业、缺乏协调与仲裁**。

而 `swarm_engine` 中已有 `arbitrator`、`conflict_resolver`、`binding_strategies`
等模块,正是为这类问题设计的。这是"真实痛点 × 现成能力"的交点,且已有充分的
事故素材可作验证集。

备选场景:PR 流水线(CI 失败 → 定位 → 修复 → 验证 → 合并)、事故响应闭环。

### 6.4 接入方式

**影子模式先行**:swarm 观察真实事件流并产出建议,不实际执行动作;
与人工处置结果对账,证明判断质量后再放开执行权。

## 7. 路线

### 阶段一 · 前置(解除阻塞)

- 打通 `agora` → `llm_gateway` 的跨项目依赖,恢复其 MCP 能力
- 文档收敛:aetherforge 顶层存在多份架构文档变体且多数久未更新,
  收敛为一份,其余标注归档并指向本文档
- 模型端口改为运行时读取,取消同步链路

### 阶段二 · 接管

HTTP 门面 → 别名配置化 → 鉴权 → 成本落账
→ **先切一个消费者验证**(建议选调用频次低、失败可见的内部工具)
→ 全量切换 → LiteLLM 停用观察 → 清理

### 阶段三 · swarm 接入

多 worktree 协调场景,影子模式运行并对账。

## 8. 风险与硬约束

| 风险 | 约束 |
|---|---|
| gateway 成为唯一入口 = 单点 | **HTTP 门面启动路径不得有任何外部网络依赖**。LiteLLM 曾因启动时拉取远端数据而挂起,该模式不得复制 |
| 代理软件干扰 | 门面须显式隔离系统代理设置 |
| 端口冲突 | 门面端口必须在 [`protocols/port-registry.yaml`](../../protocols/port-registry.yaml) 登记后使用 |
| swarm 规模大,一次接太多会失控 | 影子模式 + 单场景,不得直接接管治理主流程 |
| 新设计沦为又一份变体 | 阶段一必须先完成文档收敛,否则本文档只是新增的一份 |

## 9. 如何复核本文档的判断

本文档刻意不写易变数字。复核方式:

| 判断 | 复核命令 |
|---|---|
| 各包规模 | `find packages/*/src -name '*.py' \| wc -l` |
| 测试是否通过 | `uv run python -m pytest packages/<pkg> -q` |
| 依赖方向 | `grep -rn 'llm_gateway' packages/mesh/src packages/swarm/src` |
| 外部调用方 | `grep -rn 'aetherforge\|llm_gateway' bin/ projects/*/src` |
| BOS 暴露的能力 | 查 `projects/agora/etc/bos-services.yaml` 中 aetherforge 相关条目 |
| agora 依赖是否已打通 | `grep -n 'enabled' projects/agora/src/agora/auth/mcp_gateway.py` |

## 10. 待决事项

- [ ] 别名层最终归属:配置文件 vs 独立服务(当前倾向配置文件,随门面一起)
- [ ] `compute_mesh` 的成本核算是否上升为全局成本面(涉及与 cockpit 展示层的边界)
- [ ] swarm 首个场景确认(本文档建议多 worktree 协调,待确认)
