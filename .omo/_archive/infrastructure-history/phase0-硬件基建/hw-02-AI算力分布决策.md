# 02 — AI 算力分布决策

> 核心问题：各设备的本地推理能力如何分配？
> 更新日期：2026-05-20

---

## 一、问题背景

之前方案将 Ollama 全部放在 Mac mini M4 (24GB) 上，由 MBP 远程调用。但经过深入分析，**24GB 内存对于本地推理是一个明显瓶颈**，需要重新分配。

## 二、各设备推理能力评估

### Mac mini M4 — 24GB

| 模型规模 | 能否运行 | 可用内存余量 | 结论 |
|---------|---------|------------|------|
| 7B (Q4, ~5GB) | ✅ 流畅 | ~17GB | ✅ 日常可用 |
| 14B (Q4, ~9GB) | ✅ 流畅 | ~13GB | ✅ 日常可用 |
| 32B (Q4, ~20GB) | ⚠️ 勉强 | ~2GB | ❌ 系统会卡，不建议 |
| 72B (Q4, ~42GB) | ❌ 无法加载 | — | ❌ 不可能 |
| bge-m3 嵌入 (~2GB) | ✅ 流畅 | ~20GB | ✅ 完美 |

**结论：Mac mini 适合跑 7B-14B 模型 + 嵌入模型，不适合运行 32B 及以上。**

### MBP M5 Max — 128GB

| 模型规模 | 能否运行 | 可用内存余量 | 结论 |
|---------|---------|------------|------|
| 7B (Q4, ~5GB) | ✅ 轻松 | ~120GB | ✅ |
| 14B (Q4, ~9GB) | ✅ 轻松 | ~116GB | ✅ |
| 32B (Q4, ~20GB) | ✅ 轻松 | ~105GB | ✅ |
| 72B (Q4, ~42GB) | ✅ 轻松 | ~80GB | ✅ |
| 多个模型并行 | ✅ 轻松 | — | ✅ 可同时跑 2-3 个大模型 |

**结论：MBP M5 Max 是真正的本地算力主力。128GB 统一内存可轻松运行 72B 模型。**

### Y7000P — 48GB (Windows)

| 模型规模 | 能否运行 | 可用内存 | 结论 |
|---------|---------|---------|------|
| 理论上 32B Q4 (~20GB) | ⚠️ 可以但麻烦 | ~25GB | ❌ 不推荐 |
| 实际运行 | — | — | ❌ 无 Ollama 原生支持，WSL2 性能损失 |

**结论：Y7000P 不适合做推理服务器。Windows + WSL2 的额外开销 + 打游戏时会关 Docker，不稳定。**

## 三、2026年5月最新本地模型推荐

> 以下模型基于 2026年5月 搜索确认，均为 Ollama 可直接拉取的最新版本

### Mac mini M4 (24GB) — 轻型推理

24GB 内存现在可以跑比想象中更强的模型，关键是选对架构。

| 推荐模型 | 架构 | 量化 | 实际占用 | 推荐理由 |
|---------|------|------|---------|---------|
| **🥇 Qwen3.6-35B-A3B** ⭐ | MoE (35B总/3B激活) | Q4_K_M | **~21GB** | **首选！** MoE 架构每token只激活3B参数，35B的知识量却只占21GB内存。推理速度快，Mac mini M4实测可跑。最新版，agentic coding能力大幅提升 |
| **🥈 Qwen3.5-27B** | Dense (27B) | Q4_K_M | **~18GB** | 纯稠密模型，27B全量参数。比 MoE 稳定，Ollama 官方版兼容最好。24GB内存剩余6GB给系统，完全够用 |
| Qwen3.6-27B | Dense (27B) | Q4_K_M | ~18GB | Qwen3.6 的稠密版，性能更强，Ollama 官方支持 |

```bash
# Mac mini 上拉取（选一个即可）
ollama pull qwen3.6:35b-a3b       # MoE 首选，21GB
# 或
ollama pull qwen3.5:27b            # 稠密备选，18GB
```

### MBP M5 Max (128GB) — 重型推理

128GB 统一内存可以跑当前最强开源模型。

| 推荐模型 | 架构 | 推荐量化 | 实际占用 | 推荐理由 |
|---------|------|---------|---------|---------|
| **🥇 Qwen3-Coder-Next** ⭐ | MoE (80B总/3B激活) | Q4_K_XL | **~38GB** | **代码之王！** 80B总参、3B激活，Q4量化约38GB，在128GB上绰绰有余。是目前最强的本地代码模型，远超之前的 DeepSeek-Coder-V2 |
| **🥈 Qwen3.6-35B-A3B** | MoE (35B总/3B激活) | Q8_0 | **~37GB** | 用更高精度跑同一个模型，质量更优 |
| DeepSeek-Coder-V2 (16B) | Dense (16B) | Q4_K_M | ~11GB | 轻量备选，做快速代码补全 |

