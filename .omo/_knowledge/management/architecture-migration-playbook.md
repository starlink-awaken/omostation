---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# eCOS 架构迁移全路径

> 2026-06-07 | 执行手册
> 前置: 全量方案已通过审查

---

## M0 — 前置准备 (一次性)

```bash
# 1. 确保所有仓库干净, 无未提交修改
cd ~/Workspace && git status
cd ~/Workspace/projects/kairon && git status
cd ~/Workspace/projects/runtime && git status

# 2. 运行全量测试, 记录基线
cd ~/Workspace/projects/kairon && make test-fast 2>&1 | tee /tmp/kairon-test-baseline.txt
cd ~/Workspace/projects/runtime && uv run python -m pytest tests/ 2>&1 | tee /tmp/runtime-test-baseline.txt

# 3. 备份
cp -r ~/Workspace/projects/kairon ~/Workspace/projects/kairon.bak.$(date +%Y%m%d)
```

---

## M1 — 低风险搬家 (metaos + ecos + wksp) · 1-2天

### M1.1: metaos 独立 (7.8K, 自包含)

```bash
# 1. 创建工作目录
mkdir -p ~/Workspace/projects/metaos

# 2. 移动源码
cp -r ~/Workspace/projects/kairon/packages/metaos/src ~/Workspace/projects/metaos/
cp -r ~/Workspace/projects/kairon/packages/metaos/tests ~/Workspace/projects/metaos/

# 3. 创建 pyproject.toml (独立项目格式)
cat > ~/Workspace/projects/metaos/pyproject.toml << 'TOML'
[project]
name = "metaos"
version = "7.1.0"
description = "MetaOS — Orchestration Engine"
requires-python = ">=3.10"
dependencies = []
[project.scripts]
metaos = "metaos.metaos_main:main"
TOML

# 4. 从 kairon 的 uv workspace 中移除
# 编辑 packages/metaos/pyproject.toml, 去掉 workspace 标记

# 5. 验证
cd ~/Workspace/projects/metaos && uv sync && uv run python -c 'from metaos import __init__'

# 6. 提交
cd ~/Workspace/projects/metaos && git init && git add . && git commit -m 'init: metaos — orchestration engine'
```

### M1.2: ecos 独立 (6.3K, 自包含)

```bash
# 同上, 目录改为 projects/ecos
mkdir -p ~/Workspace/projects/ecos
cp -r ~/Workspace/projects/kairon/packages/ecos/src ~/Workspace/projects/ecos/
cp -r ~/Workspace/projects/kairon/packages/ecos/tests ~/Workspace/projects/ecos/
# ... 创建独立 pyproject.toml, uv sync, 验证, commit
```

### M1.3: wksp → cockpit (15K, 依赖 agora)

```bash
mkdir -p ~/Workspace/projects/cockpit
cp -r ~/Workspace/projects/kairon/packages/wksp/src ~/Workspace/projects/cockpit/cli/

# 创建独立 pyproject.toml (依赖将在 M3 agora 独立后解决)
# 暂时保持对 kairon/agora 的引用

# 验证
cd ~/Workspace/projects/cockpit && uv sync && uv run python -c 'import wksp'
```

### M1 验证清单

```
- [ ] metaos: uv sync + import 成功
- [ ] ecos: uv sync + import 成功
- [ ] cockpit: uv sync + import 成功
- [ ] kairon 原有 import (无对这些包的引用) 不报错
- [ ] 提交所有更改
```

---

## M2 — 中等风险 (agent-runtime + cron-service) · 2-3天

### M2.1: cron-service → runtime/scheduler

```bash
# 1. 复制源码到 runtime
cp -r ~/Workspace/projects/kairon/packages/cron-service/src/cron_service \
     ~/Workspace/projects/runtime/src/runtime/scheduler/

# 2. 更新 runtime/pyproject.toml 增加依赖
# dependencies 增加: apscheduler>=3.10, croniter>=6.2.2

# 3. 创建桥接模块 (runtime/scheduler/__init__.py)
cat > ~/Workspace/projects/runtime/src/runtime/scheduler/__init__.py << 'PY'
"""cron-service bridge — migrated from kairon."""
from .scheduler import CronScheduler
__all__ = ["CronScheduler"]
PY

# 4. 验证
cd ~/Workspace/projects/runtime && uv sync && uv run python -c "from runtime.scheduler import CronScheduler"
```

