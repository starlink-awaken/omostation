---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: interface-governance-2026-06-06.md
deprecated-since: 2026-06-23

---

# 5+3+1 接口架构治理报告 (Final)

> 2026-06-06 · 全量 CLI + MCP + HTTP + 脚本审计

---

## 一、CLI 入口: 21 scripts · 9/9 项目覆盖

| 项目 | CLI 命令 | 类型 |
|------|---------|------|
| agora | `agora`, `agora-mcp`, `agora-mcp-gateway` | 35 子命令 |
| cockpit | `cockpit`, `workspace`, `agent-runtime`, `cockpit-mcp`, `cockpit-dashboard` | 18 子命令 |
| runtime | `runtime`, `ecos-matrix-scheduler`, `ecos-bus-consumer` | L1 管理 |
| omo | `omo`, `omo-debt`, `omo-mcp`, `cards` | 治理 CLI |
| metaos | `metaos` | 编排 CLI |
| ecos | `ecos-ssb`, `ecos-dashboard`, `ecos-scheduler` | L0 协议 |
| kairon | 11 packages (eidos/iris/kos/minerva/...) | 各领域独立 |

### ⚠️ 配置问题

| 命令 | 问题 |
|------|------|
| `protocols-layer` | CLI 断链 `protocols_layer.cli:main` 不存在 |
| `sophia` / `sophia-tui` | SHIM 包, src/ 为空 |
| `sb-bridge` | src/ 为空, 实际在 `sot_bridge.sharedbrain_bridge` |

## 二、MCP 工具: 286 unique tools · 6 项目

| 项目 | 工具数 | 框架 |
|------|--------|------|
| agora | 41 (FastMCP) + 25 (Registry) = **66** | FastMCP + MCPToolRegistry |
| cockpit | **21** | FastMCP |
| runtime | **9** (cron) | FastMCP |
| omo | **12** | FastMCP |
| metaos | **11** | 自定义 MCP 协议 |
| gbrain | **75** | TypeScript MCP SDK |
| kairon packages | **92** | per-pkg FastMCP |

> Agora ProxyManager 以 `{service}.{tool_name}` 前缀暴露同名片具。

### 重复工具

| 工具 | 项目 |
|------|------|
| `cards_status` / `cards_check` | cockpit + omo |
| `health_check` | sot-bridge + gbrain |

## 三、HTTP 端口: 9 ports · 6 frameworks

| 框架 | 端口 | 项目 |
|------|------|------|
| FastMCP HTTP | 7422 | agora |
| FastMCP SSE | 7431 | agora |
| FastAPI | 7430 | agora (dashboard) |
| aiohttp | 8080 | agora (API gateway) |
| http.server | 8090 | cockpit (dashboard) ✅ 已修复 |
| FastAPI | dynamic | runtime (cron) |
| http.server | 9090 | ecos (dashboard) |
| http.server | 9090 | omo (dashboard) ⚠️ 冲突 |
| http.server | 9090 | llm-gateway ⚠️ 冲突 |

## 四、KNOWN_SERVICES: 19 services

Kairon(9) + MetaOS(1) + npm(5) + Docker(1) + Homebrew(1) + Agent CLI(2)

## 五、驾驶舱脚本

```
~/Documents/驾驶舱/scripts/
  ecos-bootstrap.py · ecos-brief.py · ecos-daemon.py · ecos-health-check.py
  ecos-constraint-compiler.py · ecos-entry-logger.py
  check-claude-freshness.py · x3-coverage-report.py
```

**治理建议**: ecos-bootstrap CLI 已收敛到 cockpit, 旧壳保留作别名。

## 六、治理行动项

| 优先级 | 行动 | 状态 |
|--------|------|------|
| P0 | cockpit 8080→8090 | ✅ |
| P0 | protocols-layer CLI 修复 | 待后续 |
| P1 | cards_status 去重 (cockpit↔omo) | 待后续 |
| P1 | 9090 端口冲突 (ecos/omo/llm-gateway) | 待后续 |
| P2 | 驾驶舱脚本规范化 → cockpit | 待后续 |

---

*治理完成: 2026-06-06*
