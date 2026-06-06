# 5+3+1 统一接口层设计方案

> 2026-06-06 · 基于全量审计 · 解决接口碎片化

---

## 一、问题诊断

当前 9 项目暴露 21 CLI + 286 MCP + 9 HTTP + 8 脚本，但：

```
问题:
  1. Agent 不知连哪个 MCP server → 需要人告诉它
  2. 端口冲突 8080/9090 → 多项目抢端口
  3. CLI 入口碎片化 → 用户需要记住 21 个命令
  4. 没有"项目有什么能力"的 SSOT → 每次问 Agent
  5. Agora 的 KNOWN_SERVICES 是硬编码 → 新项目加不进来
```

## 二、设计原则

```
不增加新层 → 不创建 I-1, 不增加维护负担
不强行合并 → 保留各项目独立性, 只加一层声明
声明式优先 → 能力用 YAML 描述, 不写代码
渐进落地 → 核心: 接口注册表 SSOT, 然后 Agora/Cockpit 消费
```

## 三、核心方案: 接口注册表 (Interface Registry)

### 3.1 新增 L0 协议: `interface-registry.yaml`

每个项目维护一个 `INTERFACE.yaml`:

```yaml
# projects/agora/INTERFACE.yaml
project: agora
layer: I0
cli:
  - name: agora
    module: agora.cli:main
    description: MCP 服务汇聚中心 CLI
  - name: agora-mcp
    module: agora.server.mcp:main
    description: 统一 MCP 服务器 (stdio)

mcp:
  server: agora.server.mcp
  transport: [stdio, http, sse]
  tools: 42
  proxy_enabled: true

http:
  - port: 7422
    protocol: FastMCP
    description: MCP HTTP endpoint
  - port: 7431
    protocol: FastMCP SSE
    description: MCP SSE endpoint
  - port: 7430
    protocol: FastAPI
    description: Web dashboard
  - port: 8080
    protocol: aiohttp
    description: REST API gateway

dependencies:
  runtime: [fastmcp, httpx, aiohttp]
  dev: [pytest, ruff, mypy]
```

### 3.2 根注册表: `protocols/interface-registry.yaml`

```yaml
# 由各项目 INTERFACE.yaml 聚合生成
interfaces:
  agora:     {$ref: ../projects/agora/INTERFACE.yaml}
  cockpit:   {$ref: ../projects/cockpit/INTERFACE.yaml}
  runtime:   {$ref: ../projects/runtime/INTERFACE.yaml}
  ...
ports:
  7422: [agora, mcp-http]
  7431: [agora, mcp-sse]
  8090: [cockpit, web-dashboard]
  ...
tools:
  workspace_context: [cockpit, L4-bridge]
  proxy_call:       [agora, core]
  ...
```

## 四、消费方式

### 4.1 Agora 自动注册 (代码不改)

```python
# agora/mcp/mcp_bootstrap.py 改为读 registry:
def load_services():
    registry = yaml.safe_load(open("protocols/interface-registry.yaml"))
    for proj, cfg in registry["interfaces"].items():
        if cfg.get("mcp"):
            register_mcp_service(proj, cfg["mcp"]["command"])
```

### 4.2 Cockpit 能力菜单 (不用硬编码)

```python
# cockpit CLI 自动生成命令列表:
registry = yaml.safe_load(open("protocols/interface-registry.yaml"))
# → 输出: "可用项目: agora(I0), cockpit(L3), kairon(L2)..."
```

### 4.3 Agent 能力发现 (MCP 工具)

```python
# 新增 MCP tool:
@mcp.tool()
def interface_list(category: str = "all") -> str:
    """列出所有注册的接口能力 (cli/mcp/http/scripts)。"""
    registry = load_registry()
    return json.dumps(filter_by_category(registry, category))
```

## 五、落地计划

### Phase 1: 注册表建立 (1h)
- [ ] 创建各项目 `INTERFACE.yaml`
- [ ] 创建根 `protocols/interface-registry.yaml`
- [ ] 解决端口冲突 (按优先级: I0 > L3 > L2)

### Phase 2: Agora 消费 (1h)
- [ ] `KNOWN_SERVICES` → 改为读 registry
- [ ] `proxy_connect` → 自动发现 MCP servers

### Phase 3: Cockpit 消费 (1h)
- [ ] CLI 默认面板 → 显示"可用项目"列表
- [ ] `interface_list` MCP 工具 → Agent 可查询

### Phase 4: CI 验证 (0.5h)
- [ ] `check-interfaces.py` → 验证 registry 与代码一致
- [ ] CI workflow → 接口保鲜检查

## 六、收益

```
之前:                              之后:
Agent: "连哪个 MCP?"               Agent: interface_list → 全量菜单
人: 21 个 CLI 各自 help            cockpit → 默认面板聚合
端口: 3 个 8080 打架                registry 排他仲裁
新项目: 手动改 KNOWN_SERVICES      INTERFACE.yaml 声明即可
```
