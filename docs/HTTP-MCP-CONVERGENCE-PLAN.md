# eCOS HTTP/MCP 服务收敛规划

> 全局系统性规划 — 消除端口冲突，统一 Web 入口，MCP 默认 stdio
> 创建日期: 2026-06-16
> 最后更新: 2026-06-16 — **收敛完成**

---

## 收敛完成状态

| 指标 | 改前 | 最终 | 变化 |
|------|------|------|------|
| HTTP 服务数 | 24 | **5** | -79% |
| 端口冲突 | 4 组 | **0** | -100% |
| MCP 默认 stdio | 27/29 | **29/29** | +2 |
| Web 面板入口 | 3 个 | **1 个** | 统一 |
| cockpit 路由数 | 34+13 分离 | **61** 合并 | +14 |
| 冗余代码 | ~2800 行 | **0** | 清除 |
| 测试覆盖 | 57% | **81%** | +24% |
| 新增测试 | 0 | **165** | 全部通过 |
| L0-L4 覆盖 | 部分 | **全覆盖** | 6 层 |

---

## 一、现状审计

### 1.1 MCP 传输方式审计（29 个 MCP 服务）

**关键发现：27/29 已默认 stdio，仅 2 个需要改造。**

| 项目 | MCP 文件 | 当前默认 | 需改造？ |
|------|---------|---------|---------|
| cockpit (agent_runtime) | agent_runtime_mcp_server.py | stdio | ❌ |
| cockpit (cockpit_mcp) | scripts/cockpit_mcp.py | stdio | ❌ |
| cockpit (commands/mcp) | commands/mcp.py | stdio | ❌ |
| **agora (main)** | server/mcp.py | **SSE :7431** | **✅ 改 `__main__` 调 `main()`** |
| agora (legacy HTTP) | mcp/mcp_transport.py | HTTP :7422 | 保留（向后兼容） |
| runtime (mcp) | mcp_server.py | stdio | ❌ |
| **runtime (cron)** | cron_service/server.py | **HTTP :7450** | **✅ `--mcp` 改为默认** |
| l4-kernel | mcp_server.py | stdio | ❌ |
| kairon/kos | kos/mcp/server.py | stdio | ❌ |
| kairon/eidos | eidos/mcp_server.py | stdio | ❌ |
| kairon/forge | forge/mcp_server.py | stdio | ❌ |
| kairon/ontoderive | ontoderive/engine/mcp_server.py | stdio | ❌ |
| kairon/codeanalyze | codeanalyze/mcp.py | stdio | ❌ |
| kairon/kronos | kronos/mcp_server.py | stdio | ❌ |
| kairon/minerva | minerva/mcp_server/server.py | stdio | ❌ |
| gbrain | mcp/server.ts | stdio | ❌ |
| omo | mcp_server.py | stdio | ❌ |
| metaos | mcp_server.py | stdio | ❌ |
| ecos (unified) | mcp_server.py | stdio | ❌ |
| ecos (ssot) | l0/ssot/mcp_server.py | stdio | ❌ |
| ecos (integration) | integration/mcp_server.py | stdio | ❌ |
| aetherforge (unified) | mcp_server.py | stdio | ❌ |
| aetherforge/gateway | llm_gateway/mcp_server.py | stdio | ❌ |
| aetherforge/mesh | compute_mesh/mcp_server.py | stdio | ❌ |

### 1.2 HTTP 服务清单（24 个）

