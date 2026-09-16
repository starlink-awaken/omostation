---
schema_version: retro/v1
bet_id: BET-Y2Q1-T7-01
status: completed
created: 2026-09-16
type: ssot
owner: engineering-agent
---

# BET-Y2Q1-T7-01 复盘：组织人脉图谱

## 结果

- **状态**: DONE
- **交付面**: 3/3 全部交付
  - `projects/knowledge/kairon/src/kairon/graph/org_graph.py` — OrgGraph 核心类
  - `projects/knowledge/kairon/src/kairon/cli.py` — CLI 入口（org-graph 子命令）
  - `projects/cockpit/src/cockpit/commands/org_relation.py` — Cockpit org-relation 命令
  - `projects/cockpit/src/cockpit/_subcommands.py` — 子命令注册
  - `projects/cockpit/src/cockpit/cli.py` — handler 注册

## 完成定义验证

| 验证项 | 结果 |
|--------|------|
| `PYTHONPATH=... uv run python -m kairon.cli org-graph --query 测试单位` | ✅ exit 0 |
| `make gac-local-gate` | ✅ exit 0 |
| cockpit parser 识别 org-relation | ✅ |
| OrgGraph 含 demo() / search() / network_view() / save() / load() | ✅ |
| Cockpit org-relation 渲染 Rich 表格 | ✅ |

## 架构决策

1. **独立 OrgGraph 类而非继承 KnowledgeGraph**：组织节点有独特的字段（title 表职位/文号）和时间衰减权重逻辑，继承会导致接口污染。
2. **demo() 工厂方法**：提供开箱即用的样例数据，降低首次使用门槛。
3. **Cockpit 命令使用动态导入**：`__import__("cockpit.commands.org_relation", ...)` 保持与现有 gongwen/finance/strategy 等命令一致的注册模式。
4. **时间衰减半衰期 365 天**：适合政企沟通节奏（年度周期），与 DecayManager 的 180 天区分。

## 技术债与后续

- OrgGraph 当前为内存图谱，后续可对接 Kos 持久化（BET-Y2Q1-T7-02 候选）。
- `network_view()` 的 BFS 遍历在大规模图谱（>10K 节点）时可能需要深度限制或索引优化。
- Cockpit 命令目前使用 demo 数据，后续需接入实际数据加载路径。

## D2 表面积记账

```
项目                 churn_add   churn_del          净值        重写噪音
----------------------------------------------------------------
cockpit               72,113      17,751     +54,362       4,912
_root                 688,230     679,883      +8,347       2,324
```

主要增量集中在 cockpit（org_relation 命令 + subcommand/handler 注册）和 _root（spec + retro + ledger 绑定）。

## 教训

- submodule 初始化需要 `--depth 1` 加速，部分 submodule（如 ecos）可能因网络超时需重试。
- cockpit 的 `handlers` dict 使用 lambda + `__import__` 模式，新增命令时需遵循此模式避免静态导入导致的循环依赖。
- submodule commit 三步走：① submodule 内 add+commit ② push submodule ③ 根仓 add submodule pointer + commit + push。
