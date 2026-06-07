# omostation Wiki

> 技术 Wiki — 系统架构、开发指南、运维手册
> Technical Wiki — Architecture, Development, Operations

---

## 架构 Architecture

### eCOS v5 分层架构 / 7-Layer Architecture

```
 L4  自我 Self     ── CARDS (SQLite) + 学习进化 Learning Evolution (MD)
 L3  入口 Entry     ── cockpit (CLI 13 + MCP Server + Web Dashboard)
 I0  织层 Weave     ── agora (Dynamic MCP Reverse Proxy Mesh, 42+ tools)
 L2  引擎 Engine    ── kairon (19 packages) · gbrain (67 MCP tools) · omo · metaos
 L1  运行时 Runtime  ── runtime (Matrix + Scheduler + KEI Sandbox)
 L0  协议 Protocol  ── ecos (SSB Protocol + Emergence Computation)
```

### BOS URI 五大域 / 5 BOS URI Domains

| Domain | URI Prefix | 项目 Projects |
|--------|-----------|--------------|
| memory | `bos://memory` | kos, kronos, gbrain, sot-bridge |
| governance | `bos://omo` | omo, metaos, eidos, protocols-layer |
| analysis | `bos://analysis` | ontoderive, minerva, codeanalyze |
| persona | `bos://persona` | sot-bridge (sharedbrain) |
| capability | `bos://forge` | forge, runtime (KEI) |

---

## 开发指南 Development

### 环境要求 / Requirements

- Python 3.13+ (for kairon, agora, cockpit, omo, metaos, runtime, ecos)
- Bun (for gbrain, hermes-console)
- uv (Python package manager)

### 项目安装 / Project Setup

```bash
# kairon monorepo
cd projects/kairon && uv sync

# agora MCP hub
cd projects/agora && uv sync

# cockpit unified entry
cd projects/cockpit && uv sync

# omo governance
cd projects/omo && uv sync

# metaos orchestration
cd projects/metaos && uv sync

# runtime
cd projects/runtime && uv sync

# ecos protocol
cd projects/ecos && uv sync

# gbrain (TypeScript)
cd projects/gbrain && bun install
```

### 测试运行 / Running Tests

```bash
# kairon: all 19 packages (4,199 tests)
cd projects/kairon && make test

# agora: 1,200 tests
cd projects/agora && uv run pytest tests/ --ignore=tests/e2e -q

# cockpit: 514 tests
cd projects/cockpit && uv run pytest src/cockpit/tests/ -q

# gbrain: ~9,737 tests
cd projects/gbrain && bun test

# omo: 530 tests
cd projects/omo && uv run pytest tests/ -q

# metaos: 188 tests
cd projects/metaos && uv run pytest tests/ -q

# runtime: 176 tests
cd projects/runtime && uv run pytest tests/ -q

# ecos: 122 tests
cd projects/ecos && uv run pytest tests/ -q

# all integration tests
bash tests/integration/run-all.sh
```

### 代码规范 / Code Standards

- **Python**: ruff format + ruff check (line-length=120, Python 3.13+)
- **TypeScript**: bun fmt + bun lint
- **Commit**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)

---

## 运维 Operations

### 启动服务 / Starting Services

```bash
# Agora MCP Server (I0 Weave)
agora-mcp                    # stdio mode
agora web                    # HTTP mode (:7422)

# Cockpit Dashboard
cockpit dashboard            # Web dashboard (:8090)

# OMO SSE Daemon (事件驱动)
omo sse-daemon               # SSE event listener + self-healing

# OMO Self-Healing CLI
omo healing status           # 引擎状态 / Engine status
omo healing rules            # 查看规则 / View rules
omo healing fix-run disk_check  # 手动执行修复 / Manual fix
```

### 自愈引擎 / Self-Healing Engine

7 条内置规则 / 7 built-in rules:
| Rule | Trigger | Action |
|------|---------|--------|
| error_spike_audit | 3 errors/5min | debt + workflow |
| timeout_cascade | 5 timeouts/5min | restart + cache clean |
| disk_quota_warning | 1 event | disk check + file clean |
| memory_pressure | 1 OOM event | process health check |
| process_dead_alert | 1 DOWN event | restart + health check |

HTTP 端点 / HTTP Endpoint: `:9091/health|status|fixes|fix/run/<name>|trends`

### CI/CD

20 GitHub Actions workflows covering all 8 projects.  
20 个 GitHub Actions 工作流覆盖全部 8 个项目。

---

## 安全 Security

- [SECURITY.md](./SECURITY.md) — 安全策略
- SSRF 防护: `agora/ssrf_guard.py` (17 网络范围拦截)
- Dashboard 认证: Bearer Token + Rate Limiting
- Token 存储: chmod 600 + .gitignore 隔离

---

## 治理 Governance

- [OMO Debt Registry](./projects/omo/.omo/debt/) — 技术债务注册表
- [System State](./.omo/state/system.yaml) — 系统健康状态 (health_score: 100.0)
- [Audit Reports](./.omo/_delivery/audits/) — 审计报告归档
- [Architecture Decision Records](./.omo/_knowledge/decisions/) — 架构决策记录

---

## 相关链接 Links

- [GitHub Repository](https://github.com/starlink-awaken/omostation)
- [Architecture Audit](./.omo/_delivery/audits/architecture_audit_20260607.md)
- [Tech Debt Roadmap](./.omo/_delivery/audits/tech_debt_roadmap_20260607.md)
- [God Module Split Plan](./projects/agora/docs/god-module-split-plan.md)
- [Relation Type Analysis](./.omo/_knowledge/analysis/relation_type_duplication.md)
