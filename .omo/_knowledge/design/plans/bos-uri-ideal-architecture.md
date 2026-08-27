---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# BOS URI 统一寻址 — 理想态架构设计

> eCOS v5 | P45 W0 | 2026-06-07 | 作者: Agora
>
> **状态**: 设计阶段 (design)  
> **父级目标**: 从「两张表互不通」到「一个路由核心」，Agent 能通过 `bos://` 访问全系统  
> **关联**: [Workflow 全局建模](../workflow-global-modeling.md) · [SSB 协议](../../../projects/ecos/LADS/ssb/)

---

## 一、定位：BOS URI 是什么

BOS URI 是整个 eCOS v5 的**统一资源寻址层**。类比：

| 类比 | URI 模式 | 寻址对象 |
|------|---------|---------|
| HTTP | `http://domain/path` | Web 资源 |
| 文件 | `file:///path` | 本地文件 |
| BOS | `bos://domain/package/action` | eCOS 全系统能力 |

**核心理念**: Agent 只需知道一个 `bos://` URI，就能访问整个系统的所有能力——不需要知道后端是 MCP 代理、本地子进程、还是 HTTP 服务。

---

## 二、现状：三套系统互不通

### 系统 A: `bos_resolver.py` (子进程 stdio)

- 28 条 POC_SERVICES 注册到 `dict`
- ProcessPool 管理子进程，JSON over stdin/stdout
- ⚠️ 不作为主 MCP 工具暴露
- ⚠️ 仅 `python -m` 手动调用

### 系统 B: `server/mcp.py` (FastMCP 服务端)

- ~45 个 MCP 工具
- `mutate_resource` 是空壳 (返回硬编码 "Phase 34 Wave 2")
- 仅 1 个 `@mcp.resource("bos://agora/registry")`
- 不认 POC_SERVICES

### 系统 C: `mcp_protocol.py` (旧协议处理器)

- ProxyManager 兜底 "Resource not found"
- `bos://execution/workers/status` 是唯一硬编码例外

### 成熟度评分

| 层 | 能力 | 当前 | 理想 | 缺口 |
|----|------|------|------|------|
| L1 | 统一路由 | 20% | 100% | 双表合一 + 动态注册 |
| L2 | Agent MCP 接口 | 10% | 100% | 读/写/发现/Schema 5 工具 |
| L2 | Schema 契约 | 0% | 100% | 从零建 |
| L3 | 治理 Pipeline | 5% | 100% | 鉴权/限流/熔断/缓存 |
| L4 | 自动注册 + 观察性 | 0% | 100% | 声明式注册 + metrics |
| **总成熟度** | | **≈10%** | | |

### 缺陷清单 (12 项，已代码验证)

```
🔴 阻断级 (Agent 完全无法用):
  1. 无 resolve_bos_uri MCP 工具（主 FastMCP）
  2. mutate_resource 是空壳
  3. 无 read_resource MCP 工具
  4. 域白名单硬编码 (正则 5 域)

🟡 体验级 (可用但混乱):
  5. POC_SERVICES 和 ProxyManager 两张独立表
  6. 无统一 BOS URI 发现口
  7. URI template 通配基础设施就绪但未激活
  8. ProxyManager 前缀 fallback 硬编码 8 条 if/else

🟢 优化级:
  9. 三种不同的错误格式 (bos_resolver vs mcp.py vs mcp_protocol)
  10. API Key 鉴权不接入 BOS URI
  11. 子进程非标准 MCP stdio
  12. mcp_protocol.py 兜底硬编码 "Resource not found"
```

---

## 三、理想态架构

### 3.1 核心架构图

```
Agent 调用:
  resolve_bos_uri("bos://memory/kos/search", {query: "..."})
  read_resource("bos://memory/kos/search", {query: "..."})
  mutate_resource("bos://omo/schema/update", {schema: {...}})
  list_bos_resources("bos://memory/")
  get_bos_schema("bos://analysis/minerva/research")
                │
       BOS Routing Core Layer (统一核心)
                │
   ┌────────────┼────────────┐
   ▼            ▼            ▼
Registry    Pipeline     Protocol Adapters
(统一注册)  (治理链)     (协议适配)
   │            │            │
   │    ┌───────┼───────┐    │
   │    │ 鉴权→限流→熔断  │    │
   │    │ →缓存→路由→重试  │    │
   │    │ →审计           │    │
   │    └───────┼───────┘    │
   │            │            │
   └────────────┼────────────┘
                ▼
        Schema Registry
        (从 M1 Workflow 节点读取)
```

### 3.2 统一注册表 API

```python
class BOSRouter:
    """统一 BOS URI 路由核心 — 替代 POC_SERVICES + ProxyManager"""

    def register(self, pattern: str, adapter: str, config: dict):
        """动态注册路由"""

    def resolve(self, uri: str) -> BOSRoute:
        """最长前缀匹配，返回 adapter + resolved_path"""

    def list(self, prefix: str = "") -> list[BOSEntry]:
        """统一发现口 — Agent 可查询所有可用资源"""

    def unregister(self, pattern: str):
        """动态注销"""
```

