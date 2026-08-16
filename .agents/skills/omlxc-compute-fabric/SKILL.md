---
name: omlxc-compute-fabric
description: "omlxc 异构算力织网、硬件温控、意图复杂度分诊、动态显存预算与优先级调度操作指南。当 Agent 需要执行本地大模型推理、预估长上下文显存、分析 Prompt 复杂度或调度本地算力时调用。"
---

# omlxc Compute Fabric — 本地异构算力织网与智能调度操作体系

> **SSOT**: `projects/omlxc/docs/ARCHITECTURE-FABRIC.md`  
> **版本**: `omlxc v3.4.0` / `AetherForge Active`  
> **核心定位**: 私有化本地异构集群 (Apple Silicon 统一内存 + NVIDIA CUDA) 的 **L4/L7 智能算力网关与 Kubernetes Scheduler for LLM**。

---

## 1. 触发场景 (When To Use)

在任意 Agent（如 OpenCode、Claude Code、Cursor、AetherForge Swarm、Kilo Code 等）遇到以下情况时，应当调用本技能：
1. **长上下文推理安全校验**：在向本地模型发送 $>16\text{k}$ Token 的超长上下文前，需预估动态 KV Cache 显存占用，防止 macOS 内存 Swap 卡顿或 Metal/CUDA OOM 崩溃。
2. **提示词意图分诊 (Triage)**：在分发任务前，分析 Prompt 属于 `FAST` (2B~4B 秒回)、`STANDARD` (9B~14B 日常开发) 还是 `REASONING` (27B~70B 深度思考)。
3. **优先级质量服务 (QoS)**：人类即时交互（P0）享有优先插队权，后台批量索引与跑分（P2）自动削峰降级。
4. **硬件温控与电量感知**：实时观察机身温度（Heavy/Trapping 状态自动溢流至已插电桌面端 Mac mini）。

---

## 2. 核心架构与调度公式 (Fabric Mathematical Principles)

每个候选模型 Placement $p$ 的最终得分：
$$\text{FinalScore}(p) = \text{BaseScore}(p) \times M_{\text{affinity}}(p) \times M_{\text{concurrency}}(p) \times M_{\text{thermal}}(p) \times M_{\text{priority}}(p)$$

- **会话与前缀亲和 ($M_{\text{affinity}}$)**：同一会话锁节点 ($1.35\times$)，相同 System/Tool 前缀锁节点 ($1.15\times$)，大幅提升 KV Cache 命中率并降低 TTFT。
- **在飞并发削峰 ($M_{\text{concurrency}}$)**：$1 / (1 + 0.5 \times N)$，达到硬顶并发限制时强制溢流至空闲节点。
- **温控与电源感知 ($M_{\text{thermal}}$)**：高热或低电量时施加 $0.5\times \sim 0.1\times$ 降权，保护电池与硬件寿命。
- **优先级保障 ($M_{\text{priority}}$)**：P0 人机交互加分 ($1.25\times$) 并保障专属保留槽位。

---

## 3. 标准调用契约 (Interface Contracts)

### 3.1 BOS URI 服务端点
| BOS URI | 传输协议 | 功能说明 |
| :--- | :--- | :--- |
| `bos://compute/aetherforge/fabric` | `stdio / omlxc` | 采集集群温控、模型架构、两级缓存等全网状态 |
| `bos://compute/aetherforge/triage` | `stdio / omlxc` | 评估输入 Prompt 的意图复杂度分级 |
| `bos://compute/aetherforge/vram` | `stdio / omlxc` | 计算指定模型在指定 Token 长度下的 KV Cache 显存 |
| `bos://compute/aetherforge/infer` | `stdio / aetherforge` | 通过 AetherForge Gateway (:9290) 触发实际推理 |

### 3.2 常用 CLI 诊断命令
```bash
# 1. 根工作区一键算力织网全景诊断
make omlxc-fabric

# 2. 检查节点温度、已注册模型架构与两级缓存统计
omlxc fabric inspect
omlxc fabric inspect --json

# 3. 实时意图复杂度分诊
omlxc fabric triage "Design a lock-free queue to prevent ABA problem"

# 4. 显存动态增长预算评估 (模型名 + Token数)
omlxc fabric vram coding 32768
omlxc fabric vram qwen-72b 65536

# 5. 通过 Cockpit 统一转发
cockpit mesh fabric
cockpit mesh triage "Fix typo in variable"
cockpit mesh vram coding 32768
```

### 3.3 Agora MCP 工具接口
智能体可通过 Agora MCP Server 调用以下标准工具：
- `fabric_inspect()` ➔ 获取当前集群物理状态 JSON。
- `fabric_triage(prompt)` ➔ 获取 `{"tier": "reasoning", "confidence": 0.85, ...}`。
- `fabric_vram_budget(model_id, context_tokens)` ➔ 获取 `{"kv_cache_mb": 8448.0, "total_estimated_vram_mb": 25948.0, ...}`。

---

## 4. 防御性操作规则与最佳实践 (Best Practices)

1. **防 OOM 原则**：在发起大于 $16\text{k}$ Token 的大长文推理前，**必须**先调用 `fabric_vram_budget` 或 `omlxc fabric vram` 进行显存预算判定。
2. **防饿死原则**：批量跑分、文档嵌入等重型任务必须声明 `priority="p2_batch"`，避免阻塞人类开发者的即时代码补全。
3. **单向门禁原则**：不得绕过 AetherForge / omlxcd 直接通过原始端口调用底层 backend，所有调度必须经过统一数据面。
