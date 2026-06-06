# P0-TASKOBJECT_LIVE 设计方案

> 2026-06-06 | 状态: design-locked

## 目标
TaskObject 从"信封日志"升级为"真正的任务路由"——Hermes 通过 TaskObject 自动路由任务到对应服务。

## 现状
- TaskObject v1 规范 ✅
- `taskobject_adapter.py` ✅ — 适配器框架
- `mcp_server.py:_record_taskobject_envelope()` ✅ — 信封日志
- 缺少: TaskObject → Hermes 的实际路由链路

## 设计方案

### 架构
```
Hermes CLI
  │
  └─→ TaskObject 信封
        ├─→ intent: run  →  dispatch to agent-runtime:9876
        ├─→ intent: query →  dispatch to MCP tool (runtime/kos/minerva)
        └─→ intent: control → dispatch to .omo/ governance
```

### 实施步骤
1. `runtime cli` 添加 `taskobject dispatch <envelope.json>` 命令
   - 读取 JSON 信封 → 调用 `taskobject_adapter.dispatch_taskobject()`
   - 返回结果
2. 在 `mcp_server.py` 中注册 `dispatch_taskobject` 工具
   - 接受 TaskObject 信封 → 解析 intent → 调用对应 MCP 工具

### 验证
```bash
echo '{"id":"test-1","intent":"query","target":{"service":"runtime","tool":"health_check","params":{}},"callback":{"channel":"stdout","format":"json"}}' | runtime taskobject dispatch -
```

参考: `protocols/task-object-v1.md`, `runtime/taskobject_adapter.py`