### 3.3 Protocol Adapter 接口

```python
class ProtocolAdapter(ABC):
    """统一协议适配接口"""

    async def call(self, uri: str, args: dict) -> BOSResult:
        """调用后端服务"""

    async def health_check(self) -> bool:
        """健康检查"""
```

实现：
- `MCPProxyAdapter`: 通过 ProxyManager 调用下游 MCP 服务
- `StdioAdapter`: ProcessPool 子进程 (迁移自 POC_SERVICES)
- `InternalAdapter`: 进程内导入调用
- `HTTPAdapter`: (新增) 远程 HTTP 服务

### 3.4 治理 Pipeline 链

```
请求 bos://memory/kos/search
  → 查缓存 (命中直接返回，跳过后续)
  → 鉴权   (API Key → BOS URI 域级别权限)
  → 配额   (accounting 模块)
  → 限流   (滑动窗口 QPS)
  → 熔断   (后端挂了自动拒绝)
  → 路由   (找到 Protocol Adapter)
  → 重试   (可配置策略)
  → 审计   (L0 SSB 事件日志)
  → 返回结果
```

### 3.5 Schema 契约

从 M1 Workflow 节点的 `steps[].action` 读取：

```yaml
# Agent 调用 get_bos_schema("bos://analysis/minerva/research")
{
  "uri": "bos://analysis/minerva/research",
  "method": "POST",
  "input": {
    "query": "string | required",
    "depth": "string | optional | enum=[L0,L1,L2,L3,L4] | default=L2",
    "sources": "string[] | optional | default=[ddg,scholar,metaso]"
  },
  "output": {
    "report": "string",
    "sources": "array",
    "confidence": "float"
  },
  "sla": {
    "max_execution_time": 600,
    "expected_completion_rate": 0.95
  }
}
```

---

## 四、实施 Roadmap

### P45 W0: 设计与注册 (当前)
- [x] T1: 理想态架构设计文档 (本文)
- [ ] T2: L0 MOF BOS 路由 M1 节点建模 (11 文件)
- [ ] T3: L0 constraints.yaml BOS 域约束更新
- [ ] T4: Phase Goals + System State 注册

### P45 W1: P0 阻断修复 (1-2天)
- [ ] T5: 暴露 `resolve_bos_uri` MCP 工具到主 FastMCP
- [ ] T6: `mutate_resource` 从空壳变真实路由
- [ ] T7: `read_resource` MCP 工具实现
- [ ] T8: `list_bos_resources` 统一发现口
- [ ] T9: 域白名单 → 注册表驱动

### P45 W2: P1 统一路由 (1天)
- [ ] T10: 统一注册表 `BOSRouter` (合并双表)
- [ ] T11: URI template 通配注册
- [ ] T12: 统一错误模型

### P45 W3: P2 治理 + Schema (1天)
- [ ] T13: BOS 鉴权集成
- [ ] T14: 自动 BOS 审计
- [ ] T15: `get_bos_schema` MCP 工具

### P46 (候选): P3 + P4
- [ ] 子进程改标准 MCP stdio
- [ ] 限流 + 熔断
- [ ] 声明式自动注册 (AGENTS.md → bos_register)
- [ ] 配置热加载
- [ ] 缓存层
- [ ] Prometheus Metrics

---

## 五、与现有系统的联动

| 已有资产 | BOS 理想态用途 |
|---------|---------------|
| Workflow M1 节点 (26个) | Schema Registry 的 action 来源 |
| `cross_layer.data_flow` | 跨域数据流可视化 |
| `workflow-catalog.yaml` | BOS 路由的 reference 层元数据 |
| L0 审计 (`l0_audit.py`) | Pipeline 审计节点 |
| API Key 系统 | Pipeline 鉴权节点 |
| accounting 模块 | Pipeline 配额节点 |
| `bos://ecos/workflow/*` | BOS URI 命名空间的 reference 层 |
| SSB 不可变日志 | 所有 BOS 操作的审计记录 |

---

## 六、关键决策记录

1. **统一注册表用内存还是 SQLite?**  
   → 内存 + 启动时从配置加载。BOS 路由是热路径不应有 IO；动态变更不频繁。

2. **Protocol Adapter 是否全部统一成 MCP stdio?**  
   → 先统一为 `call(uri, args) → result` 接口，再逐步迁移子进程到 MCP stdio。

3. **Schema Registry 数据源?**  
   → M1 Workflow 节点的 `steps[].action` + 新增 `steps[].input_schema` / `steps[].output_schema`。

4. **缓存放在 Pipeline 何处?**  
   → 链路最前面（鉴权之前）。命中缓存跳过全部后续节点。
