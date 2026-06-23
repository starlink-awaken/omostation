# BRIEFING — 2026-06-23T10:31:00+08:00

## Mission
ECOS 跨层调用重构分析：重构 ECOS 工作流直调 aetherforge swarm 命令行 subprocess 为通过 Agora MCP 网格 BOS 协议进行 RPC 调用 (bos://capability/swarm/run)。

## 🔒 My Identity
- Archetype: Read-only Explorer
- Roles: m1_explorer_1
- Working directory: /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_1/
- Original parent: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Milestone: M1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Cannot modify any source code files
- Use Chinese for communication and reports

## Current Parent
- Conversation ID: d6d08efc-a7bd-44e1-8861-e985ac7a8c92
- Updated: 2026-06-23T10:45:00+08:00

## Investigation State
- **Explored paths**:
  - `projects/ecos/src/ecos/workflow/backends/swarm.py`
  - `projects/ecos/src/ecos/workflow/agora_mcp_backend.py`
  - `projects/agora/src/agora/server/tools_bos.py`
  - `projects/agora/etc/bos-services.yaml`
- **Key findings**:
  - 明确了 `swarm.py` 执行 subprocess 命令（`_CLI_PATHS`）和对 goal 等参数的处理逻辑。
  - 明确了 `agora_mcp_backend.py` 使用 `httpx` 调用 `resolve_bos_uri` 网格工具的具体实现。
  - 确定了 `resolve_bos_uri` 返回 `status == "ok"` 的 JSON 结构，并制定了 `result` 参数映射方法。
  - 确定了 `bos-services.yaml` 用于配置 `bos://capability/swarm/run` 的 stdio 映射方法。
- **Unexplored areas**: 无，所有调查已深入到源码级细节。

## Key Decisions Made
- 确定三级降级保护策略：RPC 优先 -> Subprocess 降级 -> Mock 兜底，保障业务连续性。
- 代码层面重用 `httpx` 工具并在 `swarm.py` 内实现本地方法，保证微服务解耦。

## Artifact Index
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_1/ORIGINAL_REQUEST.md — Original request log
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_1/BRIEFING.md — Briefing status
- /Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_m1_1/analysis.md — Detailed analysis report for M1
