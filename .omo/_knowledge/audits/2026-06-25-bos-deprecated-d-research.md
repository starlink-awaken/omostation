# BOS Deprecated 声明 D 调研 — agent-runtime 部分

> **TASK**: TASK-AB15691F (28 deprecated BOS 声明对齐, expires 2026-07-25)
> **调研者**: laowang (证据驱动 D 对齐)
> **日期**: 2026-06-25
> **范围**: agent-runtime(7) — 首批调研 (omo goals 证据最明确)

## 1. agent-runtime 真实位置 (已确认)

**功能已迁移到 cockpit** (omo goals/current.yaml:49 "M2 拆分 runtime+ext/cockpit"):
- `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` — **stdio MCP server** (`mcp.run(transport="stdio")`)
- `projects/cockpit/src/cockpit/agent_runtime_cli.py` — CLI (pyproject entry: `agent-runtime = cockpit.agent_runtime_cli:main`)
- `projects/cockpit/src/cockpit/agent_runtime_server.py` — runtime 核心

## 2. 对齐分析 (BOS 7 action vs cockpit 实现)

| BOS action | cockpit 实现 | 对齐方案 |
|-----------|:---:|---------|
| `chat` | ✅ MCP `chat(message, history_json)` | 改声明: transport→mcp_stdio, command 启动 cockpit agent_runtime_mcp_server |
| `run-task` | ✅ MCP `run_task(task_name)` | 同上 |
| `execute` | ❌ (run_task 近似?) | **决策点**: 映射 run_task or 删声明 |
| `list-tools` | ❌ cockpit 无 | **决策点**: 补 cockpit or 删 |
| `agent-list` | ❌ cockpit 无 | **决策点**: 补 or 删 |
| `status` | ❌ cockpit 无 | **决策点**: 补 or 删 |
| `task-status` | ❌ cockpit 无 | **决策点**: 补 or 删 |

**结论**: 7 个里仅 2 个 (chat/run-task) cockpit 明确实现。其余 5 个 cockpit 未实现 (部分迁移未完成)。

## 3. 对齐执行方案 (待专项)

chat/run-task 对齐 (最小可行):
```yaml
# agora/etc/bos-services.yaml 改 2 个声明:
- uri: "bos://capability/agent-runtime/chat"
  transport: mcp_stdio
  command: ["uv", "run", "--directory", "projects/cockpit", "python", "-m", "cockpit.agent_runtime_mcp_server"]
  # MCP 工具名: chat
- uri: "bos://capability/agent-runtime/run-task"
  transport: mcp_stdio
  command: ["uv", "run", "--directory", "projects/cockpit", "python", "-m", "cockpit.agent_runtime_mcp_server"]
  # MCP 工具名: run_task
```
涉及 3 处源同步 (agora services.py + yaml + omo omo_bos_seeds) + transport 变更测试。

5 个未实现的决策 (补 cockpit or 删声明): 需产品判断这些功能 (list-tools/agent-list/status/task-status/execute) 是否还需要。

## 4. 剩余 21 项待调研

| 类别 | 数量 | 调研线索 |
|------|:---:|---------|
| sharedbrain/sot-bridge | 8 | 查 8001 端口实况 (omo_health.py:37 `sharedbrain-bridge-mcp: 8001`) + debt 记录 |
| system/* | 9 | internal 缺 module_path, 查 agora 内部工具真实入口 |
| gbrain | 3 | mcp_proxy 缺 http_url, 查 gbrain MCP endpoint |
| protocols-layer | 1 | routes.json 有路由, 查有无实现 |

## 5. 关键教训

- **证据驱动要全类型扫描**: 第一轮 grep(.py/.ts) 说零硬依赖, 第二轮(.json/.yaml/.md) 翻出 routes.json+health 硬依赖 → 推翻一刀切删方案, 改 C+D
- **deprecated 机制价值**: 28 项分类跟踪, 区分"调研中"vs"真实新鸿沟", 不掩盖
- **部分迁移**: agent-runtime 不是废弃, 是迁移到 cockpit 但未完成 (2/7 实现)

## 6. gbrain 调研结论 (3 项, 有 6 消费者 — 必须修非删)

**真实接入**: stdio MCP (`projects/gbrain/src/mcp/server.ts`)
- `startMcpServer(engine: BrainEngine)` + `StdioServerTransport` (server.ts:11,50)
- port-registry.yaml: `gbrain: stdio` (同 cockpit-mcp/kairon/omo)
- 当前 BOS 声明 `mcp_proxy` (HTTP, 缺 http_url) 是**声明错误** — gbrain 真实是 stdio

**修复障碍**: startMcpServer 非自入口 (需传 engine 参数), cli.ts 无 `mcp` 子命令, 无现成 stdio 启动命令.
**修复方案**: 建 gbrain stdio 入口脚本 (如 `src/mcp/stdio-entry.ts` 调 startMcpServer + 传 engine), 然后 BOS 改 transport mcp_proxy→stdio + command `bun run src/mcp/stdio-entry.ts`. 涉及 3 处源 (yaml + omo seeds; services.py 无 gbrain 声明).

**消费者证据** (--consumers): gbrain/search → 6 consumers 含 `scripts/scenario_great_search.py` 真实脚本 → 必须修不能删.

## 7. 剩余修复复杂度评估

| 类别 | 数量 | 修复性质 | 复杂度 |
|------|:---:|---------|:---:|
| agent-runtime | 7 | 改声明指向 cockpit MCP (chat/run-task) + 5 个决策 | 中 |
| gbrain | 3 | **建 TS stdio 入口脚本** + 改 transport | 中-高 (跨 TS) |
| sharedbrain/sot-bridge | 8 | ✅ **已清理 (2026-06-25)** — 包不存在+8001不跑, 删声明+routes+health+seeds | 完成 |
| system/* | 9 | 补 internal module_path (查 agora 内部入口) | 中 |
| protocols-layer | 1 | 查有无实现 → 补/删 | 调研 |

**结论**: 21 项都是"查真实入口 + 改声明/建脚本"工程, 非机械修. 按 TASK-AB15691F 逐类推进, expires 2026-07-25.
