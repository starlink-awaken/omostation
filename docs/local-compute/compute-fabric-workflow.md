---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---
# 🛠️ omlxc Compute Fabric 运维与多 Agent 协作工作流 (Runbook & Workflow)

## 1. 概述与生命周期模型

本工作流定义了在 `omostation` 多智能体与异构硬件集群下，维护、扩展与调度本地算力织网的标准作业程序 (SOP)。

```
+------------------+      +--------------------+      +--------------------+
|  1. 节点接入与自检 | ---> | 2. 意图分诊与 VRAM 预估 | ---> |  3. 亲和调度与熔断自愈 |
+------------------+      +--------------------+      +--------------------+
         │                           │                          │
         ▼                           ▼                          ▼
  Tailscale + pmset            Fast Triage Gate          Two-Tier Cache + WFQ
  (温控/电池遥测上报)          (FAST / STD / REASON)     (Prefix-Hash / 优先级插队)
```

---

## 2. 标准作业流程 (Standard Operating Procedures)

### 阶段 1：集群节点状态与温控巡检
- **执行频率**：日常启动、高负载批处理前、机身发热降频时。
- **操作指令**：
  ```bash
  # 根工作区一键诊断
  make omlxc-fabric

  # 查看本地及远端节点温控与乘子
  omlxc fabric inspect
  ```
- **判定标准**：
  - `NOMINAL`：正常放行全部模型与并发。
  - `HEAVY`：笔记本节点（MBP）自动降权 $\times 0.5$，非交互任务自动溢流至 Mac mini。
  - `TRAPPING` / 电池 $<15\%$：硬惩罚 $\times 0.1$，禁止大模型重载推理。

### 阶段 2：系统公共前缀预热 (Prefix Cache Warming)
- **执行频率**：集群节点上线、新模型加载后、Agent 重启时。
- **操作指令**：
  ```bash
  # 预热核心治理规则与系统 Prompt (0ms TTFT)
  omlxc fabric warm --model coding
  cockpit mesh warm --model coding
  ```
- **判定标准**：`warmed_count >= 3`，预热命中率达到 100%，消除后续 Agent 交互的首字冷启动开销。

### 阶段 3：任务分发前意图分诊与 VRAM 预算自愈
- **操作指令**：
  ```bash
  # 分析提示词复杂度
  omlxc fabric triage "重构数据面调度器并证明死锁自由"
  # 输出: Tier: REASONING | Confidence: 85%

  # 预估 32k 上下文显存与压缩建议
  omlxc fabric vram coding 32768
  # 输出: KV Cache: 8,448.0 MB | Total Est. VRAM: 25,948.0 MB

  # 模拟滑动窗口上下文蒸馏与显存自愈
  omlxc fabric compact --model coding --tokens 32768 --available-mb 4096
  # 输出: Compaction Advised (35.0% 压缩率，裁剪 10,240 tokens)
  ```
- **调度准则**：
  - `FAST` ➔ 引导至 Mac mini 2B~4B 极速模型（100+ TPS）。
  - `REASONING` ➔ 锁定 MBP 27B~70B 深度思考模型。
  - **显存预警与自愈**：当显存超出安全水位（85%）时，返回 `compaction_advised=True` 及 `max_safe_tokens`。上层智能体自动执行上下文滑动蒸馏，保障长程会话永不中断。

### 阶段 4：基准跑分与性能漂移检测
- **执行频率**：模型权重更新后、macOS 系统升级后、闲时自动巡检。
- **操作指令**：
  ```bash
  # 运行全量模型基准跑分
  omlxc benchmark run coding
  omlxc benchmark report
  ```
- **判定标准**：若 TPS 下降超过 25%，`PerformanceDriftDetector` 输出漂移预警并触发排查。

---

## 3. 多端调用入口速查 (Access Points)

| 场景 | 调用方式 | 示例 |
| :--- | :--- | :--- |
| **CLI (人类交互)** | `omlxc fabric ...` / `make omlxc-fabric` | `omlxc fabric inspect`, `omlxc fabric warm`, `omlxc fabric compact` |
| **Cockpit (统一网关)** | `cockpit mesh ...` | `cockpit mesh fabric`, `cockpit mesh warm` |
| **BOS URI (总线)** | `bos://compute/aetherforge/*` | `bos://compute/aetherforge/warm`, `bos://capability/swarm/run` |
| **Agora MCP (Agent)** | MCP Tools | `fabric_inspect()`, `fabric_warm_prefixes()`, `fabric_vram_budget(...)` |
| **AetherForge MCP (Swarm)** | FastMCP Tools | `forge_fabric_inspect()`, `forge_fabric_warm()`, `forge_fabric_vram()`, `forge_fabric_compact()`, `forge_swarm_run()` |
| **OpenAI 兼容接口** | `http://127.0.0.1:9290/v1` | `POST /v1/chat/completions` |
| **Cockpit Web REST** | `http://127.0.0.1:8080/api/governance/compute/*` | `GET /api/governance/compute/fabric`, `POST /fabric/compact` |
| **Cockpit UI (前端)** | `http://localhost:5173/#/compute` | 算力织网、前缀预热、显存估算与上下文蒸馏模拟大盘 |

