# Entry Convergence Design — 入口收敛方案

> 2026-06-10 | ✅ 已实施 Phase 1-2 | Phase 3-4 同步完成
> **终态**: 7 入口 → 3 入口（cockpit CLI + agora MCP :7431 + cockpit HTTP :8090）

---

## 一、现状分析

### 1.1 当前 7 个入口

```
                  Agent/用户
                      │
        ┌─────────────┼──────────────┐
        │             │              │
    cockpit CLI  cockpit MCP    cockpit HTTP
    (subprocess)  (stdio:37)    (FastAPI:8090)
        │             │
        │         agora MCP      agora HTTP
        │         (SSE:7431:42)  (aiohttp:7422)
        │             │
        │         runtime MCP    l4-kernel MCP
        │         (stdio:30)     (stdio:43)
        │
        └──── 7 入口, 4 端口, 3 协议栈
```

### 1.2 核心问题

| 问题 | 表现 | 影响 |
|------|------|------|
| **MCP 入口不统一** | cockpit MCP (stdio) + agora MCP (SSE) 同时存在 | Agent 需要知道连哪个；分头维护两个 MCP 配置 |
| **内部服务直接暴露** | runtime MCP、l4-kernel MCP 直接对外 | 旁路 agora 治理层（限流/熔断/审计）|
| **HTTP 服务分叉** | cockpit HTTP (FastAPI) + agora HTTP (aiohttp) | 两套鉴权、两套文档、双倍维护 |
| **端口混乱** | 4 个端口 (:7422/:7431/:8090 + stdio) | 运维复杂度高，端口冲突风险 |

### 1.3 工具覆盖分析

| MCP Server | 工具数 | 核心能力 | 当前入口 |
|:----------:|:------:|---------|:--------:|
| **cockpit MCP** | 21 | research/status/cards/vault/domains/workspace_context | stdio |
| **l4-kernel MCP** | 43 | domain/list/health/validate/config/tools/storage/... | stdio |
| **runtime MCP** | 30 | health/matrix/protocol/ontology/brief/kv | stdio |
| **agora MCP** | 42 | bos_resolve/proxy/registry/route/swarm/agent | SSE :7431 |

---

## 二、目标架构（3 入口）

```
                    Agent/用户
                        │
          ┌─────────────┼─────────────────┐
          │             │                 │
    cockpit CLI    agora MCP         cockpit HTTP
    (subprocess)   (SSE :7431)       (FastAPI :8090)
                   │
          ┌────────┼────────┐
          │        │        │
    cockpit MCP  l4-kernel  runtime MCP
    (stdio 代理)  MCP(代理)  (stdio 代理)
```

### 2.1 三层入口定义

| 入口 | 协议 | 端口 | 职责 | 使用者 |
|:----:|:----:|:----:|------|--------|
| **cockpit CLI** | subprocess | — | 终端运维管理 | 人类 |
| **agora MCP** | SSE JSON-RPC | **:7431** | 统一 MCP 入口，代理 cockpit/l4-kernel/runtime 的所有工具 | Agent / LLM |
| **cockpit HTTP** | FastAPI | **:8090** | 统一 Web / REST 入口，聚合 agora 功能 | 浏览器 / 第三方 |

### 2.2 内部服务下线

| 服务 | 下线方式 | 何时下线 |
|:----:|---------|:--------:|
| cockpit MCP (stdio) | 通过 agora KNOWN_SERVICES 代理暴露 | Phase 2 |
| l4-kernel MCP (stdio) | 通过 agora `bos://l4-kernel/**` 路由 | Phase 2 |
| runtime MCP (stdio) | 通过 agora `bos://runtime/**` 路由 | Phase 2 |
| agora HTTP (:7422) | 功能的 BOS MCP 工具化，由 cockpit HTTP 消费 | Phase 3 |

### 2.3 工具注册映射

```
agora MCP (:7431)                                  原服务
─────────────────────────────────────────────      ─────────
resolve_bos_uri("bos://cockpit/research/...")       cockpit MCP
resolve_bos_uri("bos://l4-kernel/domains/list")     l4-kernel MCP
resolve_bos_uri("bos://runtime/health")             runtime MCP
resolve_bos_uri("bos://memory/kos/search")          agora (已有)
```

**关键设计**: 所有内部 MCP 工具变成 `bos://` URI 资源，通过 `resolve_bos_uri` 统一访问。Agent 只需要 1 个 MCP 工具（`resolve_bos_uri`）即可访问所有能力。

---

## 三、分阶段迁移计划

### Phase 1: cockpit MCP → agora KNOWN_SERVICES（1天）

**目标**: cockpit MCP 的 21 个工具通过 agora 可访问

**改动**:
1. **agora KNOWN_SERVICES 添加 cockpit_mcp**
   ```python
   # mcp_bootstrap.py 新增:
   BosService(
       uri="bos://cockpit/context",
       domain="governance",
       package="cockpit",
       action="workspace_context",
       transport="mcp_stdio",
       command=[...cockpit-mcp...],
   )
   ```
