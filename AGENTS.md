# AGENTS.md — Agora MCP Service Mesh

> I0 织层 | MCP Hub-Spoke 架构 | 动态反向代理 Mesh

## Quick Commands

```bash
cd projects/agora && uv sync

# 快速测试 (排除 e2e + integration + slow, ~114s)
uv run pytest tests/ --ignore=tests/e2e -k "not slow and not integration and not bos_resolver" -q

# 全量测试 (含集成测试，部分需服务运行)
uv run pytest tests/ --ignore=tests/e2e -q

# 单模块测试
uv run pytest tests/test_bus_envelope.py -q
uv run pytest tests/test_router.py -q
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
- **SSE**: `agora-server --sse` (:7431)
- **Swarm**: 监听 UDP :7455 (发现) + HTTP :7422 (A2A)

## Key Files

| 文件 | 行数 | 说明 |
|------|------|------|
| `server/mcp.py` | 1,945 | MCP 工具注册 + A2A 签名验证接收端 |
| `mcp/swarm.py` | 500+ | 蜂群协调器 + 真实硬件遥测 (psutil) |
| `auth/node_identity.py` | 200+ | Ed25519 节点身份管理 |

## Security

- **X1 Swarm Trust**: 强制执行 Ed25519 节点签名。跨节点消息必须携带 `X-Swarm-Signature`。
- **SSRF 防护**: `ssrf_guard.py` — 端点 URL 验证
- **认证**: `auth/` — OAuth2, HMAC, Tenant

## Gotchas

1. **server/mcp.py 是 God Module**
2. **端口**: HTTP :7422, SSE :7431, Swarm UDP :7455. **API :8080 已废弃**，迁移至 :7422。
3. **BOS 注册表**: `etc/bos-services.yaml` 是 SSOT。

## BOS Services

### 记忆域 — memory (8)
- `bos://memory/local/all-search` — 全域聚合搜索 (KOS/gbrain/Vault) [Swarm-Aware]
- `bos://memory/gbrain/search` — gbrain 高性能搜索 (mcp_proxy)
- `bos://memory/gbrain/query` — gbrain 结构化查询 (mcp_proxy)
- `bos://memory/kos/search` — KOS 语义搜索 (poc, stdio)
- `bos://memory/vault/search` — L4 Vault 本地搜索 (ripgrep)

### 治理域 — governance (1)
- `bos://governance/quality/audit` — 记忆脊知识质量审计 (internal)
  - 输入: `{"text": "str", "query": "str"}`
  - 输出: `{"confidence": float, "reason": "str"}`

### 蜂群域 — swarm (1)
- `bos://swarm/orchestrator/status` — 蜂群拓扑与节点负载监控 (internal)


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

## Bus 子包 (Phase A.0)

### Key files
| File | LOC | Purpose |
|------|-----|---------|
| `agora/bus/__init__.py` | ~50 | facade — publish/subscribe/schedule |
| `agora/bus/envelope.py` | ~75 | BusEnvelope wire format |
| `agora/bus/router.py` | ~50 | backend dispatch + DLQ fallback |
| `agora/bus/dlq.py` | ~130 | SQLite DLQ (WAL + GC) |
| `agora/bus/backends/eventbus.py` | ~75 | wraps agora.core.event_bus |

### Gotchas
- **RETRY**: bus adapter 自身不重试 (透传), 详见 `bus/RETRY-OWNERSHIP.md`
- **DLQ**: 落 `~/.runtime/bus_dlq.db`, 50MB 滚动
- **Backend selection**: Phase A.0 只 1 个, A.1 加 7 个
- **schedule()**: stub, NotImplementedError, Phase A.1
- **Cross-repo usage**: omo 已加 `agora = { path = "../agora" }` 依赖, 可直接 `from agora.bus import publish`


## Workspace-Wide Governance (2026-06-24)

This project follows the workspace-level governance conventions documented in the root `AGENTS.md`:

- **Agent Mutation Protocol**: Any autonomous agent/cron/daemon that modifies workspace state must emit `agent_mutation_intent`, avoid direct file I/O to `.omo/`/`spaces/`, and commit immediately. See `.omo/standards/agent-mutation-protocol.md` for the full protocol.
- **SSOT Guardian**: Run `python3 bin/ssot-guardian.py` from the workspace root before committing to detect task-count, current-wave, submodule-pointer, or direct-omo-io drift.
- **direct-omo-io**: Scripts must route writes to `.omo/` through `omo CLI`, `projects/omo` core, or `projects/c2g` ingress — never via raw `open()/mkdir()/write_text()`.
- **Submodule Governance**: Commit changes inside the submodule first, then bump the root-repo pointer; `git submodule status` with a `+` prefix indicates pending drift.
