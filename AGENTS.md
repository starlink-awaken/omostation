# AGENTS.md — Cockpit Development Guide

> eCOS v5 L3 Entry Layer · CLI + MCP + Web

## Quick Commands

```bash
cd projects/cockpit

# 全量测试 (567 tests)
uv run pytest src/cockpit/tests/ -q

# 单模块测试
uv run pytest src/cockpit/tests/test_cli_main.py -q
uv run pytest src/cockpit/tests/test_cli_research_*.py -q
uv run pytest src/cockpit/tests/test_storage_*.py -q

# 关键字筛选
uv run pytest src/cockpit/tests/ -k "research" -q

# 格式化
uv run ruff format src/cockpit/

# 检查
uv run ruff check src/cockpit/

# 安装
uv sync
```

## Architecture

### 模块分层

```
L3 Cockpit
├── CLI 入口        ← cli.py (argparse dispatch → 30+ subcommands)
│   └── commands/   ← research, status, contracts, cards, mcp, ssb, mof, iterate, ...
├── MCP Server      ← scripts/cockpit_mcp.py + l0_mcp_tools.py (37+ tools, stdio)
├── Agent Runtime   ← agent_runtime_mcp_server.py (2 tools, stdio)
├── Web Dashboard   ← src/cockpit/dashboard_server.py (FastAPI, :8090) — 唯一人机交互入口 (注意：web/app.py 已废弃)
│   ├── /api/*      ← 38 API routes (services/compute/health/events/research/a2a/knowledge/...)
│   ├── /api/v1/proposals/* ← [Phase 9] HITL 审批队列 (approve/reject)
│   ├── /api/knowledge/search ← 全域聚合搜索接口 (BOS memory/local/all-search)
│   ├── /api/omo/*  ← 6 OMO governance routes (status/debt/report/healing/*)
│   ├── /api/ecos/* ← 3 eCOS routes (status/ssb/watchdog)
│   ├── /api/runtime/status ← L1 runtime matrix state
│   ├── /api/metaos/status  ← L2 metaos workflow engine
│   ├── /api/l4kernel/status ← L4 self-layer capabilities
│   ├── /dev/*      ← 4 kairon debug routes (kos/minerva/ontoderive/forge)
│   ├── /hermes/*   ← hermes-console React UI (static files)
│   └── /dash/*     ← dashboard_server.py sub-app (governance data)
├── Agent Runtime   ← agent_runtime_cli.py/server.py/mcp_server.py
└── Storage         ← storage.py (SQLite + IDataAccess Protocol)
```

### 数据流

```
CLI → cli.py → commands/<cmd>.py → storage.py (SQLite)
                                    ├→ runtime (executor 调度)
                                    ├→ omo (dashboard 数据)
                                    └→ agora (BOS URI 路由)
```

### CLI 路由映射

| 命令 | 函数 | 文件 |
|------|------|------|
| `cockpit research` | `cmd_research_*()` | commands/research.py |
| `cockpit status` | `cmd_status()` | commands/status.py |
| `cockpit contracts` | `cmd_contracts_*()` | commands/contracts.py |
| `cockpit quickstart` | `cmd_quickstart()` | commands/quickstart.py |
| `cockpit dashboard` | `cmd_dashboard()` | cli.py → dashboard_server.py |
| `cockpit data` | `cmd_data_*()` | commands/data.py |
| `cockpit code` | `cmd_code()` | commands/code.py |
| `cockpit bos` | `cmd_bos()` | commands/bos.py |
| `cockpit ssb` | `cmd_ssb()` | commands/ssb.py (委派 ecos-ssb) |
| `cockpit mof` | `cmd_mof()` | commands/mof.py (委派 mof CLI) |
| `cockpit iterate` | `cmd_iterate()` | commands/iterate.py (C2G 双擎编排流) |

### CLI Convergence (2026-06-11)

Cockpit = **sole human-facing CLI entry point**. Other CLIs (`agora`, `runtime`, `ecos-ssb`, `omo`, `metaos`) remain as internal/programmatic API only, not for direct human use.

**Wrapped CLIs:**
- `workspace ssb <args>` → delegates to `ecos-ssb`
- `workspace mof <args>` → delegates to `mof` CLI (ecos)

**Thin wrapper pattern:** `subprocess.run()` to the underlying CLI module. Wrappers live in `commands/ssb.py` and `commands/mof.py`. Easy to expand as needed.

## Key Dependencies

- **runtime** — executor 引擎、Matrix 注册表
- **omo** — 债务注册表 (dashboard 引用)
- **agora** — BOS URI 路由 (bos 命令)
- **rich** — CLI 美化输出
- **FastAPI + uvicorn** — Web Dashboard

## Testing Pattern

```bash
# 测试目录在 src/cockpit/tests/ (非根目录 tests/)
uv run pytest src/cockpit/tests/ -q

# P0 覆盖 (agent_runtime_*)
uv run pytest src/cockpit/tests/test_agent_runtime_*.py -q

# Storage 层
uv run pytest src/cockpit/tests/test_storage_*.py -q

# Research 管线
uv run pytest src/cockpit/tests/test_cli_research_*.py -q
```

## File Organization

- `src/cockpit/` — 源码 (28+ .py 文件)
- `src/cockpit/commands/` — CLI 子命令 (28 文件)
- `src/cockpit/scripts/` — MCP Server
- `src/cockpit/tests/` — 测试 (50 文件, 575 tests)
- `tests/` — 根级测试 (conftest.py + test_basic.py)

## Gotchas

1. **Python 3.13+** — 与 kairon 一致
2. **测试路径是 src/cockpit/tests/** — 不要在根目录 tests/ 放测试
3. **runtime 是硬依赖** — agent_runtime_* 模块需要 runtime 可导入
4. **storage.py IDataAccess Protocol** — 新增存储操作需实现协议接口
5. **Web Dashboard 认证可选** — AUTH_TOKEN 环境变量控制
6. **hatchling 构建** — 与 kairon/agora/runtime 一致
7. **`cockpit iterate` 非交互回退** — 无 TTY 时 `Confirm.ask` 抛 EOFError，默认走标准 C2G 流而非 Fast-Track
8. **L4 全域 8 域** — cockpit_mcp.py 注册 cards/vault/personal/public/creative/family/workdocs/opc

## Workspace-Wide Governance (2026-06-24)

This project follows the workspace-level governance conventions documented in the root `AGENTS.md`:

- **Agent Mutation Protocol**: Any autonomous agent/cron/daemon that modifies workspace state must emit `agent_mutation_intent`, avoid direct file I/O to `.omo/`/`spaces/`, and commit immediately. See `.omo/standards/agent-mutation-protocol.md` for the full protocol.
- **SSOT Guardian**: Run `python3 bin/ssot-guardian.py` from the workspace root before committing to detect task-count, current-wave, submodule-pointer, or direct-omo-io drift.
- **direct-omo-io**: Scripts must route writes to `.omo/` through `omo CLI`, `projects/omo` core, or `projects/c2g` ingress — never via raw `open()/mkdir()/write_text()`.
- **Submodule Governance**: Commit changes inside the submodule first, then bump the root-repo pointer; `git submodule status` with a `+` prefix indicates pending drift.