### M2.2: agent-runtime 拆分

```bash
# 拆成两部分:
#   A) 核心执行引擎 → runtime/executor/
#   B) CLI + API 入口 → cockpit/

# A: 拷贝核心模块 (engine, tools, config) 到 runtime
mkdir -p ~/Workspace/projects/runtime/src/runtime/executor
cp ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/engine.py \
   ~/Workspace/projects/runtime/src/runtime/executor/
cp ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/tools.py \
   ~/Workspace/projects/runtime/src/runtime/executor/
cp -r ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/config \
   ~/Workspace/projects/runtime/src/runtime/executor/

# B: CLI 和 API 入口 → cockpit
cp ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/cli.py \
   ~/Workspace/projects/cockpit/
cp ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/server.py \
   ~/Workspace/projects/cockpit/
cp ~/Workspace/projects/kairon/packages/agent-runtime/src/agent_runtime/mcp_server.py \
   ~/Workspace/projects/cockpit/

# 更新 cockpit 的入口点
cat >> ~/Workspace/projects/cockpit/pyproject.toml << 'TOML'
[project.scripts]
agent-runtime = "cli:main"
TOML
```

### M2 验证清单

```
- [x] runtime 可 import CronScheduler
- [x] runtime 可 import AgentRuntime
- [x] cockpit 可启动 agent-runtime --health
- [x] kairon 原有包的引用更新到新路径
- [x] 运行 runtime 全量测试
```

---

## M3 — 高风险 (agora 独立) · 3-4天

这是最核心的变更。agora(38K) 依赖 kairon 内 5 个包。

### M3.1: 分析依赖 (已做)

```
agora 的 5 个 kairon内部依赖:
  1. agent_runtime — 使用其 MCP server → 改为通过 MCP 协议调用
  2. eidos        — Schema 验证 → 保留 import (eidos 会保持在 kairon L2 内)
  3. kos          — 知识存储操作 → 保留 import
  4. minerva      — 研究引擎 → 保留 import
  5. kairon_lib   — 工具函数 → 提取到 agora 内部或共享库

结论: agent_runtime 已移出到 runtime, eidos/minerva/kos 保持在 kairon 内,
      agora 需要保持对这些包的引用 (它们都是 L2 知识工程包, agora 作为
      I0 枢纽需要能够使用它们)
```

### M3.2: 从 kairon 读 agora

```bash
# 1. 创建独立项目
mkdir -p ~/Workspace/projects/agora

# 2. 拷贝 agora 源码
cp -r ~/Workspace/projects/kairon/packages/agora/src ~/Workspace/projects/agora/
cp -r ~/Workspace/projects/kairon/packages/agora/tests ~/Workspace/projects/agora/

# 3. 创建独立 pyproject.toml
# 保留对 eidos, kos, minerva 的依赖 (它们保持在 kairon)
cat > ~/Workspace/projects/agora/pyproject.toml << 'TOML'
[project]
name = "agora"
version = "2.0.0"
description = "Agora — I0 MCP Service Hub"
requires-python = ">=3.13"
dependencies = [
    "eidos",
    "kos",
    "minerva",
    "core-models",
    "cryptography>=41.0",
    "httpx>=0.27",
    "structlog>=24.0",
    "fastmcp>=0.1",
    "fastapi>=0.100",
    "uvicorn>=0.20",
]
[project.scripts]
agora = "agora.cli:main"
TOML

# 4. 验证
cd ~/Workspace/projects/agora && uv sync && uv run python -c "import agora"

# 5. 更新 kairon 其他包对 agora 的引用
# wksp(已在 cockpit) 从 'agora' import → 需要可解析到项目的 agora
```

### M3.3: 精简 agora (移除非 I0 功能)