```bash
# MBP 上拉取
ollama pull qwen3-coder-next          # 80B MoE 代码模型，~38GB
ollama pull qwen3.6:35b-a3b           # 通用推理
```

### 嵌入模型 (RAG)

| 推荐模型 | 占用 | 推荐理由 |
|---------|------|---------|
| **bge-m3** | ~2.2GB | 多语言嵌入标杆，支持100+语言，KOS 语义搜索已在用，不换 |
| nomic-embed-text-v2 | ~1.5GB | 轻量备选 |

```bash
ollama pull bge-m3
```

## 四、最终分配方案

### 双层推理架构（2026年5月更新）

```
                      Mac mini 24GB                       MBP M5 Max 128GB
  ┌─────────────────────────────────────┐    ┌───────────────────────────────┐
  │                                     │    │                               │
  │  Qwen3.6-35B-A3B  (MoE · ~21GB)    │    │  Qwen3-Coder-Next (MoE·38GB) │
  │  └─ 通用推理+代码补全               │    │  └─ 最强本地代码推理          │
  │                                     │    │                               │
  │  bge-m3  (~2GB)                     │    │  Qwen3.6-35B-A3B (Q8·37GB)   │
  │  └─ 嵌入式 + RAG                    │    │  └─ 高精度通用推理            │
  │                                     │    │                               │
  │  剩余 ~1GB → 系统+Docker            │    │  剩余 ~50GB → 系统+开发环境   │
  └─────────────────────────────────────┘    └───────────────────────────────┘
          ↑ 远程调用（Tailscale） ↑                    ↑ 本地直接调用
          └──────────────────────┴────────────────────┘
                              MBP Hermes / IDE
```

**关键洞察：Mac mini 24GB 不再只能跑7B小模型。** Qwen3.6-35B-A3B 的 MoE 架构让它用21GB就达到了35B模型的知识量，推理速度却和7B模型差不多（因为每token只激活3B参数）。

### 具体分工

| 场景 | 首选模型 | 在哪跑 | 备用方案 |
|------|---------|--------|---------|
| IDE 代码补全（在线） | DeepSeek V4 Flash (云端) | New API → 代理 | GLM-4.7 Fallback |
| IDE 代码补全（离线） | Qwen3.6-35B-A3B | **Mac mini** | Qwen3-Coder-Next (MBP) |
| 复杂架构/推理（在线） | DeepSeek V4 Pro / GLM (云端) | New API → 代理 | LLM Fallback |
| **深度离线推理** | Qwen3-Coder-Next (80B MoE) | **MBP M5 Max** | Qwen3.6-35B-A3B (MBP) |
| 代码嵌入 / RAG | bge-m3 | **Mac mini** | nomic-embed-text-v2 |
| 出差/通勤 | Qwen3.6-35B-A3B | **MBP + 三星 SSD** | 存固态上，插上用 |

### 环境变量配置

```bash
# MBP 默认（在家）
export OLLAMA_HOST_MM=http://100.x.x.1:11434   # Mac mini → Qwen3.6-35B-A3B
export OLLAMA_HOST_LOCAL=http://127.0.0.1:11434 # MBP → Qwen3-Coder-Next
export ONE_API=http://100.x.x.1:3000/v1         # 云端 API 网关

# 出差时（三星 SSD）
# export OLLAMA_MODELS=/Volumes/DevDrive/Ollama-Models/
# export OLLAMA_HOST=127.0.0.1:11434
```

## 五、模型存储位置

| 模型 | 大小 | 位置 | 用途 |
|------|------|------|------|
| Qwen3.6-35B-A3B (Q4) | ~21GB | Mac mini `/Volumes/Model` | 24h 通用推理+代码 |
| bge-m3 | ~2GB | Mac mini `/Volumes/Model` | RAG语义搜索 |
| Qwen3-Coder-Next (Q4) | ~38GB | MBP 内置 SSD | 本地最强代码推理 |
| Qwen3.6-35B-A3B (Q8) | ~37GB | MBP 内置 SSD 或三星 SSD | 高精度推理（出差） |

## 六、变更说明

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 原方案 | Mac mini 承担全部7B-14B轻型推理 |
| **v2** | **2026-05-20** | **Qwen3.6-35B-A3B MoE 模型让 Mac mini 24GB 也能跑35B级别推理。MBP 跑 Qwen3-Coder-Next 80B 做深度代码推理。** |
