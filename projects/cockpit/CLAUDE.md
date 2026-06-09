# CLAUDE.md — Cockpit 统一驾驶舱

> eCOS v5 L3 Entry Layer — 用户/Agent 的唯一交互面 · CLI 23 子命令 + MCP 20 tools + Web Dashboard

---

## 项目身份

cockpit 是 eCOS v5 7 层架构的 **L3 入口层**。所有用户和 AI Agent 通过 cockpit 与系统交互。

**核心职责**：
1. **CLI 驾驶舱** — `cockpit`/`workspace` 23 个子命令
2. **MCP Server** — 20 个工具暴露给 Agora Mesh
3. **Web Dashboard** — FastAPI + 基础认证 (:8090)
4. **Agent Runtime 桥接** — 通过 runtime 调度 executor 引擎

---

## 架构

### 请求路径

```
用户/Agent
  │
  ▼
cockpit CLI ("cockpit research ...")
  │
  ├─► cli.py (argparse 路由 → 23 子命令)
  │     │
  │     ├─► commands/research.py (1257 行, 最大模块)
  │     │     └─► storage.py (SQLite IDataAccess Protocol)
  │     │
  │     ├─► commands/status.py (健康概览)
  │     ├─► commands/contracts.py (契约管理)
  │     ├─► commands/quickstart.py (环境检测)
  │     └─► commands/bos.py (BOS URI 操作, 依赖 agora)
  │
  └─► cockpit-mcp (stdio MCP Server)
        └─► 20 tools → Agora Mesh
```

### 核心模块

| 模块 | 行数 | 职责 |
|------|------|------|
| `cli.py` | 520 | 主 CLI 入口, argparse 路由 23 子命令 |
| `storage.py` | 800 | SQLite 持久化, IDataAccess Protocol |
| `dashboard_server.py` | 658 | FastAPI Web Dashboard, 可选 Bearer 认证 |
| `commands/research.py` | 1257 | 研究管线 (ask/audit/backup/compare/digest/dossier/publish/...) |
| `commands/status.py` | 719 | 项目健康概览 |
| `commands/base.py` | 423 | CLI 基类 (help, error 格式化) |
| `commands/contracts.py` | 366 | 契约验证/列表/导出 |
| `agent_runtime_server.py` | 199 | Agent Runtime HTTP 服务 |
| `agent_runtime_mcp_server.py` | 141 | Agent Runtime MCP Server |
| `l0_mcp_tools.py` | 205 | L0 MCP 工具集 |
| `data_index.py` | 230 | 数据目录索引/类型注册 |
| `scripts/cockpit_mcp.py` | 566 | Cockpit MCP Server (20 tools) |

---

## 快速命令

```bash
cd projects/cockpit

# 测试 (567 tests)
uv run pytest src/cockpit/tests/ -q

# 单个测试
uv run pytest src/cockpit/tests/test_cli_main.py -q

# 按关键字
uv run pytest src/cockpit/tests/ -k "research" -q

# 安装
uv sync
```

---

## CLI 命令清单

| 命令 | 说明 |
|------|------|
| `cockpit research` | 研究管线 (ask/audit/digest/dossier/publish/...) |
| `cockpit status` | 项目健康概览 |
| `cockpit dashboard` | 启动 Web Dashboard |
| `cockpit contracts` | 契约管理 (validate/list/export) |
| `cockpit data` | 数据管理 (index/types/gc) |
| `cockpit quickstart` | 快速初始化环境 |
| `cockpit profile` | 用户画像 |
| `cockpit mcp` | MCP 状态 |
| `cockpit governance` | 治理检查 |
| `cockpit code` | 代码分析 |
| `cockpit workflow` | 工作流管理 |
| `cockpit bos` | BOS URI 操作 |
| `cockpit events` | 事件流 |
| `cockpit import` | 数据导入 |
| `cockpit health` | 健康检查 |
| `cockpit version` | 版本信息 |

---

## GPTCHAS

1. **仅 `uv run pytest src/cockpit/tests/` 有效** — 测试在 src/ 内，`uv run pytest tests/` 路径不对
2. **runtime 是硬依赖** — `agent_runtime_*` 模块直接 import `runtime.executor.*`
3. **Web Dashboard 有可选 Bearer 认证** — `cockpit dashboard_server.py` 中的 `AUTH_TOKEN` 环境变量控制
4. **storage.py 使用 IDataAccess Protocol** — 修改存储层时需更新 `get_data_access()` 实现
5. **Python 3.13+** — 与 kairon 一致
6. **hatchling 构建** — 与 kairon/agora 一致，与 runtime 的 setuptools 不同
