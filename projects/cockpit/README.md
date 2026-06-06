# Cockpit — L3 统一入口 (统一研究驾驶舱)

> 5+3+1 架构 L3 层 · Agent 桥接 · CLI + MCP + Web
> `projects/cockpit/` · 498 tests

## 接口

| 接口类型 | 入口 | 说明 |
|---------|------|------|
| CLI | `cockpit`, `workspace` | 18 子命令 (context/cards/vault/health/brief + research/status/code/...) |
| MCP | `cockpit-mcp` | 20 个工具 (research_* × 15 + status_* × 2 + L4 bridge × 4) |
| Web | `dashboard_server.py` | stdlib http, I0 状态面板 |

## MCP Server 配置 (SSOT)

**所有 Agent 共用此配置。** 添加到 MCP client 配置中：

```json
{
  "mcpServers": {
    "cockpit": {
      "command": "uv",
      "args": ["run", "--package", "cockpit", "cockpit-mcp"]
    }
  }
}
```

或直接运行: `uv run --package cockpit python -m cockpit.scripts.cockpit_mcp`

## MCP 工具清单

### L4 Bridge (Agent 启动第一步)
| 工具 | 说明 |
|------|------|
| `workspace_context` | ★ 聚合 OMO 阶段 + CARDS + 约束 + next_guidance |
| `cards_status` | 活跃卡片, 按优先级排序 |
| `cards_check` | 操作前约束合规验证 |
| `vault_search` | L4 Vault 知识检索 |

### Research (研究管理)
`research_list`, `research_search`, `research_create`, `research_open`, `research_ask`, `research_archive`, `research_restore`, `research_tag`, `research_rename`, `research_dossier`, `research_half_life`, `research_agent_list`

### Status (状态查询)
`status_summary`, `status_json`, `daily_summary`

## 测试

```bash
uv run --package cockpit pytest src/cockpit/tests/ -q
# 498 passed
```

## 架构位置

```
L4 (知识面) → cockpit MCP bridge → Agent 获取上下文
L3 (工具面) → cockpit CLI + MCP + Web
I0 (织层)  → Agora 路由 L2 调用
```
