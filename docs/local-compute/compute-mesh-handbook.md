---
status: active
lifecycle: production
owner: compute-fabric-team
last-reviewed: 2026-09-19
type: ssot
---

# 🧠 OMOStation 算力中枢对外接入与使用指引手册 (Compute Mesh Handbook)

> **核心定位**：OMOStation 三节点私有化异构算力集群（L4 物理织网 `omlxc` + L7 智能网关 `aetherforge`）的统一对外使用规范。  
> **面向对象**：系统所有 AI Agent（OpenCode、Claude Code、Cursor、Cockpit Spine、Kairon 等）及外部第三方应用。

---

## 1. 集群全景与三节点拓扑 (Topology & Nodes)

集群由三台物理机通过 Tailscale 零配置主权虚拟专用网互联，形成兼具高吞吐统一内存与高并发 CUDA 的异构算力池：

| 节点标识 | 硬件规格 | 角色与专长 | 核心承载引擎 | 访问端点 |
| :--- | :--- | :--- | :--- | :--- |
| **`mbp-m5-max-128g`** | Apple M5 Max · 128G 统一内存 | 主力推理、大参数模型、高并发流水线 | oMLX App (port 8000) / omlxcd (UDS) / LM Studio | `127.0.0.1` / UDS Socket |
| **`macmini-m4pro-24g`** | Apple M4 Pro · 24G 统一内存 | 轻量并行、极速思维链推理 (50+ tok/s)、向量检索 | Ollama (port 11434) / LM Studio | `100.99.210.78` |
| **`y7000p-rtx4070-8g`** | Intel i7 · RTX 4070 8G CUDA | 专业视觉提取、文档 OCR、轻量小模型推理 | LM Studio (port 1234) / Ollama | `100.64.43.36` |

> [!NOTE]
> 本机控制面通过轻量 Unix Domain Socket 监听于 `~/.config/omlxc/omlxcd.sock`，所有进程内或本机 Agent 优先使用 UDS 获得近乎零传输开销的超低延迟。

---

## 2. 统一意图与模型别名映射 (Aliases & Intent Matrix)

Agent 在发起推理请求时，**严禁硬编码特定节点的物理模型文件名**，统一使用抽象别名（Alias）或功能意图（Role）。AetherForge 网关将自动解析当前集群节点的负载、温控与就绪状态执行智能调度：

| 业务意图 (Intent) | 推荐别名 (Alias) | 后端模型实现 | 物理落点 | 典型性能与特征 |
| :--- | :--- | :--- | :--- | :--- |
| **代码生成与补全** | `coding-next` / `coding` | Qwen3-Coder-30B-A3B / Devstral-24B | MBP M5 Max (MLX) | 满血代码能力，常驻内存秒级冷启动 |
| **极速思考/推理** | `fast-think` / `fast-oss` | OpenAI GPT-OSS-20B (MXFP4) | Mac mini (Ollama) | 50.48 tok/s 极速生成，原生内生思维链 |
| **深度逻辑与规划** | `reasoning` / `deep-reason` | GLM-4.7-Flash / Qwen3.6-35B | MBP (MLX / LM Studio) | 超长思维链，适合复杂架构审计与规划 |
| **图文多模态理解** | `vision` / `vision-lite` | Qwen3-VL-8B / Qwen3-VL-4B | MBP (MLX) / LM Studio | 支持高分辨率多图上下文理解 |
| **文档与表格 OCR** | `ocr` | GLM-OCR (CUDA) | Y7000P (RTX 4070) | 专门针对中文印刷体与复杂文档表格解析 |
| **语义检索向量化** | `embedding` / `embed-bge` | Qwen3-Embedding-8B / BGE-M3 | MBP / Mac mini | 1024 维多语言高精度语义向量表示 |

---

## 3. 四大标准接入方式 (Access Interfaces)

### 3.1 途径一：Python SDK 调用（工作区 Agent 首选推荐）

工作区内部的 Python 模块与 Agent 统一通过 `llm_gateway` 模块发起调用，自带透明重试、熔断与流式思考解耦：

