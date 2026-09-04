---
id: ADR-0293
status: ACCEPTED
lifecycle: spec
owner: governance-agent
last_updated: 2026-07-30
related:
  - 0247-strategic-pivot-collab-first-physical-deferred.md
  - 0291-p86-abcd-final-closeout.md
  - 0292-check-work-landed-sha-fix.md
---

# ADR-0293: Phase 45 — Governance Observability Layer

> **Status**: Accepted
> **Date**: 2026-07-29
> **Author**: governance-agent
> **Theme**: P45 多机协作奠基
> **Phase**: 45

## Context

Phase 44 实现了基础治理框架，但缺乏实时可观测性：

1. `/health` 端点仅返回 `{status, service, tools}` — 无法诊断问题根因
2. 治理债务（`.omo/debt/items/`）依赖人工扫描，未自动发现治理缺口
3. 熵（陈旧工作树引用、过期缓存、孤立债务项）无自动清理机制
4. Phase 45 next_milestone（治理可观测性）需要可执行落地

## Decision

在 `projects/agora/src/agora/server/tools_health.py` 落地三个 MCP 工具：

| Tool | 作用 |
|------|------|
| `health_check` | 综合健康自检：uptime、服务健康、后端心跳、代理状态、审计 24h 统计、治理债务摘要 |
| `entropy_cleanup_tool` | 清理过期缓存（>24h）+ 陈旧审计（>30d）+ 陈旧工作树引用 |
| `debt_auto_seed_tool` | 扫描治理缺口（无健康端点的服务、无治理标签的代理工具），自动创建债务项 |

升级 HTTP `/health` 端点（HTTP 和 SSE 两个入口）使用综合健康检查而非最小返回。

## Consequences

### Positive

- **可观测性提升**: 从 3 字段升级到 10+ 维度（uptime / services / backends / proxy / audit / debt / issues）
- **自动化发现**: 治理缺口不再依赖人工扫描
- **状态判定**: 显式 `healthy` / `degraded` 状态，便于上游路由决策
- **MCP 原生**: 3 个工具可直接通过 agora-mcp 调用，无需 CLI
- **安全清理**: 熵清理仅移除明确陈旧项（>24h / >30d），不会误删活跃数据

### Negative

- **新增依赖**: 债务项扫描需要文件系统访问，需考虑权限
- **写入面扩展**: `debt_auto_seed` 创建 `.omo/debt/items/*.yaml` — 须走 governed broker（目前直接写，遵循 ADR-0214 同等约束）
- **错误恢复**: 健康检查失败时 fallback 到最小返回，保证可用性

## Implementation

```python
# projects/agora/src/agora/server/tools_health.py
async def health_self_check() -> dict:
    """Returns: status, uptime, services, proxy, backends, audit_24h, debt, issues"""

async def entropy_cleanup() -> dict:
    """Returns: cleaned[], skipped[], cleaned_count, skipped_count"""

async def debt_auto_seed() -> dict:
    """Returns: seeded[], seeded_count, existing_debt_count"""
```

注册位置：`projects/agora/src/agora/server/mcp.py:452-454`
HTTP 端点升级：`projects/agora/src/agora/server/mcp_entry.py:34-41, 140-147`

## Verification

- 8/8 新单元测试通过 (`tests/unit/test_tools_health.py`)
- 184/184 agora 全量单元测试通过
- GaC local gate: 39/39 ALL GREEN
- Ruff check: 0 errors on new files

## Related

- Phase 41 (agent-workflow contract)
- Phase 43 (P71 baseline recovery)
- ADR-0203 (requirement iteration workflow)
- W5 (Agent Registry MVP) — current wave
