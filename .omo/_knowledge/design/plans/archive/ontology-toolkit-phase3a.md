---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 3A: 元模型层 + 可视化工具

## 任务清单

### T1: Eidos 元模型模块 (eidos/meta/) ✅
- `eidos/src/eidos/meta/__init__.py` — MetaType 枚举, MetaRelationType 枚举
- `eidos/src/eidos/meta/model.py` — MetaModel dataclass, TypeMapping

### T2: 新增类型 (eidos/types/) ✅
- `eidos/src/eidos/types/inference_rule.py` — InferenceRule dataclass
- `eidos/src/eidos/types/state_machine.py` — StateMachine + StateTransition dataclass  
- `eidos/src/eidos/types/relation.py` — Relation dataclass w/ MetaRelationType

### T3: 可视化工具 (eidos/src/eidos/viz.py) ✅
- Mermaid classDiagram 输出 (schema → diagram)
- Mermaid graph 输出 (ontology → network)
- Mermaid stateDiagram 输出 (state machine)

### T4: CLI 扩展 (eidos/src/eidos/cli.py) ✅
- `eidos meta` — 显示元模型定义
- `eidos viz schema <name>` — 可视化 Schema
- `eidos viz graph <type>` — 可视化类型实例
- `eidos viz state <machine>` — 可视化状态机

### T5: 测试 ✅
- `tests/test_meta.py` — 元模型枚举和映射
- `tests/test_types_new.py` — InferenceRule/StateMachine/Relation
- `tests/test_viz.py` — Mermaid 输出格式

总计: 50 tests, 全部通过
