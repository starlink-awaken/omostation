# Agora — MCP Service Convergence Hub

## 简介

Agora 是 kairon 生态中的 **MCP 服务汇聚枢纽**。它将多个下游 MCP 服务（kairon 工作空间包、npm 全局工具、Docker 网关、Homebrew 工具等）聚合并对外暴露为统一的 FastMCP 端点。LLM 客户端（如 Claude Code）只需连接 Agora 一个端点，即可访问全部 19 个已知服务以及动态加载的第三方工具。

Agora 提供三种运行模式：stdio（MCP 默认协议）、HTTP（端口 7422）和 SSE（端口 7431）。启动时自动检测工作空间、生成代理配置，并通过 `ProxyManager` 管理下游服务的子进程生命周期。

## 快速开始

### 安装

```bash
cd packages/agora
uv sync
```

### 启动

```bash
# stdio 模式（MCP 默认）
agora-mcp

# HTTP 模式（端口 7422）
agora-web

# SSE 模式（端口 7431）
python -m agora.server.mcp sse
```

### CLI 命令概览

Agora 提供 37 个顶层 CLI 命令，按功能域分类：

**服务管理：**
- `agora register <name> --mcp <url>` — 注册新服务
- `agora list` — 列出所有已注册服务
- `agora health [--watch]` — 健康检查（支持持续监控）
- `agora info <name>` / `agora stats` — 服务详情与统计

**工具目录（repo 全家桶）：**
- `agora repo discover <query>` — 从 GitHub + Registry 搜索 MCP 工具
- `agora repo install <name>` — 安装发现的工具
- `agora repo load <name>` — 加载工具到代理
- `agora repo pipeline <query>` — 一键 discover→install→load

**路由：**
- `agora route <tool> <service>` — 添加工具→服务路由
- `agora routes` — 列出所有路由映射

**治理：**
- `agora key create <name> --scopes <scopes>` — 创建 API 密钥
- `agora audit --since <time>` — 查询审计日志
- `agora tenant add <name>` — 管理多租户
- `agora accounting top` — 成本排名与配额

**管道：**
- `agora pipeline <name> --goal <text>` — 运行命名管道
- `agora pipeline-define <json>` — 从 JSON 定义自定义管道

**A2A 异步任务：**
- `agora a2a send <service> --goal <text>` — 提交异步任务
- `agora a2a get <task-id>` — 获取任务状态与结果

## 架构

```
LLM Client (Claude Code / cursor / …)
        │
        ▼
  ┌──────────────────────────┐
  │   FastMCP Server         │  40 个原生 @mcp.tool + N 个动态代理工具
  │   (stdio / HTTP / SSE)   │  + AuthMiddleware (AGORA_API_KEY)
  └────────┬─────────────────┘
           │
           ├──→ ProxyManager ──→ StdioMCPClient ──→ 下游 MCP 服务（子进程）
           │       (dispatch / idle_timeout / 引用计数)
           │
           ├──→ Router / SmartRouter ──→ EmbeddingStore ──→ 语义路由
           │       (负载均衡 / 熔断器 / 审计 / 计费)
           │
           ├──→ ServiceRegistry ──→ SQLite + JSON 双写
           │       (健康检查 / 熔断器 / 状态追踪)
           │
           └──→ EventBus / Audit / KeyManager / TenantManager
                   (事件 / 审计 / 认证 / 多租户 / 配额)
```

层次结构：

| 层次 | 组件 | 职责 |
|------|------|------|
| **接入层** | FastMCP Server | 统一 MCP 协议入口，40 个原生 + N 个动态代理工具 |
| **路由层** | Router / SmartRouter | 工具→服务映射，负载均衡，自然语言语义路由 |
| **代理层** | ProxyManager / ProxyRegistry | 下游服务连接管理，ProxyForwardTool 注册，空闲超时 |
| **协议层** | StdioMCPClient / HttpMCPClient | JSON-RPC 2.0 协议实现 |
| **注册层** | ServiceRegistry | 服务元数据存储，健康检查，熔断器 |
| **治理层** | Audit / Auth / Tenancy / Quota | 审计日志，API 密钥，多租户，计费配额 |
| **管道层** | Pipeline / Orchestrator / Lifecycle | 数据处理管道，工具全生命周期管理 |

