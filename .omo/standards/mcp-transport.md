# MCP 传输规范 MCP-01

## 原则
- 新 MCP Server 默认用 stdio 传输
- 需要网络暴露的用 SSE（HTTP 流）
- 统一超时: 30s
- 错误格式: {"error": {"code": "...", "message": "..."}}
- 每个 MCP Server 必须实现 `health` 工具

## 当前 MCP Server 传输方式

| 项目 | 传输 | 状态 |
|------|------|------|
| SharedBrain | stdio | ✅ |
| Forge | stdio | ✅ |
| ontoderive | stdio | ✅ |
| SSOT | stdio | ✅ |
| Iris | stdio | ✅ |
| eidos | stdio | ✅ |
| agentmesh | stdio+SSE | ✅ |
| KOS | stdio+SSE | ✅ |
| gbrain | stdio | ✅ |
| hermes-webui | WebSocket | ⚠️ 历史原因，保持 |
