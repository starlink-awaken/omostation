---
title: mcp-unification-plan
type: doc
---

# MCP 统一规划 — 2026-07-13

> 承接 [`architecture-audit-2026-07-13.md`](architecture-audit-2026-07-13.md) §2/§4 P0。
> 目标：kairon 9 个 MCP server 协议统一 FastMCP + 面收敛。

## 1. 现状（9 MCP server，协议割裂）

| 包 | 工具数 | 协议 | 状态 |
|----|--------|------|------|
| kos | 26 | **stdio 手写** | ⬜ 待迁（大活）|
| minerva | 8 | FastMCP | ✅ 已统一 |
| **eidos** | 7 | **FastMCP** | ✅ **已落地**（main 接闲置 app，4f2c51b）|
| ontoderive | 11 | FastMCP | ✅ 已统一 |
| kronos | 16 | FastMCP | ✅ 已统一 |
| iris | 8 | FastMCP | ✅ 已统一 |
| sophia | 8 | FastMCP | ✅ 已统一 |
| forge | 7 | FastMCP | ✅ 已统一 |
| ontoderive/toolforge | 0(委托) | FastMCP | 兼容委托壳（本体已注册 ToolForge）|

**协议割裂真相**：9 个里 **7 个已 FastMCP**，只有 **kos（26 工具，stdio 手写）** 和 eidos（已修）是 stdio。eidos 是"app 建好 main 没接"的半接上（decl-exec-gap），已修。**剩 kos 一个 stdio 堡垒**。

## 2. 已落地：eidos（第一步，4f2c51b）

**问题**：`_handle_fastmcp()` 早已建好 FastMCP app（7 个 @app.tool）但 `main()` 走手写 stdio loop 没接 app（app 闲置）。

**修复**：main 调 `_handle_fastmcp()` + `app.run()`（FastMCP stdio），fastmcp 未装 `sys.exit(1)`（非 fallback slop，跟 iris 模式）。pyproject 加 `[mcp]` optional dep（fastmcp>=2.0）。

**模式**：小改（app 已就绪，只接 main）。**kos 不适用此模式**（kos 无闲置 app）。

## 3. 待迁：kos（大活，专项多轮）

**kos MCP 规模**：
- 26 工具（TOOLS_SCHEMA 声明式 + tool_ 函数 + handlers dict dispatch）
- **run_stdio 144L 手写 JSON-RPC**（read stdin / parse / method dispatch / send_jsonrpc）
- 41 个 dispatch lambda
- **命名空间工具**：`self.get_profile` / `collab.create_task` / `consensus.create`（FastMCP 工具名点号要特殊处理）
- 无闲置 FastMCP app（从头建）

**迁移步骤**（专项，~1-2 天）：
1. 建 `_create_fastmcp_app()`：26 工具 `@mcp.tool` 装饰 + 完整类型注解（现多 `type:ignore`，FastMCP schema 生成要注解）
2. 命名空间工具处理：`self.*/collab.*/consensus.*` → FastMCP 工具名映射（或扁平化 `self_get_profile`）
3. main 走 `app.run()`，run_stdio 144L 废弃（保留 handle 兼容 or 删）
4. 类型注解补全（26 tool_ 函数签名）
5. 测试：MCP 协议行为不变（tools/list + tools/call 响应格式）

> **✅ 已落地 (2026-07-14, commit 51b0749)**：建 `fastmcp_app.py _create_fastmcp_app`（44 工具 @app.tool：27 本体 + 14 命名空间 + 3 FastMCP 内置）。参数从 dispatch lambda 映射。FastMCP 3.4.2 **不支持 `**kwargs`** → 命名空间用 `arguments: dict | None` 参数。main 走 `app.run()`（延迟 import 解循环），run_stdio 保留独立函数。pyproject 加 `fastmcp>=2.0`。验证 `list_tools()` 44 工具注册。**stdio 堡垒破，9 MCP 协议统一完成**。

**风险**：
- 命名空间工具（FastMCP 点号工具名支持？要验证）
- 类型注解补全工作量大（26 函数）
- SELF_HANDLERS/COLLAB_HANDLERS/CONSENSUS_HANDLERS 委托模式 FastMCP 适配

**不该草率**：kos 是最大 MCP（26 工具，1114L），迁移要专项多轮 + 充分测试。

## 4. 迁移路径

```
✅ eidos (4f2c51b): main 接闲置 app (小改, 模式 A)
✅ minerva/ontoderive/kronos/iris/sophia/forge: 已 FastMCP (无需迁)
✅ kos (51b0749): 从头建 fastmcp_app.py _create_fastmcp_app (44 工具, 模式 B) — stdio 堡垒破
⬜ agora 聚合: I0 hub 统一 MCP 面 (架构级, 跨仓 omostation)
```

**协议统一完成**：9 MCP 全 FastMCP（kos stdio 堡垒已破）。剩 agora 聚合（架构级，跨仓）。

## 5. agora MCP 聚合（架构级，跨仓）— **P0 已落地 ✅**

> **2026-07-14 P0 落地** (agora 1449aca + omostation PR#333 merged): agora mcp_proxy 已是 gateway (`ProxyRegistry` 工具聚合+路由+stdio subprocess)。**kairon 7 MCP backend 注册完成** (eidos/ontoderive/minerva/kronos/iris/sophia/forge, `bos-services.yaml` 声明式 command `uv run python -m <pkg>.mcp_server`)。kos 已接 (`bin/mcp-server-kos.py`)。**agora I0 hub subprocess 代理 kairon 9 FastMCP** (复用协议统一成果, 不重造 0-dep 定制)。

**P0 完成**: agora gateway 接线 — kairon 9 MCP 全注册 (声明式)。AI agent 经 agora 单点接入, agora `tools/list` 聚合 + `tools/call` 路由。

**剩余 (P1-P3) — 全完成 ✅**（详见 [`agora-mcp-gateway-p1-p3.md`](agora-mcp-gateway-p1-p3.md)）:
- **P1 ✅**（agora 9b18808 + PR#336）: omostation 6 MCP 注册（metaos/ecos/omo/aetherforge/c2g/cockpit）— 全局 14 mcp-server 条目收敛
- **P2 ✅**（评估修正→不废弃）: `bin/mcp-server-kos.py` 0-dep SGF-v1 硬件外挂设计, 双入口分工（0-dep 轻量 + agora gateway FastMCP）, 标注非废弃
- **P3 ✅**: SSOT 聚合验证（14 条目）+ agora 命名空间内置（registry `service.tool` 自动前缀, 冲突防护）; runtime spawn 留集成测试

## 6. 本规划基线

- 2026-07-13，eidos 落地后
- 下一步：kos 迁移专项（大活）or agora 聚合（跨仓）
- 关联：[`architecture-audit-2026-07-13.md`](architecture-audit-2026-07-13.md) §2/§4
