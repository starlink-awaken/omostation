# AGENTS.md — Agora MCP Service Mesh

> I0 织层 | MCP Hub-Spoke 架构 | 动态反向代理 Mesh

## Quick Start

```bash
cd projects/agora && uv sync
uv run pytest tests/ --ignore=tests/e2e -q    # 1165/1200 pass
```

## Architecture

### Hub-Spoke Topology

```
                      ┌─────────────────────┐
                      │   Agora Mesh (I0)     │
                      │   :7422 / :7431       │
                      └───┬──────┬──────┬─────┘
                          │      │      │
              ┌───────────┘      │      └───────────┐
              ▼                  ▼                  ▼
         ┌─────────┐      ┌─────────┐        ┌─────────┐
         │ Service A│      │ Service B│        │ Service C│
         └─────────┘      └─────────┘        └─────────┘
```

### 七层内部架构

| 层 | 组件 | 路径 |
|-----|------|------|
| 接入 | FastMCP Server (42+ tools) | `server/mcp.py` |
| 路由 | Router / SmartRouter / FederationRouter | `core/router.py` |
| 代理 | ProxyManager / ProxyRegistry | `mcp_proxy/` |
| 协议 | StdioMCPClient / HttpMCPClient | `mcp_proxy/client.py` |
| 注册 | ServiceRegistry | `core/registry.py` |
| 治理 | Audit / Auth / Tenant / Quota | `auth/` |
| 管道 | Pipeline / Orchestrator / Lifecycle | `mcp_registry/` |

### 三种运行模式

- **stdio**: `agora-mcp` (默认)
- **HTTP**: `agora-web` (:7422)
- **SSE**: `agora-server` (:7431)

## Key Files

| 文件 | 行数 | 说明 |
|------|------|------|
| `server/mcp.py` | 1,945 | MCP 工具注册 (God Module — ⚠️ 待拆分, see docs/god-module-split-plan.md) |
| `mcp_proxy/client.py` | 559 | MCP 客户端 |
| `core/router.py` | 542 | 智能路由器 |
| `mcp/bos_resolver.py` | 831 | BOS URI 解析 |
| `mcp_tools.py` | 819 | 工具注册 |

## Testing

- 测试目录: `tests/` (51 文件, 1200 tests)
- 运行: `uv run pytest tests/ --ignore=tests/e2e -q`
- e2e: `uv run pytest tests/e2e/ -q` (需网络)
- 标记: `@pytest.mark.network` 用于需要网络的测试

## Security

- **SSRF 防护**: `ssrf_guard.py` — 端点 URL 验证
- **认证**: `auth/` — OAuth2, HMAC, Tenant
- **密钥**: 全部通过 `os.environ.get()` 读取
- **无 eval/pickle**: 安全序列化

## Gotchas

1. **server/mcp.py 是 God Module** (1,945行) — 拆分计划见 `docs/god-module-split-plan.md`
2. **ecos/omo 依赖声明但无静态 import** — 通过 subprocess 交互
3. **CI 忽略 e2e 测试** — `--ignore=tests/e2e`
4. **端口**: HTTP :7422, Web :7430, SSE :7431, API :8080

## BOS Services

Agora 对外提供的 BOS URI 服务。总计 **40 路由，5 域**. Agent 通过 `resolve_bos_uri()` 或 `read_resource()` 调用。

### 核心路由 (internal)
- `bos://agora/registry` — Agora 注册表内省 (resource)
  - 无需参数，直接 `read_resource("bos://agora/registry")`

### 记忆域 — memory (5)
- `bos://memory/kos/search` — KOS 跨域语义搜索 (poc, stdio)
- `bos://memory/kos/ingest` — KOS 知识摄取 (poc, stdio)
- `bos://memory/kronos/ingest` — Kronos 知识摄取 (poc, stdio)
- `bos://memory/kronos/query` — Kronos 查询 (poc, stdio)
- `bos://memory/kronos/schedule` — Kronos 调度 (poc, stdio)

