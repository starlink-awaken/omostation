# CLAUDE.md — model-driven

> eCOS v5 Cross-Cutting Framework · 全生命周期模型驱动平台 · 24 M2类型 · 7阶段 · 12工具 · 28 MCP tools

---

## 项目身份

model-driven 是一个**横切面框架 (Cross-Cutting Framework)**，不归属任何单一层，被 L0/I0/L3/L4 四层消费。

**核心职责**：
1. **MOF 建模能力提供者** — 扩展 L0 的 M3/M2 元模型，为全系统提供 M1 节点建模能力
2. **生命周期引擎** — 为 L4 (域生命周期) 和 L2 (治理生命周期) 提供 7 阶段状态机
3. **模型驱动工具链** — 12 个核心工具 (design/generate/derive/validate/connect/compile/evolve/monitor/deploy/observe/report/archive)
4. **管理面** — Spec + ADR + OKR + OMO 桥接 + 多Agent 协作
5. **MCP 服务提供者** — 向 I0 (agora) 暴露 28 个 MCP 工具，被 L3 (cockpit) 消费
6. **并行验证层** — 与 L0 ecos 并行运行，通过自反验证保障 MOF 一致性

**消费方**: L0 ecos · I0 agora · L3 cockpit · L4 l4-kernel
**依赖**: 零内部依赖 (仅 pyyaml>=6.0)

---

## 架构

```
src/model_driven/
├── cli.py                      ← CLI 入口 (model-driven 命令, 7 子命令)
├── mcp_server.py               ← MCP Server (28 tools, 8 管理器)
├── _paths.py                   ← 路径工具 (get_workspace_dir / get_state_dir)
│
├── lifecycle/                  ← 生命周期引擎
│   ├── stages.py               ← 7 阶段定义 + 状态机
│   ├── gates.py                ← 门禁引擎 (GateEngine)
│   ├── transitions.py          ← 阶段转换规则
│   ├── tracking.py             ← LifecycleManager (生命周期追踪)
│   └── pipeline.py             ← PipelineTracker (三阶段流水线, 持久化)
│
├── management/                 ← 管理面
│   ├── spec.py                 ← SpecManager (规范管理)
│   ├── adr.py                  ← ADRManager (架构决策管理)
│   ├── okr.py                  ← OKRManager + OKRDecomposer
│   ├── omo_bridge.py           ← OMOBridge (事件/审计/同步)
│   └── agent_collab.py         ← AgentCollabManager (多Agent协作)
│
├── mof/                        ← MOF 元模型扩展
│   ├── m3_extended.py          ← M3 扩展 (LifecycleElement/ValueElement/Decision)
│   ├── m2_lifecycle.py         ← M2 扩展 (24 新类型, 7 阶段映射)
│   └── ontology_extended.py    ← 本体论扩展
│
├── toolchain/                  ← 模型驱动工具链
│   ├── tools.py                ← 12 个核心工具函数
│   ├── derivation_engine.py    ← 推导引擎 (15 DR规则 + Trigger规则)
│   ├── trigger_registry.py     ← TriggerRegistry (统一触发管理)
│   ├── trigger_m0.py           ← TriggerM0Manager (M0 运行时快照)
│   ├── bus.py                  ← ToolchainBus (工具执行总线)
│   ├── mof_scan.py             ← 工作区/项目/契约扫描 → M1 节点
│   ├── mof_model.py            ← 全量资产 → M1 节点建模
│   ├── mof_extract.py          ← 资产 → M1 逆向提炼
│   └── common.py               ← 公共工具 (now, 路径)
│
└── ssot/                       ← SSOT 全生命周期化
    └── lifecycle_ssot.py       ← LifecycleSSOT + ValueSSOT + CrossStageChecker
```

---

## 快速命令

```bash
cd projects/model-driven

# 测试 (190 tests, 100% 通过)
uv run pytest tests/ -q

# Lint 检查
uv run ruff check src/

# 自动修复
uv run ruff check --fix src/

# 格式化
uv run ruff format src/

# CLI
uv run model-driven --help
```

---

## GPTCHAS

1. **零内部依赖** — 仅依赖 pyyaml，不依赖任何 eCOS 项目
2. **Cross-Cutting Framework** — 不是 L4 层，被四层消费 (L0/I0/L3/L4)
3. **路径统一** — 所有 workspace 路径通过 `_paths.get_workspace_dir()` 获取，不再硬编码 `~/Workspace`
4. **全内存模式** — Manager 类数据在内存中，`PipelineTracker` 和 `TriggerM0Manager` 有持久化，其他 Manager 正逐步添加 save/load
5. **Trigger 统一管理** — 10 种触发机制通过 TriggerRegistry 统一注册和治理
6. **三阶段流水线** — Planning → Development → Deployment，通过 PipelineTracker 持久化追踪