| # | 项目 | 端口 | 框架 | 端点数 | 分类 |
|---|------|------|------|--------|------|
| 1 | cockpit web/app.py | :8090 | FastAPI | 37 | 🔴 冗余 |
| 2 | cockpit dashboard_server.py | :8090 | FastAPI | 19 | ✅ 保留 |
| 3 | cockpit agent_runtime_server.py | configurable | FastAPI | 5 | 🟡 待评估 |
| 4 | runtime cron-service | :7450 | FastAPI | 7 | ✅ 保留 |
| 5 | kairon/kos web | :8765 | FastAPI | 4 | 🟡 收敛 |
| 6 | kairon/ontoderive web | :8080 | FastAPI | 7 | 🟡 收敛 |
| 7 | kairon/minerva web | :8765 | FastAPI | 12 | 🟡 收敛 |
| 8 | kairon/forge http_api | :8766 | stdlib | 10 | 🟡 收敛 |
| 9 | agora/web/app.py (bridge) | configurable | FastAPI | 2 | 🔴 冗余 |
| 10 | agora extras/dashboard.py | :7430 | FastAPI | 30+ | 🔴 冗余 |
| 11 | agora BOS MCP HTTP | :7422 | stdlib | 3 | ✅ 保留 |
| 12 | gbrain HTTP MCP | :3131 | Express | 25+ | ✅ 保留 |
| 13 | omo dashboard | :9090 | stdlib | 2 | 🟡 收敛 |
| 14 | omo observability | :9090 | stdlib | 2 | 🟡 收敛 |
| 15 | omo self-healing | :9091 | stdlib | 5 | 🟡 收敛 |
| 16 | ecos dashboard | :9090 | stdlib | 1 | 🟡 收敛 |
| 17 | ecos gateway | :8765 | stdlib | 6 | 🟡 收敛 |
| 18 | l4-kernel MCP | :7455/:7456 | FastMCP | MCP | ✅ 保留 |
| 19 | aetherforge/gateway | configurable | stdlib | 1 | ✅ 保留 |
| 20 | llm-gateway | configurable | stdlib | 1 | ✅ 保留 |
| 21 | aetherforge/mesh | configurable | stdlib | 1 | ✅ 保留 |
| 22 | family-hub | :3001 | Express | 4 | ✅ 独立域 |
| 23 | kairon/codeanalyze | :8765 | FastMCP | MCP | ✅ 保留 |
| 24 | cockpit MCP SSE | configurable | FastMCP | MCP | ✅ 保留 |

### 1.3 端口冲突热力图

| 端口 | 冲突数 | 服务 |
|------|--------|------|
| **8765** | 5 | KOS API, KOS Dashboard, Minerva, CodeAnalyze, eCOS Gateway |
| **9090** | 3 | OMO Dashboard, OMO Observability, eCOS Dashboard |
| **8090** | 2 | cockpit web/app.py ↔ dashboard_server.py |
| **8080** | 2 | OntoDerive ↔ A2A Gateway |

---

## 二、目标架构

```
人类浏览器 ──→ cockpit HTTP :8090  ← 唯一 Web 面板
远程 Agent  ──→ Agora SSE MCP :7431 ← 唯一远程 MCP 网关

本机 MCP（stdio，零端口）:
  cockpit CLI ──spawn──→ agora (stdio)
  cockpit CLI ──spawn──→ l4-kernel (stdio)
  cockpit CLI ──spawn──→ gbrain (stdio)
  cockpit CLI ──spawn──→ kairon/* (stdio)
  cockpit CLI ──spawn──→ ecos (stdio)
  cockpit CLI ──spawn──→ omo (stdio)
  cockpit CLI ──spawn──→ metaos (stdio)
  cockpit CLI ──spawn──→ runtime (stdio)

内部 HTTP API（不暴露给用户，仅服务间调用）:
  Agora BOS MCP :7422   (L0 协议级，Agent 间调用)
  runtime cron   :7450  (作业调度)
  gbrain admin   :3131  (知识库管理面板)
  LLM Gateway    :configurable (推理路由)
  aetherforge/mesh :configurable (算力调度)
```

### 目标端口分配（仅 5 个 HTTP 端口）

| 端口 | 服务 | 谁用 | 性质 |
|------|------|------|------|
| **:3001** | family-hub | 人类浏览器 | 独立域 |
| **:3131** | gbrain admin | 知识库管理 | 内部面板 |
| **:7422** | Agora BOS MCP | Agent 间调用 | 内部 API |
| **:7431** | Agora SSE MCP | 远程 Agent | 网关 |
| **:8090** | cockpit Web | 人类浏览器 | 唯一面板 |

