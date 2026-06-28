# AGENTS.md — ecos Development Guide

> eCOS v6 L0 Protocol Layer · SSB 签名链 + MOF 元模型 + BOS URI 路由

## Quick Commands

```bash
cd projects/ecos
uv run pytest tests/ -q          # 测试 (以实际为准)
uv run ruff check src/           # Lint check
uv run ruff check --fix src/     # Auto-fix
uv run ruff format src/          # Format
```

## Architecture

ecos 是 eCOS v6 的 L0 协议层，负责系统底层的不可变日志和元模型定义。

```
src/ecos/
├── common/          # 公共库 (logger, exceptions, config, security, cache, persistence, metrics, governed_fs)
├── l0/              # L0 核心
│   ├── governance/  # L0 治理原语 (15 模块: distributed, role, swarm, personal, task_scheduler, failover, load_balancer, agent_registry, alert_engine, checkers, event_bus, history_store, optimization, primitives, registry)
│   ├── ssb/         # SSB 签名链 (auth, client, dump, init, integrity, schema_migrate, seq_migrate)
│   ├── emergence/   # 涌现计算 (calc, auto, watch, snapshot)
│   ├── ssot/        # SSOT 引擎 + MOF 元模型 + extractor + evolution + monitoring + patterns + performance + recovery
│   ├── symphony/    # 状态机编排 (matcher, models, state_machine, triggers)
│   ├── bus/         # Bus protocol
│   ├── concurrency/ # Lock facade + sqlite lock
│   └── triggers/    # Trigger registry + yaml loader
├── protocol/        # 协议层 (ssb/ + emergence/, 与 l0/ 同构兼容映射)
├── ssot/tools/      # MOF 工具链 (34 工具文件: mof-*.py, l0_mcp_tools.py, mof_contract_lint.py)
│                    #   mof-validate, mof-audit, mof-derive, mof-bridge-sync, mof-state-bridge,
│                    #   mof-enforce, mof-reason, mof-extract, mof-contract-lint 等
├── cli/             # CLI (dashboard, scheduler, watchdog, workflow, workflow_runs)
├── services/        # 服务层 (governance, integration, monitoring, core, constitution_watcher)
└── workflow/        # 工作流引擎 (13 模块) — 统一编排调度器
                     #   M1 DSL → loader → validator(X1-X4) → executor → backend_registry
                     #   缓存: cache.py | 熔断: circuit_breaker.py
                     #   后端: metaos / agora / symphony / swarm / runtime / default
                     #   事件驱动: event_listener → bos:// 事件 → 自动触发工作流
```

## L0 治理模块 (15 核心模块)

| 模块 | 功能 |
|------|------|
| distributed.py | CRDTSync + StateSyncService + NodeManager + CommunicationProtocol |
| role.py | RoleManager + RoleCollaboration + RoleSwitcher + RoleEvaluator |
| swarm.py | SwarmManager + EmergenceDetector + CollectiveDecision + SwarmVisualizer |
| personal.py | PersonalKnowledgeManager + KnowledgeGraphBuilder + PreferenceEngine + RecommendationEngine |
| task_scheduler.py | TaskScheduler + DAGScheduler |
| failover.py | FailoverManager |
| load_balancer.py | LoadBalancer |
| agent_registry.py | AgentRegistry |
| alert_engine.py | 告警引擎 |
| checkers.py | 检查器 |
| event_bus.py | 事件总线 |
| history_store.py | 历史存储 |
| optimization.py | 优化器 |
| primitives.py | 基础原语 |
| registry.py | 注册表 |

## 架构委托链

```
L0 定义原语 (算法 + 数据结构)
  ↓
L1 运行时 (委托 L0 + 运行时增强)
  ↓
L2 引擎 (委托 L0 + 编排逻辑)
  ↓
L3 入口 (调用 L0/L1/L2)
```

## 生产级特性

- ✅ 错误处理: 全栈 try/except + ECOSException
- ✅ 日志记录: JSON 结构化日志 (common/logger.py)
- ✅ 并发安全: threading.RLock (L0 核心模块)
- ✅ 持久化: StatePersistence (5 个核心模块)
- ✅ 安全机制: TokenManager + InputValidator (L3 MCP)
- ✅ 配置管理: ECOSConfig (3 个核心模块)
- ✅ 输入校验: InputValidator (L3 MCP)
- ✅ 缓存机制: LRU 缓存 (common/cache.py)

## 测试覆盖

```bash
cd projects/ecos
uv run pytest tests/ -q                     # 测试
uv run pytest tests/ -k "keyword" -q        # 按关键字
uv run pytest tests/test_l0/test_distributed.py -v  # 分布式场景测试
```

## Key Dependencies

- **外部**: pyyaml, requests, beautifulsoup4, jinja2, fastmcp
- **跨项目**: agora (dashboard/MOF BOS 功能, 通过 try/except 软依赖)
- ecos 是 L0 协议层，不应被上层项目直接 import。跨层通信应通过 MCP/HTTP。

## Testing Pattern

```bash
cd projects/ecos
uv run pytest tests/ -q                     # 全量测试
uv run pytest tests/ -k "keyword" -q        # 按关键字
uv run pytest tests/test_l0/test_distributed.py -v  # 分布式场景
```

## File Organization

- `src/ecos/` — 源码 (以实际文件为准)
- `src/ecos/l0/governance/` — 蜂群式AI超级大脑核心模块
- `src/ecos/common/` — 公共库 (logger, exceptions, config, security, cache, persistence)
- `tests/` — 测试用例 (以实际为准)

## Gotchas

1. **L1/L2/L3 全部委托 L0** — 不要直接实现业务逻辑，委托给 L0 原语
2. **kairon 使用 uv** — Not pip/poetry. `uv sync` to install.
3. **Python 3.13+** — ecos targets Python 3.13+
4. **BOS URI 抽象** — 状态变更与读取优先使用 `bos://` URI
5. **!! 关键修改必须立即 git commit !!** — kairon 历史中有 `git reset` 操作

## 治理状态

> 运行时状态以 `../../.omo/state/system.yaml` 为 SSOT，不在此硬编码。

## Workspace-Wide Governance (2026-06-24)

This project follows the workspace-level governance conventions documented in the root `AGENTS.md`:

- **Agent Mutation Protocol**: Any autonomous agent/cron/daemon that modifies workspace state must emit `agent_mutation_intent`, avoid direct file I/O to `.omo/`/`spaces/`, and commit immediately. See `.omo/standards/agent-mutation-protocol.md` for the full protocol.
- **SSOT Guardian**: Run `python3 bin/ssot-guardian.py` from the workspace root before committing to detect task-count, current-wave, submodule-pointer, or direct-omo-io drift.
- **direct-omo-io**: Scripts must route writes to `.omo/` through `omo CLI`, `projects/omo` core, or `projects/c2g` ingress — never via raw `open()/mkdir()/write_text()`.
- **Submodule Governance**: Commit changes inside the submodule first, then bump the root-repo pointer; `git submodule status` with a `+` prefix indicates pending drift.
