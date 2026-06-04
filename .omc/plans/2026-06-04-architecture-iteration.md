# kairon 架构迭代规划

> 基于 31 包全面扫描，覆盖架构、能力、质量三方面迭代
> 日期: 2026-06-04 | 状态: draft | 作者: architect

---

## 需求概要

对 kairon monorepo 31 个包进行架构重整，解决 MCP 入口碎片化、瘦包泛滥、shared-lib 职责过载、测试缺失等 8 项问题。

---

## 接受标准 (AC)

- [AC1] MCP 入口统一：所有 MCP 请求经过 agora 路由，其它包不再暴露独立 MCP 端口
- [AC2] Wksp 测试覆盖率 ≥70%（当前 0）
- [AC3] 10 个瘦包整合为 ≤5 个，包总数从 31 → ≤26
- [AC4] shared-lib 拆分 ≤5 个子模块
- [AC5] 跨包集成测试 ≥3 条链路
- [AC6] 所有包 __init__.py 有显式 __all__
- [AC7] 版本号符合 major.Minor.Patch 策略
- [AC8] 根目录 5 个 _fix_*.py 清理

---

## 实施步骤

### Wave 1: P0 快速修复（预计 1 天）

#### W1-T1: 根目录清理
**文件：**
- Delete: `projects/kairon/_fix_imports.py`
- Delete: `projects/kairon/_fix_merged.py`
- Delete: `projects/kairon/_fix_object_annotations.py`
- Delete: `projects/kairon/_fix_remaining.py`
- Delete: `projects/kairon/_fix_remaining2.py`
- Verify: `ruff check .` no errors

**AC:** 根目录无残留修复脚本

---

#### W1-T2: Wksp 测试覆盖
**文件：**
- Create: `packages/wksp/tests/test_basic.py`
- Create: `packages/wksp/tests/test_cli.py`
- Create: `packages/wksp/tests/conftest.py`

**步骤：**
1. 创建 conftest.py 提供测试 fixture（临时目录环境）
2. test_basic.py: 验证 import wksp, import 所有 commands 子模块
3. test_cli.py: 验证 CLI 入口（help 输出、子命令解析）

**AC:** `python3 -m pytest packages/wksp/tests/ -q` ≥10 个测试通过

---

