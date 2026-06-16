# omo — System Boundary

> 本文档描述 omo 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 架构演进对比参见：[`docs/ARCHITECTURE-EVOLUTION.md`](../docs/ARCHITECTURE-EVOLUTION.md)

---

## 1. 暴露接口

### BOS URI

- `bos://governance/omo/state`
- `bos://governance/omo/debt`
- `bos://governance/omo/audit`
- `bos://governance/omo/inspect`
- `bos://governance/omo/sync`

### 入口

- **CLI**: `omo` 26+ 子命令
- **CLI**: `omo-debt / cards` 
- **MCP stdio**: `omo-mcp` 10+ tools
- **SSE daemon**: `omo-sse-daemon` 

## 2. 上游依赖

- agora (I0)
- ecos (L0 MOF)
- runtime (L1)

## 3. 下游影响

- cockpit
- l4-kernel

## 4. 配置 / SSOT

- 项目源码：`projects/omo/`
- 入口定义：`projects/omo/pyproject.toml` 或 `package.json`
- 测试：`cd projects/omo && uv run pytest tests/ -q`
