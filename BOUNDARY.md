# omo — System Boundary

> 本文档描述 omo 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。

---

## 1. 暴露接口

### BOS URI

- `bos://governance/omo/state`
- `bos://governance/omo/debt`
- `bos://governance/omo/audit`
- `bos://governance/omo/inspect`
- `bos://governance/omo/sync`

### 入口

- **CLI**: `omo` 39 子命令 (含 deprecated bridge/strategy)
- **CLI**: `omo-debt` / `cards`
- **MCP stdio**: `omo-mcp` 19 tools
- **SSE daemon**: `omo-sse-daemon`

## 2. 上游依赖

| 项目 | 依赖方式 | 用途 |
|------|----------|------|
| agora (I0) | pyproject editable path | MCP 路由、连接池 |
| model-driven (M0) | pyproject editable path, factory 模式 | 生命周期阶段桥接 |
| bus-foundation (X) | pyproject path | Omni-Bus 适配 |
| aetherforge-gateway (X) | pyproject path | LLM 网关 |

## 3. 下游影响

| 项目 | 依赖方向 | 说明 |
|------|----------|------|
| ecos (L0) | ecos → omo (单向) | `mof-state-bridge.py` import `omo.omo_ingress` + `omo.omo_io` 做 .omo/tasks ↔ M1 同步 |
| cockpit (L3) | cockpit → omo | cockpit 调用 omo CLI/MCP 做治理操作 |
| l4-kernel (L4) | l4-kernel → omo | L4 域健康检查引用 omo 状态 |

## 4. 配置 / SSOT

- 项目源码：`projects/omo/`
- 入口定义：`projects/omo/pyproject.toml`
- 测试：`cd projects/omo && uv run pytest tests/ -q`
