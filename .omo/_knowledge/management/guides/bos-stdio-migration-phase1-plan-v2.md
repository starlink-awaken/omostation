---
last_updated: 2026-08-25
---

# BOS stdio → mcp_proxy 迁移实施方案 (详细版)

> 日期: 2026-08-01
> 阶段: Phase 1 (MCP Server 服务)
> 状态: 实施中

## 1. 技术可行性分析

### 1.1 FastMCP 传输支持

所有 MCP Server 使用 FastMCP 框架，支持以下传输方式：
- `stdio` — 标准输入输出（当前）
- `sse` — Server-Sent Events
- `streamable-http` — HTTP 流式传输

**结论**: 技术上可行，所有 MCP Server 可以运行 as HTTP 服务。

### 1.2 迁移方案

**方案 A: mcp_proxy + HTTP 端点**（推荐）

```yaml
# Before
- uri: bos://memory/kos/mcp-server
  transport: stdio
  command:
  - python3
  - bin/gac/mcp-server-kos.py

# After
- uri: bos://memory/kos/mcp-server
  transport: mcp_proxy
  mcp_endpoint: http://localhost:8765/mcp
  package: kos-mcp
  description: KOS MCP Server (HTTP proxy mode)
```

**方案 B: mcp_proxy + 命令启动**（备用）

```yaml
- uri: bos://memory/kos/mcp-server
  transport: mcp_proxy
  command: python3
  args:
  - bin/gac/mcp-server-kos.py
  - --transport
  - http
  - --port
  - "8765"
  package: kos-mcp
```

## 2. 实施计划

### 2.1 Phase 1: 验证阶段（1天）

1. **验证 KOS MCP Server HTTP 模式**
   - 启动 KOS MCP Server with HTTP transport
   - 验证端点响应
   - 测试工具调用

2. **验证 agora mcp_proxy 集成**
   - 检查 agora mcp_proxy 配置
   - 验证路由正确性
   - 测试端到端调用

### 2.2 Phase 2: 迁移阶段（2天）

1. **更新 bos-services.yaml**
   - 修改 14 个服务的传输类型
   - 添加 mcp_endpoint 配置
   - 保留原始 command 作为备用

2. **创建启动脚本**
   - 为每个 MCP Server 创建 HTTP 启动脚本
   - 配置端口分配
   - 设置进程管理

3. **测试验证**
   - 单元测试
   - 集成测试
   - 性能测试

### 2.3 Phase 3: 监控阶段（1周）

1. **监控指标**
   - 延迟变化
   - 错误率
   - 资源使用

2. **优化调整**
   - 根据监控数据调整配置
   - 优化端口分配
   - 处理异常情况

## 3. 端口分配方案

| 服务 | 端口 | 说明 |
|------|------|------|
| kos-mcp | 8765 | KOS MCP Server |
| eidos-mcp | 8766 | Eidos MCP Server |
| ontoderive-mcp | 8767 | Ontoderive MCP Server |
| minerva-mcp | 8768 | Minerva MCP Server |
| kronos-mcp | 8769 | Kronos MCP Server |
| iris-mcp | 8770 | Iris MCP Server |
| sophia-mcp | 8771 | Sophia MCP Server |
| forge-mcp | 8772 | Forge MCP Server |
| metaos-mcp | 8773 | MetaOS MCP Server |
| ecos-mcp | 8774 | ECOS MCP Server |
| omo-mcp | 8775 | OMO MCP Server |
| aetherforge-mcp | 8776 | AetherForge MCP Server |
| c2g-mcp | 8777 | C2G MCP Server |
| cockpit-mcp | 8778 | Cockpit MCP Server |

## 4. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| HTTP 端点不可用 | 低 | 高 | 保留 stdio 作为备用 |
| 端口冲突 | 中 | 中 | 端口分配表 + 冲突检测 |
| 延迟增加 | 低 | 中 | 性能基准测试 |
| 配置错误 | 中 | 中 | 配置验证脚本 |

## 5. 回滚方案

如果迁移失败，可以快速回滚：
1. 恢复 bos-services.yaml 原始配置
2. 停止 HTTP 服务
3. 重启 agora 服务
4. 验证 stdio 传输恢复正常

## 6. 成功标准

- [ ] 14 个服务全部迁移到 mcp_proxy
- [ ] 所有服务端点可达
- [ ] 延迟增加 < 100ms
- [ ] 无功能回归
- [ ] 监控指标正常
