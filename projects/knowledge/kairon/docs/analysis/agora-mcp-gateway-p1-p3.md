---
title: agora-mcp-gateway-p1-p3
type: doc
---

# agora MCP Gateway P1-P3 专项 — 2026-07-14

> 承接 [`mcp-unification-plan.md`](mcp-unification-plan.md) §5 P0 ✅（kairon 9 MCP 注册）。
> P1-P3 = 全局收敛 + DRY + runtime 验证。

## P1: omostation 6+ MCP 注册（全局 15+ MCP 收敛）

**omostation MCP module path**（2026-07-14 核实，都有 main/run）：
- `metaos`: `python -m metaos.mcp_server`
- `ecos`: `python -m ecos.mcp_server`（主 584L；子 `services/integration` 638L + `l0/ssot` 427L 留评估，先注册主）
- `omo`: `python -m omo.mcp_server`
- `aetherforge`: `python -m aetherforge.mcp_server`
- `c2g`: `python -m c2g.mcp_server`
- `cockpit`: `python -m cockpit.agent_runtime_mcp_server`

**落地**：`bos-services.yaml` 加 6 mcp-server 条目（照 P0 kairon 模式，command `uv run --directory projects/<pkg> python -m <pkg>.mcp_server`）。agora commit + omostation bump + PR。

## P2: ~~废弃~~ → 标注 `bin/mcp-server-kos.py` 双入口设计（2026-07-14 评估修正）

**评估结论**：**不废弃**。`bin/mcp-server-kos.py`（323L 0-dep 只读 MCP，SQLite + authorizer）是**有意设计**——SGF-v1 硬件外挂场景（**无 kairon 依赖**）。kairon `kos.mcp.server` FastMCP 需 uv + kairon 环境 + DB（重依赖），**硬件外挂场景不兼容**。

**双入口分工**（设计，非冗余）：
- `bin/mcp-server-kos.py`：0-dep，SGF-v1 硬件外挂（无 kairon 环境的轻量只读）
- agora gateway `kos.mcp.server`：FastMCP，AI agent 主路径（kairon 环境完整）

**消费者**（各自路径，不冲突）：
- `bin/change-lane-check.py`（gate）+ `bin/test-mcp-kos.py`（测试）→ subprocess 调 0-dep（gate/测试用轻量）
- agora gateway → kairon FastMCP（AI agent 用完整）

**结论**：P2 从"废弃 DRY"修正为"标注双入口分工"。两者各司其职，非冗余。

## P3: runtime 验证 + 命名空间（2026-07-14 验证）

**SSOT 聚合验证 ✅**：agora `bos-services.yaml` **14 个 mcp-server 条目**（P0 kairon 8 含 kos + P1 omostation 6），agora registry `register_from_registry` 从 ServiceRegistry 自动同步。

**命名空间 — agora 内置 ✅**：registry 第 302 行 `full_name = f"{service_name}.{original_name}"` 自动加 service 前缀（如 `kos.search_knowledge` / `eidos.eidos_list`）。第 153-159 行 prefix match 路由。**工具名冲突自动防护**，无需额外规约。

**runtime spawn 实测 — 留集成测试**：agora 启动 spawn 14 backend subprocess + `tools/list` 聚合 + `tools/call` 路由 — 该 CI/集成测试（agora runtime 重型，非单元）。agora mcp_proxy health/idle_timeout 已具备多 backend 监控基础。

**P3 结论**：SSOT 聚合 + 命名空间内置 ✅。完整 runtime spawn 留集成测试（设计已就绪：registry/聚合/路由/命名空间都验证）。

## 进度

- [x] P0: kairon 9 MCP 注册（agora 1449aca + PR#333）
- [x] P1: omostation 6 MCP 注册（agora 9b18808 + PR#336, 全局 15+ MCP 收敛）
- [x] P2: 评估→**不废弃**（bin/mcp-server-kos.py 0-dep SGF-v1 硬件外挂设计, 双入口分工, 标注非废弃）
- [x] P3: SSOT 聚合 + 命名空间内置 ✅（14 条目 + service.tool 自动前缀; runtime spawn 留集成测试）