2. **cockpit MCP tools 添加 BOS URI 别名**
   - 每个 `@_tool()` 函数注册一个对应的 `bos://cockpit/X` 路由
   - 复用现有的 `mcp_stdio` 传输通道

3. **测试验证**: 通过 agora 的 `resolve_bos_uri("bos://cockpit/cards/status")` 等于直接调用 `cards_status()`

**结果**: agora MCP 工具数: 42 + 21 = 63

### Phase 2: l4-kernel MCP + runtime MCP → agora 代理（1天）

**目标**: 所有 MCP 统一到 agora 的 SSE :7431

**改动**:
1. **l4-kernel 注册到 KNOWN_SERVICES**
   ```python
   # mcp_bootstrap.py 新增:
   BosService(
       uri="bos://l4-kernel/domains/list",
       domain="governance",
       package="l4-kernel",
       action="list_all",
       transport="mcp_stdio",
       command=["uv", "run", "python", "-m", "l4_kernel.mcp_server"],
   )
   ```
2. **runtime 注册到 KNOWN_SERVICES**
   ```python
   BosService(
       uri="bos://runtime/health",
       domain="capability",
       package="runtime",
       action="health",
       transport="mcp_stdio",
       command=["uv", "run", ...],
   )
   ```
3. **更新 CLAUDE.md / AGENTS.md**: 声明 agora MCP :7431 为唯一 MCP 入口
4. **废弃 stdio 入口声明**: cockpit/l4-kernel/runtime 的独立 MCP 入口标记为 deprecated

**结果**: Agent 配置从 4 个 MCP 端点 → 1 个 MCP 端点

### Phase 3: HTTP 统一 — cockpit HTTP 吸收 agora HTTP（1天）

**目标**: 所有 HTTP/REST 功能统一到 cockpit HTTP :8090

**改动**:
1. **cockpit HTTP 新增 agora 代理路由**
   ```python
   # dashboard_server.py 新增:
   @app.get("/api/agora/{path:path}")
   async def proxy_agora(path: str):
       result = await agora_client.get(f"http://localhost:7422/{path}")
       return result.json()
   ```
2. **agora HTTP 标记 deprecated**
   - 所有 agora HTTP 工具路由添加 deprecation warning 头
   - cockit HTTP 作为替代入口

**结果**: HTTP 入口: 2 → 1

### Phase 4: 端口回收 + 文档同步（0.5天）

**目标**: 清理废弃端口，更新所有文档

**改动**:
1. **端口回收**:
   - :7422 → 重定向到 :8090（或关闭）
   - stdio 入口不再作为独立服务暴露

2. **文档同步**:
   - AGENTS.md: 更新入口表
   - PANORAMA.md: 更新架构图
   - JOURNEY-PROBES.md: 更新旅程路径

---

## 四、迁移后的架构全景

```
                    Agent / LLM
                        │
               agora MCP :7431 (SSE)
                ┌───────┴───────┐
                │               │
          resolve_bos_uri   Native MCP tools
                │           (42 + 21 + 43 + 30 = 136)
        ┌───────┼───────┐
        │       │       │
    cockpit  l4-kernel  runtime  agora
    (21)     (43)       (30)     (42)

人类运维: cockpit CLI
浏览器:   cockpit HTTP :8090
```

### 配置变更

**当前 Agent 配置（4 个 MCP）**:
```json
{
  "mcp_servers": {
    "cockpit": {"command": "cockpit-mcp"},
    "agora": {"url": "http://localhost:7431/sse"},
    "l4-kernel": {"command": "l4-kernel-mcp"},
    "runtime": {"command": "runtime-mcp"}
  }
}
```

**收敛后 Agent 配置（1 个 MCP）**:
```json
{
  "mcp_servers": {
    "agora": {"url": "http://localhost:7431/sse"}
  }
}
```

---

## 五、风险与对策

| 风险 | 等级 | 对策 |
|:----:|:----:|------|
| 现有 Agent 配置依赖 stdio 入口 | 🟡 | 向后兼容：Phase 2 保留 stdio 入口但标记 deprecated，Phase 4 移除 |
| `mcp_stdio` 桥接增加延迟 | 🟢 | 已有成熟实现（mcp_stdio_bridge.py），延迟增量 <5ms |
| l4-kernel 43 工具全部注册耗时长 | 🟡 | 按使用频率分批注册：核心(10)→常用(15)→全部(43) |
| cockpit HTTP 和 agora HTTP 功能重复 | 🟡 | Phase 3 做功能审计后决定保留项 |

---

## 六、收益量化

| 指标 | 当前 | 收敛后 |
|:----|:---:|:-----:|
| MCP 入口数 | 4 | **1** |
| HTTP 入口数 | 2 | **1** |
| 总入口数 | 7 | **3** |
| Agent 配置项 | 4 | **1** |
| 端口占用 | 4 | **2** |
| 鉴权体系 | 3 套 | **1 套**（agora API key）|
| 运维复杂度 | 高 | 低 |
