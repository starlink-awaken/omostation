# gbrain — System Boundary

> 本文档描述 gbrain 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 暴露接口

### BOS URI

- `bos://memory/gbrain/query`
- `bos://memory/gbrain/search`
- `bos://memory/gbrain/sync`
- `bos://persona/sharedbrain-bridge/recall`

### 入口

- **CLI**: `gbrain` src/cli.ts
- **MCP stdio**: `gbrain serve` src/mcp/server.ts
- **MCP HTTP**: `gbrain serve --http` OAuth 2.1

## 2. 上游依赖

- agora (I0)
- kairon (L2)
- runtime (L1 bus consumer)

## 3. 下游影响

- cockpit
- omo
- family-hub

## 4. 配置 / SSOT

- 项目源码：`projects/gbrain/`
- 入口定义：`projects/gbrain/pyproject.toml` 或 `package.json`
- 测试：`cd projects/gbrain && bun test`

## 架构演进与项目边界索引

参见工作区架构演进与项目边界：[`../../docs/ARCHITECTURE-EVOLUTION.md`](../../docs/ARCHITECTURE-EVOLUTION.md)
