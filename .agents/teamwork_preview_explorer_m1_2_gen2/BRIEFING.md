# BRIEFING — 2026-06-23T10:54:00+08:00

## Mission
分析并提供向 `projects/agora/etc/bos-services.yaml` 注册 `bos://capability/swarm/run` RPC 路由的具体 yaml 条目设计，并明确 Agora 端的解析路由工具与 Swarm 引擎转发的接口。

## 🔒 My Identity
- Archetype: explorer
- Roles: Read-only investigator, Teamwork explorer
- Working directory: /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_2_gen2
- Original parent: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Milestone: M1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- 严禁修改任何 source code 文件，严禁执行修改文件操作
- 使用中文回复

## Current Parent
- Conversation ID: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Updated: not yet

## Investigation State
- **Explored paths**: `projects/agora/etc/bos-services.yaml`, `projects/agora/src/agora/mcp/resolver/api.py`, `projects/aetherforge/src/aetherforge/swarm/__init__.py`, `projects/aetherforge/packages/swarm/src/swarm_engine/graph_workflow.py`
- **Key findings**: 前任分析已定位了 `resolve_bos_uri` 对 `internal` 路由的解析逻辑，并在 aetherforge 子项目中发现了由 `GraphWorkflow` 支撑的 Swarm 引擎。但发现了一个在 package `internal` 模式下 `sys.path` 缺失子包 `packages/swarm/src` 会导致 `ModuleNotFoundError` 的隐患。
- **Unexplored areas**: 需要定位 Agora 网格服务端（在 `agora/mcp/` 或是 `aetherforge` 中）如何编写解析和处理该 BOS URI 路由的工具，并最终将请求参数转发给 Swarm 引擎，具体确定需要修改或新增的 Python 文件与函数名称。

## Key Decisions Made
- 选用 `internal` 传输模式作为主要 RPC 路由设计，并在 `rpc.py` 内部使用动态 `sys.path` 补全的 shim 机制，避免污染 `agora` 核心解析器代码。

## Artifact Index
- `/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_2_gen2/analysis.md` — 详细的路由与 RPC 重构分析报告
- `/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_2_gen2/handoff.md` — Handoff 报告
