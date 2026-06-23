# BRIEFING — 2026-06-23T10:32:00+08:00

## Mission
项目全局代码探测与重构方案调研，包括 ECOS 跨层 subprocess 调用、Swarm 底层事件总线替换、Mesh 动态反馈与 Omo 稳态落盘闭环。

## 🔒 My Identity
- Archetype: teamwork_preview_explorer
- Roles: survey_explorer_1
- Working directory: /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_survey_1/
- Original parent: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Milestone: Survey and analysis for refactoring tasks completed

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Cannot modify source code (except agent metadata files in working directory)
- Operating in CODE_ONLY network mode: No external URL access
- Must use Chinese in responses to the user (and in messages to parent)

## Current Parent
- Conversation ID: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Updated: 2026-06-23T10:32:00+08:00

## Investigation State
- **Explored paths**:
  - `projects/ecos/src/ecos/workflow/backends/swarm.py`
  - `projects/ecos/src/ecos/workflow/agora_mcp_backend.py`
  - `projects/aetherforge/packages/swarm/src/swarm_engine/_events.py`
  - `projects/aetherforge/packages/swarm/src/swarm_engine/lifecycle_events.py`
  - `projects/aetherforge/packages/swarm/src/swarm_engine/event_bus.py`
  - `projects/bus-foundation/src/bus_foundation/`
  - `projects/aetherforge/packages/mesh/src/compute_mesh/topology/registry.py`
  - `projects/omo/src/omo/omo_ingress.py`
  - `projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py`
- **Key findings**:
  - R1 的 Subprocess 命令行调用已被精确定位在 `ecos/workflow/backends/swarm.py` 中。提出以 Agora MCP 路由工具 `resolve_bos_uri` 来完成对 `bos://capability/swarm/run` RPC 调用的重构策略。
  - R2 梳理了 Swarm 内部事件桩（Stub）以及 `_events.py` 中 `_emit_hatcher_event` 方法。确立了以 `bus-foundation` 模块的 `publish` 接口与 `BusEnvelope` 信封来进行重构替换，并可下线本地 `event_bus.py` 桩。
  - R3 精确定位了 Mesh 中 `NodeRegistry` 触发状态变更的监听与通知点，同时分析了 Omo Ingress 层安全更新 `state/system.yaml` 的 POSIX 文件锁写回逻辑与 M1 YAML 的原子替换 API 闭环机制。
- **Unexplored areas**: 无

## Key Decisions Made
- Focus on search strategy using grep_search and find_by_name to locate code patterns.
- Formulate a clear, structured refactoring path based on Agora MCP routing, bus-foundation unification, and Omo Ingress/Bridge atomic lock-writing mechanisms.

## Artifact Index
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_survey_1/analysis.md — 重构设计调研报告
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_survey_1/progress.md — 进度跟踪
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_survey_1/handoff.md — Handoff 报告
