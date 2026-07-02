# runtime — System Boundary

> 本文档描述 runtime 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 暴露接口

### BOS URI

- `bos://capability/runtime/health`
- `bos://runtime/health`
- `bos://capability/agent-runtime/execute`

### 入口

- **CLI**: `runtime / ecos-matrix-scheduler` 
- **MCP stdio**: `runtime.mcp_server` MCP tools (见 project-registry.yaml: runtime)
- **HTTP**: `cron_service/server.py` :7450

## 2. 上游依赖

- agora (I0)
- ecos (L0 protocols)

## 3. 下游影响

- gbrain
- omo

## 4. 配置 / SSOT

- 项目源码：`projects/runtime/`
- 入口定义：`projects/runtime/pyproject.toml` 或 `package.json`
- 测试：`cd projects/runtime && make test`

## 架构演进与项目边界索引

参见工作区架构演进与项目边界：[`../../docs/ARCHITECTURE-EVOLUTION.md`](../../docs/ARCHITECTURE-EVOLUTION.md)
