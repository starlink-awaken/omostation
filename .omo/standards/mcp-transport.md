# MCP 传输规范 MCP-01

## 原则
- 新 MCP Server 默认用 stdio 传输
- 需要网络暴露的用 SSE（HTTP 流）
- 统一超时: 30s
- 错误格式: {"error": {"code": "...", "message": "..."}}
- 每个 MCP Server 必须实现 `health` 工具

## 当前 MCP Server 传输方式

| 项目 | 包位置 | 传输 | 状态 |
|------|---------|------|------|
| SharedBrain | `projects/SharedBrain/` | stdio | ✅ |
| kairon/agora | `projects/kairon/packages/agora/` | stdio+SSE | ✅ |
| kairon/ontoderive | `projects/kairon/packages/ontoderive/` | stdio | ✅ |
| kairon/ssot | `projects/kairon/packages/ssot/` | stdio | ✅ |
| kairon/iris | `projects/kairon/packages/iris/` | stdio | ✅ |
| kairon/eidos | `projects/kairon/packages/eidos/` | stdio | ✅ |
| kairon/kos | `projects/kairon/packages/kos/` | stdio+SSE | ✅ |
| kairon/forge | `projects/kairon/packages/forge/` | stdio | ✅ |
| kairon/minerva | `projects/kairon/packages/minerva/` | stdio | ✅ |
| kairon/metaos | `projects/kairon/packages/metaos/` | stdio | ✅ |
| agentmesh | `projects/agentmesh/` | stdio+SSE | ✅ |
| gbrain | `projects/gbrain/` | stdio | ✅ |
| hermes-webui | — | WebSocket | ⚠️ 历史原因，保持 |
