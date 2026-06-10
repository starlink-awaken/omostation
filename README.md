# runtime — eCOS Runtime Layer (L1)

> L1 服务注册、健康监控与协议管理 · 5+3+1 架构运行时底座

[![Tests](https://img.shields.io/badge/tests-184-blue)](tests/)
[![Python](https://img.shields.io/badge/python-3.13+-blue)](pyproject.toml)

---

## 架构定位

```
L3 入口层  ── cockpit
I0 织层    ── agora
L2 引擎面  ── kairon / gbrain / omo / metaos
L1 运行时  ── **runtime** (Matrix + Scheduler + KEI Sandbox)  ← 你在这里
L0 协议    ── ecos
```

## 核心能力

| 子系统 | 入口 | 说明 |
|--------|------|------|
| **Matrix** | `runtime matrix` | 服务注册表，管理 L0-I0-L1-L2 全层服务 |
| **Scheduler** | `ecos-matrix-scheduler` | 持续健康监控 (15s 间隔) + 自动愈合 |
| **KEI Sandbox** | `kei.py` / `kei_sandbox.py` | 运行时沙箱，`sys.addaudithook` 拦截文件/网络/子进程 |
| **MCP Server** | `mcp_server.py` | FastMCP stdio 模式，7 个核心工具 |
| **Cron Service** | `cron_service/` | FastAPI HTTP 调度服务，SQLite 持久化 |
| **Executor** | `executor/` | 多 Agent 编排引擎 (DAG + DSL + Swarm) |
| **Event Bus** | `ecos-bus-consumer` | Agora 事件总线消费者，对接 gbrain |

## 快速开始

```bash
# 安装
cd projects/runtime && make install

# 运行测试 (184 用例)
make test

# 格式化与检查
make fmt && make lint

# 运维命令
make sync-state     # 同步脚本到 ~/runtime/
make shellcheck     # Shell 脚本检查
make clean          # 清理构建产物
make info           # 项目信息摘要
```

## CLI 命令

```bash
runtime health                    # 当前项目健康度
runtime matrix list               # 列出所有服务
runtime matrix get <name>         # 查看服务详情
runtime service start <name>      # 启动服务
runtime service stop <name>       # 停止服务
runtime service status            # 全部服务状态
runtime protocol list             # 协议列表
runtime protocol get <name>       # 协议详情
runtime status                    # 运行状态总览
runtime version                   # 版本信息
runtime i0 status                 # I0 Fabric 状态
runtime i0 services               # I0 服务列表
runtime i0 events                 # I0 事件流
runtime i0 protocols              # I0 协议
runtime i0 graph                  # I0 拓扑图
```

## 守护进程

```bash
ecos-matrix-scheduler    # Matrix 调度器 (持续健康监控 + 自动愈合)
ecos-bus-consumer        # Agora 事件总线消费者
```

## 源码结构

```
src/runtime/
├── cli.py              # 主 CLI (16KB, 7 个子命令)
├── cli_i0.py           # I0 Fabric CLI
├── i0.py               # I0 查询集成面 (Agora SSE)
├── matrix.py           # 服务注册表 (ServiceEntry dataclass)
├── scheduler.py        # Matrix 调度器 (健康监控 + 自愈)
├── protocol.py         # L0 协议注册表
├── mcp_server.py       # FastMCP stdio (7 tools)
├── runtime_serve.py    # BOS URI 派发
├── bus_consumer.py     # Agora 事件消费者
├── kei.py              # KEI 沙箱规范定义
├── kei_sandbox.py      # KEI 运行时沙箱实现
├── kei_service_registration.py  # KEI 服务注册验证
├── state_schema.py     # 状态 Schema 验证
├── taskobject_adapter.py  # TaskObject 适配器
├── cron_service/       # Cron 调度服务 (13 文件)
├── executor/           # Agent 编排引擎 (100+ 文件)
│   ├── engine.py       # AgentRuntime 核心引擎
│   ├── orchestrator.py # DAG 任务编排 (8 Phase)
│   ├── dsl.py          # DSL 系统 (YAML/JSON)
│   ├── swarm.py        # Swarm 协议
│   └── ...
├── tools/              # MCP 工具集 (6 文件)
│   ├── matrix_tools.py
│   ├── protocol_tools.py
│   ├── kei_tools.py
│   ├── i0_tools.py
│   └── task_tools.py
└── __main__.py         # python -m runtime
```

## 协议定义

`protocols/` 目录包含 5 个协议文件:
- `L0-registry.yaml` — L0 协议注册表 (SSOT)
- `ecos-meta-model.yaml` — 元模型
- `ecos-ontology.yaml` — 本体定义
- `governance-constraints.yaml` — 治理约束
- `kei-extensions.yaml` — KEI 扩展

## 依赖

| 依赖 | 用途 |
|------|------|
| apscheduler | Cron 调度 |
| croniter | Cron 表达式解析 |
| fastapi + uvicorn | HTTP API |
| fastmcp | MCP 协议 |
| httpx | HTTP 客户端 |
| pydantic | 数据模型 |
| pyjwt | JWT 认证 |
| aetherforge-gateway | LLM 网关 |