## 核心功能

### 1. 服务注册与管理

CLI 和 MCP 工具两种方式均可注册服务。注册时同时写入 ServiceRegistry（SQLite + JSON 双写）。支持 MCP、gRPC、REST 等多种协议。

```bash
agora register my-service --mcp http://localhost:9000/mcp
agora list
agora health --watch --interval 10
```

MCP 对等工具：`register_service`、`list_services`、`check_health`。

### 2. MCP 代理

`ProxyManager` 管理所有下游 MCP 服务的子进程：启动、健康探测、空闲超时断开与延迟重连。代理工具通过 `ProxyForwardTool` 动态注册到 FastMCP，对外表现为原生工具。

MCP 对等工具：`proxy_connect`、`proxy_call`、`proxy_add_service`、`proxy_remove_service`、`proxy_status`。

### 3. 智能路由（SmartRouter）

三种路由模式覆盖不同场景：

- **direct** — 从自然语言查询中解析工具名，直接调用已加载工具
- **recommend** — 语义搜索（EmbeddingStore）匹配相似工具，返回推荐列表
- **auto** — 级联策略：先尝试 direct，回退 recommend，最后自动 discover→install→load→call

通过 `agora_execute` 工具接入，是 LLM 不确定工具时的入口。

MCP 对等工具：`agora_execute`（1 个工具，3 种模式）、`route_call`（含负载均衡 + 熔断器 + 审计 + 计费）。

### 4. 工具目录（ToolCatalog）

MCP Registry 系统提供完整的工具生命周期管理：discover→install→load→call→unload。

- **发现**：联合搜索 GitHub + 中央 Registry，经 QualityScorer 评估（星数 / 新鲜度 / 版本）
- **安装**：git clone + pip/npm install，支持 BUILTIN_MARKET 中的 18 个预配置工具
- **加载**：注册到 ProxyManager，FastMCP 动态暴露 ProxyForwardTool
- **管道**：`repo pipeline` 一键完成全流程

CLI 命令：`agora repo discover/install/load/unload/pipeline/status`。

### 5. A2A 异步任务

支持异步任务提交，适用于长时间运行的工作流（如深度研究）。任务可查询状态、取消和列表过滤。

```bash
agora a2a send minerva.research_now --goal "量子计算"
agora a2a get <task-id>
```

MCP 对等工具：`a2a_send_task`、`a2a_get_task`、`a2a_cancel_task`、`a2a_list_tasks`。

### 6. 管道

Agora 内置 Eidos 管道引擎，支持知识提取、知识工程等结构化数据处理工作流。

```bash
agora pipeline knowledge-base --goal "分析量子计算论文" --stream
agora pallas pipeline --goal "分析量子计算论文"
```

支持流式输出（`--stream`）和并行执行（`--parallel`），可从 JSON 定义自定义管道（`pipeline-define`）。

### 7. 治理

Agora 内置完整的治理体系：

| 功能 | 组件 | 用途 |
|------|------|------|
| API 密钥 | KeyManager | 创建 / 列出 / 吊销 / 轮换 Bearer Token |
| 审计 | AuditLogger | 持久化审计日志，按 actor/resource/event_type 过滤，risk_level 分级 |
| 多租户 | TenantManager | 租户 CRUD，服务白名单，速率限制 |
| 配额 | AccountingManager | 每日预算配额，成本排名，按 caller 计费 |

AuthMiddleware（`AGORA_API_KEY`）提供 Bearer Token 认证，当前默认 permissive 模式，可在 FastMCP 初始化时激活。

### 8. 事件总线

轻量级事件系统支持跨服务事件发布与订阅。事件持久化到 SQLite，支持模式匹配订阅和按时间范围查询历史。

MCP 对等工具：`publish_event`、`subscribe_event`、`get_event_log`。

## 用户旅程

Agora 面向四类用户角色：

