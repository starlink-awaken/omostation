# agora — System Boundary

> 本文档描述 agora 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 暴露接口

### BOS URI

- `bos://agora/registry`
- `bos://meta/discover`
- `bos://memory/local/all-search`

### 入口

- **CLI**: `agora` 子命令 (见 project-registry.yaml: agora)
- **MCP stdio**: `agora-mcp` 
- **SSE**: `agora-server` :7431
- **HTTP**: `agora-web` :7422 / :8080

## 2. 上游依赖

- ecos (L0 MOF/SSB)
- runtime (L1 service registry)

## 3. 下游影响

- kairon
- gbrain
- omo
- metaos
- runtime
- l4-kernel
- cockpit

## 4. 配置 / SSOT

- 项目源码：`projects/agora/`
- 入口定义：`projects/agora/pyproject.toml` 或 `package.json`
- 测试：`cd projects/agora && uv run pytest tests/ --ignore=tests/e2e -q`

## 架构演进与项目边界索引

参见工作区架构演进与项目边界：[`../../docs/ARCHITECTURE-EVOLUTION.md`](../../docs/ARCHITECTURE-EVOLUTION.md)
