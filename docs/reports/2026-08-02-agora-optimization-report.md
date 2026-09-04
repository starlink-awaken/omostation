---
type: ephemeral
created: 2026-09-03
---

# agora 全面优化报告（2026-08-02）

> **创建时间**：2026-08-02
> **范围**：agora（I0 织层）P0/P1/P2 优化项落地 + 待办记录
> **关联**：[`docs/reports/2026-08-02-agora-toolbox-deep-audit.md`](2026-08-02-agora-toolbox-deep-audit.md) · [`2026-08-02-agora-toolbox-remediation-plan.md`](2026-08-02-agora-toolbox-remediation-plan.md)

---

## 1. 本轮完成项

### P0-1 冗余直接依赖清理

- **问题**：`fastapi`/`uvicorn`/`prometheus-client`/`aiohttp` 源码零引用但直接声明
- **处理**：移除 `fastapi` + `prometheus-client`（`uvicorn` 保留为 fastmcp server extra 的间接依赖）
- **结果**：直接依赖 12 → 8，安全面缩减 1/3

### P0-2 硬编码路径 env 化

- **问题**：4 处 `/Users/xiamingxing/...` 字面量违反可移植性
- **处理**：
  - `resolver/api.py` WORKSPACE_ROOT fallback → `Path.home()/Workspace`
  - `mcp_proxy/manager.py` 同 → `os.path.expanduser("~/Workspace")`
  - `mcp/mcp_bootstrap.py` wps dist → `TOOLBOX_ROOT` env
  - `registry.yaml` → `~/ToolBox` 语义
- **结果**：`src/agora/` 下 0 处 `/Users/xiamingxing` 残留

### P1-4 吞异常修复

- **问题**：28 处 `except: pass`，其中 1 处真吞异常（`core/router.py` 压缩统计落库失败）
- **处理**：router.py 补 `logger.warning`；其余 27 处为合理豁免（CancelledError/TimeoutError/ImportError 等探测上下文）保持不变

### P1-5 死代码清理

- **处理**：删除 `server/mcp.py` `to_otel_json`（零引用）、`mcp/bos_protocol.py` `test_adapter`（零引用）

### P2-7 依赖升级

- **处理**：`uv lock --upgrade`（cryptography 50.0.0、uvicorn 0.52.1、fastmcp 3.4.5、sse-starlette 3.4.6 等）

### P2-8 env 配置收敛

- **处理**：`AGORA_INTERNAL_PORT`/`BOS_API_PORT` 收敛到 `config.py` 单一来源（`get_internal_port`/`get_api_port`），4 处重复引用统一

---

## 2. 验证

| 项 | 结果 |
|---|---|
| 全量回归 | **1479 passed / 0 failed**（与优化前完全一致） |
| ruff | 无新增错误（对比基线） |
| 硬编码残留 | 0 处 |

---

## 3. 待办（技术债，需专门 session）

### P1-3 tools_bos.py god module 拆分（deferred）

- **现状**：`server/tools_bos.py` 1626 行，`register_bos_tools` 单函数 1020 行（20+ MCP 工具闭包内嵌）
- **阻碍**：闭包引用全部内部函数（`_bos_domain_authorized` 10 次、`_get_inbox_paths` 6 次等）→ 拆子包会形成循环依赖；且大量测试 `from agora.server.tools_bos import ...` 需兼容 shim
- **建议**：独立重构 session，方案：`tools_bos/` 子包 + 顶层兼容 shim（re-export），按域拆 `inbox.py`/`bdsk.py`/`routing.py`/`registration.py`

### 其他观察（低优先）

- `cli/parser.py` build_parser 649 行（P2-9）
- `mcp_registry/orchestrator.py` reload_tool/ensure_tool_available 仅测试引用（死代码候选）
- 响应结构约定：18 个文件手写 `{"status": "ok"}`，可统一走 `_response.py`

---

*本轮优化 commit：agora `384cd6c`（refactor(agora): 全面优化）*
