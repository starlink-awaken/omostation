---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# MCP Tool and Transport Standard

> 状态: active | 版本: v1.0
> 合并来源: `MCP_STANDARDS.md`, `mcp-transport.md`
> 适用范围: 所有 MCP server / tool / transport 入口

---

## 1. Tool return contract

### 1.1 Return type

所有 `@mcp.tool()` 函数必须返回 `dict`，由框架统一序列化。

```python
return {"status": "ok", "format_version": FORMAT_VERSION, ...}
```

禁止：

- 手工 `json.dumps(...)` 作为主要返回路径
- 返回裸字符串
- 用不一致的 status 值替代 `ok` / `error`

### 1.2 Required fields

每个 tool 返回值必须显式包含：

- `status`
- `format_version`

推荐使用 `_ok()` / `_error()` 辅助函数，但 `format_version` 仍应在 tool 函数内显式出现，便于静态检查。

### 1.3 Error path

错误返回统一格式：

```python
{"status": "error", "error": "<message>", "format_version": FORMAT_VERSION}
```

禁止直接回传 traceback 或未脱敏内部细节。

## 2. Transport defaults

- 新 MCP server 默认使用 **stdio**
- 需要网络暴露或流式接入时使用 **SSE / streamable HTTP**
- 默认超时：`30s`
- 每个 MCP server 必须提供 `health`/状态能力。作为外部 Worker 接入时，必须支持心跳接口（`mcp.tool: heartbeat` 或被动响应看门狗探测），Coordinator 将据此刷新 Lease 续期。

## 3. Server baseline

每个 MCP server 至少应满足：

1. 明确 transport
2. 明确 health probe
3. 统一错误格式
4. 统一 tool 返回契约
5. 在文档或 registry 中声明 operation level / risk boundary

## 4. Recommended pattern

```python
def _ok(data: dict) -> dict:
    return {"status": "ok", **data}


def _error(message: str) -> dict:
    return {"status": "error", "error": message, "format_version": FORMAT_VERSION}
```

Tool 示例：

```python
@mcp.tool()
def health() -> dict:
    return _ok({"format_version": FORMAT_VERSION, "action": "healthy"})
```

## 5. Historical notes

- `MCP_STANDARDS.md` 保留为 legacy detailed source
- `mcp-transport.md` 保留为 legacy transport snapshot
- 新的 workflow 只应直接引用本文件