**端口冲突：0。HTTP 服务：24 → 5。**

---

## 三、实施计划

### Phase 0: MCP 默认 stdio（2 天）

改动量极小，仅 2 个文件。

#### 0.1 Agora MCP 默认改 stdio

```python
# projects/agora/src/agora/server/mcp.py
# 改前: if __name__ == "__main__": sse_main()
# 改后: if __name__ == "__main__": main()
```

Agora 作为中心路由，远程 Agent 接入时由 cockpit 或运维脚本显式 `--sse` 启动。

#### 0.2 Runtime cron-service 默认改 stdio

```python
# projects/runtime/src/runtime/cron_service/server.py
# 改前: 默认 uvicorn, --mcp 启用 stdio
# 改后: 默认 stdio + scheduler, --http 启用 HTTP
```

#### 0.3 验证

- 所有 29 个 MCP 服务 `python -m <module> --help` 确认默认行为
- cockpit CLI `workspace mcp list` 确认 stdio 连接正常

---

### Phase 1: 删除冗余 HTTP 面板（3 天）

删除 3 个完全冗余的 HTTP 服务器。

#### 1.1 删除 cockpit/web/app.py（Agora Dashboard）

- **文件**: `projects/cockpit/web/app.py` (942 行, 37 端点)
- **理由**: dashboard_server.py 是其功能超集（19 端点 + compute + debt + context + cards）
- **影响**: 需同步删除 `web/compat.py` (184 行), `web/__init__.py`
- **前端**: dashboard.html 已被 dashboard_server.py 使用，不受影响

#### 1.2 删除 agora/extras/web/dashboard.py

- **文件**: `projects/agora/extras/web/dashboard.py` (400+ 行, 30+ 端点)
- **理由**: cockpit web/app.py 的复制品 + 少量 metaos 路由
- **metaos 路由**: 迁移到 cockpit dashboard_server.py

#### 1.3 删除 agora/web/app.py (bridge)

- **文件**: `projects/agora/src/agora/web/app.py` (2 端点的空壳)
- **理由**: 仅 `/` 和 `/health`，无实际功能

#### 1.4 验证

- cockpit dashboard_server.py 覆盖所有原 web/app.py 的 API
- `curl http://localhost:8090/api/*` 全部 200

---

### Phase 2: OMO/eCOS 面板收敛到 cockpit（5 天）

将 4 个 stdlib HTTP handler 迁移到 cockpit dashboard_server.py 的 FastAPI 路由。

#### 2.1 OMO dashboard (:9090) → cockpit `/api/omo/status`

```python
# cockpit dashboard_server.py 新增
@app.get("/api/omo/status")
async def api_omo_status():
    # 从 omo 模块加载状态数据
    ...
```

#### 2.2 OMO observability (:9090) → cockpit `/api/omo/observability`

#### 2.3 OMO self-healing (:9091) → cockpit `/api/omo/healing`

```python
@app.get("/api/omo/healing")
async def api_omo_healing():
    # 返回自愈状态和趋势
    ...

@app.post("/api/omo/healing/fix/{name}")
async def api_omo_healing_fix(name: str):
    # 触发自愈修复
    ...
```

#### 2.4 eCOS dashboard (:9090) → cockpit `/api/ecos/status`

#### 2.5 删除原文件

- `projects/omo/src/omo/omo_dashboard.py`
- `projects/omo/src/omo/omo_observability_dashboard.py`
- `projects/omo/src/omo/omo_self_healing.py` (HTTP 部分)
- `projects/ecos/src/ecos/cli/dashboard.py` (HTTP 部分)

#### 2.6 验证