### 分析域 — analysis (12)
- `bos://analysis/minerva/research` — Minerva 深度研究 (poc, stdio)
- `bos://analysis/minerva/draft` — Minerva 草稿 (poc, stdio)
- `bos://analysis/minerva/audit` — Minerva 审计 (poc, stdio)
- `bos://analysis/ontoderive/derive` — 本体推导 (poc, stdio)
- `bos://analysis/ontoderive/audit` — 本体审计 (poc, stdio)
- `bos://analysis/ontoderive/fact-check` — 事实核查 (poc, stdio)
- `bos://analysis/codeanalyze/scan` — 代码扫描 (poc, stdio)
- `bos://analysis/codeanalyze/report` — 代码报告 (poc, stdio)
- `bos://analysis/codeanalyze/lint` — 代码 lint (poc, stdio)
- `bos://analysis/iris/connect` — Iris 连接 (poc, stdio)
- `bos://analysis/iris/transform` — Iris 转换 (poc, stdio)
- `bos://analysis/iris/validate` — Iris 校验 (poc, stdio)

### 治理域 — governance (8)
- `bos://governance/omo/audit` — OMO 审计 (internal)
- `bos://governance/omo/inspect` — OMO 检查 (internal)
- `bos://governance/omo/sync` — OMO 同步 (poc, stdio)
- `bos://governance/metaos/gate` — MetaOS 决策门控 (poc, stdio)
- `bos://governance/metaos/register` — MetaOS 注册 (poc, stdio)
- `bos://governance/sot-bridge/register` — SSOT 桥注册 (poc, stdio)
- `bos://governance/sot-bridge/query` — SSOT 桥查询 (poc, stdio)
- `bos://governance/protocols-layer/trigger` — 协议触发器 (poc, stdio)

### 能力域 — capability (8)
- `bos://capability/forge/register-tool` — Forge 注册工具 (poc, stdio)
- `bos://capability/forge/exec-tool` — Forge 执行工具 (poc, stdio)
- `bos://capability/forge/list-tools` — Forge 列出工具 (poc, stdio)
- `bos://capability/forge/discover` — Forge 发现 (poc, stdio)
- `bos://capability/agent-runtime/agent-list` — Agent 列表 (poc, stdio)
- `bos://capability/agent-runtime/chat` — Agent 对话 (poc, stdio)
- `bos://capability/agent-runtime/run-task` — Agent 执行任务 (poc, stdio)
- `bos://capability/agent-runtime/task-status` — Agent 任务状态 (poc, stdio)

### 人格域 — persona (7)
- `bos://persona/health-profile/summary` — 健康档案摘要 (poc, stdio)
- `bos://persona/health-profile/alert` — 健康告警 (poc, stdio)
- `bos://persona/core-models/schema` — 核心模型 Schema (poc, stdio)
- `bos://persona/core-models/validate` — 核心模型校验 (poc, stdio)
- `bos://persona/sot-bridge-persona/recall` — SSOT 人格召回 (poc, stdio)
- `bos://persona/sot-bridge-persona/recall-entity` — SSOT 实体召回 (poc, stdio)
- `bos://persona/sot-bridge-persona/sync` — SSOT 同步 (poc, stdio)

### Agent MCP 工具 (直接调用)
```
resolve_bos_uri(uri, arguments)     — 路由 BOS URI 到后端
read_resource(uri, arguments)        — 读资源 (proxy→poc 降级, 含缓存)
mutate_resource(uri, payload)       — 写资源 (真路由 + L0 审计)
list_bos_resources(prefix)           — 发现可用资源
list_bos_domains()                   — 域统计
get_bos_schema(uri)                  — 查询参数规范
bos_metrics_status(prefix, format)   — 调用指标
bos_middleware_status()              — 限流/熔断/缓存状态
```

### HTTP / SSE 入口
- HTTP: `http://localhost:7422` (`agora-mcp-gateway`)
- SSE:  `http://localhost:7431` (`agora-server`) 
- MCP stdio: `agora-mcp`

### CLI 入口
```bash
agora --help              # 30+ 子命令
mof workflow --help       # 11 workflow 管理命令
```

