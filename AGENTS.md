# AGENTS.md — ecos Development Guide

> eCOS v5 L0 Protocol Layer · SSB 签名链 + MOF 元模型 + BOS URI 路由

## Quick Commands

```bash
cd projects/ecos
uv run pytest tests/ -q          # 472 tests
uv run ruff check src/           # Lint check
uv run ruff check --fix src/     # Auto-fix
uv run ruff format src/          # Format
```

## Architecture

ecos 是 eCOS v5 7 层架构的 L0 协议层，负责系统底层的不可变日志和元模型定义。

```
src/ecos/
├── common/      # 公共库 (logger, exceptions, config, security, cache, persistence)
├── l0/          # L0 核心
│   ├── governance/  # 蜂群式AI超级大脑原语 (16个模块)
│   ├── ssb/     # SSB 签名链 (auth, client, dump, init, integrity)
│   ├── emergence/   # 涌现计算
│   ├── ssot/    # SSOT 引擎 + 工具链 (25 mof-* 工具)
│   └── symphony/    # 状态机编排
├── l1/          # L1 运行时 (委托 L0)
│   ├── runtime/     # CommunicationProtocol, StateSyncService, FailoverExecutor, LoadBalancerExecutor
│   └── transport.py # TCPNode (asyncio TCP 通信)
├── l2/          # L2 引擎 (委托 L0)
│   └── engine/      # CollaborationEngine, SwarmEngine, PersonalEngine
├── l3/          # L3 入口 (调用 L0)
│   └── entry/       # GovernanceCLI (6 命令), GovernanceMCP (14 工具)
├── cli/         # CLI (dashboard, scheduler, watchdog)
├── services/    # 服务层 (core, governance, integration, monitoring)
├── workflow/    # 工作流
└── ssot/tools/  # MOF 工具链
```

## L0 治理模块 (16个核心模块)

| 模块 | 功能 | 测试 |
|------|------|------|
| distributed.py | CRDTSync + StateSyncService + NodeManager + CommunicationProtocol | ✅ |
| role.py | RoleManager + RoleCollaboration + RoleSwitcher + RoleEvaluator | ✅ |
| swarm.py | SwarmManager + EmergenceDetector + CollectiveDecision + SwarmVisualizer | ✅ |
| personal.py | PersonalKnowledgeManager + KnowledgeGraphBuilder + PreferenceEngine + RecommendationEngine | ✅ |
| task_scheduler.py | TaskScheduler + DAGScheduler | ✅ |
| failover.py | FailoverManager | ✅ |
| load_balancer.py | LoadBalancer | ✅ |
| agent_registry.py | AgentRegistry | ✅ |

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
uv run pytest tests/ -q                     # 472 tests
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
uv run pytest tests/ -q                     # 全量 (472 tests)
uv run pytest tests/ -k "keyword" -q        # 按关键字
uv run pytest tests/test_l0/test_distributed.py -v  # 分布式场景
```

## File Organization

- `src/ecos/` — 60+ 源文件, 6,982 行
- `src/ecos/l0/governance/` — 16 个蜂群式AI超级大脑核心模块
- `src/ecos/common/` — 6 个公共库 (logger, exceptions, config, security, cache, persistence)
- `tests/` — 472 测试用例

## Gotchas

1. **L1/L2/L3 全部委托 L0** — 不要直接实现业务逻辑，委托给 L0 原语
2. **kairon 使用 uv** — Not pip/poetry. `uv sync` to install.
3. **Python 3.13+** — ecos targets Python 3.13+
4. **BOS URI 抽象** — 状态变更与读取优先使用 `bos://` URI
5. **!! 关键修改必须立即 git commit !!** — kairon 历史中有 `git reset` 操作

## 治理状态

| 指标 | 值 |
|------|-----|
| Phase | **9** |
| 在线域 | 12 个在线 |
| MOF 规则 | 5,234 |
| Git | 74 commits |