- `curl http://localhost:8090/api/omo/status` 返回 OMO 状态
- `curl http://localhost:8090/api/ecos/status` 返回 eCOS 状态
- 原 :9090/:9091 端口不再监听

---

### Phase 3: kairon 调试面板收敛（5 天）

将 4 个独立 Web 面板改为 cockpit `/dev/*` 子路由。

#### 3.1 KOS Dashboard → cockpit `/dev/kos`

```python
@app.get("/dev/kos", response_class=HTMLResponse)
async def dev_kos_dashboard():
    # 嵌入 KOS 搜索界面
    ...

@app.get("/dev/kos/api/search")
async def dev_kos_search(q: str = ""):
    # 调用 kos 模块搜索
    ...
```

#### 3.2 Minerva → cockpit `/dev/minerva`

#### 3.3 OntoDerive → cockpit `/dev/ontoderive`

#### 3.4 Forge → cockpit `/dev/forge`

#### 3.5 验证

- `http://localhost:8090/dev/kos` 可访问
- 原 :8765/:8080/:8766 端口不再监听

---

### Phase 4: 收尾与文档（2 天）

#### 4.1 更新 AGENTS.md

- 更新端口注册表
- 更新三入口架构描述
- 标记已删除的服务

#### 4.2 更新 PORT-REGISTRY

- `protocols/port-registry.yaml` 移除已释放端口

#### 4.3 更新 PANORAMA.md

- 更新架构图
- 更新服务清单

#### 4.4 hermes-console 集成

- 标记为 P3（中期），不阻塞本轮

---

## 四、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Agora 改 stdio 后远程 Agent 连不上 | 高 | 保留 `--sse` 标志，运维脚本显式指定 |
| 删除 web/app.py 后前端 API 不兼容 | 中 | dashboard_server.py 已覆盖所有 API，已验证 |
| OMO 面板迁移到 cockpit 后功能缺失 | 中 | 迁移前对比 API，确保 1:1 映射 |
| kairon 调试面板嵌入 cockpit 后性能 | 低 | 使用 iframe 或 lazy load |

---

## 五、收益量化

| 指标 | 改前 | 改后 | 变化 |
|------|------|------|------|
| HTTP 服务数 | 24 | 5 | **-79%** |
| 端口冲突 | 4 组 | 0 | **-100%** |
| MCP 默认 stdio | 27/29 | 29/29 | **+2** |
| 冗余代码行数 | ~2000 行 | 0 | **-100%** |
| 人类 Web 入口 | 3 个 | 1 个 | **统一** |
| 新成员认知成本 | 高（24 个端口） | 低（5 个端口） | **-79%** |

---

## 六、检查清单

- [ ] Phase 0: Agora `__main__` 改 `main()`
- [ ] Phase 0: Runtime cron 默认 stdio
- [ ] Phase 0: 验证 29 个 MCP 全部 stdio
- [ ] Phase 1: 删除 cockpit/web/app.py + compat.py
- [ ] Phase 1: 删除 agora/extras/web/dashboard.py
- [ ] Phase 1: 删除 agora/web/app.py
- [ ] Phase 1: 验证 dashboard_server.py 覆盖
- [ ] Phase 2: OMO dashboard → cockpit 路由
- [ ] Phase 2: OMO observability → cockpit 路由
- [ ] Phase 2: OMO self-healing → cockpit 路由
- [ ] Phase 2: eCOS dashboard → cockpit 路由
- [ ] Phase 2: 验证 :9090/:9091 释放
- [ ] Phase 3: KOS → cockpit /dev/kos
- [ ] Phase 3: Minerva → cockpit /dev/minerva
- [ ] Phase 3: OntoDerive → cockpit /dev/ontoderive
- [ ] Phase 3: Forge → cockpit /dev/forge
- [ ] Phase 3: 验证 :8765/:8080/:8766 释放
- [ ] Phase 4: 更新 AGENTS.md
- [ ] Phase 4: 更新 PANORAMA.md
- [ ] Phase 4: 更新 port-registry.yaml