```python
import asyncio
from llm_gateway import ModelGateway, LLMRequest

async def main():
    gateway = ModelGateway.from_config()
    
    # 1. 简单阻塞式调用（支持别名）
    response = await gateway.acomplete(
        LLMRequest(
            model="coding-next",
            messages=[{"role": "user", "content": "写一个 Python 二分查找函数"}],
            temperature=0.2,
            max_tokens=512,
        )
    )
    print("生成结果：", response.content)
    
    # 2. 极速思维链流式调用（自动分离思考过程）
    async for chunk in gateway.astream(
        LLMRequest(
            model="fast-think",
            messages=[{"role": "user", "content": "证明根号2是无理数"}],
            max_tokens=1024,
        )
    ):
        if chunk.reasoning_content:
            print(f"[思考中]: {chunk.reasoning_content}", end="", flush=True)
        if chunk.content:
            print(chunk.content, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 3.2 途径二：BOS 服务总线协议（SOA 架构规范）

OMOStation 体系内服务通过标准 BOS URI 进行能力发现与 RPC 路由：

- **主权推理入口**：`bos://compute/aetherforge/infer`
- **集群状态脉搏**：`bos://compute/omlxc/hud`
- **向量检索嵌入**：`bos://compute/omlxc/embed`

**调用规范示例**：
```bash
# 通过 cockpit / agent-broker 触发
cockpit service call bos://compute/aetherforge/infer \
  --json '{"model": "coding-next", "messages": [{"role": "user", "content": "hello"}]}'
```

---

### 3.3 途径三：OpenAI 兼容 REST / SSE 接口（外部 Agent 与 IDE 插件）

对于 Cursor、Claude Code、Aider、Continue、LibreChat 等标准外部客户端，算力中枢提供 100% 兼容 OpenAI 协议的 HTTP/SSE 端口：

#### 网关全局端口（推荐，带智能调度与故障转移）：
- **Base URL**：`http://127.0.0.1:4000/v1`
- **API Key**：`sk-omostation-local`（任意占位符即可）

```bash
# 测试流式对话
curl -N http://127.0.0.1:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "fast-think",
    "messages": [{"role": "user", "content": "请分析快速排序的时间复杂度"}],
    "stream": true
  }'
```

#### 本地零延迟 UDS Socket 端口（原生脚本直连）：
```bash
curl -s --unix-socket ~/.config/omlxc/omlxcd.sock \
  http://localhost/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "coding-next", "messages": [{"role": "user", "content": "hi"}]}'
```

---

### 3.4 途径四：集群脉搏探针与 CLI 工具

运维与自检使用标准探针脚本，实时观测三节点延迟、TTFT 与就绪态：

```bash
# 默认文本汇总报告
python projects/omlxc/scripts/compute-mesh-pulse.py

# 结构化 JSON 格式输出 (供 Agent/CI 机器解析)
python projects/omlxc/scripts/compute-mesh-pulse.py --json

# 综合端到端推理抽检
python projects/omlxc/scripts/compute-mesh-pulse.py --test-infer
```

---

## 4. 思维链分离与流式处理规范 (Reasoning Best Practices)

对于支持深度思考的模型（如 `fast-think` / `reasoning`）：
1. **协议层分离**：AetherForge 网关自动通过 `StreamReasoningFilter` 解析出 `<think>` 标签和 `reasoning_content` 字段；
2. **Agent 渲染准则**：
   - 当 `chunk.reasoning_content` 非空时，作为“思考中”灰色折叠或单行滚动展示；
   - 当收到最终 `chunk.content` 时，正常渲染为最终 Markdown 内容；
   - 严禁将未闭合的思考标签作为乱码倾泻到用户交互界面。

---

## 5. 弹性容灾与自愈纪律 (Resilience & Self-Healing)

1. **零崩溃保证**：`omlxc` 守护进程内置自适应超时机制，即使远端从节点（Mac mini 或 Y7000P）关机或休眠，本机探活亦被限制在 15s 以内，绝不会拖垮或阻塞本机守护进程启动。
2. **级联降级策略**：
   - 当首选的本地 MLX 后端忙时，AetherForge 自动将请求无缝降级转发至同一局域网下的 LM Studio 或 Mac mini Ollama；
   - 降级过程对上层调用方完全透明，仅在响应头注入 `X-OMO-Route-Placement` 记录。
3. **显存安全保护（75% 水位线）**：
   - 发起超长上下文推理前，必须遵循 75% 显存保护红线（MBP 保证常驻至少 25GB macOS 系统内存），严防高负载引发系统 Swap 顿挫。
