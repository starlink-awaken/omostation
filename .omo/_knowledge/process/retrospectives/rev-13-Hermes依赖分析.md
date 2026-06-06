# Hermes 依赖分析报告

> 所有依赖Hermes的模块、文件、原因和可替代方案
> 用途: 评估Hermes降级/迁移对其他模块的影响

---

## 一、依赖类型分类

```text
A类: Python包导入 (import hermes)        — 3处
B类: 路径依赖 (~/.hermes/)              — 12处
C类: 文件引用 (plugins/adapters/scripts) — 8个文件
D类: Hermes特定能力 (CLI/config)         — 2处
```

---

## 二、A类: Python包导入 (`import hermes`)

| 文件 | 导入语句 | 依赖原因 | 可替代 |
|------|---------|---------|--------|
| `scripts/auto_pull_pipeline.py` | `from hermes.memory.tree_engine import MemoryTree` | 拉取数据→记忆树入库 | 加`sys.path.insert(0, ...)`或用相对导入 |
| `memory/tree_federation.py` | `from hermes.memory.tree_engine import MemoryTree` | 跨实例记忆搜索 | 同上 |
| `scripts/self_healing.py` | `from hermes.scripts.evolution_engine import EvolutionEngine` | 异常回滚调用 | 同上 |
| `tests/integration_e2e_test.py` | `from hermes.plugins.task_orchestrator import TaskOrchestrator` | 全链路E2E测试 | 加`sys.path` |

**解决方案**: 这些都在try/except中，导入失败会降级。严格来说不是"依赖Hermes Agent"而是"路径未加入sys.path"。

---

## 三、B类: 路径硬编码 (`~/.hermes/`)

| 文件 | 路径 | 用途 |
|------|------|------|
| `scripts/evolution_engine.py` | `~/.hermes/evolution/` | pending建议持久化 |
| `scripts/evolution_engine.py` | `~/.hermes/memory_store.json` | 平面记忆(已废弃) |
| `scripts/self_reclaim.py` | `~/.hermes/cron/output/` | cron日志审计 |
| `scripts/self_healing.py` | `~/.hermes/evolution/` | 回滚读取pending |
| `scripts/bottleneck_detector.py` | `~/.hermes/evolution/pending.json` | 用户摩擦分析 |
| `scripts/strategic_awareness.py` | `~/.hermes/evolution/pending.json` | 趋势检测 |
| `scripts/metacognition.py` | `~/.hermes/` | 元认知读取记忆+evolution |
| `memory/tree_engine.py` | `~/.hermes/memory_store.json` | 平面→树迁移 |
| `memory/mcp_server.py` | `~/.hermes/memory_store.json` | 记忆读写 |
| `memory/tree_federation.py` | `~/.hermes/memory/` | 本地记忆搜索 |
| `plugins/model_router_plugin.py` | `~/.hermes/scripts/` | 模型路由路径 |
| `scripts/hermes-event-watcher.py` | `~/.hermes/` | 事件监控 |

**解决方案**: 改用环境变量 `HERMES_HOME` 或 `KOS_HOME` 统一配置。

---

## 四、C类: `.hermes/` 下的关键文件

| 目录 | 文件 | 大小 | 能否独立运行 |
|------|------|------|-------------|
| `plugins/` | `task_orchestrator.py` | 191 LOC | ✅ 独立于Hermes Agent, 仅需KOS collab API |
| `plugins/` | `model_router_plugin.py` | 88 LOC | ✅ 仅依赖model_router.py |
| `plugins/` | `consensus_plugin.py` | — | ✅ 仅依赖KOS consensus API |
| `plugins/` | `task_plugin.py` | — | ✅ 同上 |
| `adapters/` | `agora_fallback.py` | 98 LOC | ✅ 仅依赖Agora URL |
| `adapters/` | `human_node.py` | 133 LOC | ✅ 仅依赖KOS collab API |
| `adapters/` | `identity_middleware.py` | — | ✅ 仅依赖身份文件 |
| `memory/` | `tree_engine.py` | 162 LOC | ✅ 完全独立SQLite |
| `memory/` | `mcp_server.py` | 152 LOC | ✅ 独立MCP stdio服务 |
| `memory/` | `tree_federation.py` | 58 LOC | ✅ 仅依赖tree_engine |
| `skills/` | `mcp_server.py` | 99 LOC | ✅ 独立MCP stdio服务 |

**结论**: 这8个文件中**无一个真正依赖Hermes Agent运行时**。它们只是物理上放在了`~/.hermes/`下，但实际上:
- Plugins调用的是KOS collab API — KOS独立
- Memory是独立SQLite+stdio服务 — 完全独立
- Skills是独立stdio服务 — 完全独立

---

## 五、D类: Hermes特定能力

| 能力 | 依赖文件 | 影响范围 |
|------|---------|---------|
| Hermes CLI (`hermes chat`) | 不依赖 | Phase 10-12的新模块均通过直接python3调用 |
| Hermes memory tool (内置) | `memory/mcp_server.py` | 已被Memory Tree替代, flat memory只保留向后兼容 |
| Hermes skills (内置) | `skills/mcp_server.py` | 已被Skill MCP替代 |
| Hermes plugin机制 | `plugins/`下的.py | 可改为直接import |

---

## 六、依赖关系图

```
Hermes Agent 本身
  │
  ├── 实际依赖的 ├── 无 (所有新模块都能独立跑)
  │
  ├── 路径上依赖的 ├── ~/.hermes/scripts/   (自己加sys.path就能import)
  │                 ├── ~/.hermes/plugins/   (调KOS API, 非Hermes API)
  │                 ├── ~/.hermes/adapters/  (调Agora/KOS, 独立)
  │                 └── ~/.hermes/memory/    (独立SQLite+stdio)
  │
  └── 真实解耦方式 ─── 设HERMES_HOME环境变量, 所有硬编码→变量
```

## 七、如果去掉Hermes，会怎样？

| 组件 | 影响 | 迁移方式 |
|------|------|---------|
| TaskOrchestrator | ❌ 不依赖Hermes | 调用KOS collab API, 与Hermes无关 |
| Memory Tree | ❌ 不依赖Hermes | 独立SQLite+stdio MCP, 任何Agent可调 |
| ML Router | ❌ 不依赖Hermes | 纯Python, 独立运行 |
| TokenJuice | ❌ 不依赖Hermes | Agora中间件, 与Agent无关 |
| Identity CA | ❌ 不依赖Hermes | Agora模块, 独立运行 |
| WoT | ❌ 不依赖Hermes | Agora模块, 独立运行 |
| Consensus | ❌ 不依赖Hermes | KOS模块, 独立运行 |
| Marketplace | ❌ 不依赖Hermes | Agora模块, 独立运行 |
| SelfHealing | ❌ 不依赖Hermes | 只读evolution目录, 环境变量可解耦 |
| EvolutionEngine | ❌ **路径依赖** | `~/.hermes/evolution/` → `$KOS_HOME/evolution/` |

**唯一真依赖**: `evolution_engine.py` 写死了`~/.hermes/evolution/`路径。改一行即可解耦。

---

## 八、快速解耦方法

```bash
# 所有硬编码路径改为:
HERMES_HOME=${HERMES_HOME:-$HOME/.hermes}
# 之后:
EVOLUTION_DIR="$HERMES_HOME/evolution"
CRON_OUTPUT="$HERMES_HOME/cron/output"
```

改完后所有模块可在不装Hermes Agent的机器上运行。
