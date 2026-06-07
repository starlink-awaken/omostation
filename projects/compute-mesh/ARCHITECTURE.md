# compute-mesh — eCOS 算力网格

> 算力发现 · 资源聚合 · 成本核算 · 动态调度 · Worker 管理
> L1-L2 基础设施，独立于 kairon 引擎平面

## 架构 (6 层)

```
┌─────────────────────────────────────────────────────────┐
│  0: API 层 (MCP/HTTP/CLI/BOS)                          │
│  对外暴露: generate/chat/workers/list/status            │
├─────────────────────────────────────────────────────────┤
│  1: Provider 层 (来自 llm-gateway-kernel)               │
│  Ollama · OpenAI · Anthropic · Gemini · DeepSeek · HITL│
├─────────────────────────────────────────────────────────┤
│  2: 拓扑发现层 (新建)                                    │
│  mDNS 扫描 · SSH 探针 · 静态配置 · 网络分区             │
├─────────────────────────────────────────────────────────┤
│  3: 算力资源池 (新建)                                    │
│  成本核算 · 健康监控 · 负载追踪 · 配额管理              │
├─────────────────────────────────────────────────────────┤
│  4: 动态调度层 (扩展)                                    │
│  策略路由(cost/capability/load) · 请求排队 · 熔断       │
├─────────────────────────────────────────────────────────┤
│  5: Worker 层 (新建)                                     │
│  注册 · 心跳 · 通信总线 · 任务分发 · 结果聚合          │
└─────────────────────────────────────────────────────────┘
                         ↕
              eCOS L0 (M1 compute_engine)
```

## 与 llm-gateway-kernel 的关系

| 组件 | 当前在 llm-gateway-kernel | compute-mesh 中 |
|:----|:--------------------------|:----------------|
| Provider 抽象 | ✅ `llm_gateway/providers/` | ✅ **已复制** (Layer 1) |
| MCP Server | ✅ `llm_gateway/mcp_server.py` | ✅ **已复制** (Layer 0) |
| ModelRegistry | ✅ `llm_gateway/registry.py` | ✅ **已复制** |
| ModelScheduler | ✅ `llm_gateway/scheduler.py` | ✅ **已复制** (扩展为 Layer 4) |
| SSOT 加载 | ✅ `llm_gateway/ssot_loader.py` | ✅ **已复制** |
| 成本缓存 (quota_rates) | ❌ 无 | 🆕 **Layer 3 集成** |
| 拓扑发现 | ❌ 无 | 🆕 **Layer 2 新建** |
| Worker 管理 | ❌ 无 | 🆕 **Layer 5 新建** |
| engine_core (80 文件) | ⚠️ 存在但零使用 | ❌ **不迁移** |

## L0 集成

```yaml
# M1 compute_engine → 静态拓扑配置
# 运行时状态 → compute-mesh 动态维护
ENG-OLLAMA-LOCAL:
  engine_type: local_daemon
  base_url: "http://localhost:11434/v1"
  network_zone: "local"         # ← 新增字段

ENG-CC-SWITCH:
  engine_type: cloud_api
  protocols: [openai, anthropic, deepseek]
  network_zone: "cloud"
```

## CLI

```bash
compute-mesh list                    # 列出所有算力节点
compute-mesh status                  # 各节点健康+负载
compute-mesh generate "你好"          # 默认调度生成
compute-mesh topology scan           # 网络嗅探发现新节点
compute-mesh worker list             # Worker 列表
compute-mesh cost                    # 成本报告
```

## MCP Tools

| 工具 | 说明 |
|:----|------|
| `mesh_generate` | 智能路由 LLM 请求 |
| `mesh_list_nodes` | 列出所有算力节点 |
| `mesh_worker_register` | Worker 注册 |
| `mesh_worker_dispatch` | 任务分发 |
| `mesh_cost_report` | 成本报告 |

## 源文件结构

```
src/compute_mesh/
├── __init__.py
├── api/              Layer 0: CLI + MCP + HTTP
├── provider/         Layer 1: LLM Provider (来自 llm_gateway/)
├── topology/         Layer 2: 拓扑发现 (新建)
├── pool/             Layer 3: 资源池 (新建)
├── scheduler/        Layer 4: 调度 (扩展自 llm_gateway)
└── worker/           Layer 5: Worker 管理 (新建)
```