```bash
# 从 agora 源中移除:
#   - web/dashboard.html → 迁移到 cockpit/web/
#   - web/app.py (仪表板 FastAPI) → 迁移到 cockpit/
#   - a2a/ (Agent-Agent) → 迁移到 metaos/

# 保留 I0 核心:
#   - core/registry, discovery, event_bus, circuit_breaker
#   - mcp/ (mcp_bootstrap, mcp_protocol, mcp_transport)
#   - mcp_registry/ (ToolCatalog, Orchestrator, SmartRouter)
#   - mcp_proxy/ (ProxyManager)
#   - auth/ (mcp_auth)
#   - server/mcp.py (统一 MCP 服务器)
```

### M3 验证清单

```
- [x] agora 独立 uv sync 成功
- [x] agora 可启动: uv run agora --health
- [x] kairon 所有包对 agora 的 import 路径更新完毕
- [x] 端到端 MCP 调用: 从 cockpit 通过 agora 调用 kairon/agent-runtime 工具
- [x] 运行 agora 全量测试 (49 个测试文件)
```

---

## M4 — 收尾 (kairon-governance → omo) · 1天

```bash
# 1. 将 kairon-governance 功能合并到 omo
# 核心模块: ADR 采集, agaora 路由报告, 审计, 状态同步
mkdir -p ~/Workspace/projects/omo/src/omo/governance/

# 2. 拷贝并适配
cp ~/Workspace/projects/kairon/packages/kairon-governance/src/kairon_governance/adr_collect.py \
   ~/Workspace/projects/omo/src/omo/governance/
cp ~/Workspace/projects/kairon/packages/kairon-governance/src/kairon_governance/audit.py \
   ~/Workspace/projects/omo/src/omo/governance/
# ... 等等

# 3. 创建 omo governance CLI 子命令
# omo governance adr list
# omo governance audit run
```

### M4 验证清单

```
- [ ] omo 可运行合并后的 governance 命令
- [ ] kairon 对 kairon-governance 的所有引用更新到 omo
- [ ] 旧 import 路径 兼容 stub 保留 (标记 deprecated)
```

---

## 完整验证 (跨所有 M4)

```bash
# 1. 全量语法检查
for project in agora kairon gbrain omo metaos ecos runtime cockpit; do
    echo "=== $project ==="
    cd ~/Workspace/projects/$project && uv run python -c "print('ok')" 2>&1
done

# 2. 全量测试
cd ~/Workspace/projects/kairon && make test-fast        # kairon 14 包
cd ~/Workspace/projects/agora && uv run python -m pytest tests/ -q
cd ~/Workspace/projects/runtime && uv run python -m pytest tests/ -q
cd ~/Workspace/projects/omo && uv run python -m pytest tests/ -q

# 3. E2E 验证
# 启动 Agora → 注册 kairon MCP 服务 → 从 cockpit 调工具
uv run agora start &
sleep 2
curl http://localhost:7430/health
```

---

## 总时间估算

| 步骤 | 时间 | 类型 |
|------|------|------|
| M0 准备 | 1h | 一次性 |
| M1.1 metaos | 2h | 低风险 |
| M1.2 ecos | 2h | 低风险 |
| M1.3 cockpit (wksp) | 3h | 低风险 |
| M2.1 cron→runtime | 3h | 中风险 |
| M2.2 agent-runtime 拆分 | 6h | 中风险 |
| M3.1 分析 | 2h | 高风险 |
| M3.2 agora 出库 | 4h | 高风险 |
| M3.3 agora 精简 | 8h | 高风险 |
| M4 k-gov→omo | 4h | 低风险 |
| 验证 | 4h | — |
| **总计** | **~39h (~5天)** | |

---

## 回滚策略

每一步都是可逆的（移动源码，非删除）：

```bash
# 如果任何一步失败, 删除新项目, 恢复备份
rm -rf ~/Workspace/projects/agora
rm -rf ~/Workspace/projects/metaos
rm -rf ~/Workspace/projects/ecos
rm -rf ~/Workspace/projects/cockpit
cp -r ~/Workspace/projects/kairon.bak.$(date +%Y%m%d) ~/Workspace/projects/kairon
```
