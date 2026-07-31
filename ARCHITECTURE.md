# cockpit — Architecture

> **Layer**: L3 入口层  
> **Role**: 统一人类入口 / Agent 桥接层 / CLI + MCP + Web  
> **Stack**: Python 3.13+, uv, FastAPI, rich  
> **Health**: See local CI and runtime probes
> **SSOT**: 运行时健康、测试通过率、入口/工具计数以本项目 CI、运行时探针和 workspace governance SSOT 为准
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 内部架构

```mermaid

graph LR
    Human((Human))
    CLI[cockpit CLI]
    MCP[cockpit MCP]
    Web[cockpit HTTP :8090]
    Agora[agora :7431]
    L4[l4-kernel]
    L2[kairon/omo]

    Human --> CLI
    Human --> Web
    Agent -->|stdio deprecated| MCP
    CLI -->|subprocess| Agora
    Web -->|FastAPI| Agora
    MCP -->|mcp_stdio via agora| Agora
    Agora --> L2
    CLI -->|cards --check| L4

```

## 2. 入口

| Type | Entry | Port / Notes |
|:--|:--|:--|
| CLI | `cockpit / workspace` | 25+ 子命令 |
| MCP stdio | `cockpit-mcp / cockpit/scripts/cockpit_mcp.py` | ~MCP tools (见 project-registry.yaml) |
| HTTP | `cockpit-dashboard` | :8090 |

## 3. 核心模块

| Module | Responsibility |
|:--|:--|
| `src/cockpit/cli.py` | argparse CLI dispatcher |
| `src/cockpit/scripts/cockpit_mcp.py` | MCP server: research/status/L4-bridge |
| `src/cockpit/dashboard_server.py` | FastAPI Web dashboard |
| `src/cockpit/storage.py` | SQLite persistence with IDataAccess |
| `src/cockpit/commands/research.py` | Research lifecycle |
| `src/cockpit/governance/` | Cards checks / L4 bridge |

## 4. 测试

```bash
cd projects/cockpit && uv run pytest tests/ -q
```

## 架构概览

参见工作区架构概览图：[`../../docs/ARCHITECTURE-DIAGRAM.md`](../../docs/ARCHITECTURE-DIAGRAM.md)
