# Agora server/mcp.py God Module 拆分计划

> 当前状态: `server/mcp.py` 1,757 行，混合 接入/路由/代理/治理/审计 5 层逻辑
> 目标: 拆分为 4 个焦点模块，每个 <500 行，单一职责

## 当前进展 (2026-07-14)

- ✅ `server/tools_proxy.py` (647 行) — Proxy/路由/注册/事件工具
- ✅ `server/tools_registry.py` (640 行) — 仓库/生命周期/A2A/Agent Card
- ✅ `server/tools_bos.py` (889 行) — BOS URI resolve/list/schema/mutate/resources
- ✅ `server/tools_api_keys.py` — API Key 管理工具
- ✅ `server/_response.py` (61 行) — `_ok/_error/FORMAT_VERSION` 统一
- ✅ `mcp/tools_template.py` — 改为 re-export `_response.py`
- ✅ `server/mcp.py` 头部注释更新

**待推进**:
- `server/tools_bos.py` 889 行仍超大, 需二次拆分 (resolve 与 execute 分离)
- `server/mcp.py` 剩余 867 行 (AuditSubscriber + resources + main + re-exports)
- `server/tools_registry.py` 640 行, 需拆分 (repo/lifecycle/a2a/agent card)
- `server/tools_proxy.py` 647 行, 需二次拆分

## 当前结构分析

```
server/mcp.py (867 行)
├── 接入层: FastMCP Server 配置 + 全局 mcp 实例 (行 1-100)
├── 内部组件: AuditSubscriber + _get_task_manager (行 194-400)
├── Resource: 3 个 @mcp.resource 定义 (行 671-800)
├── 执行引擎: agora_execute (行 808-829)
├── 入口: main() (行 832-861)
└── Re-exports: 行 864-867
```

## 拆分方案

### Phase 1: 工具分类提取 (低风险)

```
server/mcp.py                    # 仅保留 FastMCP Server 配置 (~150 行)
server/tools_diagnostics.py      # 健康检查/状态/诊断工具 (~200 行)
server/tools_registry.py         # MCP 注册表/仓库工具 (~250 行)
server/tools_proxy.py            # 代理管理/转发工具 (~300 行)
server/tools_governance.py       # 审计/治理/A2A 工具 (~300 行)
```

**每个工具文件模式**:
```python
def register_tools(mcp: FastMCP) -> None:
    """向 mcp 实例注册本模块的所有工具。"""
    @mcp.tool()
    def tool_xxx(...): ...
```

**server/mcp.py 简化为**:
```python
from .tools_diagnostics import register_tools as register_diagnostics
from .tools_registry import register_tools as register_registry
from .tools_proxy import register_tools as register_proxy
from .tools_governance import register_tools as register_governance

def create_server():
    mcp = FastMCP("Agora")
    register_diagnostics(mcp)
    register_registry(mcp)
    register_proxy(mcp)
    register_governance(mcp)
    return mcp
```

### Phase 2: _ok/_error 提取 (立刻可做)

```
agora/response_helpers.py        # _ok/_error 统一位置
```

移除 2 处重复定义:
- `server/mcp.py:276-281`
- `mcp/tools_template.py:29-34`

### Phase 3: 测试迁移

- 每个 tools_*.py 单独测试文件
- `server/mcp.py` 仅测试 Server 创建和工具注册计数

## 风险控制

1. **渐进迁移**: 先提取最独立的工具组（诊断），运行测试后再提取下一组
2. **别名兼容**: 保留 `from server.mcp import ...` 的向后兼容
3. **测试优先**: 每次提取前先确保相关测试通过 (当前 20 个失败需先修复)

## 预估工作量

| Phase | 操作 | 预估时间 | 风险 |
|-------|------|---------|------|
| Phase 2 | _ok/_error 提取 | 15 min | 低 |
| Phase 1 | 工具分类提取 (诊断) | 30 min | 低 |
| Phase 1 | 工具分类提取 (注册表) | 30 min | 中 |
| Phase 1 | 工具分类提取 (代理) | 45 min | 中 |
| Phase 1 | 工具分类提取 (治理) | 45 min | 中 |
| Phase 3 | 测试迁移 | 60 min | 低 |
| **合计** | | **~3.5h** | |

## 预期收益

- server/mcp.py: 1,757 → ~150 行
- 每个工具模块: <300 行，单一职责
- 新人可独立修改某一类工具而无需理解整文件
- 测试覆盖可以按工具组做增量
