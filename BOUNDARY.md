# cockpit — System Boundary

> 本文档描述 cockpit 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 架构演进对比参见：[`docs/ARCHITECTURE-EVOLUTION.md`](../docs/ARCHITECTURE-EVOLUTION.md)

---

## 1. 暴露接口

### BOS URI

- `bos://cockpit/context`
- `bos://governance/cockpit/context`

### 入口

- **CLI**: `cockpit / workspace` 25+ 子命令
- **MCP stdio**: `cockpit-mcp / cockpit/scripts/cockpit_mcp.py` ~20 tools
- **HTTP**: `cockpit-dashboard` :8090

## 2. 上游依赖

- agora (I0)
- l4-kernel (L4)

## 3. 下游影响

- kairon
- omo
- runtime

## 4. 配置 / SSOT

- 项目源码：`projects/cockpit/`
- 入口定义：`projects/cockpit/pyproject.toml` 或 `package.json`
- 测试：`cd projects/cockpit && uv run pytest tests/ -q`
