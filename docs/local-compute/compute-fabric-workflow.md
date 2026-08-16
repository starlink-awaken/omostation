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

### 阶段 2：任务分发前意图分诊与 VRAM 预算
- **操作指令**：
  ```bash
  # 分析提示词复杂度
  omlxc fabric triage "重构数据面调度器并证明死锁自由"
  # 输出: Tier: REASONING | Confidence: 85%

  # 预估 32k 上下文显存
  omlxc fabric vram coding 32768
  # 输出: KV Cache: 8,448.0 MB | Total Est. VRAM: 25,948.0 MB
  ```
- **调度准则**：
  - `FAST` ➔ 引导至 Mac mini 2B~4B 极速模型（100+ TPS）。
  - `REASONING` ➔ 锁定 MBP 27B~70B 深度思考模型。
  - 显存超限（超出节点安全水位 85%）➔ 提前拦截或分块执行，杜绝中途 OOM 崩溃。

### 阶段 3：基准跑分与性能漂移检测
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
| **CLI (人类交互)** | `omlxc fabric ...` / `make omlxc-fabric` | `omlxc fabric inspect` |
| **Cockpit (统一网关)** | `cockpit mesh ...` | `cockpit mesh fabric` |
| **BOS URI (总线)** | `bos://compute/aetherforge/fabric` | `resolve_bos_uri("bos://compute/aetherforge/fabric")` |
| **Agora MCP (Agent)** | MCP Tools | `fabric_inspect()`, `fabric_vram_budget(...)` |
| **OpenAI 兼容接口** | `http://127.0.0.1:9290/v1` | `POST /v1/chat/completions` |
