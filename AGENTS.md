# AGENTS.md — Runtime Development Guide

> eCOS Runtime Layer (L1) — 服务注册、健康监控、协议管理与编排引擎

## Quick Commands

```bash
# 测试
make test                    # 全量测试 (175 cases)
pip install -e . && pytest tests/ -v  # 直接运行

# 格式化与检查
make fmt                     # ruff format src/
make lint                    # ruff check + format check
make shellcheck              # Shell 脚本检查

# 运维
make install                 # pip install -e .
make clean                   # 清理构建产物
make sync-state              # 同步脚本到 ~/runtime/
make info                    # 项目信息摘要
```

## Architecture

### 子系统分层

| 子系统 | 核心文件 | 职责 |
|--------|---------|------|
| CLI | `cli.py` (+ `cli_i0.py`) | 主命令行入口，7 子命令 |
| Matrix | `matrix.py` | 服务注册表 (ServiceEntry: name/type/status/port) |
| Scheduler | `scheduler.py` | 持续健康监控 (15s) + 自动愈合 (autoheal) |
| Protocol | `protocol.py` | L0 协议注册 (ProtocolEntry: 7 category) |
| MCP | `mcp_server.py` | FastMCP stdio (7 tools) |
| Runtime Serve | `runtime_serve.py` | BOS URI 派发 (4 actions) |
| Event Bus | `bus_consumer.py` | Agora SSE 事件消费 + SQLite 持久化 |
| KEI | `kei.py` + `kei_sandbox.py` | 沙箱权限 + audit hook；FS mutation hooks (`os.remove`/`os.unlink`/`os.rename`/`os.mkdir`/`os.rmdir`) 受 `allow_write` 前缀约束，`os.rename` 同时校验 source 与 destination |
| Cron Service | `cron_service/` (13 files) | FastAPI + SQLite 调度 |
| Executor | `executor/` (100+ files) | AgentRuntime + DAG DSL + Swarm |
| Tools | `tools/` (6 files) | MCP 工具注册 (5 工具组) |
| I0 | `i0.py` | Agora fabric 查询集成面 |

### 数据流

```
CLI / MCP → cli.py / mcp_server.py
              ↓
           matrix.py (读 ~/runtime/matrix.yaml)
           protocol.py (读 protocols/L0-registry.yaml)
              ↓
           scheduler.py (持续轮询 15s → matrix_state.json)
           bus_consumer.py (Agora SSE → SQLite → gbrain)
```

### CLI 路由映射

| 命令 | 函数 | 文件 |
|------|------|------|
| `runtime health` | `_cmd_health()` | cli.py |
| `runtime matrix list/get/resolve` | 委托 matrix_tools | cli.py → tools/ |
| `runtime service start/stop/status` | `_cmd_service_*()` | cli.py |
| `runtime protocol list/get` | 委托 protocol_tools | cli.py → tools/ |
| `runtime status` | `_cmd_status()` | cli.py |
| `runtime version` | `_cmd_version()` | cli.py |
| `runtime i0 *` | 委托 i0.py | cli_i0.py → i0.py |

## Key Dependencies

- **apscheduler + croniter** — Cron 表达式解析与调度
- **fastapi + uvicorn** — HTTP API (Cron Service)
- **fastmcp** — MCP stdio 服务端
- **httpx** — Agora SSE 客户端
- **pydantic** — 数据模型定义
- **pyjwt** — JWT 认证 (Event Bus)
- **aetherforge-gateway** — LLM 网关 + X2 预算治理拦截

## Governance (X2)

Agent 执行任务（run_task）受全系统 **X2 Budget Policy** 约束：
1. **事前拦截**: 任务启动前预估 Token 消耗，余额不足时自动熔断。
2. **实时扣减**: 任务完成后，真实消耗自动写入 `llm_quota_ledger.jsonl`，同步 SSOT 账本。
3. **自愈信号**: 预算耗尽时自动生成 OMO Debt，触发 Evolution Loop。


## Testing Pattern

```bash
# 全量
make test

# 单个文件
pytest tests/test_matrix.py -v

# 按关键字
pytest tests/ -k "scheduler" -v

# 集成测试
pytest tests/integration/ -v
```

## Gotchas

1. **Python 3.10+** — 非 3.13+，与 kairon 的 Python 要求不同
2. **setuptools 构建** — 非 hatchling，与 kairon/agora 不同
3. **Matrix 数据路径** — `~/runtime/matrix.yaml`，不在项目目录内
4. **Scheduler 写状态文件** — `matrix_state.json` + `OMO_STATE_FILE`
5. **KEI 沙箱是全局的** — `sys.addaudithook` 影响整个进程
6. **Executor 是最复杂子系统** — 100+ 文件，修改前先读 `executor/engine.py` 入口
7. **Cron Service 有独立 MCP** — `cron_service/mcp_server.py` (Hermes 集成)，不同于主 `mcp_server.py`
   - 默认 stdio 模式，`--http` 启用 HTTP API 服务

## File Organization

- `src/runtime/` — 核心源码 (112 .py 文件)
- `src/runtime/cron_service/` — Cron 调度服务 (13 文件)
- `src/runtime/executor/` — Agent 编排引擎 (100+ 文件)
- `src/runtime/tools/` — MCP 工具集 (6 文件)
- `tests/` — 测试 (10 文件, 175 用例)
- `protocols/` — 协议定义 (5 YAML 文件)
- `scripts/` — 运维脚本 (15 Shell/Python)
- `build/` — 构建产物


## Bus foundation (跨仓依赖)

本项目通过 `runtime_bus_adapter.py` 接入 [bus-foundation](https://github.com/starlink-awaken/omostation/tree/main/projects/bus-foundation) (R66 独立仓):

```python
from bus_foundation import publish, subscribe, schedule, BusEnvelope
```

- **Public API**: `publish` / `subscribe` / `schedule` / `BusEnvelope` / `EventType`
- **零 agora 依赖**: bus-foundation 是 standalone Python package
- **公共 API 冻结 6 月** (从 2026-06-12 起)
- **L0 协议层提升**: 评估 R70-R72, 决策 **Path C: Defer Indefinitely** (见 `projects/bus-foundation/docs/ADR-0003-no-l0-promotion.md`)
- **修改 bus-foundation**: 提 PR 到 `projects/bus-foundation/`, 改完跑该项目的 `uv run pytest -q` 验证

> 不要直接 import `agora.bus` (那是 backward-compat shim)。新代码用 `from bus_foundation import ...`。
