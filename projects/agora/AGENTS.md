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
| `server/mcp.py` | 1,757 | MCP 工具注册 (God Module) |
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

1. **server/mcp.py 是 God Module** (1,757行) — 拆分计划见 `docs/god-module-split-plan.md`
2. **ecos/omo 依赖声明但无静态 import** — 通过 subprocess 交互
3. **CI 忽略 e2e 测试** — `--ignore=tests/e2e`
4. **端口**: HTTP :7422, Web :7430, SSE :7431, API :8080
