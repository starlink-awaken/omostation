# ecos — System Boundary

> 本文档描述 ecos 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 架构演进对比参见：[`docs/ARCHITECTURE-EVOLUTION.md`](../docs/ARCHITECTURE-EVOLUTION.md)

---

## 1. 暴露接口

### BOS URI

- `bos://ecos/*`
- `bos://meta/discover`
- `bos://memory/vault/search`

### 入口

- **CLI**: `ecos-ssb, ecos-dashboard, ecos-scheduler` 
- **MCP stdio**: `src/ecos/mcp_server.py` ~19 tools
- **HTTP**: `ecos-dashboard` :9090
- **Tools**: `mof-validate, mof-derive, mof-bridge-sync, ...` 

## 2. 上游依赖

- agora (I0)

## 3. 下游影响

- omo
- metaos
- kairon
- runtime
- model-driven

## 4. 配置 / SSOT

- 项目源码：`projects/ecos/`
- 入口定义：`projects/ecos/pyproject.toml` 或 `package.json`
- 测试：`cd projects/ecos && uv run pytest tests/ -q`
