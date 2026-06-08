# CLAUDE.md — Runtime 运行时底座

> eCOS v5 L1 Runtime Layer · Matrix + Scheduler + KEI Sandbox + Executor

---

## 项目身份

runtime 是 eCOS v5 7 层架构的 **L1 运行时基础设施**。所有服务的注册、健康监控、沙箱执行和协议管理都由 runtime 承载。

**核心职责**：
1. **Matrix 服务注册** — YAML 驱动, 环境变量 + launchd 标签
2. **Scheduler 健康监控** — 15s 心跳, 自动愈合 (auto-heal)
3. **KEI 沙箱** — `sys.addaudithook` 运行时权限控制
4. **Cron Service** — FastAPI HTTP 调度, SQLite 持久化
5. **Executor 引擎** — AgentRuntime + DAG 编排 + DSL

---

## 子系统架构

```
L1 Runtime
├── Matrix         ← matrix.py (ServiceEntry: name/type/status/port)
│   └─ 读取 ~/runtime/matrix.yaml
├── Scheduler      ← scheduler.py (15s 心跳 + auto_heal)
│   └─ 写入 matrix_state.json + OMO_STATE_FILE
├── Protocol       ← protocol.py (L0 协议注册, 7 category)
│   └─ 读取 protocols/L0-registry.yaml
├── KEI            ← kei.py + kei_sandbox.py
│   └─ sys.addaudithook → JSONL 审计日志
├── Cron Service   ← cron_service/ (13 files)
│   └─ FastAPI + MCP + SQLite
├── Executor       ← executor/ (100+ files)
│   ├─ engine.py   — AgentRuntime (LLM → tools → result)
│   ├─ orchestrator.py — DAG 任务编排 (8 Phase)
│   ├─ dsl.py      — YAML/JSON DSL
│   └─ swarm.py    — Swarm 蜂群协议
├── MCP Server     ← mcp_server.py (7 tools, stdio)
├── Event Bus      ← bus_consumer.py (Agora SSE → SQLite → gbrain)
└── Tools          ← tools/ (5 工具组: matrix/protocol/kei/i0/task)
```

---

## 健康监控节奏

```
scheduler.py (每 15 秒)
  │
  ├─ 读取 ~/runtime/matrix.yaml
  ├─ 扫描 /Library/LaunchDaemons/ (launchd 检查)
  ├─ 检测过时 → auto_heal_enabled → launchctl 重启
  ├─ 写入 matrix_state.json (新鲜度分数)
  └─ 写入 OMO_STATE_FILE (债务注册)
```

---

## KEI 沙箱安全模型

```
KEI Manifest (kei.yaml)
  │
  ▼
sys.addaudithook (Python C-level hook)
  │
  ├─ 拦截: subprocess.Popen / socket.connect / open
  ├─ 规则: fs_read/write, network_hosts, shell_exec, env_vars
  ├─ 默认: 仅 localhost, workspace r/w, 禁止子进程
  └─ 审计: JSONL 日志 (递归保护 _IN_AUDIT)
```

---

## 快速命令

```bash
cd projects/runtime

# 测试 (184 tests)
make test

# 单个测试
uv run pytest tests/test_executor_engine.py -v

# 格式化 + 检查
make fmt && make lint

# 运维
make sync-state     # 同步脚本到 ~/runtime/
make shellcheck     # Shell 检查
make clean          # 清理
make info           # 信息摘要
```

---

## GPTCHAS

1. **Python 3.10+** — 非 kairon 的 3.13+, 与 cockpit 同级
2. **setuptools 构建** — 唯一使用 setuptools 的项目 (其他都是 hatchling)
3. **KEI 沙箱是全局的** — `sys.addaudithook` 影响整个 Python 进程
4. **Matrix 数据在 ~/runtime/ 不在项目目录** — matrix.yaml 是 SSOT
5. **Executor 最复杂** — 100+ 文件, 修改前先读 engine.py 入口
6. **Cron Service 有独立 MCP** — cron_service/mcp_server.py (Hermes), 不同于主 mcp_server.py
7. **Scheduler 写状态文件** — matrix_state.json + OMO_STATE_FILE, SOTI 健康分
8. **bus_consumer 需要 JWT** — AGORA_JWT_TOKEN 环境变量
