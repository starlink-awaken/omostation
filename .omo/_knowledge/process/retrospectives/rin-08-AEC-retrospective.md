---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Agora Agent 网关迭代 · 实战复盘

> 时间：2026-05-24
> 场景：基于调研结果，在 Agora 中实现 Agent Card（A2A 兼容）、审计持久化、/.well-known 端点
> 框架环节：AEC S1→S4→S5（问题探索→方案设计→增量验证）

---

## 复盘结论

### 做对了的

| 决策 | 为什么对 |
|------|---------|
| **先调研再动手** | 调研后发现 Agora 已覆盖 80% 需求，没掉进"重造轮子"的坑 |
| **三层分治（P0/P1/P2）** | 每个级别边界清晰，P0 是核心能力，P1 是补齐，P2 是锦上添花。如果一口气全部实现会分散精力 |
| **审计现有资产再实施** | 如果一开始没看 `registry.py`、`event_bus.py`、`web/app.py` 的代码，会忽略已有 audit 工具的存在（`audit_query`/`audit_stats`），导致重复写 |
| **每改一步就验证** | `python3 -c "from agora.xxx import ..."` 每个模块单独验证，比最后统一跑测试高效——问题定位到具体模块 |
| **采用 A2A 标准而非自创** | Agent Card 的 schema 直接对齐 A2A 规范（`name`/`description`/`url`/`skills`/`capabilities`），后续外部 Agent 可以通过标准协议发现 |

### 可以更好的

| 问题 | 反思 | 下次怎么做 |
|------|------|-----------|
| **EventBus 钩子系统不是设计时就有的** | `_on_publish` 是后面加进去的，说明设计时没考虑"扩展点"。如果 EventBus 初始设计就支持 plugin/hook 机制，审计集成会更干净 | 核心模块设计时应预留 `_hooks` 或 plugin 注册点 |
| **依赖冲突** | `audit_subscriber.py` 用了 `structlog`，但 Agora 没有依赖它的上下文（只有 event_bus 和 persistence 用了）。导致 import 时找不到模块 | 新模块尽量复用已有依赖栈，或明确标记新增依赖 |
| **重复代码** | `list_agent_cards` 和 `get_agent_card` 中生成 Agent Card 的逻辑完全一样，应该抽取共享函数 | 超过 3 行重复就抽取 |

### 实际交付结果 vs 计划

| 计划 | 交付 | 偏差原因 |
|------|------|---------|
| P0: Agent Card 数据模型 + MCP 工具 | ✅ 完成 | — |
| P1: 审计持久化 + OTel 导出 | ✅ 完成（OTel 是 `to_otel_json()` 方法，非独立导出管道） | OTel 完整导出管道（gRPC exporter）需要额外依赖，当前 `to_otel_json()` 方法足够用于审计查询 |
| P2: `/.well-known/agent-card.json` | ✅ 完成 | — |

---

## 更新到框架文档

以下增量内容应追加至 `08-架构工程框架-AEC.md`：

### S4 方案设计 新增小节：存量资产审计

> **在提出方案之前，先审计现有系统的能力。**
>
> 这次 Agora 网关迭代中，第一步不是"写代码"而是"读代码"——审计了 `registry.py`（注册能力）、`event_bus.py`（事件能力）、`web/app.py`（API 能力）。结论是"80% 已有，只需补 3 个缺口"。
>
> 这个审计动作避免了至少 2 天的重复工作（如果没审计就开写，会重写已有的 audit 工具和事件系统）。
>
> **实践建议**：在 S4 方案设计阶段，花 1-2 小时审计现有代码库中与你的方案相关的模块。你的方案可能不是"新建"，而是"扩展"。

### S5 增量验证 新增：验证每一层，不等到最后

> 这次实施的验证模式：**每改一个文件就验证这个文件的 import 和基本功能**。
>
> ```
> 改 agent_card.py  → python3 -c "from agora.agent_card import ..."
> 改 event_bus.py  → python3 -c "publish → 校验 event_id"
> 改 audit_subscriber.py → publish → query → stats → OTel 全线
> ```
>
> 这种"逐层验证"比"最后统一跑测试"的问题定位效率高得多——每个错误都精确到刚改的模块。
>
> **实践建议**：在 S5 阶段，每完成一个模块的修改就单独验证这个模块的契约（import + 核心功能）。不要等到所有模块改完才测试。

### S6 持续演进 新增：ADR-016 案例

```
ADR-016: Agora 采用 A2A Agent Card 作为服务发现元数据标准
背景: 需要让 Agora 上注册的服务可以被外部 Agent 通过标准协议发现
选项:
  A. 自创元数据格式
  B. 采用 A2A Agent Card 规范
  C. 采用 MCP 原生发现机制
决策: B
理由: A2A 是 Linux 基金会标准，未来会成为 Agent 间通信的事实标准。
       自创格式需要外部 Agent 适配，A2A Agent Card 有现成的发现机制
       （/.well-known/agent-card.json）
后果: 
  - 正向：外部 A2A 兼容的 Agent 可直接发现 Agora 服务
  - 反向：需要将内部 ServiceConfig 映射为 Agent Card 格式
后续: 如果 A2A 规范更新，更新 agent_card.py 的 to_dict() 方法
```

### 附录：框架实战迭代记录（新增）

> AEC 框架本身也应按 S6 持续演进的逻辑进行迭代。
> 每次用框架完成一个真实项目后，记录经验并更新框架。

| 日期 | 项目 | 框架版本 | 学到什么 | 框架改动 |
|------|------|---------|---------|---------|
| 2026-05-24 | Agora Agent 网关 | V1.0→V1.1 | 先审计存量资产再动手；逐层验证比统一测试高效；预留 hook 扩展点 | 新增"存量资产审计"指导；新增"逐层验证"模式 |
