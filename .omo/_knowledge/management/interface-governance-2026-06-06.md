# 5+3+1 接口架构治理报告

> 2026-06-06 · 全量审计 · CLI/MCP/HTTP/脚本

---

## 一、CLI 入口总览 (21 scripts)

| 命令 | 项目 | 类型 |
|------|------|------|
| `agora` | agora (I0) | 35 子命令, argparse |
| `cockpit` / `workspace` | cockpit (L3) | 18 子命令, argparse + Rich |
| `workspace mcp` | cockpit | stdio/sse MCP server |
| `cockpit-mcp` | cockpit | stdio MCP server (专用入口) |
| `cockpit-dashboard` | cockpit | Web dashboard (8080) |
| `agent-runtime` | cockpit | Agent runtime CLI |
| `runtime` | runtime (L1) | matrix health/ctl |
| `ecos-matrix-scheduler` | runtime | Matrix Scheduler |
| `ecos-bus-consumer` | runtime | Event bus consumer |
| `omo` | omo (L2) | 28 子命令 |
| `omo-debt` | omo | Debt CLI |
| `cards` | omo | CARDS CLI |
| `metaos` | metaos (L2) | 5 子命令 |
| `ecos-ssb` | ecos (L0) | SSB 客户端 |
| `ecos-dashboard` | ecos | HTTP dashboard (9090) |
| `ecos-scheduler` | ecos | Scheduler |
| `ontoderive` | kairon (L2) | 本体推导 CLI |
| `minerva` | kairon | 深度研究 CLI |
| `minerva-daemon` | kairon | Minerva daemon |
| `minerva-mcp` | kairon | Minerva MCP server |
| `gbrain` | gbrain (L2) | TS CLI |

### 端口冲突分析

| 端口 | 使用者 | 冲突 |
|------|--------|------|
| **8080** | agora(aiohttp) + cockpit(dashboard) + ontoderive(web) | ⚠️ 三项目共用 |
| **9090** | ecos(dashboard) + omo(dashboard) + llm-gateway(http) | ⚠️ 三项目共用 |
| **7430** | agora(FastAPI dashboard) | ✅ 独占 |
| **7431** | agora(MCP SSE) + cockpit(MCP SSE) | ⚠️ 共用 |
| **7422** | agora(MCP HTTP) | ✅ 独占 |

### 端口治理建议

```
8080: 分配给 cockpit (L3 统一入口, 优先级最高)
       agora 已有 7430/7422/7431, ontoderive 改用环境变量
9090: 分配给 ecos (L0 dashboard, 最早使用)
       omo 改用 DASHBOARD_PORT 环境变量
7431: 分配给 agora (I0 MCP, 统一入口)
       cockpit 改为使用 cockpit-mcp (stdio)
```

## 二、MCP 工具分布

| 项目 | MCP 工具数 | 传输模式 |
|------|-----------|---------|
| agora | 42+ | stdio + HTTP(7422) + SSE(7431) |
| cockpit | 20 | stdio |
| runtime | 21 (主) + 9 (cron) | stdio |
| metaos | 11 | stdio |
| omo | 10 | stdio |
| gbrain | 67 (TS) | stdio |

Kairon 内部各包 MCP 工具均通过 Agora ProxyManager 注册，不独立暴露端口。

**总计: ~180 MCP 工具**

## 三、HTTP 端点矩阵

| 项目 | 框架 | 端口 | 端点类型 |
|------|------|------|---------|
| agora | FastMCP | :7422 | MCP HTTP (42 tools) |
| agora | FastMCP | :7431 | MCP SSE |
| agora | FastAPI | :7430 | 30+ REST (dashboard/api/metrics) |
| agora | aiohttp | :8080 | REST API gateway |
| cockpit | http.server | :8080 | 8 REST (context/cards/status/debt) |
| runtime | FastAPI | dynamic | 5 REST (cron health/jobs) |
| ecos | http.server + jinja2 | :9090 | HTML dashboard |
| omo | http.server (基础) | :9090 | HTML dashboard |
| ontoderive | ? | :8080 | Web server |
| llm-gateway | http.server | :9090 | HTTP server |

## 四、临时脚本清单

### 驾驶舱 (~/Documents/驾驶舱/scripts/)

| 脚本 | 功能 |
|------|------|
| `ecos-bootstrap.py` | CLI 封装, 提供 ecos health/brief/list/deploy 等 |
| `ecos-brief.py` | 会话简报生成 |
| `ecos-daemon.py` | 守护进程 (Python v3.0) |
| `ecos-health-check.py` | 全系统健康检查 |
| `ecos-constraint-compiler.py` | 约束编译器 |
| `ecos-entry-logger.py` | 入口日志记录 |
| `check-claude-freshness.py` | CLAUDE.md 保鲜检查 |
| `x3-coverage-report.py` | X3 覆盖率报告 |

### 项目 scripts/

| 项目 | 脚本 |
|------|------|
| ecos/scripts/ | daily_digest, knowledge_gap, research_push, ssb_integrity |
| runtime/scripts/ | validate_meta_model, check_services_down, verify_kei_audit, check_stale_debts |
| omo/scripts/ | omo_audit, generate_dashboard, update_debt_freshness, omo_debt, check_freshness, omo_cost, sync_omo_state |

## 五、治理建议

### 立即 (P0)
1. **端口冲突**: 8080(3项目) 和 9090(3项目) → 按优先级分配并统一环境变量
2. **脚本收敛**: ecos-bootstrap CLI 功能已收敛到 cockpit, 废弃旧壳

### 短期 (P1)
3. **MCP 入口统一**: 所有 MCP → Agora ProxyManager 注册, 仅 cockpit/agora 暴露公共入口
4. **驾驶舱脚本**: 7 个 CLI 工具规范化 → cockpit 子命令或独立 entry point

### 长期 (P2)
5. **HTTP 框架统一**: http.server → FastAPI (runtime 已先行)
6. **端口注册表**: L0 protocols/ 下新增 port-registry.yaml SSOT
