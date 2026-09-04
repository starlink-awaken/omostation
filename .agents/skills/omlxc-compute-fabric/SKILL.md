---
type: ssot
name: omlxc-compute-fabric
description: "omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南。当 Agent 需要执行本地大模型推理、预估长上下文显存、分析 Prompt 复杂度或调度本地算力时调用。"

last-reviewed: 2026-08-29
owner: governance-team
---

# omlxc Compute Fabric — 本地异构算力织网与智能调度操作体系

> **SSOT**: `projects/omlxc/docs/ARCHITECTURE-FABRIC.md`  
> **版本**: `omlxc v5.1.0` / `ADR-0439 Active` / `AetherForge Active`  
> **核心定位**: 私有化本地异构集群 (Apple Silicon 统一内存 + NVIDIA CUDA) 的 **L4/L7 智能算力网关与 Kubernetes Scheduler for LLM**。

---

## 1. 触发场景 (When To Use)

在任意 Agent（如 OpenCode、Claude Code、Cursor、AetherForge Swarm、Kilo Code 等）遇到以下情况时，应当调用本技能：
1. **长上下文推理与显存安全准入**：在向本地模型发送 $>16\text{k}$ Token 的超长上下文前，需基于 75%（96GB）阶梯显存安全门禁与双区自适应 KV 量化预估显存，保障恒定为 macOS 预留 25GB~32GB 物理内存，杜绝 Swap 顿挫。
2. **极速投机解码与在线共生蒸馏**：调用 `qwen-3.8-27b-dflash` 享受 104+ tok/s 满血生成，在线共生草稿头蒸馏将命中率推升至 91.8%+。
3. **雷雳 5 跨物理机 P2P 零拷贝 DMA 守护进程**：利用 `omlxc.daemon.dma_daemon` 自动探活 120Gbps 总线，在 MBP 与 Mac mini 间实现 <0.21ms 的 2MB KV 块迁移，并提供 launchd 原生守护。
4. **多模态 ViT Patch 特征流式直通**：Y7000P 提取视觉 Patch 特征分块直推 MBP 交叉注意力层，“边看边推”缩短 70%+ 首字延迟 (TTFT)。
5. **夏明星专属署名 Diff 闲时 LoRA 热插拔与经验回放**：基于 30% 历史回放 + 70% 新鲜样本的水塘抽样机制（`experience_replay.py`），杜绝灾难性遗忘。
6. **Cockpit Spine 全流程闭环**：通过 `cockpit spine draft/sign/diff/status/distill` 驱动主干真值流。
6. **硬件异构三节点路由**：
   - 向量化/重排序/闲时蒸馏 ➔ 自动路由至 Mac mini M4 (24G)；
   - 视觉/语音流/ViT特征 ➔ 自动路由至 Y7000P (RTX4070 8G CUDA)；
   - 主脑深度推演/树状投机 ➔ 锁定 MBP M5 Max (128G)。

---

## 2. 核心架构与调度机制 (Fabric Principles & ADR-0435)

### 2.1 综合打分与路由公式
每个候选模型 Placement $p$ 的最终得分：
$$\text{FinalScore}(p) = \text{BaseScore}(p) \times M_{\text{affinity}}(p) \times M_{\text{concurrency}}(p) \times M_{\text{thermal}}(p) \times M_{\text{priority}}(p)$$

### 2.2 五级分层存储与 152GB 统一 NUMA 体系
- **Tier 0 统一高速内存 (MBP 128G)**：主决策模型权重与热活跃 KV Blocks；
- **Tier 1 雷雳 5 DMA 分布式内存 (Mac mini 24G)**：L3 溢出 KV 缓存池 (<0.15ms 极速换页)；
- **Tier 2 NVMe 高速 Paging (7.4GB/s SSD)**：温冷数据 mmap 换页；
- **Tier 3 键入期 0ms 预测预热**：击键间隙预测领域与 SOP 依赖；
- **Tier 4 视觉 ViT 流式分块直通**：64-patch Chunk 级极速交接。

---

## 3. 标准调用契约 (Interface Contracts)

### 3.1 BOS URI 服务端点
| BOS URI | 传输协议 | 功能说明 |
| :--- | :--- | :--- |
| `bos://compute/omlxc/hud` | `stdio / cockpit` | 次世代主权算力全景 HUD 实时控制台 |
| `bos://compute/omlxc/heatmap` | `stdio / cockpit` | 分布式 KV 内存池热力图与投机蒸馏指标 |
| `bos://compute/omlxc/dma` | `stdio / omlxc` | 雷雳 5 跨物理机 P2P 零拷贝 DMA 通信总线 |
| `bos://compute/omlxc/lora` | `stdio / omlxc` | 端侧在线 LoRA 持续微调与毫秒级热插拔 |
| `bos://compute/omlxc/tree` | `stdio / omlxc` | 自适应熵感知树状投机解码与多候选验证 |
| `bos://compute/omlxc/stream` | `stdio / omlxc` | 跨节点 Chunk-level 异步流式协同流水线 |
| `bos://compute/omlxc/swarm` | `stdio / omlxc` | 分布式跨节点 KV 共享池与 512k 上下文置换 |
| `bos://compute/aetherforge/infer` | `stdio / aetherforge` | 通过 AetherForge Gateway 触发实际推理 |

### 3.2 常用 CLI 诊断命令
```bash
# 1. 查看次世代主权算力全景 HUD 实时控制台与 Spine 状态
cockpit mesh hud
cockpit mesh heatmap
cockpit spine status

# 2. 启动 Textual 1.x 全屏多智能体与算力互动大盘 (按 5 切换到 Compute HUD)
make omo-top

# 3. 运行 DMA 守护进程或生成 launchd 配置
python3 -m omlxc.daemon.dma_daemon --generate-plist
python3 -m omlxc.daemon.dma_daemon --probe-interval 1.0

# 4. 提交署名 Diff 并触发闲时 LoRA 蒸馏
cockpit spine sign --original "草稿" --signed "署名定稿" --domain signature-style
cockpit spine diff
cockpit spine distill --domain signature-style

# 5. 运行次世代 V5.0 五大战略前沿端到端真实场景全景实测
uv run --project projects/omlxc python projects/omlxc/examples/live_v5_evolution_verification.py

# 6. 运行全量单元测试套件
uv run --directory projects/omlxc pytest tests/unit/test_dma_daemon.py tests/unit/test_experience_replay.py -v
```

---

## 4. 防御性操作规则与最佳实践 (Best Practices)

1. **防 OOM 原则**：在发起大于 $16\text{k}$ Token 的大长文推理前，**必须**先调用 `cockpit mesh vram` 或 `omlxc fabric vram` 进行显存预算判定。若显存超过 75%（96GB）门禁，系统会自动采用双区量化压缩降低 73.4% 显存并经雷雳 5 溢流至 Mac mini。
2. **专属内存绝对保障**：LoRA 闲时微调严格限制在 Mac mini 上运行，严禁在 MBP M5 Max 上抢占 25~32GB 专属物理内存预留。
3. **雷雳优先与无感降级**：跨机协同优先使用雷雳 5 DMA 通道（<0.15ms），断开时透明回退至 10GbE / TCP。