- **最终用户** — 通过 LLM 客户端（Claude Code 等）间接使用。核心路径：直接调用已知工具（ProxyForwardTool，最优性能），或通过 `agora_execute` 让系统语义路由。无需关心底层服务。
- **系统管理员** — 通过 CLI + MCP 治理工具管理全生命周期：启动初始化、服务注册、健康监控、审计合规、多租户配额。涉及从小到大的运维操作流程。
- **工具开发者** — 通过 `repo` 命令发布和安装 MCP 工具。完整流程：discover→install→load→pipeline，支持 QualityScorer 评估工具质量。
- **管道操作员** — 通过 pipeline 系统和 A2A 任务运行结构化数据处理工作流，涵盖知识提取、知识工程和异步任务提交。

## MCP 工具列表

Agora 提供 **41 个原生 `@mcp.tool()`** + N 个动态代理工具（取决于已加载的下游服务数量）。原生工具按功能域分布：

| 功能域 | 工具数 | 包括 |
|--------|--------|------|
| 代理管理 | 6 | `proxy_connect`、`proxy_call`、`proxy_status`、`proxy_add_service`、`proxy_remove_service`、`proxy_list_tools` |
| 服务注册与治理 | 4 | `register_service`、`list_services`、`check_health`、`register_push_notification` |
| 路由 | 3 | `add_route`、`list_routes`、`route_call` |
| 事件总线 | 3 | `publish_event`、`subscribe_event`、`get_event_log` |
| 审计 | 2 | `audit_query`、`audit_stats` |
| API 密钥 | 3 | `create_api_key`、`list_api_keys`、`revoke_api_key` |
| A2A 任务 | 4 | `a2a_send_task`、`a2a_get_task`、`a2a_cancel_task`、`a2a_list_tasks` |
| Agent Card | 2 | `list_agent_cards`、`get_agent_card` |
| 状态追踪 | 1 | `get_state_transitions` |
| MCP Registry | 8 | `repo_search`、`repo_discover`、`repo_status`、`repo_install`、`repo_load`、`repo_unload`、`repo_pipeline` |
| 生命周期 | 5 | `lifecycle_status`、`lifecycle_start_watch`、`lifecycle_stop_watch`、`lifecycle_load_all`、`lifecycle_unload_all` |
| 语义路由 | 1 | `agora_execute`（direct / recommend / auto） |

完整详情见 [docs/retrospective.md](docs/retrospective.md) 附录 B。

### 外部 Agent / LLM 接入

Agora 为外部 AI Agent 提供三种接入模式：

- **Manifest 获取**：`proxy_list_tools` 返回所有下游工具的完整清单（name、description、inputSchema），供外部 LLM 自主选择
- **直接调用**：`proxy_call(tool_name, arguments)` 可直接执行已注册的下游工具
- **语义路由**：`agora_execute(query, mode="auto")` 由系统自动匹配最佳工具

详见 `docs/external_access.md`。另附 `eval_agent.py` 评测脚本，可模拟外部 Agent 对 Agora 的全面接入。

## 配置

Agora 使用 `~/.agora/` 作为数据目录（可通过 `AGORA_DATA_DIR` 环境变量覆盖）：

```
~/.agora/
├── agora-proxy-services.json    # 代理配置（KNOWN_SERVICES 快照 + 用户自定义）
├── agora-services.json          # 服务注册表（ServiceRegistry JSON 后端）
├── agora.db                     # SQLite 双写数据库
├── agora-routes.json            # 工具→服务路由映射
├── service_cache.json           # 降级缓存（1h TTL）
├── market/                      # 市场工具安装目录
│   ├── published.json           # 本地发布的市场工具元数据
│   └── modelcontextprotocol__*/ # git clone 的第三方工具
└── tools.db                     # ToolCatalog（MCP Registry 目录）
```

首次启动时自动从旧路径（kairon 项目根目录）迁移数据，幂等处理。

## 开发

```bash
# 运行测试
uv run pytest

# 运行 lint
uv run ruff check

# 运行类型检查
uv run mypy src/
```

Agora 使用 **uv** 作为包管理器（不是 pip/poetry），目标 Python 3.13+。

## 文档

- [完整复盘文档](docs/retrospective.md) — 用户旅程、故事、场景、架构分层、已知问题与改进方向
