---
name: omlxc-compute-fabric
description: "omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南。当 Agent 需要执行本地大模型推理、预估长上下文显存、分析 Prompt 复杂度或调度本地算力时调用。"

last-reviewed: 2026-08-29---

# omlxc Compute Fabric — 本地异构算力织网与智能调度操作体系

> **SSOT**: `projects/omlxc/docs/ARCHITECTURE-FABRIC.md`  
> **版本**: `omlxc v3.6.0` / `ADR-0433 Active` / `AetherForge Active`  
> **核心定位**: 私有化本地异构集群 (Apple Silicon 统一内存 + NVIDIA CUDA) 的 **L4/L7 智能算力网关与 Kubernetes Scheduler for LLM**。

---

## 1. 触发场景 (When To Use)

在任意 Agent（如 OpenCode、Claude Code、Cursor、AetherForge Swarm、Kilo Code 等）遇到以下情况时，应当调用本技能：
1. **长上下文推理与显存安全准入**：在向本地模型发送 $>16\text{k}$ Token 的超长上下文前，需基于 75%（96GB）阶梯显存安全门禁与双区自适应 KV 量化预估显存，保障恒定为 macOS 预留 25GB~32GB 物理内存，杜绝 Swap 顿挫。
2. **极速投机解码调用 (DFlash 2)**：调用 `qwen-3.8-27b-dflash` 享受 70+ tok/s 满血生成，并支持电池/温控自适应降级。
3. **多 Agent 共享会话分叉 (Radix + Paged KV)**：派生子代理任务时，基于 Paged KV 块内存与 Copy-on-Write (CoW) 零拷贝复用父级 KV Cache，前缀复用率达 92%+，TTFT 降至 10ms。
4. **提示词意图分诊 (Triage)**：在分发任务前，分析 Prompt 属于 `FAST` (2B~4B 秒回)、`STANDARD` (9B~14B 日常开发) 还是 `REASONING` (27B~70B 深度思考)。
5. **优先级服务质量 (QoS)**：夏明星 P0 即时交互享有零等待抢占通行权，后台批量索引（P2）高压自动避让。
6. **硬件异构三节点路由**：
   - 向量化/重排序 ➔ 自动路由至 Mac mini M4 (24G)；
   - 视觉/语音流 ➔ 自动路由至 Y7000P (RTX4070 8G CUDA)；
   - 主脑深度推演 ➔ 锁定 MBP M5 Max (128G)。

---

## 2. 核心架构与调度机制 (Fabric Principles & ADR-0433)

### 2.1 综合打分与路由公式
每个候选模型 Placement $p$ 的最终得分：
$$\text{FinalScore}(p) = \text{BaseScore}(p) \times M_{\text{affinity}}(p) \times M_{\text{concurrency}}(p) \times M_{\text{thermal}}(p) \times M_{\text{priority}}(p)$$

- **前缀与会话亲和 ($M_{\text{affinity}}$)**：相同 System/Tool 前缀或 Radix 树命中锁节点 ($1.35\times$)，TTFT 趋近 0ms。
- **在飞并发削峰 ($M_{\text{concurrency}}$)**：$1 / (1 + 0.5 \times N)$，达到硬顶并发限制时强制溢流至空闲节点。
- **温控与电源感知 ($M_{\text{thermal}}$)**：AC 插电模式开启满血 7 步 DFlash 投机；电池模式降为 4 步安全投机（功耗降 60%）；过热降权 $0.5\times \sim 0.1\times$。
- **优先级保障 ($M_{\text{priority}}$)**：P0 人机交互加分 ($1.25\times$) 并保障专属保留槽位。

### 2.2 三级分层缓存体系 (Hierarchical Cache Hierarchy)
- **L1 语义 / 完全命中**：0ms TTFT，0 算力开销；
- **L2 内存 Paged Radix 前缀**：10ms TTFT，复用绝大部分 KV 块；
- **L3 NVMe 持久化快照**：3ms 极速冷启动 mmap 加载；
- **冷 Prefill 兜底**：自动渐进式构建新缓存节点。

---

## 3. 标准调用契约 (Interface Contracts)

### 3.1 BOS URI 服务端点
| BOS URI | 传输协议 | 功能说明 |
| :--- | :--- | :--- |
| `bos://compute/aetherforge/fabric` | `stdio / omlxc` | 采集集群温控、模型架构、三级缓存与 Paged 显存状态 |
| `bos://compute/aetherforge/triage` | `stdio / omlxc` | 评估输入 Prompt 的意图复杂度分级 |
| `bos://compute/aetherforge/vram` | `stdio / omlxc` | 计算指定模型在指定 Token 长度下的 KV Cache 显存 |
| `bos://compute/aetherforge/warm` | `stdio / omlxc` | 预热常用 System Prompt 前缀以实现 0ms TTFT |
| `bos://compute/aetherforge/infer` | `stdio / aetherforge` | 通过 AetherForge Gateway (:9290) 触发实际推理 (支持 DFlash 2) |

### 3.2 常用 CLI 诊断命令
```bash
# 1. 运行次世代主权算力织网全景演练 (树状投机 + 流式流水线 + 分布式 KV 共享池)
uv run --project projects/omlxc python projects/omlxc/examples/live_nextgen_compute_engine_benchmark.py
cockpit mesh tree
cockpit mesh stream
cockpit mesh swarm

# 2. 运行集群全景基准演练 (DFlash 2 + 三节点路由)
uv run --project projects/omlxc python bin/demo/live_cluster_wide_benchmark.py
cockpit mesh cluster

# 3. 运行上下文与三级分层缓存全景基准演练 (Radix Tree + Paged KV)
uv run --project projects/omlxc python bin/demo/live_context_and_cache_benchmark.py
cockpit mesh cache

# 3. 检查节点温度、已注册模型架构与缓存统计
omlxc fabric inspect
omlxc fabric inspect --json

# 4. 预热系统公共前缀快照缓存 (0ms TTFT)
omlxc fabric warm
cockpit mesh warm --model coding

# 5. 实时意图复杂度分诊
omlxc fabric triage "Design a lock-free queue to prevent ABA problem"

# 6. 显存阶梯预算评估 (模型名 + Token数)
omlxc fabric vram coding 32768
omlxc fabric vram qwen3.8-27b-dflash 65536

# 7. 上下文滑动蒸馏与双区量化压缩模拟
omlxc fabric compact --model coding --tokens 32768 --available-mb 4096
```

---

## 4. 防御性操作规则与最佳实践 (Best Practices)

1. **防 OOM 原则**：在发起大于 $16\text{k}$ Token 的大长文推理前，**必须**先调用 `fabric_vram_budget` 或 `omlxc fabric vram` 进行显存预算判定。若显存超过 75%（96GB）门禁，系统会自动采用双区量化压缩（Head INT8 + Tail INT4 + 8 Attention Sinks）降低 73.4% 显存。
2. **防饿死原则**：批量跑分、文档嵌入等重型任务必须声明 `priority="p2_batch"`，避免阻塞人类开发者的即时代码补全。
3. **单向门禁原则**：不得绕过 AetherForge / omlxcd 直接通过原始端口调用底层 backend，所有调度必须经过统一数据面。