#### W1-T3: API __all__ 标准化
**文件：** 所有 31 个包 src/*/__init__.py

**策略：** 每个包至少导出核心类/函数，无空 __all__

**AC:** 所有 __init__.py 有非空 __all__

---

### Wave 2: 瘦包整合（预计 2 天）

#### W2-T1: agent-hub → agent-runtime 合并
**文件：**
- Move: `packages/agent-hub/src/agent_hub/__init__.py → packages/agent-runtime/src/agent_runtime/agent_hub.py`
- Delete: `packages/agent-hub/`
- Update: `packages/agent-runtime/pyproject.toml`（移除 agent-hub 依赖）
- Update: workspace pyproject.toml（移除 agent-hub 成员）

**AC:** agent-runtime 能正常引用 AgentHub，`from agent_runtime.agent_hub import AgentHub`

---

#### W2-T2: sharedbrain-standalone → sharedbrain-bridge 合并
**文件：**
- Move: `packages/sharedbrain-standalone/src/` → `packages/sharedbrain-bridge/src/sharedbrain_bridge/standalone/`
- Delete: `packages/sharedbrain-standalone/`
- Update: workspace 配置

**AC:** sharedbrain-bridge 能正常引用 standalone 模块

---

#### W2-T3: observability → shared-lib 合并
**文件：**
- Move: `packages/observability/src/observability/` → `packages/shared-lib/src/kairon_lib/observability/`
- Delete: `packages/observability/`
- Update: workspace 配置

**AC:** `from kairon_lib.observability import MetricsCollector` 正常

---

#### W2-T4: gc-engine → eidos 合并
**文件：**
- Move: `packages/gc-engine/src/gc_engine/` → `packages/eidos/src/eidos/gc/`
- Delete: `packages/gc-engine/`
- Update: workspace 配置

**AC:** `from eidos.gc import GCEngine` 正常

---

#### W2-T5: eu-pricing → kaironcloud-billing 合并
**文件：**
- Move: `packages/eu-pricing/src/eu_pricing/` → `packages/kaironcloud-billing/src/kaironcloud_billing/pricing/`
- Delete: `packages/eu-pricing/`
- Update: workspace 配置

**AC:** `from kaironcloud_billing.pricing import EnergyLedger` 正常

---

#### W2-T6: pontus → minerva 合并
**文件：**
- Move: `packages/pontus/src/pontus/` → `packages/minerva/src/minerva/pipeline/pontus/`
- Delete: `packages/pontus/`
- Update: workspace 配置

**AC:** `from minerva.pipeline.pontus import DAGScheduler` 正常

---

### Wave 3: 架构重构（预计 2 天）

#### W3-T1: MCP 入口统一到 agora
**分析：** 当前 10+ 包各自暴露 MCP server，绕过 agora 路由/断路器/认证体系。

**方案：** 
- agora 作为唯一 MCP 暴露层（7430/7431）
- 其他包注册为 agora backend（mcp_proxy 模式）
- 通过 agora 的 ServiceRegistry 统一发现

**文件：**
- Modify: `packages/agora/src/agora/mcp_proxy/manager.py` — 增加 backend 注册流程
- Modify: `packages/agora/src/agora/agent_registry.py` — 扩充 backend 描述字段
- Create: `packages/agora/src/agora/mcp_unification.py` — MCP 统一注册管理
- Modify: 各包 pyproject.toml — 移除独立 MCP 入口脚本
- Modify: `packages/agora/pyproject.toml` — 增加统一 MCP CLI 入口

**AC:** 所有 MCP 请求通过 agora 7430/7431，各包独立 MCP 入口移除

---

#### W3-T2: shared-lib 模块化拆分
**分析：** 166 文件涵盖 governance/audit/cognitive/metrics/core 五个域，内部依赖混乱。

**方案：** 目录结构重组：

```
shared-lib/src/kairon_lib/
├── __init__.py        # 兼容导出
├── _compat.py         # 保持
├── governance/        # committee_hall, committee, consensus_mechanism, rfc_lifecycle, voting_framework, approval_queue, approval_router
├── audit/             # audit_trail, audit_query, adr_storage, retrospective
├── cognitive/         # cognitive_loop, workflow_engine, delivery_loop, thinking
├── metrics/           # evolution_metrics, harvest_scheduler
└── core/              # errors, capability_standardization, emergency_stop, human_in_the_loop
```

**AC:** 原有导入路径 `from kairon_lib.xxx import YYY` 保持兼容

---

### Wave 4: 质量提升（预计 2 天）

#### W4-T1: 跨包集成测试
**创建测试链路：**
1. agora → agent-runtime: MCP 调用 → agent 执行
2. agent-runtime → engine-core: agent 调度 → worker 分发
3. engine-core → llm-gateway: 任务执行 → LLM 调用

**文件：**
- Create: `tests/integration/run-all.sh`
- Create: `tests/integration/test_agora_agent_flow.py`
- Create: `tests/integration/test_engine_llm_flow.py`

**AC:** 3 条集成链路可通过 `bash tests/integration/run-all.sh` 运行

---

#### W4-T2: 版本号规范化
**策略：**
- major 升级走 gate review（架构变更）
- minor 升级新增功能
- patch 修复 bug
- 当前 0.1.0 包根据实际成熟度重新定级

**AC:** 所有包版本号符合统一策略

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 瘦包合并破坏现有导入 | 中 | 高 | 保留兼容导入路径，逐步迁移 |
| MCP 统一导致服务中断 | 中 | 高 | 分层灰度，先迁非核心包 |
| shared-lib 拆分破坏依赖 | 高 | 中 | 保持向后兼容 __init__ 导出 |
| Wksp 测试发现深层 Bug | 中 | 低 | 测试本身就是发现问题的目的 |

---

## 验证步骤

1. `python3 -m pytest packages/ -q` 全部通过
2. `ruff check packages/` 0 error
3. 验证各包 __init__ 导入
4. 验证 nova 统一 MCP 端口可达
5. `bash tests/integration/run-all.sh` 通过

---

## 工作量估算

| Wave | 任务 | 估算 |
|------|------|------|
| W1 | P0 快速修复 | ~0.5 天 |
| W2 | 瘦包整合 ×6 | ~1 天 |
| W3 | 架构重构 ×2 | ~2 天 |
| W4 | 质量提升 ×2 | ~1.5 天 |
| **总计** | | **~5 天** |
