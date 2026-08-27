# AGENTS.md — .omo

## Scope

`.omo/` 是治理与运行态的核心状态域，包含真值、运行投影和治理面定义。该目录属于受约束编辑边界。

## 先决条件

1. 阅读根仓 [`../AGENTS.md`](../AGENTS.md)。
2. 任何治理状态写入请走 OMO/C2G 变更通道，不直接手工修改关键状态文件。
3. 处理需求型改动遵循 ADR-0203 工作流：`bootstrap -> start -> claim -> verify -> closeout`。

## 编辑规则

- 严禁直接手工编辑 `.omo/state/system.yaml` 与运行态快照类关键文件；优先通过受管 CLI/运行态同步命令更新。
- 任何 SSOT 变更必须同步审计链路（`make ssot-sync` / `make ssot-status`）。
- 修改 registry 的同时补齐对应的引用文档与治理入口（AGENTS/README/README 指南）。

## 常用命令

- `uv run --with pyyaml python ../bin/agent-workflow.py suggest --from-diff`
- `uv run --with pyyaml python ../bin/agent-workflow.py compliance`
- `make ssot-status`

